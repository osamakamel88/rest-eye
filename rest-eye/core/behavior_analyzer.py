import math
import time
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from .config import config
from .pose_detector import (
    NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR,
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST, LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE
)

def euclidean_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def calculate_angle(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
    """Calculates the angle at point b (in degrees) given points a, b, c."""
    try:
        ba = (a[0] - b[0], a[1] - b[1])
        bc = (c[0] - b[0], c[1] - b[1])
        dot_product = ba[0] * bc[0] + ba[1] * bc[1]
        mag_ba = math.hypot(*ba)
        mag_bc = math.hypot(*bc)
        if mag_ba * mag_bc == 0:
            return 180.0
        cosine_angle = dot_product / (mag_ba * mag_bc)
        cosine_angle = max(-1.0, min(1.0, cosine_angle))
        angle = math.degrees(math.acos(cosine_angle))
        return angle
    except Exception:
        return 180.0

class PersonSession:
    def __init__(self, track_id: int):
        self.track_id = track_id
        self.first_seen = time.time()
        self.last_seen = time.time()
        
        # Posture Accumulators
        self.current_posture = "STANDING"
        self.posture_start_time = time.time()
        self.total_standing_sec = 0.0
        self.total_sitting_sec = 0.0
        self.total_bending_sec = 0.0
        
        # Position tracking for Loitering
        self.last_pos = (0.0, 0.0)
        self.stationary_start_time = time.time()
        self.is_loitering = False
        
        # Eating Behavior State Machine
        self.is_hand_near_mouth = False
        self.hand_near_mouth_start: Optional[float] = None
        self.eating_cycles_count = 0
        self.last_eating_alert_time: float = 0.0
        self.eating_alert_triggered = False
        self.hand_mouth_min_dist_ratio = 1.0

    def update_time(self, current_time: float):
        dt = current_time - self.last_seen
        self.last_seen = current_time
        
        # Accumulate time for current posture
        if self.current_posture == "STANDING":
            self.total_standing_sec += dt
        elif self.current_posture == "SITTING":
            self.total_sitting_sec += dt
        elif self.current_posture == "BENDING":
            self.total_bending_sec += dt

class BehaviorAnalyzer:
    def __init__(self):
        self.sessions: Dict[int, PersonSession] = {}
        self.cleanup_timeout = 30.0  # Remove track after 30s of disappearance

    def _get_kpt(self, kpts: List[Any], idx: int) -> Optional[Tuple[float, float, float]]:
        """Returns (x, y, conf) if valid, else None."""
        if not kpts or idx >= len(kpts):
            return None
        pt = kpts[idx]
        if len(pt) >= 3:
            x, y, conf = pt[0], pt[1], pt[2]
            if conf > 0.25:
                return (x, y, conf)
        elif len(pt) >= 2:
            return (pt[0], pt[1], 1.0)
        return None

    def analyze(self, detected_persons: List[Dict[str, Any]], frame_w: int, frame_h: int) -> List[Dict[str, Any]]:
        current_time = time.time()
        analyzed_results = []
        
        # Cleanup old sessions
        stale_ids = [pid for pid, s in self.sessions.items() if current_time - s.last_seen > self.cleanup_timeout]
        for pid in stale_ids:
            del self.sessions[pid]

        for person in detected_persons:
            pid = person["track_id"]
            kpts = person.get("keypoints", [])
            bbox = person["bbox"]

            if pid not in self.sessions:
                self.sessions[pid] = PersonSession(pid)
            session = self.sessions[pid]
            session.update_time(current_time)

            # 1. Analyze Posture (Sitting vs Standing vs Bending)
            posture_info = self._analyze_posture(kpts, bbox)
            new_posture = posture_info["posture"]
            if new_posture != session.current_posture:
                session.current_posture = new_posture
                session.posture_start_time = current_time

            # 2. Analyze Loitering / Inactivity
            center_x = (bbox[0] + bbox[2]) / 2.0
            center_y = (bbox[1] + bbox[3]) / 2.0
            pos_dist = euclidean_dist((center_x, center_y), session.last_pos)
            if pos_dist < 25.0:  # Within 25px radius
                stationary_duration = current_time - session.stationary_start_time
                if stationary_duration > config.loitering_alert_seconds:
                    session.is_loitering = True
            else:
                session.last_pos = (center_x, center_y)
                session.stationary_start_time = current_time
                session.is_loitering = False

            # 3. Analyze Eating / Grazing Action
            eating_info = self._analyze_eating_action(kpts, session, current_time)

            # Package analysis output for this person
            result = {
                "track_id": pid,
                "bbox": bbox,
                "confidence": person["confidence"],
                "keypoints": kpts,
                "posture": session.current_posture,
                "posture_duration_sec": round(current_time - session.posture_start_time, 1),
                "total_standing_sec": round(session.total_standing_sec, 1),
                "total_sitting_sec": round(session.total_sitting_sec, 1),
                "is_loitering": session.is_loitering,
                "is_hand_near_mouth": eating_info["is_hand_near_mouth"],
                "eating_dwell_sec": round(eating_info["dwell_duration"], 2),
                "is_eating": eating_info["is_eating"],
                "trigger_new_eating_alert": eating_info["trigger_alert"],
                "eating_cycles": session.eating_cycles_count,
                "wrist_mouth_dist_ratio": round(eating_info["min_dist_ratio"], 3)
            }
            analyzed_results.append(result)

        return analyzed_results

    def _analyze_posture(self, kpts: List[Any], bbox: List[float]) -> Dict[str, Any]:
        """Calculates sitting vs standing. Kitchen counters occlude legs, so default to STANDING unless knees clearly bent."""
        l_hip = self._get_kpt(kpts, LEFT_HIP)
        r_hip = self._get_kpt(kpts, RIGHT_HIP)
        l_knee = self._get_kpt(kpts, LEFT_KNEE)
        r_knee = self._get_kpt(kpts, RIGHT_KNEE)
        l_ankle = self._get_kpt(kpts, LEFT_ANKLE)
        r_ankle = self._get_kpt(kpts, RIGHT_ANKLE)

        knee_angles = []
        if l_hip and l_knee and l_ankle:
            knee_angles.append(calculate_angle((l_hip[0], l_hip[1]), (l_knee[0], l_knee[1]), (l_ankle[0], l_ankle[1])))
        if r_hip and r_knee and r_ankle:
            knee_angles.append(calculate_angle((r_hip[0], r_hip[1]), (r_knee[0], r_knee[1]), (r_ankle[0], r_ankle[1])))

        # If knees are clearly visible and bent sharply, person is sitting
        if knee_angles:
            avg_knee_angle = sum(knee_angles) / len(knee_angles)
            if avg_knee_angle < config.sitting_knee_angle_max:
                return {"posture": "SITTING", "knee_angle": avg_knee_angle}
            else:
                return {"posture": "STANDING", "knee_angle": avg_knee_angle}

        # In a restaurant kitchen, prep counters hide legs. People standing at counters are STANDING.
        return {"posture": "STANDING", "knee_angle": None}

    def _analyze_eating_action(self, kpts: List[Any], session: PersonSession, current_time: float) -> Dict[str, Any]:
        """
        Robustly detects Eating and Drinking gestures:
        - Hand raised above elbow (wrist_y < elbow_y)
        - Hand within mouth / lower-face radius
        - Scale-normalized by shoulder width or head size
        """
        nose = self._get_kpt(kpts, NOSE)
        l_eye = self._get_kpt(kpts, LEFT_EYE)
        r_eye = self._get_kpt(kpts, RIGHT_EYE)
        l_ear = self._get_kpt(kpts, LEFT_EAR)
        r_ear = self._get_kpt(kpts, RIGHT_EAR)
        l_shoulder = self._get_kpt(kpts, LEFT_SHOULDER)
        r_shoulder = self._get_kpt(kpts, RIGHT_SHOULDER)
        l_elbow = self._get_kpt(kpts, LEFT_ELBOW)
        r_elbow = self._get_kpt(kpts, RIGHT_ELBOW)
        l_wrist = self._get_kpt(kpts, LEFT_WRIST)
        r_wrist = self._get_kpt(kpts, RIGHT_WRIST)

        # 1. Determine Head & Mouth Anchor
        mouth_x, mouth_y = 0.0, 0.0
        head_radius = 45.0  # default fallback

        if nose:
            mouth_x, mouth_y = nose[0], nose[1] + 15.0
            if l_eye and r_eye:
                eye_dist = euclidean_dist((l_eye[0], l_eye[1]), (r_eye[0], r_eye[1]))
                head_radius = max(35.0, eye_dist * 2.2)
        elif l_eye and r_eye:
            mouth_x = (l_eye[0] + r_eye[0]) / 2.0
            mouth_y = (l_eye[1] + r_eye[1]) / 2.0 + 25.0
            head_radius = max(35.0, euclidean_dist((l_eye[0], l_eye[1]), (r_eye[0], r_eye[1])) * 2.2)
        elif l_shoulder and r_shoulder:
            mouth_x = (l_shoulder[0] + r_shoulder[0]) / 2.0
            mouth_y = (l_shoulder[1] + r_shoulder[1]) / 2.0 - 45.0
            head_radius = max(40.0, euclidean_dist((l_shoulder[0], l_shoulder[1]), (r_shoulder[0], r_shoulder[1])) * 0.45)
        else:
            return {
                "is_hand_near_mouth": False,
                "dwell_duration": 0.0,
                "is_eating": False,
                "trigger_alert": False,
                "min_dist_ratio": 1.0
            }

        # Reference scale: shoulder width
        ref_scale = 100.0
        if l_shoulder and r_shoulder:
            ref_scale = max(50.0, euclidean_dist((l_shoulder[0], l_shoulder[1]), (r_shoulder[0], r_shoulder[1])))
        else:
            ref_scale = head_radius * 2.0

        # Check left and right hands
        hand_near = False
        min_dist_ratio = 2.0

        for wrist, elbow in [(l_wrist, l_elbow), (r_wrist, r_elbow)]:
            if not wrist:
                continue
            
            d_mouth = euclidean_dist((wrist[0], wrist[1]), (mouth_x, mouth_y))
            ratio = d_mouth / ref_scale
            if ratio < min_dist_ratio:
                min_dist_ratio = ratio

            # Condition 1: Hand in mouth/face radius
            is_in_face_zone = d_mouth <= (head_radius * 1.6) or ratio <= 0.58

            # Condition 2: Hand is raised (wrist higher than or level with elbow)
            hand_raised = True
            if elbow:
                hand_raised = wrist[1] <= (elbow[1] + 25.0)

            if is_in_face_zone and hand_raised:
                hand_near = True

        session.hand_mouth_min_dist_ratio = min_dist_ratio
        dwell_duration = 0.0
        is_eating = False
        trigger_alert = False

        if hand_near:
            if not session.is_hand_near_mouth:
                session.is_hand_near_mouth = True
                session.hand_near_mouth_start = current_time

            dwell_duration = current_time - (session.hand_near_mouth_start or current_time)

            # Trigger eating if hand stays near mouth for >= 0.4s (instant for drinking/snacking)
            if dwell_duration >= 0.4 or min_dist_ratio <= 0.40:
                is_eating = True
                if (current_time - session.last_eating_alert_time) > config.eating_cooldown_seconds:
                    session.last_eating_alert_time = current_time
                    session.eating_cycles_count += 1
                    trigger_alert = True
        else:
            session.is_hand_near_mouth = False
            session.hand_near_mouth_start = None

        return {
            "is_hand_near_mouth": hand_near,
            "dwell_duration": dwell_duration,
            "is_eating": is_eating,
            "trigger_alert": trigger_alert,
            "min_dist_ratio": min_dist_ratio
        }
