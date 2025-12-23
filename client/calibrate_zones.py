"""
Zone Calibration Tool for No Diggity

Interactive tool to define polygon zones on camera feed.
Click to add points, press keys to control zones.
"""

import sys
from pathlib import Path

import cv2
import numpy as np

# Add shared module to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from config import CLIENT_CONFIG
except ImportError:
    CLIENT_CONFIG = {
        'camera_index': 0,
        'camera_resolution': (640, 480),
    }


class ZoneCalibrator:
    """Interactive zone calibration tool"""

    def __init__(self, camera_index: int, resolution: tuple):
        self.camera_index = camera_index
        self.resolution = resolution
        self.camera = None
        self.frame = None

        # Current zone being drawn
        self.current_zone = []
        self.zones = {}  # {zone_name: {'polygon': [...], 'color': (...)}}
        self.zone_counter = 1

        # Colors for different zones
        self.colors = [
            (0, 255, 0),  # Green
            (255, 0, 0),  # Blue
            (0, 0, 255),  # Red
            (255, 255, 0),  # Cyan
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
        ]
        self.color_index = 0

        # UI state
        self.window_name = 'Zone Calibration Tool'
        self.help_visible = True

    def init_camera(self):
        """Initialize camera"""
        print('📷 Initializing camera...')
        self.camera = cv2.VideoCapture(self.camera_index)

        # Set resolution
        width, height = self.resolution
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        if not self.camera.isOpened():
            raise RuntimeError('Failed to open camera')

        # Capture initial frame
        ret, self.frame = self.camera.read()
        if not ret:
            raise RuntimeError('Failed to read from camera')

        print(f'✓ Camera initialized: {self.frame.shape[1]}x{self.frame.shape[0]}')

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Add point to current zone
            self.current_zone.append((x, y))
            print(f'  Point added: ({x}, {y})')

    def draw_zones(self, frame):
        """Draw all zones and current zone on frame"""
        overlay = frame.copy()

        # Draw completed zones
        for zone_name, zone_data in self.zones.items():
            polygon = np.array(zone_data['polygon'], np.int32)
            color = zone_data['color']

            # Fill polygon with transparency
            cv2.fillPoly(overlay, [polygon], color)

            # Draw outline
            cv2.polylines(overlay, [polygon], True, color, 2)

            # Draw zone name
            center = polygon.mean(axis=0).astype(int)
            cv2.putText(
                overlay,
                zone_name,
                tuple(center),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        # Draw current zone being created
        if len(self.current_zone) > 0:
            color = self.colors[self.color_index % len(self.colors)]

            # Draw points
            for point in self.current_zone:
                cv2.circle(overlay, point, 5, color, -1)

            # Draw lines between points
            if len(self.current_zone) > 1:
                for i in range(len(self.current_zone) - 1):
                    cv2.line(
                        overlay,
                        self.current_zone[i],
                        self.current_zone[i + 1],
                        color,
                        2,
                    )

            # Draw closing line if 3+ points
            if len(self.current_zone) >= 3:
                cv2.line(
                    overlay,
                    self.current_zone[-1],
                    self.current_zone[0],
                    color,
                    1,
                    cv2.LINE_AA,
                )

        # Blend overlay
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

        return frame

    def draw_help(self, frame):
        """Draw help text on frame"""
        if not self.help_visible:
            return frame

        help_text = [
            'ZONE CALIBRATION TOOL',
            '',
            'Click: Add point to zone',
            'ENTER: Complete zone',
            'ESC: Cancel current zone',
            'C: Clear all zones',
            'S: Save zones to file',
            'H: Toggle help',
            'Q: Quit',
            '',
            f'Current zone: {len(self.current_zone)} points',
            f'Total zones: {len(self.zones)}',
        ]

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 10 + 25 * len(help_text)), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Draw text
        y = 30
        for i, line in enumerate(help_text):
            if i == 0:  # Title
                color = (0, 255, 255)
                thickness = 2
            elif line == '':
                continue
            else:
                color = (255, 255, 255)
                thickness = 1

            cv2.putText(
                frame,
                line,
                (20, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                thickness,
            )
            y += 25

        return frame

    def complete_zone(self):
        """Complete the current zone and add to zones dict"""
        if len(self.current_zone) < 3:
            print('⚠️  Need at least 3 points to create a zone')
            return

        zone_name = input(
            f'\n📝 Enter name for zone (or press Enter for "zone_{self.zone_counter}"): '
        ).strip()
        if not zone_name:
            zone_name = f'zone_{self.zone_counter}'

        self.zones[zone_name] = {
            'polygon': self.current_zone.copy(),
            'color': self.colors[self.color_index % len(self.colors)],
        }

        print(f'✓ Zone "{zone_name}" created with {len(self.current_zone)} points')

        # Reset for next zone
        self.current_zone = []
        self.zone_counter += 1
        self.color_index += 1

    def cancel_zone(self):
        """Cancel the current zone"""
        if len(self.current_zone) > 0:
            print('❌ Current zone cancelled')
            self.current_zone = []

    def clear_all_zones(self):
        """Clear all zones"""
        if len(self.zones) > 0:
            confirm = input(f'\n⚠️  Clear all {len(self.zones)} zones? (y/n): ').lower()
            if confirm == 'y':
                self.zones = {}
                self.zone_counter = 1
                print('✓ All zones cleared')
        else:
            print('ℹ️  No zones to clear')

    def save_zones(self):
        """Save zones to a Python config file"""
        if len(self.zones) == 0:
            print('⚠️  No zones to save')
            return

        output_file = 'zones_config.py'

        with open(output_file, 'w') as f:
            f.write('# Generated zone configuration\n')
            f.write('# Copy these zones to your config.py\n\n')
            f.write('ZONES = {\n')

            for zone_name, zone_data in self.zones.items():
                f.write(f"    '{zone_name}': {{\n")
                f.write(f"        'name': '{zone_name.replace('_', ' ').title()}',\n")
                f.write(f"        'enabled': True,\n")
                f.write(f"        'polygon': [\n")

                for point in zone_data['polygon']:
                    f.write(f'            {point},\n')

                f.write('        ]\n')
                f.write('    },\n')

            f.write('}\n')

        print(f'\n✓ Zones saved to {output_file}')
        print(f'  Copy the ZONES dict to your config.py')

    def run(self):
        """Main run loop"""
        self.init_camera()

        # Create window and set mouse callback
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

        print('\n🎯 Zone Calibration Tool Started')
        print('   Click to add points, press ENTER to complete zone')
        print('   Press H for help, Q to quit\n')

        while True:
            # Capture frame
            ret, frame = self.camera.read()
            if not ret:
                print('⚠️  Failed to read frame')
                break

            # Draw zones and help
            display = self.draw_zones(frame)
            display = self.draw_help(display)

            # Show frame
            cv2.imshow(self.window_name, display)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                # Quit
                break

            elif key == 13:  # ENTER
                # Complete zone
                self.complete_zone()

            elif key == 27:  # ESC
                # Cancel current zone
                self.cancel_zone()

            elif key == ord('c'):
                # Clear all zones
                self.clear_all_zones()

            elif key == ord('s'):
                # Save zones
                self.save_zones()

            elif key == ord('h'):
                # Toggle help
                self.help_visible = not self.help_visible

        # Cleanup
        self.camera.release()
        cv2.destroyAllWindows()

        # Offer to save on exit
        if len(self.zones) > 0:
            print(f'\n📊 You created {len(self.zones)} zones')
            save = input('   Save zones before exiting? (y/n): ').lower()
            if save == 'y':
                self.save_zones()


def main():
    """Main entry point"""
    calibrator = ZoneCalibrator(
        CLIENT_CONFIG['camera_index'], CLIENT_CONFIG['camera_resolution']
    )

    try:
        calibrator.run()
    except KeyboardInterrupt:
        print('\n👋 Calibration cancelled')
    except Exception as e:
        print(f'❌ Error: {e}')
        raise


if __name__ == '__main__':
    main()
