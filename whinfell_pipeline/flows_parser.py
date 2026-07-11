"""WTM-Flows CSV → L1 sidecar — PR-3a."""

from __future__ import annotations

import csv
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from whinfell_pipeline.data_dictionary import (
    canonical_asset_for_ticker,
    funds_flow_basket_for_node,
    funds_flow_column_map,
    funds_flow_sidecar_path,
    get_funds_flow_ingest,
)

__all__ = [
    "assess_flows_basket_health",
    "compute_rolling_metrics",
    "default_flows_sidecar_path",
    "detect_flows_format",
    "ensure_flows_sidecar",
    "find_latest_quarantine_flows_csv",
    "parse_and_write",
    "parse_flows_csv",
    "try_parse_flows_csv",
    "write_flows_sidecar",
]

_SIDECAR_VERSION = "1.0.0"
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y")


def _norm_header(header: str) -> str:
    return header.strip().lower()


def _parse_float(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("%", "")
    if not s or s in ("—", "-", "n/a", "na"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(val: str) -> str | None:
    s = str(val or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def detect_flows_format(headers: list[str]) -> str:
    """Return wtm_flows_wide | invalid."""
    norm = [_norm_header(h) for h in headers]
    if not any(h == "date" for h in norm):
        return "invalid"
    has_flow = any("flow" in h and ("(d)" in h or "periodic" in h) for h in norm)
    if not has_flow:
        return "invalid"
    return "wtm_flows_wide"


def _column_patterns() -> dict[str, list[str]]:
    return funds_flow_column_map()


def _match_ticker_columns(headers: list[str]) -> dict[str, dict[str, str]]:
    """Map ticker -> {field: header_name}."""
    patterns = _column_patterns()
    tickers: dict[str, dict[str, str]] = {}
    for header in headers:
        nh = _norm_header(header)
        if nh == "date":
            continue
        for field, pats in patterns.items():
            for pat in pats:
                m = re.match(r"^" + re.escape(pat.replace("{TICKER}", r"([A-Za-z0-9.]+)")).replace(r"\(\[A-Za-z0-9.\]\+\)", r"([A-Za-z0-9.]+)") + r"$", header, re.I)
                if not m and "{TICKER}" in pat:
                    escaped = pat.replace("{TICKER}", "")
                    if escaped.lower() in nh:
                        prefix = header[: header.lower().index(escaped.lower())].strip()
                        if prefix:
                            ticker = prefix.upper()
                            tickers.setdefault(ticker, {})[field] = header
                elif m:
                    ticker = m.group(1).upper()
                    tickers.setdefault(ticker, {})[field] = header
    # Fallback: "{TICKER} Flow (D)" style via split
    for header in headers:
        nh = _norm_header(header)
        for suffix, field in (
            (" flow (d)", "flow_usd_1d"),
            (" flow % aum (d)", "flow_pct_aum_1d"),
            (" aum", "aum_usd"),
        ):
            if nh.endswith(suffix):
                ticker = header[: len(header) - len(suffix)].strip().upper()
                if ticker and field not in tickers.get(ticker, {}):
                    tickers.setdefault(ticker, {})[field] = header
    return tickers


def compute_rolling_metrics(
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    """5D sums and persistence from ordered session rows (oldest→newest)."""
    if not sessions:
        return {
            "flow_usd_5d": None,
            "flow_pct_aum_5d": None,
            "sessions_in_5d": 0,
            "persistence_score_20d": None,
        }
    tail5 = sessions[-5:]
    flow_usd_5d = sum(float(s["flow_usd_1d"]) for s in tail5 if s.get("flow_usd_1d") is not None)
    pct_vals = [float(s["flow_pct_aum_1d"]) for s in tail5 if s.get("flow_pct_aum_1d") is not None]
    flow_pct_aum_5d = sum(pct_vals) if pct_vals else None
    tail20 = sessions[-20:]
    persistence = None
    if flow_pct_aum_5d is not None and tail20:
        sign_5d = 1 if flow_pct_aum_5d > 0 else (-1 if flow_pct_aum_5d < 0 else 0)
        if sign_5d != 0:
            matches = sum(
                1 for s in tail20
                if s.get("flow_pct_aum_1d") is not None
                and ((float(s["flow_pct_aum_1d"]) > 0) == (sign_5d > 0))
            )
            persistence = round(matches / min(20, len(tail20)), 2)
    return {
        "flow_usd_5d": round(flow_usd_5d, 2) if tail5 else None,
        "flow_pct_aum_5d": round(flow_pct_aum_5d, 4) if flow_pct_aum_5d is not None else None,
        "sessions_in_5d": len(tail5),
        "persistence_score_20d": persistence,
    }


def parse_flows_csv(path: Path | str, *, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Parse WTM-Flows wide CSV into L1 sidecar dict."""
    if rows is not None:
        parsed_rows = rows
        headers = list(rows[0].keys()) if rows else []
        source_file = "inline_rows"
    else:
        p = Path(path)
        with p.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                raise ValueError("missing header row")
            headers = list(reader.fieldnames)
            parsed_rows = [dict(r) for r in reader]
        source_file = p.name

    fmt = detect_flows_format(headers)
    if fmt != "wtm_flows_wide":
        raise ValueError(f"unsupported flows format: {fmt}")

    patterns = _column_patterns()
    date_col = next((h for h in headers if _norm_header(h) == "date"), None)
    if not date_col:
        raise ValueError("missing Date column")

    ticker_cols = _match_ticker_columns(headers)
    if not ticker_cols:
        raise ValueError("no ticker flow columns detected")

    series_by_ticker: dict[str, list[dict[str, Any]]] = {t: [] for t in ticker_cols}

    for row in parsed_rows:
        date = _parse_date(str(row.get(date_col) or ""))
        if not date:
            continue
        for ticker, cols in ticker_cols.items():
            flow_usd = _parse_float(row.get(cols.get("flow_usd_1d", "")))
            aum = _parse_float(row.get(cols.get("aum_usd", "")))
            flow_pct = _parse_float(row.get(cols.get("flow_pct_aum_1d", "")))
            if flow_pct is None and flow_usd is not None and aum and aum > 0:
                flow_pct = (flow_usd / aum) * 100.0
            if flow_usd is None and flow_pct is not None and aum and aum > 0:
                flow_usd = (flow_pct / 100.0) * aum
            if flow_usd is None and flow_pct is None:
                continue
            series_by_ticker[ticker].append({
                "date": date,
                "flow_usd_1d": flow_usd,
                "aum_usd": aum,
                "flow_pct_aum_1d": flow_pct,
            })

    tickers_out: dict[str, Any] = {}
    latest_date = ""
    max_sessions = 0
    for ticker, sessions in series_by_ticker.items():
        if not sessions:
            continue
        sessions.sort(key=lambda s: s["date"])
        latest = sessions[-1]
        rolling = compute_rolling_metrics(sessions)
        asset_id = canonical_asset_for_ticker("koyfin", ticker) or ""
        tail = sessions[-20:]
        tickers_out[ticker] = {
            "ticker": ticker,
            "asset_id": asset_id,
            "canonical_asset_resolved": bool(asset_id),
            "latest": {
                "date": latest["date"],
                "flow_usd_1d": latest.get("flow_usd_1d"),
                "aum_usd": latest.get("aum_usd"),
                "flow_pct_aum_1d": latest.get("flow_pct_aum_1d"),
            },
            "rolling": rolling,
            "series_tail": [
                {
                    "date": s["date"],
                    "flow_usd_1d": s.get("flow_usd_1d"),
                    "aum_usd": s.get("aum_usd"),
                    "flow_pct_aum_1d": s.get("flow_pct_aum_1d"),
                }
                for s in tail
            ],
        }
        if latest["date"] > latest_date:
            latest_date = latest["date"]
        max_sessions = max(max_sessions, len(sessions))

    ingest = get_funds_flow_ingest()
    return {
        "version": _SIDECAR_VERSION,
        "as_of": latest_date or datetime.now().date().isoformat(),
        "source_file": source_file,
        "source_channel": ingest.get("source_channel_primary", "koyfin_wtm_flows"),
        "ingest_mode": "timeseries_primary",
        "units": dict(ingest.get("units") or {
            "flow_usd": "millions_usd",
            "aum_usd": "millions_usd",
            "flow_pct_aum": "percent",
        }),
        "history_sessions": max_sessions,
        "tickers": tickers_out,
        "fallback_overlay": {"active": False, "source": None, "tickers_patched": []},
        "warnings": [],
    }


def write_flows_sidecar(payload: Mapping[str, Any], path: Path | str) -> Path:
    """Atomic write of L1 sidecar."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".json.tmp")
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        Path(tmp).replace(p)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return p


def default_flows_sidecar_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / funds_flow_sidecar_path()


def parse_and_write(csv_path: Path | str, output_path: Path | str | None = None) -> dict[str, Any]:
    """Parse CSV and write sidecar; return payload."""
    payload = parse_flows_csv(csv_path)
    out = Path(output_path) if output_path else default_flows_sidecar_path()
    write_flows_sidecar(payload, out)
    return payload


def try_parse_flows_csv(path: Path | str) -> dict[str, Any] | None:
    """Parse flows CSV; return None when file missing (no exception)."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return parse_flows_csv(p)
    except (ValueError, OSError):
        return None


def find_latest_quarantine_flows_csv(repo_root: Path) -> Path | None:
    """Newest quarantine WTM-Flows-Global.csv (or flows_global.csv fallback)."""
    quarantine = repo_root / "staged_raw" / "quarantine"
    if not quarantine.is_dir():
        return None
    for day_dir in sorted(quarantine.iterdir(), reverse=True):
        if not day_dir.is_dir():
            continue
        for name in ("WTM-Flows-Global.csv", "flows_global.csv"):
            p = day_dir / name
            if p.is_file():
                return p
    return None


def _canonical_flows_csv_paths(repo_root: Path) -> list[Path]:
    """Production quarantine CSV first; head fixture as fallback."""
    candidates: list[Path] = []
    latest = find_latest_quarantine_flows_csv(repo_root)
    if latest is not None:
        candidates.append(latest)
    quarantine = repo_root / "staged_raw" / "quarantine"
    if quarantine.is_dir():
        for day_dir in sorted(quarantine.iterdir(), reverse=True):
            if not day_dir.is_dir():
                continue
            for name in ("WTM-Flows-Global.csv", "flows_global.csv"):
                p = day_dir / name
                if p.is_file() and p not in candidates:
                    candidates.append(p)
            for p in sorted(day_dir.glob("flows_*.csv"), reverse=True):
                if p not in candidates:
                    candidates.append(p)
    head_fixture = repo_root / "whinfell_pipeline" / "examples" / "flows" / "WTM-Flows-Global-head.csv"
    if head_fixture.is_file():
        candidates.append(head_fixture)
    return candidates


def assess_flows_basket_health(
    sidecar: Mapping[str, Any] | None,
    node_id: str = "credit",
) -> dict[str, Any]:
    """Assess node basket coverage against L1 sidecar tickers."""
    basket = funds_flow_basket_for_node(node_id) or {}
    etfs = list(basket.get("etfs") or [])
    expected = [str(e.get("ticker") or "").upper() for e in etfs if e.get("ticker")]

    if not sidecar:
        return {
            "status": "unavailable",
            "node_id": node_id,
            "missing_tickers": expected,
            "warnings": ["missing_wtm_flows_file"],
        }

    sidecar_tickers = sidecar.get("tickers") or {}
    missing_tickers: list[str] = []
    for ticker in expected:
        row = sidecar_tickers.get(ticker)
        if not isinstance(row, dict):
            missing_tickers.append(ticker)
            continue
        rolling = row.get("rolling") or {}
        if rolling.get("flow_pct_aum_5d") is None:
            missing_tickers.append(ticker)

    warnings: list[str] = list(sidecar.get("warnings") or [])
    if not expected:
        return {
            "status": "unavailable",
            "node_id": node_id,
            "missing_tickers": [],
            "warnings": warnings + ["no_basket_defined"],
        }
    if not missing_tickers:
        status = "ok"
    elif len(missing_tickers) < len(expected):
        status = "partial"
        warnings.append("partial_basket_coverage")
        warnings.append(f"missing_basket_etfs:{','.join(missing_tickers)}")
    else:
        status = "unavailable"
        if "missing_wtm_flows_file" not in warnings:
            warnings.append("missing_wtm_flows_file")

    deduped = list(dict.fromkeys(warnings))
    return {
        "status": status,
        "node_id": node_id,
        "missing_tickers": missing_tickers,
        "warnings": deduped,
    }


def _sidecar_is_viable(payload: Mapping[str, Any] | None) -> bool:
    """Minimum production parse — timeseries or dated snapshot fallback."""
    if not payload or not isinstance(payload, dict):
        return False
    mode = str(payload.get("ingest_mode") or "")
    tickers = (payload or {}).get("tickers") or {}
    if mode == "fallback_1d_only":
        return len(tickers) >= 1 and bool(str(payload.get("as_of") or "").strip())
    if mode == "timeseries_primary":
        return len(tickers) >= 1
    return False


def _sidecar_is_healthy(payload: Mapping[str, Any] | None) -> bool:
    if not _sidecar_is_viable(payload):
        return False
    mode = str(payload.get("ingest_mode") or "")
    tickers = (payload or {}).get("tickers") or {}
    if mode == "fallback_1d_only":
        return len(tickers) >= 1
    return len(tickers) >= 10


def ensure_flows_sidecar(repo_root: Path | None = None) -> dict[str, Any] | None:
    """Ensure L1 sidecar; refresh when quarantine CSV is newer than sidecar mtime."""
    root = repo_root or Path(__file__).resolve().parents[1]
    out_path = default_flows_sidecar_path(root)
    latest_quarantine = find_latest_quarantine_flows_csv(root)
    existing: dict[str, Any] | None = None
    should_refresh = not out_path.is_file()

    if out_path.is_file():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if not _sidecar_is_healthy(existing):
                should_refresh = True
            elif latest_quarantine is not None and latest_quarantine.stat().st_mtime > out_path.stat().st_mtime:
                should_refresh = True
            elif not should_refresh:
                return dict(existing)
        except (json.JSONDecodeError, OSError):
            should_refresh = True

    if should_refresh:
        def _try_refresh(csv_path: Path, *, require_healthy: bool) -> dict[str, Any] | None:
            payload = try_parse_flows_csv(csv_path)
            if not payload:
                return None
            ok = _sidecar_is_healthy(payload) if require_healthy else _sidecar_is_viable(payload)
            if not ok:
                return None
            write_flows_sidecar(payload, out_path)
            return payload

        quarantine_is_newer = (
            latest_quarantine is not None
            and out_path.is_file()
            and latest_quarantine.stat().st_mtime > out_path.stat().st_mtime
        )
        if quarantine_is_newer:
            refreshed = _try_refresh(latest_quarantine, require_healthy=False)
            if refreshed is not None:
                return refreshed
        for csv_path in _canonical_flows_csv_paths(root):
            refreshed = _try_refresh(csv_path, require_healthy=True)
            if refreshed is not None:
                return refreshed

    if existing is not None:
        return dict(existing)
    if out_path.is_file():
        try:
            return dict(json.loads(out_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Parse WTM-Flows CSV → L1 sidecar JSON")
    parser.add_argument("--input", "-i", required=True, help="flows_*.csv or WTM-Flows-Global.csv path")
    parser.add_argument("--output", "-o", default=None, help="Sidecar output (default: data/flows/v1/latest_flows.json)")
    args = parser.parse_args(argv)
    try:
        payload = parse_and_write(args.input, args.output)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    out = Path(args.output) if args.output else default_flows_sidecar_path()
    print(f"flows_parser_ok tickers={len(payload.get('tickers') or {})} sessions={payload.get('history_sessions')}")
    print(f"output={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


