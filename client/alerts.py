"""
Alert system for No Diggity.

Manages multiple alert types: GPIO, snapshots, notifications, logging.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Try to import GPIO for Raspberry Pi
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print('ℹ️  RPi.GPIO not available - GPIO alerts disabled')


class AlertHandler:
    """Base class for alert handlers"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get('enabled', True)

    def trigger(self, alert_data: dict):
        """Trigger the alert"""
        raise NotImplementedError

    def cleanup(self):
        """Cleanup resources"""
        pass


class GPIOAlertHandler(AlertHandler):
    """Handle GPIO-based alerts (ultrasonic speaker, buzzer, etc.)"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.pin = config.get('pin', 18)
        self.frequency = config.get('frequency', 20000)  # 20kHz for ultrasonic
        self.duration = config.get('duration', 0.5)  # seconds
        self.duty_cycle = config.get('duty_cycle', 50)  # 50%
        self.pwm = None

        if self.enabled and GPIO_AVAILABLE:
            self.setup_gpio()

    def setup_gpio(self):
        """Setup GPIO pins"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            self.pwm = GPIO.PWM(self.pin, self.frequency)
            print(
                f'✓ GPIO alert handler initialized on pin {self.pin} at {self.frequency}Hz'
            )
        except Exception as e:
            print(f'⚠️  Failed to setup GPIO: {e}')
            self.enabled = False

    def trigger(self, alert_data: dict):
        """Trigger GPIO output"""
        if not self.enabled or not self.pwm:
            return

        try:
            print(f'🔊 Triggering GPIO alert on pin {self.pin}')
            self.pwm.start(self.duty_cycle)
            time.sleep(self.duration)
            self.pwm.stop()
        except Exception as e:
            print(f'❌ GPIO alert failed: {e}')

    def cleanup(self):
        """Cleanup GPIO"""
        if self.pwm:
            self.pwm.stop()
        if GPIO_AVAILABLE:
            GPIO.cleanup()


class SnapshotAlertHandler(AlertHandler):
    """Capture and save snapshots when alerts trigger"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.save_dir = Path(config.get('save_dir', 'snapshots'))
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.include_boxes = config.get('include_boxes', True)
        self.include_zones = config.get('include_zones', True)
        self.max_snapshots = config.get('max_snapshots', 1000)

        print(f'✓ Snapshot alert handler initialized: {self.save_dir}')

    def trigger(self, alert_data: dict):
        """Save snapshot"""
        try:
            frame = alert_data.get('frame')
            if frame is None:
                print('⚠️  No frame provided for snapshot')
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            zones = '_'.join(alert_data.get('zones', ['unknown']))
            filename = f'{timestamp}_{zones}.jpg'
            filepath = self.save_dir / filename

            # Annotate frame if requested
            annotated = self.annotate_frame(
                frame.copy(),
                alert_data.get('detections', []),
                alert_data.get('zone_polygons', {}),
                alert_data.get('triggered_zones', set()),
            )

            # Save
            cv2.imwrite(str(filepath), annotated)
            print(f'📸 Snapshot saved: {filename}')

            # Cleanup old snapshots if limit exceeded
            self.cleanup_old_snapshots()

            # Save metadata
            metadata_file = filepath.with_suffix('.json')
            with open(metadata_file, 'w') as f:
                json.dump(
                    {
                        'timestamp': timestamp,
                        'zones': list(alert_data.get('triggered_zones', [])),
                        'detection_count': len(alert_data.get('detections', [])),
                        'frame_id': alert_data.get('frame_id'),
                    },
                    f,
                    indent=2,
                )

        except Exception as e:
            print(f'❌ Snapshot failed: {e}')

    def annotate_frame(
        self, frame, detections: list, zone_polygons: dict, triggered_zones: set
    ):
        """Annotate frame with detection boxes and zones"""
        if not self.include_boxes and not self.include_zones:
            return frame

        overlay = frame.copy()

        # Draw zones
        if self.include_zones and zone_polygons:
            for zone_id, polygon in zone_polygons.items():
                if zone_id in triggered_zones:
                    color = (0, 0, 255)  # Red for triggered
                    thickness = 3
                else:
                    color = (0, 255, 0)  # Green for inactive
                    thickness = 2

                pts = np.array(polygon, np.int32)
                cv2.polylines(overlay, [pts], True, color, thickness)

        # Draw detection boxes
        if self.include_boxes and detections:
            for det in detections:
                x1, y1, x2, y2 = (
                    int(det['x1']),
                    int(det['y1']),
                    int(det['x2']),
                    int(det['y2']),
                )
                conf = det.get('confidence', 0)

                # Draw box
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 255), 2)

                # Draw label
                label = f'{det.get("class_name", "dog")} {conf:.2f}'
                cv2.putText(
                    overlay,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 255),
                    2,
                )

        # Blend overlay
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Add timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(
            frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        return frame

    def cleanup_old_snapshots(self):
        """Remove old snapshots if limit exceeded"""
        snapshots = sorted(self.save_dir.glob('*.jpg'))
        if len(snapshots) > self.max_snapshots:
            to_remove = len(snapshots) - self.max_snapshots
            for snapshot in snapshots[:to_remove]:
                snapshot.unlink()
                # Also remove metadata
                snapshot.with_suffix('.json').unlink(missing_ok=True)


class LogAlertHandler(AlertHandler):
    """Log alerts to file"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.log_file = Path(config.get('log_file', 'alerts.log'))

        # Setup logging
        self.logger = logging.getLogger('AlertLogger')
        self.logger.setLevel(logging.INFO)

        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.INFO)

        # Format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)

        self.logger.addHandler(fh)

        print(f'✓ Log alert handler initialized: {self.log_file}')

    def trigger(self, alert_data: dict):
        """Log alert"""
        try:
            zones = ', '.join(alert_data.get('zones', ['unknown']))
            frame_id = alert_data.get('frame_id', 'N/A')
            detection_count = len(alert_data.get('detections', []))

            message = (
                f'ALERT: Dog on counter detected | '
                f'Zones: {zones} | '
                f'Frame: {frame_id} | '
                f'Detections: {detection_count}'
            )

            self.logger.info(message)

        except Exception as e:
            print(f'❌ Log alert failed: {e}')


class NotificationAlertHandler(AlertHandler):
    """Send push notifications (Pushover, email, etc.)"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.method = config.get('method', 'pushover')  # pushover, email, telegram
        self.credentials = config.get('credentials', {})

        print(f'✓ Notification alert handler initialized: {self.method}')

    def trigger(self, alert_data: dict):
        """Send notification"""
        if not self.enabled:
            return

        try:
            zones = ', '.join(alert_data.get('zones', ['unknown']))
            message = f'🚨 Dog detected on {zones}!'

            if self.method == 'pushover':
                self.send_pushover(message)
            elif self.method == 'email':
                self.send_email(message, alert_data)
            elif self.method == 'telegram':
                self.send_telegram(message)
            else:
                print(f'⚠️  Unknown notification method: {self.method}')

        except Exception as e:
            print(f'❌ Notification failed: {e}')

    def send_pushover(self, message: str):
        """Send Pushover notification"""
        try:
            import requests

            user_key = self.credentials.get('user_key')
            api_token = self.credentials.get('api_token')

            if not user_key or not api_token:
                print('⚠️  Pushover credentials not configured')
                return

            response = requests.post(
                'https://api.pushover.net/1/messages.json',
                data={
                    'token': api_token,
                    'user': user_key,
                    'message': message,
                    'priority': 1,  # High priority
                },
            )

            if response.status_code == 200:
                print('📱 Pushover notification sent')
            else:
                print(f'⚠️  Pushover failed: {response.status_code}')

        except ImportError:
            print('⚠️  requests library not installed for Pushover')
        except Exception as e:
            print(f'❌ Pushover error: {e}')

    def send_email(self, message: str, alert_data: dict):
        """Send email notification"""
        # TODO: Implement email notifications
        print('📧 Email notifications not yet implemented')

    def send_telegram(self, message: str):
        """Send Telegram notification"""
        # TODO: Implement Telegram notifications
        print('💬 Telegram notifications not yet implemented')


class AlertManager:
    """Manages all alert handlers and cooldown logic"""

    def __init__(self, config: dict):
        self.config = config
        self.handlers = []
        self.cooldown_seconds = config.get('cooldown_seconds', 30)
        self.last_alert_time = {}  # {zone_id: timestamp}

        # Initialize handlers
        self.init_handlers()

    def init_handlers(self):
        """Initialize all enabled alert handlers"""
        handler_configs = self.config.get('handlers', {})

        # GPIO handler
        if handler_configs.get('gpio', {}).get('enabled', False):
            self.handlers.append(GPIOAlertHandler(handler_configs['gpio']))

        # Snapshot handler
        if handler_configs.get('snapshot', {}).get('enabled', True):
            self.handlers.append(
                SnapshotAlertHandler(handler_configs.get('snapshot', {}))
            )

        # Log handler
        if handler_configs.get('log', {}).get('enabled', True):
            self.handlers.append(LogAlertHandler(handler_configs.get('log', {})))

        # Notification handler
        if handler_configs.get('notification', {}).get('enabled', False):
            self.handlers.append(
                NotificationAlertHandler(handler_configs['notification'])
            )

        print(f'✓ Alert manager initialized with {len(self.handlers)} handlers')

    def should_trigger(self, triggered_zones: set) -> bool:
        """Check if alert should trigger based on cooldown"""
        current_time = time.time()

        for zone_id in triggered_zones:
            last_alert = self.last_alert_time.get(zone_id, 0)
            if current_time - last_alert < self.cooldown_seconds:
                return False

        return True

    def trigger_alert(self, alert_data: dict):
        """Trigger all alert handlers"""
        triggered_zones = alert_data.get('triggered_zones', set())

        # Check cooldown
        if not self.should_trigger(triggered_zones):
            print(f'⏱️  Alert on cooldown (last: {self.cooldown_seconds}s ago)')
            return

        # Update last alert times
        current_time = time.time()
        for zone_id in triggered_zones:
            self.last_alert_time[zone_id] = current_time

        # Trigger all handlers
        for handler in self.handlers:
            if handler.enabled:
                try:
                    handler.trigger(alert_data)
                except Exception as e:
                    print(f'❌ Handler {handler.__class__.__name__} failed: {e}')

    def cleanup(self):
        """Cleanup all handlers"""
        for handler in self.handlers:
            try:
                handler.cleanup()
            except Exception as e:
                print(f'⚠️  Cleanup failed for {handler.__class__.__name__}: {e}')
