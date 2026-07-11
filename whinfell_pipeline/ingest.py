#!/usr/bin/env python3
"""Unified ingest: adapter → canonical → Parquet + optional WTM EXPORT v2.1."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whinfell_pipeline.adapters.registry import parse_with_best_adapter
from whinfell_pipeline.canonical import DecisionBundle, ValidationStatus
from whinfell_pipeline.decision_export import write_wtm_export_v21
from whinfell_pipeline.normalize import partition_records
from whinfell_pipeline.version import BUNDLE_VERSION, PIPELINE_VERSION


@dataclass
class IngestResult:
    adapter_id: str = ""
    validation_status: ValidationStatus = ValidationStatus.FAILED
    lineage_hash: str = ""
    global_written: int = 0
    china_written: int = 0
    execution_records: int = 0
    global_parquet_path: str = ""
    china_parquet_path: str = ""
    wtm_export_path: str = ""
    warnings: list[str] = field(default_factory=list)


def _load_payload(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(raw)
    return raw


def ingest_payload(
    payload: Any,
    *,
    global_output: Path | None = None,
    china_output: Path | None = None,
    append: bool = True,
    write_export: Path | None = None,
) -> IngestResult:
    """Run full pipeline on a raw payload."""
    from china_policy_track.storage import default_parquet_path as china_default
    from china_policy_track.storage import write_observations as write_china
    from whinfell_pipeline.global_track.storage import default_parquet_path as global_default
    from whinfell_pipeline.global_track.storage import write_observations as write_global

    result = IngestResult()
    adapter, parsed = parse_with_best_adapter(payload)

    if adapter is None:
        result.warnings = list(parsed.warnings)
        return result

    result.adapter_id = adapter.adapter_id
    result.validation_status = parsed.validation_status
    result.lineage_hash = parsed.lineage_hash
    result.warnings = list(parsed.warnings)

    if not parsed.ok:
        return result

    global_obs, china_obs, execution = partition_records(parsed.records)
    result.execution_records = len(execution)

    if execution:
        sidecar = Path(__file__).resolve().parents[1] / "data" / "execution" / "v1" / "latest_execution.json"
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        latest = execution[-1]
        sidecar.write_text(
            json.dumps(
                {
                    "payload": latest,
                    "as_of": latest.get("as_of") or datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if global_obs:
        g_path = write_global(global_obs, global_output or global_default(), append=append)
        result.global_written = len(global_obs)
        result.global_parquet_path = str(g_path)

    if china_obs:
        c_path = write_china(china_obs, china_output or china_default(), append=append)
        result.china_written = len(china_obs)
        result.china_parquet_path = str(c_path)

    if write_export and global_obs:
        g0 = global_obs[0].to_dict()
        china_data = china_obs[0].to_dict() if china_obs else {}
        block = write_wtm_export_v21(g0, china_data=china_data)
        write_export.parent.mkdir(parents=True, exist_ok=True)
        write_export.write_text(block + "\n", encoding="utf-8")
        result.wtm_export_path = str(write_export)
    elif parsed.wtm_export_block and write_export:
        write_export.parent.mkdir(parents=True, exist_ok=True)
        write_export.write_text(parsed.wtm_export_block + "\n", encoding="utf-8")
        result.wtm_export_path = str(write_export)

    return result


def ingest_file(
    input_path: Path,
    *,
    global_output: Path | None = None,
    china_output: Path | None = None,
    append: bool = True,
    write_export: Path | None = None,
) -> IngestResult:
    payload = _load_payload(input_path)
    return ingest_payload(
        payload,
        global_output=global_output,
        china_output=china_output,
        append=append,
        write_export=write_export,
    )


def bundle_from_transmission_control(data: dict[str, Any]) -> DecisionBundle:
    """Validate/normalize a browser-exported decision bundle."""
    return DecisionBundle.from_mapping(data)


def main(argv: list[str] | None = None) -> int:
    from whinfell_pipeline.staged_csv import default_staged_root, ingest_staged_root, init_staged_tree

    parser = argparse.ArgumentParser(description="Whinfell pipeline ingest (adapter → Parquet)")
    parser.add_argument("--input", default=None, help="Path to .json bundle or .txt export")
    parser.add_argument("--staged", action="store_true", help="Scan staged_raw/ CSV tree")
    parser.add_argument("--staged-root", default=None, help="Override staged_raw root (default: repo/staged_raw)")
    parser.add_argument("--dry-run", action="store_true", help="Validate staged CSVs without writing Parquet")
    parser.add_argument("--no-archive", action="store_true", help="Keep staged CSVs in place after ingest")
    parser.add_argument("--init-staged", action="store_true", help="Create staged_raw/ folder tree and exit")
    parser.add_argument("--global-output", default=None, help="Global Parquet path override")
    parser.add_argument("--china-output", default=None, help="China Parquet path override")
    parser.add_argument("--export", default=None, help="Optional path to write WTM EXPORT v2.1 text")
    parser.add_argument("--no-append", action="store_true", help="Overwrite Parquet instead of append")
    args = parser.parse_args(argv)

    if args.init_staged:
        root = init_staged_tree(Path(args.staged_root) if args.staged_root else None)
        print(f"staged_tree_ok root={root}")
        return 0

    if args.staged:
        root = Path(args.staged_root) if args.staged_root else default_staged_root()
        result = ingest_staged_root(
            root,
            global_output=Path(args.global_output) if args.global_output else None,
            china_output=Path(args.china_output) if args.china_output else None,
            append=not args.no_append,
            write_export=Path(args.export) if args.export else None,
            archive=not args.no_archive,
            dry_run=args.dry_run,
        )
        print(f"pipeline_staged_ingest_ok version={PIPELINE_VERSION} bundle={BUNDLE_VERSION}")
        print(f"staged_root={root}")
        print(f"files_found={result.files_found}")
        print(f"files_processed={result.files_processed}")
        print(f"files_failed={result.files_failed}")
        print(f"global_written={result.global_written}")
        print(f"china_written={result.china_written}")
        print(f"execution_records={result.execution_records}")
        for fr in result.file_results:
            print(
                f"file={fr.path} source={fr.source} dataset={fr.dataset or '-'} "
                f"adapter={fr.adapter_id or '-'} status={fr.validation_status or '-'} "
                f"archived={fr.archived_to or '-'}"
            )
            for w in fr.warnings:
                print(f"warning={fr.path}: {w}")
            for e in fr.errors:
                print(f"error={fr.path}: {e}")
        return 0 if result.files_failed == 0 and result.files_found > 0 else (1 if result.files_failed else 0)

    if not args.input:
        print("ERROR: provide --input <file> or --staged", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 1

    result = ingest_file(
        input_path,
        global_output=Path(args.global_output) if args.global_output else None,
        china_output=Path(args.china_output) if args.china_output else None,
        append=not args.no_append,
        write_export=Path(args.export) if args.export else None,
    )

    print(f"pipeline_ingest_ok version={PIPELINE_VERSION} bundle={BUNDLE_VERSION}")
    print(f"adapter={result.adapter_id or 'none'}")
    print(f"validation_status={result.validation_status.value}")
    print(f"lineage_hash={result.lineage_hash}")
    print(f"global_written={result.global_written}")
    print(f"china_written={result.china_written}")
    print(f"execution_records={result.execution_records}")
    if result.global_parquet_path:
        print(f"global_parquet_path={result.global_parquet_path}")
    if result.china_parquet_path:
        print(f"china_parquet_path={result.china_parquet_path}")
    if result.wtm_export_path:
        print(f"wtm_export_path={result.wtm_export_path}")
    for w in result.warnings:
        print(f"warning={w}")

    return 0 if result.validation_status != ValidationStatus.FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())