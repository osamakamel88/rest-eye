import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Project base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ALERTS_DIR = DATA_DIR / "alerts"
MODELS_DIR = DATA_DIR / "models"
UPLOADS_DIR = DATA_DIR / "uploads"
ZONES_FILE = DATA_DIR / "zones.json"
NOTES_FILE = DATA_DIR / "audit_notes.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
ALERTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SAMPLE_VIDEO = r"D:\Downloads\a_restaurant_back_kitchen_wher.mp4"

@dataclass
class RestEyeConfig:
    # Video Source
    video_source: str = DEFAULT_SAMPLE_VIDEO
    camera_name: str = "Kitchen Cam 01"
    target_fps: int = 25
    loop_video: bool = True
    
    # AI Pose Model
    pose_model: str = "yolo11n-pose.pt"  # Will fallback to yolov8n-pose.pt if needed
    conf_threshold: float = 0.35
    device: str = "auto"  # 'cuda', 'cpu', or 'auto'
    
    # Eating Behavior Detection Parameters
    wrist_mouth_dist_ratio: float = 0.38    # Hand-to-mouth distance normalized by torso length
    eating_dwell_seconds: float = 1.0       # Seconds hand stays in mouth zone
    eating_cooldown_seconds: float = 8.0    # Seconds before triggering duplicate alert for same person
    
    # Posture Tracking (Sitting vs Standing)
    sitting_knee_angle_max: float = 125.0   # Knee angle in degrees for sitting
    sitting_torso_ratio_min: float = 1.10   # Torso-to-lower-body vertical compression
    loitering_alert_seconds: float = 120.0  # Alert if stationary/idle in restricted zone > 2 mins
    
    # Video Incident Recording
    clip_pre_seconds: float = 4.0          # Buffer before incident
    clip_post_seconds: float = 4.0         # Buffer after incident
    
    # Web & Streaming
    web_host: str = "0.0.0.0"
    web_port: int = 8000

config = RestEyeConfig()
