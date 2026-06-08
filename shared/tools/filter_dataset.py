import cv2
import os
import shutil
import numpy as np
from pathlib import Path
import time

def calculate_dhash(image, hash_size=8):
    """
    Tính Difference Hash (dHash) của ảnh.
    Trả về một mảng boolean 2D kích thước hash_size x hash_size.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Resize thành (hash_size + 1, hash_size) để so sánh các điểm ảnh liền kề hàng ngang
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    # So sánh pixel cột bên phải với cột bên trái
    diff = resized[:, 1:] > resized[:, :-1]
    return diff

def get_hamming_distance(hash1, hash2):
    """
    Tính khoảng cách Hamming giữa 2 hash (số lượng bit khác nhau).
    """
    return np.count_nonzero(hash1 != hash2)

def is_green_screen(image, threshold=0.75):
    """
    Kiểm tra xem ảnh có bị lỗi màn hình xanh (Green Screen) do lỗi RTSP/decode không.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Khoảng màu xanh lá cây trong không gian HSV
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([85, 255, 255])
    
    mask = cv2.inRange(hsv, lower_green, upper_green)
    green_ratio = np.sum(mask > 0) / mask.size
    return green_ratio > threshold

def is_solid_color(image, std_threshold=10.0):
    """
    Kiểm tra xem ảnh có phải là một màu đơn sắc (VD: màn hình đen, màn hình xám) không.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    std_dev = np.std(gray)
    return std_dev < std_threshold

def get_blur_score(image):
    """
    Tính độ mờ của ảnh bằng phương pháp phương sai Laplacian.
    Giá trị càng thấp -> ảnh càng mờ.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def main():
    print("=" * 70)
    print("       CÔNG CỤ LỌC TRÙNG LẶP VÀ KHỬ NHIỄU BỘ DỮ LIỆU ẢNH (RTSP/VIDEO)")
    print("=" * 70)
    
    # 1. Nhập đường dẫn thư mục ảnh đầu vào
    while True:
        input_path_str = input("👉 Nhập đường dẫn thư mục chứa ảnh (1700 ảnh): ").strip().strip('"\'')
        input_dir = Path(input_path_str)
        if input_dir.exists() and input_dir.is_dir():
            break
        print("❌ Thư mục không tồn tại! Vui lòng nhập lại.")
        
    # Lấy danh sách ảnh hỗ trợ
    valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
    image_paths = sorted([f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions])
    
    total_images = len(image_paths)
    if total_images == 0:
        print("❌ Không tìm thấy ảnh nào trong thư mục này!")
        return
        
    print(f"📋 Tìm thấy {total_images} ảnh trong thư mục.")
    
    # 2. Lựa chọn cấu hình lọc
    print("\n⚙️ CẤU HÌNH BỘ LỌC:")
    
    # Lọc ảnh trùng lặp
    enable_dup = input("  - Bật lọc trùng lặp? (Y/n): ").strip().lower() != 'n'
    dup_mode = "consecutive"
    max_hamming_dist = 2
    if enable_dup:
        print("    --- Chế độ lọc trùng ---")
        print("    [1] Lọc ảnh trùng LIỀN KỀ (Consecutive) - So sánh ảnh với các ảnh ngay trước nó (Nhanh, phù hợp cho video liên tục)")
        print("    [2] Lọc ảnh trùng TOÀN CỤC (Global) - So sánh với toàn bộ ảnh đã duyệt qua (Tìm ảnh tĩnh lặp lại bất kỳ lúc nào)")
        choice = input("    Chọn chế độ (Mặc định 1): ").strip()
        if choice == '2':
            dup_mode = "global"
        
        dist_input = input("    Chọn ngưỡng khoảng cách Hamming (0-64, Mặc định: 2 - càng nhỏ càng yêu cầu giống nhau tuyệt đối): ").strip()
        if dist_input.isdigit():
            max_hamming_dist = int(dist_input)
            
    # Lọc ảnh mờ (Blur)
    enable_blur = input("\n  - Bật lọc ảnh bị mờ/nhoè (Motion Blur)? (Y/n): ").strip().lower() != 'n'
    blur_threshold = 70.0
    if enable_blur:
        blur_input = input("    Chọn ngưỡng Laplacian (Mặc định: 70.0 - Dưới ngưỡng này sẽ coi là mờ. Tăng lên để lọc mạnh hơn): ").strip()
        if blur_input:
            try:
                blur_threshold = float(blur_input)
            except ValueError:
                print("    Ngưỡng không hợp lệ, dùng mặc định 70.0")

    # Lọc ảnh lỗi màn hình xanh (Green Screen/RTSP Error)
    enable_noise = input("\n  - Bật lọc màn hình lỗi (Xanh lá, Đen thui, Đơn sắc)? (Y/n): ").strip().lower() != 'n'
    
    # 3. Phương thức lưu kết quả
    print("\n📦 PHƯƠNG THỨC XỬ LÝ FILE:")
    print("  [1] COPY ảnh sạch sang thư mục mới (Khuyên dùng - An toàn, không mất dữ liệu gốc)")
    print("  [2] MOVE các ảnh trùng/lỗi sang thư mục riêng (Nhanh hơn, giữ nguyên ảnh sạch ở thư mục gốc)")
    action_choice = input("Chọn phương thức (Mặc định 1): ").strip()
    action_mode = "copy" if action_choice != '2' else "move"
    
    # Thiết lập thư mục đầu ra
    output_base = input_dir.parent / f"{input_dir.name}_filtered_{int(time.time())}"
    if action_mode == "copy":
        clean_dir = output_base / "clean"
        dup_dir = output_base / "duplicates"
        noise_dir = output_base / "noise"
        
        clean_dir.mkdir(parents=True, exist_ok=True)
        dup_dir.mkdir(parents=True, exist_ok=True)
        noise_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📂 Kết quả sẽ được copy vào: {output_base.resolve()}")
    else:
        # Move mode: tạo thư mục loại bỏ nằm ngay trong thư mục gốc
        discard_dir = input_dir / "discarded_files"
        dup_dir = discard_dir / "duplicates"
        noise_dir = discard_dir / "noise"
        
        dup_dir.mkdir(parents=True, exist_ok=True)
        noise_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n📂 Các file loại bỏ sẽ được chuyển vào: {discard_dir.resolve()}")

    # 4. Thực hiện lọc
    print("\n🚀 Bắt đầu quá trình quét và lọc...")
    start_time = time.time()
    
    clean_count = 0
    dup_count = 0
    noise_count = 0
    corrupt_count = 0
    
    # Danh sách để so sánh trùng lặp
    # Mỗi phần tử: (dhash, path)
    processed_hashes = []
    
    # Dùng sliding window cho chế độ consecutive để tối ưu hoá (ví dụ lưu 5 ảnh gần nhất)
    CONSECUTIVE_WINDOW = 5

    for idx, img_path in enumerate(image_paths):
        # Hiển thị tiến độ
        if (idx + 1) % 50 == 0 or idx == total_images - 1:
            progress = ((idx + 1) / total_images) * 100
            print(f"⌛ Đang xử lý: {idx + 1}/{total_images} ảnh ({progress:.1f}%) | Sạch: {clean_count} | Trùng: {dup_count} | Lỗi: {noise_count + corrupt_count}", end="\r")

        # Đọc ảnh
        img = cv2.imread(str(img_path))
        if img is None:
            # Ảnh bị hỏng
            corrupt_count += 1
            if action_mode == "copy":
                shutil.copy2(img_path, noise_dir / img_path.name)
            else:
                shutil.move(img_path, noise_dir / img_path.name)
            continue
            
        # Kiểm tra nhiễu (màn hình xanh, đơn sắc)
        is_noisy = False
        reason = ""
        
        if enable_noise:
            if is_solid_color(img):
                is_noisy = True
                reason = "solid_color"
            elif is_green_screen(img):
                is_noisy = True
                reason = "green_screen"
                
        # Kiểm tra ảnh mờ
        if not is_noisy and enable_blur:
            blur_score = get_blur_score(img)
            if blur_score < blur_threshold:
                is_noisy = True
                reason = f"blurry_score_{blur_score:.1f}"
                
        if is_noisy:
            noise_count += 1
            # Đổi tên file phụ nếu muốn theo dõi nguyên nhân lỗi
            dest_name = f"{img_path.stem}_{reason}{img_path.suffix}"
            if action_mode == "copy":
                shutil.copy2(img_path, noise_dir / dest_name)
            else:
                shutil.move(img_path, noise_dir / dest_name)
            continue
            
        # Kiểm tra trùng lặp bằng dHash
        is_duplicate = False
        img_hash = calculate_dhash(img)
        
        if enable_dup:
            if dup_mode == "consecutive":
                # So sánh với cửa sổ N ảnh sạch gần nhất
                for prev_hash, prev_path in processed_hashes[-CONSECUTIVE_WINDOW:]:
                    dist = get_hamming_distance(img_hash, prev_hash)
                    if dist <= max_hamming_dist:
                        is_duplicate = True
                        break
            else:
                # So sánh với TOÀN BỘ ảnh sạch đã lưu trước đó
                for prev_hash, prev_path in processed_hashes:
                    dist = get_hamming_distance(img_hash, prev_hash)
                    if dist <= max_hamming_dist:
                        is_duplicate = True
                        break
                        
        if is_duplicate:
            dup_count += 1
            if action_mode == "copy":
                shutil.copy2(img_path, dup_dir / img_path.name)
            else:
                shutil.move(img_path, dup_dir / img_path.name)
        else:
            # Ảnh sạch
            clean_count += 1
            processed_hashes.append((img_hash, img_path))
            
            if action_mode == "copy":
                shutil.copy2(img_path, clean_dir / img_path.name)
            # Nếu ở mode move, ảnh sạch được giữ nguyên tại chỗ

    elapsed_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("✨ QUÁ TRÌNH LỌC DỮ LIỆU HOÀN TẤT! ✨")
    print("=" * 70)
    print(f"⏱️  Thời gian chạy: {elapsed_time:.1f} giây")
    print(f"📊 Thống kê chi tiết:")
    print(f"   - Tổng số ảnh quét: {total_images}")
    print(f"   - Ảnh sạch (Clean):  {clean_count} ({(clean_count/total_images)*100:.1f}%)")
    print(f"   - Ảnh trùng (Dup):   {dup_count} ({(dup_count/total_images)*100:.1f}%)")
    print(f"   - Ảnh mờ/lỗi (Noise): {noise_count} ({(noise_count/total_images)*100:.1f}%)")
    print(f"   - Ảnh hỏng (Corrupt): {corrupt_count} ({(corrupt_count/total_images)*100:.1f}%)")
    print("-" * 70)
    if action_mode == "copy":
        print(f"📂 Thư mục chứa ảnh sạch:  {clean_dir.resolve()}")
        print(f"📂 Thư mục ảnh trùng lặp: {dup_dir.resolve()}")
        print(f"📂 Thư mục ảnh lỗi/mờ:   {noise_dir.resolve()}")
    else:
        print(f"📂 Ảnh sạch vẫn nằm tại thư mục gốc: {input_dir.resolve()}")
        print(f"📂 Thư mục chứa ảnh đã lọc ra:      {discard_dir.resolve()}")
    print("=" * 70)

if __name__ == "__main__":
    main()
