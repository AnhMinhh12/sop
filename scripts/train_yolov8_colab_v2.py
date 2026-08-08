"""
Train YOLOv8 trên Google Colab — phiên bản v2 cho TFF4040
=========================================================
Cải tiến so với bản cũ:
  - Tự động nhận diện cấu trúc dataset giải nén từ Roboflow/Google Drive
  - Cập nhật tự động path trong data.yaml tránh lỗi đường dẫn
  - Augmentation mạnh hơn để xử lý class ít data (sp, robot)
  - Copy-paste, mosaic, mixup tăng để tăng tỉ lệ positive sample
  - Close mosaic ở 80% epoch (YOLOv8 mặc định)
  - Export ONNX + rename thành max.onnx
  - Verify lại model với dummy inference

Cách dùng:
  1. Upload folder/zip dataset YOLO lên Google Drive (MyDrive/tff4040.v1-07-08.yolov8.zip hoặc folder tff4040.v1-07-08.yolov8)
  2. Mở Colab → Runtime > Change runtime type > T4 GPU
  3. Copy toàn bộ nội dung file này → paste vào 1 cell → Run (Shift+Enter)
  4. Sau khi train xong, tải file max.onnx về thư mục shared/models/yolo/

Dataset YOLOv8 cần có cấu trúc:
  tff4040.v1-07-08.yolov8/
  ├── data.yaml
  ├── train/images/*.jpg
  ├── train/labels/*.txt
  ├── valid/images/*.jpg
  └── valid/labels/*.txt
"""

import os
import shutil
import subprocess
from pathlib import Path

# ==== CẤU HÌNH - ĐÃ CẬP NHẬT THEO DATASET MỚI ====
DRIVE_DATASET_ZIP = "/content/drive/MyDrive/tff4040_08_08.zip"
DRIVE_DATASET_DIR = "/content/tff4040_08_08"
DATA_YAML = os.path.join(DRIVE_DATASET_DIR, "data.yaml")
DRIVE_PROJECT_DIR = "/content/drive/MyDrive/yolo_runs"

# Có thể tăng lên yolov8s/m để model mạnh hơn (chậm hơn ~3x)
MODEL_SIZE = "yolov8n.pt"

# Epochs: với ~800-1500 ảnh, 100-150 epochs là đủ
# YOLOv8 sẽ tự early-stop nếu không cải thiện sau PATIENCE epoch
EPOCHS = 150
IMG_SIZE = 640
BATCH_SIZE = 16  # Colab T4 VRAM 16GB, batch 16 ổn với yolov8n/s
PATIENCE = 30    # Tăng patience vì class ít data sẽ dao động
WORKERS = 2

PROJECT_NAME = "tff4040_yolov8"
RUN_NAME = "exp_v2_aug"

os.makedirs(DRIVE_PROJECT_DIR, exist_ok=True)


def sh(cmd):
    """Chạy shell command trên Colab."""
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
    except Exception:
        pass
    sh("rm -rf /content/drive && mkdir -p /content/drive")
    drive.mount('/content/drive')
except ImportError:
    print("⚠️  Không chạy trên Google Colab, bỏ qua bước mount Drive.")


# =====================================================================
# 2) CÀI ĐẶT
# =====================================================================
print("\n" + "=" * 60)
print("2) CÀI ĐẶT")
print("=" * 60)
sh("pip install -q ultralytics>=8.2.0 opencv-python-headless onnx onnxruntime pyyaml")


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
# 4) CHUẨN BỊ DATASET
# =====================================================================
print("\n" + "=" * 60)
print("4) CHUẨN BỊ DATASET")
print("=" * 60)

# 4.1) Giải nén file zip hoặc sao chép thư mục từ Drive sang local Colab (/content/tff4040_08_08)
# Việc giải nén trên ổ SSD cục bộ của Colab giúp tăng tốc độ train gấp nhiều lần và tránh ô nhiễm Google Drive
if os.path.exists(DRIVE_DATASET_ZIP):
    print(f"- Giải nén {DRIVE_DATASET_ZIP} vào {DRIVE_DATASET_DIR} ...")
    sh(f"unzip -q -o '{DRIVE_DATASET_ZIP}' -d '{DRIVE_DATASET_DIR}'")
    print("- Giải nén xong.")
else:
    # Nếu không có zip, mà user upload thư mục lên Drive
    drive_folder = "/content/drive/MyDrive/tff4040_08_08"
    if os.path.exists(drive_folder):
        print(f"- Copy dataset từ Drive vào {DRIVE_DATASET_DIR} để train nhanh hơn...")
        sh(f"cp -r '{drive_folder}' '{DRIVE_DATASET_DIR}'")
        print("- Copy xong.")

# 4.2) Tự động phát hiện vị trí chính xác của data.yaml (phòng khi folder bị lồng hoặc flat)
if not os.path.exists(DATA_YAML):
    print(f"🔍 Đang tìm kiếm file data.yaml trong {DRIVE_DATASET_DIR}...")
    search_path = list(Path(DRIVE_DATASET_DIR).rglob("data.yaml")) + list(Path(DRIVE_DATASET_DIR).rglob("data.yml"))
    if not search_path and os.path.exists("/content/drive/MyDrive/"):
        # Tìm rộng hơn trong MyDrive phòng trường hợp khác
        search_path = list(Path("/content/drive/MyDrive/").glob("**/tff4040_08_08/**/data.yaml"))
    
    if search_path:
        actual_yaml = str(search_path[0])
        print(f"✅ Tìm thấy data.yaml thực tế tại: {actual_yaml}")
        DATA_YAML = actual_yaml
        DRIVE_DATASET_DIR = str(Path(actual_yaml).parent)
    else:
        print(f"❌ Không tìm thấy data.yaml tại {DATA_YAML}")
        sh("ls -la /content/drive/MyDrive/ | head -30")
        raise FileNotFoundError("Không tìm thấy data.yaml trong thư mục dataset.")

# Cập nhật đường dẫn tuyệt đối
DRIVE_DATASET_DIR = os.path.abspath(DRIVE_DATASET_DIR)
DATA_YAML = os.path.abspath(DATA_YAML)

print(f"📂 Dataset root: {DRIVE_DATASET_DIR}")
print(f"📄 Dataset YAML: {DATA_YAML}")

# 4.3) Đọc và tự động chuẩn hóa file data.yaml
import yaml as _yaml
with open(DATA_YAML, "r") as f:
    try:
        _data = _yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️ Lỗi đọc data.yaml: {e}")
        _data = {}

if _data:
    # Cập nhật path tuyệt đối để YOLO không bị lỗi tìm ảnh
    _data["path"] = DRIVE_DATASET_DIR
    # Đảm bảo các đường dẫn con là tương đối với path
    for key in ["train", "val", "test"]:
        if key in _data and _data[key]:
            val = _data[key]
            # Nếu chứa đường dẫn tuyệt đối cũ, chuyển về tương đối
            if val.startswith("/content/"):
                try:
                    _data[key] = str(Path(val).relative_to(DRIVE_DATASET_DIR))
                except ValueError:
                    # Nếu không cùng thư mục cha, trỏ thẳng vào thư mục con chuẩn
                    _data[key] = f"{key}/images"
    
    with open(DATA_YAML, "w") as f:
        _yaml.safe_dump(_data, f, default_flow_style=False)
    print("📝 Đã chuẩn hóa thành công file data.yaml.")

print("\n--- data.yaml hiện tại ---")
with open(DATA_YAML, "r") as f:
    print(f.read())

if _data and "names" in _data:
    names_raw = _data["names"]
    if isinstance(names_raw, dict):
        class_names_map = {int(k): str(v) for k, v in names_raw.items()}
    elif isinstance(names_raw, list):
        class_names_map = {i: str(v) for i, v in enumerate(names_raw)}
    else:
        raise ValueError(f"Format names không hỗ trợ: {type(names_raw)}")
else:
    raise ValueError("data.yaml không có key 'names'")

n_classes = len(class_names_map)
print(f"\n📋 Danh sách class: {class_names_map}")

# Thống kê phân bố tập dữ liệu
def count_split(split_dir):
    img_dir = os.path.join(split_dir, "images")
    lbl_dir = os.path.join(split_dir, "labels")
    if not os.path.isdir(img_dir):
        return 0, 0
    n_img = sum(len(files) for _, _, files in os.walk(img_dir))
    n_lbl = sum(len(files) for _, _, files in os.walk(lbl_dir))
    return n_img, n_lbl

print("\nThống kê dataset:")
class_counts = {i: 0 for i in class_names_map.keys()}

for split in ("train", "valid", "test"):
    p = os.path.join(DRIVE_DATASET_DIR, split)
    if os.path.isdir(p):
        ni, nl = count_split(p)
        print(f"  {split:<5} : {ni:>5} images, {nl:>5} labels")

        # Đếm class trong nhãn tập train
        if split == "train":
            lbl_dir = os.path.join(p, "labels")
            if os.path.isdir(lbl_dir):
                for lbl_file in os.listdir(lbl_dir):
                    if lbl_file.endswith(".txt"):
                        with open(os.path.join(lbl_dir, lbl_file)) as f:
                            for line in f:
                                parts = line.strip().split()
                                if parts:
                                    cls = int(parts[0])
                                    if cls in class_counts:
                                        class_counts[cls] += 1

print("\nPhân bố class trong train set:")
for cls_id in sorted(class_names_map.keys()):
    name = class_names_map[cls_id]
    count = class_counts[cls_id]
    bar = "█" * (min(count, 500) // 10)
    print(f"  {name:<8}: {count:>5} {bar}")


# =====================================================================
# 5) TRAIN với augmentation mạnh
# =====================================================================
print("\n" + "=" * 60)
print(f"5) TRAIN - {EPOCHS} epochs, batch={BATCH_SIZE}, imgsz={IMG_SIZE}")
print("   Augmentation mạnh: mosaic=1.0, mixup=0.15, copy_paste=0.3")
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
    # Augmentation cơ bản (tăng mạnh so với default)
    hsv_h=0.02,     # Tăng hue
    hsv_s=0.8,      # Tăng saturation
    hsv_v=0.5,      # Tăng value/brightness
    translate=0.15, # Tăng dịch chuyển
    scale=0.6,      # Tăng scale variation
    fliplr=0.5,
    flipud=0.0,     # Giữ nguyên hướng khuôn máy
    degrees=5.0,    # Xoay nhẹ ±5°
    perspective=0.0005,
    # Augmentation nâng cao
    mosaic=1.0,        # Tạo ảnh ghép từ 4 ảnh
    mixup=0.15,        # Tạo ảnh lai giữa các ảnh
    copy_paste=0.3,    # Sao chép vật thể giữa các ảnh
    close_mosaic=20,   # Tắt mosaic ở 20 epoch cuối để học viền tinh tế hơn
    cos_lr=True,       # Cosine learning rate scheduler
    amp=True,          # Kích hoạt Auto Mixed Precision
)


# =====================================================================
# 6) VALIDATE
# =====================================================================
print("\n" + "=" * 60)
print("6) VALIDATE trên valid set")
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
print(f"\n[VALID]")
print(f"  mAP50      : {metrics.box.map50:.4f}")
print(f"  mAP50-95   : {metrics.box.map:.4f}")
print(f"  Precision  : {metrics.box.mp:.4f}")
print(f"  Recall     : {metrics.box.mr:.4f}")


# =====================================================================
# 7) EXPORT ONNX (Output name: max.onnx)
# =====================================================================
print("\n" + "=" * 60)
print("7) EXPORT ONNX")
print("=" * 60)

EXPORT_DIR = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# Export model
model.export(
    format="onnx",
    imgsz=IMG_SIZE,
    simplify=True,
    opset=12,
    dynamic=False,
)

# Di chuyển và đổi tên thành TFF4040_final.onnx
best_onnx_source = best_weights.replace(".pt", ".onnx")
onnx_path = os.path.join(EXPORT_DIR, "TFF4040_final.onnx")

if os.path.exists(best_onnx_source):
    shutil.copy2(best_onnx_source, onnx_path)
    print(f"  ✅ Copy thành công ONNX: {best_onnx_source} → {onnx_path}")
else:
    # Fallback tìm trong runs default của ultralytics
    runs_dir = Path("/content/runs/detect") / RUN_NAME
    found = False
    for f in runs_dir.glob("*.onnx"):
        shutil.copy2(f, onnx_path)
        print(f"  ✅ Copy thành công từ fallback: {f} → {onnx_path}")
        found = True
    if not found:
        print("⚠️ Không tìm thấy file ONNX được sinh ra sau export.")


# =====================================================================
# 8) VERIFY ONNX
# =====================================================================
print("\n" + "=" * 60)
print("8) VERIFY ONNX")
print("=" * 60)

if os.path.exists(onnx_path):
    import onnxruntime as ort
    import numpy as np

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    out = sess.get_outputs()[0]
    print(f"  Input  : {inp.name} {inp.shape} {inp.type}")
    print(f"  Output : {out.name} {out.shape} {out.type}")

    # Chạy thử forward pass với mảng ngẫu nhiên
    dummy = np.random.rand(1, 3, IMG_SIZE, IMG_SIZE).astype(np.float32)
    result = sess.run(None, {inp.name: dummy})
    print(f"  Test forward pass: OK, output shape {result[0].shape}")


# =====================================================================
# 9) TEST NHANH VỚI VIDEO (nếu có)
# =====================================================================
print("\n" + "=" * 60)
print("9) TEST NHANH VỚI VIDEO (optional)")
print("=" * 60)

TEST_VIDEO_DRIVE = "/content/drive/MyDrive/test_video.mp4"
if os.path.exists(TEST_VIDEO_DRIVE) and os.path.exists(onnx_path):
    print(f"  Đang test trên video: {TEST_VIDEO_DRIVE}")
    test_model = YOLO(onnx_path, task="detect")
    preds = test_model.predict(
        source=TEST_VIDEO_DRIVE,
        conf=0.15,
        save=True,
        project="/content/drive/MyDrive/yolo_test_outputs",
        name="video_test",
    )
    print(f"  Kết quả lưu tại: /content/drive/MyDrive/yolo_test_outputs/video_test/")
else:
    print(f"  Bỏ qua test video (không có {TEST_VIDEO_DRIVE} hoặc model ONNX).")


# =====================================================================
# 10) BACKUP AN TOÀN
# =====================================================================
print("\n" + "=" * 60)
print("10) BACKUP AN TOÀN")
print("=" * 60)

SAFE_DIR = "/content/drive/MyDrive/yolo_safe_backup_v2"
os.makedirs(SAFE_DIR, exist_ok=True)

# Copy PT weights
for f in ["best.pt", "last.pt"]:
    src = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "weights", f)
    if os.path.exists(src):
        dst = os.path.join(SAFE_DIR, f"tff4040_v2_{f}")
        shutil.copy2(src, dst)
        print(f"  Backup PyTorch model → {dst}")

# Copy TFF4040_final.onnx
if os.path.exists(onnx_path):
    dst_onnx = os.path.join(SAFE_DIR, "TFF4040_final.onnx")
    shutil.copy2(onnx_path, dst_onnx)
    print(f"  Backup ONNX model → {dst_onnx}")

print(f"\n🛡 Thư mục backup an toàn tại: {SAFE_DIR}")


# =====================================================================
# 11) HƯỚNG DẪN SAU KHI TRAIN
# =====================================================================
print("\n" + "=" * 60)
print("✅ HOÀN TẤT")
print("=" * 60)

final_onnx = os.path.join(SAFE_DIR, "TFF4040_final.onnx")
final_pt = os.path.join(SAFE_DIR, "tff4040_v2_best.pt")

print(f"""
📁 FILES CẦN TẢI VỀ (từ Google Drive của bạn):

   1. {final_onnx}
      ← File model ONNX dùng để chạy deploy thực tế (đầu ra: TFF4040_final.onnx)

   2. {final_pt}
      ← File model PyTorch gốc để lưu trữ / retrain sau này nếu cần

═══════════════════════════════════════════════════════════════════

📋 CÁC BƯỚC THỰC HIỆN TIẾP THEO:

   1. Truy cập Google Drive cá nhân.
   2. Tìm thư mục: yolo_safe_backup_v2/
   3. Tải file "TFF4040_final.onnx" và "tff4040_v2_best.pt" về máy.
   4. Copy file "TFF4040_final.onnx" vào dự án local tại đường dẫn:
      shared/models/yolo/TFF4040_final.onnx (hoặc cập nhật config.yaml trỏ tới tên file này)
""")

# Xác minh file thực sự có mặt trong backup
for label, path in [("ONNX Model", final_onnx), ("PT Model", final_pt)]:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  ✅ [OK] {label}: {path} ({size_mb:.1f} MB)")
    else:
        print(f"  ❌ [ERROR] {label} không tìm thấy tại đường dẫn backup!")
