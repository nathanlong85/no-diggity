"""
Model loader for No Diggity detection server.

Auto-detects available hardware (GPU/CPU) and loads the most appropriate
object detection model.
"""

import multiprocessing
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np


class ModelType:
    """Model type constants"""

    YOLO_V8 = 'yolov8'
    MOBILENET_SSD = 'mobilenet'


class DetectionModel:
    """Base class for detection models"""

    def __init__(self, model_type: str, confidence_threshold: float = 0.5):
        self.model_type = model_type
        self.confidence_threshold = confidence_threshold
        self.dog_class_id = None

    def detect(self, frame: np.ndarray) -> list:
        """
        Run detection on a frame.

        Args:
            frame: OpenCV image (numpy array)

        Returns:
            List of detections with format:
            [{'x1': int, 'y1': int, 'x2': int, 'y2': int,
              'confidence': float, 'class_id': int, 'class_name': str}]
        """
        raise NotImplementedError


class YOLOv8Model(DetectionModel):
    """YOLOv8 detection model"""

    def __init__(self, model_size: str = 'n', confidence_threshold: float = 0.5):
        super().__init__(ModelType.YOLO_V8, confidence_threshold)

        print(f'📦 Loading YOLOv8{model_size}...')

        try:
            from ultralytics import YOLO

            self.model = YOLO(f'yolov8{model_size}.pt')
            self.dog_class_id = 16  # COCO dataset dog class
            print(f'✓ YOLOv8{model_size} loaded successfully')

        except ImportError:
            raise RuntimeError(
                'ultralytics not installed. Run: pip install ultralytics'
            )

    def detect(self, frame: np.ndarray) -> list:
        """Run YOLOv8 detection"""
        # Run inference
        results = self.model(frame, verbose=False)[0]

        detections = []

        # Parse results
        for box in results.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            # Only process dogs above confidence threshold
            if (
                class_id == self.dog_class_id
                and confidence >= self.confidence_threshold
            ):
                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                detections.append(
                    {
                        'x1': int(x1),
                        'y1': int(y1),
                        'x2': int(x2),
                        'y2': int(y2),
                        'confidence': confidence,
                        'class_id': class_id,
                        'class_name': 'dog',
                    }
                )

        return detections


class MobileNetSSDModel(DetectionModel):
    """MobileNet-SSD detection model"""

    def __init__(self, confidence_threshold: float = 0.5):
        super().__init__(ModelType.MOBILENET_SSD, confidence_threshold)

        print('📦 Loading MobileNet-SSD...')

        # Model paths
        prototxt_path = Path('deploy.prototxt')
        model_path = Path('mobilenet_iter_73000.caffemodel')

        # Download if not exists
        self._download_model_files(prototxt_path, model_path)

        # Load model
        self.net = cv2.dnn.readNetFromCaffe(str(prototxt_path), str(model_path))
        self.dog_class_id = 12  # MobileNet-SSD dog class
        print('✓ MobileNet-SSD loaded successfully')

    def _download_model_files(self, prototxt_path: Path, model_path: Path):
        """Download MobileNet-SSD model files if they don't exist"""
        prototxt_url = 'https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt'
        model_url = 'https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel'

        if not prototxt_path.exists():
            print(f'  Downloading {prototxt_path}...')
            urllib.request.urlretrieve(prototxt_url, prototxt_path)
            print('  ✓ Downloaded prototxt')

        if not model_path.exists():
            print(f'  Downloading {model_path} (~23MB)...')
            urllib.request.urlretrieve(model_url, model_path)
            print('  ✓ Downloaded model weights')

    def detect(self, frame: np.ndarray) -> list:
        """Run MobileNet-SSD detection"""
        height, width = frame.shape[:2]

        # Prepare frame for MobileNet-SSD
        blob = cv2.dnn.blobFromImage(
            frame, 0.007843, (300, 300), (127.5, 127.5, 127.5), False
        )
        self.net.setInput(blob)
        detections_raw = self.net.forward()

        detections = []

        # Loop through detections
        for i in range(detections_raw.shape[2]):
            confidence = detections_raw[0, 0, i, 2]

            if confidence > self.confidence_threshold:
                class_id = int(detections_raw[0, 0, i, 1])

                # Check if it's a dog
                if class_id == self.dog_class_id:
                    # Get bounding box coordinates (normalized 0-1)
                    box = detections_raw[0, 0, i, 3:7] * np.array(
                        [width, height, width, height]
                    )
                    x1, y1, x2, y2 = box.astype(int)

                    detections.append(
                        {
                            'x1': int(x1),
                            'y1': int(y1),
                            'x2': int(x2),
                            'y2': int(y2),
                            'confidence': float(confidence),
                            'class_id': class_id,
                            'class_name': 'dog',
                        }
                    )

        return detections


def detect_hardware():
    """
    Detect available hardware capabilities.

    Returns:
        Dict with hardware info
    """
    hardware = {
        'cuda_available': False,
        'cpu_cores': multiprocessing.cpu_count(),
        'recommended_model': None,
    }

    # Check for CUDA
    try:
        import torch

        hardware['cuda_available'] = torch.cuda.is_available()

        if hardware['cuda_available']:
            hardware['cuda_device'] = torch.cuda.get_device_name(0)
    except ImportError:
        pass

    # Recommend model based on hardware
    if hardware['cuda_available']:
        hardware['recommended_model'] = 'yolov8s'  # Larger model for GPU
    elif hardware['cpu_cores'] >= 4:
        hardware['recommended_model'] = 'yolov8n'  # Nano model for CPU
    else:
        hardware['recommended_model'] = 'mobilenet'  # Fallback for weak CPUs

    return hardware


def load_model(
    preference: str = 'auto', confidence_threshold: float = 0.5
) -> DetectionModel:
    """
    Load the most appropriate detection model.

    Args:
        preference: 'auto', 'yolo', or 'mobilenet'
        confidence_threshold: Minimum confidence for detections

    Returns:
        DetectionModel instance
    """
    hardware = detect_hardware()

    print('\n🔍 Hardware Detection:')
    print(f'   CPU cores: {hardware["cpu_cores"]}')
    print(f'   CUDA available: {hardware["cuda_available"]}')
    if hardware['cuda_available']:
        print(f'   GPU: {hardware["cuda_device"]}')
    print(f'   Recommended: {hardware["recommended_model"]}')

    # Determine which model to load
    if preference == 'auto':
        model_choice = hardware['recommended_model']
    elif preference in ['yolo', 'yolov8']:
        model_choice = 'yolov8n'
    elif preference == 'mobilenet':
        model_choice = 'mobilenet'
    else:
        print(f'⚠️  Unknown preference: {preference}, using auto')
        model_choice = hardware['recommended_model']

    print(f'\n🎯 Loading model: {model_choice}')

    # Load the model
    if model_choice in ['yolov8n', 'yolov8s']:
        size = model_choice[-1]  # 'n' or 's'
        return YOLOv8Model(model_size=size, confidence_threshold=confidence_threshold)
    else:
        return MobileNetSSDModel(confidence_threshold=confidence_threshold)
