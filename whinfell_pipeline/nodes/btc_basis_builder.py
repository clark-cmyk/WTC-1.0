import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from whinfell_pipeline.lego.data_loader import load_historical_barchart_curve, incremental_update_30d, compute_quartiles

def build_btc_basis_node(full_historical=True, incremental_csv=None):
    history_df = load_historical_barchart_curve()
    if incremental_csv and Path(incremental_csv).exists():
        try:
            incr_df = pd.read_csv(incremental_csv)
            print("Loaded columns:", list(incr_df.columns))
            if 'BTCXAU Close' in incr_df.columns:
                incr_df['spot'] = pd.to_numeric(incr_df['BTCXAU Close'], errors='coerce')
            elif 'spot' not in incr_df.columns:
                spot_col = next((c for c in incr_df.columns if 'close' in c.lower() or 'spot' in c.lower() or 'price' in c.lower()), None)
                if spot_col:
                    incr_df['spot'] = pd.to_numeric(incr_df[spot_col], errors='coerce')
            if not history_df.empty and not incr_df.empty:
                history_df = pd.concat([history_df, incr_df], ignore_index=True).drop_duplicates()
            else:
                history_df = incr_df if not incr_df.empty else history_df
        except Exception as e:
            print(f"incr csv err: {e}")
    latest = history_df.iloc[-1].to_dict() if not history_df.empty else {}
    current = {
        "date": str(latest.get('date', datetime.now().date())),
        "spot": float(latest.get('spot', 0)),
        "futures": float(latest.get('futures', 0)),
        "basis_dollar": float(latest.get('basis_dollars', 0)),
        "basis_pct": float(latest.get('basis_pct', 0))
    }
    # populate history as list of dicts
    hist_list = []
    for _, row in history_df.iterrows():
        hist_list.append({
            "date": str(row.get('date', '')),
            "spot": float(row.get('spot', 0)),
            "futures": float(row.get('futures', 0)) if 'futures' in row else current["futures"],
            "basis_pct": float(row.get('basis_pct', 0)) if 'basis_pct' in row else current["basis_pct"]
        })
    quartiles = compute_quartiles(history_df)
    node_data = {
        "node": "btc_basis",
        "timestamp": datetime.now().isoformat(),
        "current": current,
        "history": hist_list,
        "quartiles": quartiles,
        "meta": {"source": "barchart/v1 + basiswatch", "total_records": len(history_df)}
    }
    Path("data/nodes").mkdir(parents=True, exist_ok=True)
    with open("data/nodes/btc_basis.json", "w") as f:
        json.dump(node_data, f, indent=2, default=str)
    print("✅ Built. Spot:", current["spot"], "records:", len(hist_list), "timestamp updated")
    return node_data
