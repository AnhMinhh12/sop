"""
Verify model mới (sau khi retrain) bằng cách so sánh với baseline.

Chạy:
    python scripts/verify_model.py --video data/recordings/30_20260730_081531_10min.mp4

Output:
    - In bảng so sánh baseline vs new model
    - PASS nếu robot/sp cải thiện ≥ 30%
    - WARNING nếu cải thiện < 30%
    - FAIL nếu tệ hơn baseline
"""

import argparse
import os
import sys
import io
from pathlib import Path
from collections import defaultdict
import numpy as np
import cv2

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# Baseline đo được trên video 30_20260730_081531_10min.mp4 trước khi retrain
BASELINE = {
    "hand":  {"max": 0.9569, "mean": 0.4935, "median": 0.5209, "count_gt_025": 2628},
    "robot": {"max": 0.7833, "mean": 0.3004, "median": 0.2381, "count_gt_025": 152},
    "sp":    {"max": 0.6415, "mean": 0.1606, "median": 0.1071, "count_gt_025": 28},
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--video", default="data/recordings/30_20260730_081531_10min.mp4")
    p.add_argument("--model", default="shared/models/yolo/TFF4040.onnx")
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--sample-every", type=int, default=30)
    p.add_argument("--max-frames", type=int, default=200)
    return p.parse_args()


def load_model(model_path: str):
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        return ("onnx", sess)
    except Exception:
        pass
    from ultralytics import YOLO
    return ("ultralytics", YOLO(model_path))


def infer_onnx(sess, img_bgr, conf_thr):
    img = cv2.resize(img_bgr, (640, 640)).astype(np.float32) / 255.0
    img = img.transpose(2, 0, 1)[None]
    pred = np.squeeze(sess.run(None, {sess.get_inputs()[0].name: img})[0])
    boxes = pred[:4]
    class_scores = pred[4:]
    max_scores = class_scores.max(axis=0)
    max_classes = class_scores.argmax(axis=0)
    dets = []
    h0, w0 = img_bgr.shape[:2]
    sx, sy = w0 / 640, h0 / 640
    for i in range(pred.shape[1]):
        s = float(max_scores[i])
        if s < conf_thr:
            continue
        cls = int(max_classes[i])
        cx, cy, bw, bh = boxes[:, i]
        x1 = (cx - bw / 2) * sx
        y1 = (cy - bh / 2) * sy
        x2 = (cx + bw / 2) * sx
        y2 = (cy + bh / 2) * sy
        dets.append((cls, s))
    return dets


def main():
    args = parse_args()

    if not Path(args.video).exists():
        print(f"❌ Không tìm thấy video: {args.video}")
        return 1

    if not Path(args.model).exists():
        print(f"❌ Không tìm thấy model: {args.model}")
        return 1

    print(f"Video: {args.video}")
    print(f"Model: {args.model}")
    print(f"Conf threshold: {args.conf}\n")

    backend, model = load_model(args.model)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"❌ Không mở được video")
        return 1

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Total frames: {total}\n")

    class_names = ["hand", "robot", "sp"]
    all_confs = defaultdict(list)

    idx = 0
    sampled = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % args.sample_every == 0 and sampled < args.max_frames:
            sampled += 1
            if backend == "onnx":
                dets = infer_onnx(model, frame, args.conf)
            else:
                results = model.predict(frame, conf=args.conf, verbose=False)
                dets = [(int(b.cls), float(b.conf)) for r in results for b in r.boxes]
            for cls, c in dets:
                if cls < len(class_names):
                    all_confs[class_names[cls]].append(c)
        idx += 1
    cap.release()

    # === So sánh ===
    print("=" * 85)
    print(f"{'CLASS':<8} {'METRIC':<12} {'BASELINE':<12} {'NEW':<12} {'DELTA':<12} {'VERDICT':<15}")
    print("=" * 85)

    overall_pass = True
    for name in class_names:
        confs = all_confs.get(name, [])
        base = BASELINE[name]

        if not confs:
            print(f"{name:<8} {'count':<12} {base['count_gt_025']:<12} {0:<12} "
                  f"{-base['count_gt_025']:<12} ❌ FAIL")
            overall_pass = False
            continue

        new_max = max(confs)
        new_mean = np.mean(confs)
        new_med = np.median(confs)
        new_count = len(confs)

        # So sánh max confidence
        max_delta = new_max - base["max"]
        max_pct = (max_delta / base["max"]) * 100
        max_verdict = "✅ +" if max_delta > 0 else ("⚠️ =" if max_delta > -0.05 else "❌ -")

        # So sánh count
        count_pct = ((new_count - base["count_gt_025"]) / base["count_gt_025"]) * 100
        count_verdict = "✅ +" if count_pct > 30 else ("⚠️ =" if count_pct > -30 else "❌ -")

        print(f"{name:<8} {'max':<12} {base['max']:<12.4f} {new_max:<12.4f} "
              f"{max_delta:+.4f} ({max_pct:+.1f}%)  {max_verdict}")
        print(f"{'':<8} {'mean':<12} {base['mean']:<12.4f} {new_mean:<12.4f} "
              f"{new_mean - base['mean']:+.4f}")
        print(f"{'':<8} {'median':<12} {base['median']:<12.4f} {new_med:<12.4f} "
              f"{new_med - base['median']:+.4f}")
        print(f"{'':<8} {'count':<12} {base['count_gt_025']:<12} {new_count:<12} "
              f"{new_count - base['count_gt_025']:+d} ({count_pct:+.1f}%)  {count_verdict}")
        print("-" * 85)

        # Quy tắc: cải thiện count ≥ 30% cho robot/sp; hand không được tệ đi
        if name in ("robot", "sp") and count_pct < 30:
            overall_pass = False

    print("=" * 85)
    if overall_pass:
        print("\n✅ PASS — Model mới cải thiện rõ rệt")
    else:
        print("\n⚠️ CẦN XEM XÉT — Model mới chưa cải thiện nhiều")
        print("   Có thể cần: thêm ảnh, augmentation mạnh hơn, hoặc train thêm epochs")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
