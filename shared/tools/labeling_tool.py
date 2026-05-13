import cv2
import os
import time

# --- CẤU HÌNH ---
VIDEO_SOURCE = "random.mp4" # Đổi thành link RTSP nếu muốn
OUTPUT_DIR = "training/data"
CLASS_ID = 0 # 0 là Hand

os.makedirs(f"{OUTPUT_DIR}/images", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/labels", exist_ok=True)

print("--- YOLO MANUAL LABELING TOOL ---")
print("HDSD:")
print("1. Nhấn SPACE để TẠM DỪNG video và bắt đầu vẽ box.")
print("2. Dùng chuột quét box bàn tay -> Nhấn ENTER để lưu nhãn.")
print("3. Nhấn ESC để thoát sau khi lưu đủ.")

cap = cv2.VideoCapture(VIDEO_SOURCE)
cv2.namedWindow("Labeling", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Labeling", 1280, 720)

count = 0
while True:
    ret, frame = cap.read()
    if not ret: break
    
    cv2.imshow("Labeling", frame)
    key = cv2.waitKey(20) & 0xFF
    
    # Nhấn Space để dừng và gán nhãn
    if key == ord(' ') or key == 32:
        print("\n[PAUSE] Đang chọn vùng bàn tay...")
        roi = cv2.selectROI("Labeling", frame, fromCenter=False, showCrosshair=True)
        
        if roi != (0, 0, 0, 0):
            x, y, w, h = roi
            img_h, img_w = frame.shape[:2]
            
            # Chuyển sang chuẩn YOLO (center_x, center_y, width, height) dải 0-1
            cx = (x + w/2) / img_w
            cy = (y + h/2) / img_h
            norm_w = w / img_w
            norm_h = h / img_h
            
            # Lưu Ảnh
            timestamp = int(time.time() * 1000)
            img_name = f"hand_{timestamp}.jpg"
            cv2.imwrite(f"{OUTPUT_DIR}/images/{img_name}", frame)
            
            # Lưu Nhãn .txt
            with open(f"{OUTPUT_DIR}/labels/hand_{timestamp}.txt", "w") as f:
                f.write(f"{CLASS_ID} {cx:.6f} {cy:.6f} {norm_w:.6f} {norm_h:.6f}")
                
            count += 1
            print(f"✅ Đã lưu ảnh + nhãn thứ {count}: {img_name}")
        else:
            print("❌ Đã hủy.")

    elif key == 27: # ESC
        break

cap.release()
cv2.destroyAllWindows()
print(f"\nHoàn tất! Bạn đã gán nhãn được {count} ảnh trong thư mục {OUTPUT_DIR}")
