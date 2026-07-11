"""Batch CSV collection orchestrator — replaces slow per-ticker agent downloads."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

MANIFEST_NAME = "collection_manifest.yaml"
DESK_URLS_NAME = "desk_urls.yaml"
ENV_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")

# Maps batch_export id → desk_urls.yaml key path
_BATCH_DESK_KEYS: dict[str, tuple[str, str]] = {
    "koyfin_rates": ("koyfin", "WTM-Rates-Credit"),
    "koyfin_equities": ("koyfin", "WTM-Equities-Breadth"),
    "koyfin_import_core": ("koyfin", "WTM-Import-Core"),
    "koyfin_credit": ("koyfin", "WTM-Credit-Confirmation"),
    "koyfin_china": ("koyfin", "WTM-China-Policy"),
    "koyfin_daily_spot": ("koyfin", "Whinfell-Daily-TimeSeries"),
    "barchart_futures_intraday": ("barchart", "WTM-Futures-Intraday"),
    "barchart_futures_daily": ("barchart", "WTM-Futures-Daily"),
    "barchart_core_batch": ("barchart", "WTM-Barchart-Core"),
    "barchart_btc_basis": ("barchart", "WTM-BTC-Basis"),
    "koyfin_crypto_price": ("koyfin", "WTM-Crypto-Price"),
    "koyfin_crypto_correl_btc": ("koyfin", "WTM-Crypto-Correl"),
    "koyfin_crypto_correl_eth": ("koyfin", "WTM-Crypto-Correl-ETH"),
    "koyfin_crypto_correl_xrp": ("koyfin", "WTM-Crypto-Correl-XRP"),
    "koyfin_crypto_correl_sol": ("koyfin", "WTM-Crypto-Correl-SOL"),
    "koyfin_crypto_corr_series": ("koyfin", "WTM-Crypto-Snapshot"),
    "koyfin_flows_global": ("koyfin", "WTM-Flows-Global"),
    "koyfin_flows_gov": ("koyfin", "WTM-GOV-USPRC"),
}

DATE_MDY_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
DATE_YMD_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
BROWSER_DUPE_RE = re.compile(r" \(\d+\)(?=\.csv$)", re.I)


def strip_browser_duplicate_suffix(filename: str) -> str:
    """Normalize browser re-download names: 'file (1).csv' → 'file.csv'."""
    return BROWSER_DUPE_RE.sub("", filename)


@dataclass
class NormalizeResult:
    renamed: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


@dataclass
class WatchResult:
    ready: bool = False
    present: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    normalize: NormalizeResult = field(default_factory=NormalizeResult)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parent / MANIFEST_NAME


def default_drop_dir() -> Path:
    return Path.home() / "Downloads" / "whinfell_drop"


def expand_env(value: str) -> str:
    """Replace ${VAR} with os.environ; leave unset placeholders as fallback_url consumers handle."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return os.environ.get(key, match.group(0))

    return ENV_VAR_RE.sub(repl, value)


def default_desk_urls_path() -> Path:
    return Path(__file__).resolve().parent / DESK_URLS_NAME


def load_desk_urls(path: Path | None = None) -> dict[str, Any]:
    desk_path = path or default_desk_urls_path()
    if not desk_path.exists():
        return {}
    with desk_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["_desk_urls_path"] = str(desk_path)
    return data


def _resolve_url_field(raw: str, wired: str | None, fallback: str) -> str:
    expanded = expand_env(raw)
    if expanded and not expanded.startswith("${"):
        return expanded
    if wired:
        wired_exp = expand_env(wired)
        if wired_exp and not wired_exp.startswith("${"):
            return wired_exp
    return fallback


def merge_desk_urls_into_manifest(manifest: dict[str, Any], desk: dict[str, Any]) -> dict[str, Any]:
    """Wire saved-view URLs from desk_urls.yaml into batch_exports."""
    if not desk:
        return manifest
    for entry in manifest.get("batch_exports", []):
        batch_id = entry.get("id", "")
        keys = _BATCH_DESK_KEYS.get(batch_id)
        if not keys:
            continue
        section, view_name = keys
        spec = (desk.get(section) or {}).get(view_name) or {}
        if not isinstance(spec, dict):
            continue
        resolved = _resolve_url_field(
            str(spec.get("url", entry.get("url", ""))),
            spec.get("wired_url"),
            str(entry.get("fallback_url", "")),
        )
        entry["url"] = resolved
        entry["desk_navigate"] = spec.get("navigate", "")
        entry["desk_export_menu"] = spec.get("export_menu", "")
        entry["desk_assist_urls"] = spec.get("assist_urls", [])
        entry["desk_replace_me"] = bool(spec.get("replace_me"))
    manifest["_desk_urls_path"] = desk.get("_desk_urls_path", "")
    return manifest


def enrich_manifest_from_dictionary(manifest: dict[str, Any]) -> dict[str, Any]:
    from whinfell_pipeline.data_dictionary import raw_patterns_for_dataset

    for entry in manifest.get("batch_exports", []):
        ds = entry.get("dictionary_dataset") or entry.get("dataset")
        if not ds:
            continue
        patterns = raw_patterns_for_dataset(str(ds))
        if patterns:
            entry["raw_filename_patterns"] = patterns
    return manifest


def load_manifest(path: Path | None = None, desk_urls_path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or default_manifest_path()
    with manifest_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data["_manifest_path"] = str(manifest_path)
    desk = load_desk_urls(desk_urls_path)
    merged = merge_desk_urls_into_manifest(data, desk)
    return enrich_manifest_from_dictionary(merged)


def resolve_drop_dir(manifest: dict[str, Any], override: Path | None = None) -> Path:
    if override:
        return override.expanduser()
    raw = manifest.get("drop_dir", "~/Downloads/whinfell_drop")
    return Path(expand_env(str(raw))).expanduser()


def ensure_drop_dir(drop: Path) -> Path:
    drop.mkdir(parents=True, exist_ok=True)
    return drop


def file_yyyymmdd(path: Path) -> str:
    base = path.stem
    m = DATE_MDY_RE.search(base)
    if m:
        return f"{m.group(3)}{m.group(1)}{m.group(2)}"
    m = DATE_YMD_RE.search(base)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%Y%m%d")


def file_hhmm(path: Path) -> str:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime("%H%M")


def is_canonical_name(name: str) -> bool:
    from whinfell_pipeline.data_dictionary import canonical_filename_patterns

    return any(fnmatch.fnmatch(name, pat) for pat in canonical_filename_patterns())


def should_skip(name: str, manifest: dict[str, Any]) -> bool:
    for pat in manifest.get("skip_patterns", []):
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def infer_canonical_name(filename: str, path: Path) -> str | None:
    """Map raw vendor filename → staged contract name (Master DD normalize_rules)."""
    from whinfell_pipeline.data_dictionary import normalize_glob_rules

    clean_name = strip_browser_duplicate_suffix(filename)
    ymd = file_yyyymmdd(path)
    hhmm = file_hhmm(path)
    lower = clean_name.lower()

    for rule in normalize_glob_rules():
        pattern = str(rule.get("detect_glob", "")).lower()
        template = str(rule.get("canonical_template", ""))
        if not pattern or not template:
            continue
        if fnmatch.fnmatch(lower, pattern):
            return (
                template.replace("{YYYYMMDD}", ymd)
                .replace("{HHMM}", hhmm)
            )
    return None


def normalize_drop_dir(
    drop: Path,
    manifest: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> NormalizeResult:
    """Rename raw vendor exports to canonical staged filenames."""
    manifest = manifest or load_manifest()
    result = NormalizeResult()
    if not drop.is_dir():
        result.warnings.append(f"drop dir not found: {drop}")
        return result

    for path in sorted(drop.glob("*.csv")):
        name = path.name
        if should_skip(name, manifest):
            result.skipped += 1
            result.actions.append(f"skip  noise: {name}")
            continue
        if is_canonical_name(name):
            result.skipped += 1
            result.actions.append(f"skip  canonical: {name}")
            continue

        dest_name = infer_canonical_name(name, path)
        if not dest_name:
            result.skipped += 1
            result.warnings.append(f"no rule for: {name}")
            result.actions.append(f"warn  no rule: {name}")
            continue

        dest = drop / dest_name
        if dest.exists() and dest.resolve() != path.resolve():
            result.skipped += 1
            result.actions.append(f"skip  exists: {dest_name}")
            continue
        if dest.resolve() == path.resolve():
            result.skipped += 1
            continue

        if dry_run:
            result.actions.append(f"dry   {name} -> {dest_name}")
            result.renamed += 1
            continue

        path.rename(dest)
        result.renamed += 1
        result.actions.append(f"ok    {name} -> {dest_name}")

    return result


def resolve_batch_url(entry: dict[str, Any]) -> str:
    return _resolve_url_field(
        str(entry.get("url", "")),
        None,
        str(entry.get("fallback_url", "https://app.koyfin.com/")),
    )


def build_collection_plan(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Machine-readable plan for Comet / Perplexity."""
    manifest = manifest or load_manifest()
    batches = manifest.get("batch_exports", [])
    steps: list[dict[str, Any]] = []
    total_clicks = 0

    optional_steps: list[dict[str, Any]] = []

    def _step_from_entry(entry: dict[str, Any], step_no: int) -> dict[str, Any]:
        clicks = int(entry.get("clicks", 2))
        return {
            "step": step_no,
            "id": entry["id"],
            "source": entry.get("source"),
            "dataset": entry.get("dataset"),
            "saved_view": entry.get("saved_view"),
            "url": resolve_batch_url(entry),
            "clicks": clicks,
            "instructions": entry.get("steps", []),
            "navigate": entry.get("desk_navigate", ""),
            "export_menu": entry.get("desk_export_menu", ""),
            "assist_urls": entry.get("desk_assist_urls", []),
            "needs_clark_url": entry.get("desk_replace_me", False),
            "drop_dir": str(resolve_drop_dir(manifest)),
            "canonical_name": entry.get("canonical_name"),
            "optional": bool(entry.get("optional")),
            "notes": entry.get("notes", ""),
        }

    for entry in sorted(batches, key=lambda e: e.get("priority", 99)):
        if entry.get("optional"):
            optional_steps.append(_step_from_entry(entry, len(optional_steps) + 1))
            continue
        clicks = int(entry.get("clicks", 2))
        total_clicks += clicks
        steps.append(_step_from_entry(entry, len(steps) + 1))

    return {
        "version": manifest.get("version", "1.0.0"),
        "mode": "batch",
        "strategy": "Export only — required bulk screens + optional crypto enrichments.",
        "total_exports_required": len(steps),
        "total_exports_optional": len(optional_steps),
        "total_clicks_required": total_clicks,
        "drop_dir": str(resolve_drop_dir(manifest)),
        "required_batch_ids": manifest.get("required_batch_ids", []),
        "optional_batch_ids": [s["id"] for s in optional_steps],
        "agent_rules": manifest.get("agent_rules", []),
        "authority_files": [
            "whinfell_pipeline/collection_manifest.yaml",
            "whinfell_pipeline/desk_urls.yaml",
            "whinfell_pipeline/data_dictionary.yaml",
        ],
        "steps": steps,
        "optional_steps": optional_steps,
        "after_exports": [
            f"scripts/normalize_whinfell_drop.sh {resolve_drop_dir(manifest)}",
            f"python3 {repo_root() / 'run_batch_collect.py'} run --window today",
            "Transmission Control → Import Latest Hydration Bundle",
        ],
    }


def build_per_ticker_plan(
    manifest: dict[str, Any] | None = None,
    *,
    tickers: list[str] | None = None,
    export_type: str = "historical",
) -> dict[str, Any]:
    """Analytics-only plan — use sparingly."""
    manifest = manifest or load_manifest()
    registry = manifest.get("tickers", {})
    selected = tickers or manifest.get("ticker_queue", [])
    steps: list[dict[str, Any]] = []

    for key in selected:
        clean = key.replace("*", "").replace("1", "").upper()
        if clean not in registry:
            continue
        spec = registry[clean]
        url = spec.get("urls", {}).get(export_type) or spec.get("urls", {}).get("quote", "")
        steps.append({
            "ticker": spec.get("shortcut", key),
            "asset": clean,
            "contract": spec.get("contract_nearby"),
            "url": url,
            "export_type": export_type,
        })

    return {
        "version": manifest.get("version", "1.0.0"),
        "mode": "per_ticker_analytics",
        "warning": "Slow path — use batch_exports for daily Whinfell unless Clark requests full archive.",
        "export_type": export_type,
        "drop_dir": str(resolve_drop_dir(manifest)),
        "steps": steps,
    }


def open_batch_urls(
    manifest: dict[str, Any] | None = None,
    *,
    include_optional: bool = False,
    delay_sec: float = 1.5,
) -> list[str]:
    """Open saved-view URLs in the default browser (macOS open)."""
    manifest = manifest or load_manifest()
    opened: list[str] = []
    for entry in sorted(manifest.get("batch_exports", []), key=lambda e: e.get("priority", 99)):
        if entry.get("optional") and not include_optional:
            continue
        url = resolve_batch_url(entry)
        if not url:
            continue
        subprocess.run(["open", url], check=False)
        opened.append(url)
        time.sleep(delay_sec)
    return opened


def _pattern_matches_filename(pattern: str, filename: str) -> bool:
    lower = filename.lower()
    glob_pat = pattern.replace("{YYYYMMDD}", "*").replace("{HHMM}", "*").lower()
    if fnmatch.fnmatch(lower, glob_pat):
        return True
    if is_canonical_name(filename):
        prefix = glob_pat.split("_")[0]
        if prefix and lower.startswith(prefix + "_"):
            return True
    return fnmatch.fnmatch(lower, pattern.lower())


def count_matching_files(drop: Path, patterns: list[str]) -> list[str]:
    found: set[str] = set()
    for path in drop.glob("*.csv"):
        if any(_pattern_matches_filename(pat, path.name) for pat in patterns):
            found.add(path.name)
    return sorted(found)


def check_batch_ready(
    drop: Path,
    manifest: dict[str, Any] | None = None,
) -> WatchResult:
    """Return whether required batch exports are present (canonical or raw)."""
    manifest = manifest or load_manifest()
    result = WatchResult()
    required = manifest.get("required_batch_ids", [])
    id_to_entry = {e["id"]: e for e in manifest.get("batch_exports", [])}

    for req_id in required:
        entry = id_to_entry.get(req_id)
        if not entry:
            result.missing.append(req_id)
            continue
        patterns = [entry.get("canonical_name", "").replace("{YYYYMMDD}", "*").replace("{HHMM}", "*")]
        patterns.extend(entry.get("raw_filename_patterns", []))
        patterns = [p for p in patterns if p]
        matches = count_matching_files(drop, patterns)
        if matches:
            result.present.extend(matches)
        else:
            result.missing.append(req_id)

    result.present = sorted(set(result.present))
    result.ready = len(result.missing) == 0
    return result


def watch_drop_dir(
    drop: Path,
    manifest: dict[str, Any] | None = None,
    *,
    timeout_sec: int = 600,
    poll_sec: float = 5.0,
    auto_run: bool = False,
) -> WatchResult:
    """Poll drop dir until required batch files appear, then normalize."""
    manifest = manifest or load_manifest()
    ensure_drop_dir(drop)
    deadline = time.time() + timeout_sec
    last_norm = NormalizeResult()

    while time.time() < deadline:
        last_norm = normalize_drop_dir(drop, manifest)
        status = check_batch_ready(drop, manifest)
        status.normalize = last_norm
        if status.ready:
            if auto_run:
                run_pipeline(drop, manifest)
            return status
        time.sleep(poll_sec)

    status = check_batch_ready(drop, manifest)
    status.normalize = last_norm
    return status


def fetch_barchart_historical(
    symbol: str,
    *,
    api_key: str,
    start_date: str = "20250101",
    end_date: str | None = None,
    out_dir: Path | None = None,
) -> Path:
    """
    Parallel-friendly Barchart OnDemand fetch when BARCHART_API_KEY is set.

    Uses marketdata.websol.barchart.com (paid API — not the free browser export).
    """
    end = end_date or datetime.now().strftime("%Y%m%d")
    params = urllib.parse.urlencode({
        "apikey": api_key,
        "symbol": symbol,
        "startDate": start_date,
        "endDate": end,
        "type": "daily",
    })
    url = f"https://marketdata.websol.barchart.com/getHistory.csv?{params}"
    out_dir = out_dir or default_drop_dir()
    ensure_drop_dir(out_dir)
    dest = out_dir / f"{symbol.lower()}_daily-nearby_historical-data-{datetime.now():%m-%d-%Y}.csv"

    req = urllib.request.Request(url, headers={"User-Agent": "WhinfellBatchCollect/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Barchart API {symbol}: HTTP {exc.code}") from exc

    if not body or b"Symbol" not in body[:500] and b"symbol" not in body[:500].lower():
        raise RuntimeError(f"Barchart API {symbol}: unexpected response (check api key / symbol)")

    dest.write_bytes(body)
    return dest


def fetch_all_tickers_api(
    manifest: dict[str, Any] | None = None,
    *,
    api_key: str | None = None,
    tickers: list[str] | None = None,
    out_dir: Path | None = None,
) -> list[str]:
    """Fetch historical CSV for all tickers via API (fast, no browser)."""
    manifest = manifest or load_manifest()
    key = api_key or os.environ.get("BARCHART_API_KEY", "")
    if not key:
        raise ValueError("BARCHART_API_KEY not set — browser batch_exports or set API key")

    registry = manifest.get("tickers", {})
    selected = tickers or [t.replace("*", "").replace("1", "") for t in manifest.get("ticker_queue", [])]
    out_dir = out_dir or resolve_drop_dir(manifest)
    ensure_drop_dir(out_dir)
    saved: list[str] = []

    for key_sym in selected:
        spec = registry.get(key_sym.upper())
        if not spec:
            continue
        symbol = spec.get("contract_nearby", "")
        if not symbol:
            continue
        try:
            path = fetch_barchart_historical(symbol, api_key=key, out_dir=out_dir)
            saved.append(str(path))
        except RuntimeError as exc:
            print(f"warn  {exc}", file=sys.stderr)

    normalize_drop_dir(out_dir, manifest)
    return saved


def run_pipeline(
    drop: Path,
    manifest: dict[str, Any] | None = None,
    *,
    operator: str = "desk",
    window: str = "today",
    skip_daily: bool = False,
) -> int:
    """Normalize → stage → collect → hydrate."""
    manifest = manifest or load_manifest()
    root = repo_root()
    normalize_drop_dir(drop, manifest)

    base_cmd = [
        sys.executable,
        str(root / "run_csv_download.py"),
    ]
    common_args = [
        "--downloads",
        str(drop),
        "--operator",
        operator,
        "--window",
        window,
    ]
    if skip_daily:
        proc = subprocess.run([*base_cmd, "stage", *common_args], cwd=root)
        return proc.returncode

    daily_cmd = [
        *base_cmd,
        "daily",
        *common_args,
        "--hydrate-output",
        str(root / "data" / "hydration" / "latest.json"),
    ]
    proc = subprocess.run(daily_cmd, cwd=root)
    return proc.returncode


def cmd_plan(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    if args.mode == "per_ticker":
        plan = build_per_ticker_plan(manifest, tickers=args.tickers, export_type=args.export_type)
    else:
        plan = build_collection_plan(manifest)
    text = json.dumps(plan, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"plan_written={args.output}")
    else:
        print(text)
    return 0


def cmd_open(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    urls = open_batch_urls(manifest, include_optional=args.include_optional, delay_sec=args.delay)
    print(f"urls_opened={len(urls)}")
    for u in urls:
        print(f"url={u}")
    print(f"drop_dir={resolve_drop_dir(manifest)}")
    print("next=Export each tab to whinfell_drop, then: python3 run_batch_collect.py run")
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    drop = resolve_drop_dir(manifest, Path(args.drop) if args.drop else None)
    result = normalize_drop_dir(drop, manifest, dry_run=args.dry_run)
    print(f"normalize_ok renamed={result.renamed} skipped={result.skipped}")
    for line in result.actions:
        print(line)
    for w in result.warnings:
        print(f"warn={w}", file=sys.stderr)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    drop = resolve_drop_dir(manifest, Path(args.drop) if args.drop else None)
    ensure_drop_dir(drop)
    normalize_drop_dir(drop, manifest)
    status = check_batch_ready(drop, manifest)
    print(f"drop_dir={drop}")
    print(f"ready={status.ready}")
    print(f"present={','.join(status.present) or '-'}")
    print(f"missing={','.join(status.missing) or '-'}")
    return 0 if status.ready else 1


def cmd_watch(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    drop = resolve_drop_dir(manifest, Path(args.drop) if args.drop else None)
    status = watch_drop_dir(
        drop,
        manifest,
        timeout_sec=args.timeout,
        poll_sec=args.poll,
        auto_run=args.auto_run,
    )
    print(f"ready={status.ready}")
    print(f"present={','.join(status.present) or '-'}")
    print(f"missing={','.join(status.missing) or '-'}")
    print(f"renamed={status.normalize.renamed}")
    return 0 if status.ready else 1


def cmd_fetch_api(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    drop = resolve_drop_dir(manifest, Path(args.drop) if args.drop else None)
    saved = fetch_all_tickers_api(manifest, tickers=args.tickers, out_dir=drop)
    print(f"fetch_api_ok count={len(saved)}")
    for p in saved:
        print(f"file={p}")
    return 0 if saved else 1


def cmd_barchart_only(args: argparse.Namespace) -> int:
    from whinfell_pipeline.barchart_hydration import default_output_dir, run_barchart_hydration

    out_dir = Path(args.output_dir) if args.output_dir else default_output_dir()
    file_only = not getattr(args, "use_api", False)
    result = run_barchart_hydration(
        api_key=args.api_key or None,
        output_dir=out_dir,
        start_date=args.start_date,
        verbose=True,
        file_only=file_only,
    )

    counts = result["counts"]
    m = result["manifest"]
    print("barchart_hydration_begin source=barchart_only")
    print(f"symbol_count_approved={counts['approved']}")
    print(f"fetch_policy={m.get('fetch_policy', 'file_only')}")
    print(f"api_key_present={m.get('api_key_present', False)}")
    print(f"approved={counts['approved']} core_ok={counts['core_ok']} "
          f"curve_ok={counts['curve_ok']} spread_ok={counts['spread_ok']}")
    print(f"failed={m['symbol_count_failed']} empty={m['symbol_count_empty']}")
    for name, path in result["paths"].items():
        print(f"output={name} path={path}")
    print("barchart_hydration_ok source=barchart_only")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest) if args.manifest else None)
    drop = resolve_drop_dir(manifest, Path(args.drop) if args.drop else None)
    ensure_drop_dir(drop)
    code = run_pipeline(
        drop,
        manifest,
        operator=args.operator,
        window=args.window,
        skip_daily=args.stage_only,
    )
    return code


def _add_drop_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", help="Path to collection_manifest.yaml")
    parser.add_argument("--drop", help="Drop folder (default: ~/Downloads/whinfell_drop)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Whinfell batch CSV collection — fast path for Comet / Perplexity",
    )
    _add_drop_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Emit JSON collection plan for agents")
    _add_drop_args(p_plan)
    p_plan.add_argument("--mode", choices=("batch", "per_ticker"), default="batch")
    p_plan.add_argument("--export-type", default="historical")
    p_plan.add_argument("--tickers", nargs="*", help="Subset for per_ticker mode (e.g. BT ER)")
    p_plan.add_argument("-o", "--output", help="Write plan JSON to file")
    p_plan.set_defaults(func=cmd_plan)

    p_open = sub.add_parser("open", help="Open all batch saved-view URLs in browser (macOS)")
    _add_drop_args(p_open)
    p_open.add_argument("--include-optional", action="store_true")
    p_open.add_argument("--delay", type=float, default=1.5, help="Seconds between open calls")
    p_open.set_defaults(func=cmd_open)

    p_norm = sub.add_parser("normalize", help="Rename raw vendor files → canonical names")
    _add_drop_args(p_norm)
    p_norm.add_argument("--dry-run", action="store_true")
    p_norm.set_defaults(func=cmd_normalize)

    p_status = sub.add_parser("status", help="Check if required batch files are in drop dir")
    _add_drop_args(p_status)
    p_status.set_defaults(func=cmd_status)

    p_watch = sub.add_parser("watch", help="Poll drop dir until required files arrive")
    _add_drop_args(p_watch)
    p_watch.add_argument("--timeout", type=int, default=600)
    p_watch.add_argument("--poll", type=float, default=5.0)
    p_watch.add_argument("--auto-run", action="store_true", help="Run pipeline when ready")
    p_watch.set_defaults(func=cmd_watch)

    p_fetch = sub.add_parser("fetch-api", help="Barchart API historical fetch (needs BARCHART_API_KEY)")
    _add_drop_args(p_fetch)
    p_fetch.add_argument("--tickers", nargs="*", help="Asset roots: BT ER CL ...")
    p_fetch.set_defaults(func=cmd_fetch_api)

    p_run = sub.add_parser("run", help="normalize + stage + daily chain")
    _add_drop_args(p_run)
    p_run.add_argument("--operator", default="desk")
    p_run.add_argument("--window", default="today")
    p_run.add_argument("--stage-only", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_bc = sub.add_parser(
        "barchart-only",
        help="Barchart-only first-pass hydration (all approved symbols, no Koyfin)",
    )
    p_bc.add_argument("--output-dir", help="Output directory (default: data/barchart/v1)")
    p_bc.add_argument("--start-date", default="20250101", help="History start YYYYMMDD")
    p_bc.add_argument("--api-key", help="Barchart API key (default: BARCHART_API_KEY env)")
    p_bc.add_argument(
        "--use-api",
        action="store_true",
        help="Allow API fallback when local CSV supplement is missing (not desk default)",
    )
    p_bc.set_defaults(func=cmd_barchart_only)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())