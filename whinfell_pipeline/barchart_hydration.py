"""Barchart-only first-pass hydration — core / curve / spread history + manifest."""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from whinfell_pipeline.data_dictionary import (
    barchart_all_approved_symbols,
    barchart_canonical_core_map,
    barchart_core_symbols,
    barchart_curve_symbols,
    barchart_history_field_map,
    barchart_instrument_class_map,
    barchart_spread_symbols,
    load_data_dictionary,
)
from whinfell_pipeline.raw_csv_transform import _find_col, _to_float, detect_vendor_format

BARCHART_HYDRATION_VERSION = "1.0.0"
HISTORY_POINT_FIELDS = frozenset({
    "date", "open", "high", "low", "close", "volume", "open_interest", "change", "pct_change",
})
NUMERIC_HISTORY_FIELDS = frozenset({"open", "high", "low", "close", "volume", "open_interest", "change"})

MONTH_CODES = "FGHJKMNQUVXZ"
CONTRACT_RE = re.compile(r"^(.+)([FGHJKMNQUVXZ])(\d{2})$")
SPREAD_RE = re.compile(r"^_S_([A-Z]+)_(.+)$")
WATCHLIST_DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
INTERACTIVE_CHART_RE = re.compile(r"^(.+?)_Barchart_Interactive_Chart_", re.I)
BARCHART_FOOTER_MARKERS = ("Downloaded from Barchart", "DOWNLOADED FROM BARCHART")


@dataclass(frozen=True)
class SupplementSource:
    path: Path
    fetch_mode: str
    priority: int


@dataclass
class SymbolOutcome:
    raw_symbol: str
    bucket: str
    status: str
    canonical_id: str = ""
    row_count: int = 0
    reason: str = ""
    contract_meta: dict[str, Any] = field(default_factory=dict)
    spread_meta: dict[str, Any] = field(default_factory=dict)


def default_output_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "data" / "barchart" / "v1"


def default_supplement_dirs(repo_root: Path | None = None) -> list[Path]:
    """Real operator drop + staged barchart + legacy Archive charts — not test fixtures."""
    root = repo_root or Path(__file__).resolve().parents[1]
    dirs = [
        Path.home() / "Downloads" / "whinfell_drop",
        root / "staged_raw" / "quarantine",
        root / "staged_raw" / "source=barchart",
        Path.home() / "Downloads" / "Archive",
        Path.home() / "Documents" / "ExcelCSVs" / "Barchart",
    ]
    return [d for d in dirs if d.is_dir()]


def load_barchart_api_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit.strip()
    import os

    env_key = os.environ.get("BARCHART_API_KEY", "").strip()
    if env_key:
        return env_key
    root = Path(__file__).resolve().parents[1]
    candidates = [
        root / ".env",
        root / "secrets" / "barchart_api_key",
        Path.home() / ".config" / "whinfell" / "barchart_api_key",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if path.name == ".env":
            for line in text.splitlines():
                if line.startswith("BARCHART_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
            continue
        if text:
            return text
    return ""


def recorded_examples_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "whinfell_pipeline" / "examples" / "barchart_hydration" / "recorded"


def _spread_meta_from_norm(norm: dict[str, Any], bucket: str) -> dict[str, Any]:
    if bucket != "spread":
        return {}
    return {k: norm[k] for k in ("spread_kind", "spread_legs", "source_system") if k in norm}


def _skip_supplement_path(path: Path) -> bool:
    if " (1)" in path.name:
        return True
    try:
        path.resolve().relative_to(recorded_examples_dir().resolve())
        return True
    except ValueError:
        pass
    parts = {p.name for p in path.resolve().parents}
    return "barchart_hydration" in parts and "examples" in parts


def _pending_outcome(raw_symbol: str) -> tuple[dict[str, Any], str, SymbolOutcome]:
    bucket = classify_bucket(raw_symbol)
    hint = _group_hint_for_symbol(raw_symbol)
    norm = normalize_barchart_symbol(raw_symbol, group_hint=hint)
    outcome = SymbolOutcome(
        raw_symbol=raw_symbol,
        bucket=bucket,
        status="pending",
        canonical_id=norm.get("canonical_id", ""),
        contract_meta=norm.get("contract_meta") or {},
        spread_meta=_spread_meta_from_norm(norm, bucket),
    )
    return norm, bucket, outcome


def instrument_class_for_symbol(norm: dict[str, Any], bucket: str) -> str:
    if norm.get("instrument_class"):
        return str(norm["instrument_class"])
    ic_map = barchart_instrument_class_map()
    raw = norm.get("raw_symbol", "")
    if raw in ic_map:
        return ic_map[raw]
    if bucket == "curve":
        return "futures"
    if bucket == "spread":
        return "spread"
    if bucket == "core":
        return "index"
    return "unknown"


def pricing_mode_for_symbol(norm: dict[str, Any], bucket: str) -> str:
    if norm.get("pricing_mode"):
        return str(norm["pricing_mode"])
    if bucket == "spread":
        return "derived_or_structured"
    return "exchange_traded"


def classify_bucket(raw_symbol: str) -> str:
    if raw_symbol.startswith("_S_"):
        return "spread"
    core = set(barchart_core_symbols())
    if raw_symbol in core:
        return "core"
    curves = set(barchart_curve_symbols())
    spreads = set(barchart_spread_symbols())
    if raw_symbol in curves:
        return "curve"
    if raw_symbol in spreads:
        return "spread"
    return "unknown"


def _contract_type_bucket_from_root(root: str, group_hint: str | None = None) -> str:
    if group_hint:
        return group_hint.replace("_", "-")
    prefixes = {
        "DX": "fx-futures", "E6": "fx-futures", "J6": "fx-futures", "A6": "fx-futures",
        "GC": "metals-curves", "HG": "metals-curves",
        "CL": "energy-curves", "NG": "energy-curves",
        "BT": "btc-futures-curves",
        "TA": "sofr-curves",
        "ZM": "rates-strips", "ZL": "rates-strips", "ZB": "rates-strips",
        "ZF": "rates-strips", "ZN": "rates-strips", "ZQ": "rates-strips",
        "OY": "hy-contracts", "OG": "hy-contracts",
    }
    for p, bucket in prefixes.items():
        if root.startswith(p):
            return bucket
    return "misc-contracts"


def parse_contract_meta(raw_symbol: str) -> dict[str, Any]:
    sym = raw_symbol.strip().upper()
    m = CONTRACT_RE.match(sym)
    if not m:
        return {
            "contract_root": sym,
            "month_code": "",
            "year": "",
            "contract_type_bucket": "unknown-contract",
        }
    root, month, year = m.group(1), m.group(2), m.group(3)
    year_full = f"20{year}" if len(year) == 2 else year
    return {
        "contract_root": root,
        "month_code": month,
        "year": year_full,
        "contract_type_bucket": _contract_type_bucket_from_root(root),
    }


def parse_spread_meta(raw_symbol: str) -> dict[str, Any]:
    m = SPREAD_RE.match(raw_symbol)
    spread_kind = m.group(1) if m else "UNKNOWN"
    legs = m.group(2) if m else raw_symbol
    return {
        "instrument_class": "spread",
        "source_system": "barchart",
        "pricing_mode": "derived_or_structured",
        "spread_kind": spread_kind,
        "spread_legs": legs,
    }


def normalize_barchart_symbol(raw_symbol: str, *, group_hint: str | None = None) -> dict[str, Any]:
    """Return canonical mapping metadata for a raw Barchart symbol."""
    bucket = classify_bucket(raw_symbol)
    core_map = barchart_canonical_core_map()
    out: dict[str, Any] = {
        "raw_symbol": raw_symbol,
        "bucket": bucket,
    }
    if raw_symbol in core_map:
        out["canonical_id"] = core_map[raw_symbol]
        out["instrument_class"] = instrument_class_for_symbol(out, bucket)
        out["pricing_mode"] = pricing_mode_for_symbol(out, bucket)
        return out
    if bucket == "spread":
        meta = parse_spread_meta(raw_symbol)
        out.update(meta)
        slug = re.sub(r"[^a-z0-9]+", "_", raw_symbol.lower()).strip("_")
        out["canonical_id"] = f"barchart_spread_{slug}"
        return out
    if bucket in ("curve", "unknown") and not raw_symbol.startswith("_S_"):
        meta = parse_contract_meta(raw_symbol)
        if group_hint:
            meta["contract_type_bucket"] = _contract_type_bucket_from_root(
                meta.get("contract_root", ""), group_hint=group_hint
            )
        out["contract_meta"] = meta
        root = meta.get("contract_root", "").lower()
        month = meta.get("month_code", "").lower()
        year = meta.get("year", "")[-2:]
        out["canonical_id"] = f"barchart_contract_{root}{month}{year}"
        out["instrument_class"] = instrument_class_for_symbol(out, bucket)
        out["pricing_mode"] = pricing_mode_for_symbol(out, bucket)
        return out
    out["canonical_id"] = f"barchart_unknown_{re.sub(r'[^a-z0-9]+', '_', raw_symbol.lower())}"
    return out


def _remap_barchart_time_latest(
    headers: list[str], rows: list[dict[str, str]]
) -> tuple[list[str], list[dict[str, str]]]:
    if "Time" not in headers or "Date" in headers:
        return headers, rows
    remap_headers = [
        "Date" if h == "Time" else "Close" if h == "Latest" else h for h in headers
    ]
    remapped_rows: list[dict[str, str]] = []
    for row in rows:
        nr: dict[str, str] = {}
        for h, nh in zip(headers, remap_headers):
            nr[nh] = row.get(h, "")
        remapped_rows.append(nr)
    return remap_headers, remapped_rows


def normalize_history_rows(headers: list[str], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    headers, rows = _remap_barchart_time_latest(headers, rows)
    fmap = barchart_history_field_map()
    norm_headers = {h: fmap.get(h, h.strip().lower().replace(" ", "_")) for h in headers}
    out: list[dict[str, Any]] = []
    for row in rows:
        point: dict[str, Any] = {}
        for h, internal in norm_headers.items():
            if internal not in HISTORY_POINT_FIELDS:
                continue
            val = row.get(h)
            if val is None or str(val).strip() == "":
                continue
            if internal in NUMERIC_HISTORY_FIELDS:
                num = _to_float(val)
                if num is not None:
                    point[internal] = num
                else:
                    point[internal] = str(val).strip()
            elif internal == "pct_change":
                num = _to_float(val)
                point[internal] = num if num is not None else str(val).strip()
            else:
                point[internal] = str(val).strip()
        if point:
            out.append(point)
    deduped: dict[str, dict[str, Any]] = {}
    for point in out:
        key = str(point.get("date", ""))
        if key:
            deduped[key] = point
    return list(deduped.values()) if deduped else out


def _build_history_record(
    *,
    raw_symbol: str,
    norm: dict[str, Any],
    bucket: str,
    outcome: SymbolOutcome,
    points: list[dict[str, Any]],
    fetch_mode: str = "api",
    source_file: str | None = None,
    vendor_format: str = "",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "raw_symbol": raw_symbol,
        "canonical_id": norm.get("canonical_id", ""),
        "bucket": bucket,
        "source_system": "barchart",
        "fetch_mode": fetch_mode,
        "vendor_format": vendor_format,
        "instrument_class": instrument_class_for_symbol(norm, bucket),
        "pricing_mode": pricing_mode_for_symbol(norm, bucket),
        "contract_meta": norm.get("contract_meta") or {},
        "spread_meta": outcome.spread_meta or {},
        "field_map_version": BARCHART_HYDRATION_VERSION,
        "row_count": len(points),
        "points": points,
        "latest": points[-1],
    }
    if source_file:
        record["source_file"] = source_file
    return record


def fetch_barchart_daily_csv(
    symbol: str,
    *,
    api_key: str,
    start_date: str = "20250101",
    end_date: str | None = None,
) -> bytes:
    end = end_date or datetime.now().strftime("%Y%m%d")
    params = urllib.parse.urlencode({
        "apikey": api_key,
        "symbol": symbol,
        "startDate": start_date,
        "endDate": end,
        "type": "daily",
    })
    url = f"https://marketdata.websol.barchart.com/getHistory.csv?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "WhinfellBarchartHydration/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def _strip_barchart_footer_lines(lines: list[str]) -> list[str]:
    return [
        ln for ln in lines
        if ln.strip() and not any(marker in ln for marker in BARCHART_FOOTER_MARKERS)
    ]


def _symbol_from_interactive_chart_path(path: Path, approved: set[str]) -> str | None:
    m = INTERACTIVE_CHART_RE.match(path.name)
    if not m:
        return None
    stem = m.group(1).strip().upper()
    if stem in approved:
        return stem
    return _match_symbol_from_filename(stem, approved)


def _parse_interactive_chart_lines(
    lines: list[str],
    *,
    target_symbol: str,
) -> tuple[list[str], list[dict[str, str]]]:
    """Barchart interactive chart export: symbol row, header row, then OHLC rows."""
    if len(lines) < 3:
        return [], []
    sym_cells = next(csv.reader([lines[0]]))
    hdr_cells = next(csv.reader([lines[1]]))
    target = target_symbol.strip().upper()
    close_idx = None
    for idx, cell in enumerate(sym_cells):
        cell_u = cell.strip().upper()
        if cell_u.startswith("SYMBOL:"):
            sym = cell_u.split(":", 1)[1].strip()
            if sym == target:
                hdr = hdr_cells[idx].strip().lower() if idx < len(hdr_cells) else ""
                if hdr in ("close", "latest"):
                    close_idx = idx
                    break
    if close_idx is None:
        return [], []
    date_idx = None
    for idx, hdr in enumerate(hdr_cells):
        if hdr.strip().lower() in ("date time", "time", "date"):
            date_idx = idx
            break
    if date_idx is None:
        return [], []
    headers = ["Symbol", "Time", "Latest"]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = next(csv.reader([line]))
        if len(cells) <= max(close_idx, date_idx):
            continue
        date_val = cells[date_idx].strip()
        close_val = cells[close_idx].strip()
        if not date_val or not close_val:
            continue
        rows.append({"Symbol": target, "Time": date_val, "Latest": close_val})
    return headers, rows


def _parse_barchart_csv(
    body: bytes,
    *,
    path_hint: str = "",
    target_symbol: str = "",
) -> tuple[list[str], list[dict[str, str]], str]:
    """Parse Barchart CSV bytes using legacy vendor-format detection."""
    text = body.decode("utf-8", errors="replace")
    lines = _strip_barchart_footer_lines(text.splitlines())
    if not lines:
        return [], [], "empty"

    first = lines[0]
    if "Symbol:" in first and len(lines) >= 3:
        sym = target_symbol or _symbol_from_interactive_chart_path(
            Path(path_hint or "interactive.csv"), set(barchart_all_approved_symbols())
        ) or ""
        headers, rows = _parse_interactive_chart_lines(lines, target_symbol=sym)
        if rows:
            return headers, rows, "barchart_interactive_chart"

    header_line = lines[0]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    if not reader.fieldnames:
        return [], [], "unknown"
    headers = [h.strip().strip('"') for h in reader.fieldnames]
    rows = [dict(r) for r in reader]
    fmt = detect_vendor_format(headers, path_hint or "barchart.csv", header_line=header_line)

    sym_col = _find_col(headers, "Symbol", "Contract")
    if sym_col and sym_col != "Symbol" and "Symbol" not in headers:
        for row in rows:
            row["Symbol"] = row.get(sym_col, "")

    return headers, rows, fmt or "unknown"


def _parse_csv_body(body: bytes, *, path_hint: str = "", target_symbol: str = "") -> tuple[list[str], list[dict[str, str]]]:
    headers, rows, _fmt = _parse_barchart_csv(body, path_hint=path_hint, target_symbol=target_symbol)
    return headers, rows


def _group_hint_for_symbol(raw_symbol: str) -> str | None:
    dd = load_data_dictionary()
    groups = (dd.get("universes") or {}).get("barchart_curves", {}).get("symbol_groups") or {}
    for name, syms in groups.items():
        if raw_symbol in syms:
            return name
    return None


def _match_symbol_from_filename(stem: str, approved: set[str]) -> str | None:
    stem_u = stem.upper()
    if stem_u in approved:
        return stem_u
    for sym in approved:
        if sym.upper().replace("!", "") == stem_u.replace("!", ""):
            return sym
    return None


def _as_of_date_from_path(path: Path) -> str:
    m = WATCHLIST_DATE_RE.search(path.name)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _is_watchlist_path(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("watchlist-") and "intraday" in name


def _row_count_for_symbol(path: Path, raw_symbol: str) -> int:
    try:
        headers, rows = _parse_csv_body(
            path.read_bytes(), path_hint=path.name, target_symbol=raw_symbol
        )
    except OSError:
        return 0
    if not rows:
        return 0
    if "Symbol" not in headers:
        return len(rows)
    target = raw_symbol.strip().upper()
    return sum(
        1 for row in rows
        if str(row.get("Symbol", "")).strip().upper() == target
    )


def _symbols_in_historical_csv(path: Path) -> set[str]:
    try:
        headers, rows, fmt = _parse_barchart_csv(path.read_bytes(), path_hint=path.name)
    except OSError:
        return set()
    if fmt == "barchart_interactive_chart":
        sym = _symbol_from_interactive_chart_path(path, set(barchart_all_approved_symbols()))
        return {sym} if sym else set()
    if not headers or "Symbol" not in headers:
        return set()
    return {str(row.get("Symbol", "")).strip().upper() for row in rows if row.get("Symbol", "").strip()}


def hydrate_from_csv_body(
    raw_symbol: str,
    body: bytes,
    *,
    fetch_mode: str,
    source_file: str | None = None,
) -> tuple[dict[str, Any] | None, SymbolOutcome]:
    """Parse Barchart CSV bytes → normalized history record."""
    norm, bucket, outcome = _pending_outcome(raw_symbol)

    path_hint = Path(source_file).name if source_file else ""
    headers, rows, vendor_format = _parse_barchart_csv(
        body, path_hint=path_hint, target_symbol=raw_symbol
    )
    if not rows:
        outcome.status = "empty"
        outcome.reason = "no data rows in CSV"
        return None, outcome

    sym_col = _find_col(headers, "Symbol", "Contract")
    if sym_col:
        target = raw_symbol.strip().upper()
        rows = [
            row for row in rows
            if str(row.get(sym_col, row.get("Symbol", ""))).strip().upper() == target
        ]
        if not rows:
            outcome.status = "empty"
            outcome.reason = f"no rows for {raw_symbol} in CSV"
            return None, outcome

    points = normalize_history_rows(headers, rows)
    if not points:
        outcome.status = "empty"
        outcome.reason = "no parseable history points"
        return None, outcome

    record = _build_history_record(
        raw_symbol=raw_symbol,
        norm=norm,
        bucket=bucket,
        outcome=outcome,
        points=points,
        fetch_mode=fetch_mode,
        source_file=source_file,
        vendor_format=vendor_format,
    )
    outcome.status = "ok"
    outcome.row_count = len(points)
    return record, outcome


def ingest_historical_csv(path: Path, raw_symbol: str) -> tuple[dict[str, Any] | None, SymbolOutcome]:
    """Parse local Barchart daily-nearby historical export."""
    return ingest_supplement(SupplementSource(path, "local_csv_supplement", 100), raw_symbol)


def ingest_watchlist_snapshot(path: Path, raw_symbol: str) -> tuple[dict[str, Any] | None, SymbolOutcome]:
    """Parse Barchart watchlist intraday export as a single-day desk snapshot."""
    norm, bucket, outcome = _pending_outcome(raw_symbol)
    try:
        headers, rows, vendor_format = _parse_barchart_csv(
            path.read_bytes(), path_hint=path.name, target_symbol=raw_symbol
        )
    except OSError as exc:
        outcome.status = "failed"
        outcome.reason = str(exc)
        return None, outcome

    if not rows or not _find_col(headers, "Symbol", "Contract"):
        outcome.status = "empty"
        outcome.reason = "watchlist CSV missing Symbol rows"
        return None, outcome

    as_of = _as_of_date_from_path(path)
    target = raw_symbol.strip().upper()
    rows = [row for row in rows if str(row.get("Symbol", "")).strip().upper() == target]
    if not rows:
        outcome.status = "empty"
        outcome.reason = f"no watchlist row for {raw_symbol}"
        return None, outcome

    if "Time" not in headers:
        headers = list(headers) + ["Time"]
    for row in rows:
        row["Time"] = as_of

    points = normalize_history_rows(headers, rows)
    if not points:
        outcome.status = "empty"
        outcome.reason = "no parseable watchlist points"
        return None, outcome

    record = _build_history_record(
        raw_symbol=raw_symbol,
        norm=norm,
        bucket=bucket,
        outcome=outcome,
        points=points,
        fetch_mode="watchlist_snapshot_supplement",
        source_file=str(path),
        vendor_format=vendor_format,
    )
    outcome.status = "ok"
    outcome.row_count = len(points)
    return record, outcome


def ingest_supplement(
    source: SupplementSource,
    raw_symbol: str,
) -> tuple[dict[str, Any] | None, SymbolOutcome]:
    if source.fetch_mode == "watchlist_snapshot_supplement":
        return ingest_watchlist_snapshot(source.path, raw_symbol)
    try:
        body = source.path.read_bytes()
    except OSError as exc:
        _, _, outcome = _pending_outcome(raw_symbol)
        outcome.status = "failed"
        outcome.reason = str(exc)
        return None, outcome
    return hydrate_from_csv_body(
        raw_symbol,
        body,
        fetch_mode=source.fetch_mode,
        source_file=str(source.path),
    )


def discover_local_supplements(dirs: list[Path]) -> dict[str, SupplementSource]:
    """Map approved symbol -> best real desk CSV supplement (history > daily > watchlist)."""
    approved = set(barchart_all_approved_symbols())
    found: dict[str, SupplementSource] = {}

    def _consider(sym: str, path: Path, fetch_mode: str, priority: int) -> None:
        if sym not in approved:
            return
        if _skip_supplement_path(path):
            return
        if fetch_mode == "local_csv_supplement":
            priority += _row_count_for_symbol(path, sym)
        candidate = SupplementSource(path, fetch_mode, priority)
        current = found.get(sym)
        if current is None or candidate.priority > current.priority:
            found[sym] = candidate

    for d in dirs:
        if not d.is_dir():
            continue
        paths: list[Path] = []
        for pat in (
            "*daily-nearby_historical*.csv",
            "futures_daily_*.csv",
            "*_Barchart_Interactive_Chart_*.csv",
            "*-prices-intraday-*.csv",
            "futures-spreads-*.csv",
            "watchlist-wtm-canonical-universe-intraday*.csv",
            "watchlist-dailymonitor*-intraday*.csv",
        ):
            paths.extend(sorted(d.rglob(pat)))
        for path in paths:
            if _is_watchlist_path(path):
                for sym in _symbols_in_historical_csv(path):
                    _consider(sym, path, "watchlist_snapshot_supplement", 20)
                continue
            if INTERACTIVE_CHART_RE.match(path.name):
                sym = _symbol_from_interactive_chart_path(path, approved)
                if sym:
                    _consider(sym, path, "local_csv_supplement", 95)
                continue
            if "futures_daily_" in path.name:
                for sym in _symbols_in_historical_csv(path):
                    _consider(sym, path, "staged_futures_daily", 40)
                continue
            if path.name.startswith("futures-spreads-"):
                continue
            stem = path.name.split("_daily-nearby")[0].split("__")[-1]
            if stem.endswith(".csv"):
                stem = Path(stem).stem
            sym = _match_symbol_from_filename(stem, approved)
            if sym:
                _consider(sym, path, "local_csv_supplement", 80)
            for csv_sym in _symbols_in_historical_csv(path):
                _consider(csv_sym, path, "local_csv_supplement", 80)
    return found


def discover_local_historical_csvs(dirs: list[Path]) -> dict[str, Path]:
    """Backward-compatible path map from discover_local_supplements."""
    return {sym: src.path for sym, src in discover_local_supplements(dirs).items()}


def hydrate_symbol(
    raw_symbol: str,
    *,
    api_key: str,
    start_date: str = "20250101",
    supplement: SupplementSource | None = None,
    local_csv: Path | None = None,
    file_only: bool = True,
) -> tuple[dict[str, Any] | None, SymbolOutcome]:
    _, _, outcome = _pending_outcome(raw_symbol)

    src = supplement
    if src is None and local_csv and local_csv.exists():
        src = SupplementSource(local_csv, "local_csv_supplement", 100)
    if src is not None and src.path.exists():
        return ingest_supplement(src, raw_symbol)

    if file_only or not api_key:
        outcome.status = "failed"
        outcome.reason = "no local CSV supplement (file-only desk path)"
        return None, outcome

    try:
        body = fetch_barchart_daily_csv(raw_symbol, api_key=api_key, start_date=start_date)
    except urllib.error.HTTPError as exc:
        outcome.status = "failed"
        outcome.reason = f"HTTP {exc.code}"
        return None, outcome
    except Exception as exc:
        outcome.status = "failed"
        outcome.reason = str(exc)
        return None, outcome

    if not body or not body.strip():
        outcome.status = "empty"
        outcome.reason = "empty response body"
        return None, outcome

    return hydrate_from_csv_body(raw_symbol, body, fetch_mode="api")


def format_symbol_outcome_line(outcome: SymbolOutcome) -> str:
    parts = [
        f"symbol={outcome.raw_symbol}",
        f"bucket={outcome.bucket}",
        f"status={outcome.status}",
        f"canonical_id={outcome.canonical_id}",
    ]
    if outcome.row_count:
        parts.append(f"row_count={outcome.row_count}")
    if outcome.reason:
        parts.append(f"reason={outcome.reason}")
    return " ".join(parts)


def run_barchart_hydration(
    *,
    api_key: str | None = None,
    output_dir: Path | None = None,
    start_date: str = "20250101",
    symbols: list[str] | None = None,
    supplement_dirs: list[Path] | None = None,
    verbose: bool = True,
    log_fn: Any = None,
    file_only: bool = True,
) -> dict[str, Any]:
    key = load_barchart_api_key(api_key) if not file_only else ""

    out_dir = output_dir or default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    approved = symbols or barchart_all_approved_symbols()
    dirs = default_supplement_dirs() if supplement_dirs is None else supplement_dirs
    supplement_map = discover_local_supplements(dirs)
    emit: Callable[..., None] = log_fn if log_fn is not None else (print if verbose else lambda *_a, **_k: None)

    core_hist: list[dict[str, Any]] = []
    curve_hist: list[dict[str, Any]] = []
    spread_hist: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []

    for raw in approved:
        record, outcome = hydrate_symbol(
            raw,
            api_key=key,
            start_date=start_date,
            supplement=supplement_map.get(raw),
            file_only=file_only,
        )
        supplement = supplement_map.get(raw)
        outcomes.append({
            "raw_symbol": outcome.raw_symbol,
            "bucket": outcome.bucket,
            "status": outcome.status,
            "canonical_id": outcome.canonical_id,
            "row_count": outcome.row_count,
            "reason": outcome.reason,
            "contract_meta": outcome.contract_meta,
            "spread_meta": outcome.spread_meta,
            "fetch_mode": supplement.fetch_mode if supplement else "",
            "source_file": str(supplement.path) if supplement else "",
            "vendor_format": record.get("vendor_format", "") if record else "",
        })
        emit(format_symbol_outcome_line(outcome))
        if record is None:
            continue
        if outcome.bucket == "core":
            core_hist.append(record)
        elif outcome.bucket == "spread":
            spread_hist.append(record)
        else:
            curve_hist.append(record)

    manifest = {
        "barchart_hydration_version": BARCHART_HYDRATION_VERSION,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "barchart_only",
        "fetch_policy": "file_only" if file_only else "file_with_api_fallback",
        "api_key_present": bool(key),
        "supplement_dirs": [str(d) for d in dirs],
        "local_supplements": {
            k: {"path": str(v.path), "fetch_mode": v.fetch_mode, "priority": v.priority}
            for k, v in supplement_map.items()
        },
        "symbol_count_approved": len(approved),
        "symbol_count_ok": sum(1 for o in outcomes if o["status"] == "ok"),
        "symbol_count_failed": sum(1 for o in outcomes if o["status"] == "failed"),
        "symbol_count_empty": sum(1 for o in outcomes if o["status"] == "empty"),
        "outcomes": outcomes,
    }

    payloads = {
        "barchart_core_history": {
            "version": BARCHART_HYDRATION_VERSION,
            "bucket": "core",
            "as_of": manifest["as_of"],
            "symbol_count": len(core_hist),
            "records": core_hist,
        },
        "barchart_curve_history": {
            "version": BARCHART_HYDRATION_VERSION,
            "bucket": "curve",
            "as_of": manifest["as_of"],
            "symbol_count": len(curve_hist),
            "records": curve_hist,
        },
        "barchart_spread_history": {
            "version": BARCHART_HYDRATION_VERSION,
            "bucket": "spread",
            "as_of": manifest["as_of"],
            "symbol_count": len(spread_hist),
            "records": spread_hist,
        },
        "barchart_run_manifest": manifest,
    }

    paths: dict[str, str] = {}
    for name, payload in payloads.items():
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        paths[name] = str(path)

    return {
        "ok": True,
        "paths": paths,
        "manifest": manifest,
        "counts": {
            "approved": len(approved),
            "core_ok": len(core_hist),
            "curve_ok": len(curve_hist),
            "spread_ok": len(spread_hist),
        },
    }