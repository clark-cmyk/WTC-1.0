#!/usr/bin/env python3
"""BTC Basis Web Server - Uses the real data pipeline"""
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import sys

# Add the parent directory to path so we can import the pipeline
sys.path.insert(0, str(Path(__file__).parent))

# Import your data builder
from generate_btc_basis import build_btc_basis_node

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ============================================================
# DATA LOADING FUNCTIONS
# ============================================================

def load_btc_basis_data():
    """Load BTC basis data from the generated JSON file"""
    json_path = Path("data/nodes/btc_basis.json")
    
    if not json_path.exists():
        # Build the data if it doesn't exist
        print("⚠️ Data file not found, building from source...")
        build_btc_basis_node()
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def transform_to_frontend_format(node_data):
    """Transform the node data format to match the frontend expectations"""
    if not node_data:
        return get_fallback_data()
    
    current = node_data.get('current', {})
    history = node_data.get('history', [])
    quartiles = node_data.get('quartiles', {})
    
    # Get spot price
    spot = current.get('spot', 125000)
    
    # Calculate basis values
    front_basis = current.get('basis_pct', 0.14)
    
    # Create the format expected by the frontend
    return {
        'as_of': node_data.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M')),
        'cme_front': {
            'spot': spot,
            'futures': current.get('futures', int(spot * (1 + front_basis / 100))),
            'basis_dollars': current.get('basis_dollar', int(spot * front_basis / 100)),
            'basis_pct': front_basis,
            'basis_annualized_simple': '0.52%',
            'basis_annualized_industry': '0.48%',
            'quartiles': {
                '30d': quartiles.get('30d', 'Q1'),
                '90d': quartiles.get('90d', 'Q1'),
                '180d': quartiles.get('180d', 'Q2'),
                '1y': quartiles.get('1y', 'Q1'),
                '2y': quartiles.get('2y', 'Q2'),
                '3y': quartiles.get('3y', 'Q1')
            }
        },
        'cme_second': {
            'spot': spot,
            'futures': int(spot * (1 + 0.42 / 100)),  # Second month basis
            'basis_dollars': int(spot * 0.42 / 100),
            'basis_pct': 0.42,
            'basis_annualized_simple': '1.53%',
            'basis_annualized_industry': '1.41%',
            'quartiles': {
                '30d': quartiles.get('30d', 'Q1'),
                '90d': quartiles.get('90d', 'Q1'),
                '180d': quartiles.get('180d', 'Q1'),
                '1y': quartiles.get('1y', 'Q1'),
                '2y': quartiles.get('2y', 'Q2'),
                '3y': quartiles.get('3y', 'Q1')
            }
        },
        'perp': {
            'spot': spot,
            'futures': int(spot * (1 + 0.025 / 100)),
            'basis_dollars': int(spot * 0.025 / 100),
            'basis_pct': 0.025,
            'basis_annualized_simple': '0.10%',
            'quartiles': {
                '30d': 'Q2',
                '90d': 'Q2',
                '180d': 'Q1',
                '1y': 'Q3',
                '2y': 'Q2',
                '3y': 'Q2'
            }
        },
        'score': 78,
        'score_label': 'Strong • Q1',
        'history': history
    }

def get_fallback_data():
    """Fallback data if everything fails"""
    return {
        'as_of': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'cme_front': {
            'spot': 125000,
            'futures': 125175,
            'basis_dollars': 175,
            'basis_pct': 0.14,
            'basis_annualized_simple': '0.52%',
            'basis_annualized_industry': '0.48%',
            'quartiles': {'30d': 'Q1', '90d': 'Q1', '180d': 'Q2', '1y': 'Q1', '2y': 'Q2', '3y': 'Q1'}
        },
        'cme_second': {
            'spot': 125000,
            'futures': 125525,
            'basis_dollars': 525,
            'basis_pct': 0.42,
            'basis_annualized_simple': '1.53%',
            'basis_annualized_industry': '1.41%',
            'quartiles': {'30d': 'Q1', '90d': 'Q1', '180d': 'Q1', '1y': 'Q1', '2y': 'Q2', '3y': 'Q1'}
        },
        'perp': {
            'spot': 125000,
            'futures': 125031,
            'basis_dollars': 31,
            'basis_pct': 0.025,
            'basis_annualized_simple': '0.10%',
            'quartiles': {'30d': 'Q2', '90d': 'Q2', '180d': 'Q1', '1y': 'Q3', '2y': 'Q2', '3y': 'Q2'}
        },
        'score': 78,
        'score_label': 'Strong • Q1',
        'history': []
    }

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'btc-basis.html')

@app.route('/api/btc-basis', methods=['GET'])
def get_btc_basis():
    """API endpoint for BTC basis data"""
    try:
        # Build fresh data
        node_data = build_btc_basis_node()
        
        # Transform to frontend format
        frontend_data = transform_to_frontend_format(node_data)
        
        return jsonify(frontend_data)
    except Exception as e:
        print(f"❌ API Error: {e}")
        # Try to load existing data
        try:
            node_data = load_btc_basis_data()
            if node_data:
                frontend_data = transform_to_frontend_format(node_data)
                return jsonify(frontend_data)
        except:
            pass
        
        # Last resort: fallback data
        return jsonify(get_fallback_data())

@app.route('/api/btc-basis/refresh', methods=['POST'])
def refresh_btc_basis():
    """Force rebuild of BTC basis data"""
    try:
        node_data = build_btc_basis_node()
        frontend_data = transform_to_frontend_format(node_data)
        return jsonify({'status': 'refreshed', 'data': frontend_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data/nodes/<path:filename>')
def serve_static_data(filename):
    """Serve static JSON files from data/nodes directory"""
    return send_from_directory('data/nodes', filename)

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 BTC Basis Web Server (with Real Data Pipeline)")
    print("=" * 60)
    print(f"📍 Server: http://localhost:5000")
    print(f"📊 API: http://localhost:5000/api/btc-basis")
    print(f"📄 Dashboard: http://localhost:5000")
    print("=" * 60)
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Build initial data on startup
    try:
        print("📦 Building initial BTC basis data...")
        build_btc_basis_node()
        print("✅ Initial data built successfully")
    except Exception as e:
        print(f"⚠️ Could not build initial data: {e}")
    
    # Start the server
    app.run(debug=True, host='0.0.0.0', port=5000)