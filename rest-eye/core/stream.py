import time
import threading
from typing import Optional, Union, Tuple
import cv2
import numpy as np

class VideoStream:
    """
    Multi-threaded non-blocking video capture for RTSP, Webcams, and MP4 files.
    """
    def __init__(self, source: Union[str, int], loop: bool = True, target_fps: int = 25):
        # Convert numeric strings to int for webcam
        if isinstance(source, str) and source.isdigit():
            self.source = int(source)
            self.is_file = False
        elif isinstance(source, int):
            self.source = source
            self.is_file = False
        else:
            self.source = source
            self.is_file = True

        self.loop = loop
        self.target_fps = target_fps
        self.frame_delay = 1.0 / max(1, target_fps)

        self.cap: Optional[cv2.VideoCapture] = None
        self.current_frame: Optional[np.ndarray] = None
        self.is_running = False
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        
        self.width = 1280
        self.height = 720
        self.actual_fps = 25.0
        self.total_frames = 0
        
        self._init_capture()

    def _init_capture(self):
        try:
            print(f"[VideoStream] Connecting to source: {self.source}")
            self.cap = cv2.VideoCapture(self.source)
            if self.cap.isOpened():
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.actual_fps = fps if fps > 0 and fps < 120 else 25.0
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                print(f"[VideoStream] Connected! Resolution: {self.width}x{self.height}, FPS: {self.actual_fps:.1f}, Frames: {self.total_frames}")
            else:
                print(f"[VideoStream] Warning: Could not open source {self.source}")
        except Exception as e:
            print(f"[VideoStream] Initialization error: {e}")

    def start(self):
        if self.is_running:
            return self
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        return self

    def _capture_loop(self):
        while self.is_running:
            start_t = time.time()
            if self.cap is None or not self.cap.isOpened():
                time.sleep(0.5)
                self._init_capture()
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                if self.is_file and self.loop:
                    # Rewind to beginning
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.05)
                    continue
                else:
                    time.sleep(0.1)
                    continue

            with self.lock:
                self.current_frame = frame

            # Throttle to simulate realistic video playback speed
            elapsed = time.time() - start_t
            sleep_time = max(0.001, self.frame_delay - elapsed)
            time.sleep(sleep_time)

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        with self.lock:
            if self.current_frame is not None:
                return True, self.current_frame.copy()
            return False, None

    def change_source(self, new_source: Union[str, int]):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        if self.cap:
            self.cap.release()
            
        if isinstance(new_source, str) and new_source.isdigit():
            self.source = int(new_source)
            self.is_file = False
        elif isinstance(new_source, int):
            self.source = new_source
            self.is_file = False
        else:
            self.source = new_source
            self.is_file = True

        self._init_capture()
        self.start()

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        print("[VideoStream] Stream stopped.")
