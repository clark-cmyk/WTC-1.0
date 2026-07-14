#!/usr/bin/env python3
"""Whinfell Run CSV Download - Simple Launcher"""
from whinfell_pipeline.csv_download import cmd_daily

if __name__ == "__main__":
    print("🚀 Starting Whinfell Daily Pipeline...")
    result = cmd_daily()
    print(f"✅ Pipeline finished: {result.message}")
    print(f"   Hydration file: {result.hydrate_output}")
    print("   Ready for UI refresh.")
