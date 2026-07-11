"""Raw vendor CSV → single-row WTM observation (BUILD 2.2e)."""

from __future__ import annotations

import csv
import io
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whinfell_pipeline.staged_csv import (
    SOURCE_BARCHART,
    SOURCE_CHINA,
    SOURCE_KOYFIN,
)

TRANSFORM_VERSION = "2.2e"

MONTH_CODES = {
    "F": "Jan", "G": "Feb", "H": "Mar", "J": "Apr", "K": "May", "M": "Jun",
    "N": "Jul", "Q": "Aug", "U": "Sep", "V": "Oct", "X": "Nov", "Z": "Dec",
}

BTC_ROOTS = ("BTM", "BTN", "BTC")


@dataclass
class TransformResult:
    path: Path
    transformed: bool = False
    warnings: list[str] = field(default_factory=list)
    vendor_format: str = ""


def _norm_headers(headers: list[str]) -> set[str]:
    return {h.strip().strip('"').lower() for h in headers if h and h.strip()}


def is_wtm_observation(headers: list[str], source: str) -> bool:
    norm = _norm_headers(headers)
    if "timestamp" not in norm:
        return False
    if source == SOURCE_CHINA:
        return bool({"policy_strength", "state_impulse_score"} & norm)
    if source == SOURCE_BARCHART:
        return bool({"near_month", "basis_spread"} & norm)
    return bool({"whinfell_score", "regime_tag", "key_observation"} & norm)


def detect_vendor_format(headers: list[str], filename: str, *, header_line: str = "") -> str:
    norm = _norm_headers(headers)
    name = filename.lower()
    hl = header_line or ",".join(headers)
    if hl.count("Type") >= 2 and "Strike" in hl:
        return "barchart_options"
    if "IV Skew" in hl or ({"iv", "delta", "gamma"} <= norm and "strike" in norm):
        return "barchart_volgreeks"
    if {"leg1", "leg2", "type", "latest"} <= norm:
        return "barchart_spreads"
    if {"symbol", "time", "latest"} <= norm:
        return "barchart_historical"
    if {"symbol", "latest"} <= norm and "time" not in norm:
        return "barchart_watchlist"
    if {"contract", "latest", "time"} <= norm:
        return "barchart_prices"
    if "date" in norm:
        corr_cols = sum(1 for h in headers if re.search(r"SPY\s*Corr", h, re.I))
        close_cols = sum(1 for h in norm if "close" in h)
        if corr_cols >= 2 and close_cols <= 2:
            return "koyfin_correlation_series"
    if "date" in norm:
        return_cols = sum(1 for h in headers if re.search(r"\breturn\b", h, re.I))
        if return_cols >= 2:
            return "koyfin_return_timeseries"
    if "date" in norm and any("close" in h for h in norm):
        return "koyfin_wide_timeseries"
    if "ticker" in norm and ("last price" in norm or "total return (1d)" in norm):
        return "koyfin_snapshot"
    if "policy_strength" in norm or "china_regime_tag" in norm:
        return "wtm_china"
    if name.startswith("china_policy"):
        return "koyfin_china_candidate"
    return "unknown"


def _now_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _obs_id(prefix: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{prefix}-{day}-raw2wtm-01"


def _month_from_symbol(symbol: str) -> str:
    sym = symbol.strip().upper()
    m = re.search(r"([FGHJKMNQUVXZ])(\d{1,2})$", sym)
    if m:
        return MONTH_CODES.get(m.group(1), m.group(1))
    return ""


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace("%", "").replace(",", "").replace("$", "")
    if not s or s.upper() in ("N/A", "NA", "-", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_col(headers: list[str], *candidates: str) -> str | None:
    norm_map = {h.strip().lower(): h for h in headers}
    for cand in candidates:
        key = cand.lower()
        if key in norm_map:
            return norm_map[key]
    for h in headers:
        hl = h.strip().lower()
        for cand in candidates:
            if cand.lower() in hl:
                return h
    return None


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if "Downloaded from Barchart" not in ln]
    if not lines:
        raise ValueError("empty file")
    header_line = lines[0]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    if not reader.fieldnames:
        raise ValueError("missing header row")
    headers = list(reader.fieldnames)
    rows = [dict(r) for r in reader]
    if not rows:
        raise ValueError("no data rows")
    return headers, rows, header_line


def _write_observation(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})


def _score_to_state(score: int) -> tuple[str, str]:
    if score < 45:
        return "impaired", "Risk-Off / Credit Stress"
    if score < 55:
        return "stressed", "Fragile Risk-On"
    if score < 70:
        return "elevated", "Constructive / Selective Risk-On"
    return "normal", "Confirmed Risk-On"


def _compute_koyfin_return_score(rows: list[dict[str, str]], headers: list[str]) -> tuple[int, str]:
    """Desk heuristic from Koyfin Date + Return columns (credit/rates wide export)."""
    date_col = _find_col(headers, "Date", "date")
    if not date_col:
        return 50, "Auto-transform: no Date column."

    dated: list[tuple[str, dict[str, str]]] = []
    for row in rows:
        d = (row.get(date_col) or "").strip()
        if d:
            dated.append((d, row))
    if not dated:
        return 50, "Auto-transform: empty Koyfin return series."

    _, latest = dated[-1]
    _, prior = dated[-6] if len(dated) >= 6 else dated[0]
    score = 50.0
    notes: list[str] = []

    for header in headers:
        if not re.search(r"\breturn\b", header, re.I):
            continue
        ticker = header.split()[0].upper()
        cur = _to_float(latest.get(header))
        prev = _to_float(prior.get(header))
        if cur is None:
            continue
        weight = 2.0 if ticker in ("HYG", "KHYB", "IWM", "SPY", "IBIT", "QQQ") else 1.0
        if cur > 0.005:
            score += 4 * weight
            notes.append(f"{ticker} +")
        elif cur < -0.005:
            score -= 4 * weight
            notes.append(f"{ticker} -")
        if prev is not None and cur > prev + 0.003:
            score += 2 * weight
        elif prev is not None and cur < prev - 0.003:
            score -= 2 * weight

    score_i = max(0, min(100, int(round(score))))
    obs = "; ".join(notes[:6]) if notes else "Desk auto-transform from Koyfin return export (2.2e)."
    return score_i, obs


def _compute_koyfin_wide_score(rows: list[dict[str, str]], headers: list[str]) -> tuple[int, str]:
    """Desk heuristic from Koyfin wide time-series (C1-inspired, proxy-only)."""
    date_col = _find_col(headers, "Date", "date")
    if not date_col:
        return 50, "Auto-transform: no Date column."

    dated: list[tuple[str, dict[str, str]]] = []
    for row in rows:
        d = (row.get(date_col) or "").strip()
        if d:
            dated.append((d, row))
    if not dated:
        return 50, "Auto-transform: empty Koyfin series."

    _, latest = dated[-1]
    _, prior = dated[-6] if len(dated) >= 6 else dated[0]

    score = 50.0
    notes: list[str] = []

    hyg_col = _find_col(headers, "HYG Close", "HYG Adj. Close")
    if hyg_col:
        cur, prev = _to_float(latest.get(hyg_col)), _to_float(prior.get(hyg_col))
        if cur is not None and prev is not None and prev != 0:
            chg = (cur - prev) / prev
            if chg > 0.01:
                score += 10
                notes.append("HYG firm")
            elif chg < -0.01:
                score -= 10
                notes.append("HYG soft")

    iwm_col = _find_col(headers, "IWM Close", "IWM Adj. Close")
    spy_col = _find_col(headers, "SPY Close", "SPY Adj. Close", "QQQ Close")
    if iwm_col and spy_col:
        iwm_c, iwm_p = _to_float(latest.get(iwm_col)), _to_float(prior.get(iwm_col))
        spy_c, spy_p = _to_float(latest.get(spy_col)), _to_float(prior.get(spy_col))
        if all(v is not None for v in (iwm_c, iwm_p, spy_c, spy_p)) and iwm_p and spy_p:
            iwm_ret = (iwm_c - iwm_p) / iwm_p
            spy_ret = (spy_c - spy_p) / spy_p
            if iwm_ret > spy_ret + 0.005:
                score += 8
                notes.append("breadth leading")
            elif iwm_ret < spy_ret - 0.005:
                score -= 8
                notes.append("breadth lagging")

    btc_col = _find_col(headers, "BTCUSD Close", "IBIT Close")
    if btc_col and spy_col:
        btc_c, btc_p = _to_float(latest.get(btc_col)), _to_float(prior.get(btc_col))
        spy_c, spy_p = _to_float(latest.get(spy_col)), _to_float(prior.get(spy_col))
        if all(v is not None for v in (btc_c, btc_p, spy_c, spy_p)) and btc_p and spy_p:
            btc_ret = (btc_c - btc_p) / btc_p
            spy_ret = (spy_c - spy_p) / spy_p
            if btc_ret < spy_ret - 0.01:
                score -= 8
                notes.append("BTC lagging SPY")
            elif btc_ret > spy_ret + 0.01:
                score += 5
                notes.append("BTC confirming")

    lqd_col = _find_col(headers, "LQD Close", "LQD Adj. Close")
    if hyg_col and lqd_col:
        hyg_c, hyg_p = _to_float(latest.get(hyg_col)), _to_float(prior.get(hyg_col))
        lqd_c, lqd_p = _to_float(latest.get(lqd_col)), _to_float(prior.get(lqd_col))
        if all(v is not None for v in (hyg_c, hyg_p, lqd_c, lqd_p)) and lqd_p and hyg_p:
            ratio_now = hyg_c / lqd_c
            ratio_prev = hyg_p / lqd_p
            if ratio_now > ratio_prev * 1.002:
                score += 6
                notes.append("HYG/LQD ratio rising")
            elif ratio_now < ratio_prev * 0.998:
                score -= 6
                notes.append("HYG/LQD ratio falling")

    score_i = max(0, min(100, int(round(score))))
    obs = "; ".join(notes) if notes else "Desk auto-transform from Koyfin wide export (2.2e)."
    return score_i, obs


def _compute_koyfin_snapshot_score(rows: list[dict[str, str]], headers: list[str], dataset: str) -> tuple[int, str]:
    score = 50.0
    notes: list[str] = []

    ret_col = _find_col(headers, "Total Return (1D)", "Total Return (1M)")
    flow_col = _find_col(headers, "Fund Flows/Periodic (D)", "Fund Flows/Periodic (W)")
    ticker_col = _find_col(headers, "Ticker", "ticker")

    for row in rows:
        ticker = (row.get(ticker_col or "") or "").strip().upper()
        if not ticker or ticker in ("BTC ETFS", "TICKER"):
            continue
        ret = _to_float(row.get(ret_col or ""))
        if ret is None:
            continue
        weight = 1.0
        if dataset == "credit" and ticker in ("HYG", "LQD"):
            weight = 2.0
        if dataset == "equities" and ticker in ("IWM", "SPY", "IBIT", "QQQ"):
            weight = 2.0
        if ret > 0.005:
            score += 4 * weight
            notes.append(f"{ticker} +")
        elif ret < -0.005:
            score -= 4 * weight
            notes.append(f"{ticker} -")

        flow = _to_float(row.get(flow_col or ""))
        if flow is not None and dataset == "credit" and ticker == "HYG":
            if flow > 0:
                score += 3
                notes.append("HYG inflows")
            elif flow < 0:
                score -= 3
                notes.append("HYG outflows")

    score_i = max(0, min(100, int(round(score))))
    label = dataset or "snapshot"
    obs = "; ".join(notes[:6]) if notes else f"Desk auto-transform from Koyfin {label} snapshot (2.2e)."
    return score_i, obs


def _pick_btc_row(rows: list[dict[str, str]], headers: list[str]) -> dict[str, str] | None:
    sym_col = _find_col(headers, "Symbol", "Contract", "symbol")
    if not sym_col:
        return rows[-1]
    for row in reversed(rows):
        sym = (row.get(sym_col) or "").strip().upper()
        if any(sym.startswith(root) for root in BTC_ROOTS):
            return row
    return rows[-1]


def _transform_koyfin_global(
    path: Path,
    headers: list[str],
    rows: list[dict[str, str]],
    dataset: str | None,
) -> dict[str, Any]:
    fmt = detect_vendor_format(headers, path.name)
    if fmt == "koyfin_return_timeseries":
        score, key_obs = _compute_koyfin_return_score(rows, headers)
    elif fmt == "koyfin_wide_timeseries":
        score, key_obs = _compute_koyfin_wide_score(rows, headers)
    else:
        score, key_obs = _compute_koyfin_snapshot_score(rows, headers, dataset or "rates")
    tx_state, regime = _score_to_state(score)
    return {
        "observation_id": _obs_id("global"),
        "timestamp": _now_timestamp(),
        "whinfell_score": score,
        "transmission_state": tx_state,
        "regime_tag": regime,
        "key_observation": key_obs,
        "_transform_version": TRANSFORM_VERSION,
        "_vendor_format": fmt,
    }


def _transform_barchart_execution(
    path: Path,
    headers: list[str],
    rows: list[dict[str, str]],
    dataset: str | None,
) -> dict[str, Any]:
    fmt = detect_vendor_format(headers, path.name)

    if fmt in ("barchart_options", "barchart_volgreeks"):
        row = rows[0]
        val = _to_float(row.get("Latest") or row.get(_find_col(headers, "Latest") or ""))
        mid = abs(val) if val is not None else 1.0
        return {
            "observation_id": _obs_id("exec"),
            "timestamp": _now_timestamp(),
            "near_month": "ATM",
            "far_month": "Chain",
            "basis_spread": f"{val:.2f}" if val is not None else "0.00",
            "ref_low": f"{mid * 0.8:.2f}",
            "ref_mid": f"{mid:.2f}",
            "ref_high": f"{mid * 1.2:.2f}",
            "_transform_version": TRANSFORM_VERSION,
            "_vendor_format": fmt,
        }

    if fmt == "barchart_spreads":
        row = rows[-1]
        leg1 = (row.get("Leg1") or row.get(_find_col(headers, "Leg1") or "") or "").strip()
        leg2 = (row.get("Leg2") or "").strip()
        spread = _to_float(row.get("Latest") or row.get(_find_col(headers, "Latest") or ""))
        near = _month_from_symbol(leg1) or leg1[:3]
        far = _month_from_symbol(leg2) or leg2[:3]
        basis = spread if spread is not None else 0.0
        mid = abs(basis)
        return {
            "observation_id": _obs_id("exec"),
            "timestamp": _now_timestamp(),
            "near_month": near,
            "far_month": far,
            "basis_spread": f"{basis:.2f}",
            "ref_low": f"{mid * 0.8:.2f}",
            "ref_mid": f"{mid:.2f}",
            "ref_high": f"{mid * 1.2:.2f}",
            "_transform_version": TRANSFORM_VERSION,
            "_vendor_format": fmt,
        }

    sym_col = _find_col(headers, "Symbol", "Contract")
    latest_col = _find_col(headers, "Latest", "Close")
    row = _pick_btc_row(rows, headers) if sym_col else rows[-1]
    symbol = (row.get(sym_col or "") or "BTM").strip().upper()
    latest = _to_float(row.get(latest_col or ""))
    near = _month_from_symbol(symbol) or "Front"
    basis = latest if latest is not None else 0.0
    mid = abs(basis) if basis else 1.0

    warnings_note = ""
    if fmt == "barchart_watchlist":
        warnings_note = "watchlist-snapshot"

    return {
        "observation_id": _obs_id("exec"),
        "timestamp": _now_timestamp(),
        "near_month": near,
        "far_month": "Back",
        "basis_spread": f"{basis:.2f}",
        "ref_low": f"{mid * 0.8:.2f}",
        "ref_mid": f"{mid:.2f}",
        "ref_high": f"{mid * 1.2:.2f}",
        "_transform_version": TRANSFORM_VERSION,
        "_vendor_format": fmt or warnings_note or dataset or "barchart",
    }


def _transform_china(path: Path, headers: list[str], rows: list[dict[str, str]]) -> dict[str, Any]:
    row = rows[-1]
    norm = _norm_headers(headers)

    def _get(*keys: str, default: str = "") -> str:
        for k in keys:
            if k.lower() in norm:
                for hk, hv in row.items():
                    if hk and hk.strip().lower() == k.lower():
                        return (hv or "").strip()
        return default

    return {
        "observation_id": _obs_id("china"),
        "timestamp": _now_timestamp(),
        "policy_strength": _get("policy_strength", default="50"),
        "state_impulse_score": _get("state_impulse_score", default="0"),
        "growth_impulse_score": _get("growth_impulse_score", default="0"),
        "china_regime_tag": _get("china_regime_tag", "dominant_theme", default="desk-auto"),
        "_transform_version": TRANSFORM_VERSION,
    }


def transform_to_observation_row(
    path: Path,
    *,
    source: str,
    dataset: str | None = None,
) -> tuple[dict[str, Any], list[str], str]:
    """Return (observation_row, warnings, vendor_format)."""
    headers, rows, header_line = _read_rows(path)
    warnings: list[str] = []

    if is_wtm_observation(headers, source):
        row = rows[-1]
        payload = {k.strip().lower(): v for k, v in row.items() if k}
        return payload, warnings, "wtm_existing"

    fmt = detect_vendor_format(headers, path.name, header_line=header_line)
    if fmt == "unknown":
        raise ValueError(f"unrecognized vendor CSV layout: {path.name}")

    warnings.append(f"raw→WTM transform applied ({fmt})")

    if source == SOURCE_CHINA:
        return _transform_china(path, headers, rows), warnings, fmt
    if source == SOURCE_BARCHART:
        return _transform_barchart_execution(path, headers, rows, dataset), warnings, fmt
    if source == SOURCE_KOYFIN:
        return _transform_koyfin_global(path, headers, rows, dataset), warnings, fmt

    raise ValueError(f"unsupported source for transform: {source}")


def observation_fieldnames(source: str) -> list[str]:
    if source == SOURCE_CHINA:
        return [
            "observation_id", "timestamp", "policy_strength", "state_impulse_score",
            "growth_impulse_score", "china_regime_tag",
        ]
    if source == SOURCE_BARCHART:
        return [
            "observation_id", "timestamp", "near_month", "far_month", "basis_spread",
            "ref_low", "ref_mid", "ref_high",
        ]
    return [
        "observation_id", "timestamp", "whinfell_score", "transmission_state",
        "regime_tag", "key_observation",
    ]


def transform_file(
    path: Path,
    *,
    source: str,
    dataset: str | None = None,
    out_path: Path | None = None,
) -> TransformResult:
    """Write single-row WTM observation CSV; return result metadata."""
    headers, _, _ = _read_rows(path)
    if is_wtm_observation(headers, source):
        return TransformResult(path=path, transformed=False, vendor_format="wtm_existing")

    row, warnings, fmt = transform_to_observation_row(path, source=source, dataset=dataset)
    dest = out_path or path
    _write_observation(dest, observation_fieldnames(source), row)
    return TransformResult(path=dest, transformed=True, warnings=warnings, vendor_format=fmt)


_BARCHART_RAW_DATASETS = frozenset({"futures_daily", "futures_intraday", "options", "greeks", "btc_basis"})
_BARCHART_RAW_FORMATS = frozenset({
    "barchart_historical",
    "barchart_volgreeks",
    "barchart_options",
    "barchart_spreads",
})


def prepare_staged_csv(
    path: Path,
    *,
    source: str,
    dataset: str | None = None,
) -> TransformResult:
    """
    Return a path suitable for staged_csv validation (transformed temp file if needed).
    Caller should unlink temp paths after staging when path != original.
    """
    if dataset == "flows":
        return TransformResult(path=path, transformed=False, vendor_format="wtm_flows_wide")

    headers, _, header_line = _read_rows(path)
    fmt = detect_vendor_format(headers, path.name, header_line=header_line)
    if (
        source == SOURCE_BARCHART
        and dataset in _BARCHART_RAW_DATASETS
        and fmt in _BARCHART_RAW_FORMATS
    ):
        return TransformResult(path=path, transformed=False, vendor_format=fmt)

    if is_wtm_observation(headers, source):
        return TransformResult(path=path, transformed=False, vendor_format="wtm_existing")

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".csv",
        prefix=f"{path.stem}__wtm_",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    )
    tmp_path = Path(tmp.name)
    tmp.close()

    result = transform_file(path, source=source, dataset=dataset, out_path=tmp_path)
    result.path = tmp_path
    return result