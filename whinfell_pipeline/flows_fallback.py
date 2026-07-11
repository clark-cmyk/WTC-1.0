"""Credit cross-section 1D flow fallback — PR-3b (Credit node only)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from whinfell_pipeline.data_dictionary import funds_flow_basket_for_node

_CREDIT_FLOW_COL = "fund flows/periodic (d)"
_CREDIT_TICKER_COL = "ticker"
_CREDIT_AUM_COL = "aum"

_SIDECAR_VERSION = "1.0.0"


def _norm_header(header: str) -> str:
    return header.strip().lower()


def _find_column(headers: list[str], *candidates: str) -> str | None:
    norm_map = {_norm_header(h): h for h in headers}
    for cand in candidates:
        key = cand.lower()
        if key in norm_map:
            return norm_map[key]
    for h in headers:
        nh = _norm_header(h)
        for cand in candidates:
            if cand.lower() in nh:
                return h
    return None


def parse_credit_cross_section_flows(
    path: Path | str,
    *,
    rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Parse credit snapshot CSV rows into 1D flow records.

    Expects Ticker, AUM, and Fund Flows/Periodic (D) columns (Koyfin credit export).
    """
    parsed_rows: list[dict[str, Any]]
    if rows is not None:
        parsed_rows = rows
        headers = list(rows[0].keys()) if rows else []
    else:
        p = Path(path)
        with p.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                return []
            headers = list(reader.fieldnames)
            parsed_rows = [dict(row) for row in reader]

    ticker_col = _find_column(headers, "Ticker", _CREDIT_TICKER_COL)
    aum_col = _find_column(headers, "AUM", _CREDIT_AUM_COL)
    flow_col = _find_column(headers, "Fund Flows/Periodic (D)", _CREDIT_FLOW_COL)
    if not ticker_col or not aum_col or not flow_col:
        return []

    credit_basket = funds_flow_basket_for_node("credit") or {}
    allowed = {str(e["ticker"]).upper() for e in credit_basket.get("etfs", [])}

    out: list[dict[str, Any]] = []
    for row in parsed_rows:
        ticker = str(row.get(ticker_col) or "").strip().upper()
        if not ticker or ticker not in allowed:
            continue
        try:
            aum = float(str(row.get(aum_col) or "").replace(",", ""))
            flow_usd = float(str(row.get(flow_col) or "").replace(",", ""))
        except (TypeError, ValueError):
            continue
        if aum <= 0:
            continue
        flow_pct = (flow_usd / aum) * 100.0
        etf_spec = next(
            (e for e in credit_basket.get("etfs", []) if str(e.get("ticker", "")).upper() == ticker),
            {},
        )
        out.append(
            {
                "ticker": ticker,
                "asset_id": str(etf_spec.get("asset_id") or ""),
                "flow_usd_1d": flow_usd,
                "aum_usd": aum,
                "flow_pct_aum_1d": round(flow_pct, 4),
            }
        )
    return out


def merge_fallback_into_sidecar(
    sidecar: dict[str, Any] | None,
    credit_rows: list[dict[str, Any]],
    *,
    as_of: str = "",
    source_file: str = "credit_cross_section",
) -> dict[str, Any]:
    """
    Patch Credit basket tickers with 1D-only data; never writes 5D rolling fields.
    """
    base: dict[str, Any] = dict(sidecar) if sidecar else {}
    tickers: dict[str, Any] = dict(base.get("tickers") or {})
    session_date = as_of or base.get("as_of") or ""

    for row in credit_rows:
        ticker = str(row["ticker"]).upper()
        tickers[ticker] = {
            "ticker": ticker,
            "asset_id": row.get("asset_id") or "",
            "canonical_asset_resolved": bool(row.get("asset_id")),
            "latest": {
                "date": session_date,
                "flow_usd_1d": row["flow_usd_1d"],
                "aum_usd": row["aum_usd"],
                "flow_pct_aum_1d": row["flow_pct_aum_1d"],
            },
            "rolling": {},
            "series_tail": [],
        }

    patched = [str(r["ticker"]).upper() for r in credit_rows]
    return {
        "version": base.get("version") or _SIDECAR_VERSION,
        "as_of": session_date,
        "source_file": source_file,
        "source_channel": "credit_cross_section_fallback",
        "ingest_mode": "fallback_1d_only",
        "units": base.get("units")
        or {
            "flow_usd": "millions_usd",
            "aum_usd": "millions_usd",
            "flow_pct_aum": "percent",
        },
        "tickers": tickers,
        "fallback_overlay": {
            "active": True,
            "source": "credit_cross_section",
            "tickers_patched": patched,
        },
        "warnings": list(base.get("warnings") or []),
    }