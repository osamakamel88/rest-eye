import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import config, ALERTS_DIR, UPLOADS_DIR, NOTES_FILE, BASE_DIR, DEFAULT_SAMPLE_VIDEO
from core.engine import RestEyeEngine
import json
import shutil
from fastapi import UploadFile, File

app = FastAPI(title="Rest-Eye CCTV AI Sentry", version="1.0.0")

# Enable CORS for local dashboards
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

# Data models
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
    severity: Optional[str] = "NORMAL"  # "NORMAL", "WARNING", "VIOLATION"

class ZoneModel(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = "restricted_eating"
    color: str = "#ef4444"
    polygon: List[List[float]]
    alert_on_eating: bool = True
    alert_on_loiter: bool = True
    loiter_threshold_sec: float = 90.0

class ToggleRequest(BaseModel):
    skeleton: Optional[bool] = None
    boxes: Optional[bool] = None
    zones: Optional[bool] = None
    hud: Optional[bool] = None

def load_audit_notes() -> List[Dict[str, Any]]:
    if NOTES_FILE.exists():
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_audit_notes(notes: List[Dict[str, Any]]):
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2)
    except Exception as e:
        print(f"Error saving notes: {e}")

# Streaming generator for live annotated MJPEG video feed
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

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
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
    """Uploads any MP4/AVI/MOV video file for analysis and audits."""
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
    """Controls video playback speed (0.25x to 4.0x timelapse)."""
    eng = get_engine()
    eng.stream.set_speed(req.speed)
    return {"status": "success", "speed": eng.stream.speed_multiplier}

@app.post("/api/playback")
def control_playback(req: PlaybackRequest):
    """Controls playback pause/play and rewind."""
    eng = get_engine()
    if req.action == "toggle_pause":
        paused = eng.stream.toggle_pause()
        return {"status": "success", "is_paused": paused}
    elif req.action == "rewind":
        eng.stream.rewind()
        return {"status": "success", "rewound": True}
    return {"status": "error", "message": "Unknown action"}

# Audit Notes Endpoints
@app.get("/api/notes")
def get_notes():
    return {"notes": load_audit_notes()}

@app.post("/api/notes")
def add_note(note_data: AuditNoteModel):
    notes = load_audit_notes()
    new_entry = {
        "id": f"note-{int(time.time()*1000)}",
        "note": note_data.note,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "time_offset": note_data.time_offset or time.strftime("%H:%M:%S"),
        "person_id": note_data.person_id,
        "zone": note_data.zone or "Kitchen",
        "severity": note_data.severity or "NORMAL"
    }
    notes.insert(0, new_entry)
    save_audit_notes(notes)
    return {"status": "success", "note": new_entry}

@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str):
    notes = load_audit_notes()
    notes = [n for n in notes if n.get("id") != note_id]
    save_audit_notes(notes)
    return {"status": "success"}

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
    return "<h1>Rest-Eye CCTV Sentry backend is running.</h1>"
