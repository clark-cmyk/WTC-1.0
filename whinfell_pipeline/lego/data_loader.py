import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

def load_historical_barchart_curve(symbol="BTC", start="2020-01-01"):
    """Load historical BTC spot from barchart (from 2020-01-01) + latest basis from basiswatch."""
    records = []

    # Primary: historical spot from barchart/v1, filtered to start date
    barchart_file = Path("data/barchart/v1/barchart_core_history.json")
    if barchart_file.exists():
        try:
            with open(barchart_file) as f:
                data = json.load(f)
            for r in data.get("records", []):
                if r.get("raw_symbol") == "^BTCUSD":
                    for pt in r.get("points", []):
                        if pt.get("date") and pt.get("close") is not None:
                            if pt["date"] >= start:
                                records.append({
                                    "date": pt["date"],
                                    "spot": float(pt["close"]),
                                    "futures": 0.0,
                                    "basis_pct": 0.0
                                })
                    break
        except Exception as e:
            print(f"barchart load err: {e}")

    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")

    # Overlay latest from basiswatch for current spot/futures/basis_pct
    basis_dir = Path("data/basiswatch")
    basis_files = list(basis_dir.glob("*wtm_basiswatch_BTC*.csv")) + list(basis_dir.glob("*basiswatch*.csv"))
    if basis_files:
        basis_file = max(basis_files, key=lambda p: p.stat().st_mtime)
        try:
            df_basis = pd.read_csv(basis_file, comment="#")
            if "section" in df_basis.columns:
                spot_rows = df_basis[df_basis["section"].astype(str).str.contains("spot", case=False, na=False)]
            else:
                spot_rows = df_basis
            if not spot_rows.empty:
                row = spot_rows.iloc[0]
                latest_spot = float(row.get("spot", row.get("BTCXAU Close", 0)) or 0)
                latest_fut = float(row.get("futures", 0) or 0)
                latest_bp = float(row.get("basis_pct", 0) or 0)
                latest_date = str(datetime.now().date())
                if not df.empty:
                    # Update last row with latest basis info
                    df.loc[df.index[-1], "spot"] = latest_spot
                    df.loc[df.index[-1], "futures"] = latest_fut
                    df.loc[df.index[-1], "basis_pct"] = latest_bp
                    df.loc[df.index[-1], "date"] = pd.to_datetime(latest_date)
                else:
                    df = pd.DataFrame([{
                        "date": pd.to_datetime(latest_date),
                        "spot": latest_spot,
                        "futures": latest_fut,
                        "basis_pct": latest_bp
                    }])
        except Exception as e:
            print(f"basiswatch load err: {e}")

    if df.empty:
        df = pd.DataFrame([{"date": pd.to_datetime(start), "spot": 0, "futures": 0, "basis_pct": 0}])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    for col in ["spot", "futures", "basis_pct"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df

def incremental_update_30d(latest_csv):
    if Path(latest_csv).exists():
        return pd.read_csv(latest_csv)
    return pd.DataFrame()

def compute_quartiles(history_df, periods=None):
    if periods is None:
        periods = ["30d", "60d", "90d", "1y", "3y", "since2020"]
    if history_df.empty or "basis_pct" not in history_df.columns:
        return {p: {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0} for p in periods}
    vals = history_df["basis_pct"].dropna()
    if len(vals) == 0:
        return {p: {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0} for p in periods}
    q25 = float(vals.quantile(0.25))
    q50 = float(vals.quantile(0.5))
    q75 = float(vals.quantile(0.75))
    qmax = float(vals.max())
    quart = {"Q1": q25, "Q2": q50, "Q3": q75, "Q4": qmax}
    return {p: quart for p in periods}
