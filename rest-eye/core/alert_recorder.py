import os
import time
import json
import threading
from collections import deque
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
from .config import config, ALERTS_DIR

class AlertRecorder:
    def __init__(self, max_buffer_seconds: float = 8.0, fps: int = 25):
        self.fps = fps
        self.max_buffer_len = int(max_buffer_seconds * fps)
        self.frame_buffer = deque(maxlen=self.max_buffer_len)
        self.alerts_log_file = ALERTS_DIR / "alerts_log.json"
        self.alerts: List[Dict[str, Any]] = self._load_alerts()
        self.lock = threading.Lock()

    def _load_alerts(self) -> List[Dict[str, Any]]:
        if self.alerts_log_file.exists():
            try:
                with open(self.alerts_log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AlertRecorder] Error loading alerts log: {e}")
        return []

    def _save_alerts(self):
        try:
            with open(self.alerts_log_file, "w", encoding="utf-8") as f:
                json.dump(self.alerts, f, indent=2)
        except Exception as e:
            print(f"[AlertRecorder] Error saving alerts log: {e}")

    def add_frame(self, frame: np.ndarray):
        """Adds a raw frame (copy) to the rolling buffer."""
        if frame is not None:
            # Shallow copy or clone to avoid mutations
            self.frame_buffer.append((time.time(), frame.copy()))

    def get_alerts(self) -> List[Dict[str, Any]]:
        with self.lock:
            # Return copy in reverse chronological order
            return list(reversed(self.alerts))

    def trigger_incident(
        self,
        alert_type: str,  # "EATING_VIOLATION", "LOITERING", "UNAUTHORIZED_ZONE"
        person_id: int,
        zone_name: str,
        annotated_frame: np.ndarray,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Creates an alert, saves high-res snapshot, and records 8-second MP4 clip.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        alert_id = f"alert_{timestamp}_{person_id}_{int(time.time() * 1000) % 1000}"
        
        snapshot_filename = f"{alert_id}.jpg"
        video_filename = f"{alert_id}.mp4"
        snapshot_path = ALERTS_DIR / snapshot_filename
        video_path = ALERTS_DIR / video_filename

        # Save Snapshot
        if annotated_frame is not None:
            cv2.imwrite(str(snapshot_path), annotated_frame)

        # Pre-buffered frames snapshot for clip
        with self.lock:
            buffered_frames = [f[1] for f in self.frame_buffer]

        # Spawn recording thread to capture the next post_seconds
        thread = threading.Thread(
            target=self._record_clip,
            args=(buffered_frames, video_path, config.clip_post_seconds),
            daemon=True
        )
        thread.start()

        alert_entry = {
            "id": alert_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "unix_time": time.time(),
            "type": alert_type,
            "person_id": person_id,
            "zone": zone_name,
            "snapshot_url": f"/api/alerts/{snapshot_filename}",
            "video_url": f"/api/alerts/{video_filename}",
            "details": details,
            "status": "UNREVIEWED"
        }

        with self.lock:
            self.alerts.append(alert_entry)
            self._save_alerts()

        print(f"[AlertRecorder] >>> ALERT TRIGGERED: {alert_type} for Person #{person_id} in {zone_name}")
        return alert_entry

    def _record_clip(self, pre_frames: List[np.ndarray], output_path: Path, post_seconds: float):
        """Asynchronously writes pre-frames + captures upcoming frames for MP4 export."""
        try:
            time.sleep(post_seconds)  # Wait for post frames to populate buffer
            
            # Combine pre-frames and recent post-frames
            all_frames = []
            with self.lock:
                all_frames = [f[1] for f in self.frame_buffer]

            if not all_frames:
                return

            h, w, _ = all_frames[0].shape
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, self.fps, (w, h))

            for frame in all_frames:
                writer.write(frame)

            writer.release()
            print(f"[AlertRecorder] Incident clip saved successfully: {output_path.name}")
        except Exception as e:
            print(f"[AlertRecorder] Failed to record clip: {e}")
