#!/usr/bin/env python3
"""
agent_wrapper.py
Clean interface for Orchestrator and Captains to control the data pipeline.
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Path to your existing pipeline
PIPELINE = Path(__file__).parent.parent / "run_csv_download.py"


def run_pipeline(command: str, **kwargs) -> Dict[str, Any]:
    """
    Main function the agents will use to control the pipeline.

    Examples:
        run_pipeline("daily")
        run_pipeline("collect", source="koyfin")
        run_pipeline("hydrate")
        run_pipeline("collect", source="barchart", mode="incremental")
    """
    allowed = ["init", "stage", "collect", "hydrate", "daily"]

    if command not in allowed:
        return {"success": False, "error": f"Invalid command: {command}"}

    cmd = [sys.executable, str(PIPELINE), command]

    # Add any extra arguments
    for key, value in kwargs.items():
        cmd.extend([f"--{key}", str(value)])

    print(f"[AgentWrapper] Executing: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=PIPELINE.parent
        )

        return {
            "success": result.returncode == 0,
            "command": command,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ====================== CONVENIENCE FUNCTIONS ======================

def run_full_daily():
    """Full daily refresh (recommended for scheduled runs)"""
    return run_pipeline("daily")


def collect_data(source: str = "all"):
    """Collect data only (no hydration)"""
    return run_pipeline("collect", source=source)


def hydrate_data():
    """Process existing raw data into Blackboard"""
    return run_pipeline("hydrate")


if __name__ == "__main__":
    # Quick test
    print(run_full_daily())