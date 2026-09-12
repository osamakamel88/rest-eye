import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Organization(Base):
    """Restaurant Chain / Business Tenant"""
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True)
    plan_tier = Column(String(50), default="pro")  # 'starter', 'pro', 'enterprise'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="organization", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="organization", cascade="all, delete-orphan")
    settings = relationship("TenantSettings", back_populates="organization", uselist=False, cascade="all, delete-orphan")

class User(Base):
    """User account scoped to an Organization"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="owner")  # 'owner', 'branch_manager', 'auditor'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")

class Branch(Base):
    """Restaurant Location / Branch"""
    __tablename__ = "branches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), default="القاهرة")
    address = Column(String(255), nullable=True)
    timezone = Column(String(50), default="Africa/Cairo")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="branches")
    cameras = relationship("Camera", back_populates="branch", cascade="all, delete-orphan")

class Camera(Base):
    """CCTV Camera Stream associated with a Branch"""
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    stream_source = Column(Text, nullable=False)  # RTSP URL, WebRTC, or sample file path
    camera_type = Column(String(50), default="KITCHEN")  # 'KITCHEN', 'STORAGE', 'PREP_LINE', 'COOLER'
    is_active = Column(Boolean, default=True)
    ai_settings = Column(JSON, default=lambda: {
        "detect_eating": True,
        "detect_drinking": True,
        "detect_posture": True,
        "detect_loitering": True,
        "sensitivity": 0.38
    })
    created_at = Column(DateTime, default=datetime.utcnow)

    branch = relationship("Branch", back_populates="cameras")
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="camera", cascade="all, delete-orphan")

class Zone(Base):
    """Interactive Polygon Restricted Zone on Camera Feed"""
    __tablename__ = "zones"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    camera_id = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    zone_type = Column(String(50), default="restricted_eating")  # 'restricted_eating', 'no_loiter', 'cold_storage'
    polygon_points = Column(JSON, nullable=False)  # [[norm_x, norm_y], ...]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    camera = relationship("Camera", back_populates="zones")

class Incident(Base):
    """AI Violation / Incident Log with 8s Clip and Snapshot"""
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_type = Column(String(100), nullable=False, index=True)  # 'UNAUTHORIZED_EATING', 'RESTRICTED_ZONE_BREACH', 'LOITERING'
    person_track_id = Column(Integer, nullable=True)
    zone_name = Column(String(255), nullable=True)
    posture = Column(String(50), default="STANDING")
    dwell_sec = Column(Float, default=0.0)
    video_clip_url = Column(Text, nullable=True)  # S3/R2 Presigned URL or local static path
    snapshot_url = Column(Text, nullable=True)    # S3/R2 Snapshot URL or local static path
    details = Column(JSON, default=dict)
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    organization = relationship("Organization", back_populates="incidents")
    camera = relationship("Camera", back_populates="incidents")

class AuditNote(Base):
    """Manual shift audit note attached to timeline"""
    __tablename__ = "audit_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id = Column(String(36), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp_video = Column(String(50), nullable=True)  # e.g., "01:23"
    note_text = Column(Text, nullable=False)
    severity = Column(String(50), default="VIOLATION")  # 'VIOLATION', 'WARNING', 'NORMAL'
    created_at = Column(DateTime, default=datetime.utcnow)

class TenantSettings(Base):
    """Cloudflare R2, Telegram, WhatsApp API Settings per Tenant"""
    __tablename__ = "tenant_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Cloud Storage (R2 / S3)
    r2_account_id = Column(String(255), nullable=True)
    r2_access_key_id = Column(String(255), nullable=True)
    r2_secret_access_key = Column(String(255), nullable=True)
    r2_bucket_name = Column(String(255), nullable=True)
    r2_public_url = Column(String(255), nullable=True)

    # Notifications
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(255), nullable=True)
    telegram_enabled = Column(Boolean, default=False)

    whatsapp_api_url = Column(String(255), nullable=True)
    whatsapp_token = Column(String(255), nullable=True)
    whatsapp_phone_number = Column(String(255), nullable=True)
    whatsapp_enabled = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="settings")
