from pathlib import Path
import subprocess
import sys
import json

# Determine repository root robustly
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR if (SCRIPT_DIR / "run_csv_download.py").exists() else SCRIPT_DIR.parent
PIPELINE = REPO_ROOT / "run_csv_download.py"

def run_full_daily():
    if not PIPELINE.exists():
        return {
            "success": False,
            "error": f"Pipeline script not found: {PIPELINE}",
            "repo_root": str(REPO_ROOT),
            "searched_locations": [str(SCRIPT_DIR), str(REPO_ROOT)]
        }
    
    cmd = [sys.executable, str(PIPELINE), "daily"]
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Try to parse JSON output from pipeline
        try:
            output = json.loads(result.stdout.strip())
            if isinstance(output, dict):
                return output
            else:
                return {
                    "success": result.returncode == 0,
                    "data": output,
                    "returncode": result.returncode
                }
        except (json.JSONDecodeError, TypeError):
            # Fallback to structured response
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
                "pipeline": str(PIPELINE)
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Pipeline execution timed out after 300 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e), "pipeline": str(PIPELINE)}

if __name__ == "__main__":
    print(json.dumps(run_full_daily(), indent=2))