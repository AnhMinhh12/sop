"""
Train YOLOv8 — phiên bản LOCAL (chạy trên máy có GPU NVIDIA, không cần Colab)
==========================================================================
Yêu cầu: GPU NVIDIA + CUDA + Python 3.10+

Trước khi chạy:
    pip install ultralytics torch torchvision opencv-python

Dataset: đặt folder tff4040.yolov8 cùng cấp với script, hoặc sửa DATASET_DIR.
"""

import os
import shutil
from pathlib import Path

# ==== CẤU HÌNH ====
DATASET_DIR = r"D:\Downloads\tff4040.yolov8"   # <-- sửa đường dẫn dataset
DATA_YAML = os.path.join(DATASET_DIR, "data.yaml")
PROJECT_DIR = r"D:\Projects\yolo_runs"          # <-- nơi lưu kết quả train

MODEL_SIZE = "yolov8n.pt"
EPOCHS = 100
IMG_SIZE = 640
BATCH_SIZE = 16
PATIENCE = 20
WORKERS = 0               # Windows thì để 0 để tránh lỗi multiprocessing
PROJECT_NAME = "tff4040_yolov8"
RUN_NAME = "exp"

os.makedirs(PROJECT_DIR, exist_ok=True)


# ==== 1) Kiểm tra GPU ====
import torch
print(f"CUDA available : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU            : {torch.cuda.get_device_name(0)}")
    props = torch.cuda.get_device_properties(0)
    total_mem = getattr(props, "total_memory", None) or getattr(props, "total_mem")
    print(f"VRAM (GB)      : {total_mem / 1e9:.2f}")
else:
    print("⚠️  Không có GPU. Training sẽ rất chậm.")


# ==== 2) Kiểm tra dataset ====
print(f"\nDataset dir    : {DATASET_DIR}")
print(f"data.yaml path : {DATA_YAML}")
print(f"Exists         : {os.path.exists(DATA_YAML)}")

if not os.path.exists(DATA_YAML):
    raise FileNotFoundError(
        f"Không tìm thấy {DATA_YAML}. "
        f"Sửa DATASET_DIR trong script hoặc giải nén {DATASET_DIR}.zip trước."
    )

with open(DATA_YAML, "r") as f:
    print("\n--- data.yaml ---")
    print(f.read())

def count_split(split_dir):
    img_dir = os.path.join(split_dir, "images")
    lbl_dir = os.path.join(split_dir, "labels")
    if not os.path.isdir(img_dir):
        return 0, 0
    n_img = sum(len(files) for _, _, files in os.walk(img_dir))
    n_lbl = sum(len(files) for _, _, files in os.walk(lbl_dir))
    return n_img, n_lbl

for split in ("train", "valid", "test"):
    p = os.path.join(DATASET_DIR, split)
    if os.path.isdir(p):
        ni, nl = count_split(p)
        print(f"  {split:<5} : {ni:>5} images, {nl:>5} labels")


# ==== 3) Train ====
from ultralytics import YOLO

device = 0 if torch.cuda.is_available() else "cpu"
print(f"\n→ Train với device={device}\n")

model = YOLO(MODEL_SIZE)
model.train(
    data=DATA_YAML,
    epochs=EPOCHS,
    imgsz=IMG_SIZE,
    batch=BATCH_SIZE,
    project=PROJECT_DIR,
    name=f"{PROJECT_NAME}/{RUN_NAME}",
    patience=PATIENCE,
    workers=WORKERS,
    device=device,
    exist_ok=True,
    pretrained=True,
    optimizer="auto",
    seed=42,
    augment=True,
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    translate=0.1, scale=0.5, fliplr=0.5,
    mosaic=1.0, mixup=0.0,
)


# ==== 4) Validate ====
best_weights = os.path.join(PROJECT_DIR, PROJECT_NAME, RUN_NAME, "weights", "best.pt")
model = YOLO(best_weights)

metrics = model.val(
    data=DATA_YAML,
    imgsz=IMG_SIZE, batch=BATCH_SIZE,
    conf=0.25, iou=0.6,
    device=device,
)
print(f"\n[VAL] mAP50    : {metrics.box.map50:.4f}")
print(f"[VAL] mAP50-95 : {metrics.box.map:.4f}")
print(f"[VAL] Precision: {metrics.box.mp:.4f}")
print(f"[VAL] Recall   : {metrics.box.mr:.4f}")


# ==== 5) Test (nếu có) ====
test_dir = os.path.join(DATASET_DIR, "test")
if os.path.isdir(test_dir):
    test_yaml = os.path.join(PROJECT_DIR, "_test_tmp.yaml")
    with open(DATA_YAML, "r") as f:
        original = f.read()
    with open(test_yaml, "w") as f:
        f.write(original.replace("valid/images", "test/images"))

    test_metrics = model.val(
        data=test_yaml, imgsz=IMG_SIZE, batch=BATCH_SIZE,
        conf=0.25, iou=0.6, device=device,
    )
    print(f"\n[TEST] mAP50    : {test_metrics.box.map50:.4f}")
    print(f"[TEST] mAP50-95 : {test_metrics.box.map:.4f}")
    os.remove(test_yaml)


# ==== 6) Export ONNX ====
EXPORT_DIR = os.path.join(PROJECT_DIR, PROJECT_NAME, RUN_NAME, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

model.export(format="onnx", imgsz=IMG_SIZE, simplify=True, opset=12)

runs_dir = Path("runs") / "detect" / RUN_NAME
for f in runs_dir.glob("*.onnx"):
    shutil.copy2(f, EXPORT_DIR)
print(f"\n✅ Exported to {EXPORT_DIR}")


# ==== 7) Inference mẫu ====
sample_img = None
valid_images_dir = os.path.join(DATASET_DIR, "valid", "images")
if os.path.isdir(valid_images_dir):
    for ext in ("jpg", "jpeg", "png"):
        cands = list(Path(valid_images_dir).glob(f"*.{ext}"))
        if cands:
            sample_img = str(cands[0])
            break

if sample_img:
    preds = model.predict(source=sample_img, conf=0.25, save=True)
    print(f"\nPredicted : {sample_img}")
    print(f"Boxes     : {len(preds[0].boxes)}")
    print(f"Saved to  : {preds[0].save_dir}")
else:
    print("\nKhông tìm thấy ảnh valid mẫu.")


# ==== 8) Kết quả ====
print(f"""
📁 Kết quả tại:
   {os.path.join(PROJECT_DIR, PROJECT_NAME, RUN_NAME)}

Files:
   - weights/best.pt
   - weights/last.pt
   - results.png
   - confusion_matrix.png
   - exports/best.onnx
""")