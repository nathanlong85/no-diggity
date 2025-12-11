"""
Configuration for No Diggity client.
"""

import os

CLIENT_CONFIG = {
    # Server connection
    'server_host': os.getenv('DOG_SERVER_HOST', 'localhost'),
    'server_port': int(os.getenv('DOG_SERVER_PORT', 8765)),
    # Camera settings
    'camera_index': 0,
    'camera_resolution': (640, 480),  # Lower = faster processing
    # Frame processing
    'frame_skip': 5,  # Send every Nth frame
    'jpeg_quality': 70,  # 50-85 recommended for balance
    # Detection settings
    'confidence_threshold': 0.5,
    'min_elevated_size_ratio': 0.3,
    # Web server (for Phase 4)
    'web_server_port': 5000,
    # Zones (preserved from original config)
    'zones': {
        'kitchen_counter': {
            'polygon': [
                (341, 398),
                (370, 390),
                (395, 383),
                (420, 372),
                (439, 359),
                (352, 339),
                (244, 373),
            ],
            'action': 'sound_alert',
            'color': (0, 255, 255),  # Yellow
            'name': 'Kitchen Counter',
            'enabled': True,
        },
        'dining_table': {
            'polygon': [(700, 100), (1100, 150), (1050, 400), (680, 380)],
            'action': 'sound_alert',
            'color': (255, 0, 255),  # Magenta
            'name': 'Dining Table',
            'enabled': False,
        },
        'island_counter': {
            'polygon': [(300, 400), (700, 420), (680, 650), (290, 630)],
            'action': 'sound_alert',
            'color': (255, 165, 0),  # Orange
            'name': 'Island',
            'enabled': False,
        },
    },
}
