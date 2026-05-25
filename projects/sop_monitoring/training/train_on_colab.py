# ==========================================
# SCRIPT HUAN LUYEN YOLO TU DONG TREN COLAB
# Copy toan bo code nay vao 1 cell cua Google Colab va chay
# ==========================================

import os
import shutil
from pathlib import Path

# 0. CẤU HÌNH THÔNG TIN HUẤN LUYỆN
# Tên file zip bạn tải từ Roboflow lên Google Drive (ví dụ: "hand_sop.v1i.yolov11.zip")
# Hãy đảm bảo bạn đã tải file này lên thư mục MyDrive (Drive của tôi) trên Google Drive.
ZIP_NAME = "hand_sop.v1i.yolov11.zip"

# Mã sản phẩm đầu ra (Ví dụ: "TFF4040", "626287")
# File model xuất ra sẽ có tên là {PRODUCT_CODE}.onnx
PRODUCT_CODE = "TFF4040"

# Số epoch huấn luyện (Khuyên dùng từ 100 - 150 cho độ chính xác cao)
EPOCHS = 100

# 1. KET NOI GOOGLE DRIVE
from google.colab import drive
print(">>> Dang ket noi voi Google Drive...")
drive.mount('/content/drive')

# 2. CAU HINH DUONG DAN TREN GOOGLE DRIVE VA COLAB DYNAMIC
drive_zip_path = Path(f"/content/drive/MyDrive/{ZIP_NAME}")
# Thay thế đuôi .zip để tạo tên thư mục
folder_name = ZIP_NAME.replace(".zip", "")
drive_folder_path = Path(f"/content/drive/MyDrive/{folder_name}")
local_dataset_path = Path(f"/content/{folder_name}")

# 3. SAO CHEP VA GIAI NEN DU LIEU TREN COLAB
if drive_zip_path.exists():
    print(f"\n>>> Tim thay file zip: {drive_zip_path}. Dang giai nen sang Colab local...")
    import zipfile
    temp_extract = Path("/content/temp_extract")
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)
    
    # Giải nén vào thư mục tạm
    with zipfile.ZipFile(drive_zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    # Kiểm tra cấu trúc thư mục sau giải nén
    children = [c for c in temp_extract.glob("*") if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / "images").exists():
        # Trường hợp zip cả thư mục cha
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(children[0]), str(local_dataset_path))
    else:
        # Trường hợp zip ruột bên trong (chứa train, valid, test, data.yaml trực tiếp)
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(temp_extract), str(local_dataset_path))
        
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    print("✅ Giai nen du lieu thanh cong!")
    
elif drive_folder_path.exists():
    print(f"\n>>> Tim thay thu muc giai nen: {drive_folder_path}. Dang copy sang Colab local...")
    if local_dataset_path.exists():
        shutil.rmtree(local_dataset_path)
    shutil.copytree(drive_folder_path, local_dataset_path)
    print("✅ Sao chep du lieu thanh cong!")
    
else:
    raise FileNotFoundError(
        f"❌ Khong tim thay file '{drive_zip_path}' hoac thu muc '{drive_folder_path}' tren Drive. "
        f"Vui long tai file '{ZIP_NAME}' len My Drive (Drive cua toi) va kiem tra lai!"
    )

# 4. KHOI TAO / CAP NHAT LAI dataset.yaml VOI DUONG DAN CUC BO
print("\n>>> Dang cau hinh lai file dataset.yaml...")
import yaml

# Đọc cấu hình lớp từ file data.yaml gốc tải về từ Roboflow
original_yaml_path = local_dataset_path / "data.yaml"
class_names = {0: "hand"} # Mặc định

if original_yaml_path.exists():
    try:
        with open(original_yaml_path, "r", encoding="utf-8") as f:
            orig_data = yaml.safe_load(f)
            if orig_data and "names" in orig_data:
                class_names = orig_data["names"]
                print(f"✅ Tim thay danh sach lop tu data.yaml goc: {class_names}")
    except Exception as e:
        print(f"⚠️ Khong the doc class names tu data.yaml: {e}. Dung mac dinh: {class_names}")

# Kiểm tra thư mục thực tế để map đúng đường dẫn tương đối
train_rel = "train/images"
val_rel = "valid/images"
test_rel = "test/images"

if (local_dataset_path / "images/train").exists():
    train_rel = "images/train"
if (local_dataset_path / "images/val").exists():
    val_rel = "images/val"
if (local_dataset_path / "images/test").exists():
    test_rel = "images/test"

# Tạo chuỗi names cho yaml
names_str = ""
if isinstance(class_names, list):
    for i, name in enumerate(class_names):
        names_str += f"  {i}: {name}\n"
elif isinstance(class_names, dict):
    for k, v in class_names.items():
        names_str += f"  {k}: {v}\n"

yaml_content = f"""path: {local_dataset_path.as_posix()}
train: {train_rel}
val: {val_rel}
test: {test_rel}
names:
{names_str}"""

local_yaml_path = local_dataset_path / "dataset.yaml"
with open(local_yaml_path, 'w', encoding='utf-8') as f:
    f.write(yaml_content)
print(f"✅ Da cap nhat lai file cau hinh tai: {local_yaml_path}")
print(yaml_content)

# 5. CAI DAT THU VIEN ULTRALYTICS
print("\n>>> Dang cai dat thu vien Ultralytics...")
os.system("pip install ultralytics")
print("✅ Da cai dat Ultralytics!")

# 6. BAT DAU HUAN LUYEN MODEL YOLOv11
print(f"\n>>> Bat dau huan luyen model YOLOv11 voi {EPOCHS} epochs...")
from ultralytics import YOLO

# Dùng phiên bản lightweight YOLOv11n để có FPS cao nhất trên CPU Xeon server
model = YOLO("yolo11n.pt")

results = model.train(
    data=str(local_yaml_path),
    epochs=EPOCHS,        # Số lượng epoch huấn luyện
    imgsz=416,            # Bắt buộc theo config InferenceEngine CPU của server
    device=0,             # Chạy trên GPU của Colab
    workers=4
)
print("✅ Huan luyen hoan tat!")

# 7. EXPORT MODEL SANG ONNX CPU-OPTIMIZED
print("\n>>> Dang export model sang ONNX CPU-Optimized...")
# Đặt dynamic=False và imgsz=416 để ONNX Runtime trên CPU server chạy ổn định và nhanh nhất
onnx_path = model.export(format="onnx", imgsz=416, dynamic=False)
print(f"✅ Export ONNX thanh cong tai: {onnx_path}")

# 8. COPY MODEL ONNX DA HOAN THANH VE LAI GOOGLE DRIVE
print("\n>>> Dang copy model ONNX ve lai Google Drive cua ban...")
exported_file = Path(onnx_path)

# Tạo thư mục trên Drive nếu chưa có để lưu model
drive_folder_path.mkdir(parents=True, exist_ok=True)
dest_file_on_drive = drive_folder_path / f"{PRODUCT_CODE}.onnx"

shutil.copy(exported_file, dest_file_on_drive)
print(f"🎉 🎉 🎉 HOAN THANH!")
print(f"Model moi da duoc luu tai Google Drive: {dest_file_on_drive}")
print(f"Ban chi can vao Drive tai file '{PRODUCT_CODE}.onnx' ve va copy de vao models/yolo/ hoac shared/models/yolo/ cua Server.")
