#!/usr/bin/env bash
echo "=== WTC Clean Start ==="

# Kill anything on old ports
echo "Killing old processes on ports 5001, 8000, 8767..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8767 | xargs kill -9 2>/dev/null || true

sleep 1

echo "Starting clean backend on port 8000..."
python3 app.py
