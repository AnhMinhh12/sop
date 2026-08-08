"""
Train YOLOv8 - chạy 1 cell duy nhất trên Google Colab
=====================================================
Cách dùng:
  1. Upload folder/zip dataset YOLO len Google Drive (MyDrive/tff4040.yolov8.zip)
  2. Mở Colab, tạo notebook moi, bật GPU (Runtime > Change runtime type > T4)
  3. Copy toan bo noi dung file nay, paste vao 1 cell, Run (Shift+Enter)
  4. Sau khi train xong, model nam trong MyDrive/yolo_runs/tff4040_yolov8/exp/
"""

import os
import shutil
import subprocess
from pathlib import Path

# ==== CẤU HÌNH ====
DRIVE_DATASET_ZIP = "/content/drive/MyDrive/tff4040.yolov8.zip"
DRIVE_DATASET_DIR = "/content/drive/MyDrive/tff4040.yolov8"
DATA_YAML = os.path.join(DRIVE_DATASET_DIR, "data.yaml")
DRIVE_PROJECT_DIR = "/content/drive/MyDrive/yolo_runs"

MODEL_SIZE = "yolov8n.pt"
EPOCHS = 100
IMG_SIZE = 640
BATCH_SIZE = 16
PATIENCE = 20
WORKERS = 2
PROJECT_NAME = "tff4040_yolov8"
RUN_NAME = "exp"

os.makedirs(DRIVE_PROJECT_DIR, exist_ok=True)


def sh(cmd):
    """Chạy shell command trên Colab, tương đương !cmd nhưng an toàn khi chạy trong .py."""
    print(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=False, text=True)


# =====================================================================
# 1) MOUNT GOOGLE DRIVE
# =====================================================================
print("\n" + "=" * 60)
print("1) MOUNT GOOGLE DRIVE")
print("=" * 60)

try:
    from google.colab import drive
    try:
        drive.flush_and_unmount()
        print("- Đã unmount drive cũ.")
    except Exception as e:
        print(f"- Không có drive cũ: {e}")
    sh("rm -rf /content/drive && mkdir -p /content/drive")
    drive.mount('/content/drive')
except ImportError:
    print("⚠️  Không chạy trên Google Colab, bỏ qua bước mount Drive.")
    print("   Script giả định dữ liệu đã có sẵn ở:", DRIVE_DATASET_DIR)


# =====================================================================
# 2) CÀI ULTRALYTICS
# =====================================================================
print("\n" + "=" * 60)
print("2) CÀI ULTRALYTICS")
print("=" * 60)
sh("pip install -q ultralytics>=8.2.0 opencv-python-headless")


# =====================================================================
# 3) KIỂM TRA GPU
# =====================================================================
print("\n" + "=" * 60)
print("3) KIỂM TRA GPU")
print("=" * 60)
import torch
print(f"CUDA available : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU            : {torch.cuda.get_device_name(0)}")
    props = torch.cuda.get_device_properties(0)
    total_mem = getattr(props, "total_memory", None) or getattr(props, "total_mem")
    print(f"VRAM (GB)      : {total_mem / 1e9:.2f}")
device = 0 if torch.cuda.is_available() else "cpu"


# =====================================================================
# 4) CHUẨN BỊ DATASET (giải nén zip nếu cần)
# =====================================================================
print("\n" + "=" * 60)
print("4) CHUẨN BỊ DATASET")
print("=" * 60)

if not os.path.exists(DATA_YAML):
    if not os.path.exists(DRIVE_DATASET_ZIP):
        print(f"❌ Không tìm thấy {DRIVE_DATASET_ZIP}")
        sh("ls -la /content/drive/MyDrive/ | head -30")
        raise FileNotFoundError(f"Upload {os.path.basename(DRIVE_DATASET_ZIP)} lên MyDrive/")
    print(f"- Giải nén {DRIVE_DATASET_ZIP} ...")
    sh(f"unzip -q -o '{DRIVE_DATASET_ZIP}' -d /content/drive/MyDrive/")
    print("- Giải nén xong.")

if not os.path.exists(DATA_YAML):
    print(f"❌ Vẫn không thấy {DATA_YAML}")
    sh(f"ls -la {DRIVE_DATASET_DIR}")
    raise FileNotFoundError(
        f"data.yaml không tồn tại sau khi giải nén. "
        f"Kiểm tra cấu trúc bên trong zip."
    )

print(f"✅ data.yaml: {DATA_YAML}")
print("\n--- data.yaml ---")
with open(DATA_YAML, "r") as f:
    print(f.read())


def count_split(split_dir):
    img_dir = os.path.join(split_dir, "images")
    lbl_dir = os.path.join(split_dir, "labels")
    if not os.path.isdir(img_dir):
        return 0, 0
    n_img = sum(len(files) for _, _, files in os.walk(img_dir))
    n_lbl = sum(len(files) for _, _, files in os.walk(lbl_dir))
    return n_img, n_lbl

print("Thống kê dataset:")
for split in ("train", "valid", "test"):
    p = os.path.join(DRIVE_DATASET_DIR, split)
    if os.path.isdir(p):
        ni, nl = count_split(p)
        print(f"  {split:<5} : {ni:>5} images, {nl:>5} labels")


# =====================================================================
# 5) TRAIN
# =====================================================================
print("\n" + "=" * 60)
print(f"5) TRAIN - {EPOCHS} epochs, batch={BATCH_SIZE}, imgsz={IMG_SIZE}")
print("=" * 60)

from ultralytics import YOLO

model = YOLO(MODEL_SIZE)
model.train(
    data=DATA_YAML,
    epochs=EPOCHS,
    imgsz=IMG_SIZE,
    batch=BATCH_SIZE,
    project=os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME),
    name=RUN_NAME,
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


# =====================================================================
# 6) VALIDATE trên valid set
# =====================================================================
print("\n" + "=" * 60)
print("6) VALIDATE")
print("=" * 60)

best_weights = os.path.join(
    DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "weights", "best.pt"
)
model = YOLO(best_weights)
metrics = model.val(
    data=DATA_YAML,
    imgsz=IMG_SIZE, batch=BATCH_SIZE,
    conf=0.25, iou=0.6,
    device=device,
)
print(f"mAP50      : {metrics.box.map50:.4f}")
print(f"mAP50-95   : {metrics.box.map:.4f}")
print(f"Precision  : {metrics.box.mp:.4f}")
print(f"Recall     : {metrics.box.mr:.4f}")


# =====================================================================
# 7) TEST (nếu có test set)
# =====================================================================
print("\n" + "=" * 60)
print("7) TEST")
print("=" * 60)

test_dir = os.path.join(DRIVE_DATASET_DIR, "test")
if os.path.isdir(test_dir):
    test_yaml = os.path.join(DRIVE_PROJECT_DIR, "_test_tmp.yaml")
    with open(DATA_YAML, "r") as f:
        original = f.read()
    with open(test_yaml, "w") as f:
        f.write(original.replace("valid/images", "test/images"))
    test_metrics = model.val(
        data=test_yaml, imgsz=IMG_SIZE, batch=BATCH_SIZE,
        conf=0.25, iou=0.6, device=device,
    )
    print(f"[TEST] mAP50    : {test_metrics.box.map50:.4f}")
    print(f"[TEST] mAP50-95 : {test_metrics.box.map:.4f}")
    os.remove(test_yaml)
else:
    print("Không có test set.")


# =====================================================================
# 8) EXPORT ONNX
# =====================================================================
print("\n" + "=" * 60)
print("8) EXPORT ONNX")
print("=" * 60)

EXPORT_DIR = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)
model.export(format="onnx", imgsz=IMG_SIZE, simplify=True, opset=12)

runs_dir = Path("/content/runs/detect") / RUN_NAME
for f in runs_dir.glob("*.onnx"):
    shutil.copy2(f, EXPORT_DIR)
print(f"✅ Exported to {EXPORT_DIR}")


# =====================================================================
# 9) INFERENCE MẪU
# =====================================================================
print("\n" + "=" * 60)
print("9) INFERENCE MẪU")
print("=" * 60)

sample_img = None
valid_images_dir = os.path.join(DRIVE_DATASET_DIR, "valid", "images")
if os.path.isdir(valid_images_dir):
    for ext in ("jpg", "jpeg", "png"):
        cands = list(Path(valid_images_dir).glob(f"*.{ext}"))
        if cands:
            sample_img = str(cands[0])
            break

if sample_img:
    preds = model.predict(source=sample_img, conf=0.25, save=True)
    print(f"Predicted : {sample_img}")
    print(f"Boxes     : {len(preds[0].boxes)}")
    print(f"Saved to  : {preds[0].save_dir}")
else:
    print("Không tìm thấy ảnh valid mẫu.")


# =====================================================================
# 10) KẾT QUẢ
# =====================================================================
print("\n" + "=" * 60)
print("10) KẾT QUẢ")
print("=" * 60)

run_root = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME)
print(f"""
📁 Kết quả train lưu tại:
   {run_root}

Files quan trọng:
   - weights/best.pt        : Model tốt nhất
   - weights/last.pt        : Checkpoint cuối
   - results.png            : Biểu đồ loss / metrics
   - confusion_matrix.png   : Confusion matrix
   - exports/best.onnx      : ONNX (deploy)
""")

# =====================================================================
# 11) BACKUP AN TOÀN — tránh mất khi Colab ngắt
# =====================================================================
print("\n" + "=" * 60)
print("11) BACKUP AN TOÀN")
print("=" * 60)

SAFE_DIR = "/content/drive/MyDrive/yolo_safe_backup"
os.makedirs(SAFE_DIR, exist_ok=True)

for f in ["best.pt", "last.pt"]:
    src = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "weights", f)
    if os.path.exists(src):
        dst = os.path.join(SAFE_DIR, f"tff4040_{f}")
        shutil.copy2(src, dst)
        print(f"Backup {f} -> {dst}")

# Mirror exports/*
exports_src = Path(EXPORT_DIR)
if exports_src.exists():
    for f in exports_src.iterdir():
        shutil.copy2(f, SAFE_DIR + "/")
        print(f"Backup {f.name} -> {SAFE_DIR}/")

print(f"\n🛡 Backup an toàn tại: {SAFE_DIR}")
print("   Tải về từ Google Drive nếu cần.")