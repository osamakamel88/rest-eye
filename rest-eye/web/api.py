import os
import time
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
from fastapi import FastAPI, HTTPException, Request, Response, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from core.config import config, ALERTS_DIR, UPLOADS_DIR, NOTES_FILE, BASE_DIR, DEFAULT_SAMPLE_VIDEO
from core.engine import RestEyeEngine
from core.db.session import get_db, init_db
from core.db.models import Organization, User, Branch, Camera, Zone, Incident, TenantSettings
from core.db import crud
from core.auth.security import create_access_token, verify_password, get_password_hash
from core.auth.dependencies import get_current_user, get_current_tenant, get_optional_user
from core.storage.storage_manager import storage_manager, StorageManager
from core.notifications.notifier import alert_notifier, AlertNotifier

# Initialize DB tables on startup
init_db()

app = FastAPI(
    title="REST-EYE Enterprise AI Sentry SaaS",
    description="Multi-Tenant CCTV AI Video Analytics Platform for Restaurants",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
engine: Optional[RestEyeEngine] = None

def get_engine() -> RestEyeEngine:
    global engine
    if engine is None:
        engine = RestEyeEngine().start()
    return engine

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class UserRegisterSchema(BaseModel):
    restaurant_name: str
    email: str
    password: str
    full_name: Optional[str] = "مدير التشغيل"

class UserLoginSchema(BaseModel):
    email: str
    password: str

class BranchCreateSchema(BaseModel):
    name: str
    city: Optional[str] = "القاهرة"
    address: Optional[str] = ""

class CameraCreateSchema(BaseModel):
    branch_id: str
    name: str
    stream_source: str
    camera_type: Optional[str] = "KITCHEN"

class ZoneCreateSchema(BaseModel):
    camera_id: str
    name: str
    polygon_points: List[List[float]]
    zone_type: Optional[str] = "restricted_eating"

class CloudSettingsSchema(BaseModel):
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_public_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    whatsapp_api_url: Optional[str] = None
    whatsapp_token: Optional[str] = None
    whatsapp_phone_number: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None

class SourceRequest(BaseModel):
    source: str
    camera_name: Optional[str] = "Kitchen Cam"

class SpeedRequest(BaseModel):
    speed: float

class PlaybackRequest(BaseModel):
    action: str  # "toggle_pause", "rewind"

class AuditNoteModel(BaseModel):
    id: Optional[str] = None
    note: str
    timestamp: Optional[str] = None
    time_offset: Optional[str] = None
    person_id: Optional[int] = None
    zone: Optional[str] = "Kitchen"
    severity: Optional[str] = "NORMAL"

class ZoneModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "restricted_eating"
    color: str = "#ef4444"
    polygon: List[List[float]]

class ToggleRequest(BaseModel):
    skeleton: Optional[bool] = None
    boxes: Optional[bool] = None
    zones: Optional[bool] = None
    hud: Optional[bool] = None

# ==========================================
# AUTH & MULTI-TENANT REST API (v2)
# ==========================================
@app.post("/api/v2/auth/register")
def register_tenant(data: UserRegisterSchema, db: Session = Depends(get_db)):
    """Registers a new restaurant organization and admin user account"""
    existing_user = crud.get_user_by_email(db, data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل")

    slug = data.restaurant_name.lower().replace(" ", "-")[:50]
    org = crud.create_organization(db=db, name=data.restaurant_name, slug=f"{slug}-{int(time.time()) % 1000}")
    user = crud.create_user(
        db=db,
        org_id=org.id,
        email=data.email,
        hashed_pw=get_password_hash(data.password),
        full_name=data.full_name or "المدير العام",
        role="owner"
    )
    # Create a default branch
    crud.create_branch(db=db, org_id=org.id, name="الفرع الرئيسي (Main Branch)")

    token = create_access_token({"sub": user.email, "org_id": org.id, "role": user.role})
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.full_name, "role": user.role},
        "organization": {"id": org.id, "name": org.name, "plan": org.plan_tier}
    }

@app.post("/api/v2/auth/login")
def login_user(data: UserLoginSchema, db: Session = Depends(get_db)):
    """Authenticates user and returns scoped JWT Token"""
    user = crud.get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة (Invalid email or password)")

    token = create_access_token({"sub": user.email, "org_id": user.organization_id, "role": user.role})
    org = crud.get_organization(db, user.organization_id)
    return {
        "status": "success",
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.full_name, "role": user.role},
        "organization": {"id": org.id, "name": org.name, "plan": org.plan_tier} if org else None
    }

@app.get("/api/v2/auth/me")
def get_current_profile(user: User = Depends(get_current_user), tenant: Organization = Depends(get_current_tenant)):
    return {
        "user": {"id": user.id, "email": user.email, "name": user.full_name, "role": user.role},
        "organization": {"id": tenant.id, "name": tenant.name, "plan": tenant.plan_tier, "slug": tenant.slug}
    }

# --- Branches & Cameras ---
@app.get("/api/v2/branches")
def list_tenant_branches(tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    branches = crud.list_branches(db, tenant.id)
    result = []
    for b in branches:
        cams = crud.list_cameras_by_branch(db, b.id)
        result.append({
            "id": b.id,
            "name": b.name,
            "city": b.city,
            "address": b.address,
            "cameras_count": len(cams),
            "cameras": [{"id": c.id, "name": c.name, "type": c.camera_type, "source": c.stream_source} for c in cams]
        })
    return {"status": "success", "branches": result}

@app.post("/api/v2/branches")
def add_tenant_branch(data: BranchCreateSchema, tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    branch = crud.create_branch(db, tenant.id, data.name, data.city or "القاهرة", data.address or "")
    return {"status": "success", "branch": {"id": branch.id, "name": branch.name}}

@app.post("/api/v2/cameras")
def add_branch_camera(data: CameraCreateSchema, tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    branch = crud.get_branch(db, data.branch_id, tenant.id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    cam = crud.create_camera(db, branch.id, data.name, data.stream_source, data.camera_type or "KITCHEN")
    return {"status": "success", "camera": {"id": cam.id, "name": cam.name}}

@app.get("/api/v2/incidents")
def get_tenant_incidents(
    camera_id: Optional[str] = None,
    limit: int = 50,
    tenant: Organization = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    incidents = crud.list_incidents(db, tenant.id, camera_id=camera_id, limit=limit)
    return {
        "status": "success",
        "total": len(incidents),
        "incidents": [
            {
                "id": inc.id,
                "type": inc.incident_type,
                "camera_id": inc.camera_id,
                "person_id": inc.person_track_id,
                "zone_name": inc.zone_name,
                "posture": inc.posture,
                "dwell_sec": inc.dwell_sec,
                "video_url": inc.video_clip_url,
                "snapshot_url": inc.snapshot_url,
                "created_at": inc.created_at.strftime("%Y-%m-%d %H:%M:%S") if inc.created_at else None
            }
            for inc in incidents
        ]
    }

# --- Cloud Integrations (R2, Telegram, WhatsApp) ---
@app.get("/api/v2/settings")
def get_settings(tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    s = crud.get_tenant_settings(db, tenant.id)
    return {
        "status": "success",
        "settings": {
            "r2_configured": bool(s.r2_account_id and s.r2_access_key_id),
            "r2_bucket_name": s.r2_bucket_name or config.r2_bucket_name,
            "r2_public_url": s.r2_public_url or config.r2_public_url,
            "telegram_configured": bool(s.telegram_bot_token and s.telegram_chat_id),
            "telegram_chat_id": s.telegram_chat_id or config.telegram_chat_id,
            "whatsapp_configured": bool(s.whatsapp_api_url and s.whatsapp_phone_number),
            "whatsapp_phone": s.whatsapp_phone_number or config.whatsapp_phone_number
        }
    }

@app.post("/api/v2/settings")
def save_settings(data: CloudSettingsSchema, tenant: Organization = Depends(get_current_tenant), db: Session = Depends(get_db)):
    updated = crud.update_tenant_settings(db, tenant.id, data.model_dump(exclude_unset=True))
    return {"status": "success", "message": "تم حفظ الإعدادات بنجاح"}

@app.post("/api/v2/test-telegram")
async def test_telegram_alert(token: Optional[str] = None, chat_id: Optional[str] = None):
    t = token or config.telegram_bot_token
    c = chat_id or config.telegram_chat_id
    success, msg = await alert_notifier.send_telegram_alert(
        title="تجربة الربط السحابي (Test Alert)",
        message="✅ تم بنجاح ربط نظام REST-EYE مع بوت التليجرام الخاص بك. ستصلك هنا مقاطع وتنبيهات التجاوزات فوراً.",
        token=t,
        chat_id=c
    )
    return {"success": success, "message": msg}

@app.post("/api/v2/test-r2")
def test_r2_storage(account_id: Optional[str] = None, access_key: Optional[str] = None, secret_key: Optional[str] = None, bucket: Optional[str] = None):
    mgr = StorageManager(
        account_id=account_id or config.r2_account_id,
        access_key=access_key or config.r2_access_key_id,
        secret_key=secret_key or config.r2_secret_access_key,
        bucket_name=bucket or config.r2_bucket_name
    )
    success, msg = mgr.test_connection()
    return {"success": success, "message": msg}

# ==========================================
# STREAMING & CONTROL CENTER ENDPOINTS
# ==========================================
def generate_frames():
    eng = get_engine()
    while True:
        ret, frame, persons = eng.process_frame()
        if not ret or frame is None:
            time.sleep(0.04)
            continue

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.012)

@app.get("/api/stream")
def video_stream():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/status")
def get_status():
    eng = get_engine()
    return {
        "status": "ONLINE",
        "fps": eng.fps,
        "source": eng.source,
        "camera_name": config.camera_name,
        "speed": eng.stream.speed_multiplier,
        "is_paused": eng.stream.is_paused,
        "active_person_count": len(eng.active_persons),
        "persons": eng.active_persons,
        "total_alerts": len(eng.alert_recorder.alerts),
        "toggles": {
            "skeleton": eng.show_skeleton,
            "boxes": eng.show_boxes,
            "zones": eng.show_zones,
            "hud": eng.show_hud
        }
    }

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """Uploads any video for fast-forward AI audit"""
    eng = get_engine()
    safe_filename = f"upload_{int(time.time())}_{file.filename.replace(' ', '_')}"
    dest_path = UPLOADS_DIR / safe_filename
    
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    config.camera_name = f"Audit File: {file.filename}"
    eng.change_source(str(dest_path))
    
    return {
        "status": "success",
        "filename": safe_filename,
        "path": str(dest_path),
        "message": "Video uploaded and analysis started!"
    }

@app.post("/api/speed")
def set_playback_speed(req: SpeedRequest):
    eng = get_engine()
    eng.stream.set_speed(req.speed)
    return {"status": "success", "speed": eng.stream.speed_multiplier}

@app.post("/api/playback")
def control_playback(req: PlaybackRequest):
    eng = get_engine()
    if req.action == "toggle_pause":
        paused = eng.stream.toggle_pause()
        return {"status": "success", "is_paused": paused}
    elif req.action == "rewind":
        eng.stream.rewind()
        return {"status": "success", "rewound": True}
    return {"status": "error", "message": "Unknown action"}

@app.get("/api/alerts")
def get_alerts():
    eng = get_engine()
    return {"alerts": eng.alert_recorder.get_alerts()}

@app.get("/api/alerts/{filename}")
def get_alert_asset(filename: str):
    file_path = ALERTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Alert media file not found")
    media_type = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
    return FileResponse(file_path, media_type=media_type)

@app.get("/api/zones")
def get_zones():
    eng = get_engine()
    return {"zones": eng.zone_manager.get_zones()}

@app.post("/api/zones")
def save_zones(zones_data: List[ZoneModel]):
    eng = get_engine()
    raw_zones = [z.model_dump() for z in zones_data]
    for idx, z in enumerate(raw_zones):
        if not z.get("id"):
            z["id"] = f"zone-{idx+1:02d}"
    eng.zone_manager.update_zones(raw_zones)
    return {"status": "success", "zones": eng.zone_manager.get_zones()}

@app.delete("/api/zones/{zone_id}")
def delete_zone(zone_id: str):
    eng = get_engine()
    success = eng.zone_manager.remove_zone(zone_id)
    if not success:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"status": "success", "zones": eng.zone_manager.get_zones()}

@app.post("/api/source")
def switch_source(req: SourceRequest):
    eng = get_engine()
    source_val = req.source
    if source_val.lower() == "sample":
        source_val = DEFAULT_SAMPLE_VIDEO
    elif source_val.isdigit():
        source_val = int(source_val)

    if req.camera_name:
        config.camera_name = req.camera_name

    eng.change_source(source_val)
    return {"status": "success", "current_source": str(eng.source)}

@app.post("/api/toggles")
def update_toggles(req: ToggleRequest):
    eng = get_engine()
    if req.skeleton is not None:
        eng.show_skeleton = req.skeleton
    if req.boxes is not None:
        eng.show_boxes = req.boxes
    if req.zones is not None:
        eng.show_zones = req.zones
    if req.hud is not None:
        eng.show_hud = req.hud
    return {"status": "success"}

# Serve static dashboard files
STATIC_DIR = BASE_DIR / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>REST-EYE Enterprise AI Sentry is running.</h1>"
