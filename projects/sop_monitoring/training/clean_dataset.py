import os
import shutil
import random
import cv2
import yaml
from pathlib import Path

# Cấu hình các đường dẫn nguồn
TAY_NGAN_DIR = Path("data/training_collection/extracted_data/images")
TAY_DAI_DIR = Path("projects/sop_monitoring/training/dataset tay dai")
OUTPUT_DIR = Path("projects/sop_monitoring/training/dataset hop nhat")

TRAIN_RATIO = 0.8
SEED = 42

def validate_yolo_label(label_path: Path) -> bool:
    """
    Kiem tra tinh hop le cua file nhan YOLO.
    Dinh dang: class_id x_center y_center width height
    """
    try:
        if not label_path.exists() or label_path.stat().st_size == 0:
            return False
            
        with open(label_path, 'r') as f:
            lines = f.read().strip().split('\n')
            
        valid_lines = 0
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
                
            class_id = int(parts[0])
            coords = [float(x) for x in parts[1:]]
            
            # Chỉ chấp nhận class 0 (hand)
            if class_id != 0:
                continue
                
            # Kiểm tra tọa độ normalized phải thuộc [0, 1]
            if all(0.0 <= c <= 1.0 for c in coords):
                valid_lines += 1
                
        return valid_lines > 0
    except Exception:
        return False

def clean_and_merge_datasets():
    """
    Quét và gộp cả hai tập dữ liệu tay ngắn & tay dài, loại bỏ ảnh/nhãn lỗi,
    sau đó phân chia Train/Val 80/20 lưu vào thư mục 'dataset hop nhat'.
    """
    random.seed(SEED)
    print("=== BAT DAU GOP VA CHUAN BI DU LIEU TAY NGAN & TAY DAI ===")
    
    # 0. Xóa sạch thư mục cũ nếu có để tránh nhiễu
    if OUTPUT_DIR.exists():
        print(f"Purging old output directory: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
        
    valid_pairs = [] # List of tuples: (image_path, label_path, prefix)
    corrupted_images = 0
    mismatched_files = 0
    invalid_labels = 0

    # 1. Quét dữ liệu tay ngắn (Short sleeves)
    tay_ngan_count = 0
    if TAY_NGAN_DIR.exists():
        print(f"\n1. Quet du lieu tay ngan tai: {TAY_NGAN_DIR}")
        all_files = list(TAY_NGAN_DIR.glob("*"))
        image_files = [f for f in all_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        
        for img_path in image_files:
            txt_path = img_path.with_suffix('.txt')
            if not txt_path.exists():
                mismatched_files += 1
                continue
                
            img = cv2.imread(str(img_path))
            if img is None:
                corrupted_images += 1
                continue
                
            if not validate_yolo_label(txt_path):
                invalid_labels += 1
                continue
                
            valid_pairs.append((img_path, txt_path, "tay_ngan"))
            tay_ngan_count += 1
        print(f"   -> Tim thay {tay_ngan_count} cap tay ngan hop le.")
    else:
        print(f"\n[CANH BAO] Khong tim thay thu muc tay ngan tai: {TAY_NGAN_DIR}")

    # 2. Quét dữ liệu tay dài (Long sleeves)
    tay_dai_count = 0
    if TAY_DAI_DIR.exists():
        print(f"\n2. Quet du lieu tay dai tai: {TAY_DAI_DIR}")
        all_files = list(TAY_DAI_DIR.glob("*"))
        image_files = [f for f in all_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        
        for img_path in image_files:
            txt_path = img_path.with_suffix('.txt')
            if not txt_path.exists():
                mismatched_files += 1
                continue
                
            img = cv2.imread(str(img_path))
            if img is None:
                corrupted_images += 1
                continue
                
            if not validate_yolo_label(txt_path):
                invalid_labels += 1
                continue
                
            valid_pairs.append((img_path, txt_path, "tay_dai"))
            tay_dai_count += 1
        print(f"   -> Tim thay {tay_dai_count} cap tay dai hop le.")
    else:
        print(f"\n[CANH BAO] Khong tim thay thu muc tay dai tai: {TAY_DAI_DIR}")

    # Báo cáo lọc
    print(f"\n--- BAO CAO LOC DU LIEU GOP ---")
    print(f"   - Tong so cap anh-nhan HOP LE: {len(valid_pairs)} (Tay ngan: {tay_ngan_count}, Tay dai: {tay_dai_count})")
    print(f"   - So anh bi loi/khong doc duoc: {corrupted_images}")
    print(f"   - So anh/nhan thieu file ghep cap: {mismatched_files}")
    print(f"   - So file nhan sai dinh dang YOLO/toa do loi: {invalid_labels}")

    if len(valid_pairs) == 0:
        print("\n[LOI] Khong co du lieu hop le nao de phan chia! Vui long kiem tra lai.")
        return

    # 3. Phân chia tập dữ liệu (Train/Val Split)
    random.shuffle(valid_pairs)
    split_idx = int(len(valid_pairs) * TRAIN_RATIO)
    train_pairs = valid_pairs[:split_idx]
    val_pairs = valid_pairs[split_idx:]

    print(f"\n3. Phan chia ti le {int(TRAIN_RATIO*100)}/{int((1-TRAIN_RATIO)*100)}:")
    print(f"   - Tap Huan luyen (Train): {len(train_pairs)} anh")
    print(f"   - Tap Kiem thu (Val): {len(val_pairs)} anh")

    # 4. Tạo cấu trúc thư mục YOLO
    print(f"\n4. Dang khoi tao cau truc thu muc tai: {OUTPUT_DIR}")
    for split in ['train', 'val']:
        (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # 5. Sao chép và đổi tên file để tránh trùng lặp
    print("\n5. Dang sao chep file...")
    for split, pairs in [('train', train_pairs), ('val', val_pairs)]:
        for i, (img_path, txt_path, prefix) in enumerate(pairs):
            new_filename = f"hand_{prefix}_{i:06d}"
            dest_img = OUTPUT_DIR / "images" / split / f"{new_filename}{img_path.suffix}"
            dest_txt = OUTPUT_DIR / "labels" / split / f"{new_filename}.txt"
            
            shutil.copy(img_path, dest_img)
            shutil.copy(txt_path, dest_txt)

    # 6. Tạo file cấu hình dataset.yaml
    print("\n6. Khoi tao file cau hinh dataset.yaml...")
    abs_path = os.path.abspath(OUTPUT_DIR).replace("\\", "/")
    yaml_data = {
        'path': abs_path,
        'train': 'images/train',
        'val': 'images/val',
        'names': {
            0: 'hand'
        }
    }
    
    yaml_path = OUTPUT_DIR / "dataset.yaml"
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n*** HOAN THANH GOP VA CHUAN BI DU LIEU! ***")
    print(f"   - Thu muc dataset gop: {OUTPUT_DIR.resolve()}")
    print(f"   - File cau hinh: {yaml_path.resolve()}")
    print("\n>>> BUOC TIEP THEO:")
    print("1. Nen thu muc 'dataset hop nhat' nay thanh file .zip va day len Google Drive.")
    print("2. Chay file train_on_colab.py tren Google Colab de huan luyen model toi uu cho ca tay ngan & tay dai!")

if __name__ == "__main__":
    clean_and_merge_datasets()
