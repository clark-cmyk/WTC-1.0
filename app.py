import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request, send_from_directory
import asyncio

from drone_wars.core import DroneWars

app = Flask(__name__, static_folder='.', static_url_path='')
drone_wars = DroneWars()

@app.route('/')
def index():
    return send_from_directory('.', 'wtc_1.0.html')

@app.route('/api/refresh-data', methods=['POST'])
def refresh_data():
    try:
        drone_wars.log("🔄 Refresh Data triggered by user", "system")
        result = asyncio.run(drone_wars.run())
        return jsonify({
            "success": True,
            "message": "Refresh completed successfully",
            "logs": drone_wars.get_logs(),
            "panel_content": result.get("panel_content", {}),
            "market_summary": result.get("summary", "")
        })
    except Exception as e:
        error_msg = f"Critical error: {str(e)}"
        drone_wars.log(error_msg, "error")
        return jsonify({
            "success": False,
            "message": error_msg,
            "logs": drone_wars.get_logs()
        }), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify({"logs": drone_wars.get_logs()})


if __name__ == '__main__':
    print("🚀 WTC-1.0 Drone Wars Backend started on http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
