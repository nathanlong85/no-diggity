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

# Import server config and model loader
try:
    from config import SERVER_CONFIG
    from model_loader import load_model
except ImportError:
    print('❌ Error: Make sure config.py and model_loader.py exist in server/')
    sys.exit(1)


class DetectionServer:
    """WebSocket server for processing detection frames"""

    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.stats = {
            'frames_processed': 0,
            'total_processing_time': 0.0,
            'errors': 0,
            'dogs_detected': 0,
        }

    async def initialize_model(self):
        """Initialize ML model"""
        print('🤖 Initializing ML model...')

        # Load model based on config preference
        self.model = load_model(
            preference=self.config['model_preference'],
            confidence_threshold=self.config['confidence_threshold'],
        )

        print('✓ Model ready\n')

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

        # Run detection
        detections = self.model.detect(frame)

        # Check if any dogs detected
        elevated = len(detections) > 0  # For now, any detection is "elevated"
        # TODO: Phase 3 - Add polygon zone checking for proper elevated detection

        processing_time = time.time() - start_time

        if detections:
            self.stats['dogs_detected'] += 1

        return DetectionMessage.create(frame_id, elevated, detections, processing_time)

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
            avg_fps = 1.0 / avg_time if avg_time > 0 else 0

            num_dogs = len(detection['boxes'])
            status = f'🐕 {num_dogs} dog(s)' if num_dogs > 0 else '✓ No dogs'

            print(
                f'   → {status} | '
                f'Processing: {detection["processing_time"] * 1000:.1f}ms '
                f'(avg: {avg_time * 1000:.1f}ms, {avg_fps:.1f} FPS)'
            )

            return detection

        except Exception as e:
            print(f'❌ Error processing frame: {e}')
            import traceback

            traceback.print_exc()
            self.stats['errors'] += 1
            return ErrorMessage.create(
                'processing_error', str(e), message.get('frame_id')
            )

    async def handle_client(self, websocket):
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
            import traceback

            traceback.print_exc()
        finally:
            print(f'\n📊 Session stats:')
            print(f'   Frames processed: {self.stats["frames_processed"]}')
            print(f'   Dogs detected: {self.stats["dogs_detected"]}')
            if self.stats['frames_processed'] > 0:
                avg_time = (
                    self.stats['total_processing_time'] / self.stats['frames_processed']
                )
                avg_fps = 1.0 / avg_time if avg_time > 0 else 0
                print(
                    f'   Average processing: {avg_time * 1000:.1f}ms ({avg_fps:.1f} FPS)'
                )
            print(f'   Errors: {self.stats["errors"]}')

    async def start(self):
        """Start the WebSocket server"""
        await self.initialize_model()

        host = self.config['host']
        port = self.config['port']

        print(f'🚀 Starting detection server...')
        print(f'   Host: {host}')
        print(f'   Port: {port}')
        print(f'   Model: {self.model.model_type}')
        print(f'   Confidence threshold: {self.config["confidence_threshold"]}')

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
