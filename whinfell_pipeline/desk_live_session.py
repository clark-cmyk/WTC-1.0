#!/usr/bin/env python3
"""Desk live session — parse latest quarantine flows, hydrate bundle, emit manifest."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whinfell_pipeline.flows_parser import (
    assess_flows_basket_health,
    default_flows_sidecar_path,
    find_latest_quarantine_flows_csv,
    parse_and_write,
)
from whinfell_pipeline.hydrate import build_hydration_bundle


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_dir(repo_root: Path) -> Path:
    env = os.environ.get("GROK_GOAL_SCRATCH", "").strip()
    if env:
        scratch = Path(env)
        scratch.mkdir(parents=True, exist_ok=True)
        return scratch
    return repo_root / "data" / "hydration"


def run_desk_live_session(
    *,
    repo_root: Path | None = None,
    hydrate_output: Path | None = None,
    node_id: str = "credit",
) -> dict[str, Any]:
    """Parse newest quarantine flows CSV, hydrate bundle, write golden manifest."""
    root = repo_root or _repo_root()
    csv_path = find_latest_quarantine_flows_csv(root)
    if csv_path is None:
        raise FileNotFoundError(
            "No quarantine WTM-Flows-Global.csv found under staged_raw/quarantine/"
        )

    sidecar_path = default_flows_sidecar_path(root)
    flows_payload = parse_and_write(csv_path, sidecar_path)

    bundle_path = hydrate_output or (root / "data" / "hydration" / "latest.json")
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = build_hydration_bundle(repo_root=root, flows_sidecar=flows_payload)
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    flows_health = assess_flows_basket_health(flows_payload, node_id=node_id)
    manifest = {
        "session_type": "desk_live",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "flows_csv": str(csv_path),
        "sidecar_path": str(sidecar_path),
        "hydration_bundle": str(bundle_path),
        "flows_health": flows_health,
        "snapshot_id": bundle.get("snapshot_id"),
        "freshness_status": bundle.get("freshness_status"),
        "flows_sidecar_status": (bundle.get("flows_sidecar") or {}).get("flows_status"),
    }
    manifest_path = _manifest_dir(root) / "golden_session_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "csv_path": csv_path,
        "sidecar_path": sidecar_path,
        "bundle_path": bundle_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "bundle": bundle,
    }


def _print_next_steps(result: dict[str, Any]) -> None:
    bundle_path = result["bundle_path"]
    manifest_path = result["manifest_path"]
    health = result["manifest"]["flows_health"]
    print("desk_live_session_ok")
    print(f"flows_csv={result['csv_path']}")
    print(f"sidecar={result['sidecar_path']}")
    print(f"hydration_bundle={bundle_path}")
    print(f"manifest={manifest_path}")
    print(f"flows_health_status={health.get('status')}")
    print("")
    print("Next steps for Clark:")
    print("  1. Open Transmission Control (Whinfell_Transmission_Control.command)")
    print("  2. Import Latest Hydration Bundle")
    print(f"  3. Select file: {bundle_path}")
    if health.get("status") == "partial":
        missing = ", ".join(health.get("missing_tickers") or [])
        print(f"  4. Note: partial basket — missing tickers: {missing}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Desk live session: quarantine flows → sidecar → hydration bundle"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Hydration bundle output (default: data/hydration/latest.json)",
    )
    parser.add_argument(
        "--node-id",
        default="credit",
        help="Node id for basket health assessment (default: credit)",
    )
    args = parser.parse_args(argv)

    try:
        result = run_desk_live_session(
            hydrate_output=Path(args.output) if args.output else None,
            node_id=args.node_id,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    _print_next_steps(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())