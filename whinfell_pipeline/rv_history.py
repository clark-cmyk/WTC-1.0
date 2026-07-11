"""ARCH-1 — consolidated RV history for quartile horizons."""

from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from whinfell_pipeline.data_dictionary import get_rv_series_registry
from whinfell_pipeline.node_cockpits import default_spread_history_path

# Koyfin wide-export column → rv_series history_key (ARCH-1 live quartiles)
_KOYFIN_DIRECT_COLUMNS: dict[str, str] = {
    "sofr close": "SOFR",
    "btcusd / spy corr": "BTC_SPY_CORR",
    "iwm / spy corr": "IWM_SPY",
}

_KOYFIN_RATIO_PAIRS: dict[str, tuple[str, str]] = {
    "HYG_LQD": ("HYG Close", "LQD Close"),
    "IBIT_QQQ": ("IBIT Close", "QQQ Close"),
}


def default_dated_series_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "rv" / "v1" / "dated_series_history.json"


def default_curve_history_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "barchart" / "v1" / "barchart_curve_history.json"


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return list(payload.get("records") or [])


def _points_from_record(rec: dict[str, Any]) -> list[tuple[str, float]]:
    series: list[tuple[str, float]] = []
    for pt in rec.get("points") or []:
        if not isinstance(pt, dict):
            continue
        d = str(pt.get("date") or "")
        close = pt.get("close")
        if d and close is not None:
            series.append((d, float(close)))
    latest = rec.get("latest")
    if isinstance(latest, dict) and latest.get("close") is not None:
        d = str(latest.get("date") or "")
        if d:
            series.append((d, float(latest["close"])))
    return sorted(series, key=lambda x: x[0])


def _index_barchart_records(records: list[dict[str, Any]]) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        pts = _points_from_record(rec)
        if not pts:
            continue
        keys = {
            str(rec.get("raw_symbol") or ""),
            str(rec.get("canonical_id") or ""),
        }
        spread_meta = rec.get("spread_meta") or {}
        if isinstance(spread_meta, dict):
            for leg in spread_meta.get("spread_legs") or []:
                keys.add(str(leg))
        for key in keys:
            k = key.strip().upper()
            if not k:
                continue
            existing = out.get(k, [])
            merged = sorted(set(existing + pts), key=lambda x: x[0])
            out[k] = merged
    return out


def _load_dated_series_bundle(path: Path) -> dict[str, list[tuple[str, float]]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, list[tuple[str, float]]] = {}
    for key, block in (payload.get("series") or {}).items():
        if not isinstance(block, dict):
            continue
        pts: list[tuple[str, float]] = []
        for pt in block.get("points") or []:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                pts.append((str(pt[0]), float(pt[1])))
            elif isinstance(pt, dict):
                d = str(pt.get("date") or "")
                v = pt.get("value")
                if d and v is not None:
                    pts.append((d, float(v)))
        if pts:
            out[str(key).upper()] = sorted(pts, key=lambda x: x[0])
    return out


def _lookup_history(
    history_key: str,
    spread_idx: dict[str, list[tuple[str, float]]],
    dated_idx: dict[str, list[tuple[str, float]]],
) -> list[tuple[str, float]]:
    key = history_key.upper()
    if key in dated_idx and len(dated_idx[key]) >= 2:
        return dated_idx[key]
    if key in spread_idx and len(spread_idx[key]) >= 2:
        return spread_idx[key]
    for idx in (spread_idx, dated_idx):
        for sym, vals in idx.items():
            if key in sym.upper() and len(vals) >= 2:
                return vals
    # Single-point barchart stub — use dated bundle fallback
    if key in dated_idx:
        return dated_idx[key]
    return []


def _parse_koyfin_date(raw: str) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    for fmt in ("%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _header_index(headers: list[str]) -> dict[str, str]:
    return {h.strip().lower(): h for h in headers if h and h.strip()}


def _series_from_wide_csv(path: Path) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = list(reader.fieldnames or [])
            if not headers:
                return out
            idx = _header_index(headers)
            date_col = idx.get("date")
            if not date_col:
                return out

            direct_cols: dict[str, str] = {}
            for col_lower, hk in _KOYFIN_DIRECT_COLUMNS.items():
                if col_lower in idx:
                    direct_cols[idx[col_lower]] = hk

            ratio_cols: dict[str, tuple[str, str]] = {}
            for hk, (num_pat, den_pat) in _KOYFIN_RATIO_PAIRS.items():
                num = idx.get(num_pat.lower())
                den = idx.get(den_pat.lower())
                if num and den:
                    ratio_cols[hk] = (num, den)

            for row in reader:
                d = _parse_koyfin_date(row.get(date_col) or "")
                if not d:
                    continue
                for col, hk in direct_cols.items():
                    val = row.get(col)
                    if val is None or str(val).strip() == "":
                        continue
                    try:
                        v = float(str(val).replace(",", ""))
                    except ValueError:
                        continue
                    out.setdefault(hk, []).append((d, v))
                for hk, (num_col, den_col) in ratio_cols.items():
                    try:
                        num = float(str(row.get(num_col) or "").replace(",", ""))
                        den = float(str(row.get(den_col) or "").replace(",", ""))
                    except ValueError:
                        continue
                    if den == 0:
                        continue
                    out.setdefault(hk, []).append((d, round(num / den, 6)))

            for hk in list(out.keys()):
                out[hk] = sorted(out[hk], key=lambda x: x[0])
    except OSError:
        return {}
    return out


def load_koyfin_rv_series(repo_root: Path | None = None) -> dict[str, list[tuple[str, float]]]:
    """Extract RV history from staged Koyfin wide exports (rates/equities/credit)."""
    root = repo_root or Path(__file__).resolve().parents[1]
    staged = root / "staged_raw"
    patterns = ("rates_*.csv", "equities_*.csv", "credit_*.csv")
    candidates: list[Path] = []
    for pat in patterns:
        candidates.extend(staged.glob(f"source=koyfin/dataset=*/{pat}"))
        candidates.extend(staged.glob(f"**/source=koyfin/**/{pat}"))
    candidates = sorted({p.resolve() for p in candidates if p.is_file()}, key=lambda p: p.stat().st_mtime, reverse=True)

    merged: dict[str, list[tuple[str, float]]] = {}
    for path in candidates[:6]:
        chunk = _series_from_wide_csv(path)
        for hk, vals in chunk.items():
            if len(vals) >= 2 and (hk not in merged or len(vals) > len(merged[hk])):
                merged[hk] = vals
    return merged


def load_rv_history(repo_root: Path | None = None) -> dict[str, list[tuple[str, float]]]:
    """Load merged history keyed by rv_series history_key."""
    root = repo_root or Path(__file__).resolve().parents[1]
    spread_path = default_spread_history_path(root)
    curve_path = default_curve_history_path(root)
    dated_path = default_dated_series_path(root)

    spread_idx = _index_barchart_records(_load_json_records(spread_path))
    curve_idx = _index_barchart_records(_load_json_records(curve_path))
    for k, v in curve_idx.items():
        if k not in spread_idx or len(v) > len(spread_idx.get(k, [])):
            spread_idx[k] = v

    dated_idx = _load_dated_series_bundle(dated_path)
    koyfin_idx = load_koyfin_rv_series(root)

    reg = get_rv_series_registry()
    out: dict[str, list[tuple[str, float]]] = {}
    for row in reg.get("series", {}).values():
        if not isinstance(row, dict):
            continue
        hk = str(row.get("history_key") or "")
        if not hk:
            continue
        key = hk.upper()
        if key in koyfin_idx and len(koyfin_idx[key]) >= 2:
            out[key] = koyfin_idx[key]
            continue
        vals = _lookup_history(hk, spread_idx, dated_idx)
        if vals:
            out[key] = vals
    return out


def ensure_dated_series_fixture(repo_root: Path | None = None, *, sessions: int = 800) -> Path:
    """Write deterministic dated series history for all rv_series keys (idempotent)."""
    root = repo_root or Path(__file__).resolve().parents[1]
    path = default_dated_series_path(root)
    reg = get_rv_series_registry()
    end = date(2026, 6, 29)
    series_out: dict[str, Any] = {}
    for sid, row in (reg.get("series") or {}).items():
        if not isinstance(row, dict):
            continue
        hk = str(row.get("history_key") or sid)
        unit = str(row.get("unit") or "pct")
        base = {
            "pct": 1.25,
            "bps": 320.0,
            "ratio": 0.98,
            "usd": 45000.0,
        }.get(unit, 1.0)
        seed = sum(ord(c) for c in hk)
        points: list[list[Any]] = []
        for i in range(sessions):
            d = (end - timedelta(days=sessions - 1 - i)).isoformat()
            # Deterministic oscillation — not random
            v = base * (1.0 + 0.08 * ((i + seed) % 17 - 8) / 8.0)
            points.append([d, round(v, 4)])
        series_out[hk.upper()] = {"series_id": sid, "unit": unit, "points": points}

    payload = {
        "version": "1.0",
        "as_of": end.isoformat(),
        "sessions": sessions,
        "series": series_out,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path