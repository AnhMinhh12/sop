import cv2
import yaml
import os
import time

def capture_snapshot():
    # 1. Đọc cấu hình để lấy RTSP URL
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        print(f"❌ LỖI: Không tìm thấy file cấu hình tại {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ LỖI: Không thể đọc file YAML: {e}")
        return

    if 'cameras' not in config or not config['cameras']:
        print("❌ LỖI: Không có camera nào được định nghĩa trong config.yaml")
        return

    # Lấy camera đầu tiên hoặc cho phép chọn nếu cần, ở đây lấy cái đầu tiên cho nhanh
    camera = config['cameras'][0]
    rtsp_url = camera.get('rtsp_url')
    cam_id = camera.get('id', 'unknown')

    if not rtsp_url:
        print(f"❌ LỖI: Camera {cam_id} không có rtsp_url")
        return

    print(f"--- CAPTURE SNAPSHOT ---")
    print(f"📸 Camera: {cam_id}")
    print(f"🔗 URL: {rtsp_url}")
    print(f"⏳ Đang kết nối... (Vui lòng đợi giây lát)")

    # 2. Kết nối và lấy khung hình
    # Thiết kế để lấy khung hình mới nhất, tránh lấy khung hình cũ trong buffer
    cap = cv2.VideoCapture(rtsp_url)
    
    if not cap.isOpened():
        print(f"❌ LỖI: Không thể kết nối tới RTSP. Vui lòng kiểm tra lại URL hoặc đường truyền mạng.")
        return

    # Đợi một chút để camera ổn định và lấy frame mới
    time.sleep(2)
    
    # Đọc thử vài frame để clear buffer
    for _ in range(5):
        cap.grab()
        
    ret, frame = cap.retrieve()

    if ret:
        output_path = "test.jpg"
        cv2.imwrite(output_path, frame)
        print(f"\n✅ THÀNH CÔNG!")
        print(f"📍 Đã lưu ảnh snapshot vào: {os.path.abspath(output_path)}")
        print(f"🚀 Bây giờ bạn có thể chạy: python shared/tools/zone_selector.py")
    else:
        print(f"❌ LỖI: Kết nối được nhưng không lấy được hình ảnh (frame is None).")

    cap.release()

if __name__ == "__main__":
    capture_snapshot()
