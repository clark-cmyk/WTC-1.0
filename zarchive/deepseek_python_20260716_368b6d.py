#!/usr/bin/env python3
"""BTC Basis Backend Server"""
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime, timedelta
import random
import os

# Create Flask app
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all routes

# ============================================================
# DATA GENERATION FUNCTIONS
# ============================================================

def generate_historical_data(days=30, base_spot=125000):
    """Generate realistic historical BTC basis data"""
    history = []
    spot = base_spot
    
    for i in range(days - 1, -1, -1):
        d = datetime.now() - timedelta(days=i)
        # Add realistic random walk
        spot = spot + (random.random() - 0.48) * 800
        spot = max(spot, 118000)
        spot = min(spot, 132000)
        
        # Basis varies with market conditions
        basis_pct = 0.08 + random.random() * 0.5
        fut_price = int(spot * (1 + basis_pct / 100))
        
        history.append({
            'date': d.strftime('%Y-%m-%d'),
            'spot': int(spot),
            'futures': fut_price,
            'basis_pct': round(basis_pct, 2)
        })
    
    return history

def get_basis_data():
    """Generate complete BTC basis dataset"""
    history = generate_historical_data(30)
    current = history[-1]
    spot = current['spot']
    
    # Current basis values
    front_basis = 0.14
    second_basis = 0.42
    perp_basis = 0.025
    
    return {
        'as_of': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'cme_front': {
            'spot': spot,
            'futures': int(spot * (1 + front_basis / 100)),
            'basis_dollars': int(spot * front_basis / 100),
            'basis_pct': front_basis,
            'basis_annualized_simple': '0.52%',
            'basis_annualized_industry': '0.48%',
            'quartiles': {
                '30d': 'Q1',
                '90d': 'Q1',
                '180d': 'Q2',
                '1y': 'Q1',
                '2y': 'Q2',
                '3y': 'Q1'
            }
        },
        'cme_second': {
            'spot': spot,
            'futures': int(spot * (1 + second_basis / 100)),
            'basis_dollars': int(spot * second_basis / 100),
            'basis_pct': second_basis,
            'basis_annualized_simple': '1.53%',
            'basis_annualized_industry': '1.41%',
            'quartiles': {
                '30d': 'Q1',
                '90d': 'Q1',
                '180d': 'Q1',
                '1y': 'Q1',
                '2y': 'Q2',
                '3y': 'Q1'
            }
        },
        'perp': {
            'spot': spot,
            'futures': int(spot * (1 + perp_basis / 100)),
            'basis_dollars': int(spot * perp_basis / 100),
            'basis_pct': perp_basis,
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
        data = get_basis_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data/nodes/<path:filename>')
def serve_static_data(filename):
    """Serve static JSON files from data/nodes directory"""
    return send_from_directory('data/nodes', filename)

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Force refresh of basis data with slight variation"""
    try:
        data = get_basis_data()
        # Add slight random variation to simulate real-time
        data['cme_front']['basis_pct'] = round(0.10 + random.random() * 0.3, 2)
        data['cme_second']['basis_pct'] = round(0.30 + random.random() * 0.4, 2)
        data['score'] = 70 + int(random.random() * 20)
        return jsonify({'status': 'refreshed', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# HELPER: Save static fallback data
# ============================================================

def save_static_data():
    """Save current data to static JSON file for fallback"""
    try:
        data = get_basis_data()
        os.makedirs('data/nodes', exist_ok=True)
        with open('data/nodes/btc_basis.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved static fallback data to data/nodes/btc_basis.json")
        return True
    except Exception as e:
        print(f"❌ Error saving static data: {e}")
        return False

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 BTC Basis Backend Server")
    print("=" * 60)
    print(f"📍 Server: http://localhost:5000")
    print(f"📊 API: http://localhost:5000/api/btc-basis")
    print(f"📄 Dashboard: http://localhost:5000")
    print("=" * 60)
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    # Save initial static data for fallback
    save_static_data()
    
    # Start the Flask server
    app.run(debug=True, host='0.0.0.0', port=5000)