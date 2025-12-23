"""
Web Dashboard for No Diggity.

Provides real-time monitoring, snapshot gallery, and statistics.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'no-diggity-secret-key'
socketio = SocketIO(app, cors_allowed_origins='*')

# Shared state
dashboard_state = {
    'stats': {
        'frames_captured': 0,
        'frames_sent': 0,
        'detections_received': 0,
        'elevated_count': 0,
        'alerts_triggered': 0,
        'current_fps': 0,
        'avg_latency_ms': 0,
        'uptime_seconds': 0,
    },
    'recent_alerts': [],  # Last 50 alerts
    'current_detections': [],  # Current frame detections
    'connected_clients': 0,
    'server_status': 'disconnected',
    'last_update': time.time(),
}
state_lock = Lock()

# Configuration
SNAPSHOT_DIR = Path('snapshots')
ALERT_LOG_FILE = Path('alerts.log')
MAX_RECENT_ALERTS = 50


# State update functions (called by client.py)
def update_stats(stats: dict):
    """Update dashboard statistics"""
    with state_lock:
        dashboard_state['stats'].update(stats)
        dashboard_state['last_update'] = time.time()

    # Broadcast to connected clients
    socketio.emit('stats_update', dashboard_state['stats'])


def add_alert(alert_data: dict):
    """Add new alert to recent alerts"""
    alert_entry = {
        'timestamp': datetime.now().isoformat(),
        'zones': alert_data.get('zones', []),
        'detection_count': len(alert_data.get('detections', [])),
        'frame_id': alert_data.get('frame_id'),
        'snapshot': None,
    }

    # Find associated snapshot
    if 'frame_id' in alert_data:
        snapshots = sorted(SNAPSHOT_DIR.glob('*.jpg'), reverse=True)
        if snapshots:
            alert_entry['snapshot'] = snapshots[0].name

    with state_lock:
        dashboard_state['recent_alerts'].insert(0, alert_entry)
        if len(dashboard_state['recent_alerts']) > MAX_RECENT_ALERTS:
            dashboard_state['recent_alerts'].pop()

    # Broadcast to connected clients
    socketio.emit('new_alert', alert_entry)


def update_detections(detections: list):
    """Update current detections"""
    with state_lock:
        dashboard_state['current_detections'] = detections

    socketio.emit('detections_update', detections)


def set_server_status(status: str):
    """Update server connection status"""
    with state_lock:
        dashboard_state['server_status'] = status

    socketio.emit('status_update', {'status': status})


# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/stats')
def get_stats():
    """Get current statistics"""
    with state_lock:
        return jsonify(dashboard_state['stats'])


@app.route('/api/alerts')
def get_alerts():
    """Get recent alerts"""
    with state_lock:
        return jsonify(dashboard_state['recent_alerts'])


@app.route('/api/snapshots')
def get_snapshots():
    """Get list of snapshots"""
    if not SNAPSHOT_DIR.exists():
        return jsonify([])

    snapshots = []
    for img_file in sorted(SNAPSHOT_DIR.glob('*.jpg'), reverse=True)[:100]:
        # Load metadata if exists
        metadata_file = img_file.with_suffix('.json')
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)

        snapshots.append(
            {
                'filename': img_file.name,
                'timestamp': metadata.get('timestamp', ''),
                'zones': metadata.get('zones', []),
                'detection_count': metadata.get('detection_count', 0),
                'size': img_file.stat().st_size,
            }
        )

    return jsonify(snapshots)


@app.route('/snapshots/<path:filename>')
def serve_snapshot(filename):
    """Serve snapshot images"""
    return send_from_directory(SNAPSHOT_DIR, filename)


@app.route('/api/alert_log')
def get_alert_log():
    """Get recent alert log entries"""
    if not ALERT_LOG_FILE.exists():
        return jsonify([])

    # Read last 100 lines
    with open(ALERT_LOG_FILE) as f:
        lines = f.readlines()

    recent_lines = lines[-100:] if len(lines) > 100 else lines
    return jsonify(recent_lines)


@app.route('/api/state')
def get_state():
    """Get complete dashboard state"""
    with state_lock:
        return jsonify(dashboard_state)


# SocketIO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    with state_lock:
        dashboard_state['connected_clients'] += 1

    # Send initial state
    socketio.emit('initial_state', dashboard_state)
    print(
        f'📱 Dashboard client connected (total: {dashboard_state["connected_clients"]})'
    )


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    with state_lock:
        dashboard_state['connected_clients'] = max(
            0, dashboard_state['connected_clients'] - 1
        )

    print(
        f'📱 Dashboard client disconnected (total: {dashboard_state["connected_clients"]})'
    )


def run_dashboard(host='0.0.0.0', port=5000):
    """Run the dashboard server"""
    print(f'\n🌐 Starting web dashboard on http://{host}:{port}')
    print(f'   Open http://localhost:{port} in your browser')

    # Create snapshot directory if it doesn't exist
    SNAPSHOT_DIR.mkdir(exist_ok=True)

    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    run_dashboard()
