#!/usr/bin/env python3
"""Real run_csv_download.py - calls actual pipeline."""

import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "whinfell_pipeline"))

from whinfell_pipeline.csv_download import cmd_daily

def main():
    try:
        result = cmd_daily(
            downloads_dir=REPO_ROOT / "data" / "downloads",
            staged_root=REPO_ROOT / "staged_raw",
            operator="default",
            window="1d",
            export_path=REPO_ROOT / "data",
            hydrate_output=REPO_ROOT / "data" / "hydration" / "latest.json"
        )

        print(json.dumps({
            "success": len(result.errors) == 0,
            "message": "Daily pipeline completed",
            "files_staged": result.stage.files_staged,
            "files_quarantined": result.stage.files_quarantined,
            "hydrate_output": str(result.hydrate_output),
            "errors": result.errors
        }, indent=2))

    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2))

if __name__ == "__main__":
    main()
