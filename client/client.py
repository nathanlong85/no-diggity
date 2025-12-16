"""
WebSocket client for No Diggity camera.

This client captures frames from the camera and sends them to the server
for processing, then receives detection results.
"""

import asyncio
import sys
import time
from pathlib import Path

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

# Import client config
try:
    from config import CLIENT_CONFIG
except ImportError:
    # Default config if config.py doesn't exist yet
    CLIENT_CONFIG = {
        'server_host': 'localhost',
        'server_port': 8765,
        'camera_index': 0,
        'camera_resolution': (640, 480),
        'frame_skip': 5,
        'jpeg_quality': 70,
    }


class DetectionClient:
    """WebSocket client for sending frames and receiving detections"""

    def __init__(self, config: dict):
        self.config = config
        self.camera = None
        self.frame_id = 0
        self.websocket = None
        self.running = False

        # Statistics
        self.stats = {
            'frames_sent': 0,
            'frames_captured': 0,
            'detections_received': 0,
            'elevated_count': 0,
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

        print(f'✓ Camera initialized: {frame.shape[1]}x{frame.shape[0]}')
        return frame.shape[:2]

    async def connect(self):
        """Connect to the WebSocket server"""
        uri = f'ws://{self.config["server_host"]}:{self.config["server_port"]}'
        print(f'\n🔌 Connecting to server: {uri}')

        try:
            self.websocket = await websockets.connect(uri)
            print('✓ Connected to server')
            return True
        except Exception as e:
            print(f'❌ Connection failed: {e}')
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
        elevated = detection['elevated']
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

        # Add to history
        self.detection_history.append((frame_id, elevated))
        if len(self.detection_history) > self.max_history:
            self.detection_history.pop(0)

        # Check for consecutive elevated detections
        consecutive = self.check_consecutive_elevated()

        # Log result with performance info
        status = '🚨 ELEVATED' if elevated else '✓ Floor'
        latency = (
            self.perf_stats['latencies'][-1] if self.perf_stats['latencies'] else 0
        )

        print(
            f'📡 Frame {frame_id}: {status} '
            f'| Dogs: {len(boxes)} '
            f'| Server: {processing_time * 1000:.0f}ms '
            f'| Latency: {latency * 1000:.0f}ms '
            f'| Consecutive: {consecutive}'
        )

        if elevated:
            self.stats['elevated_count'] += 1

        # Trigger alert if consecutive
        if consecutive:
            self.trigger_alert()

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

    def trigger_alert(self):
        """Trigger alert for consecutive elevated detections"""
        print('\n' + '=' * 50)
        print('🚨 ALERT: Dog on counter detected! (consecutive)')
        print('=' * 50 + '\n')
        # TODO: Add ultrasonic speaker trigger here

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
            f'   Avg Latency: {avg_latency * 1000:.0f}ms (min: {min_latency * 1000:.0f}ms, max: {max_latency * 1000:.0f}ms)'
        )
        print(
            f'   Frames Sent: {self.stats["frames_sent"]} | Received: {self.stats["detections_received"]}'
        )
        print(f'   Elevated Detections: {self.stats["elevated_count"]}')
        print('─' * 60 + '\n')

    async def capture_loop(self):
        """Main loop for capturing and sending frames"""
        print('\n📸 Starting frame capture...')
        frame_count = 0
        last_perf_log = time.time()

        while self.running:
            ret, frame = self.camera.read()
            if not ret:
                print('⚠️  Failed to read frame')
                await asyncio.sleep(0.1)
                continue

            frame_count += 1
            self.stats['frames_captured'] += 1
            self.perf_stats['fps_frame_count'] += 1

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

            # Only send every Nth frame
            if frame_count % self.config['frame_skip'] == 0:
                try:
                    await self.send_frame(frame)
                except Exception as e:
                    print(f'❌ Failed to send frame: {e}')
                    break

            # Small delay to not overwhelm the camera
            await asyncio.sleep(0.01)

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

            if self.perf_stats['latencies']:
                avg_latency = sum(self.perf_stats['latencies']) / len(
                    self.perf_stats['latencies']
                )
                print(f'   Average latency: {avg_latency * 1000:.0f}ms')


def main():
    """Main entry point"""
    client = DetectionClient(CLIENT_CONFIG)
    asyncio.run(client.run())


if __name__ == '__main__':
    main()
