import time
from typing import Optional, Dict, Any, List, Tuple
import cv2
import numpy as np

from .config import config
from .stream import VideoStream
from .pose_detector import PoseDetector
from .behavior_analyzer import BehaviorAnalyzer
from .zone_manager import ZoneManager
from .alert_recorder import AlertRecorder

# Skeleton Joint Pairs for COCO 17 Keypoints
SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),      # Head
    (5, 6),                              # Shoulders
    (5, 7), (7, 9),                      # Left Arm
    (6, 8), (8, 10),                     # Right Arm
    (5, 11), (6, 12), (11, 12),          # Torso
    (11, 13), (13, 15),                  # Left Leg
    (12, 14), (14, 16)                   # Right Leg
]

class RestEyeEngine:
    def __init__(self, source: str = None):
        self.source = source or config.video_source
        self.stream = VideoStream(self.source, loop=config.loop_video, target_fps=config.target_fps)
        self.pose_detector = PoseDetector(conf=config.conf_threshold)
        self.behavior_analyzer = BehaviorAnalyzer()
        self.zone_manager = ZoneManager()
        self.alert_recorder = AlertRecorder(fps=config.target_fps)
        
        # Telemetry stats
        self.fps = 0.0
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.active_persons: List[Dict[str, Any]] = []
        
        # Overlay toggles
        self.show_skeleton = True
        self.show_boxes = True
        self.show_zones = True
        self.show_hud = True

    def start(self):
        self.stream.start()
        print(f"[RestEyeEngine] Engine started with source: {self.source}")
        return self

    def stop(self):
        self.stream.stop()
        print("[RestEyeEngine] Engine stopped.")

    def change_source(self, new_source: str):
        self.source = new_source
        self.stream.change_source(new_source)

    def process_frame(self) -> Tuple[bool, Optional[np.ndarray], List[Dict[str, Any]]]:
        """
        Grabs frame, performs inference, detects eating/posture, records alerts, and draws overlays.
        """
        ret, frame = self.stream.read()
        if not ret or frame is None:
            return False, None, []

        h, w, _ = frame.shape
        self.alert_recorder.add_frame(frame)

        # 1. Pose Tracking
        detected_persons = self.pose_detector.detect_and_track(frame)

        # 2. Behavior Analysis (Eating, Sitting, Standing, Loitering)
        analyzed_persons = self.behavior_analyzer.analyze(detected_persons, w, h)
        
        # 3. Zone Matching & Alert Evaluation
        for person in analyzed_persons:
            bbox = person["bbox"]
            pid = person["track_id"]
            
            # Find which restricted zones person is in
            in_zones = self.zone_manager.check_person_in_zones(bbox, w, h)
            person["zones"] = [z["name"] for z in in_zones]
            person["in_restricted_zone"] = len(in_zones) > 0

            # Eating Alert Trigger
            if person.get("trigger_new_eating_alert"):
                zone_label = ", ".join(person["zones"]) if person["zones"] else "Kitchen / Prep Area"
                annotated_snapshot = self.draw_overlays(frame.copy(), [person], h, w, highlight_pid=pid)
                self.alert_recorder.trigger_incident(
                    alert_type="UNAUTHORIZED_EATING",
                    person_id=pid,
                    zone_name=zone_label,
                    annotated_frame=annotated_snapshot,
                    details={
                        "posture": person["posture"],
                        "dwell_sec": person["eating_dwell_sec"],
                        "dist_ratio": person["wrist_mouth_dist_ratio"],
                        "cycles": person["eating_cycles"]
                    }
                )

        self.active_persons = analyzed_persons

        # Calculate FPS
        self.frame_count += 1
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = round(self.frame_count / (now - self.last_fps_time), 1)
            self.frame_count = 0
            self.last_fps_time = now

        # 4. Generate Annotated Display Frame
        annotated_frame = self.draw_overlays(frame.copy(), analyzed_persons, h, w)
        return True, annotated_frame, analyzed_persons

    def draw_overlays(
        self,
        frame: np.ndarray,
        persons: List[Dict[str, Any]],
        h: int,
        w: int,
        highlight_pid: Optional[int] = None
    ) -> np.ndarray:
        overlay = frame.copy()

        # 1. Draw Restricted Zones
        if self.show_zones:
            for zone in self.zone_manager.get_zones():
                poly_norm = zone.get("polygon", [])
                if len(poly_norm) >= 3:
                    pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in poly_norm], np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    
                    # Fill semi-transparent zone
                    color_bgr = (40, 40, 230) if zone.get("type") == "restricted_eating" else (240, 180, 20)
                    cv2.fillPoly(overlay, [pts], color_bgr)
                    cv2.polylines(frame, [pts], isClosed=True, color=color_bgr, thickness=2)
                    
                    # Label
                    lbl_x, lbl_y = int(poly_norm[0][0] * w), max(20, int(poly_norm[0][1] * h) - 8)
                    cv2.putText(frame, zone.get("name", "Zone"), (lbl_x, lbl_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            # Blend zones
            cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        # 2. Draw Persons & Keypoints
        for person in persons:
            pid = person["track_id"]
            bbox = [int(v) for v in person["bbox"]]
            x1, y1, x2, y2 = bbox
            is_eating = person.get("is_eating", False)
            is_hand_near_mouth = person.get("is_hand_near_mouth", False)
            posture = person.get("posture", "STANDING")
            posture_sec = person.get("posture_duration_sec", 0.0)
            
            # Status colors: Green (Normal), Yellow (Hand near mouth), Red (Eating)
            if is_eating:
                box_color = (0, 0, 240)  # Red
                status_text = "EATING DETECTED!"
            elif is_hand_near_mouth:
                box_color = (0, 190, 255)  # Orange / Yellow
                status_text = "Hand Near Mouth"
            else:
                box_color = (0, 220, 100)  # Green
                status_text = "Normal"

            if highlight_pid is not None and pid == highlight_pid:
                box_color = (0, 0, 255)
                status_text = "INCIDENT SNAPSHOT"

            # Draw Bounding Box
            if self.show_boxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                
                # Tag label
                label = f"#{pid} [{posture} {int(posture_sec)}s] - {status_text}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(frame, (x1, max(0, y1 - 24)), (x1 + tw + 10, y1), box_color, -1)
                cv2.putText(frame, label, (x1 + 5, max(15, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0) if is_hand_near_mouth else (255, 255, 255), 2)

            # Draw Skeleton
            if self.show_skeleton:
                kpts = person.get("keypoints", [])
                # Draw connections
                for p1_idx, p2_idx in SKELETON_EDGES:
                    if p1_idx < len(kpts) and p2_idx < len(kpts):
                        p1, p2 = kpts[p1_idx], kpts[p2_idx]
                        if len(p1) >= 2 and len(p2) >= 2:
                            conf1 = p1[2] if len(p1) >= 3 else 1.0
                            conf2 = p2[2] if len(p2) >= 3 else 1.0
                            if conf1 > 0.25 and conf2 > 0.25:
                                pt1 = (int(p1[0]), int(p1[1]))
                                pt2 = (int(p2[0]), int(p2[1]))
                                edge_color = (0, 0, 255) if is_eating else (255, 200, 50)
                                cv2.line(frame, pt1, pt2, edge_color, 2)

                # Draw Keypoint Dots
                for kp in kpts:
                    if len(kp) >= 2:
                        conf = kp[2] if len(kp) >= 3 else 1.0
                        if conf > 0.25:
                            cv2.circle(frame, (int(kp[0]), int(kp[1])), 4, (0, 255, 255), -1)

        # 3. Draw Telemetry HUD Header
        if self.show_hud:
            cv2.rectangle(frame, (0, 0), (w, 36), (15, 15, 20), -1)
            hud_text = f"REST-EYE SENTRY  |  {config.camera_name}  |  FPS: {self.fps}  |  Personnel: {len(persons)}  |  Alerts: {len(self.alert_recorder.alerts)}"
            cv2.putText(frame, hud_text, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 180), 2)
            
            # Live clock
            clock_text = time.strftime("%Y-%m-%d %H:%M:%S")
            (cw, _), _ = cv2.getTextSize(clock_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.putText(frame, clock_text, (w - cw - 16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        return frame
