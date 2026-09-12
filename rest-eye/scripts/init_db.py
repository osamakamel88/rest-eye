import sys
import io
from pathlib import Path

# Force utf-8 output on Windows console
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure rest-eye base directory is in sys.path
base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))

from core.db.session import init_db, SessionLocal
from core.db.crud import (
    create_organization,
    create_user,
    create_branch,
    create_camera,
    create_zone,
    get_user_by_email,
    get_organization_by_slug
)
from core.auth.security import get_password_hash
from core.config import DEFAULT_SAMPLE_VIDEO

def seed_demo_data():
    print("==================================================")
    print(" [REST-EYE] Multi-Tenant SaaS Database Setup")
    print("==================================================")
    init_db()
    db = SessionLocal()

    try:
        # 1. Create Demo Restaurant Tenant (سلسلة مطاعم الذواقة)
        org = get_organization_by_slug(db, "gourmet-burgers")
        if not org:
            print("[Seed] Creating Demo Organization: Gourmet Burgers Franchise...")
            org = create_organization(
                db=db,
                name="سلسلة مطاعم الذواقة (Gourmet Burgers)",
                slug="gourmet-burgers",
                plan_tier="enterprise"
            )
        else:
            print(f"[Seed] Organization exists: {org.slug} (ID: {org.id})")

        # 2. Create Owner User Account
        user = get_user_by_email(db, "demo@recode.dev")
        if not user:
            print("[Seed] Creating Demo Owner Account: demo@recode.dev...")
            user = create_user(
                db=db,
                org_id=org.id,
                email="demo@recode.dev",
                hashed_pw=get_password_hash("DemoPass123!"),
                full_name="مدير تشغيل السلسلة",
                role="owner"
            )
        else:
            print(f"[Seed] User exists: {user.email}")

        # 3. Create Branches (الفروع)
        branches_data = [
            {"name": "فرع التجمع الخامس (Fifth Settlement)", "city": "القاهرة الجديدة", "address": "شارع التسعين الشمالي"},
            {"name": "فرع المعادي (Maadi Hub)", "city": "القاهرة", "address": "شارع النصر، المعادي"},
            {"name": "فرع الشيخ زايد (Zayed Center)", "city": "الجيزة", "address": "وصلة دهشور"}
        ]
        
        created_branches = []
        for b_data in branches_data:
            branch = create_branch(db=db, org_id=org.id, name=b_data["name"], city=b_data["city"], address=b_data["address"])
            created_branches.append(branch)
            print(f"[Seed] Created Branch: {b_data['name']}")

        # 4. Create Cameras for Branch 1
        main_branch = created_branches[0]
        cam1 = create_camera(
            db=db,
            branch_id=main_branch.id,
            name="كاميرا المطبخ وخط التجهيز (Kitchen Main 01)",
            stream_source=DEFAULT_SAMPLE_VIDEO,
            camera_type="KITCHEN"
        )
        print(f"[Seed] Created Camera: {cam1.name} (ID: {cam1.id})")

        # 5. Create Default Restricted Zones
        zone1 = create_zone(
            db=db,
            camera_id=cam1.id,
            name="منطقة الثلاجة والمخزن الحساس (Cold Storage & Inventory)",
            polygon_points=[[0.05, 0.20], [0.65, 0.20], [0.65, 0.88], [0.05, 0.88]],
            zone_type="restricted_eating"
        )
        print(f"[Seed] Created Zone: {zone1.name}")

        print("==================================================")
        print(" [SUCCESS] Multi-Tenant Database Seeded Cleanly!")
        print(" Demo Email    : demo@recode.dev")
        print(" Demo Password : DemoPass123!")
        print("==================================================")

    except Exception as e:
        print(f"[Seed Error] {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
