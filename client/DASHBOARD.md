# Web Dashboard Guide

The No Diggity web dashboard provides real-time monitoring and visualization of your detection system.

## Features

✨ **Real-time Statistics**
- Camera FPS and frame processing
- Detection counts and alerts
- System uptime
- Average latency tracking

📸 **Snapshot Gallery**
- View recent detection snapshots
- Click to view full-size
- Automatic updates when new alerts trigger

🚨 **Alert History**
- Live feed of recent alerts
- Shows zones, timestamps, and detection counts
- Highlights critical alerts

📊 **Live Updates**
- WebSocket-based real-time updates
- No page refresh needed
- Connection status indicator

## Installation

### Install Dependencies

```bash
pip install flask flask-socketio
```

Or install all dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Option 1: Automatic Start (Recommended)

The dashboard starts automatically with the client:

```bash
cd client
python client.py
```

Then open your browser to:
```
http://localhost:5000
```

### Option 2: Dashboard Only

Run just the dashboard without detection:

```bash
cd client
python client.py --dashboard-only
```

### Option 3: Manual Control

**Disable dashboard:**
```bash
python client.py --no-dashboard
```

**Custom port:**
```bash
python client.py --dashboard-port 8080
```

## Configuration

Edit `client/config.py`:

```python
CLIENT_CONFIG = {
    'enable_dashboard': True,  # Enable/disable dashboard
    # ... other settings
}
```

## Dashboard Interface

### Header
- **System Status**: Green = connected, Red = disconnected
- **Connection Indicator**: Shows real-time connection status

### Performance Stats Card
- **Camera FPS**: Current frame rate from camera
- **Avg Latency**: Round-trip time (client → server → client)
- **Frames Sent**: Total frames sent to server
- **Detections Received**: Total detection responses

### Alert Stats Card
- **Total Alerts**: Big number showing all triggered alerts
- **Elevated Detections**: Count of dogs detected in zones

### Uptime Card
- Shows system running time in HH:MM:SS format

### Recent Alerts Section
- Live feed of last 10 alerts
- Shows zone names, timestamps, detection counts
- Auto-updates when new alerts occur

### Snapshot Gallery
- Grid of recent detection snapshots
- Shows up to 20 most recent images
- Click any image to view full-size
- Overlay shows zone and detection count
- Auto-updates every 30 seconds

## Network Access

### Access from Other Devices

By default, the dashboard binds to `0.0.0.0`, making it accessible from other devices on your network.

**From your phone/tablet:**
1. Find your computer's IP address: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
2. Open browser to: `http://YOUR_IP:5000`

Example: `http://192.168.1.100:5000`

### Security Note

The dashboard has no authentication by default. For production use:

1. **Use a firewall** to limit access
2. **Add authentication** (see Advanced section below)
3. **Use HTTPS** if exposing to the internet

## File Structure

```
client/
├── web_server.py           # Flask server and API
├── templates/
│   └── dashboard.html      # Dashboard UI
├── snapshots/              # Stored detection images
│   ├── *.jpg              # Snapshot images
│   └── *.json             # Snapshot metadata
└── alerts.log             # Alert log file
```

## API Endpoints

The dashboard exposes several API endpoints:

### GET `/api/stats`
Returns current statistics:
```json
{
  "frames_captured": 1234,
  "frames_sent": 246,
  "detections_received": 246,
  "elevated_count": 12,
  "alerts_triggered": 3,
  "current_fps": 15.2,
  "avg_latency_ms": 85,
  "uptime_seconds": 3600
}
```

### GET `/api/alerts`
Returns recent alerts (last 50):
```json
[
  {
    "timestamp": "2024-12-23T14:30:52.123",
    "zones": ["Kitchen Counter"],
    "detection_count": 1,
    "frame_id": 42,
    "snapshot": "20241223_143052_123_counter.jpg"
  }
]
```

### GET `/api/snapshots`
Returns list of snapshots:
```json
[
  {
    "filename": "20241223_143052_123_counter.jpg",
    "timestamp": "20241223_143052_123",
    "zones": ["counter"],
    "detection_count": 1,
    "size": 45678
  }
]
```

### GET `/snapshots/<filename>`
Serves snapshot images directly.

### WebSocket Events

The dashboard uses Socket.IO for real-time updates:

**Client → Server:**
- `connect` - Client connected
- `disconnect` - Client disconnected

**Server → Client:**
- `initial_state` - Full state on connection
- `stats_update` - New statistics
- `new_alert` - New alert triggered
- `status_update` - Server status changed

## Troubleshooting

### Dashboard Not Starting

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
pip install flask flask-socketio
```

### Can't Access from Other Devices

**Check:**
1. Firewall allows port 5000
2. Computer and device on same network
3. Using correct IP address
4. Dashboard is running

**Test locally first:**
```bash
curl http://localhost:5000/api/stats
```

### Snapshots Not Showing

**Check:**
1. Snapshot handler is enabled in `config.py`
2. `snapshots/` directory exists and has images
3. Browser console for errors (F12)

### Live Updates Not Working

**Check:**
1. Browser console for WebSocket errors
2. Try refreshing the page
3. Check if client is running and connected

### High CPU Usage

The dashboard is lightweight, but if experiencing issues:

1. **Reduce snapshot frequency** - Snapshots use most resources
2. **Limit snapshot display** - Dashboard shows max 20
3. **Increase alert cooldown** - Reduces update frequency

## Advanced Usage

### Custom Styling

Edit `client/templates/dashboard.html` to customize the look:

```html
<style>
    /* Change colors */
    body {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    h1 {
        color: #667eea;
    }
</style>
```

### Add Authentication

Add basic authentication to `web_server.py`:

```python
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("your_password_here")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# Add @auth.login_required to routes
@app.route('/')
@auth.login_required
def index():
    return render_template('dashboard.html')
```

Install: `pip install flask-httpauth`

### Reverse Proxy (Nginx)

For production deployment:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Mobile Responsive

The dashboard is already mobile-responsive! Open on your phone for monitoring on-the-go.

## Performance

**Resource Usage:**
- **Memory**: ~50MB (Flask + SocketIO)
- **CPU**: <5% (idle), ~10% (active updates)
- **Network**: Minimal (~1KB/s for stats updates)

**Scalability:**
- Supports multiple concurrent viewers
- Real-time updates via WebSocket
- Tested with 10+ simultaneous connections

## Integration with External Tools

### Prometheus Metrics

Export metrics for monitoring:

```python
# Add to web_server.py
@app.route('/metrics')
def metrics():
    return f"""
# HELP no_diggity_alerts_total Total alerts triggered
# TYPE no_diggity_alerts_total counter
no_diggity_alerts_total {dashboard_state['stats']['alerts_triggered']}

# HELP no_diggity_fps Current camera FPS
# TYPE no_diggity_fps gauge
no_diggity_fps {dashboard_state['stats']['current_fps']}
"""
```

### Webhook Notifications

Add webhook support to `web_server.py`:

```python
import requests

@socketio.on('new_alert')
def send_webhook(alert):
    webhook_url = "https://your-webhook-url.com"
    requests.post(webhook_url, json=alert)
```

## Tips & Tricks

1. **Bookmark the URL** - Add to your phone's home screen for quick access
2. **Multiple Tabs** - Open dashboard on multiple devices simultaneously
3. **Screenshot History** - Use browser's back button to review past snapshots
4. **Console Logging** - Press F12 to see debug info in browser console
5. **Auto-Refresh** - Dashboard automatically updates, no need to refresh

## Support

For issues, check:
1. Console output when running `client.py`
2. Browser console (F12) for JavaScript errors
3. `alerts.log` for alert history
4. GitHub issues for known problems
