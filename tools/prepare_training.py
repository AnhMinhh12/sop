import os
import shutil
import random

DATA_DIR = "training/data"
OUTPUT_DIR = "training/yolo_dataset"
TRAIN_RATIO = 0.8

def prepare():
    images = [f for f in os.listdir(f"{DATA_DIR}/images") if f.endswith('.jpg')]
    random.shuffle(images)
    
    split_idx = int(len(images) * TRAIN_RATIO)
    train_images = images[:split_idx]
    val_images = images[split_idx:]

    for split, imgs in [('train', train_images), ('val', val_images)]:
        img_path = f"{OUTPUT_DIR}/images/{split}"
        lbl_path = f"{OUTPUT_DIR}/labels/{split}"
        os.makedirs(img_path, exist_ok=True)
        os.makedirs(lbl_path, exist_ok=True)
        
        for img in imgs:
            shutil.copy(f"{DATA_DIR}/images/{img}", f"{img_path}/{img}")
            txt_name = img.replace('.jpg', '.txt')
            if os.path.exists(f"{DATA_DIR}/labels/{txt_name}"):
                shutil.copy(f"{DATA_DIR}/labels/{txt_name}", f"{lbl_path}/{txt_name}")

    # Tạo file dataset.yaml cho YOLO
    abs_path = os.path.abspath(OUTPUT_DIR).replace("\\", "/")
    yaml_content = f"""
path: {abs_path}
train: images/train
val: images/val
names:
  0: hand
"""
    with open(f"{OUTPUT_DIR}/dataset.yaml", "w") as f:
        f.write(yaml_content)
    
    print(f"--- CHUẨN BỊ XONG ---")
    print(f"Tổng số ảnh: {len(images)}")
    print(f"Dữ liệu huấn luyện đã sẵn sàng tại: {OUTPUT_DIR}")
    print(f"Hãy nén thư mục này và mang sang máy có GPU để Train!")

if __name__ == "__main__":
    prepare()
