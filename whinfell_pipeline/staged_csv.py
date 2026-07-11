"""Staged CSV folder layout, validation, and scan for Chunk 2.2c."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

STAGED_ROOT_NAME = "staged_raw"

SOURCE_BARCHART = "barchart"
SOURCE_KOYFIN = "koyfin"
SOURCE_CHINA = "china_policy"
SOURCE_CRYPTO = "crypto"

BARCHART_DATASETS = ("futures_intraday", "futures_daily", "options", "greeks")
KOYFIN_DATASETS = ("rates", "credit", "equities", "flows")
CRYPTO_DATASETS = (
    "crypto_snapshot",
    "btc_price_chart",
    "btc_correl_chart",
    "eth_correl_chart",
    "xrp_correl_chart",
    "sol_correl_chart",
    "crypto_corr_series",
)

FILENAME_RE = re.compile(
    r"^(?:"
    r"(?P<dataset>[a-z][a-z0-9_]*)_(?P<date>\d{8})_(?P<time>\d{4})"
    r"|"
    r"(?P<product>[a-z][a-z0-9_]*)_(?P<flavor>[a-z][a-z0-9_]*)_(?P<date2>\d{8})"
    r"|"
    r"WTM-Flows(?:-[A-Za-z0-9]+)?"
    r")\.csv$",
    re.IGNORECASE,
)

FLOWS_VENDOR_GLOB = "WTM-Flows*.csv"

GLOBAL_HEADERS = frozenset({
    "observation_id", "timestamp", "whinfell_score", "transmission_state",
    "regime_tag", "key_observation", "sq3_score", "sq3_band",
})
EXECUTION_HEADERS = frozenset({
    "observation_id", "timestamp", "near_month", "far_month", "basis_spread",
    "ref_low", "ref_mid", "ref_high",
})
CHINA_HEADERS = frozenset({
    "observation_id", "timestamp", "policy_strength", "state_impulse_score",
    "growth_impulse_score", "china_regime_tag", "dominant_theme",
})


@dataclass
class StagedFile:
    path: Path
    source: str
    dataset: str | None
    filename: str


@dataclass
class StagedValidation:
    ok: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class StagedIngestFileResult:
    path: str
    source: str
    dataset: str | None
    adapter_id: str = ""
    validation_status: str = ""
    archived_to: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class StagedIngestResult:
    files_found: int = 0
    files_processed: int = 0
    files_failed: int = 0
    global_written: int = 0
    china_written: int = 0
    execution_records: int = 0
    file_results: list[StagedIngestFileResult] = field(default_factory=list)


def default_staged_root(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / STAGED_ROOT_NAME


def staged_source_dir(root: Path, source: str) -> Path:
    return root / f"source={source}"


def staged_dataset_dir(root: Path, source: str, dataset: str) -> Path:
    return staged_source_dir(root, source) / f"dataset={dataset}"


def staged_archived_dir(container: Path) -> Path:
    return container / "archived"


def iter_staged_layout(root: Path) -> Iterable[tuple[str, str | None, Path]]:
    """Yield (source, dataset|None, directory holding pending CSV files)."""
    if not root.exists():
        return
    for source in (SOURCE_BARCHART, SOURCE_KOYFIN, SOURCE_CRYPTO, SOURCE_CHINA):
        src_dir = staged_source_dir(root, source)
        if not src_dir.is_dir():
            continue
        if source == SOURCE_CHINA:
            yield source, None, src_dir
            continue
        if source == SOURCE_CRYPTO:
            datasets = CRYPTO_DATASETS
        else:
            datasets = BARCHART_DATASETS if source == SOURCE_BARCHART else KOYFIN_DATASETS
        for ds in datasets:
            ds_dir = staged_dataset_dir(root, source, ds)
            if ds_dir.is_dir():
                yield source, ds, ds_dir


def init_staged_tree(root: Path | None = None) -> Path:
    """Create staged_raw/ tree with archived/ placeholders."""
    base = root or default_staged_root()
    layouts: list[tuple[str, str | None]] = [
        *((SOURCE_BARCHART, ds) for ds in BARCHART_DATASETS),
        *((SOURCE_KOYFIN, ds) for ds in KOYFIN_DATASETS),
        *((SOURCE_CRYPTO, ds) for ds in CRYPTO_DATASETS),
        (SOURCE_CHINA, None),
    ]
    for source, dataset in layouts:
        pending = staged_dataset_dir(base, source, dataset) if dataset else staged_source_dir(base, source)
        pending.mkdir(parents=True, exist_ok=True)
        archived = staged_archived_dir(pending)
        archived.mkdir(parents=True, exist_ok=True)
        (pending / ".gitkeep").touch(exist_ok=True)
        (archived / ".gitkeep").touch(exist_ok=True)
    readme = base / "README.md"
    if not readme.exists():
        readme.write_text(_STAGED_README, encoding="utf-8")
    return base


def validate_filename(name: str) -> StagedValidation:
    out = StagedValidation(ok=False)
    if not name.lower().endswith(".csv"):
        out.errors.append("not a .csv file")
        return out
    if name.startswith("."):
        out.errors.append("hidden file")
        return out
    if not FILENAME_RE.match(name):
        out.errors.append(
            "filename must match {dataset}_{YYYYMMDD}_{HHMM}.csv "
            "or {product}_{flavor}_{YYYYMMDD}.csv"
        )
        return out
    out.ok = True
    return out


def _required_headers(source: str, dataset: str | None) -> frozenset[str]:
    if source == SOURCE_CHINA:
        return CHINA_HEADERS
    if source == SOURCE_BARCHART:
        return EXECUTION_HEADERS
    if source == SOURCE_CRYPTO:
        return frozenset()
    return GLOBAL_HEADERS


def _header_check(source: str, dataset: str | None, headers: list[str]) -> StagedValidation:
    out = StagedValidation(ok=True)
    norm = {h.strip().lower() for h in headers if h and h.strip()}
    if not norm:
        out.ok = False
        out.errors.append("empty header row")
        return out
    required = _required_headers(source, dataset)
    missing_core: list[str] = []
    if source == SOURCE_CHINA:
        for req in ("observation_id", "timestamp", "policy_strength"):
            if req not in norm:
                missing_core.append(req)
    elif source == SOURCE_BARCHART:
        vendor_native = (
            ({"symbol", "time"} <= norm or "time" in norm)
            and "latest" in norm
        ) or (
            {"leg1", "leg2", "type", "latest"} <= norm
        ) or (
            "strike" in "".join(norm) and "latest" in norm
        )
        if vendor_native:
            return out
        if "timestamp" not in norm:
            missing_core.append("timestamp")
        if not ({"near_month", "basis_spread"} & norm):
            missing_core.append("near_month or basis_spread")
    elif source == SOURCE_CRYPTO:
        return out
    elif dataset == "flows":
        snapshot_fmt = "ticker" in norm and any(
            "fund flows/periodic (d)" in h for h in norm
        )
        wide_fmt = "date" in norm and any(
            "flow" in h and ("(d)" in h or "periodic" in h)
            for h in norm
        )
        if not snapshot_fmt and not wide_fmt:
            missing_core.append(
                "date + flow columns (wide timeseries) or Ticker + Fund Flows/Periodic (D) (snapshot)"
            )
    else:
        if "timestamp" not in norm:
            missing_core.append("timestamp")
        if not ({"whinfell_score", "key_observation", "regime_tag"} & norm):
            missing_core.append("whinfell_score, regime_tag, or key_observation")
    if missing_core:
        out.ok = False
        out.errors.append(f"missing required headers: {', '.join(missing_core)}")
    optional_missing = required - norm
    if optional_missing:
        out.warnings.append(f"optional headers absent: {', '.join(sorted(optional_missing))}")
    return out


def read_csv_payload(path: Path) -> tuple[dict[str, Any], list[str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("missing header row")
        headers = list(reader.fieldnames)
        rows = list(reader)
    if not rows:
        raise ValueError("no data rows")
    row = rows[-1]
    payload: dict[str, Any] = {}
    for key, val in row.items():
        if key is None:
            continue
        k = key.strip().lower()
        v = (val or "").strip()
        if not k:
            continue
        if k in ("whinfell_score", "sq3_score", "policy_strength", "state_impulse_score", "growth_impulse_score"):
            try:
                payload[k] = int(v) if v else None
            except ValueError:
                payload[k] = v
        else:
            payload[k] = v
    return payload, headers


def csv_to_adapter_payload(staged: StagedFile, row_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row_payload)
    payload["source"] = staged.source
    if staged.dataset:
        payload["_dataset"] = staged.dataset
        payload["_staged_file"] = staged.filename
    if staged.source == SOURCE_CHINA:
        payload["_track_hint"] = "china_policy"
        if payload.get("china_regime_tag") and not payload.get("dominant_theme"):
            payload["dominant_theme"] = payload["china_regime_tag"]
    elif staged.source == SOURCE_KOYFIN:
        payload["_track_hint"] = "global"
    return payload


def scan_staged_root(root: Path) -> list[StagedFile]:
    init_staged_tree(root)
    found: list[StagedFile] = []
    for source, dataset, pending_dir in iter_staged_layout(root):
        archived = staged_archived_dir(pending_dir)
        for path in sorted(pending_dir.glob("*.csv")):
            if archived in path.parents:
                continue
            found.append(StagedFile(
                path=path,
                source=source,
                dataset=dataset,
                filename=path.name,
            ))
    return found


def validate_crypto_staged_file(staged: StagedFile) -> StagedValidation:
    from whinfell_pipeline.crypto_sleeve import ingest_crypto_file

    fn_val = validate_filename(staged.filename)
    if not fn_val.ok:
        return fn_val
    _, ingest_res = ingest_crypto_file(staged.path, dataset=staged.dataset)
    if not ingest_res.ok:
        return StagedValidation(ok=False, errors=list(ingest_res.errors), warnings=list(ingest_res.warnings))
    return StagedValidation(ok=True, warnings=fn_val.warnings + ingest_res.warnings)


def validate_staged_file(staged: StagedFile) -> StagedValidation:
    if staged.source == SOURCE_CRYPTO:
        return validate_crypto_staged_file(staged)
    fn_val = validate_filename(staged.filename)
    if not fn_val.ok:
        return fn_val
    try:
        _, headers = read_csv_payload(staged.path)
    except Exception as exc:
        return StagedValidation(ok=False, errors=[str(exc)])
    hdr_val = _header_check(staged.source, staged.dataset, headers)
    if not hdr_val.ok:
        return hdr_val
    return StagedValidation(ok=True, warnings=fn_val.warnings + hdr_val.warnings)


def archive_staged_file(staged: StagedFile, *, when: datetime | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    dest_dir = staged_archived_dir(staged.path.parent)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stamp}__{staged.filename}"
    shutil.move(str(staged.path), str(dest))
    return dest


def ingest_staged_root(
    root: Path,
    *,
    global_output: Path | None = None,
    china_output: Path | None = None,
    append: bool = True,
    write_export: Path | None = None,
    archive: bool = True,
    dry_run: bool = False,
) -> StagedIngestResult:
    from whinfell_pipeline.adapters.registry import parse_with_best_adapter
    from whinfell_pipeline.ingest import ingest_payload

    result = StagedIngestResult()
    files = scan_staged_root(root)
    result.files_found = len(files)

    for staged in files:
        fr = StagedIngestFileResult(
            path=str(staged.path),
            source=staged.source,
            dataset=staged.dataset,
        )
        if staged.source == SOURCE_CRYPTO:
            fr.validation_status = "crypto_deferred"
            fr.adapter_id = "crypto_sleeve"
            result.files_processed += 1
            result.file_results.append(fr)
            continue
        if staged.source == SOURCE_KOYFIN and staged.dataset == "flows":
            val = validate_staged_file(staged)
            if not val.ok:
                fr.errors = list(val.errors)
                result.files_failed += 1
                result.file_results.append(fr)
                continue
            fr.warnings = list(val.warnings)
            if dry_run:
                fr.validation_status = "dry_run"
                fr.adapter_id = "flows_parser"
                result.files_processed += 1
                result.file_results.append(fr)
                continue
            try:
                from datetime import datetime, timezone

                from whinfell_pipeline.flows_parser import (
                    default_flows_sidecar_path,
                    parse_and_write,
                    try_parse_flows_csv,
                    write_flows_sidecar,
                )

                repo_root = Path(__file__).resolve().parents[1]
                out_path = default_flows_sidecar_path(repo_root)
                payload = try_parse_flows_csv(staged.path)
                adapter_id = "flows_parser"
                if payload is None:
                    from whinfell_pipeline.flows_fallback import (
                        merge_fallback_into_sidecar,
                        parse_credit_cross_section_flows,
                    )
                    from whinfell_pipeline.funds_flows import load_flows_sidecar

                    credit_rows = parse_credit_cross_section_flows(staged.path)
                    if not credit_rows:
                        raise ValueError("unsupported flows format: invalid")
                    as_of = datetime.fromtimestamp(
                        staged.path.stat().st_mtime, tz=timezone.utc
                    ).date().isoformat()
                    payload = merge_fallback_into_sidecar(
                        load_flows_sidecar(repo_root),
                        credit_rows,
                        as_of=as_of,
                        source_file=staged.filename,
                    )
                    write_flows_sidecar(payload, out_path)
                    adapter_id = "flows_fallback"
                    fr.warnings.append("flows_snapshot_1d_fallback")
                else:
                    write_flows_sidecar(payload, out_path)
                fr.validation_status = "parsed"
                fr.adapter_id = adapter_id
                fr.warnings.append(f"flows_sidecar tickers={len(payload.get('tickers') or {})}")
                result.files_processed += 1
                if archive:
                    archived = archive_staged_file(staged)
                    fr.archived_to = str(archived)
            except Exception as exc:
                fr.errors.append(str(exc))
                result.files_failed += 1
            result.file_results.append(fr)
            continue
        val = validate_staged_file(staged)
        if not val.ok:
            fr.errors = list(val.errors)
            result.files_failed += 1
            result.file_results.append(fr)
            continue
        fr.warnings = list(val.warnings)
        try:
            row_payload, _ = read_csv_payload(staged.path)
            payload = csv_to_adapter_payload(staged, row_payload)
        except Exception as exc:
            fr.errors.append(str(exc))
            result.files_failed += 1
            result.file_results.append(fr)
            continue

        if dry_run:
            fr.validation_status = "dry_run"
            fr.adapter_id = "dry_run"
            result.files_processed += 1
            result.file_results.append(fr)
            continue

        adapter, parsed = parse_with_best_adapter(payload)
        if adapter is None or not parsed.ok:
            fr.errors.append("no adapter matched staged CSV payload")
            if parsed.warnings:
                fr.warnings.extend(parsed.warnings)
            result.files_failed += 1
            result.file_results.append(fr)
            continue

        ingest_res = ingest_payload(
            payload,
            global_output=global_output,
            china_output=china_output,
            append=append,
            write_export=write_export,
        )
        fr.adapter_id = ingest_res.adapter_id or adapter.adapter_id
        fr.validation_status = ingest_res.validation_status.value
        fr.warnings.extend(ingest_res.warnings)
        if ingest_res.validation_status.value == "failed":
            fr.errors.append("ingest failed")
            result.files_failed += 1
        else:
            result.files_processed += 1
            result.global_written += ingest_res.global_written
            result.china_written += ingest_res.china_written
            result.execution_records += ingest_res.execution_records
            if archive:
                archived = archive_staged_file(staged)
                fr.archived_to = str(archived)
        result.file_results.append(fr)

    return result


_STAGED_README = """# staged_raw — Operator CSV staging (Chunk 2.2c)

Drop collector CSV exports here before pipeline ingest. Processed files move to `archived/` under each dataset folder.

## Layout

```
staged_raw/
├── source=barchart/
│   ├── dataset=futures_intraday/
│   ├── dataset=futures_daily/
│   ├── dataset=options/
│   └── dataset=greeks/
├── source=koyfin/
│   ├── dataset=rates/
│   ├── dataset=credit/
│   └── dataset=equities/
├── source=crypto/
│   ├── dataset=crypto_snapshot/
│   ├── dataset=btc_price_chart/
│   ├── dataset=btc_correl_chart/
│   ├── dataset=eth_correl_chart/
│   ├── dataset=xrp_correl_chart/
│   ├── dataset=sol_correl_chart/
│   └── dataset=crypto_corr_series/
└── source=china_policy/
```

## Naming

- `{dataset}_{YYYYMMDD}_{HHMM}.csv`
- `{product}_{flavor}_{YYYYMMDD}.csv`

## Daily chain

1. Export from Transmission Control or Comet collector
2. Save CSV into the matching `source=` / `dataset=` folder
3. `python3 -m whinfell_pipeline.ingest --staged`
4. `python3 -m whinfell_pipeline.hydrate -o /tmp/hydration.json`
5. Import hydration bundle in Transmission Control

Initialize tree: `python3 -m whinfell_pipeline.staged_csv init`
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Staged CSV utilities (Chunk 2.2c)")
    parser.add_argument("command", nargs="?", default="init", choices=("init", "scan", "validate"))
    parser.add_argument("--root", default=None, help="staged_raw root path")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else default_staged_root()
    if args.command == "init":
        path = init_staged_tree(root)
        print(f"staged_tree_ok root={path}")
        return 0
    if args.command == "scan":
        files = scan_staged_root(root)
        for f in files:
            print(f"{f.source}\t{f.dataset or '-'}\t{f.filename}")
        print(f"files_found={len(files)}")
        return 0
    files = scan_staged_root(root)
    failed = 0
    for f in files:
        val = validate_staged_file(f)
        status = "ok" if val.ok else "fail"
        print(f"{status}\t{f.path}")
        for e in val.errors:
            print(f"  error: {e}")
        if not val.ok:
            failed += 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())