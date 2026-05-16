import cv2
import numpy as np
import yaml
import os

# --- CẤU HÌNH ---
CONFIG_PATH = os.path.join("..", "..", "config", "config.yaml")
IMAGE_PATH = "test.jpg" 
VIDEO_SOURCE_FALLBACK = "video_test.mp4" 
window_name = "Polygon Zone Selector (Real Camera Mode)"

def get_rtsp_from_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
            cameras = cfg.get('cameras', [])
            if cameras:
                return cameras[0].get('rtsp_url')
    except Exception as e:
        print(f"[!] Khong the doc file cau hinh: {e}")
    return None

print("--- POLYGON ZONE SELECTOR (CHON VUNG TREN CAMERA THUC TE) ---")
print("HDSD:")
print("1. Click chuot trai 4 LAN de chon 4 goc cua vung.")
print("2. Nhan 's' de LUU vung (toa do se in ra console).")
print("3. Nhan 'c' de XOA cac diem dang chon.")
print("4. Nhan 'q' de THOAT.")

# --- LOAD NGUỒN DỮ LIỆU ---
frame = None

# 1. Thu lay tu Camera thuc te truoc
rtsp_url = get_rtsp_from_config(CONFIG_PATH)
if rtsp_url:
    print(f"[*] Dang ket noi toi Camera thuc te: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)
    if cap.isOpened():
        # Doc bo qua vai frame dau de tranh buffer cu
        for _ in range(15): cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret:
            print("[+] Da chup duoc anh thuc te tu Camera.")
        else:
            print("[!] Ket noi duoc nhung khong lay duoc frame.")
    else:
        print("[-] Khong the mo stream RTSP.")

# 2. Du phong neu camera loi hoac khong co config
if frame is None:
    frame = cv2.imread(IMAGE_PATH)
    if frame is not None:
        print(f"[+] Da load anh du phong: {IMAGE_PATH}")
    else:
        print(f"[*] Dang thu mo video du phong: {VIDEO_SOURCE_FALLBACK}")
        cap = cv2.VideoCapture(VIDEO_SOURCE_FALLBACK)
        ret, frame = cap.read()
        if not ret:
            print("[!] LOI: Khong the mo duoc ca Camera, Anh hay Video. Vui long kiem tra lai cau hinh!")
            exit()
        cap.release()

h, w = frame.shape[:2]
current_points = []
all_polygons = []

def mouse_callback(event, x, y, flags, param):
    global current_points
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(current_points) < 4:
            current_points.append((x, y))
            print(f"[*] Diem {len(current_points)}: ({x}, {y})")

cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.resizeWindow(window_name, 1280, 720)
cv2.setMouseCallback(window_name, mouse_callback)

while True:
    temp_frame = frame.copy()
    
    # Vẽ các vùng đã lưu (Màu xanh lá)
    for item in all_polygons:
        pts = np.array(item["pixel_points"], np.int32)
        cv2.polylines(temp_frame, [pts], True, (0, 255, 0), 2)
        # Hiển thị tên vùng
        cv2.putText(temp_frame, item["name"], (pts[0][0], pts[0][1] - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

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

    # Nhan 's' de luu toa do
    if key == ord('s') and len(current_points) == 4:
        # MOI: Cho phep nhap ten vung de do phai sua tay trong YAML
        print("\n" + "-"*30)
        zone_name = input("Nhap ten vung (VD: middle_table, mold...): ").strip()
        if not zone_name: 
            zone_name = f"zone_{len(all_polygons)+1}"
        
        rel_points = [[round(p[0]/w, 3), round(p[1]/h, 3)] for p in current_points]
        all_polygons.append({
            "name": zone_name, 
            "points": rel_points,
            "pixel_points": list(current_points)
        })
        
        print(f"[+] DA LUU '{zone_name}': {rel_points}")
        print("-"*30)
        current_points = []
        print("Goi y: Chon tiep vung khac hoac nhan 'q' de ket thuc.")

    # Nhan 'c' de xoa diem dang chon
    elif key == ord('c'):
        current_points = []
        print("[x] Da xoa cac diem dang chon.")

    # Nhấn 'q' để thoát
    elif key == ord('q'):
        break

# In ket qua cuoi cung de copy vao YAML
print("\n" + "="*60)
print("DANH SACH TOA DO (Copy dan truc tiep duoi muc 'zones:' trong YAML):")
print("="*60)
for item in all_polygons:
    print(f"  {item['name']}: {item['points']}")
print("="*60)

cv2.destroyAllWindows()
