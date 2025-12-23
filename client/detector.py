"""
Detection logic for No Diggity client.

Handles zone checking, position analysis, and elevated detection logic.
"""

import cv2
import numpy as np


def check_polygon_zones(box: tuple, zones: dict) -> list:
    """
    Check which polygon zones a bounding box overlaps with.

    Args:
        box: (x1, y1, x2, y2) bounding box coordinates
        zones: Dictionary of zone configurations

    Returns:
        List of zone IDs that the box overlaps with
    """
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

    for zone_id, zone in zones.items():
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


def analyze_dog_position(
    box: dict, frame_height: int, zones: dict, min_size_ratio: float
) -> dict:
    """
    Analyze if dog is elevated based on position and size.

    Args:
        box: Detection box dict with keys: x1, y1, x2, y2, confidence, class_id, class_name
        frame_height: Height of the video frame
        zones: Dictionary of zone configurations
        min_size_ratio: Minimum size ratio to consider elevated

    Returns:
        Dictionary with keys:
            - elevated: bool - Whether dog is elevated
            - zones: list - Zone IDs the dog is in
            - top_y: int - Top Y coordinate
            - size_ratio: float - Relative size of dog
    """
    x1, y1, x2, y2 = box['x1'], box['y1'], box['x2'], box['y2']

    dog_top = y1
    box_height = y2 - y1

    # Calculate relative size
    relative_size = box_height / frame_height

    # Check which zones dog is in
    triggered_zones = check_polygon_zones((x1, y1, x2, y2), zones)

    # Check multiple indicators
    is_large_enough = relative_size > min_size_ratio
    in_any_zone = len(triggered_zones) > 0

    return {
        'elevated': is_large_enough and in_any_zone,
        'zones': triggered_zones,
        'top_y': dog_top,
        'size_ratio': relative_size,
    }


def analyze_detections(
    detections: list, frame_height: int, zones: dict, min_size_ratio: float
) -> dict:
    """
    Analyze all detections and return summary.

    Args:
        detections: List of detection boxes from server
        frame_height: Height of the video frame
        zones: Dictionary of zone configurations
        min_size_ratio: Minimum size ratio to consider elevated

    Returns:
        Dictionary with keys:
            - elevated: bool - Any dog is elevated
            - triggered_zones: set - All zones with elevated dogs
            - analyses: list - Individual analysis for each detection
    """
    elevated_detected = False
    all_triggered_zones = set()
    analyses = []

    for detection in detections:
        analysis = analyze_dog_position(detection, frame_height, zones, min_size_ratio)
        analyses.append(analysis)

        if analysis['elevated']:
            elevated_detected = True
            all_triggered_zones.update(analysis['zones'])

    return {
        'elevated': elevated_detected,
        'triggered_zones': all_triggered_zones,
        'analyses': analyses,
    }
