import cv2
import os
import time

# --- CẤU HÌNH ---
VIDEO_PATH = "random.mp4" # Đường dẫn video của bạn
OUTPUT_DIR = "training/raw_frames"
FRAME_INTERVAL = 40 # Cứ 10 khung hình lấy 1 ảnh (Tránh trùng lặp quá nhiều)

os.makedirs(OUTPUT_DIR, exist_ok=True)

cap = cv2.VideoCapture(VIDEO_PATH)
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"--- FRAME EXTRACTOR ---")
print(f"Video: {VIDEO_PATH} ({fps} FPS)")
print(f"Tổng số khung hình: {total_frames}")
print(f"Dự kiến trích xuất: {total_frames // FRAME_INTERVAL} ảnh")

count = 0
saved_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if count % FRAME_INTERVAL == 0:
        # Resize nhẹ để khi upload lên web cho nhanh (vẫn giữ chất lượng đủ để AI học)
        # file_path = f"{OUTPUT_DIR}/frame_{saved_count:05d}.jpg"
        # Nếu muốn giữ nguyên độ phân giải gốc:
        file_path = f"{OUTPUT_DIR}/img_{int(time.time()*1000)}_{saved_count}.jpg"
        
        cv2.imwrite(file_path, frame)
        saved_count += 1
        
        if saved_count % 50 == 0:
            print(f"Đã trích xuất {saved_count} ảnh...")

    count += 1

cap.release()
print(f"\n✅ HOÀN TẤT!")
print(f"Đã lưu {saved_count} ảnh vào: {OUTPUT_DIR}")
print(f"Bây giờ bạn có thể nén thư mục này và upload lên Roboflow/CVAT để gán nhãn.")
