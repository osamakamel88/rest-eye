from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .models import Organization, User, Branch, Camera, Zone, Incident, AuditNote, TenantSettings
from datetime import datetime

# --- Organization & Tenants ---
def create_organization(db: Session, name: str, slug: str, plan_tier: str = "pro") -> Organization:
    org = Organization(name=name, slug=slug, plan_tier=plan_tier)
    db.add(org)
    db.commit()
    db.refresh(org)
    
    # Create default settings
    settings = TenantSettings(organization_id=org.id)
    db.add(settings)
    db.commit()
    return org

def get_organization_by_slug(db: Session, slug: str) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.slug == slug, Organization.is_active == True).first()

def get_organization(db: Session, org_id: str) -> Optional[Organization]:
    return db.query(Organization).filter(Organization.id == org_id).first()

def list_organizations(db: Session) -> List[Organization]:
    return db.query(Organization).filter(Organization.is_active == True).all()

# --- Users ---
def create_user(db: Session, org_id: str, email: str, hashed_pw: str, full_name: str, role: str = "owner") -> User:
    user = User(
        organization_id=org_id,
        email=email.lower().strip(),
        hashed_password=hashed_pw,
        full_name=full_name,
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower().strip(), User.is_active == True).first()

# --- Branches ---
def create_branch(db: Session, org_id: str, name: str, city: str = "القاهرة", address: str = "") -> Branch:
    branch = Branch(organization_id=org_id, name=name, city=city, address=address)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch

def list_branches(db: Session, org_id: str) -> List[Branch]:
    return db.query(Branch).filter(Branch.organization_id == org_id, Branch.is_active == True).all()

def get_branch(db: Session, branch_id: str, org_id: str) -> Optional[Branch]:
    return db.query(Branch).filter(Branch.id == branch_id, Branch.organization_id == org_id).first()

# --- Cameras ---
def create_camera(db: Session, branch_id: str, name: str, stream_source: str, camera_type: str = "KITCHEN") -> Camera:
    camera = Camera(
        branch_id=branch_id,
        name=name,
        stream_source=stream_source,
        camera_type=camera_type
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera

def list_cameras_by_branch(db: Session, branch_id: str) -> List[Camera]:
    return db.query(Camera).filter(Camera.branch_id == branch_id, Camera.is_active == True).all()

def get_camera(db: Session, camera_id: str) -> Optional[Camera]:
    return db.query(Camera).filter(Camera.id == camera_id).first()

# --- Zones ---
def create_zone(db: Session, camera_id: str, name: str, polygon_points: list, zone_type: str = "restricted_eating") -> Zone:
    zone = Zone(
        camera_id=camera_id,
        name=name,
        polygon_points=polygon_points,
        zone_type=zone_type
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone

def list_zones_by_camera(db: Session, camera_id: str) -> List[Zone]:
    return db.query(Zone).filter(Zone.camera_id == camera_id, Zone.is_active == True).all()

def delete_zone(db: Session, zone_id: str) -> bool:
    zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if zone:
        db.delete(zone)
        db.commit()
        return True
    return False

# --- Incidents ---
def record_incident(
    db: Session,
    org_id: str,
    camera_id: str,
    incident_type: str,
    person_track_id: Optional[int] = None,
    zone_name: Optional[str] = None,
    posture: str = "STANDING",
    dwell_sec: float = 0.0,
    video_clip_url: Optional[str] = None,
    snapshot_url: Optional[str] = None,
    details: Optional[dict] = None
) -> Incident:
    incident = Incident(
        organization_id=org_id,
        camera_id=camera_id,
        incident_type=incident_type,
        person_track_id=person_track_id,
        zone_name=zone_name,
        posture=posture,
        dwell_sec=dwell_sec,
        video_clip_url=video_clip_url,
        snapshot_url=snapshot_url,
        details=details or {},
        created_at=datetime.utcnow()
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident

def list_incidents(
    db: Session,
    org_id: str,
    branch_id: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = 50
) -> List[Incident]:
    query = db.query(Incident).filter(Incident.organization_id == org_id)
    if camera_id:
        query = query.filter(Incident.camera_id == camera_id)
    return query.order_by(desc(Incident.created_at)).limit(limit).all()

# --- Tenant Settings ---
def get_tenant_settings(db: Session, org_id: str) -> Optional[TenantSettings]:
    settings = db.query(TenantSettings).filter(TenantSettings.organization_id == org_id).first()
    if not settings:
        settings = TenantSettings(organization_id=org_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

def update_tenant_settings(db: Session, org_id: str, update_data: dict) -> TenantSettings:
    settings = get_tenant_settings(db, org_id)
    for k, v in update_data.items():
        if hasattr(settings, k) and v is not None:
            setattr(settings, k, v)
    db.commit()
    db.refresh(settings)
    return settings
