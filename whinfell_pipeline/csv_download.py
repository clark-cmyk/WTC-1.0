#!/usr/bin/env python3
"""Real CSV Download Orchestration"""

from pathlib import Path
from dataclasses import dataclass
import json
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from whinfell_pipeline.staged_csv import cmd_stage, cmd_collect, cmd_hydrate

@dataclass
class DailyRunResult:
    success: bool = False
    stage_files: int = 0
    errors: list = None
    hydrate_output: str = ""

def cmd_daily(downloads_dir=None, staged_root=None, operator="default", window="1d", export_path=None, hydrate_output=None):
    downloads_dir = Path(downloads_dir) if downloads_dir else REPO_ROOT / "data" / "downloads"
    staged_root = Path(staged_root) if staged_root else REPO_ROOT / "staged_raw"
    hydrate_output = Path(hydrate_output) if hydrate_output else REPO_ROOT / "data" / "hydration" / "latest.json"

    downloads_dir.mkdir(parents=True, exist_ok=True)
    staged_root.mkdir(parents=True, exist_ok=True)
    hydrate_output.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stage from whinfell_drop
        stage_result = cmd_stage(downloads_dir=downloads_dir, staged_root=staged_root)
        
        # Collect and hydrate
        collect_result = cmd_collect(staged_root=staged_root)
        hydrate_result, hydrate_msg = cmd_hydrate(hydrate_output)

        success = stage_result.get("files_staged", 0) > 0

        return DailyRunResult(
            success=success,
            stage_files=stage_result.get("files_staged", 0),
            errors=[] if success else ["collect failed"],
            hydrate_output=str(hydrate_output)
        )
    except Exception as e:
        return DailyRunResult(success=False, errors=[str(e)])

if __name__ == "__main__":
    result = cmd_daily()
    print(json.dumps({
        "success": result.success,
        "stage_files": result.stage_files,
        "errors": result.errors,
        "hydrate_output": result.hydrate_output
    }, indent=2))
