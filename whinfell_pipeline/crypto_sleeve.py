"""Crypto sleeve — first-class BTC/ETH/XRP/SOL spot, chart history, and correlation support."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CRYPTO_SLEEVE_VERSION = "1.0.0"

SOURCE_CRYPTO = "crypto"

# Koyfin ticker → canonical asset key
ASSET_TICKER_MAP: dict[str, str] = {
    "BTCUSD": "btc_spot_usd",
    "ETHUSD": "eth_spot_usd",
    "XRPUSD": "xrp_spot_usd",
    "SOLUSD": "sol_spot_usd",
}

ASSET_KEYS = tuple(ASSET_TICKER_MAP.values())

# Chart export filename stem → canonical chart key
CHART_FILENAME_MAP: dict[str, str] = {
    "btc_price_chart": "btc_price_chart",
    "btc_correl_chart": "btc_correl_chart",
    "eth_correl_chart": "eth_correl_chart",
    "xrp_correl_chart": "xrp_correl_chart",
    "sol_correl_chart": "sol_correl_chart",
    "wtm_crypto_price": "btc_price_chart",
    "wtm_crypto_correl": "btc_correl_chart",
}

# Desk view labels (metadata only)
CHART_VIEW_LABELS: dict[str, str] = {
    "btc_price_chart": "WTM-Crypto-Price",
    "btc_correl_chart": "WTM-Crypto-Correl",
    "eth_correl_chart": "WTM-Crypto-Correl-ETH",
    "xrp_correl_chart": "WTM-Crypto-Correl-XRP",
    "sol_correl_chart": "WTM-Crypto-Correl-SOL",
}

CRYPTO_DATASETS = (
    "crypto_snapshot",
    "btc_price_chart",
    "btc_correl_chart",
    "eth_correl_chart",
    "xrp_correl_chart",
    "sol_correl_chart",
    "crypto_corr_series",
)

# Historical pairwise correlation CSV (non-crypto sleeve pairs)
CORREL_PAIR_MAP: dict[str, str] = {
    "HYG SPY Corr": "corr_hyg_spy",
    "JAAA SPY Corr": "corr_jaaa_spy",
    "BKLN SPY Corr": "corr_bkln_spy",
    "CWB SPY Corr": "corr_cwb_spy",
    "XLRE SPY Corr": "corr_xlre_spy",
}

_SNAPSHOT_HEADER_ALIASES: dict[str, str] = {
    "last price": "last_price",
    "1d chg": "chg_1d",
    "total return (1d)": "chg_1d",
    "volatility 1m": "vol_1m",
    "volatility (1m)": "vol_1m",
    "volatility 3m": "vol_3m",
    "volatility (3m)": "vol_3m",
    "volatility 1y": "vol_1y",
    "volatility (1y)": "vol_1y",
    "total return 5d": "tr_5d",
    "total return 1w": "tr_1w",
    "total return (1w)": "tr_1w",
    "total return 1m": "tr_1m",
    "total return (1m)": "tr_1m",
    "total return 3m": "tr_3m",
    "total return (3m)": "tr_3m",
    "total return 6m": "tr_6m",
    "total return (6m)": "tr_6m",
    "total return 1y": "tr_1y",
    "total return (1y)": "tr_1y",
    "ticker": "ticker",
    "name": "name",
}

_CORR_HEADER_RE = re.compile(
    r"^(.+?)\s*(?:/\s*)?SPY\s*Corr$",
    re.IGNORECASE,
)


@dataclass
class CryptoIngestResult:
    ok: bool = True
    source_type: str = ""
    dataset: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_crypto_json_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "crypto" / "v1" / "latest_crypto_sleeve.json"


def _norm_header_label(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().strip('"').lower())


def normalize_koyfin_header(header: str) -> tuple[str, str]:
    """Return (internal_snake_key, raw_label)."""
    raw = header.strip().strip('"')
    norm = _norm_header_label(raw)
    if norm in _SNAPSHOT_HEADER_ALIASES:
        return _SNAPSHOT_HEADER_ALIASES[norm], raw
    if norm == "date":
        return "date", raw
    pair_key = normalize_correlation_header(raw)
    if pair_key:
        return pair_key, raw
    slug = re.sub(r"[^a-z0-9]+", "_", norm).strip("_")
    return slug or "field", raw


def normalize_correlation_header(header: str) -> str | None:
    raw = header.strip().strip('"')
    if raw in CORREL_PAIR_MAP:
        return CORREL_PAIR_MAP[raw]
    m = _CORR_HEADER_RE.match(raw)
    if not m:
        return None
    left = re.sub(r"[^A-Za-z0-9]+", " ", m.group(1)).strip().upper()
    left = left.replace(" ", "_")
    if not left:
        return None
    return f"corr_{left.lower()}_spy"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty file")
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    if not reader.fieldnames:
        raise ValueError("missing header row")
    headers = [h for h in reader.fieldnames if h is not None]
    rows = [dict(r) for r in reader]
    return headers, rows


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
    norm_map = {_norm_header_label(h): h for h in headers}
    for cand in candidates:
        key = cand.lower()
        if key in norm_map:
            return norm_map[key]
    for h in headers:
        hl = _norm_header_label(h)
        for cand in candidates:
            if cand.lower() in hl:
                return h
    return None


def _snapshot_tickers_present(rows: list[dict[str, str]], headers: list[str]) -> set[str]:
    ticker_col = _find_col(headers, "Ticker", "ticker")
    if not ticker_col:
        return set()
    found: set[str] = set()
    for row in rows:
        t = (row.get(ticker_col) or "").strip().upper()
        if t in ASSET_TICKER_MAP:
            found.add(t)
    return found


def detect_crypto_source_type(
    headers: list[str],
    filename: str,
    *,
    rows: list[dict[str, str]] | None = None,
) -> str:
    """Route: snapshot | chart_timeseries | correlation_series | unknown."""
    norm = {_norm_header_label(h) for h in headers}
    name = filename.lower()

    for token in CRYPTO_DATASETS:
        if token in name:
            if token == "crypto_snapshot":
                return "snapshot"
            if token.endswith("_chart"):
                return "chart_timeseries"
            if token == "crypto_corr_series":
                return "correlation_series"

    if "date" in norm:
        corr_cols = [h for h in headers if normalize_correlation_header(h)]
        close_cols = [h for h in headers if " close" in _norm_header_label(h)]
        if corr_cols and len(close_cols) <= 2:
            return "correlation_series"
        crypto_close = any(
            _find_col(headers, f"{ticker} Close", f"{ticker} Adj. Close")
            for ticker in ASSET_TICKER_MAP
        )
        if crypto_close and len(close_cols) >= 4:
            return "wide_timeseries_backup"
        if len(headers) <= 4 and any("corr" in _norm_header_label(h) for h in headers):
            return "chart_timeseries"
        if len(headers) <= 4:
            return "chart_timeseries"

    if "ticker" in norm and ("last price" in norm or "total return (1d)" in norm):
        tickers = _snapshot_tickers_present(rows or [], headers)
        if tickers:
            return "snapshot"
        if name.startswith("koyfin_whinpump") or "whinpump" in name:
            return "snapshot"

    if name.startswith("koyfin_whinpump") or "whinpump" in name:
        if rows and _snapshot_tickers_present(rows, headers):
            return "snapshot"

    return "unknown"


def chart_key_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem.lower()
    for token, key in CHART_FILENAME_MAP.items():
        if token in stem:
            return key
    m = re.match(r"^(btc|eth|xrp|sol)_(price|correl)_chart", stem)
    if m:
        return f"{m.group(1)}_{m.group(2)}_chart"
    return None


def asset_key_for_chart(chart_key: str) -> str | None:
    ticker_by_prefix = {
        "btc": "BTCUSD",
        "eth": "ETHUSD",
        "xrp": "XRPUSD",
        "sol": "SOLUSD",
    }
    m = re.match(r"^(btc|eth|xrp|sol)_(?:price|correl)_chart", chart_key)
    if m:
        return ASSET_TICKER_MAP.get(ticker_by_prefix[m.group(1)])
    return None


def parse_snapshot_rows(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    source_file: str = "",
) -> dict[str, Any]:
    """Extract cross-sectional crypto spot state from Koyfin watchlist export."""
    ticker_col = _find_col(headers, "Ticker", "ticker")
    if not ticker_col:
        raise ValueError("snapshot missing Ticker column")

    header_map = {h: normalize_koyfin_header(h) for h in headers}
    assets: dict[str, Any] = {}

    for row in rows:
        ticker = (row.get(ticker_col) or "").strip().upper()
        asset_key = ASSET_TICKER_MAP.get(ticker)
        if not asset_key:
            continue

        fields: dict[str, Any] = {"ticker": ticker, "asset_key": asset_key}
        raw_meta: dict[str, str] = {}
        for h, (internal, raw_label) in header_map.items():
            val = row.get(h)
            if val is None or str(val).strip() == "":
                continue
            raw_meta[raw_label] = str(val).strip()
            if internal in ("ticker", "name"):
                fields[internal] = str(val).strip()
            elif internal.startswith(("last_", "chg_", "vol_", "tr_")):
                fields[internal] = _to_float(val)
            else:
                fields.setdefault(internal, str(val).strip())

        fields["_raw"] = raw_meta
        assets[asset_key] = fields

    if not assets:
        raise ValueError("no in-scope crypto tickers in snapshot")

    return {
        "source_type": "snapshot",
        "source_file": source_file,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
        "tickers_found": sorted({a["ticker"] for a in assets.values()}),
    }


def parse_chart_timeseries(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    chart_key: str,
    source_file: str = "",
) -> dict[str, Any]:
    """Parse Koyfin chart export as dated time series (price or correlation)."""
    date_col = _find_col(headers, "Date", "date")
    if not date_col:
        raise ValueError("chart export missing Date column")

    value_cols = [h for h in headers if h != date_col]
    if not value_cols:
        raise ValueError("chart export has no value columns")

    series_name = value_cols[0]
    for h in value_cols:
        hl = _norm_header_label(h)
        if chart_key.endswith("_price_chart") and "close" in hl:
            series_name = h
            break
        if chart_key.endswith("_correl_chart") and "corr" in hl:
            series_name = h
            break

    internal, raw_label = normalize_koyfin_header(series_name)
    hl = _norm_header_label(series_name)
    if chart_key.endswith("_price_chart") and "close" in hl:
        internal = "close"
    elif chart_key.endswith("_correl_chart") and "corr" in hl:
        internal = "correl"
    elif internal == re.sub(r"[^a-z0-9]+", "_", hl).strip("_"):
        internal = "value"

    points: list[dict[str, Any]] = []
    for row in rows:
        d = (row.get(date_col) or "").strip()
        if not d:
            continue
        v = _to_float(row.get(series_name))
        if v is None:
            continue
        points.append({"date": d, internal: v})

    if not points:
        raise ValueError("chart export has no parseable rows")

    asset_key = asset_key_for_chart(chart_key)
    return {
        "source_type": "chart_timeseries",
        "chart_key": chart_key,
        "desk_view": CHART_VIEW_LABELS.get(chart_key, ""),
        "asset_key": asset_key,
        "source_file": source_file,
        "field": internal,
        "raw_field": raw_label,
        "points": points,
        "row_count": len(points),
        "latest": points[-1],
    }


def parse_correlation_series(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    source_file: str = "",
) -> dict[str, Any]:
    """Parse dated pairwise correlation CSV (non-crypto sleeve template)."""
    date_col = _find_col(headers, "Date", "date")
    if not date_col:
        raise ValueError("correlation series missing Date column")

    pair_cols: dict[str, str] = {}
    raw_labels: dict[str, str] = {}
    for h in headers:
        if h == date_col:
            continue
        key = normalize_correlation_header(h)
        if key:
            pair_cols[key] = h
            raw_labels[key] = h.strip()

    if not pair_cols:
        raise ValueError("correlation series has no pairwise Corr columns")

    points: list[dict[str, Any]] = []
    for row in rows:
        d = (row.get(date_col) or "").strip()
        if not d:
            continue
        point: dict[str, Any] = {"date": d}
        any_val = False
        for key, col in pair_cols.items():
            v = _to_float(row.get(col))
            if v is not None:
                point[key] = v
                any_val = True
        if any_val:
            points.append(point)

    if not points:
        raise ValueError("correlation series has no parseable rows")

    return {
        "source_type": "correlation_series",
        "source_file": source_file,
        "pairs": sorted(pair_cols.keys()),
        "raw_labels": raw_labels,
        "points": points,
        "row_count": len(points),
        "latest": points[-1],
    }


def extract_wide_timeseries_crypto(
    headers: list[str],
    rows: list[dict[str, str]],
    *,
    source_file: str = "",
) -> dict[str, Any]:
    """Backup: pull crypto Close columns from Whinfell-Daily-TimeSeries wide export."""
    date_col = _find_col(headers, "Date", "date")
    if not date_col:
        raise ValueError("wide timeseries missing Date column")

    asset_cols: dict[str, str] = {}
    for ticker, asset_key in ASSET_TICKER_MAP.items():
        col = _find_col(headers, f"{ticker} Close", f"{ticker} Adj. Close")
        if col:
            asset_cols[asset_key] = col

    if not asset_cols:
        raise ValueError("wide timeseries has no crypto Close columns")

    by_asset: dict[str, list[dict[str, Any]]] = {k: [] for k in asset_cols}
    for row in rows:
        d = (row.get(date_col) or "").strip()
        if not d:
            continue
        for asset_key, col in asset_cols.items():
            v = _to_float(row.get(col))
            if v is not None:
                by_asset[asset_key].append({"date": d, "close": v})

    charts: dict[str, Any] = {}
    for asset_key, points in by_asset.items():
        if not points:
            continue
        ticker = next(k for k, v in ASSET_TICKER_MAP.items() if v == asset_key)
        prefix = ticker.replace("USD", "").lower()
        ck = "btc_price_chart" if ticker == "BTCUSD" else f"{prefix}_price_chart_backup"
        charts[ck] = {
            "source_type": "wide_timeseries_backup",
            "chart_key": ck,
            "asset_key": asset_key,
            "source_file": source_file,
            "field": "close",
            "points": points,
            "row_count": len(points),
            "latest": points[-1],
            "priority": "backup",
        }

    return {"charts": charts, "source_file": source_file}


def load_crypto_sidecar(path: Path | None = None) -> dict[str, Any]:
    p = path or default_crypto_json_path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("payload"), dict):
        return dict(data["payload"])
    return dict(data) if isinstance(data, dict) else {}


def write_crypto_sidecar(payload: dict[str, Any], path: Path | None = None) -> Path:
    p = path or default_crypto_json_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "crypto_sleeve_version": CRYPTO_SLEEVE_VERSION,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    p.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return p


def _prefer_chart(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return incoming
    if existing.get("priority") == "backup" and incoming.get("priority") != "backup":
        return incoming
    if incoming.get("priority") == "backup" and existing.get("priority") != "backup":
        return existing
    if incoming.get("row_count", 0) >= existing.get("row_count", 0):
        return incoming
    return existing


def merge_crypto_payload(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge ingest patch into cumulative crypto sleeve payload."""
    out = dict(base)
    out.setdefault("assets", {})
    out.setdefault("charts", {})
    out.setdefault("correlation_series", {})
    out.setdefault("sources", [])
    out["crypto_sleeve_version"] = CRYPTO_SLEEVE_VERSION

    if patch.get("source_type") == "snapshot":
        for key, asset in patch.get("assets", {}).items():
            out["assets"][key] = asset
        out["snapshot"] = {
            "as_of": patch.get("as_of"),
            "source_file": patch.get("source_file"),
            "tickers_found": patch.get("tickers_found", []),
        }
    elif patch.get("source_type") == "chart_timeseries":
        ck = patch.get("chart_key") or "unknown_chart"
        out["charts"][ck] = _prefer_chart(out["charts"].get(ck), patch)
    elif patch.get("source_type") == "correlation_series":
        out["correlation_series"]["pairwise"] = patch
    elif patch.get("charts"):
        for ck, chart in patch["charts"].items():
            out["charts"][ck] = _prefer_chart(out["charts"].get(ck), chart)

    src_entry = {
        "source_type": patch.get("source_type"),
        "source_file": patch.get("source_file"),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
    if patch.get("chart_key"):
        src_entry["chart_key"] = patch["chart_key"]
    out["sources"] = (out.get("sources") or [])[-19:] + [src_entry]
    out["as_of"] = datetime.now(timezone.utc).isoformat()
    return out


def ingest_crypto_file(path: Path, *, dataset: str | None = None) -> tuple[dict[str, Any], CryptoIngestResult]:
    """Parse one crypto-sleeve CSV and return (patch, result)."""
    result = CryptoIngestResult(dataset=dataset)
    headers, rows = _read_csv(path)
    source_type = detect_crypto_source_type(headers, path.name, rows=rows)
    if source_type == "unknown" and dataset:
        if dataset == "crypto_snapshot":
            source_type = "snapshot"
        elif dataset.endswith("_chart"):
            source_type = "chart_timeseries"
        elif dataset == "crypto_corr_series":
            source_type = "correlation_series"

    result.source_type = source_type
    try:
        if source_type == "snapshot":
            patch = parse_snapshot_rows(headers, rows, source_file=path.name)
        elif source_type == "chart_timeseries":
            chart_key = chart_key_from_filename(path.name) or (dataset or "")
            if not chart_key:
                raise ValueError("cannot infer chart_key from filename")
            patch = parse_chart_timeseries(headers, rows, chart_key=chart_key, source_file=path.name)
        elif source_type == "correlation_series":
            patch = parse_correlation_series(headers, rows, source_file=path.name)
        elif source_type == "wide_timeseries_backup":
            patch = extract_wide_timeseries_crypto(headers, rows, source_file=path.name)
            patch["source_type"] = "wide_timeseries_backup"
        else:
            raise ValueError(f"unrecognized crypto source layout: {path.name}")
    except ValueError as exc:
        result.ok = False
        result.errors.append(str(exc))
        return {}, result

    return patch, result


def ingest_crypto_paths(paths: Iterable[Path], *, sidecar_path: Path | None = None) -> dict[str, Any]:
    """Ingest multiple crypto CSVs and persist merged sidecar."""
    payload = load_crypto_sidecar(sidecar_path)
    for path in paths:
        patch, res = ingest_crypto_file(path)
        if res.ok and patch:
            payload = merge_crypto_payload(payload, patch)
        elif res.errors:
            payload.setdefault("ingest_errors", []).append(
                {"file": path.name, "errors": res.errors}
            )
    if payload:
        write_crypto_sidecar(payload, sidecar_path)
    return payload


def legacy_btc_price_alias(payload: dict[str, Any]) -> float | None:
    """Compatibility shim only — do not use as primary source object."""
    chart = (payload.get("charts") or {}).get("btc_price_chart")
    if chart and chart.get("latest"):
        latest = chart["latest"]
        for key in ("close", "value", "last_price"):
            if key in latest:
                return _to_float(latest[key])
    btc = (payload.get("assets") or {}).get("btc_spot_usd")
    if btc:
        return _to_float(btc.get("last_price"))
    return None


def hydration_crypto_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Shape crypto sleeve for Transmission Control hydration import."""
    block = {
        "version": CRYPTO_SLEEVE_VERSION,
        "as_of": payload.get("as_of"),
        "assets": payload.get("assets") or {},
        "charts": {
            k: {
                "chart_key": v.get("chart_key"),
                "asset_key": v.get("asset_key"),
                "field": v.get("field"),
                "row_count": v.get("row_count"),
                "latest": v.get("latest"),
                "priority": v.get("priority", "primary"),
            }
            for k, v in (payload.get("charts") or {}).items()
        },
        "correlation_series": payload.get("correlation_series") or {},
        "snapshot": payload.get("snapshot") or {},
        "legacy_BTCPRice": legacy_btc_price_alias(payload),
    }
    return block