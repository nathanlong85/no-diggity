"""
Client configuration for No Diggity.

Configure camera, server connection, zones, and alert handlers.
"""

CLIENT_CONFIG = {
    # Server connection
    'server_host': 'localhost',
    'server_port': 8765,
    # Web dashboard
    'enable_dashboard': True,  # Enable web dashboard
    # Camera settings
    'camera_index': 0,
    'camera_resolution': (640, 480),
    'frame_skip': 5,  # Send every 5th frame
    'jpeg_quality': 70,  # JPEG compression quality (1-100)
    # Detection settings
    'min_elevated_size_ratio': 0.3,  # Minimum size ratio to consider elevated
    # Zone definitions
    # Run calibrate_zones.py to create these interactively
    'zones': {
        'counter': {
            'name': 'Kitchen Counter',
            'enabled': True,
            'polygon': [
                (100, 50),  # Top-left
                (540, 50),  # Top-right
                (540, 250),  # Bottom-right
                (100, 250),  # Bottom-left
            ],
        },
        'table': {
            'name': 'Dining Table',
            'enabled': True,
            'polygon': [
                (50, 260),
                (300, 260),
                (300, 400),
                (50, 400),
            ],
        },
        # Add more zones as needed
    },
    # Alert system configuration
    'alerts': {
        'cooldown_seconds': 30,  # Minimum time between alerts for same zone
        'handlers': {
            # GPIO handler (ultrasonic speaker, buzzer, etc.)
            'gpio': {
                'enabled': False,  # Set to True on Raspberry Pi with GPIO
                'pin': 18,  # BCM pin number
                'frequency': 20000,  # 20kHz for ultrasonic
                'duration': 0.5,  # seconds
                'duty_cycle': 50,  # PWM duty cycle (0-100)
            },
            # Snapshot handler
            'snapshot': {
                'enabled': True,
                'save_dir': 'snapshots',  # Directory to save snapshots
                'include_boxes': True,  # Draw detection boxes on snapshots
                'include_zones': True,  # Draw zone polygons on snapshots
                'max_snapshots': 1000,  # Max snapshots to keep (oldest deleted)
            },
            # Log handler
            'log': {
                'enabled': True,
                'log_file': 'alerts.log',
            },
            # Notification handler
            'notification': {
                'enabled': False,  # Enable for push notifications
                'method': 'pushover',  # 'pushover', 'email', 'telegram'
                'credentials': {
                    # For Pushover:
                    'user_key': 'YOUR_USER_KEY_HERE',
                    'api_token': 'YOUR_API_TOKEN_HERE',
                    # For Email (not yet implemented):
                    # 'smtp_server': 'smtp.gmail.com',
                    # 'smtp_port': 587,
                    # 'username': 'your_email@gmail.com',
                    # 'password': 'your_password',
                    # 'recipient': 'recipient@email.com',
                    # For Telegram (not yet implemented):
                    # 'bot_token': 'YOUR_BOT_TOKEN',
                    # 'chat_id': 'YOUR_CHAT_ID',
                },
            },
        },
    },
}
