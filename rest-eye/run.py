import argparse
import os
import sys
import uvicorn
from pathlib import Path

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config, DEFAULT_SAMPLE_VIDEO

def main():
    parser = argparse.ArgumentParser(description="REST-EYE: Restaurant CCTV AI Sentry")
    parser.add_argument(
        "--source",
        type=str,
        default=DEFAULT_SAMPLE_VIDEO,
        help=f"Video source path, camera index (e.g. 0), or RTSP URL. Default: {DEFAULT_SAMPLE_VIDEO}"
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web dashboard host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Web dashboard port (default: 8000)")
    parser.add_argument("--conf", type=float, default=0.35, help="Detection confidence threshold (default: 0.35)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    # Update global config
    config.video_source = args.source
    config.web_host = args.host
    config.web_port = args.port
    config.conf_threshold = args.conf

    print("=" * 65)
    print(" [REST-EYE] Restaurant CCTV AI Sentry")
    print("=" * 65)
    print(f" * Active Video Source : {config.video_source}")
    print(f" * Pose Model          : {config.pose_model}")
    print(f" * Web Dashboard URL   : http://localhost:{config.web_port}")
    print("=" * 65)
    print("Starting server... Open http://localhost:8000 in your browser.\n")

    # Start FastAPI Web Application
    uvicorn.run(
        "web.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
