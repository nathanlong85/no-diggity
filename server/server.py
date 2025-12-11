"""
WebSocket server for No Diggity remote processing.

This server receives frames from the client, processes them with ML models,
and returns detection results.
"""

import asyncio
import sys
import time
from pathlib import Path

import websockets

# Add shared module to path
sys.path.append(str(Path(__file__).parent.parent))

from shared.protocol import (
    DetectionMessage,
    ErrorMessage,
    FrameMessage,
    MessageType,
    deserialize_message,
    serialize_message,
)

# Import server config
try:
    from config import SERVER_CONFIG
except ImportError:
    # Default config if config.py doesn't exist yet
    SERVER_CONFIG = {
        'host': '0.0.0.0',
        'port': 8765,
        'model_preference': 'auto',
    }


class DetectionServer:
    """WebSocket server for processing detection frames"""

    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.stats = {
            'frames_processed': 0,
            'total_processing_time': 0.0,
            'errors': 0,
        }

    async def initialize_model(self):
        """Initialize ML model (placeholder for now)"""
        print('🤖 Initializing ML model...')
        # TODO: Phase 2 - Load actual model
        print('⚠️  Using FAKE detections for Phase 1 testing')
        self.model = 'fake_model'
        print('✓ Model ready')

    async def process_frame(self, frame, frame_id: int) -> dict:
        """
        Process a single frame and return detection results.

        Args:
            frame: OpenCV image (numpy array)
            frame_id: Frame sequence number

        Returns:
            Detection message dictionary
        """
        start_time = time.time()

        # TODO: Phase 2 - Replace with actual model inference
        # For now, return fake detections
        await asyncio.sleep(0.05)  # Simulate processing time

        # Fake detection: alternating elevated/not elevated
        elevated = (frame_id % 3) == 0
        boxes = []

        if elevated:
            # Fake bounding box
            boxes.append(
                {
                    'x1': 100,
                    'y1': 150,
                    'x2': 300,
                    'y2': 350,
                    'confidence': 0.85,
                    'class_id': 12,  # Dog class
                    'class_name': 'dog',
                }
            )

        processing_time = time.time() - start_time

        return DetectionMessage.create(frame_id, elevated, boxes, processing_time)

    async def handle_frame_message(self, message: dict) -> dict:
        """Handle incoming frame message"""
        try:
            # Decode frame
            frame, frame_id, timestamp = FrameMessage.decode(message)

            # Log reception
            latency = time.time() - timestamp
            print(
                f'📸 Received frame {frame_id} '
                f'(shape: {frame.shape}, latency: {latency * 1000:.1f}ms)'
            )

            # Process frame
            detection = await self.process_frame(frame, frame_id)

            # Update stats
            self.stats['frames_processed'] += 1
            self.stats['total_processing_time'] += detection['processing_time']

            # Log result
            avg_time = (
                self.stats['total_processing_time'] / self.stats['frames_processed']
            )
            status = '🚨 ELEVATED' if detection['elevated'] else '✓ Floor'
            print(
                f'   → {status} | '
                f'Processing: {detection["processing_time"] * 1000:.1f}ms '
                f'(avg: {avg_time * 1000:.1f}ms)'
            )

            return detection

        except Exception as e:
            print(f'❌ Error processing frame: {e}')
            self.stats['errors'] += 1
            return ErrorMessage.create(
                'processing_error', str(e), message.get('frame_id')
            )

    async def handle_client(self, websocket, path):
        """Handle a single client connection"""
        client_addr = websocket.remote_address
        print(f'\n🔌 Client connected: {client_addr}')

        try:
            async for message_str in websocket:
                # Deserialize message
                message = deserialize_message(message_str)

                # Route message by type
                if message['type'] == MessageType.FRAME:
                    response = await self.handle_frame_message(message)
                    await websocket.send(serialize_message(response))

                elif message['type'] == MessageType.PING:
                    # Respond to ping
                    from shared.protocol import PingPongMessage

                    pong = PingPongMessage.create_pong(message['timestamp'])
                    await websocket.send(serialize_message(pong))

                else:
                    print(f'⚠️  Unknown message type: {message["type"]}')

        except websockets.exceptions.ConnectionClosed:
            print(f'🔌 Client disconnected: {client_addr}')
        except Exception as e:
            print(f'❌ Error handling client: {e}')
        finally:
            print(f'\n📊 Session stats:')
            print(f'   Frames processed: {self.stats["frames_processed"]}')
            if self.stats['frames_processed'] > 0:
                avg_fps = 1.0 / (
                    self.stats['total_processing_time'] / self.stats['frames_processed']
                )
                print(f'   Average processing FPS: {avg_fps:.1f}')
            print(f'   Errors: {self.stats["errors"]}')

    async def start(self):
        """Start the WebSocket server"""
        await self.initialize_model()

        host = self.config['host']
        port = self.config['port']

        print(f'\n🚀 Starting detection server...')
        print(f'   Host: {host}')
        print(f'   Port: {port}')
        print(f'   Model: {self.config["model_preference"]}')

        async with websockets.serve(self.handle_client, host, port):
            print(f'\n✓ Server running on ws://{host}:{port}')
            print('   Waiting for connections...\n')
            await asyncio.Future()  # Run forever


def main():
    """Main entry point"""
    server = DetectionServer(SERVER_CONFIG)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print('\n\n👋 Server shutting down...')


if __name__ == '__main__':
    main()
