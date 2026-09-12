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
from .storage.storage_manager import storage_manager
from .notifications.notifier import alert_notifier
from .db.session import SessionLocal
from .db.crud import record_incident

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
            self.frame_buffer.append((time.time(), frame.copy()))

    def get_alerts(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(reversed(self.alerts))

    def trigger_incident(
        self,
        alert_type: str,
        person_id: int,
        zone_name: str,
        annotated_frame: np.ndarray,
        details: Dict[str, Any],
        org_id: Optional[str] = None,
        camera_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an incident: saves snapshot, records 8-second MP4,
        uploads to Cloudflare R2 / S3, records to DB, and sends Telegram/WhatsApp alert.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        alert_id = f"alert_{timestamp}_{person_id}_{int(time.time() * 1000) % 1000}"
        
        snapshot_filename = f"{alert_id}.jpg"
        video_filename = f"{alert_id}.mp4"
        snapshot_path = ALERTS_DIR / snapshot_filename
        video_path = ALERTS_DIR / video_filename

        # 1. Save Local Snapshot
        if annotated_frame is not None:
            cv2.imwrite(str(snapshot_path), annotated_frame)

        # 2. Get buffered frames for video writer thread
        with self.lock:
            buffered_frames = [f[1] for f in self.frame_buffer]

        # 3. Spawn background thread for video recording & cloud upload & notifications
        thread = threading.Thread(
            target=self._process_incident_media,
            args=(
                alert_id,
                alert_type,
                person_id,
                zone_name,
                snapshot_path,
                video_path,
                details,
                config.clip_post_seconds,
                org_id,
                camera_id
            ),
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

    def _process_incident_media(
        self,
        alert_id: str,
        alert_type: str,
        person_id: int,
        zone_name: str,
        snapshot_path: Path,
        video_path: Path,
        details: Dict[str, Any],
        post_seconds: float,
        org_id: Optional[str] = None,
        camera_id: Optional[str] = None
    ):
        """Asynchronously writes MP4, uploads to Cloudflare R2, saves to DB and dispatches alert"""
        try:
            time.sleep(post_seconds)  # Wait for post-incident frames
            
            # 1. Write MP4 video clip
            all_frames = []
            with self.lock:
                all_frames = [f[1] for f in self.frame_buffer]

            if all_frames:
                h, w, _ = all_frames[0].shape
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(video_path), fourcc, self.fps, (w, h))
                for frame in all_frames:
                    writer.write(frame)
                writer.release()
                print(f"[AlertRecorder] Video clip written: {video_path.name}")

            # 2. Upload to Cloudflare R2 / S3 (or get local URL)
            snapshot_url = storage_manager.upload_file(snapshot_path, f"snapshots/{snapshot_path.name}")
            video_url = storage_manager.upload_file(video_path, f"clips/{video_path.name}") if video_path.exists() else None

            # 3. Save to Multi-Tenant Database
            try:
                db = SessionLocal()
                # If org_id / camera_id not provided, query default demo tenant
                from .db.models import Organization, Camera
                if not org_id:
                    default_org = db.query(Organization).first()
                    org_id = default_org.id if default_org else "default-tenant"
                if not camera_id:
                    default_cam = db.query(Camera).first()
                    camera_id = default_cam.id if default_cam else "default-camera"

                record_incident(
                    db=db,
                    org_id=org_id,
                    camera_id=camera_id,
                    incident_type=alert_type,
                    person_track_id=person_id,
                    zone_name=zone_name,
                    posture=details.get("posture", "STANDING"),
                    dwell_sec=details.get("dwell_sec", 0.0),
                    video_clip_url=video_url or f"/api/alerts/{video_path.name}",
                    snapshot_url=snapshot_url or f"/api/alerts/{snapshot_path.name}",
                    details=details
                )
                db.close()
            except Exception as dbe:
                print(f"[AlertRecorder] DB record error (safe fallback): {dbe}")

            # 4. Dispatch Instant Alert to Telegram and WhatsApp
            alert_notifier.dispatch_incident(
                incident_type=alert_type,
                camera_name=config.camera_name,
                zone_name=zone_name,
                person_id=person_id,
                dwell_sec=details.get("dwell_sec", 0.0),
                photo_path=snapshot_path if snapshot_path.exists() else None,
                video_path=video_path if video_path.exists() else None,
                video_url=video_url
            )

        except Exception as e:
            print(f"[AlertRecorder] Incident media processing error: {e}")
