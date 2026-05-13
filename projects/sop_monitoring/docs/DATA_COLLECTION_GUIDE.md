# Hướng dẫn thu thập dữ liệu trên Windows (Local)

**Mục tiêu:** Quay/chụp dữ liệu từ Webcam máy tính hoặc IP Camera để huấn luyện model ngay trên máy local.

---

## 1. Chuẩn bị trên máy Local (Windows)

### Cài đặt thư viện
Mở PowerShell hoặc CMD và chạy:
```powershell
pip install opencv-python pyyaml numpy
```

### Xác định Camera của bạn
- **Nếu dùng Webcam:** Thường là index `0`. Nếu có nhiều webcam thì thử `1`, `2`.
- **Nếu dùng IP Camera:** Cần URL RTSP (vd: `rtsp://admin:password@192.168.1.100:554/stream`).

---

## 2. Script thu thập dữ liệu (Chạy trên Windows)

Tôi đã tối ưu script `training/collect_data.py` để bạn có thể truyền số `0` thay vì URL RTSP nếu muốn dùng Webcam.

```python
import cv2
import os
import time
import argparse
from datetime import datetime

def connect_camera(source):
    # Nếu truyền vào số "0", "1", OpenCV sẽ hiểu là Webcam
    if source.isdigit():
        source = int(source)
    
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ Không thể mở camera: {source}")
        return None
    return cap

def mode_record(source, output_path, duration, fps_cap=15):
    cap = connect_camera(source)
    if not cap: return

    # Cấu hình lưu file
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps_cap, (frame_width, frame_height))

    print(f"🎬 Đang quay... Nhấn 'q' để dừng sớm.")
    start_time = time.time()
    
    while (time.time() - start_time) < duration:
        ret, frame = cap.read()
        if not ret: break
        
        out.write(frame)
        cv2.imshow("Preview - Dang quay (Nhan Q de dung)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"✅ Đã lưu video: {output_path}")

def mode_capture(source, save_dir):
    cap = connect_camera(source)
    if not cap: return
    if not os.path.exists(save_dir): os.makedirs(save_dir)

    print(f"📸 Chế độ chụp ảnh. Nhấn SPACE để chụp, Q để thoát.")
    count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        display = frame.copy()
        cv2.putText(display, f"Chup duoc: {count} | SPACE: Chup | Q: Thoat", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Preview - Bam SPACE de chup", display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            img_name = f"frame_{count}_{datetime.now().strftime('%H%M%S')}.jpg"
            cv2.imwrite(os.path.join(save_dir, img_name), frame)
            count += 1
            print(f"📷 Đã lưu {img_name}")
        elif key == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["record", "capture"], required=True)
    parser.add_argument("--source", default="0", help="Index webcam (0) hoặc link RTSP")
    parser.add_argument("--out", default="data/raw/video.mp4")
    parser.add_argument("--dir", default="data/raw/images")
    parser.add_argument("--time", type=int, default=30, help="Số giây quay video")
    
    args = parser.parse_args()
    
    if args.mode == "record":
        mode_record(args.source, args.out, args.time)
    else:
        mode_capture(args.source, args.dir)
```

---

## 3. Cách chạy trên máy của bạn

### 👉 Chụp ảnh từ Webcam (để gán nhãn YOLO)
Nhấn **phím Cách (Space)** mỗi khi bạn đưa tay vào tư thế muốn chụp:
```powershell
python training/collect_data.py --mode capture --source 0 --dir data/raw/pick_bottle
```

### 👉 Quay video từ Webcam (để train LSTM)
Tự động quay trong 60 giây:
```powershell
python training/collect_data.py --mode record --source 0 --out data/raw/action_1.mp4 --time 60
```

### 👉 Nếu bạn dùng IP Camera (RTSP)
Thay `0` bằng URL của bạn:
```powershell
python training/collect_data.py --mode capture --source "rtsp://admin:123456@192.168.1.100:554/stream"
```

---

## 4. Lưu ý quan trọng khi chọn camera
1. **Góc quay:** Phải giống hệt góc quay bạn định lắp đặt thực tế (thường là góc nhìn từ trên xuống hoặc chéo từ trên xuống).
2. **Ánh sáng:** Tránh bị ngược sáng từ cửa sổ.
3. **Môi trường:** Dọn dẹp các vật thể gây nhiễu trong khung hình trước khi quay.

---
*Dữ liệu sau khi chụp sẽ nằm trong thư mục `data/raw/`. Bạn hãy kiểm tra lại ảnh xem có bị mờ (motion blur) không trước khi sang bước gán nhãn.*
