"""
Test model TFF4040.onnx trên video với threshold thấp để xem raw confidence
của cả 3 class (hand, robot, sp) - xem model có "thấy" gì không.

Chạy:
    python scripts/test_video_raw.py --video data/recordings/30_20260730_081531_10min.mp4
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict
import sys
import io

# Force UTF-8 stdout for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", default="data/recordings/30_20260730_081531_10min.mp4")
    p.add_argument("--model", default="shared/models/yolo/TFF4040.onnx")
    p.add_argument("--conf", type=float, default=0.05,
                   help="Threshold rất thấp để xem model có thấy gì không")
    p.add_argument("--sample-every", type=int, default=30,
                   help="Lấy mẫu mỗi N frame")
    p.add_argument("--max-frames", type=int, default=300,
                   help="Giới hạn số frame để test nhanh")
    p.add_argument("--save-snapshot", action="store_true",
                   help="Lưu 1 frame có detection cao nhất để xem")
    return p.parse_args()


def load_model(model_path: str):
    """Load ONNX model bằng onnxruntime (ưu tiên) hoặc ultralytics."""
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        return ("onnx", sess)
    except Exception:
        pass

    from ultralytics import YOLO
    return ("ultralytics", YOLO(model_path))


def infer_onnx(sess, img_bgr: np.ndarray, conf_thr: float):
    """Inference bằng onnxruntime, trả về list detection [(cls, conf, x1,y1,x2,y2)]."""
    img = cv2.resize(img_bgr, (640, 640))
    img = img.astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)[None]  # NCHW

    outputs = sess.run(None, {sess.get_inputs()[0].name: img})
    pred = outputs[0]  # shape (1, 7, 8400) hoặc (1, 84, 8400) - tùy model
    pred = np.squeeze(pred)  # (7, 8400) hoặc (84, 8400)

    # Parse theo format YOLOv8: 4 box + N class
    boxes = pred[:4]            # cx, cy, w, h (đã normalize)
    class_scores = pred[4:]     # (N_class, 8400)
    n_class = class_scores.shape[0]
    max_scores = class_scores.max(axis=0)
    max_classes = class_scores.argmax(axis=0)

    dets = []
    h0, w0 = img_bgr.shape[:2]
    scale_x, scale_y = w0 / 640, h0 / 640
    for i in range(pred.shape[1]):
        s = float(max_scores[i])
        if s < conf_thr:
            continue
        cls = int(max_classes[i])
        cx, cy, bw, bh = boxes[:, i]
        x1 = (cx - bw / 2) * scale_x
        y1 = (cy - bh / 2) * scale_y
        x2 = (cx + bw / 2) * scale_x
        y2 = (cy + bh / 2) * scale_y
        dets.append((cls, s, x1, y1, x2, y2))
    return dets


def main():
    args = parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        # Thử path khác (Windows)
        candidates = list(Path("data").rglob(f"*{video_path.stem}*"))
        if not candidates:
            print(f"❌ Không tìm thấy video: {video_path}")
            print(f"   Tìm trong data/: {list(Path('data').rglob('*.mp4'))[:5]}")
            return
        video_path = candidates[0]
        print(f"📹 Dùng video: {video_path}")

    print(f"🤖 Loading model: {args.model}")
    backend, model = load_model(args.model)
    print(f"   backend: {backend}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"❌ Không mở được video: {video_path}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"📊 Video: {total_frames} frames @ {fps:.1f} FPS ({total_frames/fps:.1f}s)")

    class_names = ["hand", "robot", "sp"]
    max_per_class = defaultdict(lambda: (0.0, -1, None))  # conf, frame_idx, det
    all_detections_per_class = defaultdict(list)
    frames_with_detection = 0

    frame_idx = 0
    sampled = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % args.sample_every == 0 and sampled < args.max_frames:
            sampled += 1
            if backend == "onnx":
                dets = infer_onnx(model, frame, args.conf)
            else:
                # ultralytics
                results = model.predict(frame, conf=args.conf, verbose=False)
                dets = []
                for r in results:
                    for b in r.boxes:
                        dets.append((
                            int(b.cls), float(b.conf),
                            float(b.xyxy[0][0]), float(b.xyxy[0][1]),
                            float(b.xyxy[0][2]), float(b.xyxy[0][3]),
                        ))

            if dets:
                frames_with_detection += 1
                for cls, conf, *box in dets:
                    name = class_names[cls] if cls < len(class_names) else f"cls{cls}"
                    all_detections_per_class[name].append(conf)
                    if conf > max_per_class[name][0]:
                        max_per_class[name] = (conf, frame_idx, (cls, conf, box))

            if sampled % 50 == 0:
                print(f"  Frame {frame_idx}/{total_frames} (sampled {sampled})")

        frame_idx += 1

    cap.release()

    # === Report ===
    print("\n" + "=" * 60)
    print(f"📈 KẾT QUẢ RAW (threshold = {args.conf})")
    print(f"   Frames sampled: {sampled} / {total_frames}")
    print(f"   Frames có detection ≥ {args.conf}: {frames_with_detection}")
    print("=" * 60)

    for name in class_names:
        confs = all_detections_per_class.get(name, [])
        max_conf, max_frame, _ = max_per_class[name]
        if confs:
            print(f"\n  {name.upper()}:")
            print(f"    Số lần detect:    {len(confs)}")
            print(f"    Max confidence:   {max_conf:.4f} (frame #{max_frame})")
            print(f"    Mean confidence:  {np.mean(confs):.4f}")
            print(f"    Median:           {np.median(confs):.4f}")
            print(f"    >0.25:            {sum(1 for c in confs if c > 0.25)}")
            print(f"    >0.10:            {sum(1 for c in confs if c > 0.10)}")
        else:
            print(f"\n  {name.upper()}: ❌ KHÔNG detect lần nào (threshold {args.conf})")

    print("\n" + "=" * 60)
    print("🔍 NHẬN XÉT:")
    for name in class_names:
        confs = all_detections_per_class.get(name, [])
        if not confs:
            print(f"  - {name}: Model KHÔNG nhận ra class này (cần retrain)")
        elif max(confs) < 0.25:
            print(f"  - {name}: Model thấy nhưng rất yếu (max={max(confs):.3f}) → retrain")
        elif max(confs) < 0.5:
            print(f"  - {name}: Model thấy ở mức trung bình (max={max(confs):.3f}) → có thể chấp nhận")
        else:
            print(f"  - {name}: Model detect tốt (max={max(confs):.3f}) ✅")


if __name__ == "__main__":
    main()
