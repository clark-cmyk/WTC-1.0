#!/usr/bin/env python3
"""Lightweight China Policy ingestion: parse → normalize → write Parquet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from china_policy_track.data_parser import parse_input
from china_policy_track.storage import default_parquet_path, write_observations
from china_policy_track.version import EXPORT_FORMAT, SCHEMA_VERSION, TRACK_ID


def ingest_payload(payload: str | dict[str, Any], *, output: Path | None = None, append: bool = True) -> Path:
    observation = parse_input(payload)
    return write_observations([observation], output, append=append)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest China Policy track observations to Parquet")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to .txt (Perplexity export) or .json (Koyfin/Barchart structured export)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Parquet output path (default: data/china_policy/v1/china_policy_observations.parquet)",
    )
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Overwrite Parquet instead of appending",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 1

    raw = input_path.read_text(encoding="utf-8")
    if input_path.suffix.lower() == ".json":
        payload: str | dict[str, Any] = json.loads(raw)
    else:
        payload = raw

    out = Path(args.output) if args.output else default_parquet_path()
    path = ingest_payload(payload, output=out, append=not args.no_append)

    print(f"china_policy_ingest_ok track={TRACK_ID} schema={SCHEMA_VERSION}")
    print(f"export_format={EXPORT_FORMAT}")
    print(f"observation_written=1")
    print(f"parquet_path={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())