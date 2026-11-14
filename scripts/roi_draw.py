import cv2
import numpy as np
import os
import sys
import yaml
import argparse

def copy_to_clipboard(text: str):
    """Copy chuỗi text vào Clipboard Windows để người dùng dán (Ctrl+V) ngay lập tức."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
        return True
    except Exception:
        pass
    return False

def load_cameras_from_config():
    """Load danh sách camera từ config/config.yaml."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("cameras", [])
        except Exception as e:
            print(f"Error reading config: {e}")
    return []

def select_video_source():
    """Menu tương tác cho phép chọn RTSP từ camera config, file video hoặc nhập link RTSP/URL bất kỳ."""
    cameras = load_cameras_from_config()
    
    print("\n" + "="*65)
    print("CHỌN NGUỒN HÌNH ẢNH / VIDEO ĐỂ VẼ VÙNG (ROI)")
    print("="*65)
    
    options = []
    
    # 1. Các file video mẫu có sẵn trong data/recordings
    recordings_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "recordings")
    if os.path.exists(recordings_dir):
        for f in os.listdir(recordings_dir):
            if f.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
                full_path = os.path.join(recordings_dir, f)
                rel_path = os.path.relpath(full_path).replace("\\", "/")
                options.append({
                    "title": f"File video có sẵn: {f}",
                    "source": rel_path
                })
    
    # 2. Danh sách camera từ config
    for cam in cameras:
        cam_id = cam.get("id", "")
        cam_name = cam.get("name", cam_id)
        rtsp = cam.get("rtsp_url", "")
        options.append({
            "title": f"Camera [{cam_name}] ({cam_id}): {rtsp}",
            "source": rtsp
        })

    # 3. Ảnh tĩnh chụp trước đó
    if os.path.exists("test_live_camera.jpg"):
        options.append({
            "title": "Ảnh tĩnh chụp trước đó: test_live_camera.jpg",
            "source": "test_live_camera.jpg"
        })

    for idx, opt in enumerate(options, 1):
        print(f" [{idx}] {opt['title']}")
    
    print(f" [0] Nhập đường dẫn thủ công (link RTSP, link mp4 hoặc đường dẫn file)")
    print("="*65)
    
    choice = input(f"Chọn nguồn [1-{len(options)}] (mặc định 1), hoặc bấm 0: ").strip()
    
    if choice == "0":
        user_input = input("Vui lòng nhập đường link RTSP hoặc đường dẫn file video: ").strip()
        return user_input.strip("\"'")
    
    try:
        val = int(choice) if choice else 1
        if 1 <= val <= len(options):
            return options[val - 1]["source"]
    except ValueError:
        pass
        
    if options:
        return options[0]["source"]
    
    return input("Vui lòng nhập đường link RTSP hoặc file video: ").strip().strip("\"'")

def extract_frame_from_source(source_path):
    """Trích xuất 1 khung hình từ ảnh hoặc video/RTSP."""
    # Nếu là ảnh tĩnh
    if source_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        if os.path.exists(source_path):
            img = cv2.imread(source_path)
            if img is not None:
                return img
    
    print(f"\nĐang mở nguồn video: {source_path} ...")
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        print(f"LỖI: Không thể mở video hoặc kết nối RTSP tới: {source_path}")
        return None

    is_file = os.path.exists(source_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if is_file else 0

    if is_file and total_frames > 1:
        print("\n" + "-"*65)
        print("ĐANG XEM TRƯỚC VIDEO ĐỂ CHỌN KHUNG HÌNH VẼ:")
        print(" - Phím [SPACE] (Cách): Tạm dừng / Xem tiếp")
        print(" - Phím [ENTER]: CHỐT khung hình này để vẽ vùng")
        print(" - Phím [ESC] hoặc [q]: Thoát")
        print("-"*65)
        
        win_preview = "Preview Video - Chon Frame de ve"
        cv2.namedWindow(win_preview, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(win_preview, 960, 540)
        
        selected_frame = None
        paused = False
        
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                selected_frame = frame
            
            display = selected_frame.copy()
            cur_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            info_text = f"Frame: {cur_idx}/{total_frames} | {'[TAM DUNG]' if paused else '[DANG PHAT]'} - Nhan ENTER de CHOT"
            cv2.putText(display, info_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow(win_preview, display)
            
            key = cv2.waitKey(30 if not paused else 100) & 0xFF
            if key == 32:  # Space
                paused = not paused
            elif key in (13, 10, ord('s'), ord('S')):  # Enter / s
                cv2.destroyWindow(win_preview)
                cap.release()
                return selected_frame
            elif key in (27, ord('q'), ord('Q')):
                cv2.destroyWindow(win_preview)
                cap.release()
                return None
    else:
        # Với RTSP camera trực tiếp
        print("Đang đọc frame từ camera...")
        for _ in range(15):
            cap.grab()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return frame
        else:
            print("LỖI: Không thể đọc được khung hình từ luồng RTSP.")
            return None

def main():
    parser = argparse.ArgumentParser(description="Tool lấy tọa độ đa giác chuẩn hóa (ROI Drawing)")
    parser.add_argument("--source", "-s", type=str, default=None, help="Đường link RTSP, URL hoặc file video/ảnh")
    args = parser.parse_args()

    print("="*65)
    print("TOOL LẤY TỌA ĐỘ ĐA GIÁC ĐÃ CHUẨN HÓA (ROI NORMALIZED COORDINATES)")
    print("="*65)
    
    source = args.source
    if not source:
        source = select_video_source()
        
    if not source:
        print("Không có nguồn dữ liệu nào được chọn. Đã thoát.")
        return

    frame = extract_frame_from_source(source)
    if frame is None:
        return

    # Lưu lại frame đang vẽ
    cv2.imwrite("test_live_camera.jpg", frame)
    print(f"\n-> Đã lưu ảnh đang vẽ vào: test_live_camera.jpg")

    h, w = frame.shape[:2]
    points = []
    zone_count = 1
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal points
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
            draw_image()
        elif event == cv2.EVENT_RBUTTONDOWN:
            if points:
                points.pop()
                draw_image()

    def draw_image(banner_msg=None):
        img_copy = frame.copy()
        
        # Vẽ các điểm đã chọn
        for i, pt in enumerate(points):
            cv2.circle(img_copy, pt, 5, (0, 0, 255), -1)
            cv2.putText(img_copy, str(i + 1), (pt[0] + 6, pt[1] - 6), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        
        # Vẽ các đoạn thẳng nối các điểm
        if len(points) > 1:
            pts_array = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img_copy, [pts_array], isClosed=False, color=(0, 255, 0), thickness=2)
            # Nối điểm cuối với điểm đầu (nét mờ)
            cv2.line(img_copy, points[-1], points[0], (255, 100, 0), 1)
        
        # Thanh hướng dẫn trực quan trên ảnh
        cv2.rectangle(img_copy, (0, 0), (w, 40), (40, 40, 40), -1)
        guide_text = f"Diem: {len(points)} | Chuot Trai: Chon diem | Chuot Phai: Undo | Enter: CHOT TOA DO | ESC: Thoat"
        if banner_msg:
            guide_text = banner_msg
        cv2.putText(img_copy, guide_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

        cv2.imshow(win_name, img_copy)

    win_name = "Draw ROI [Nhan ENTER de Lay Toa Do]"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1024, 768)
    cv2.setMouseCallback(win_name, mouse_callback)
    
    print("\n" + "="*65)
    print("HƯỚNG DẪN THAO TÁC TRÊN CỬA SỔ VẼ:")
    print(" - Click CHUỘT TRÁI : Chọn từng đỉnh của đa giác")
    print(" - Click CHUỘT PHẢI: Hoàn tác (Undo) điểm vừa click")
    print(" - Phím 'c'         : Xóa hết các điểm để vẽ lại")
    print(" - Phím 'ENTER' / 's': HOÀN THÀNH VÀ LẤY TỌA ĐỘ (Tự động Copy vào Clipboard)")
    print(" - Phím 'ESC' / 'q'  : Thoát công cụ")
    print("="*65 + "\n")
    
    draw_image()
    
    saved_zones_file = "latest_roi_coordinates.txt"
    with open(saved_zones_file, "w", encoding="utf-8") as f:
        f.write("# TỌA ĐỘ ROI VỪA ĐƯỢC VẼ BẰNG ROI_DRAW.PY\n\n")

    while True:
        key = cv2.waitKey(20) & 0xFF
        
        if key in (27, ord('q'), ord('Q')):
            print("\nĐã đóng cửa sổ vẽ ROI.")
            break
            
        elif key in (ord('c'), ord('C')):
            points = []
            draw_image("Da xoa het cac diem. Vui long click lai tu dau.")
            print("-> Đã xóa các điểm.")
            
        # Bắt phím ENTER (mã 13 hoặc 10 trên Windows), hoặc phím 's' / phím Space
        elif key in (13, 10, ord('s'), ord('S'), 32):
            if len(points) < 3:
                draw_image("CHU Y: Can it nhat 3 diem de tao thanh da giac!")
                print("LƯU Ý: Cần chọn ít nhất 3 điểm để tạo đa giác!")
                continue
                
            normalized_points = [[round(pt[0] / w, 3), round(pt[1] / h, 3)] for pt in points]
            yaml_format = f"[[{'], ['.join([f'{pt[0]}, {pt[1]}' for pt in normalized_points])}]]"
            
            # Tự động copy vào clipboard
            copied = copy_to_clipboard(yaml_format)
            
            # Ghi ra file text dự phòng
            with open(saved_zones_file, "a", encoding="utf-8") as f:
                f.write(f"zone_{zone_count}: {yaml_format}\n")

            print("\n" + "="*70)
            print(f" ĐÃ LẤY THÀNH CÔNG TỌA ĐỘ VÙNG #{zone_count} ({len(normalized_points)} điểm):")
            print(yaml_format)
            print("="*70)
            if copied:
                print(">> [TỰ ĐỘNG COPY] Đã copy tọa độ vào Clipboard (Bộ nhớ tạm)!")
                print(">> Bạn chỉ cần mở file yaml và ấn tổ hợp phím [Ctrl + V] để dán trực tiếp.")
            print(f">> Tọa độ cũng đã được lưu tự động vào file: {saved_zones_file}")
            print("="*70)
            
            zone_count += 1
            draw_image(f"DA CHOT VUNG #{zone_count - 1}! Toa do da duoc Copy vao Clipboard.")
            
            # Cho phép tiếp tục vẽ vùng tiếp theo mà không làm gián đoạn
            points = []
            
    cv2.destroyAllWindows()
    print(f"\nToàn bộ tọa độ đã vẽ được lưu tại: {os.path.abspath(saved_zones_file)}")

if __name__ == "__main__":
    main()
