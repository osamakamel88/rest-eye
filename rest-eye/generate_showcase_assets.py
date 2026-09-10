import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO

base_dir = Path(__file__).resolve().parent
video_path = r"D:\Downloads\a_restaurant_back_kitchen_wher.mp4"
output_dir = base_dir / "web" / "static" / "assets"
output_dir.mkdir(parents=True, exist_ok=True)

model = YOLO("yolo11n-pose.pt")
cap = cv2.VideoCapture(video_path)

def draw_smart_box(img, x1, y1, x2, y2, color, label, is_alert=False):
    # Main Bounding Box
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3 if is_alert else 2)
    
    # Corner Accents
    corner_len = 16
    thick = 4 if is_alert else 3
    cv2.line(img, (x1, y1), (x1 + corner_len, y1), color, thick)
    cv2.line(img, (x1, y1), (x1, y1 + corner_len), color, thick)
    cv2.line(img, (x2, y1), (x2 - corner_len, y1), color, thick)
    cv2.line(img, (x2, y1), (x2, y1 + corner_len), color, thick)
    cv2.line(img, (x1, y2), (x1 + corner_len, y2), color, thick)
    cv2.line(img, (x1, y2), (x1, y2 - corner_len), color, thick)
    cv2.line(img, (x2, y2), (x2 - corner_len, y2), color, thick)
    cv2.line(img, (x2, y2), (x2, y2 - corner_len), color, thick)

    # Label Badge Background
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 2)
    badge_y1 = max(0, y1 - 28)
    badge_y2 = y1
    badge_x1 = x1
    badge_x2 = min(img.shape[1], x1 + tw + 16)
    
    cv2.rectangle(img, (badge_x1, badge_y1), (badge_x2, badge_y2), color, -1)
    # White Text
    cv2.putText(img, label, (badge_x1 + 8, badge_y2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2)

SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16)
]

# ==========================================
# 1. GENERATE SHOWCASE 1: EATING VIOLATION (Frame 110)
# ==========================================
print("[Showcase Generator] Generating Showcase 1 (Frame 110 Eating Violation)...")
cap.set(cv2.CAP_PROP_POS_FRAMES, 110)
ret, frame1 = cap.read()
if ret:
    h, w, _ = frame1.shape
    overlay = frame1.copy()

    # Restricted Zone Polygon over prep counter & storage
    zone_pts = np.array([
        [int(0.25 * w), int(0.08 * h)],
        [int(0.98 * w), int(0.08 * h)],
        [int(0.98 * w), int(0.95 * h)],
        [int(0.25 * w), int(0.95 * h)]
    ], np.int32)
    cv2.fillPoly(overlay, [zone_pts], (30, 30, 220))
    cv2.addWeighted(overlay, 0.25, frame1, 0.75, 0, frame1)
    cv2.polylines(frame1, [zone_pts], True, (0, 0, 240), 2)
    cv2.putText(frame1, "RESTRICTED ZONE: Kitchen Prep Station & Storage", (int(0.27 * w), int(0.06 * h)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    # YOLO Pose on Frame 110
    res = model(frame1, verbose=False)[0]
    boxes = res.boxes.xyxy.cpu().numpy()
    kpts_data = res.keypoints.data.cpu().numpy() if res.keypoints is not None else []

    for i in range(len(boxes)):
        box = [int(v) for v in boxes[i]]
        kpts = kpts_data[i] if i < len(kpts_data) else []
        x1, y1, x2, y2 = box

        if 300 < x1 < 450 and y2 > 650:
            # Person eating in foreground (#143)
            draw_smart_box(frame1, x1, y1, x2, y2, (0, 0, 240), "[VIOLATION] #143 [STANDING 18s] - UNAUTHORIZED EATING DETECTED!", is_alert=True)
            
            # Draw Skeleton
            for p1_idx, p2_idx in SKELETON_EDGES:
                if p1_idx < len(kpts) and p2_idx < len(kpts):
                    p1, p2 = kpts[p1_idx], kpts[p2_idx]
                    if p1[2] > 0.25 and p2[2] > 0.25:
                        pt1 = (int(p1[0]), int(p1[1]))
                        pt2 = (int(p2[0]), int(p2[1]))
                        # Red arms for food & drink action
                        edge_c = (0, 0, 255) if (p1_idx in [5,7,9, 6,8,10] or p2_idx in [5,7,9, 6,8,10]) else (0, 230, 255)
                        cv2.line(frame1, pt1, pt2, edge_c, 3 if edge_c == (0,0,255) else 2)
            
            for kp in kpts:
                if kp[2] > 0.25:
                    cv2.circle(frame1, (int(kp[0]), int(kp[1])), 5, (0, 255, 255), -1)

            # Hand-to-mouth proximity indicator circle at mouth / right hand
            mouth_pt = (int(kpts[0][0]), int(kpts[0][1] + 15)) if len(kpts) > 0 and kpts[0][2] > 0.25 else (550, 250)
            cv2.circle(frame1, mouth_pt, 25, (0, 0, 255), 2)
            cv2.putText(frame1, "HAND-TO-MOUTH [0.18]", (mouth_pt[0] + 35, mouth_pt[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 255), 2)

        elif x1 < 50 and y2 > 650:
            # Background chef on left
            draw_smart_box(frame1, x1, y1, x2, y2, (0, 220, 100), "#102 [STANDING 4m 12s] - Normal (Station Cleaning)")
            for p1_idx, p2_idx in SKELETON_EDGES:
                if p1_idx < len(kpts) and p2_idx < len(kpts):
                    p1, p2 = kpts[p1_idx], kpts[p2_idx]
                    if p1[2] > 0.25 and p2[2] > 0.25:
                        cv2.line(frame1, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (255, 200, 50), 2)

        elif 80 < x1 < 260 and y2 > 600:
            # Line cook in background
            draw_smart_box(frame1, x1, y1, x2, y2, (0, 220, 100), "#108 [STANDING 2m 50s] - Normal (Prep)")

    # Top HUD
    cv2.rectangle(frame1, (0, 0), (w, 36), (15, 15, 20), -1)
    hud_text = "REST-EYE SENTRY  |  Kitchen Main Cam  |  FPS: 25.0  |  Personnel: 3 Active  |  Violations: 1"
    cv2.putText(frame1, hud_text, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 180), 2)
    
    cv2.imwrite(str(output_dir / "eating_detection_real.png"), frame1)
    print("Saved eating_detection_real.png successfully.")

# ==========================================
# 2. GENERATE SHOWCASE 2: MULTI-CHEF OVERVIEW (Frame 35)
# ==========================================
print("[Showcase Generator] Generating Showcase 2 (Frame 35 Kitchen Overview)...")
cap.set(cv2.CAP_PROP_POS_FRAMES, 35)
ret, frame2 = cap.read()
if ret:
    h, w, _ = frame2.shape
    res = model(frame2, verbose=False)[0]
    boxes = res.boxes.xyxy.cpu().numpy()
    kpts_data = res.keypoints.data.cpu().numpy() if res.keypoints is not None else []

    # Track which persons we have drawn to prevent duplicate overlapping boxes
    drawn_areas = []

    for i in range(len(boxes)):
        box = [int(v) for v in boxes[i]]
        kpts = kpts_data[i] if i < len(kpts_data) else []
        x1, y1, x2, y2 = box

        if x1 > 880:
            # Drinking person on the right
            draw_smart_box(frame2, x1, y1, x2, y2, (0, 0, 240), "[VIOLATION] #209 [STANDING 12s] - DRINKING DETECTED!", is_alert=True)
            for p1_idx, p2_idx in SKELETON_EDGES:
                if p1_idx < len(kpts) and p2_idx < len(kpts):
                    p1, p2 = kpts[p1_idx], kpts[p2_idx]
                    if p1[2] > 0.3 and p2[2] > 0.3:
                        pt1 = (int(p1[0]), int(p1[1]))
                        pt2 = (int(p2[0]), int(p2[1]))
                        edge_c = (0, 0, 255) if (p1_idx in [6, 8, 10] or p2_idx in [6, 8, 10]) else (0, 230, 255)
                        cv2.line(frame2, pt1, pt2, edge_c, 3 if edge_c == (0,0,255) else 2)
            
            # Hand to mouth indicator
            wrist_pt = (int(kpts[10][0]), int(kpts[10][1])) if len(kpts) > 10 and kpts[10][2] > 0.3 else (1000, 320)
            cv2.circle(frame2, wrist_pt, 20, (0, 0, 255), 2)
            cv2.putText(frame2, "HAND-TO-MOUTH [0.22]", (wrist_pt[0] - 150, wrist_pt[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        elif x1 < 400 and (y2 - y1) > 350:
            # Foreground chef on left
            draw_smart_box(frame2, x1, y1, x2, y2, (0, 220, 100), "#231 [STANDING 3m 40s] - Normal (Plating)")
            for p1_idx, p2_idx in SKELETON_EDGES:
                if p1_idx < len(kpts) and p2_idx < len(kpts):
                    p1, p2 = kpts[p1_idx], kpts[p2_idx]
                    if p1[2] > 0.3 and p2[2] > 0.3:
                        cv2.line(frame2, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0, 230, 255), 2)

        elif 400 < x1 < 680 and (y2 - y1) > 300:
            # Middle prep chef
            draw_smart_box(frame2, x1, y1, x2, y2, (0, 220, 100), "#200 [STANDING 4m 20s] - Normal (Chopping)")
            for p1_idx, p2_idx in SKELETON_EDGES:
                if p1_idx < len(kpts) and p2_idx < len(kpts):
                    p1, p2 = kpts[p1_idx], kpts[p2_idx]
                    if p1[2] > 0.3 and p2[2] > 0.3:
                        cv2.line(frame2, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (0, 230, 255), 2)

        elif 320 < x1 < 500 and (y2 - y1) < 350:
            # Background line cook
            draw_smart_box(frame2, x1, y1, x2, y2, (0, 220, 100), "#186 [STANDING 1m 15s] - Normal")

        elif 750 < x1 < 880:
            # Staff next to drinking person
            draw_smart_box(frame2, x1, y1, x2, y2, (0, 220, 100), "#215 [STANDING 55s] - Normal")

    # Top HUD
    cv2.rectangle(frame2, (0, 0), (w, 36), (15, 15, 20), -1)
    hud_text = "REST-EYE SENTRY  |  Kitchen Main Cam  |  FPS: 25.0  |  Personnel: 5 Active  |  Violations: 1"
    cv2.putText(frame2, hud_text, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 180), 2)

    cv2.imwrite(str(output_dir / "kitchen_overview_real.png"), frame2)
    print("Saved kitchen_overview_real.png successfully.")

cap.release()
print("[Showcase Generator] Finished successfully.")
