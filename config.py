import cv2

CONFIG = {
    'camera_index': 0,
    'camera_resolution': (640, 480),  # Lower resolution = faster processing
    'confidence_threshold': 0.5,
    'disable_autofocus': False,
    'dog_class_id': 12,
    'frame_skip': 5,  # Process every Nth frame (higher = less CPU)
    'jpeg_quality': 70,  # Lower quality = less encoding time (50-85 recommended)
    'manual_focus_value': 0.3,
    'min_elevated_size_ratio': 0.3,
    'model_path': 'mobilenet_iter_73000.caffemodel',
    'prototxt_path': 'deploy.prototxt',
    'web_server_port': 5000,
    'zones': {
        """
            Define multiple detection zones as polygons
            Each polygon is a list of (x, y) coordinate points
            Points should go clockwise or counter-clockwise around the zone
        """
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


def init_camera():
    camera = cv2.VideoCapture(CONFIG['camera_index'])

    # Set lower resolution for better performance
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG['camera_resolution'][0])
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG['camera_resolution'][1])

    # Reduce framerate if possible (not all cameras support this)
    camera.set(cv2.CAP_PROP_FPS, 15)

    if CONFIG['disable_autofocus']:
        camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)

        if CONFIG['manual_focus_value'] is not None:
            camera.set(cv2.CAP_PROP_FOCUS, CONFIG['manual_focus_value'])

    return camera
