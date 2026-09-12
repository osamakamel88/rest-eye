import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Project base paths
BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env from rest-eye directory or workspace root
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

DATA_DIR = BASE_DIR / "data"
ALERTS_DIR = DATA_DIR / "alerts"
MODELS_DIR = DATA_DIR / "models"
UPLOADS_DIR = DATA_DIR / "uploads"
DB_DIR = DATA_DIR / "db"
ZONES_FILE = DATA_DIR / "zones.json"
NOTES_FILE = DATA_DIR / "audit_notes.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
ALERTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SAMPLE_VIDEO = r"D:\Downloads\a_restaurant_back_kitchen_wher.mp4"

@dataclass
class RestEyeConfig:
    # Video Source
    video_source: str = os.getenv("DEFAULT_VIDEO_SOURCE", DEFAULT_SAMPLE_VIDEO)
    camera_name: str = os.getenv("CAMERA_NAME", "Kitchen Cam 01")
    target_fps: int = int(os.getenv("TARGET_FPS", "25"))
    loop_video: bool = True
    
    # AI Pose Model
    pose_model: str = os.getenv("POSE_MODEL", "yolo11n-pose.pt")
    conf_threshold: float = float(os.getenv("CONF_THRESHOLD", "0.35"))
    device: str = os.getenv("AI_DEVICE", "auto")
    
    # Eating Behavior Detection Parameters
    wrist_mouth_dist_ratio: float = 0.38
    eating_dwell_seconds: float = 1.0
    eating_cooldown_seconds: float = 8.0
    
    # Posture Tracking (Sitting vs Standing)
    sitting_knee_angle_max: float = 125.0
    sitting_torso_ratio_min: float = 1.10
    loitering_alert_seconds: float = 120.0
    
    # Video Incident Recording
    clip_pre_seconds: float = 4.0
    clip_post_seconds: float = 4.0
    
    # Web & API
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8000"))
    jwt_secret: str = os.getenv("JWT_SECRET", "recode-developments-rest-eye-super-secret-key-2026")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    # Multi-Tenant Database (Supabase / PostgreSQL / SQLite Fallback)
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR / 'rest_eye_saas.db'}")
    
    # Cloudflare R2 / AWS S3 Object Storage
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "rest-eye-incidents")
    r2_public_url: str = os.getenv("R2_PUBLIC_URL", "")  # e.g., https://pub-xxx.r2.dev or custom cdn
    
    # Automated Alert Dispatchers
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    whatsapp_api_url: str = os.getenv("WHATSAPP_API_URL", "")
    whatsapp_token: str = os.getenv("WHATSAPP_TOKEN", "")
    whatsapp_phone_number: str = os.getenv("WHATSAPP_PHONE_NUMBER", "")

config = RestEyeConfig()
