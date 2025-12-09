import threading

import cv2
import logging
import numpy as np
from flask import Flask, Response, render_template_string
from ultralytics import YOLO

from calibration_template import HTML_TEMPLATE
from config import ZONES, init_camera

# Height threshold - dog's TOP position must be above this line
COUNTER_HEIGHT_THRESHOLD = 300

# Size threshold - dog bounding box height relative to frame
MIN_ELEVATED_SIZE_RATIO = 0.3  # Dog takes up at least 30% of frame height

# Confidence threshold for detections
CONFIDENCE_THRESHOLD = 0.5

# Web server settings
WEB_SERVER_PORT = 5000
# ======================================================

# Flask app
app = Flask(__name__)

# Global variables for video processing
model = None
cap = None
latest_frame = None
frame_lock = threading.Lock()

# Loggers
logging.getLogger('ultralytics').setLevel(logging.ERROR)


def check_polygon_zones(box):
    """Check which polygon zones the dog bounding box overlaps with"""
    x1, y1, x2, y2 = box

    # Get the 4 corners and center of the bounding box
    box_points = [
        (int(x1), int(y1)),  # Top-left
        (int(x2), int(y1)),  # Top-right
        (int(x2), int(y2)),  # Bottom-right
        (int(x1), int(y2)),  # Bottom-left
        (int((x1 + x2) / 2), int((y1 + y2) / 2)),  # Center
    ]

    triggered_zones = []

    for zone_id, zone in ZONES.items():
        if not zone['enabled']:
            continue

        polygon = np.array(zone['polygon'], np.int32)

        # Check if any point of the bounding box is inside the polygon
        for point in box_points:
            result = cv2.pointPolygonTest(polygon, point, False)
            if result >= 0:  # Point is inside or on the polygon
                triggered_zones.append(zone_id)
                break

    return triggered_zones


def analyze_dog_position(box, frame_height):
    """Analyze if dog is elevated based on position and size"""
    x1, y1, x2, y2 = box

    dog_top = y1
    box_height = y2 - y1

    # Calculate relative size
    relative_size = box_height / frame_height

    # Check which zones dog is in
    triggered_zones = check_polygon_zones([x1, y1, x2, y2])

    # Check multiple indicators
    is_high_enough = dog_top < COUNTER_HEIGHT_THRESHOLD
    is_large_enough = relative_size > MIN_ELEVATED_SIZE_RATIO
    in_any_zone = len(triggered_zones) > 0

    return {
        'elevated': is_high_enough and is_large_enough and in_any_zone,
        'zones': triggered_zones,
        'top_y': dog_top,
        'size_ratio': relative_size,
    }


def draw_polygon_zones(frame):
    """Draw all enabled polygon zones on the frame"""
    overlay = frame.copy()

    for _, zone in ZONES.items():
        if not zone['enabled']:
            continue

        polygon = np.array(zone['polygon'], np.int32)

        # Draw filled polygon on overlay
        cv2.fillPoly(overlay, [polygon], zone['color'])

        # Draw polygon outline on main frame
        cv2.polylines(frame, [polygon], True, zone['color'], 3)

        # Add label near first point
        label_x = zone['polygon'][0][0] + 10
        label_y = zone['polygon'][0][1] + 30

        # Draw label background
        label_size = cv2.getTextSize(zone['name'], cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(
            frame,
            (label_x - 5, label_y - label_size[1] - 5),
            (label_x + label_size[0] + 5, label_y + 5),
            zone['color'],
            -1,
        )

        cv2.putText(
            frame,
            zone['name'],
            (label_x, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

        # Draw dots at polygon vertices for calibration
        for point in zone['polygon']:
            cv2.circle(frame, point, 5, zone['color'], -1)
            cv2.circle(frame, point, 6, (255, 255, 255), 1)

    # Blend overlay with original frame
    cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
    return frame


def trigger_alert(zones):
    """Trigger appropriate alerts for the zones"""
    for zone_id in zones:
        zone = ZONES[zone_id]
        print(f'🚨 ALERT: Dog detected on {zone["name"]}!')

        # Here you would trigger your ultrasonic sound or other actions
        if zone['action'] == 'sound_alert':
            # TODO: Add your ultrasonic speaker code here
            # Example for Raspberry Pi GPIO:
            # import RPi.GPIO as GPIO
            # BUZZER_PIN = 18  # Choose your GPIO pin
            # GPIO.setmode(GPIO.BCM)
            # GPIO.setup(BUZZER_PIN, GPIO.OUT)
            #
            # # Create PWM for ultrasonic frequency (e.g., 20kHz)
            # pwm = GPIO.PWM(BUZZER_PIN, 20000)  # 20kHz
            # pwm.start(50)  # 50% duty cycle
            # time.sleep(0.5)  # Play for 0.5 seconds
            # pwm.stop()
            pass


def process_frames():
    """Continuously process frames from webcam"""
    global latest_frame, cap, model

    while True:
        ret, frame = cap.read()
        if not ret:
            print('Error: Could not read frame')
            break

        frame_height = frame.shape[0]

        # Draw zones on frame
        frame = draw_polygon_zones(frame)

        # Run detection
        results = model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)

        elevated_detected = False
        all_triggered_zones = set()

        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_name = result.names[int(box.cls[0])]
                confidence = float(box.conf[0])

                if class_name == 'dog':
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)

                    # Analyze position
                    analysis = analyze_dog_position(xyxy, frame_height)

                    # Choose color based on status
                    if analysis['elevated']:
                        color = (0, 0, 255)  # Red - ALERT!
                        label = '⚠️ DOG ELEVATED!'
                        elevated_detected = True
                        all_triggered_zones.update(analysis['zones'])
                    else:
                        color = (0, 255, 0)  # Green - safe
                        label = 'Dog (floor)'

                    # Draw bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)

                    # Draw label with confidence
                    label_text = f'{label} ({confidence:.2f})'
                    label_size = cv2.getTextSize(
                        label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                    )[0]
                    cv2.rectangle(
                        frame,
                        (x1, y1 - label_size[1] - 10),
                        (x1 + label_size[0], y1),
                        color,
                        -1,
                    )
                    cv2.putText(
                        frame,
                        label_text,
                        (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2,
                    )

                    # Show which zones are triggered
                    if analysis['zones']:
                        zones_text = 'Zones: ' + ', '.join(
                            [ZONES[z]['name'] for z in analysis['zones']]
                        )
                        cv2.putText(
                            frame,
                            zones_text,
                            (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            1,
                        )

                    # Draw detailed stats
                    info_y = y2 + 40
                    cv2.putText(
                        frame,
                        f'Top Y: {int(analysis["top_y"])} | Size: {analysis["size_ratio"]:.2f}',
                        (x1, info_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        color,
                        1,
                    )

        # Trigger alerts if needed
        if elevated_detected and all_triggered_zones:
            trigger_alert(all_triggered_zones)

        # Status indicator at top
        status_bg_color = (0, 0, 139) if elevated_detected else (0, 100, 0)
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), status_bg_color, -1)

        status_text = (
            '🚨 ALERT: DOG ON COUNTER!' if elevated_detected else '✓ All Clear'
        )
        cv2.putText(
            frame,
            status_text,
            (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 255),
            3,
        )

        # Show active zones in alert
        if elevated_detected and all_triggered_zones:
            zones_names = ', '.join([ZONES[z]['name'] for z in all_triggered_zones])
            cv2.putText(
                frame,
                f'Location: {zones_names}',
                (frame.shape[1] - 400, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        # Update latest frame
        with frame_lock:
            latest_frame = frame.copy()


def generate_frames():
    """Generator function for Flask to stream frames"""
    while True:
        with frame_lock:
            if latest_frame is None:
                continue
            frame = latest_frame.copy()

        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/')
def index():
    """Main page with video stream"""
    # Get actual camera resolution
    ret, frame = cap.read()

    if ret:
        video_width = frame.shape[1]
        video_height = frame.shape[0]
    else:
        video_width = 640
        video_height = 480

    return render_template_string(
        HTML_TEMPLATE,
        zones=ZONES,
        video_width=video_width,
        video_height=video_height,
    )


@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(
        generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame'
    )


def main():
    global model, cap

    print('Loading YOLO model...')
    model = YOLO('yolo11n.onnx')

    print('\n=== CONFIGURED ZONES (POLYGONS) ===')
    for _, zone in ZONES.items():
        status = 'ENABLED' if zone['enabled'] else 'DISABLED'
        print(f'  {zone["name"]}: {status}')
        print(f'    Points: {zone["polygon"]}')
    print('====================================\n')

    print('Opening webcam...')
    cap = init_camera()

    if not cap.isOpened():
        print('Error: Could not open webcam')
        return

    # Get frame dimensions
    ret, test_frame = cap.read()
    if ret:
        print(f'Camera resolution: {test_frame.shape[1]}x{test_frame.shape[0]}')

    # Start frame processing in separate thread
    processing_thread = threading.Thread(target=process_frames, daemon=True)
    processing_thread.start()

    print(f'\n🌐 Web server starting on port {WEB_SERVER_PORT}')
    print(f'📱 Open http://YOUR_PI_IP:{WEB_SERVER_PORT} in your browser')
    print(f'   (or http://localhost:{WEB_SERVER_PORT} if running locally)\n')

    # Start Flask server
    app.run(host='::', port=WEB_SERVER_PORT, debug=False, threaded=True)


if __name__ == '__main__':
    main()
