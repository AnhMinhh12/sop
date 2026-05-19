# HƯỚNG DẪN HUẤN LUYỆN MODEL TRÊN GOOGLE COLAB

Vì server hiện tại không có card đồ họa GPU rời, chúng ta sẽ tận dụng GPU miễn phí của Google Colab để train model YOLOv11 chỉ trong khoảng **10-15 phút**.

---

### BƯỚC 1: Mở Google Colab
1. Truy cập vào trang: [Google Colab](https://colab.research.google.com/)
2. Đăng nhập bằng tài khoản Google có chứa thư mục `dataset hop nhat` trên Drive của bạn.
3. Chọn **New Notebook** (Sổ tay mới).

---

### BƯỚC 2: Cấu hình phần cứng GPU cho Colab
1. Trên menu của Colab, chọn: **Runtime** -> **Change runtime type** (Thời gian chạy -> Thay đổi loại thời gian chạy).
2. Tại mục **Hardware accelerator** (Trình tăng tốc phần cứng), chọn **T4 GPU**.
3. Nhấn **Save** (Lưu).

---

### BƯỚC 3: Chạy script huấn luyện tự động
Copy toàn bộ nội dung code dưới đây, dán vào một ô lệnh (cell) trên Colab và nhấn nút **Play** (hoặc tổ hợp phím `Ctrl + Enter`):

```python
# ==========================================================
# SCRIPT HUẤN LUYỆN YOLO TỰ ĐỘNG BẰNG DỮ LIỆU GOOGLE DRIVE
# ==========================================================

import os
import shutil
from pathlib import Path

# 1. KẾT NỐI GOOGLE DRIVE
from google.colab import drive
print(">>> Đang kết nối với Google Drive...")
drive.mount('/content/drive')

# 2. ĐƯỜNG DẪN TRÊN DRIVE VÀ COLAB LOCAL
drive_zip_path = Path("/content/drive/MyDrive/dataset hop nhat.zip")
drive_folder_path = Path("/content/drive/MyDrive/dataset hop nhat")
local_dataset_path = Path("/content/dataset_hop_nhat")

# 3. SAO CHẾP VÀ GIẢI NÉN DỮ LIỆU TRÊN COLAB
if drive_zip_path.exists():
    print(f"\n>>> Tìm thấy file zip: {drive_zip_path}. Đang giải nén sang Colab local...")
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
    print("✅ Giải nén dữ liệu thành công!")
    
elif drive_folder_path.exists():
    print(f"\n>>> Tìm thấy thư mục giải nén: {drive_folder_path}. Đang copy sang Colab local...")
    if local_dataset_path.exists():
        shutil.rmtree(local_dataset_path)
    shutil.copytree(drive_folder_path, local_dataset_path)
    print("✅ Sao chép dữ liệu thành công!")
    
else:
    raise FileNotFoundError(
        f"❌ Không tìm thấy file '{drive_zip_path}' hoặc thư mục '{drive_folder_path}' trên Drive. "
        "Vui lòng kiểm tra lại xem đã tải đúng lên My Drive (Drive của tôi) chưa!"
    )

# 4. CẬP NHẬT CẤU HÌNH PATH TRONG dataset.yaml
print("\n>>> Đang cấu hình lại file dataset.yaml...")
yaml_content = f"""path: {local_dataset_path.as_posix()}
train: images/train
val: images/val
names:
  0: hand
"""
local_yaml_path = local_dataset_path / "dataset.yaml"
with open(local_yaml_path, 'w', encoding='utf-8') as f:
    f.write(yaml_content)
print(f"✅ Đã cập nhật file cấu hình tại: {local_yaml_path}")

# 5. CÀI ĐẶT THƯ VIỆN ULTRALYTICS
print("\n>>> Đang cài đặt thư viện Ultralytics...")
os.system("pip install ultralytics")
print("✅ Đã cài đặt Ultralytics!")

# 6. HUẤN LUYỆN MODEL YOLOv11 NANO
print("\n>>> Bắt đầu huấn luyện model YOLOv11...")
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data=str(local_yaml_path),
    epochs=100,           # Chạy 100 epochs, mất khoảng 10-15 phút trên GPU T4
    imgsz=416,            # Kích thước ảnh chuẩn 416 của dự án
    device=0,             # GPU
    workers=4
)
print("✅ Huấn luyện hoàn tất!")

# 7. EXPORT SANG ONNX CPU-OPTIMIZED
print("\n>>> Đang xuất model sang ONNX cho CPU server...")
onnx_path = model.export(format="onnx", imgsz=416, dynamic=False)
print(f"✅ Export ONNX thành công tại: {onnx_path}")

# 8. COPY FILE ONNX VỀ LẠI THƯ MỤC TRÊN GOOGLE DRIVE
print("\n>>> Đang sao chép file model ONNX về lại Drive...")
exported_file = Path(onnx_path)

drive_folder_path.mkdir(parents=True, exist_ok=True)
dest_file_on_drive = drive_folder_path / "TFF4040.onnx"

shutil.copy(exported_file, dest_file_on_drive)
print(f"🎉 🎉 🎉 HOÀN THÀNH!")
print(f"Model mới đã được lưu trên Drive của bạn tại: {dest_file_on_drive}")
```

---

### BƯỚC 4: Tải model về Server và chạy hệ thống
1. Khi chạy xong, bạn mở Google Drive ra, truy cập vào thư mục `dataset hop nhat`.
2. Bạn sẽ thấy một file mới được sinh ra tên là **`TFF4040.onnx`**.
3. Tải file này về máy server của bạn.
4. Ghi đè file này vào thư mục của dự án theo đường dẫn:
   📂 `shared/models/yolo/TFF4040.onnx`

Hệ thống giám sát SOP sẽ tự động cập nhật mô hình mới và chạy mượt mà trên CPU Xeon của bạn!
