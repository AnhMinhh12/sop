# ==========================================
# SCRIPT HUAN LUYEN YOLO TU DONG TREN COLAB
# Copy toan bo code nay vao 1 cell cua Google Colab va chay
# ==========================================

import os
import shutil
from pathlib import Path

# 1. KET NOI GOOGLE DRIVE
from google.colab import drive
print(">>> Dang ket noi voi Google Drive...")
drive.mount('/content/drive')

# 2. CAU HINH DUONG DAN TREN GOOGLE DRIVE VA COLAB
drive_zip_path = Path("/content/drive/MyDrive/dataset hop nhat.zip")
drive_folder_path = Path("/content/drive/MyDrive/dataset hop nhat")
local_dataset_path = Path("/content/dataset_hop_nhat")

# 3. SAO CHEP VA GIAI NEN DU LIEU TREN COLAB
if drive_zip_path.exists():
    print(f"\n>>> Tim thay file zip: {drive_zip_path}. Dang giai nen sang Colab local...")
    import zipfile
    temp_extract = Path("/content/temp_extract")
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)
    
    # Giai nen vao thu muc tam
    with zipfile.ZipFile(drive_zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    # Kiem tra cau truc thu muc sau giai nen
    children = [c for c in temp_extract.glob("*") if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / "images").exists():
        # Truong hop zip ca thu muc cha
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(children[0]), str(local_dataset_path))
    else:
        # Truong hop zip ruot ben trong
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
        "Vui long kiem tra lai xem da tai dung len My Drive (Drive cua toi) chua!"
    )

# 4. KHOI TAO / CAP NHAT LAI dataset.yaml VOI DUONG DAN CUC BO
print("\n>>> Dang cau hinh lai file dataset.yaml...")
yaml_content = f"""path: {local_dataset_path.as_posix()}
train: images/train
val: images/val
names:
  0: hand
"""
local_yaml_path = local_dataset_path / "dataset.yaml"
with open(local_yaml_path, 'w', encoding='utf-8') as f:
    f.write(yaml_content)
print(f"✅ Da cap nhat lai file cau hinh tai: {local_yaml_path}")

# 5. CAI DAT THU VIEN ULTRALYTICS
print("\n>>> Dang cai dat thu vien Ultralytics...")
os.system("pip install ultralytics")
print("✅ Da cai dat Ultralytics!")

# 6. BAT DAU HUAN LUYEN MODEL YOLOv11
print("\n>>> Bat dau huan luyen model YOLOv11...")
from ultralytics import YOLO

# Dung phien ban lightweight YOLOv11n de co FPS cao nhat tren CPU Xeon server
model = YOLO("yolo11n.pt")

results = model.train(
    data=str(local_yaml_path),
    epochs=100,           # So luong epoch chay. Co the tang len 150 neu muon do chinh xac cao hon.
    imgsz=416,            # Bat buoc theo config InferenceEngine CPU cua server
    device=0,             # Chay tren GPU cua Colab
    workers=4
)
print("✅ Huan luyen hoan tat!")

# 7. EXPORT MODEL SANG ONNX CPU-OPTIMIZED
print("\n>>> Dang export model sang ONNX CPU-Optimized...")
# Dat dynamic=False va imgsz=416 de ONNX Runtime tren CPU server chay on dinh nhat
onnx_path = model.export(format="onnx", imgsz=416, dynamic=False)
print(f"✅ Export ONNX thanh cong tai: {onnx_path}")

# 8. COPY MODEL ONNX DA HOAN THANH VE LAI GOOGLE DRIVE
print("\n>>> Dang copy model ONNX ve lai Google Drive cua ban...")
exported_file = Path(onnx_path)

# Tạo thư mục trên Drive nếu chưa có để lưu model
drive_folder_path.mkdir(parents=True, exist_ok=True)
dest_file_on_drive = drive_folder_path / "TFF4040.onnx"

shutil.copy(exported_file, dest_file_on_drive)
print(f"🎉 🎉 🎉 HOAN THANH!")
print(f"Model moi da duoc luu tai Google Drive: {dest_file_on_drive}")
print("Ban chi can vao Drive tai file 'TFF4040.onnx' ve va copy de vao models/yolo/ cua Server.")
