"""
Shared message protocol for No Diggity client-server communication.

This module defines the message formats exchanged between the Pi client
and the PC server over WebSocket.
"""

import base64
import json
import time
from typing import Any

import cv2
import numpy as np


class MessageType:
    """Message type constants"""

    FRAME = 'frame'
    DETECTION = 'detection'
    ERROR = 'error'
    PING = 'ping'
    PONG = 'pong'


class FrameMessage:
    """Frame message sent from client to server"""

    @staticmethod
    def create(
        frame: np.ndarray, frame_id: int, jpeg_quality: int = 70
    ) -> dict[str, Any]:
        """
        Create a frame message from a numpy image array.

        Args:
            frame: OpenCV image (numpy array)
            frame_id: Unique frame sequence number
            jpeg_quality: JPEG compression quality (0-100)

        Returns:
            Dictionary ready to be JSON serialized
        """
        # Encode frame as JPEG
        ret, buffer = cv2.imencode(
            '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        )

        if not ret:
            raise ValueError('Failed to encode frame as JPEG')

        # Convert to base64
        image_base64 = base64.b64encode(buffer).decode('utf-8')

        return {
            'type': MessageType.FRAME,
            'frame_id': frame_id,
            'timestamp': time.time(),
            'image': image_base64,
            'shape': frame.shape[:2],  # (height, width)
        }

    @staticmethod
    def decode(message: dict[str, Any]) -> tuple[np.ndarray, int, float]:
        """
        Decode a frame message back to numpy array.

        Args:
            message: Frame message dictionary

        Returns:
            Tuple of (frame, frame_id, timestamp)
        """
        # Decode base64
        image_bytes = base64.b64decode(message['image'])

        # Convert to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)

        # Decode JPEG
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        return frame, message['frame_id'], message['timestamp']


class DetectionMessage:
    """Detection message sent from server to client"""

    @staticmethod
    def create(
        frame_id: int,
        elevated: bool,
        boxes: list[dict[str, Any]],
        processing_time: float,
    ) -> dict[str, Any]:
        """
        Create a detection result message.

        Args:
            frame_id: Frame sequence number this detection corresponds to
            elevated: Whether any elevated dog was detected
            boxes: List of detection boxes with format:
                   [{'x1': int, 'y1': int, 'x2': int, 'y2': int,
                     'confidence': float, 'class_id': int, 'class_name': str}]
            processing_time: Time taken to process frame (seconds)

        Returns:
            Dictionary ready to be JSON serialized
        """
        return {
            'type': MessageType.DETECTION,
            'frame_id': frame_id,
            'timestamp': time.time(),
            'elevated': elevated,
            'boxes': boxes,
            'processing_time': processing_time,
        }


class ErrorMessage:
    """Error message for communication issues"""

    @staticmethod
    def create(
        error_type: str, message: str, frame_id: int | None = None
    ) -> dict[str, Any]:
        """Create an error message"""
        return {
            'type': MessageType.ERROR,
            'error_type': error_type,
            'message': message,
            'frame_id': frame_id,
            'timestamp': time.time(),
        }


class PingPongMessage:
    """Ping/Pong messages for connection health checks"""

    @staticmethod
    def create_ping() -> dict[str, Any]:
        """Create a ping message"""
        return {'type': MessageType.PING, 'timestamp': time.time()}

    @staticmethod
    def create_pong(ping_timestamp: float) -> dict[str, Any]:
        """Create a pong message in response to a ping"""
        return {
            'type': MessageType.PONG,
            'ping_timestamp': ping_timestamp,
            'pong_timestamp': time.time(),
        }


def serialize_message(message: dict[str, Any]) -> str:
    """Serialize a message dictionary to JSON string"""
    return json.dumps(message)


def deserialize_message(message_str: str) -> dict[str, Any]:
    """Deserialize a JSON string to message dictionary"""
    return json.loads(message_str)
