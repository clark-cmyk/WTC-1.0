#!/usr/bin/env python3
"""
WTC Backend Starter
"""

import subprocess
import time
import sys
from pathlib import Path

PORT = 5001
BACKEND_DIR = Path(__file__).parent.parent
BACKEND_SCRIPT = BACKEND_DIR / "collect-data.py"

def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_backend() -> dict:
    if is_port_in_use(PORT):
        print(f"✅ Backend already running on port {PORT}")
        return {"success": True, "message": "already running"}

    print(f"Starting WTC Backend on port {PORT}...")

    try:
        subprocess.Popen([
            sys.executable, str(BACKEND_SCRIPT)
        ], cwd=BACKEND_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        time.sleep(3)

        if is_port_in_use(PORT):
            print("✅ Backend started successfully")
            return {"success": True, "message": "started"}
        else:
            print("❌ Failed to start backend")
            return {"success": False, "message": "failed to start"}
    except Exception as e:
        print(f"Error starting backend: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = start_backend()
    print(result)
