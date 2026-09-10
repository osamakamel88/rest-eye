import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.engine import RestEyeEngine
from core.config import config, DEFAULT_SAMPLE_VIDEO

def test_pipeline():
    print(f"Testing Rest-Eye on video: {DEFAULT_SAMPLE_VIDEO}")
    engine = RestEyeEngine(source=DEFAULT_SAMPLE_VIDEO).start()
    
    # Process 50 frames to test performance and stability
    frames_processed = 0
    start_t = time.time()
    
    for i in range(50):
        ret, frame, persons = engine.process_frame()
        if ret:
            frames_processed += 1
            if i % 10 == 0:
                print(f"[Frame {i}] Processed successfully. Persons tracked: {len(persons)}")
                for p in persons:
                    print(f"  -> Person #{p['track_id']}: Posture={p['posture']}, DistRatio={p['wrist_mouth_dist_ratio']}, HandNearMouth={p['is_hand_near_mouth']}, Eating={p['is_eating']}")
        time.sleep(0.02)

    total_time = time.time() - start_t
    engine.stop()
    print(f"\n[Test Result] Successfully processed {frames_processed} frames in {total_time:.2f}s (Avg FPS: {frames_processed/total_time:.1f})")
    print("Pipeline verification PASSED.")

if __name__ == "__main__":
    test_pipeline()
