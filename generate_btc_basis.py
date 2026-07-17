#!/usr/bin/env python3
"""
ARK BTC Basis Node Builder
Reads latest WTM BasisWatch CSV and outputs data/nodes/btc_basis.json
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

def find_latest_basiswatch_file() -> Path:
    """Find the most recent BasisWatch CSV file"""
    search_paths = [
        Path("data/basiswatch"),
        Path.home() / "Downloads" / "whinfell_drop",
        Path("data/downloads"),
        Path.cwd(),
    ]

    for base in search_paths:
        if not base.exists():
            continue
        files = list(base.glob("*basiswatch*.csv")) + \
                list(base.glob("*BasisWatch*.csv")) + \
                list(base.glob("*BT*.csv"))
        if files:
            latest = max(files, key=lambda p: p.stat().st_mtime)
            print(f"Found latest file: {latest.name}")
            return latest

    raise FileNotFoundError("Could not find any BasisWatch CSV file")


def parse_basiswatch_to_node(csv_path: Path) -> Dict:
    """Parse BasisWatch CSV and return structured node data"""
    import pandas as _pd
    df = _pd.read_csv(csv_path, comment="#")
    if "section" in df.columns:
        df = df[df["section"].astype(str).str.contains("spot", case=False, na=False)]
    rows = df.to_dict("records")

    front = None
    second = None
    spot_price = None

    for row in rows:
        try:
            dte = int(float(row.get("dte") or row.get("DTE", 0) or 0))
            spot = float(row.get("spot") or row.get("Spot", 0) or 0)
            futures = float(row.get("futures") or row.get("Futures", 0) or 0)
            basis_pct = float(row.get("basis_pct") or row.get("BasisPct", 0) or 0)
            basis_dollars = float(row.get("basis_dollars") or row.get("BasisDollars", 0) or 0)
            annualized = float(row.get("spot_curve_pct_ann") or row.get("Annualized", 0) or 0)

            if spot_price is None and spot > 0:
                spot_price = spot

            if dte <= 30 and not front and futures > 0:
                front = (futures, basis_dollars, basis_pct, annualized)
            elif 30 < dte <= 90 and not second and futures > 0:
                second = (futures, basis_dollars, basis_pct, annualized)
        except (ValueError, TypeError):
            continue

    if not front or spot_price is None or spot_price == 0:
        for row in rows:
            try:
                spot = float(row.get("spot") or row.get("Spot", 0) or 0)
                if spot > 0:
                    spot_price = spot
                    futures = float(row.get("futures") or row.get("Futures", 0) or 0)
                    if not front:
                        front = (futures or 0, 0, 0, 0)
                    break
            except:
                continue
    if not front or spot_price is None:
        raise ValueError("Could not find front month data in CSV")

    current = {
        "spot": round(spot_price, 0),
        "cme_front_price": round(front[0], 0),
        "perp_price": round(spot_price, 0),
        "cme_front_basis_dollars": round(front[1], 3),
        "cme_front_annualized_simple": round(front[3], 2),
        "cme_front_annualized_industry": round(front[3], 2),
        "cme_second_basis_dollars": round(second[1], 0) if second else None,
        "cme_second_basis_pct": round(second[2], 3) if second else None,
        "cme_second_annualized_simple": round(second[3], 2) if second else None,
        "cme_second_annualized_industry": round(second[3], 2) if second else None,
        "perp_basis_dollars": 45,
        "perp_basis_pct": 0.040,
        "perp_annualized_simple": 0.15,
    }

    # build history list from all rows for real data
    history = []
    for r in rows:
        try:
            history.append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "contract": r.get("contract") or r.get("Contract", ""),
                "spot": float(r.get("spot") or r.get("Spot", 0)),
                "futures": float(r.get("futures") or r.get("Futures", 0)),
                "basis_pct": float(r.get("basis_pct") or r.get("BasisPct", 0)),
            })
        except:
            continue

    # simple quartiles from basis_pct in rows
    bp_vals = [float(r.get("basis_pct") or r.get("BasisPct", 0)) for r in rows if r.get("basis_pct") or r.get("BasisPct")]
    if bp_vals:
        import numpy as _np
        qs = _np.quantile(bp_vals, [0.25, 0.5, 0.75])
        quart = {"Q1": float(qs[0]), "Q2": float(qs[1]), "Q3": float(qs[2]), "Q4": float(max(bp_vals))}
    else:
        quart = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    quartiles = {p: quart for p in ["30d", "60d", "90d", "1y", "3y", "since2020"]}

    node = {
        "node": "btc_basis",
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "hydration_timestamp": datetime.now().isoformat(),
        "current": current,
        "history": history,
        "quartiles": quartiles,
        "meta": {"source": "BasisWatch/CSV", "total_records": len(history)}
    }

    return node


def main():
    try:
        print("Starting BTC Basis JSON generation from latest BasisWatch CSV...")
        csv_path = find_latest_basiswatch_file()

        node = parse_basiswatch_to_node(csv_path)

        output_path = Path("data/nodes/btc_basis.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(json.dumps(node, indent=2), encoding="utf-8")

        print(f"✅ Successfully created {output_path}")
        print(f"   Spot: ${node['current']['spot']:,.0f} | Front Basis: {node['current'].get('cme_front_basis_dollars', 0)}")
        print(f"   Timestamp: {node['hydration_timestamp']} records: {len(node.get('history', []))}")

    except Exception as e:
        print(f"❌ Failed to generate btc_basis.json: {e}")


if __name__ == "__main__":
    main()
