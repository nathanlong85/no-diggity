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

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, send_from_directory
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
    'current_frame': None,  # Current annotated frame for live feed
    'zones': {},  # Zone definitions
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

    # Debug: Print stats update (can be removed in production)
    # print(f'📊 Dashboard stats updated: FPS={stats.get("current_fps", 0):.1f}, Alerts={stats.get("alerts_triggered", 0)}')


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


def update_video_frame(frame: np.ndarray, detections: list = None, zones: dict = None):
    """Update the current video frame with annotations"""
    if frame is None:
        return

    # Create annotated frame
    annotated = frame.copy()

    # Draw zones if provided
    if zones:
        overlay = annotated.copy()
        for zone_id, zone in zones.items():
            if not zone.get('enabled', True):
                continue

            polygon = np.array(zone['polygon'], np.int32)
            color = (0, 255, 0)  # Green for zones

            # Fill polygon with transparency
            cv2.fillPoly(overlay, [polygon], color)

            # Draw outline
            cv2.polylines(annotated, [polygon], True, color, 2)

            # Draw zone name
            center = polygon.mean(axis=0).astype(int)
            cv2.putText(
                annotated,
                zone.get('name', zone_id),
                tuple(center),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        # Blend overlay for transparency
        cv2.addWeighted(overlay, 0.3, annotated, 0.7, 0, annotated)

    # Draw detection boxes if provided
    if detections:
        for det in detections:
            x1, y1, x2, y2 = (
                int(det['x1']),
                int(det['y1']),
                int(det['x2']),
                int(det['y2']),
            )
            conf = det.get('confidence', 0)

            # Draw box (yellow for detections)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 255), 2)

            # Draw label with background
            label = f'{det.get("class_name", "dog")} {conf:.2f}'
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                (0, 255, 255),
                -1,
            )
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                2,
            )

    # Add timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cv2.putText(
        annotated,
        timestamp,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    # Add FPS counter
    fps = dashboard_state['stats'].get('current_fps', 0)
    cv2.putText(
        annotated,
        f'FPS: {fps:.1f}',
        (10, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    with state_lock:
        dashboard_state['current_frame'] = annotated


def set_zones(zones: dict):
    """Update zone definitions"""
    with state_lock:
        dashboard_state['zones'] = zones


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
        # Exclude current_frame as it's not JSON serializable
        state_to_send = {
            'stats': dashboard_state['stats'],
            'recent_alerts': dashboard_state['recent_alerts'],
            'current_detections': dashboard_state['current_detections'],
            'zones': dashboard_state['zones'],
            'connected_clients': dashboard_state['connected_clients'],
            'server_status': dashboard_state['server_status'],
            'last_update': dashboard_state['last_update'],
        }
        return jsonify(state_to_send)


def generate_video_stream():
    """Generate MJPEG stream from current frames"""
    while True:
        with state_lock:
            frame = dashboard_state.get('current_frame')

        if frame is not None:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
                )

        # Small delay to prevent overwhelming the client
        time.sleep(0.033)  # ~30 FPS max


@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(
        generate_video_stream(), mimetype='multipart/x-mixed-replace; boundary=frame'
    )


# SocketIO events
@socketio.on('connect')
def handle_connect(auth=None):
    """Handle client connection"""
    with state_lock:
        dashboard_state['connected_clients'] += 1

    # Send initial state (excluding current_frame which isn't JSON serializable)
    state_to_send = {
        'stats': dashboard_state['stats'],
        'recent_alerts': dashboard_state['recent_alerts'],
        'current_detections': dashboard_state['current_detections'],
        'zones': dashboard_state['zones'],
        'server_status': dashboard_state['server_status'],
    }

    socketio.emit('initial_state', state_to_send)
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
