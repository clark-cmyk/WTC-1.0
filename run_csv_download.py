import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "whinfell_pipeline"))

from whinfell_pipeline.csv_download import cmd_daily

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["daily"])
    args = parser.parse_args()

    if args.mode == "daily":
        result = cmd_daily(
            downloads_dir=BASE_DIR / "data" / "downloads",
            staged_root=BASE_DIR / "staged_raw",
            operator="default",
            window="1d",
            export_path=BASE_DIR / "data",
            hydrate_output=BASE_DIR / "data" / "hydrated"  # Use Path instead of bool
        )
        print(result)
    else:
        print("Only 'daily' mode supported right now")

if __name__ == "__main__":
    main()
