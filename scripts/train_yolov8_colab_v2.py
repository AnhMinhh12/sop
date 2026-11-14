"""
Train YOLOv11 trên Google Colab — Mã Sản Phẩm TK_1A00-V0022
============================================================
3 Classes chuẩn từ Roboflow (TK_1A00-V0022.v1i.yolov11 / data.yaml):
  0: accessory (Phụ kiện / linh kiện phụ)
  1: hand      (Bàn tay công nhân)
  2: product   (Sản phẩm chính)

Tự động hóa:
  - Tự động nhận diện bài toán Segmentation (YOLO11-seg) hay Bounding Box (YOLO11-detect)
  - Tự động tìm kiếm file zip `TK_1A00-V0022.v1i.yolov11.zip` hoặc thư mục trên Google Drive / Colab
  - Cập nhật chuẩn hóa path trong data.yaml
  - Tự động export ONNX chuẩn: `TK_1A00-V0022.onnx` (để dùng trực tiếp trong hệ thống AI)
  - Verify lại model ONNX với dummy inference
  - Tự động backup vào Google Drive: `MyDrive/yolo11_safe_backup/`

Cách dùng:
  1. Nén thư mục dataset thành file `TK_1A00-V0022.v1i.yolov11.zip` rồi upload lên Google Drive (MyDrive).
     (Hoặc kéo thả trực tiếp file zip vào tab Files của Colab)
  2. Mở Google Colab -> Runtime > Change runtime type > T4 GPU.
  3. Copy toàn bộ code file này -> paste vào 1 cell trên Colab -> Run (Shift + Enter).
  4. Sau khi train xong, tải file `TK_1A00-V0022.onnx` về máy.
"""

import os
import shutil
import subprocess
from pathlib import Path

# ==== CẤU HÌNH DATASET / MODEL ====
DATASET_NAME = "TK_1A00-V0022.v1i.yolov11"
PRODUCT_CODE = "TK_1A00-V0022"
DRIVE_DATASET_ZIP = f"/content/drive/MyDrive/{DATASET_NAME}.zip"
DRIVE_DATASET_DIR = f"/content/{DATASET_NAME}"
DATA_YAML = os.path.join(DRIVE_DATASET_DIR, "data.yaml")
DRIVE_PROJECT_DIR = "/content/drive/MyDrive/yolo_runs"

# Model mặc định: yolo11n.pt (script sẽ tự chuyển thành yolo11n-seg.pt nếu dataset là polygon)
# Có thể đổi thành yolo11s.pt / yolo11m.pt nếu muốn model chính xác hơn
MODEL_SIZE = "yolo11n.pt"

# Epochs & Hyperparameters
EPOCHS = 150
IMG_SIZE = 640
BATCH_SIZE = 16  # Colab T4 VRAM 16GB chạy batch 16 rất nhẹ và mượt
PATIENCE = 30    # Dừng sớm nếu không cải thiện sau 30 epoch
WORKERS = 2

PROJECT_NAME = f"{PRODUCT_CODE}_yolov11"
RUN_NAME = "v1"

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
# 2) CÀI ĐẶT THƯ VIỆN
# =====================================================================
print("\n" + "=" * 60)
print("2) CÀI ĐẶT THƯ VIỆN")
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
# 4) CHUẨN BỊ DATASET (TỰ ĐỘNG DÒ TÌM & GIẢI NÉN)
# =====================================================================
print("\n" + "=" * 60)
print("4) CHUẨN BỊ DATASET")
print("=" * 60)

found_zip = None
local_dataset_zip = Path(f"/content/{DATASET_NAME}.zip")

if os.path.exists(DRIVE_DATASET_ZIP):
    found_zip = DRIVE_DATASET_ZIP
elif local_dataset_zip.exists():
    found_zip = str(local_dataset_zip)
else:
    # Dò toàn bộ file zip trong MyDrive và /content
    zip_candidates = []
    for root in (Path("/content/drive/MyDrive"), Path("/content")):
        if root.exists():
            zip_candidates.extend(root.rglob("*.zip"))
    zip_candidates = list(dict.fromkeys(zip_candidates))

    def normalized_name(value):
        return "".join(ch for ch in value.lower() if ch.isalnum())

    expected_name = normalized_name(PRODUCT_CODE)
    # Ưu tiên tìm file có chứa mã sản phẩm TK_1A00-V0022 hoặc tên dataset
    zip_matches = [
        p for p in zip_candidates
        if expected_name in normalized_name(p.stem) or "tk1a00v0022" in normalized_name(p.stem)
    ]
    if zip_matches:
        found_zip = str(zip_matches[0])
        print(f"✅ Tự động tìm thấy file zip: {found_zip}")
    elif len(zip_candidates) == 1:
        found_zip = str(zip_candidates[0])
        print(f"⚠️ Dùng file zip duy nhất tìm thấy: {found_zip}")
    elif zip_candidates:
        print("⚠️ Có nhiều file zip, danh sách tìm thấy:")
        for candidate in zip_candidates:
            print(f"   - {candidate}")

if found_zip:
    print(f"- Giải nén {found_zip} vào {DRIVE_DATASET_DIR} ...")
    sh(f"unzip -q -o '{found_zip}' -d '{DRIVE_DATASET_DIR}'")
    print("- Giải nén xong.")
else:
    # Nếu không có zip, tìm thư mục trên Drive
    drive_folder = f"/content/drive/MyDrive/{DATASET_NAME}"
    if not os.path.exists(drive_folder) and os.path.exists("/content/drive/MyDrive/"):
        folder_matches = [
            p for p in Path("/content/drive/MyDrive/").glob("*")
            if p.is_dir() and "tk_1a00" in p.name.lower()
        ]
        if folder_matches:
            drive_folder = str(folder_matches[0])
            print(f"✅ Tự động tìm thấy thư mục dataset trên Drive: {drive_folder}")

    if os.path.exists(drive_folder):
        print(f"- Copy dataset từ Drive vào {DRIVE_DATASET_DIR}...")
        sh(f"cp -r '{drive_folder}' '{DRIVE_DATASET_DIR}'")
        print("- Copy xong.")

# Tìm kiếm file data.yaml
if not os.path.exists(DATA_YAML):
    print(f"🔍 Đang tìm kiếm file data.yaml trong {DRIVE_DATASET_DIR} và /content/...")
    search_paths = (
        list(Path(DRIVE_DATASET_DIR).rglob("data.yaml")) + 
        list(Path(DRIVE_DATASET_DIR).rglob("data.yml")) +
        list(Path("/content/").glob("**/*tk*/**/data.yaml")) +
        list(Path("/content/").glob("**/*tk*/**/data.yml"))
    )
    if not search_paths and os.path.exists("/content/drive/MyDrive/"):
        search_paths = (
            list(Path("/content/drive/MyDrive/").glob("**/*tk*/**/data.yaml")) +
            list(Path("/content/drive/MyDrive/").glob("**/*tk*/**/data.yml"))
        )
    if not search_paths:
        broad_paths = []
        for root in (Path("/content"), Path("/content/drive/MyDrive")):
            if root.exists():
                broad_paths.extend(root.rglob("data.yaml"))
                broad_paths.extend(root.rglob("data.yml"))
        search_paths = [p for p in broad_paths if any((p.parent / split).exists()
                        for split in ("train", "valid", "test"))]
    
    if search_paths:
        actual_yaml = str(search_paths[0])
        print(f"✅ Tìm thấy data.yaml thực tế tại: {actual_yaml}")
        DATA_YAML = actual_yaml
        DRIVE_DATASET_DIR = str(Path(actual_yaml).parent)
    else:
        print(f"❌ Không tìm thấy data.yaml tại {DATA_YAML}")
        raise FileNotFoundError(
            f"Không tìm thấy data.yaml. Hãy upload file {DATASET_NAME}.zip "
            "vào MyDrive rồi chạy lại."
        )

DRIVE_DATASET_DIR = os.path.abspath(DRIVE_DATASET_DIR)
DATA_YAML = os.path.abspath(DATA_YAML)

print(f"📂 Dataset root: {DRIVE_DATASET_DIR}")
print(f"📄 Dataset YAML: {DATA_YAML}")

# Chuẩn hóa đường dẫn trong data.yaml
import yaml as _yaml
with open(DATA_YAML, "r", encoding="utf-8") as f:
    try:
        _data = _yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️ Lỗi đọc data.yaml: {e}")
        _data = {}

if _data:
    _data["path"] = DRIVE_DATASET_DIR
    for key in ["train", "val", "test"]:
        if key in _data and _data[key]:
            val = str(_data[key])
            if val.startswith("/content/"):
                try:
                    _data[key] = str(Path(val).relative_to(DRIVE_DATASET_DIR))
                except ValueError:
                    _data[key] = f"{key}/images"
    
    with open(DATA_YAML, "w", encoding="utf-8") as f:
        _yaml.safe_dump(_data, f, default_flow_style=False)
    print("📝 Đã chuẩn hóa đường dẫn trong file data.yaml.")

print("\n--- Nội dung data.yaml ---")
with open(DATA_YAML, "r", encoding="utf-8") as f:
    print(f.read())

# Default fallback nếu data.yaml thiếu class
default_classes = {0: 'accessory', 1: 'hand', 2: 'product'}

if _data and "names" in _data:
    names_raw = _data["names"]
    if isinstance(names_raw, dict):
        class_names_map = {int(k): str(v) for k, v in names_raw.items()}
    elif isinstance(names_raw, list):
        class_names_map = {i: str(v) for i, v in enumerate(names_raw)}
    else:
        class_names_map = default_classes
else:
    class_names_map = default_classes

print(f"\n📋 Danh sách class ({len(class_names_map)} classes): {class_names_map}")

# =====================================================================
# 4.4) TỰ ĐỘNG NHẬN DIỆN: SEGMENTATION HAY OBJECT DETECTION
# =====================================================================
box_count = 0
seg_count = 0

for split in ["train", "valid"]:
    lbl_dir = Path(DRIVE_DATASET_DIR) / split / "labels"
    if lbl_dir.exists():
        for lbl_file in lbl_dir.glob("*.txt"):
            try:
                with open(lbl_file, "r", encoding="utf-8") as lf:
                    for line in lf:
                        tokens = line.strip().split()
                        if not tokens or tokens[0].startswith("#"):
                            continue
                        try:
                            _ = int(tokens[0])
                            _ = [float(x) for x in tokens[1:]]
                            if len(tokens) == 5:
                                box_count += 1
                            elif len(tokens) >= 7 and len(tokens) % 2 == 1:
                                seg_count += 1
                        except ValueError:
                            continue
            except Exception:
                continue

print(f"\n📊 Kiểm tra định dạng nhãn dataset: {box_count} Bounding Boxes, {seg_count} Polygons")
is_segmentation = (seg_count > box_count) and (seg_count > 0)

if is_segmentation:
    print("🎯 PHÁT HIỆN DATASET DẠNG: INSTANCE SEGMENTATION (Polygon đa giác)")
    if not MODEL_SIZE.endswith("-seg.pt"):
        base = MODEL_SIZE.replace(".pt", "")
        MODEL_SIZE = f"{base}-seg.pt"
    print(f"👉 Tự động sử dụng mô hình Segmentation: {MODEL_SIZE}")
else:
    print("🎯 PHÁT HIỆN DATASET DẠNG: OBJECT DETECTION (Bounding box)")
    if "-seg" in MODEL_SIZE:
        MODEL_SIZE = MODEL_SIZE.replace("-seg", "")
    print(f"👉 Sử dụng mô hình Detection: {MODEL_SIZE}")

# Thống kê phân bố dataset
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
        if split == "train":
            lbl_dir = os.path.join(p, "labels")
            if os.path.isdir(lbl_dir):
                for lbl_file in os.listdir(lbl_dir):
                    if lbl_file.endswith(".txt"):
                        with open(os.path.join(lbl_dir, lbl_file), "r", encoding="utf-8") as f:
                            for line in f:
                                parts = line.strip().split()
                                if parts:
                                    try:
                                        cls = int(parts[0])
                                        if cls in class_counts:
                                            class_counts[cls] += 1
                                    except ValueError:
                                        pass

print("\nPhân bố class trong train set:")
for cls_id in sorted(class_names_map.keys()):
    name = class_names_map[cls_id]
    count = class_counts.get(cls_id, 0)
    bar = "█" * (min(count, 500) // 10)
    print(f"  [{cls_id}] {name:<12}: {count:>5} {bar}")


# =====================================================================
# 5) TRAIN YOLOv11 TỐI ƯU CHO MÃ TK_1A00-V0022
# =====================================================================
print("\n" + "=" * 60)
print(f"5) TRAIN - {EPOCHS} epochs, batch={BATCH_SIZE}, imgsz={IMG_SIZE}")
print(f"   Model: {MODEL_SIZE} | Product: {PRODUCT_CODE}")
print("=" * 60)

# Xóa cache nhãn cũ
sh(f"find '{DRIVE_DATASET_DIR}' -name '*.cache' -delete 2>/dev/null")

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
    # Augmentation tối ưu cho thao tác lắp ráp/kiểm tra linh kiện
    hsv_h=0.015,     # Tăng biến thiên màu nhẹ
    hsv_s=0.7,       # Tăng bão hòa màu để phân biệt sản phẩm vs phụ kiện vs tay
    hsv_v=0.4,       # Biến thiên độ sáng môi trường xưởng
    translate=0.1,   # Dịch chuyển nhẹ
    scale=0.5,       # Đổi tỉ lệ xa gần khi cầm sản phẩm/phụ kiện
    fliplr=0.5,      # Lật ngang
    flipud=0.0,      # Giữ nguyên góc nhìn camera từ trên xuống
    degrees=15.0,    # Xoay ±15° linh hoạt khi cầm nghiêng sản phẩm
    perspective=0.0005,
    mosaic=1.0,         # Ghép 4 ảnh tăng bối cảnh
    mixup=0.1,          # Trộn ảnh nhẹ
    copy_paste=0.2 if is_segmentation else 0.0,
    close_mosaic=15,    # Tắt mosaic 15 epoch cuối để hội tụ chính xác viền vật thể
    cos_lr=True,        # Giảm learning rate theo cosine
    amp=True,           # Tối ưu FP16 trên Colab GPU T4
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
    imgsz=IMG_SIZE,
    batch=BATCH_SIZE,
    conf=0.25,
    iou=0.6,
    device=device,
)

print(f"\n[KẾT QUẢ ĐÁNH GIÁ]")
if hasattr(metrics, "box") and metrics.box is not None:
    print(f"  Box mAP50    : {metrics.box.map50:.4f}")
    print(f"  Box mAP50-95 : {metrics.box.map:.4f}")
    print(f"  Precision    : {metrics.box.mp:.4f}")
    print(f"  Recall       : {metrics.box.mr:.4f}")
if hasattr(metrics, "seg") and metrics.seg is not None:
    print(f"  Mask mAP50   : {metrics.seg.map50:.4f}")
    print(f"  Mask mAP50-95: {metrics.seg.map:.4f}")


# =====================================================================
# 7) EXPORT ONNX
# =====================================================================
print("\n" + "=" * 60)
print("7) EXPORT ONNX")
print("=" * 60)

EXPORT_DIR = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# Export sang định dạng ONNX
model.export(
    format="onnx",
    imgsz=IMG_SIZE,
    simplify=True,
    opset=12,
    dynamic=False,
)

best_onnx_source = best_weights.replace(".pt", ".onnx")
onnx_path = os.path.join(EXPORT_DIR, f"{PRODUCT_CODE}.onnx")

if os.path.exists(best_onnx_source):
    shutil.copy2(best_onnx_source, onnx_path)
    print(f"  ✅ Copy thành công: {onnx_path}")
else:
    runs_dir = Path("/content/runs")
    found = False
    for f in runs_dir.rglob("*.onnx"):
        shutil.copy2(f, onnx_path)
        print(f"  ✅ Copy thành công từ fallback: {f} -> {onnx_path}")
        found = True
        break
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

    dummy = np.random.rand(1, 3, IMG_SIZE, IMG_SIZE).astype(np.float32)
    result = sess.run(None, {inp.name: dummy})
    print(f"  Test forward pass: OK, output shape {result[0].shape}")


# =====================================================================
# 9) BACKUP AN TOÀN VÀO GOOGLE DRIVE
# =====================================================================
print("\n" + "=" * 60)
print("9) BACKUP AN TOÀN VÀO GOOGLE DRIVE")
print("=" * 60)

SAFE_DIR = "/content/drive/MyDrive/yolo11_safe_backup"
os.makedirs(SAFE_DIR, exist_ok=True)

# Copy PT weights
for f in ["best.pt", "last.pt"]:
    src = os.path.join(DRIVE_PROJECT_DIR, PROJECT_NAME, RUN_NAME, "weights", f)
    if os.path.exists(src):
        dst = os.path.join(SAFE_DIR, f"{PRODUCT_CODE}_{f}")
        shutil.copy2(src, dst)
        print(f"  Backup PyTorch model -> {dst}")

# Copy model ONNX
if os.path.exists(onnx_path):
    dst_onnx = os.path.join(SAFE_DIR, f"{PRODUCT_CODE}.onnx")
    shutil.copy2(onnx_path, dst_onnx)
    print(f"  Backup ONNX model -> {dst_onnx}")

print(f"\n🛡️ Thư mục backup an toàn tại: {SAFE_DIR}")


# =====================================================================
# 10) HƯỚNG DẪN SAU KHI TRAIN
# =====================================================================
print("\n" + "=" * 60)
print("✅ HOÀN TẤT QUÁ TRÌNH HUẤN LUYỆN")
print("=" * 60)

final_onnx = os.path.join(SAFE_DIR, f"{PRODUCT_CODE}.onnx")
final_pt = os.path.join(SAFE_DIR, f"{PRODUCT_CODE}_best.pt")

print(f"""
📁 FILE CẦN TẢI VỀ MÁY (từ Google Drive của bạn):

   👉 {final_onnx}
      (File model ONNX hoàn chỉnh để triển khai chạy thực tế)

═══════════════════════════════════════════════════════════════════

📋 CÁC BƯỚC ĐƯA VÀO DỰ ÁN:
   1. Mở Google Drive, vào thư mục: yolo11_safe_backup/
   2. Tải file '{PRODUCT_CODE}.onnx' về máy tính.
   3. Copy file vào thư mục models của trạm/mã {PRODUCT_CODE}.
   4. Khởi chạy giám sát!
""")
