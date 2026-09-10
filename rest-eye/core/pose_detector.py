import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from pathlib import Path
from .config import config, MODELS_DIR

# COCO 17 Keypoint Indices
NOSE = 0
LEFT_EYE = 1
RIGHT_EYE = 2
LEFT_EAR = 3
RIGHT_EAR = 4
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16

class PoseDetector:
    def __init__(self, model_name: str = None, conf: float = 0.35, device: str = "auto"):
        self.model_name = model_name or config.pose_model
        self.conf = conf
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            print(f"[PoseDetector] Loading YOLO Pose model: {self.model_name}...")
            # If model file is in models directory or default
            try:
                self.model = YOLO(self.model_name)
            except Exception as e:
                print(f"[PoseDetector] Could not load {self.model_name}, falling back to yolov8n-pose.pt: {e}")
                self.model = YOLO("yolov8n-pose.pt")
                
            print("[PoseDetector] Pose Model loaded successfully.")
        except Exception as e:
            print(f"[PoseDetector] Error initializing YOLO: {e}")
            self.model = None

    def detect_and_track(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs YOLO pose detection and tracking on a single frame.
        Returns a list of detected persons with track_id, bbox, and keypoints.
        """
        if self.model is None or frame is None:
            return []

        try:
            # Run tracking with ByteTrack
            results = self.model.track(
                source=frame,
                persist=True,
                conf=self.conf,
                verbose=False,
                tracker="bytetrack.yaml"
            )
            
            detected_persons = []
            if not results or len(results) == 0:
                return []

            res = results[0]
            boxes = res.boxes
            keypoints_obj = res.keypoints

            if boxes is None or len(boxes) == 0:
                return []

            # Extract data
            xyxy = boxes.xyxy.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()
            
            # Track IDs may be None if tracker is initializing
            if boxes.id is not None:
                track_ids = boxes.id.int().cpu().numpy()
            else:
                track_ids = np.arange(len(boxes))

            # Keypoints: shape (N, 17, 2 or 3)
            kpts_data = None
            if keypoints_obj is not None and keypoints_obj.data is not None:
                kpts_data = keypoints_obj.data.cpu().numpy()

            for i in range(len(boxes)):
                pid = int(track_ids[i])
                box = xyxy[i].tolist()
                score = float(confidences[i])
                
                kpts = kpts_data[i].tolist() if kpts_data is not None and i < len(kpts_data) else []

                detected_persons.append({
                    "track_id": pid,
                    "bbox": box,  # [x1, y1, x2, y2]
                    "confidence": score,
                    "keypoints": kpts,  # List of [x, y, conf] or [x, y] for 17 points
                })

            return detected_persons

        except Exception as e:
            print(f"[PoseDetector] Inference error: {e}")
            return []
