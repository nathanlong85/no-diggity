"""
WebSocket client for No Diggity camera.

This client captures frames from the camera and sends them to the server
for processing, then receives detection results and checks zones.
"""

import asyncio
import sys
import time
from pathlib import Path
from threading import Thread

import cv2
import websockets

# Add shared module to path
sys.path.append(str(Path(__file__).parent.parent))

from shared.protocol import (
    FrameMessage,
    MessageType,
    deserialize_message,
    serialize_message,
)

# Import client config and detector
try:
    from config import CLIENT_CONFIG
    from detector import analyze_detections
    from alerts import AlertManager

    # Try to import web dashboard
    try:
        from web_server import (
            add_alert,
            set_server_status,
            set_zones,
            update_stats,
            update_video_frame,
        )

        DASHBOARD_AVAILABLE = True
    except ImportError:
        DASHBOARD_AVAILABLE = False
        print('ℹ️  Web dashboard not available')

        # Mock dashboard functions
        def update_stats(stats):
            pass

        def add_alert(alert_data):
            pass

        def set_server_status(status):
            pass

        def set_zones(zones):
            pass

        def update_video_frame(frame, detections=None, zones=None):
            pass

except ImportError:
    # Default config if config.py doesn't exist yet
    CLIENT_CONFIG = {
        'server_host': 'localhost',
        'server_port': 8765,
        'camera_index': 0,
        'camera_resolution': (640, 480),
        'frame_skip': 5,
        'jpeg_quality': 70,
        'min_elevated_size_ratio': 0.3,
        'zones': {},
    }

    # Mock analyze_detections if detector not available
    def analyze_detections(detections, frame_height, zones, min_size_ratio):
        return {
            'elevated': len(detections) > 0,
            'triggered_zones': set(),
            'analyses': [],
        }

    # Mock AlertManager if alerts not available
    class AlertManager:
        def __init__(self, config):
            pass

        def trigger_alert(self, alert_data):
            print('⚠️  Alert system not configured')

        def cleanup(self):
            pass

    # Mock dashboard functions
    def update_stats(stats):
        pass

    def add_alert(alert_data):
        pass

    def set_server_status(status):
        pass

    def set_zones(zones):
        pass

    def update_video_frame(frame, detections=None, zones=None):
        pass

    DASHBOARD_AVAILABLE = False


class DetectionClient:
    """WebSocket client for sending frames and receiving detections"""

    def __init__(self, config: dict):
        self.config = config
        self.camera = None
        self.frame_id = 0
        self.websocket = None
        self.running = False
        self.frame_height = 480  # Will be set on camera init
        self.current_frame = None  # Store current frame for snapshots

        # Statistics
        self.stats = {
            'frames_sent': 0,
            'frames_captured': 0,
            'detections_received': 0,
            'elevated_count': 0,
            'alerts_triggered': 0,
        }

        # Detection history for consecutive tracking
        self.detection_history = []  # [(frame_id, elevated), ...]
        self.max_history = 10

        # Performance tracking
        self.perf_stats = {
            'last_fps_time': time.time(),
            'fps_frame_count': 0,
            'current_fps': 0,
            'send_times': [],  # Track send times for average
            'latencies': [],  # Track round-trip latencies
            'frame_send_times': {},  # {frame_id: send_timestamp}
        }
        self.perf_log_interval = 5.0  # Log stats every 5 seconds

        # Alert manager
        alert_config = config.get('alerts', {})
        self.alert_manager = AlertManager(alert_config)

        # Dashboard integration
        self.dashboard_enabled = (
            config.get('enable_dashboard', True) and DASHBOARD_AVAILABLE
        )
        self.start_time = time.time()

    def init_camera(self):
        """Initialize camera"""
        print('📷 Initializing camera...')
        self.camera = cv2.VideoCapture(self.config['camera_index'])

        # Set resolution
        width, height = self.config['camera_resolution']
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not self.camera.isOpened():
            raise RuntimeError('Failed to open camera')

        # Test read
        ret, frame = self.camera.read()
        if not ret:
            raise RuntimeError('Failed to read from camera')

        # Store frame dimensions
        self.frame_height = frame.shape[0]

        print(f'✓ Camera initialized: {frame.shape[1]}x{frame.shape[0]}')

        # Print enabled zones
        enabled_zones = [
            z['name'] for z in self.config['zones'].values() if z['enabled']
        ]
        if enabled_zones:
            print(f'✓ Active zones: {", ".join(enabled_zones)}')
        else:
            print('⚠️  No zones enabled - all detections will be considered floor')

        # Send zones to dashboard
        if self.dashboard_enabled:
            set_zones(self.config['zones'])
            # Send initial stats
            self.update_dashboard_stats()

        return frame.shape[:2]

    async def connect(self):
        """Connect to the WebSocket server"""
        uri = f'ws://{self.config["server_host"]}:{self.config["server_port"]}'
        print(f'\n🔌 Connecting to server: {uri}')

        try:
            self.websocket = await websockets.connect(uri)
            print('✓ Connected to server')
            if self.dashboard_enabled:
                set_server_status('connected')
            return True
        except Exception as e:
            print(f'❌ Connection failed: {e}')
            if self.dashboard_enabled:
                set_server_status('disconnected')
            return False

    async def send_frame(self, frame):
        """Send a frame to the server"""
        if not self.websocket:
            return

        self.frame_id += 1
        send_start = time.time()

        # Create frame message
        message = FrameMessage.create(frame, self.frame_id, self.config['jpeg_quality'])

        # Send to server
        await self.websocket.send(serialize_message(message))

        send_time = time.time() - send_start
        self.stats['frames_sent'] += 1

        # Track performance
        self.perf_stats['send_times'].append(send_time)
        self.perf_stats['frame_send_times'][self.frame_id] = time.time()

        # Keep only last 100 measurements
        if len(self.perf_stats['send_times']) > 100:
            self.perf_stats['send_times'].pop(0)

        return self.frame_id

    async def receive_detections(self):
        """Receive detection results from server"""
        if not self.websocket:
            return

        try:
            async for message_str in self.websocket:
                message = deserialize_message(message_str)

                if message['type'] == MessageType.DETECTION:
                    await self.handle_detection(message)

                elif message['type'] == MessageType.ERROR:
                    print(f'❌ Server error: {message["message"]}')

        except websockets.exceptions.ConnectionClosed:
            print('🔌 Connection to server closed')
            self.running = False

    async def handle_detection(self, detection: dict):
        """Process received detection result"""
        frame_id = detection['frame_id']
        boxes = detection['boxes']
        processing_time = detection.get('processing_time', 0)

        self.stats['detections_received'] += 1

        # Calculate latency (round-trip time)
        if frame_id in self.perf_stats['frame_send_times']:
            latency = time.time() - self.perf_stats['frame_send_times'][frame_id]
            self.perf_stats['latencies'].append(latency)

            # Keep only last 100 measurements
            if len(self.perf_stats['latencies']) > 100:
                self.perf_stats['latencies'].pop(0)

            # Clean up old send times
            del self.perf_stats['frame_send_times'][frame_id]

        # Analyze detections with zone checking
        analysis = analyze_detections(
            boxes,
            self.frame_height,
            self.config['zones'],
            self.config.get('min_elevated_size_ratio', 0.3),
        )

        elevated = analysis['elevated']
        triggered_zones = analysis['triggered_zones']

        # Add to history
        self.detection_history.append((frame_id, elevated))
        if len(self.detection_history) > self.max_history:
            self.detection_history.pop(0)

        # Check for consecutive elevated detections
        consecutive = self.check_consecutive_elevated()

        # Build status message
        if elevated:
            zone_names = [self.config['zones'][z]['name'] for z in triggered_zones]
            status = f'🚨 ELEVATED ({", ".join(zone_names)})'
            self.stats['elevated_count'] += 1
        else:
            status = '✓ Floor'

        # Calculate latency for display
        latency_ms = (
            self.perf_stats['latencies'][-1] * 1000
            if self.perf_stats['latencies']
            else 0
        )

        print(
            f'📡 Frame {frame_id}: {status} '
            f'| Dogs: {len(boxes)} '
            f'| Server: {processing_time * 1000:.0f}ms '
            f'| Latency: {latency_ms:.0f}ms '
            f'| Consecutive: {consecutive}'
        )

        # Trigger alert if consecutive
        if consecutive:
            self.trigger_alert(triggered_zones, boxes)

        # Update dashboard video feed
        if self.dashboard_enabled and self.current_frame is not None:
            update_video_frame(self.current_frame, boxes, self.config['zones'])

    def check_consecutive_elevated(self) -> bool:
        """
        Check if any 2 consecutive frames show elevated dog.
        Allows 1 frame gap (within 2 frame IDs).
        """
        if len(self.detection_history) < 2:
            return False

        # Sort by frame_id (handle out-of-order results)
        sorted_history = sorted(self.detection_history, key=lambda x: x[0])

        for i in range(len(sorted_history) - 1):
            frame_a, elevated_a = sorted_history[i]
            frame_b, elevated_b = sorted_history[i + 1]

            # Within 2 frame IDs AND both elevated
            if elevated_a and elevated_b and (frame_b - frame_a) <= 2:
                return True

        return False

    def trigger_alert(self, triggered_zones: set, detections: list):
        """Trigger alert for consecutive elevated detections"""
        zone_names = [self.config['zones'][z]['name'] for z in triggered_zones]

        print('\n' + '=' * 60)
        print('🚨 ALERT: Dog on counter detected! (consecutive)')
        if zone_names:
            print(f'   Location: {", ".join(zone_names)}')
        print('=' * 60 + '\n')

        self.stats['alerts_triggered'] += 1

        # Prepare alert data
        alert_data = {
            'frame_id': self.frame_id,
            'triggered_zones': triggered_zones,
            'zones': zone_names,
            'detections': detections,
            'frame': self.current_frame,
            'zone_polygons': {
                z: self.config['zones'][z]['polygon'] for z in triggered_zones
            },
        }

        # Trigger alert manager
        self.alert_manager.trigger_alert(alert_data)

        # Update dashboard
        if self.dashboard_enabled:
            add_alert(alert_data)

    def log_performance_stats(self):
        """Log performance statistics"""
        if not self.perf_stats['send_times']:
            return

        # Calculate averages
        avg_send = sum(self.perf_stats['send_times']) / len(
            self.perf_stats['send_times']
        )

        if self.perf_stats['latencies']:
            avg_latency = sum(self.perf_stats['latencies']) / len(
                self.perf_stats['latencies']
            )
            min_latency = min(self.perf_stats['latencies'])
            max_latency = max(self.perf_stats['latencies'])
        else:
            avg_latency = min_latency = max_latency = 0

        # Calculate current FPS
        current_fps = self.perf_stats['current_fps']

        print('\n' + '─' * 60)
        print('⚡ PERFORMANCE STATS:')
        print(f'   Camera FPS: {current_fps:.1f}')
        print(f'   Avg Send Time: {avg_send * 1000:.1f}ms')
        print(
            f'   Avg Latency: {avg_latency * 1000:.0f}ms '
            f'(min: {min_latency * 1000:.0f}ms, max: {max_latency * 1000:.0f}ms)'
        )
        print(
            f'   Frames Sent: {self.stats["frames_sent"]} | '
            f'Received: {self.stats["detections_received"]}'
        )
        print(
            f'   Elevated: {self.stats["elevated_count"]} | '
            f'Alerts: {self.stats["alerts_triggered"]}'
        )
        print('─' * 60 + '\n')

        # Update dashboard
        if self.dashboard_enabled:
            self.update_dashboard_stats()

    def update_dashboard_stats(self):
        """Update dashboard with current stats"""
        avg_latency_ms = 0
        if self.perf_stats['latencies']:
            avg_latency_ms = (
                sum(self.perf_stats['latencies']) / len(self.perf_stats['latencies'])
            ) * 1000

        uptime = time.time() - self.start_time

        update_stats(
            {
                'frames_captured': self.stats['frames_captured'],
                'frames_sent': self.stats['frames_sent'],
                'detections_received': self.stats['detections_received'],
                'elevated_count': self.stats['elevated_count'],
                'alerts_triggered': self.stats['alerts_triggered'],
                'current_fps': self.perf_stats['current_fps'],
                'avg_latency_ms': avg_latency_ms,
                'uptime_seconds': uptime,
            }
        )

    async def capture_loop(self):
        """Main loop for capturing and sending frames"""
        print('\n📸 Starting frame capture...')
        frame_count = 0
        last_perf_log = time.time()
        last_dashboard_update = time.time()

        while self.running:
            ret, frame = self.camera.read()
            if not ret:
                print('⚠️  Failed to read frame')
                await asyncio.sleep(0.1)
                continue

            frame_count += 1
            self.stats['frames_captured'] += 1
            self.perf_stats['fps_frame_count'] += 1

            # Store current frame for snapshots
            self.current_frame = frame

            # Calculate FPS every second
            elapsed = time.time() - self.perf_stats['last_fps_time']
            if elapsed >= 1.0:
                self.perf_stats['current_fps'] = (
                    self.perf_stats['fps_frame_count'] / elapsed
                )
                self.perf_stats['fps_frame_count'] = 0
                self.perf_stats['last_fps_time'] = time.time()

            # Log performance stats periodically
            if time.time() - last_perf_log >= self.perf_log_interval:
                self.log_performance_stats()
                last_perf_log = time.time()

            # Update dashboard more frequently (every 2 seconds)
            if self.dashboard_enabled and time.time() - last_dashboard_update >= 2.0:
                self.update_dashboard_stats()
                last_dashboard_update = time.time()

            # Only send every Nth frame
            if frame_count % self.config['frame_skip'] == 0:
                try:
                    await self.send_frame(frame)
                except Exception as e:
                    print(f'❌ Failed to send frame: {e}')
                    break

            # Small delay to not overwhelm the camera
            await asyncio.sleep(0.01)

        # Clean up alert manager
        self.alert_manager.cleanup()

    async def run(self):
        """Main run loop"""
        # Initialize camera
        self.init_camera()

        # Connect to server
        if not await self.connect():
            print('❌ Failed to connect to server')
            return

        self.running = True

        # Run capture and receive loops concurrently
        try:
            await asyncio.gather(self.capture_loop(), self.receive_detections())
        except KeyboardInterrupt:
            print('\n👋 Shutting down...')
        finally:
            self.running = False
            if self.camera:
                self.camera.release()
            if self.websocket:
                await self.websocket.close()

            # Print final stats
            print(f'\n📊 Final Session Statistics:')
            print(f'   Frames captured: {self.stats["frames_captured"]}')
            print(f'   Frames sent: {self.stats["frames_sent"]}')
            print(f'   Detections received: {self.stats["detections_received"]}')
            print(f'   Elevated detections: {self.stats["elevated_count"]}')
            print(f'   Alerts triggered: {self.stats["alerts_triggered"]}')

            if self.perf_stats['latencies']:
                avg_latency = sum(self.perf_stats['latencies']) / len(
                    self.perf_stats['latencies']
                )
                print(f'   Average latency: {avg_latency * 1000:.0f}ms')

            # Update dashboard
            if self.dashboard_enabled:
                self.update_dashboard_stats()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='No Diggity Detection Client')
    parser.add_argument(
        '--no-dashboard', action='store_true', help='Disable web dashboard'
    )
    parser.add_argument(
        '--dashboard-only',
        action='store_true',
        help='Run dashboard only (no detection)',
    )
    parser.add_argument(
        '--dashboard-port', type=int, default=5000, help='Dashboard port'
    )
    args = parser.parse_args()

    # Run dashboard only
    if args.dashboard_only:
        if DASHBOARD_AVAILABLE:
            from web_server import run_dashboard

            print('🌐 Starting dashboard server...')
            run_dashboard(port=args.dashboard_port)
        else:
            print('❌ Dashboard not available. Install Flask and flask-socketio:')
            print('   pip install flask flask-socketio')
        return

    # Override dashboard setting
    if args.no_dashboard:
        CLIENT_CONFIG['enable_dashboard'] = False

    # Start dashboard in background thread if enabled
    if CLIENT_CONFIG.get('enable_dashboard', True) and DASHBOARD_AVAILABLE:
        from web_server import run_dashboard

        dashboard_thread = Thread(
            target=run_dashboard, kwargs={'port': args.dashboard_port}, daemon=True
        )
        dashboard_thread.start()
        print(f'🌐 Dashboard started on http://localhost:{args.dashboard_port}')
        time.sleep(1)  # Give dashboard time to start

    # Start detection client
    client = DetectionClient(CLIENT_CONFIG)
    asyncio.run(client.run())


if __name__ == '__main__':
    main()
