import cv2
import numpy as np
import os
import yaml

def load_rtsp_url():
    """Load the first RTSP URL from config/config.yaml as default."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                cameras = config.get("cameras", [])
                if cameras:
                    return cameras[0].get("rtsp_url")
        except Exception as e:
            print(f"Error reading config: {e}")
    return None

def main():
    print("==================================================================")
    print("TOOL LẤY TỌA ĐỘ ĐA GIÁC ĐÃ CHUẨN HÓA (ROI NORMALIZED COORDINATES)")
    print("==================================================================")
    
    # 1. Chọn nguồn ảnh
    image_path = "test_live_camera.jpg"
    frame = None
    
    if os.path.exists(image_path):
        print(f"Tìm thấy ảnh tĩnh đã lưu: {image_path}")
        use_saved = input("Bạn có muốn sử dụng ảnh này không? (Y/n): ").strip().lower()
        if use_saved != 'n':
            frame = cv2.imread(image_path)
            if frame is None:
                print("Không thể đọc ảnh tĩnh, sẽ thử kết nối RTSP.")
    
    if frame is None:
        rtsp_url = load_rtsp_url()
        if not rtsp_url:
            rtsp_url = input("Vui lòng nhập RTSP URL hoặc đường dẫn file ảnh/video: ").strip()
        else:
            print(f"Đọc RTSP URL mặc định từ config: {rtsp_url}")
            custom_url = input("Nhấn Enter để dùng link này, hoặc nhập link mới: ").strip()
            if custom_url:
                rtsp_url = custom_url
        
        print("Đang kết nối để lấy 1 khung ảnh...")
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print("LỖI: Không thể kết nối tới nguồn video/RTSP.")
            return
        
        # Đọc vài frame để tránh ảnh đen/nhiễu lúc mới kết nối
        for _ in range(15):
            cap.grab()
            
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            print("LỖI: Không thể đọc frame từ RTSP.")
            return
        
        # Lưu lại để lần sau sử dụng nhanh
        cv2.imwrite(image_path, frame)
        print(f"Đã chụp thành công và lưu ảnh vào: {image_path}")

    # Tạo bản sao để vẽ
    h, w = frame.shape[:2]
    points = []
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal points
        if event == cv2.EVENT_LBUTTONDOWN:
            # Thêm điểm mới
            points.append((x, y))
            draw_image()
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Undo điểm cuối
            if points:
                points.pop()
                draw_image()

    def draw_image():
        img_copy = frame.copy()
        # Vẽ các điểm đã chọn
        for i, pt in enumerate(points):
            cv2.circle(img_copy, pt, 4, (0, 0, 255), -1)
            cv2.putText(img_copy, str(i + 1), (pt[0] + 5, pt[1] - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Vẽ đa giác nếu có từ 2 điểm trở lên
        if len(points) > 1:
            pts_array = np.array(points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img_copy, [pts_array], isClosed=False, color=(0, 255, 0), thickness=2)
            
            # Nếu trên 2 điểm thì vẽ nét đứt/mờ nối điểm cuối với điểm đầu để dễ hình dung đa giác đóng
            cv2.line(img_copy, points[-1], points[0], (255, 0, 0), 1)
            
        cv2.imshow("Draw ROI - Click chuot trai de chon, Chuot phai de Undo, ESC de thoat, ENTER de hoan thanh", img_copy)

    # Hướng dẫn sử dụng
    print("\n HƯỚNG DẪN SỬ DỤNG WINDOWS VẼ:")
    print(" - Click CHUỘT TRÁI: Chọn đỉnh của vùng đa giác (Polygon)")
    print(" - Click CHUỘT PHẢI: Hoàn tác (Undo) điểm vừa chọn")
    print(" - Phím 'c': Xóa toàn bộ điểm đã chọn")
    print(" - Phím 'ENTER' hoặc 's': Hoàn thành và in tọa độ ra màn hình")
    print(" - Phím 'ESC' hoặc 'q': Thoát không lưu")
    
    cv2.namedWindow("Draw ROI - Click chuot trai de chon, Chuot phai de Undo, ESC de thoat, ENTER de hoan thanh", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Draw ROI - Click chuot trai de chon, Chuot phai de Undo, ESC de thoat, ENTER de hoan thanh", 1024, 768)
    cv2.setMouseCallback("Draw ROI - Click chuot trai de chon, Chuot phai de Undo, ESC de thoat, ENTER de hoan thanh", mouse_callback)
    
    draw_image()
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):  # ESC hoặc q
            print("Đã thoát công cụ.")
            break
        elif key == ord('c'):  # Xóa sạch
            points = []
            draw_image()
        elif key == 13 or key == ord('s'):  # Enter hoặc s
            if len(points) < 3:
                print("Vui lòng chọn ít nhất 3 điểm để tạo đa giác!")
                continue
                
            # Tính toán tọa độ chuẩn hóa (x/w, y/h) làm tròn 3 chữ số thập phân
            normalized_points = [[round(pt[0] / w, 3), round(pt[1] / h, 3)] for pt in points]
            
            print("\n================ TỌA ĐỘ ĐÃ CHUẨN HÓA ================")
            print(f"Số điểm: {len(normalized_points)}")
            print("Dạng YAML:")
            yaml_format = f"[[{'], ['.join([f'{pt[0]}, {pt[1]}' for pt in normalized_points])}]]"
            print(yaml_format)
            print("=====================================================")
            print("\nBạn có thể copy đoạn tọa độ trên dán trực tiếp vào file config yaml.")
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
