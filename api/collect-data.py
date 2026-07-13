from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/api/collect-data', methods= )
def collect_data():
    try:
        data = request.get_json() or        source = data.get('source', 'all')
        
        print(f"Received collection request for: {source}")
        
        # Run your existing Python downloader
        result = subprocess.run( , capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Data collection completed",
                "source": source,
                "output": result.stdout.strip()
            })
        else:
            return jsonify({
                "success": False,
                "message": "Python script failed",
                "error": result.stderr.strip()
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)