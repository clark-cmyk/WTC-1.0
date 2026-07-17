#!/usr/bin/env python3
"""
Fixed artifacts/generate_btc_basis.py - wired builder
"""
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from whinfell_pipeline.lego.data_loader import load_historical_barchart_curve, compute_quartiles

def build_btc_basis_node(full_historical=True, incremental_csv=None):
    """Full BTC Basis node builder with wiring to real data."""
    history_df = load_historical_barchart_curve()

    if incremental_csv and Path(incremental_csv).exists():
        try:
            incr_df = pd.read_csv(incremental_csv)
            print(f"✅ Loaded CSV with columns: {list(incr_df.columns)}")
            if 'BTCXAU Close' in incr_df.columns:
                incr_df['spot'] = pd.to_numeric(incr_df['BTCXAU Close'], errors='coerce')
                print("✅ Mapped BTCXAU Close to spot")
            else:
                spot_col = next((col for col in incr_df.columns if any(x in col.lower() for x in ['close', 'spot', 'price'])), None)
                if spot_col:
                    incr_df['spot'] = pd.to_numeric(incr_df[spot_col], errors='coerce')
                    print(f"✅ Mapped {spot_col} to spot")
            incr_df['basis_pct'] = incr_df.get('basis_pct', 0.0)
            if not history_df.empty:
                history_df = pd.concat([history_df, incr_df], ignore_index=True).drop_duplicates()
            else:
                history_df = incr_df.copy()
        except Exception as e:
            print(f"CSV load error: {e}")

    if 'basis_pct' not in history_df.columns or history_df['basis_pct'].isna().all():
        history_df['basis_pct'] = 0.0

    latest = history_df.iloc[-1] if not history_df.empty else {}
    current = {
        "date": str(latest.get('date', datetime.now().date())),
        "spot": float(latest.get('spot', 0)),
        "futures": float(latest.get('futures', 0)),
        "basis_dollar": 0.0,
        "basis_pct": float(latest.get('basis_pct', 0))
    }

    quartiles = compute_quartiles(history_df)

    hist_list = []
    for _, r in history_df.iterrows():
        hist_list.append({
            "date": str(r.get('date', '')),
            "spot": float(r.get('spot', 0)),
            "futures": float(r.get('futures', current['futures'])),
            "basis_pct": float(r.get('basis_pct', current['basis_pct']))
        })

    node_data = {
        "node": "btc_basis",
        "timestamp": datetime.now().isoformat(),
        "current": current,
        "history": hist_list,
        "quartiles": quartiles,
        "meta": {"source": "BasisWatch/CSV + barchart/v1", "total_records": len(history_df)}
    }

    Path("data/nodes").mkdir(parents=True, exist_ok=True)
    with open("data/nodes/btc_basis.json", "w") as f:
        json.dump(node_data, f, indent=2, default=str)

    print("✅ Node built successfully. records:", len(hist_list))
    return node_data

if __name__ == "__main__":
    build_btc_basis_node()