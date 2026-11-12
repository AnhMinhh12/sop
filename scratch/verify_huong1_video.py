import os
import sys
import cv2

sys.path.insert(0, os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.loader import EngineLoader


def verify_on_video():
    video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0

    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)

    print(f"Running Hướng 1 engine on first 120s of {video_path} (fps={fps})...")
    frame_idx = 0
    prev_msg = ""
    while frame_idx < int(120 * fps):
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % 2 != 0:
            continue

        sec = frame_idx / fps
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]

        engine.update(hands_data=hands, products_data=prods, timestamp=sec)
        if engine.status_msg != prev_msg or engine.state in ["COMPLETED", "VIOLATION"]:
            print(
                f"[{sec:5.1f}s] State={engine.state:10s} | Slots={sum(engine.slots)}/8 "
                f"| Good={engine.total_good} NG={engine.total_ng} | {engine.status_msg}"
            )
            prev_msg = engine.status_msg

    cap.release()
    print(f"\nSUMMARY: Good={engine.total_good}, NG={engine.total_ng}, Cycles={engine.cycle_count}")


if __name__ == "__main__":
    verify_on_video()

