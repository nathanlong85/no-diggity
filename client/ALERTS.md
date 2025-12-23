# Alert System Documentation

The No Diggity alert system provides multiple ways to respond when a dog is detected on the counter.

## Overview

The alert system is modular and configurable. When consecutive elevated detections occur, the system triggers all enabled alert handlers:

1. **GPIO Handler** - Ultrasonic speaker/buzzer control
2. **Snapshot Handler** - Capture and save detection images
3. **Log Handler** - Write alerts to log file
4. **Notification Handler** - Push notifications (Pushover, email, etc.)

## Configuration

All alert settings are configured in `client/config.py` under the `'alerts'` key:

```python
'alerts': {
    'cooldown_seconds': 30,  # Minimum time between alerts
    'handlers': {
        'gpio': {...},
        'snapshot': {...},
        'log': {...},
        'notification': {...}
    }
}
```

## Alert Handlers

### 1. GPIO Handler

Controls hardware devices via Raspberry Pi GPIO pins.

**Use cases:**
- Ultrasonic speaker (20kHz to deter dogs)
- Audible buzzer
- LED indicators
- Relay control for other devices

**Configuration:**
```python
'gpio': {
    'enabled': True,  # Only works on Raspberry Pi with RPi.GPIO
    'pin': 18,        # BCM pin number
    'frequency': 20000,  # PWM frequency in Hz
    'duration': 0.5,  # How long to activate (seconds)
    'duty_cycle': 50, # PWM duty cycle (0-100%)
}
```

**Hardware Setup:**
- Connect ultrasonic speaker/buzzer to GPIO pin (default: BCM 18)
- Recommended: Use a transistor/MOSFET for higher current devices
- Add appropriate resistors and protection diodes

**Wiring Example (Ultrasonic Speaker):**
```
GPIO Pin 18 -> 1kΩ resistor -> Base of NPN transistor
Transistor collector -> Speaker (+)
Speaker (-) -> Ground
Transistor emitter -> Ground
```

### 2. Snapshot Handler

Captures and saves annotated images when alerts trigger.

**Features:**
- Saves frames with detection boxes
- Draws zone polygons
- Adds timestamp overlay
- Saves metadata as JSON
- Auto-cleanup of old snapshots

**Configuration:**
```python
'snapshot': {
    'enabled': True,
    'save_dir': 'snapshots',
    'include_boxes': True,   # Draw detection boxes
    'include_zones': True,   # Draw zone polygons
    'max_snapshots': 1000,   # Auto-delete oldest
}
```

**Output Files:**
- `snapshots/20241223_143052_123_counter.jpg` - Annotated image
- `snapshots/20241223_143052_123_counter.json` - Metadata

**Metadata Format:**
```json
{
  "timestamp": "20241223_143052_123",
  "zones": ["counter"],
  "detection_count": 1,
  "frame_id": 42
}
```

### 3. Log Handler

Writes alerts to a text file with timestamps.

**Configuration:**
```python
'log': {
    'enabled': True,
    'log_file': 'alerts.log',
}
```

**Log Format:**
```
2024-12-23 14:30:52,123 - INFO - ALERT: Dog on counter detected | Zones: Kitchen Counter | Frame: 42 | Detections: 1
```

### 4. Notification Handler

Sends push notifications to your phone/device.

**Supported Methods:**
- **Pushover** (implemented) - Simple push notifications
- **Email** (planned) - Email alerts with snapshot attachments
- **Telegram** (planned) - Telegram bot messages

#### Pushover Setup

1. Create account at [pushover.net](https://pushover.net)
2. Install Pushover app on your phone
3. Get your User Key from the dashboard
4. Create an application to get an API Token

**Configuration:**
```python
'notification': {
    'enabled': True,
    'method': 'pushover',
    'credentials': {
        'user_key': 'YOUR_USER_KEY_HERE',
        'api_token': 'YOUR_API_TOKEN_HERE',
    }
}
```

**Install required package:**
```bash
pip install requests
```

## Alert Flow

1. **Detection** - Server detects dog and sends bounding boxes
2. **Zone Check** - Client checks if dog is in elevated zones
3. **Consecutive Check** - Checks for 2+ consecutive elevated frames
4. **Cooldown Check** - Verifies cooldown period has passed
5. **Trigger All Handlers** - Executes all enabled alert handlers

## Cooldown System

The cooldown prevents spam alerts:

- Separate cooldown per zone
- Default: 30 seconds
- Alerts won't trigger again for the same zone until cooldown expires
- Different zones can trigger independently

**Example:**
```
14:30:00 - Alert triggered for "counter" zone
14:30:15 - Dog still on counter (no alert - cooldown)
14:30:35 - Alert can trigger again for "counter"
```

## Testing Alerts

### Test Individual Handlers

You can test handlers without running the full system:

```python
from alerts import SnapshotAlertHandler, LogAlertHandler
import cv2

# Test snapshot handler
config = {'save_dir': 'test_snapshots', 'enabled': True}
handler = SnapshotAlertHandler(config)

frame = cv2.imread('test_frame.jpg')
alert_data = {
    'frame': frame,
    'zones': ['counter'],
    'triggered_zones': {'counter'},
    'detections': [],
    'zone_polygons': {},
    'frame_id': 1
}

handler.trigger(alert_data)
```

### Test GPIO on Raspberry Pi

```python
from alerts import GPIOAlertHandler

config = {
    'enabled': True,
    'pin': 18,
    'frequency': 20000,
    'duration': 0.5,
    'duty_cycle': 50
}

handler = GPIOAlertHandler(config)
handler.trigger({})  # Test trigger
handler.cleanup()
```

## Troubleshooting

### GPIO Not Working

**Error:** `ℹ️ RPi.GPIO not available - GPIO alerts disabled`

**Solution:** Install RPi.GPIO:
```bash
pip install RPi.GPIO
```

**Note:** GPIO only works on Raspberry Pi. On other systems, this alert type is automatically disabled.

### Snapshots Not Saving

**Check:**
1. Write permissions on snapshot directory
2. Disk space available
3. Check for errors in console output

### Pushover Not Sending

**Check:**
1. Internet connection
2. User Key and API Token are correct
3. `requests` library is installed: `pip install requests`
4. Check Pushover dashboard for delivery status

## Advanced: Custom Alert Handlers

You can create custom alert handlers by extending `AlertHandler`:

```python
from alerts import AlertHandler

class CustomAlertHandler(AlertHandler):
    def __init__(self, config: dict):
        super().__init__(config)
        # Your initialization
    
    def trigger(self, alert_data: dict):
        # Your alert logic
        pass
    
    def cleanup(self):
        # Cleanup resources
        pass
```

Then register it in `AlertManager.init_handlers()`.

## Performance Impact

**Handler Performance:**
- **GPIO:** ~1ms (negligible)
- **Log:** ~2ms (negligible)
- **Snapshot:** ~50-100ms (depends on image size)
- **Notification:** ~200-500ms (network dependent)

All handlers run synchronously when an alert triggers. For high-performance requirements, consider:
- Disable snapshot handler
- Use GPIO only
- Increase cooldown period

## Best Practices

1. **Start Simple** - Enable only log and snapshot handlers initially
2. **Test GPIO** - Test GPIO separately before enabling in production
3. **Adjust Cooldown** - Tune cooldown based on your needs (30-60s recommended)
4. **Monitor Storage** - Set appropriate `max_snapshots` to avoid filling disk
5. **Backup Logs** - Rotate or backup `alerts.log` periodically
