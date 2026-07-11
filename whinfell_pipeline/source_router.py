"""ARCH-1 — unified ingest routing via Master Data Dictionary source_systems."""

from __future__ import annotations

import csv
import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whinfell_pipeline.data_dictionary import (
    barchart_all_approved_symbols,
    barchart_core_symbols,
    barchart_curve_symbols,
    canonical_asset_for_ticker,
    load_data_dictionary,
    source_system_ids,
)
from whinfell_pipeline.raw_csv_transform import detect_vendor_format

_BARCHART_SYMBOL_RE = re.compile(
    r"(?:^|__)([a-z]{1,6}\d{1,2}[a-z]?\d{0,2})",
    re.I,
)


@dataclass
class RouteResult:
    path: str
    source_class: str = "unknown"
    vendor: str = ""
    priority: str = ""
    parser: str = ""
    output_kinds: list[str] = field(default_factory=list)
    vendor_format: str = ""
    symbols: list[str] = field(default_factory=list)
    canonical_assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    matched_by: str = ""

    def to_meta(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "vendor": self.vendor,
            "priority": self.priority,
            "parser": self.parser,
            "output_kinds": self.output_kinds,
            "vendor_format": self.vendor_format,
            "symbols": self.symbols,
            "canonical_assets": self.canonical_assets,
            "matched_by": self.matched_by,
            "warnings": self.warnings,
        }


def _read_csv_headers(path: Path) -> tuple[list[str], str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], str(exc)
    if not text.strip():
        return [], ""
    first = text.splitlines()[0]
    try:
        headers = next(csv.reader([first]))
    except csv.Error:
        headers = [c.strip().strip('"') for c in first.split(",")]
    return headers, first


def _norm_headers(headers: list[str]) -> set[str]:
    return {h.strip().strip('"').lower() for h in headers if h and h.strip()}


def _filename_tokens(name: str) -> list[str]:
    stem = Path(name).stem.lower()
    tokens = re.split(r"[_\-\s]+", stem)
    return [t for t in tokens if t]


def extract_barchart_symbols(filename: str) -> list[str]:
    """Pull contract/symbol tokens from native Barchart export filenames."""
    name = filename.lower()
    found: list[str] = []
    for m in _BARCHART_SYMBOL_RE.finditer(name):
        sym = m.group(1).upper()
        if sym not in found:
            found.append(sym)
    for token in _filename_tokens(name):
        if re.fullmatch(r"[a-z]{1,6}\d{1,2}[a-z]?\d{0,2}", token, re.I):
            sym = token.upper()
            if sym not in found:
                found.append(sym)
    for pat in (
        r"([a-z0-9]{3,12})_daily_historical",
        r"([a-z0-9]{3,12})_daily-nearby_historical",
        r"^([a-z0-9]{3,12})-volatility-greeks",
        r"^([a-z0-9]{3,12})-options",
    ):
        m = re.search(pat, name)
        if m:
            sym = m.group(1).upper()
            if sym not in found:
                found.append(sym)
    if "futures-spreads" in name:
        m = re.search(r"futures-spreads-([a-z0-9]+)", name)
        if m:
            sym = m.group(1).upper()
            if sym not in found:
                found.append(sym)
    return found


def _infer_vendor_format(headers: list[str], filename: str, header_line: str = "") -> str:
    fmt = detect_vendor_format(headers, filename, header_line=header_line)
    if fmt != "unknown":
        return fmt
    norm = _norm_headers(headers)
    if {"time", "latest", "open", "high", "low"} <= norm:
        return "barchart_historical"
    if {"time", "latest"} <= norm:
        return "barchart_historical"
    return fmt


def _headers_match(detect: dict[str, Any], headers: list[str], filename: str) -> bool:
    norm = _norm_headers(headers)
    hl = ",".join(headers)

    for req in detect.get("headers_any") or []:
        if str(req).lower() not in norm and str(req) not in headers:
            return False

    pattern = detect.get("headers_pattern")
    if pattern and pattern not in hl:
        return False

    min_close = detect.get("min_close_columns")
    if min_close is not None:
        close_cols = sum(1 for h in norm if "close" in h)
        if close_cols < int(min_close):
            return False

    patterns = detect.get("filename_patterns") or []
    if patterns:
        lower = filename.lower()
        if not any(fnmatch.fnmatch(lower, str(p).lower()) for p in patterns):
            return False

    prefix = detect.get("saved_view_prefix")
    if prefix and not Path(filename).stem.upper().startswith(str(prefix).upper()):
        return False

    return True


def _symbol_aliases(sym: str) -> set[str]:
    s = sym.upper().strip()
    aliases = {s, f"^{s}", f"${s}"}
    if s.startswith("^"):
        aliases.add(s[1:])
    if s.startswith("$"):
        aliases.add(s[1:])
    return aliases


def _symbol_in_universe(symbols: list[str], universe: list[str]) -> bool:
    approved: set[str] = set()
    for u in universe:
        approved |= _symbol_aliases(str(u))
    for sym in symbols:
        if _symbol_aliases(sym) & approved:
            return True
    return False


def _resolve_canonical_assets(vendor: str, symbols: list[str]) -> list[str]:
    assets: list[str] = []
    for sym in symbols:
        aid = canonical_asset_for_ticker(vendor, sym)
        if aid and aid not in assets:
            assets.append(aid)
    return assets


def _match_source_system(
    system_id: str,
    spec: dict[str, Any],
    *,
    headers: list[str],
    filename: str,
    symbols: list[str],
    dd: dict[str, Any],
) -> RouteResult | None:
    detect = spec.get("detect") or {}
    if not _headers_match(detect, headers, filename):
        return None

    if detect.get("symbol_in") == "barchart_core":
        if not _symbol_in_universe(symbols, barchart_core_symbols(dd)):
            return None
    elif detect.get("symbol_in") == "barchart_curves":
        if not _symbol_in_universe(symbols, barchart_curve_symbols(dd)):
            return None

    vendor = str(spec.get("vendor") or "")
    return RouteResult(
        path="",
        source_class=system_id,
        vendor=vendor,
        priority=str(spec.get("priority") or ""),
        parser=str(spec.get("parser") or ""),
        output_kinds=[str(o) for o in (spec.get("outputs") or [])],
        symbols=symbols,
        canonical_assets=_resolve_canonical_assets(vendor, symbols),
        matched_by=f"source_systems.{system_id}",
    )


# Specificity-ordered — first match wins
_SOURCE_ORDER = [
    "koyfin_saved_chart",
    "koyfin_correlation_csv",
    "koyfin_snapshot_csv",
    "koyfin_wide_timeseries",
    "koyfin_dashboard_object",
    "barchart_curve_history",
    "barchart_core_history",
    "barchart_quote_snapshot",
]


def route_ingest(path: str | Path, *, data: dict[str, Any] | None = None) -> RouteResult:
    """Classify a CSV for ingest routing (dictionary-driven, delegates to legacy detectors)."""
    p = Path(path)
    dd = data or load_data_dictionary()
    headers, header_line = _read_csv_headers(p)
    filename = p.name
    symbols = extract_barchart_symbols(filename)

    result = RouteResult(path=str(p.resolve()))

    if not headers:
        result.warnings.append("empty or unreadable CSV headers")
        return result

    try:
        from whinfell_pipeline.crypto_sleeve import detect_crypto_source_type

        crypto_type = detect_crypto_source_type(headers, filename)
    except Exception:
        crypto_type = "unknown"

    result.vendor_format = _infer_vendor_format(headers, filename, header_line=header_line)
    if crypto_type != "unknown":
        result.warnings.append(f"crypto_sleeve_type:{crypto_type}")

    if result.vendor_format in ("barchart_historical", "barchart_volgreeks", "barchart_options", "barchart_spreads"):
        if symbols and _symbol_in_universe(symbols, barchart_all_approved_symbols(dd)):
            spec = (dd.get("source_systems") or {}).get("barchart_core_history") or {}
            return RouteResult(
                path=result.path,
                source_class="barchart_core_history",
                vendor="barchart",
                priority=str(spec.get("priority") or "primary"),
                parser=str(spec.get("parser") or ""),
                output_kinds=[str(o) for o in (spec.get("outputs") or [])],
                vendor_format=result.vendor_format,
                symbols=symbols,
                canonical_assets=_resolve_canonical_assets("barchart", symbols),
                warnings=list(result.warnings),
                matched_by="barchart_vendor_format",
            )

    systems = dd.get("source_systems") or {}
    order = [sid for sid in _SOURCE_ORDER if sid in systems]
    order.extend(sid for sid in source_system_ids(dd) if sid not in order)

    for system_id in order:
        spec = systems.get(system_id)
        if not isinstance(spec, dict):
            continue
        hit = _match_source_system(
            system_id,
            spec,
            headers=headers,
            filename=filename,
            symbols=symbols,
            dd=dd,
        )
        if hit:
            hit.path = result.path
            hit.vendor_format = result.vendor_format
            hit.warnings = list(result.warnings)
            return hit

    # Filename-only fallback for approved Barchart symbols without header match
    if symbols and _symbol_in_universe(symbols, barchart_all_approved_symbols(dd)):
        result.source_class = "barchart_core_history"
        result.vendor = "barchart"
        result.priority = "primary"
        result.symbols = symbols
        result.canonical_assets = _resolve_canonical_assets("barchart", symbols)
        result.output_kinds = ["historical_timeseries"]
        result.matched_by = "barchart_symbol_fallback"
        return result

    result.warnings.append("no source_system match")
    return result