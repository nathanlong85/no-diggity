"""
Configuration for No Diggity detection server.
"""

import os

SERVER_CONFIG = {
    # Network settings
    'host': '0.0.0.0',  # Listen on all interfaces
    'port': int(os.getenv('DOG_SERVER_PORT', 8765)),
    # Model selection: 'auto', 'yolo', or 'mobilenet'
    'model_preference': os.getenv('DOG_MODEL', 'auto'),
    # Detection settings
    'confidence_threshold': 0.5,
    'dog_class_id': 12,  # MobileNet-SSD dog class
    # 'dog_class_id': 16,  # YOLOv8 dog class (uncomment when using YOLO)
}
