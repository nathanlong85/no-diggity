import cv2

# ============ CONFIGURATION - ADJUST THESE ============
# Define multiple detection zones as polygons
# Each polygon is a list of (x, y) coordinate points
# Points should go clockwise or counter-clockwise around the zone
ZONES = {
    'kitchen_counter': {
        'polygon': [
            (341, 398), 
            (370, 390),
            (395, 383),
            (420, 372),
            (439, 359), 
            (352, 339),
            (244, 373)
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
}

CAMERA_INDEX = 0
DISABLE_AUTOFOCUS = False
MANUAL_FOCUS_VALUE = 0.3


def init_camera():
    camera = cv2.VideoCapture(CAMERA_INDEX)

    if DISABLE_AUTOFOCUS:
        camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)

        if MANUAL_FOCUS_VALUE is not None:
            camera.set(cv2.CAP_PROP_FOCUS, MANUAL_FOCUS_VALUE)

    return camera
