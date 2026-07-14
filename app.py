from flask import Flask, request, jsonify, make_response
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.append(str(REPO_ROOT))

from whinfell_pipeline.agent_wrapper import run_full_daily

app = Flask(__name__)

# Manual CORS for development
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.route("/")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "message": "WTC 1.0 Backend running on port 5001"})

@app.route('/api/trigger-collection', methods=['POST', 'OPTIONS'])
def trigger_collection():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        result = run_full_daily()
        return jsonify({
            "success": result.get("success", False),
            "command": "daily",
            "message": result.get("message", ""),
            "error": result.get("error"),
            "stdout": result.get("stdout", "")
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 WTC-1.0 Drone Wars Backend started on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
