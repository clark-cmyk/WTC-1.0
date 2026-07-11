"""Comet CSV download → stage → collect → hydrate orchestration."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from whinfell_pipeline.staged_csv import (
    BARCHART_DATASETS,
    CRYPTO_DATASETS,
    FILENAME_RE,
    KOYFIN_DATASETS,
    SOURCE_BARCHART,
    SOURCE_CHINA,
    SOURCE_CRYPTO,
    SOURCE_KOYFIN,
    StagedFile,
    default_staged_root,
    init_staged_tree,
    ingest_staged_root,
    scan_staged_root,
    staged_dataset_dir,
    staged_source_dir,
    validate_staged_file,
)
from whinfell_pipeline.version import COMET_COLLECTOR_ID, COMET_COLLECTOR_VERSION, PIPELINE_VERSION

MANIFEST_VERSION = "1.0.0"
RUNBOOK_VERSION = "1.0.0"


@dataclass
class StageFileResult:
    source_path: str
    staged_path: str = ""
    meta_path: str = ""
    source: str = ""
    dataset: str | None = None
    status: str = "staged"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StageRunResult:
    files_scanned: int = 0
    files_staged: int = 0
    files_quarantined: int = 0
    files_skipped: int = 0
    manifest_path: str = ""
    file_results: list[StageFileResult] = field(default_factory=list)


@dataclass
class DailyRunResult:
    stage: StageRunResult = field(default_factory=StageRunResult)
    collect_exit: int = 0
    collect_stdout: str = ""
    hydrate_exit: int = 0
    hydrate_output: str = ""
    barchart_exit: int = 0
    barchart_stdout: str = ""
    manifest_path: str = ""
    errors: list[str] = field(default_factory=list)


def default_downloads_dir() -> Path:
    return Path.home() / "Downloads"


def manifests_dir(root: Path) -> Path:
    return root / "manifests"


def quarantine_dir(root: Path, when: datetime | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    return root / "quarantine" / when.strftime("%Y%m%d")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_window(window: str | None) -> timedelta:
    if not window:
        return timedelta(hours=24)
    w = window.strip().lower()
    if w in ("today", "day"):
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return now - start
    m = re.fullmatch(r"(\d+)([hdm])", w)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "h":
            return timedelta(hours=n)
        if unit == "d":
            return timedelta(days=n)
        return timedelta(minutes=n)
    raise ValueError(f"unrecognized --window value: {window!r} (use today, 24h, 6h, 30m)")


def file_within_window(path: Path, window: timedelta) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - window
    return mtime >= cutoff


def infer_staged_destination(filename: str) -> tuple[str, str | None]:
    """Map a CSV filename to (source, dataset) using the staged_raw contract."""
    match = FILENAME_RE.match(filename)
    if not match:
        raise ValueError(
            f"filename must match {{dataset}}_{{YYYYMMDD}}_{{HHMM}}.csv "
            f"or {{product}}_{{flavor}}_{{YYYYMMDD}}.csv: {filename}"
        )
    dataset = match.group("dataset")
    if dataset:
        ds = dataset.lower()
        if ds in CRYPTO_DATASETS:
            return SOURCE_CRYPTO, ds
        if ds in KOYFIN_DATASETS:
            return SOURCE_KOYFIN, ds
        if ds in BARCHART_DATASETS:
            return SOURCE_BARCHART, ds
        if ds in ("china_policy", "china"):
            return SOURCE_CHINA, None
        raise ValueError(f"unknown dataset token in filename: {ds}")
    product = (match.group("product") or "").lower()
    flavor = (match.group("flavor") or "").lower()
    if product in ("china", "china_policy"):
        return SOURCE_CHINA, None
    combined = f"{product}_{flavor}" if flavor else product
    if combined in CRYPTO_DATASETS:
        return SOURCE_CRYPTO, combined
    if product == "crypto":
        if flavor in CRYPTO_DATASETS:
            return SOURCE_CRYPTO, flavor
        raise ValueError(f"unknown crypto flavor in filename: {flavor}")
    return SOURCE_BARCHART, "futures_intraday"


def staged_destination_dir(root: Path, source: str, dataset: str | None) -> Path:
    if source == SOURCE_CHINA:
        return staged_source_dir(root, source)
    if dataset is None:
        raise ValueError(f"dataset required for source={source}")
    return staged_dataset_dir(root, source, dataset)


def _maybe_ingest_crypto_wide_backup(src: Path, dataset: str | None) -> list[str]:
    """Whinfell-Daily-TimeSeries wide export is backup chart history for crypto."""
    if dataset != "rates":
        return []
    from whinfell_pipeline.crypto_sleeve import (
        _read_csv,
        detect_crypto_source_type,
        extract_wide_timeseries_crypto,
        load_crypto_sidecar,
        merge_crypto_payload,
        write_crypto_sidecar,
    )

    try:
        headers, rows = _read_csv(src)
    except Exception:
        return []
    if detect_crypto_source_type(headers, src.name, rows=rows) != "wide_timeseries_backup":
        return []
    try:
        patch = extract_wide_timeseries_crypto(headers, rows, source_file=src.name)
        patch["source_type"] = "wide_timeseries_backup"
    except ValueError as exc:
        return [f"crypto wide backup skipped: {exc}"]
    payload = merge_crypto_payload(load_crypto_sidecar(), patch)
    write_crypto_sidecar(payload)
    charts = len(patch.get("charts") or {})
    return [f"crypto wide backup ingested from {src.name} ({charts} chart series)"]


def _maybe_ingest_crypto_snapshot_from_credit(src: Path, dataset: str | None) -> list[str]:
    """WhinPump / credit snapshot also feeds crypto cross-section validation."""
    if dataset != "credit":
        return []
    from whinfell_pipeline.crypto_sleeve import detect_crypto_source_type, ingest_crypto_file, merge_crypto_payload, load_crypto_sidecar, write_crypto_sidecar

    try:
        from whinfell_pipeline.crypto_sleeve import _read_csv
        headers, rows = _read_csv(src)
    except Exception:
        return []
    if detect_crypto_source_type(headers, src.name, rows=rows) != "snapshot":
        return []
    patch, res = ingest_crypto_file(src, dataset="crypto_snapshot")
    if not res.ok:
        return [f"crypto snapshot sidecar skipped: {'; '.join(res.errors)}"]
    payload = merge_crypto_payload(load_crypto_sidecar(), patch)
    write_crypto_sidecar(payload)
    return [f"crypto snapshot ingested from {src.name} ({len(patch.get('assets', {}))} assets)"]


def write_meta_sidecar(
    csv_path: Path,
    *,
    source_file: Path,
    operator: str,
    source: str,
    dataset: str | None,
    status: str,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    route: dict[str, Any] | None = None,
) -> Path:
    meta_path = csv_path.with_suffix(csv_path.suffix + ".meta.json")
    payload = {
        "meta_version": MANIFEST_VERSION,
        "collector_id": COMET_COLLECTOR_ID,
        "collector_version": COMET_COLLECTOR_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "source_file": str(source_file.resolve()),
        "staged_path": str(csv_path.resolve()),
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "source": source,
        "dataset": dataset,
        "filename": csv_path.name,
        "sha256": _sha256_file(csv_path),
        "status": status,
        "errors": errors or [],
        "warnings": warnings or [],
    }
    if route:
        payload["route"] = route
    meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return meta_path


def _manifest_stamp(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    return when.strftime("%Y%m%d_%H%M%S")


def write_stage_manifest(
    root: Path,
    *,
    operator: str,
    downloads_dir: Path,
    window: str,
    result: StageRunResult,
    when: datetime | None = None,
) -> Path:
    when = when or datetime.now(timezone.utc)
    out_dir = manifests_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"stage_manifest__{_manifest_stamp(when)}.json"
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "runbook_version": RUNBOOK_VERSION,
        "manifest_type": "stage",
        "created_at": when.isoformat(),
        "operator": operator,
        "staged_root": str(root.resolve()),
        "downloads_dir": str(downloads_dir.resolve()),
        "window": window,
        "files_scanned": result.files_scanned,
        "files_staged": result.files_staged,
        "files_quarantined": result.files_quarantined,
        "files_skipped": result.files_skipped,
        "entries": [
            {
                "source_path": fr.source_path,
                "staged_path": fr.staged_path,
                "meta_path": fr.meta_path,
                "source": fr.source,
                "dataset": fr.dataset,
                "status": fr.status,
                "errors": fr.errors,
                "warnings": fr.warnings,
            }
            for fr in result.file_results
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    result.manifest_path = str(path)
    return path


def write_daily_manifest(
    root: Path,
    *,
    operator: str,
    downloads_dir: Path,
    window: str,
    stage_result: StageRunResult,
    collect_exit: int,
    collect_stdout: str,
    hydrate_exit: int,
    hydrate_output: str,
    export_path: str | None,
    errors: list[str],
    when: datetime | None = None,
) -> Path:
    when = when or datetime.now(timezone.utc)
    out_dir = manifests_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"daily_manifest__{_manifest_stamp(when)}.json"
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "runbook_version": RUNBOOK_VERSION,
        "manifest_type": "daily",
        "created_at": when.isoformat(),
        "operator": operator,
        "staged_root": str(root.resolve()),
        "downloads_dir": str(downloads_dir.resolve()),
        "window": window,
        "stage_manifest": stage_result.manifest_path,
        "stage": {
            "files_scanned": stage_result.files_scanned,
            "files_staged": stage_result.files_staged,
            "files_quarantined": stage_result.files_quarantined,
            "files_skipped": stage_result.files_skipped,
        },
        "collect_exit": collect_exit,
        "collect_stdout": collect_stdout,
        "hydrate_exit": hydrate_exit,
        "hydrate_output": hydrate_output,
        "export_path": export_path,
        "errors": errors,
        "chain_ok": collect_exit == 0 and hydrate_exit == 0 and not errors,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def quarantine_file(
    src: Path,
    root: Path,
    *,
    operator: str,
    reason: str,
    when: datetime | None = None,
) -> Path:
    when = when or datetime.now(timezone.utc)
    dest_dir = quarantine_dir(root, when)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stamp = when.strftime("%H%M%S")
        dest = dest_dir / f"{stamp}__{src.name}"
    shutil.copy2(src, dest)
    meta_path = dest.with_suffix(dest.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "meta_version": MANIFEST_VERSION,
                "status": "quarantined",
                "operator": operator,
                "source_file": str(src.resolve()),
                "quarantined_at": when.isoformat(),
                "reason": reason,
                "sha256": _sha256_file(dest),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return dest


def iter_download_candidates(downloads_dir: Path, window: timedelta) -> Iterable[Path]:
    if not downloads_dir.is_dir():
        return
    for path in sorted(downloads_dir.glob("*.csv")):
        if path.name.startswith("."):
            continue
        if file_within_window(path, window):
            yield path


def stage_file(
    src: Path,
    root: Path,
    *,
    operator: str,
    overwrite: bool = False,
) -> StageFileResult:
    from whinfell_pipeline.raw_csv_transform import prepare_staged_csv

    fr = StageFileResult(source_path=str(src.resolve()))
    temp_stage: Path | None = None
    route_meta: dict[str, Any] | None = None
    try:
        from whinfell_pipeline.source_router import route_ingest

        route = route_ingest(src)
        route_meta = route.to_meta()
        if route.warnings:
            fr.warnings.extend(route.warnings)
    except Exception as exc:
        fr.warnings.append(f"route_ingest skipped: {exc}")

    try:
        source, dataset = infer_staged_destination(src.name)
    except ValueError as exc:
        fr.status = "quarantined"
        fr.errors.append(str(exc))
        quarantine_file(src, root, operator=operator, reason=str(exc))
        return fr

    dest_dir = staged_destination_dir(root, source, dataset)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    if dest.exists() and not overwrite:
        staged = StagedFile(path=dest, source=source, dataset=dataset, filename=src.name)
        existing = validate_staged_file(staged)
        if existing.ok:
            fr.status = "skipped"
            fr.source = source
            fr.dataset = dataset
            fr.staged_path = str(dest)
            fr.warnings.append("already staged with valid contract")
            return fr

    try:
        if source == SOURCE_CRYPTO or dataset == "flows":
            stage_src = src
        else:
            prepared = prepare_staged_csv(src, source=source, dataset=dataset)
            stage_src = prepared.path
            if prepared.transformed:
                temp_stage = stage_src
                fr.warnings.extend(prepared.warnings)
            elif prepared.warnings:
                fr.warnings.extend(prepared.warnings)
    except Exception as exc:
        if temp_stage and temp_stage.exists():
            temp_stage.unlink()
        fr.status = "quarantined"
        fr.errors.append(f"raw→WTM transform failed: {exc}")
        quarantine_file(src, root, operator=operator, reason=str(exc))
        return fr

    shutil.copy2(stage_src, dest)
    if temp_stage and temp_stage.exists():
        temp_stage.unlink()
    staged = StagedFile(path=dest, source=source, dataset=dataset, filename=src.name)
    validation = validate_staged_file(staged)
    if not validation.ok:
        fr.status = "quarantined"
        fr.errors.extend(validation.errors)
        fr.warnings.extend(validation.warnings)
        quarantine_dir_path = quarantine_file(
            dest,
            root,
            operator=operator,
            reason="; ".join(validation.errors) or "validation failed",
        )
        if dest.exists():
            dest.unlink()
        fr.staged_path = str(quarantine_dir_path)
        meta = quarantine_dir_path.with_suffix(quarantine_dir_path.suffix + ".meta.json")
        fr.meta_path = str(meta)
        return fr

    fr.status = "staged"
    fr.source = source
    fr.dataset = dataset
    fr.staged_path = str(dest)
    fr.warnings.extend(validation.warnings)
    meta = write_meta_sidecar(
        dest,
        source_file=src,
        operator=operator,
        source=source,
        dataset=dataset,
        status="staged",
        warnings=validation.warnings,
        route=route_meta,
    )
    fr.meta_path = str(meta)
    fr.warnings.extend(_maybe_ingest_crypto_snapshot_from_credit(src, dataset))
    fr.warnings.extend(_maybe_ingest_crypto_wide_backup(src, dataset))
    return fr


def cmd_init(staged_root: Path | None = None) -> Path:
    root = init_staged_tree(staged_root)
    manifests_dir(root).mkdir(parents=True, exist_ok=True)
    quarantine_dir(root).mkdir(parents=True, exist_ok=True)
    return root


def cmd_stage(
    *,
    downloads_dir: Path,
    staged_root: Path,
    operator: str,
    window: str,
    overwrite: bool = False,
) -> StageRunResult:
    init_staged_tree(staged_root)
    manifests_dir(staged_root).mkdir(parents=True, exist_ok=True)
    delta = parse_window(window)
    result = StageRunResult()
    for src in iter_download_candidates(downloads_dir, delta):
        result.files_scanned += 1
        fr = stage_file(src, staged_root, operator=operator, overwrite=overwrite)
        result.file_results.append(fr)
        if fr.status == "staged":
            result.files_staged += 1
        elif fr.status == "quarantined":
            result.files_quarantined += 1
        else:
            result.files_skipped += 1
    write_stage_manifest(
        staged_root,
        operator=operator,
        downloads_dir=downloads_dir,
        window=window,
        result=result,
    )
    return result


def ingest_crypto_staged_root(staged_root: Path, *, archive: bool = True) -> tuple[int, list[str]]:
    from whinfell_pipeline.crypto_sleeve import ingest_crypto_file, merge_crypto_payload, load_crypto_sidecar, write_crypto_sidecar
    from whinfell_pipeline.staged_csv import archive_staged_file, validate_crypto_staged_file

    payload = load_crypto_sidecar()
    lines: list[str] = []
    ingested = 0
    for staged in scan_staged_root(staged_root):
        if staged.source != SOURCE_CRYPTO:
            continue
        val = validate_crypto_staged_file(staged)
        if not val.ok:
            lines.append(f"crypto_error={staged.path}: {'; '.join(val.errors)}")
            continue
        patch, res = ingest_crypto_file(staged.path, dataset=staged.dataset)
        if not res.ok:
            lines.append(f"crypto_error={staged.path}: {'; '.join(res.errors)}")
            continue
        payload = merge_crypto_payload(payload, patch)
        ingested += 1
        lines.append(
            f"crypto_ingest file={staged.filename} type={res.source_type} dataset={staged.dataset or '-'}"
        )
        if archive:
            archive_staged_file(staged)
    if ingested:
        write_crypto_sidecar(payload)
    return ingested, lines


def cmd_collect(
    staged_root: Path,
    *,
    export_path: Path | None = None,
    dry_run: bool = False,
) -> tuple[int, str]:
    ingest_result = ingest_staged_root(
        staged_root,
        write_export=export_path,
        archive=not dry_run,
        dry_run=dry_run,
    )
    crypto_ingested, crypto_lines = (0, [])
    if not dry_run:
        crypto_ingested, crypto_lines = ingest_crypto_staged_root(staged_root, archive=True)
    lines = [
        f"pipeline_staged_ingest_ok version={PIPELINE_VERSION}",
        f"staged_root={staged_root}",
        f"files_found={ingest_result.files_found}",
        f"files_processed={ingest_result.files_processed}",
        f"files_failed={ingest_result.files_failed}",
        f"global_written={ingest_result.global_written}",
        f"china_written={ingest_result.china_written}",
        f"execution_records={ingest_result.execution_records}",
        f"crypto_ingested={crypto_ingested}",
    ]
    lines.extend(crypto_lines)
    for fr in ingest_result.file_results:
        lines.append(
            f"file={fr.path} source={fr.source} dataset={fr.dataset or '-'} "
            f"adapter={fr.adapter_id or '-'} status={fr.validation_status or '-'} "
            f"archived={fr.archived_to or '-'}"
        )
        for w in fr.warnings:
            lines.append(f"warning={fr.path}: {w}")
        for e in fr.errors:
            lines.append(f"error={fr.path}: {e}")
    out = "\n".join(lines) + "\n"
    if ingest_result.files_failed:
        return 1, out
    if ingest_result.files_found == 0:
        return 1, out
    return 0, out


def cmd_barchart_history(*, verbose: bool = False) -> tuple[int, str]:
    """File-based Barchart history hydration (desk CSV path, no API)."""
    from whinfell_pipeline.barchart_hydration import default_output_dir, run_barchart_hydration

    lines: list[str] = []

    def _log(msg: str) -> None:
        lines.append(msg)

    result = run_barchart_hydration(file_only=True, verbose=verbose, log_fn=_log)
    counts = result["counts"]
    m = result["manifest"]
    summary = [
        "barchart_history_ok",
        f"fetch_policy={m.get('fetch_policy', 'file_only')}",
        f"approved={counts['approved']} core_ok={counts['core_ok']} "
        f"curve_ok={counts['curve_ok']} spread_ok={counts['spread_ok']}",
        f"failed={m['symbol_count_failed']} empty={m['symbol_count_empty']}",
        f"output_dir={default_output_dir()}",
    ]
    for name, path in result["paths"].items():
        summary.append(f"output={name} path={path}")
    out = "\n".join(summary + lines) + "\n"
    return 0, out


def cmd_hydrate(hydrate_output: Path) -> tuple[int, str]:
    from whinfell_pipeline.hydrate import build_hydration_bundle

    try:
        bundle = build_hydration_bundle()
    except ValueError as exc:
        return 1, f"ERROR: {exc}\n"
    hydrate_output.parent.mkdir(parents=True, exist_ok=True)
    hydrate_output.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    desk_copy = Path.home() / "Desktop" / "Whinfell_Hydration_latest.json"
    dl_copy = Path.home() / "Downloads" / "Whinfell_Hydration_latest.json"
    for copy_path in (desk_copy, dl_copy):
        try:
            shutil.copy2(hydrate_output, copy_path)
        except OSError:
            pass
    lines = [
        "hydration_ok",
        f"snapshot_id={bundle.get('snapshot_id', '')}",
        f"freshness_status={bundle.get('freshness_status', '')}",
        f"output={hydrate_output}",
        f"desk_copy={desk_copy}",
        f"downloads_copy={dl_copy}",
    ]
    return 0, "\n".join(lines) + "\n"


def cmd_daily(
    *,
    downloads_dir: Path,
    staged_root: Path,
    operator: str,
    window: str,
    export_path: Path | None,
    hydrate_output: Path,
    overwrite: bool = False,
    skip_stage: bool = False,
    skip_collect: bool = False,
    skip_hydrate: bool = False,
    skip_barchart_history: bool = False,
) -> DailyRunResult:
    result = DailyRunResult()
    cmd_init(staged_root)

    if not skip_stage:
        result.stage = cmd_stage(
            downloads_dir=downloads_dir,
            staged_root=staged_root,
            operator=operator,
            window=window,
            overwrite=overwrite,
        )
    else:
        result.stage.manifest_path = ""

    if not skip_collect:
        result.collect_exit, result.collect_stdout = cmd_collect(
            staged_root,
            export_path=export_path,
        )
        if result.collect_exit != 0:
            result.errors.append("collect failed")
    else:
        result.collect_exit = 0

    if not skip_hydrate:
        result.hydrate_exit, hydrate_msg = cmd_hydrate(hydrate_output)
        result.hydrate_output = str(hydrate_output.resolve())
        if result.hydrate_exit != 0:
            result.errors.append("hydrate failed")
            result.errors.append(hydrate_msg.strip())
    else:
        result.hydrate_exit = 0

    if not skip_barchart_history:
        result.barchart_exit, result.barchart_stdout = cmd_barchart_history()
    else:
        result.barchart_exit = 0

    result.manifest_path = str(
        write_daily_manifest(
            staged_root,
            operator=operator,
            downloads_dir=downloads_dir,
            window=window,
            stage_result=result.stage,
            collect_exit=result.collect_exit,
            collect_stdout=result.collect_stdout,
            hydrate_exit=result.hydrate_exit,
            hydrate_output=result.hydrate_output,
            export_path=str(export_path) if export_path else None,
            errors=result.errors,
        )
    )
    return result


def run_subprocess_fallback(module: str, args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out