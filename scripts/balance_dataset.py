"""
Cân bằng dataset bằng cách oversample class thiếu.
Chạy trên Colab SAU KHI mount Drive, TRƯỚC KHI train.

Cách dùng:
    1. Mở Colab, mount Drive
    2. Chạy script này (copy toàn bộ vào 1 cell)
    3. Sau đó chạy train_yolov8_colab_v2.py
"""

import os
import shutil
import random
from pathlib import Path

# ==== CẤU HÌNH ====
DRIVE_DATASET_DIR = "/content/drive/MyDrive/tff4040.yolov8"
TARGET_PER_CLASS = {
    "hand": 923,    # Giữ nguyên
    "robot": 500,   # Oversample từ ~70 lên 500 (~7 lần)
    "sp": 500,      # Oversample từ ~81 lên 500 (~6 lần)
}
# Lưu ý: copy-paste chỉ là tạm thời để cân bằng tỉ lệ.
# Train với augmentation mạnh sẽ tạo thêm variation.
# Chất lượng vẫn tốt hơn nhiều so với không cân bằng.

CLASS_NAMES = ["hand", "robot", "sp"]


def count_class_in_file(label_path):
    """Đếm số lượng object của từng class trong 1 file label YOLO."""
    counts = {}
    if not os.path.exists(label_path):
        return counts
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                cls = int(parts[0])
                counts[cls] = counts.get(cls, 0) + 1
    return counts


def has_class(label_path, target_class_id):
    """File label có chứa class target không."""
    counts = count_class_in_file(label_path)
    return counts.get(target_class_id, 0) > 0


def oversample_class(dataset_dir, split, class_id, target_count):
    """
    Oversample: copy ảnh có class_id để tăng số lượng instance.
    Chỉ copy các ảnh CÓ class_id (không phải mọi ảnh).
    """
    images_dir = os.path.join(dataset_dir, split, "images")
    labels_dir = os.path.join(dataset_dir, split, "labels")

    if not os.path.isdir(images_dir) or not os.path.isdir(labels_dir):
        return 0, 0

    # Tìm các ảnh có class target
    target_images = []
    for label_file in os.listdir(labels_dir):
        if not label_file.endswith(".txt"):
            continue
        if has_class(os.path.join(labels_dir, label_file), class_id):
            img_name = label_file.replace(".txt", ".jpg")
            if not os.path.exists(os.path.join(images_dir, img_name)):
                img_name = label_file.replace(".txt", ".png")
            if os.path.exists(os.path.join(images_dir, img_name)):
                target_images.append((label_file, img_name))

    # Đếm instance hiện tại
    current_count = 0
    for label_file, _ in target_images:
        counts = count_class_in_file(os.path.join(labels_dir, label_file))
        current_count += counts.get(class_id, 0)

    if current_count >= target_count:
        print(f"  [{split}] class {class_id}: đã đủ ({current_count} >= {target_count})")
        return 0, current_count

    # Cần thêm bao nhiêu instance
    need = target_count - current_count
    # Mỗi ảnh trung bình có bao nhiêu instance của class này
    if not target_images:
        print(f"  [{split}] class {class_id}: KHÔNG có ảnh nào!")
        return 0, 0

    avg_per_img = current_count / len(target_images)
    # Số lần copy mỗi ảnh
    copies_per_img = max(1, int(need / len(target_images) / max(1, avg_per_img)) + 1)

    print(f"  [{split}] class {class_id}: hiện {current_count} / target {target_count}")
    print(f"           → cần {need} thêm, copy {copies_per_img} lần mỗi ảnh ({len(target_images)} ảnh)")

    copied = 0
    idx = 0
    while copied < need:
        for label_file, img_name in target_images:
            if copied >= need:
                break
            idx += 1
            # Tên file mới với suffix _dup_xxx
            base = label_file.rsplit(".", 1)[0]
            new_label = f"{base}_dup{idx}.txt"
            new_img = img_name.rsplit(".", 1)
            new_img_name = f"{new_img[0]}_dup{idx}.{new_img[1]}"

            # Copy
            shutil.copy2(
                os.path.join(labels_dir, label_file),
                os.path.join(labels_dir, new_label),
            )
            shutil.copy2(
                os.path.join(images_dir, img_name),
                os.path.join(images_dir, new_img_name),
            )
            copied += 1

    new_count = current_count + copied
    print(f"           → done: {new_count} instance")
    return copied, new_count


# ==== Main ====
print("=" * 60)
print("OVERSAMPLE CLASSES - Cân bằng dataset")
print("=" * 60)

for split in ("train", "valid", "test"):
    print(f"\n[{split}]")
    for cls_id, cls_name in enumerate(CLASS_NAMES):
        target = TARGET_PER_CLASS.get(cls_name, 200)
        if split != "train":
            # Không oversample valid/test (giữ nguyên để đánh giá công bằng)
            continue
        oversample_class(DRIVE_DATASET_DIR, split, cls_id, target)

print("\n" + "=" * 60)
print("✅ Oversample hoàn tất")
print("=" * 60)
print("\nTiếp theo: chạy lại train script.")