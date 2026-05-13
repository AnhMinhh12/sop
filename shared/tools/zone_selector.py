import cv2
import numpy as np

# --- CẤU HÌNH ---
# Bạn hãy để file ảnh muốn chọn vùng vào đây (VD: snapshot.jpg)
IMAGE_PATH = "test.jpg" 
VIDEO_SOURCE = "video_test.mp4" # Dự phòng nếu không có ảnh
window_name = "Polygon Zone Selector (Image Mode)"

print("--- POLYGON ZONE SELECTOR (CHỌN VÙNG TRÊN ẢNH) ---")
print("HDSD:")
print("1. Click chuột trái 4 LẦN để chọn 4 góc của vùng.")
print("2. Nhấn 's' để LƯU vùng (tọa độ sẽ in ra console).")
print("3. Nhấn 'c' để XÓA các điểm đang chọn.")
print("4. Nhấn 'q' để THOÁT.")

# --- LOAD NGUỒN DỮ LIỆU ---
frame = cv2.imread(IMAGE_PATH)

if frame is None:
    print(f"⚠️ Không tìm thấy ảnh tại: {IMAGE_PATH}")
    print(f"🎬 Đang thử mở video dự phòng: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    ret, frame = cap.read()
    if not ret:
        print("❌ LỖI: Không thể mở được cả ảnh và video. Vui lòng kiểm tra lại đường dẫn!")
        exit()
    cap.release()
else:
    print(f"✅ Đã load ảnh: {IMAGE_PATH}")

h, w = frame.shape[:2]
current_points = []
all_polygons = []

def mouse_callback(event, x, y, flags, param):
    global current_points
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(current_points) < 4:
            current_points.append((x, y))
            print(f"📍 Điểm {len(current_points)}: ({x}, {y})")

cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)
cv2.setMouseCallback(window_name, mouse_callback)

while True:
    temp_frame = frame.copy()
    
    # Vẽ các vùng đã lưu (Màu xanh lá)
    for poly in all_polygons:
        pts = np.array(poly, np.int32)
        cv2.polylines(temp_frame, [pts], True, (0, 255, 0), 2)

    # Vẽ vùng đang chọn (Màu đỏ/xanh dương)
    for pt in current_points:
        cv2.circle(temp_frame, pt, 5, (0, 0, 255), -1)
    
    if len(current_points) > 1:
        pts = np.array(current_points, np.int32)
        cv2.polylines(temp_frame, [pts], False, (0, 0, 255), 2)
    
    if len(current_points) == 4:
        pts = np.array(current_points, np.int32)
        cv2.polylines(temp_frame, [pts], True, (255, 0, 0), 2)

    cv2.imshow(window_name, temp_frame)
    key = cv2.waitKey(1) & 0xFF

    # Nhấn 's' để lưu tọa độ
    if key == ord('s') and len(current_points) == 4:
        rel_points = [[round(p[0]/w, 3), round(p[1]/h, 3)] for p in current_points]
        all_polygons.append(current_points)
        print(f"\n✅ ĐÃ LƯU VÙNG: {rel_points}")
        current_points = []
        print("💡 Gợi ý: Chọn tiếp vùng khác hoặc nhấn 'q' để kết thúc.")

    # Nhấn 'c' để xóa điểm đang chọn
    elif key == ord('c'):
        current_points = []
        print("🗑️ Đã xóa các điểm đang chọn.")

    # Nhấn 'q' để thoát
    elif key == ord('q'):
        break

# In kết quả cuối cùng để copy vào YAML
print("\n" + "="*60)
print("DANH SÁCH Tọa độ QUY ĐỔI (Copy dán vào config/sop_definitions/):")
print("="*60)
for i, poly in enumerate(all_polygons):
    rel_poly = [[round(p[0]/w, 3), round(p[1]/h, 3)] for p in poly]
    print(f"zone_{i+1}: {rel_poly}")
print("="*60)

cv2.destroyAllWindows()
