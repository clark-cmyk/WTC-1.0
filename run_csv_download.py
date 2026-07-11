#!/usr/bin/env python3
"""Comet daily CSV download → stage → collect → hydrate operator runbook."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.csv_download import (  # noqa: E402
    cmd_collect,
    cmd_daily,
    cmd_hydrate,
    cmd_init,
    cmd_stage,
    default_downloads_dir,
    default_staged_root,
)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--downloads", default=None, help="Browser downloads folder (default: ~/Downloads)")
    parser.add_argument("--staged-root", default=None, help="staged_raw root (default: repo/staged_raw)")
    parser.add_argument("--operator", default="desk", help="Operator id for manifests and .meta.json sidecars")
    parser.add_argument("--window", default="24h", help="Candidate window: today, 24h, 6h, 30m")
    parser.add_argument("--export", default=None, help="Optional WTM EXPORT v2.1 path during collect")
    parser.add_argument("--hydrate-output", default=None, help="Hydration bundle output (default: data/hydration/latest.json)")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing staged CSV with same name")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Whinfell Comet CSV download & staging workflow (runbook v1.0)",
    )
    _add_common_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize staged_raw/, manifests/, quarantine/")
    _add_common_args(p_init)

    p_stage = sub.add_parser("stage", help="Copy CSVs from downloads → staged_raw (never move)")
    _add_common_args(p_stage)
    p_stage.add_argument("--dry-run", action="store_true", help="Reserved — stage always copies only")

    p_collect = sub.add_parser("collect", help="Run ingest --staged → Parquet + execution sidecar")
    _add_common_args(p_collect)

    p_hydrate = sub.add_parser("hydrate", help="Build hydration bundle for Transmission Control import")
    _add_common_args(p_hydrate)

    p_daily = sub.add_parser("daily", help="Full chain: init → stage → collect → hydrate")
    _add_common_args(p_daily)
    p_daily.add_argument("--skip-stage", action="store_true")
    p_daily.add_argument("--skip-collect", action="store_true")
    p_daily.add_argument("--skip-hydrate", action="store_true")
    p_daily.add_argument("--skip-barchart-history", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    downloads = Path(args.downloads) if args.downloads else default_downloads_dir()
    staged_root = Path(args.staged_root) if args.staged_root else default_staged_root(REPO_ROOT)
    hydrate_out = (
        Path(args.hydrate_output)
        if args.hydrate_output
        else REPO_ROOT / "data" / "hydration" / "latest.json"
    )
    export_path = Path(args.export) if args.export else None

    if args.command == "init":
        root = cmd_init(staged_root)
        print(f"csv_download_init_ok root={root}")
        print(f"manifests={root / 'manifests'}")
        print(f"quarantine={root / 'quarantine'}")
        return 0

    if args.command == "stage":
        if not downloads.is_dir():
            print(f"ERROR: downloads folder not found: {downloads}", file=sys.stderr)
            return 1
        result = cmd_stage(
            downloads_dir=downloads,
            staged_root=staged_root,
            operator=args.operator,
            window=args.window,
            overwrite=args.overwrite,
        )
        print("csv_download_stage_ok")
        print(f"manifest={result.manifest_path}")
        print(f"files_scanned={result.files_scanned}")
        print(f"files_staged={result.files_staged}")
        print(f"files_quarantined={result.files_quarantined}")
        print(f"files_skipped={result.files_skipped}")
        for fr in result.file_results:
            print(f"file={fr.source_path} status={fr.status} staged={fr.staged_path or '-'}")
            for e in fr.errors:
                print(f"error={fr.source_path}: {e}")
        return 0 if result.files_quarantined == 0 else 1

    if args.command == "collect":
        code, out = cmd_collect(staged_root, export_path=export_path)
        sys.stdout.write(out)
        return code

    if args.command == "hydrate":
        code, out = cmd_hydrate(hydrate_out)
        sys.stdout.write(out)
        return code

    if args.command == "daily":
        if not downloads.is_dir():
            print(f"ERROR: downloads folder not found: {downloads}", file=sys.stderr)
            return 1
        result = cmd_daily(
            downloads_dir=downloads,
            staged_root=staged_root,
            operator=args.operator,
            window=args.window,
            export_path=export_path,
            hydrate_output=hydrate_out,
            overwrite=args.overwrite,
            skip_stage=args.skip_stage,
            skip_collect=args.skip_collect,
            skip_hydrate=args.skip_hydrate,
            skip_barchart_history=args.skip_barchart_history,
        )
        print("csv_download_daily_ok" if not result.errors else "csv_download_daily_partial")
        print(f"hydration_bundle={hydrate_out}")
        print("next_step=Transmission Control → Import Latest Hydration Bundle")
        print(f"daily_manifest={result.manifest_path}")
        print(f"stage_manifest={result.stage.manifest_path or '-'}")
        print(f"files_staged={result.stage.files_staged}")
        print(f"files_quarantined={result.stage.files_quarantined}")
        print(f"collect_exit={result.collect_exit}")
        print(f"hydrate_exit={result.hydrate_exit}")
        print(f"barchart_exit={result.barchart_exit}")
        print(f"hydrate_output={result.hydrate_output or '-'}")
        if result.barchart_stdout:
            sys.stdout.write(result.barchart_stdout)
        for err in result.errors:
            print(f"error={err}")
        if result.collect_stdout:
            sys.stdout.write(result.collect_stdout)
        return 0 if not result.errors and result.collect_exit == 0 and result.hydrate_exit == 0 else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())