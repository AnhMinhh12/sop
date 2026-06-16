# ==========================================
# SCRIPT HUAN LUYEN YOLO TU DONG TREN COLAB
# Copy toan bo code nay vao 1 cell cua Google Colab va chay
# ==========================================

import os
import shutil
from pathlib import Path

# 0. CẤU HÌNH THÔNG TIN HUẤN LUYỆN
# Tên file zip bạn tải lên Google Drive (ví dụ: "laprap.yolov11.zip")
# Hãy đảm bảo bạn đã tải file này lên thư mục MyDrive (Drive của tôi) trên Google Drive.
ZIP_NAME = "laprap_justhand.zip"

# Mã sản phẩm đầu ra (Ví dụ: "TFF4040", "laprap")
# File model xuất ra sẽ có tên là {PRODUCT_CODE}.onnx
PRODUCT_CODE = "laprap"

# Số epoch huấn luyện (Khuyên dùng từ 100 - 150 cho độ chính xác cao)
EPOCHS = 100

# 1. KET NOI GOOGLE DRIVE HOAC DUNG LOCAL ZIP FILE
folder_name = ZIP_NAME.replace(".zip", "")
local_zip_path = Path(f"/content/{ZIP_NAME}")
local_dataset_path = Path(f"/content/{folder_name}")

use_drive = True

# Kiểm tra nếu Google Drive đã được kết nối sẵn (ví dụ: qua nút Mount Drive trên giao diện Colab)
if Path("/content/drive/MyDrive").exists():
    print(">>> Google Drive da duoc ket noi san tu truoc hoac qua giao dien Colab. Bo qua buoc mount.")
    use_drive = True
# Nếu người dùng đã upload trực tiếp file zip lên Colab
elif local_zip_path.exists():
    print(f"\n>>> Phat hien file zip '{ZIP_NAME}' da duoc upload truc tiep len Colab. Bo qua mount Google Drive.")
    use_drive = False
else:
    try:
        from google.colab import drive
        print(">>> Dang ket noi voi Google Drive...")
        # Sử dụng force_remount=True để tránh lỗi cache mount cũ
        drive.mount('/content/drive', force_remount=True)
    except Exception as e:
        print(f"\n⚠️ Mount Google Drive that bai: {e}")
        print("="*60)
        print("💡 HUONG DAN KHAC PHUC:")
        print("Vì bạn đã up folder lên My Drive, hãy kết nối Drive với Colab qua giao diện:")
        print("1. Click vào biểu tượng THU MỤC (Files) ở thanh công cụ bên trái Google Colab.")
        print("2. Click vào biểu tượng Mount Drive (Thư mục có logo Google Drive ở giữa thanh menu).")
        print("3. Chọn 'Kết nối với Google Drive' và đăng nhập/cấp quyền khi cửa sổ hiện lên.")
        print("4. Sau khi kết nối thành công (thư mục 'drive' xuất hiện ở bên trái), hãy chạy lại cell này.")
        print("="*60)
        raise e

# 2. CAU HINH DUONG DAN TREN GOOGLE DRIVE VA COLAB DYNAMIC
drive_zip_path = Path(f"/content/drive/MyDrive/{ZIP_NAME}")
drive_folder_path = Path(f"/content/drive/MyDrive/{folder_name}")

# 3. SAO CHEP VA GIAI NEN DU LIEU TREN COLAB
if not use_drive:
    print(f"\n>>> Dang giai nen file zip local: {local_zip_path}...")
    import zipfile
    temp_extract = Path("/content/temp_extract")
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(local_zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    children = [c for c in temp_extract.glob("*") if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / "images").exists():
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(children[0]), str(local_dataset_path))
    else:
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(temp_extract), str(local_dataset_path))
        
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    print("✅ Giai nen du lieu local thanh cong!")

elif drive_zip_path.exists():
    print(f"\n>>> Tim thay file zip tren Drive: {drive_zip_path}. Dang giai nen sang Colab local...")
    import zipfile
    temp_extract = Path("/content/temp_extract")
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    temp_extract.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(drive_zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
        
    children = [c for c in temp_extract.glob("*") if c.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir() and (children[0] / "images").exists():
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(children[0]), str(local_dataset_path))
    else:
        if local_dataset_path.exists():
            shutil.rmtree(local_dataset_path)
        shutil.move(str(temp_extract), str(local_dataset_path))
        
    if temp_extract.exists():
        shutil.rmtree(temp_extract)
    print("✅ Giai nen du lieu tu Drive thanh cong!")
    
elif drive_folder_path.exists():
    print(f"\n>>> Tim thay thu muc giai nen tren Drive: {drive_folder_path}. Dang copy sang Colab local...")
    if local_dataset_path.exists():
        shutil.rmtree(local_dataset_path)
    shutil.copytree(drive_folder_path, local_dataset_path)
    print("✅ Sao chep du lieu tu Drive thanh cong!")
    
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

# Kiểm tra thư mục thực tế và tự động chia split (train/val/test) nếu chưa có
print("\n>>> Dang kiem tra va chia split (train/val/test)...")
import random
random.seed(42)

# Xác định các thư mục
train_images_dir = local_dataset_path / "train/images"
train_labels_dir = local_dataset_path / "train/labels"

# Nếu dữ liệu nằm ở cấu trúc khác (ví dụ: images/train) thì tìm kiếm
if not train_images_dir.exists():
    for root, dirs, files in os.walk(local_dataset_path):
        if 'train' in dirs and os.path.exists(os.path.join(root, 'train', 'images')):
            train_images_dir = Path(root) / "train/images"
            train_labels_dir = Path(root) / "train/labels"
            break

# Kiểm tra xem có thư mục validation hoặc test thực sự chứa ảnh không
val_images_dir = local_dataset_path / "valid/images"
if not val_images_dir.exists():
    val_images_dir = local_dataset_path / "images/val"

has_validation = False
if val_images_dir.exists():
    val_imgs = list(val_images_dir.glob("*.jpg")) + list(val_images_dir.glob("*.png")) + list(val_images_dir.glob("*.jpeg"))
    if len(val_imgs) > 0:
        has_validation = True

if not has_validation:
    print("⚠️ Khong tim thay tap validation. Bat dau tu dong chia split (train: 80%, val: 10%, test: 10%)...")
    
    if not train_images_dir.exists():
        raise FileNotFoundError(f"❌ Khong tim thay thu muc chua anh train tai: {train_images_dir}")
        
    all_imgs = list(train_images_dir.glob("*.jpg")) + list(train_images_dir.glob("*.png")) + list(train_images_dir.glob("*.jpeg"))
    print(f"Tong so anh tim thay: {len(all_imgs)}")
    
    if len(all_imgs) == 0:
        raise ValueError(f"❌ Thu muc {train_images_dir} khong chua file anh nao!")
        
    random.shuffle(all_imgs)
    
    # Tính toán index split
    total = len(all_imgs)
    train_end = int(total * 0.8)
    val_end = train_end + int(total * 0.1)
    
    splits = {
        'train': all_imgs[:train_end],
        'val': all_imgs[train_end:val_end],
        'test': all_imgs[val_end:]
    }
    
    # Tạo thư mục mới để chứa split
    new_images_dir = local_dataset_path / "split_data/images"
    new_labels_dir = local_dataset_path / "split_data/labels"
    
    for split_name, split_files in splits.items():
        split_img_dir = new_images_dir / split_name
        split_lbl_dir = new_labels_dir / split_name
        split_img_dir.mkdir(parents=True, exist_ok=True)
        split_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        for img_path in split_files:
            # Copy ảnh sang thư mục split tương ứng
            shutil.copy2(img_path, split_img_dir / img_path.name)
            
            # Tìm label tương ứng
            lbl_name = img_path.stem + ".txt"
            lbl_path = train_labels_dir / lbl_name
            if lbl_path.exists():
                shutil.copy2(lbl_path, split_lbl_dir / lbl_name)
            else:
                # Tạo label trống nếu không có
                with open(split_lbl_dir / lbl_name, 'w') as f:
                    pass
                    
    # Cập nhật đường dẫn tương đối cho dataset.yaml
    train_rel = "split_data/images/train"
    val_rel = "split_data/images/val"
    test_rel = "split_data/images/test"
    print("✅ Tu dong chia split thanh cong!")
else:
    print("✅ Tap validation hop le da ton tai. Giu nguyen split.")
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

# 8. COPY MODEL ONNX DA HOAN THANH VE LAI GOOGLE DRIVE HOAC COLAB LOCAL
exported_file = Path(onnx_path)

if use_drive:
    print("\n>>> Dang copy model ONNX ve lai Google Drive cua ban...")
    try:
        drive_folder_path.mkdir(parents=True, exist_ok=True)
        dest_file_on_drive = drive_folder_path / f"{PRODUCT_CODE}.onnx"
        shutil.copy(exported_file, dest_file_on_drive)
        print(f"🎉 🎉 🎉 HOAN THANH!")
        print(f"Model moi da duoc luu tai Google Drive: {dest_file_on_drive}")
        print(f"Ban chi can vao Drive tai file '{PRODUCT_CODE}.onnx' ve va copy de vao models/yolo/ hoac shared/models/yolo/ cua Server.")
    except Exception as e:
        print(f"⚠️ Khong the copy vao Drive: {e}. Model duoc luu lai tai Colab local.")
        dest_file_local = Path(f"/content/{PRODUCT_CODE}.onnx")
        shutil.copy(exported_file, dest_file_local)
        print(f"🎉 🎉 🎉 HOAN THANH!")
        print(f"Hay tai file '{PRODUCT_CODE}.onnx' truc tiep tu muc Files ben trai Google Colab.")
else:
    dest_file_local = Path(f"/content/{PRODUCT_CODE}.onnx")
    shutil.copy(exported_file, dest_file_local)
    print(f"🎉 🎉 🎉 HOAN THANH!")
    print(f"Model moi da duoc luu tai Colab local: {dest_file_local}")
    print(f"Ban hay click chuot phai vao file '{PRODUCT_CODE}.onnx' o muc Files ben trai Google Colab va chon 'Download' de tai ve máy.")
