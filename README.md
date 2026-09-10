# 👁️ REST-EYE: Restaurant CCTV AI Sentry

An AI computer vision monitoring solution designed for restaurant back-offices, prep kitchens, and inventory storage areas to prevent inventory shrinkage and monitor staff behaviors.

---

## 🚀 Key Capabilities

- 🛑 **Unauthorized Eating & Drinking Detection**: Evaluates hand-to-mouth proximity, dwell times, and feeding gestures to detect unauthorized snacking/grazing in prep and inventory zones.
- ⏱️ **Staff Dwell Time & Posture Tracking**: Real-time measurement of standing vs sitting vs idle duration per staff member.
- 📐 **Interactive Restricted Polygon Zones**: Point-and-click zone creator directly on the live camera view (e.g., Walk-in Coolers, Storage Shelves, Food Prep Lines).
- 📹 **Automated Incident Recording**: Saves 8-second MP4 video clips (pre-event buffer + post-event recording) and snapshots for every violation.
- 🌐 **Interactive Web Control Center**: Real-time CCTV stream with skeleton/box overlays, audio alerts, and client demonstration mode for Vercel.

---

## 🛠️ Tech Stack

- **Pose & Object Tracking**: Ultralytics YOLO11-Pose + ByteTrack
- **Computer Vision**: OpenCV, NumPy
- **Backend API & Streaming**: FastAPI, Uvicorn, WebSockets
- **Frontend Dashboard**: HTML5, Tailwind-compatible CSS, Vanilla JS Canvas

---

## ⚡ Quick Start (Local CCTV / Video Mode)

### 1. Install Dependencies
```bash
pip install -r rest-eye/requirements.txt
```

### 2. Run the Sentry
```bash
python rest-eye/run.py
```
*Or double click `launch_rest_eye.bat` on Windows.*

### 3. Open the Dashboard
Navigate to: **[http://localhost:8000](http://localhost:8000)**

---

## ☁️ Deployment (Vercel Client Demonstration)

This repository includes a standalone **Interactive Client Pitch Mode** ready for Vercel deployment:

1. Push this repository to your GitHub:
   ```bash
   git add .
   git commit -m "feat: REST-EYE restaurant CCTV AI sentry"
   git push origin master
   ```
2. Import the repository into **[Vercel](https://vercel.com)**.
3. Deploy! You will receive a live URL (`https://rest-eye.vercel.app`) you can open on any phone, tablet, or laptop to pitch directly to restaurant owners.
