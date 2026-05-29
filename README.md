# 🌟 SOP Real-time Assembly Monitoring System (AI Monitoring Hub)

Hệ thống giám sát thao tác lắp ráp của công nhân qua IP Camera thời gian thực (Real-time). Hệ thống tự động phát hiện bàn tay của công nhân (bằng mô hình YOLO ONNX chạy trên CPU), theo dõi sự tương tác với các vùng không gian (ROI), kiểm soát trình tự lắp ráp (SOP), cảnh báo âm thanh khi phát hiện vi phạm, lưu video clip vi phạm và hiển thị trực quan thông tin trên Web Dashboard.

---

## 🚀 Tính năng nổi bật

1. **Giám sát thời gian thực đa trạm (Multi-station)**:
   - Hỗ trợ giám sát song song nhiều luồng RTSP camera độc lập qua mô hình đa luồng (Multi-threading).
   - Tự động phát hiện mất kết nối camera và tự động kết nối lại (`rtsp_manager.py`).

2. **Tối ưu hóa chạy trên CPU (Intel Xeon Server)**:
   - **Không yêu cầu GPU**: Hệ thống sử dụng **ONNX Runtime CPU** và kiến trúc Threading để chạy tuần tự mượt mà trên bộ vi xử lý CPU Intel Xeon Silver 4510.
   - Hạn chế số lượng luồng OpenCV, tối ưu hóa các tham số `OMP_NUM_THREADS` và `MKL_NUM_THREADS` để tránh quá tải tài nguyên hệ thống.

3. **Cơ chế đệm vòng lưu clip vi phạm (Pre-event Ring Buffer)**:
   - Duy trì liên tục một bộ đệm vòng (`FrameRingBuffer`) cho mỗi camera để lưu trữ video trước khi sự cố xảy ra.
   - Khi phát hiện vi phạm, hệ thống sẽ lưu clip video ngắn chứa 5 giây trước sự kiện và 5 giây sau sự kiện dưới dạng file MP4 (chuẩn nén H.264).

4. **Tự động quản lý bộ nhớ đĩa (Storage Management)**:
   - Kịch bản chạy nền liên tục kiểm tra dung lượng ổ đĩa.
   - Tự động xóa các clip vi phạm cũ nhất khi dung lượng ổ đĩa vượt quá ngưỡng 85% (`cleanup.py`).

5. **Giao diện Web Dashboard Trực quan (SPA)**:
   - Giao diện đơn trang (Single Page Application) hiện đại hiển thị luồng video MJPEG thời gian thực cùng với trạng thái bước SOP, biểu đồ hiệu suất, tỷ lệ tuân thủ và nhật ký vi phạm.
   - Cập nhật sự kiện tức thời qua kết nối **Websocket (Socket.IO)**.
   - Đồng bộ hóa các bộ lọc Máy và Mã hàng mượt mà.

---

## 🛠️ Stack công nghệ

- **Core Logic**: Python 3.10+, PyYAML, psutil
- **Deep Learning / AI**: ONNX Runtime, OpenCV, PyTorch & Torchvision (để nạp các tiện ích phụ)
- **Database**: MySQL (kết nối qua thư viện `pymysql` và Pool `DBUtils.PooledDB` đảm bảo thread-safe)
- **Web App / Real-time**: Flask, Flask-SocketIO, Eventlet, Flask-CORS
- **Multimedia Alert**: sounddevice, soundfile (phát cảnh báo âm thanh trực tiếp từ máy chủ), imageio & imageio-ffmpeg (nén clip vi phạm)

---

## 📁 Cấu trúc thư mục dự án

```
AI_Monitoring_Hub/
├── app/                        # Giao diện Dashboard & Flask server
│   ├── __init__.py
│   ├── routes.py               # Định nghĩa các HTTP API & Socket.IO events
│   ├── templates/              # Giao diện HTML (dashboard, lịch sử, thống kê)
│   └── static/                 # Tài nguyên CSS, JS và hình ảnh minh họa
├── config/                     # Cấu hình hệ thống
│   └── config.yaml             # Cấu hình chính (camera, model, database, lưu trữ)
├── data/                       # Lưu trữ dữ liệu runtime
│   ├── logs/                   # System & Application logs
│   └── violations/             # Các file clip vi phạm (.mp4)
├── projects/
│   └── sop_monitoring/         # Pipeline xử lý logic SOP
│       ├── config/             # Cấu hình vùng không gian (ROI) từng sản phẩm (TFF4040, 626287)
│       ├── core/               # Trọng tâm xử lý logic
│       │   ├── engines/        # Logic SOP chi tiết cho từng mã sản phẩm
│       │   │   ├── base_engine.py
│       │   │   ├── loader.py   # Nạp động các engine tương ứng
│       │   │   ├── 626287_engine.py
│       │   │   └── TFF4040_engine.py
│       │   ├── spatial_engine.py
│       │   ├── tracking_engine.py
│       │   ├── sop_graph.py
│       │   ├── violation_detector.py
│       │   └── action_inference.py
│       ├── docs/               # Tài liệu hướng dẫn & Quy chuẩn phát triển
│       │   ├── READING_ORDER.md  # Thứ tự đọc code cho lập trình viên mới
│       │   └── RULES.md
│       ├── training/           # Công cụ xử lý & Chuẩn bị tập dữ liệu train YOLO
│       ├── buffer.py           # Bộ đệm vòng (Ring buffer)
│       ├── hand_detector.py    # YOLO ONNX wrapper
│       └── processor.py        # Bộ điều phối luồng FrameProcessor
├── shared/                     # Thư viện dùng chung của hệ thống
│   ├── db/                     # Tầng kết nối & Truy vấn Database (MySQL)
│   ├── events/                 # Lưu clip vi phạm & Cảnh báo âm thanh
│   ├── services/               # Đọc config, ghi log, vẽ thông tin (annotator)
│   ├── tools/                  # Công cụ cấu hình ROI & thu thập video
│   ├── inference_engine.py     # Singleton chạy mô hình YOLO ONNX CPU
│   └── rtsp_manager.py         # Quản lý kết nối camera RTSP
├── main.py                     # Entry point khởi chạy hệ thống
├── requirements.txt            # Danh sách các thư viện phụ thuộc
├── sync_ui.py                  # Script đồng bộ giao diện từ Hub
└── .env                        # File chứa biến môi trường (Database, Paths, CPU)
```

> [!NOTE]
> Để hiểu rõ hơn về các file và bắt đầu nghiên cứu mã nguồn, vui lòng xem qua tài liệu [READING_ORDER.md](projects/sop_monitoring/docs/READING_ORDER.md).

---

## ⚙️ Hướng dẫn cài đặt & Cấu hình

### 1. Chuẩn bị môi trường
Cài đặt các gói thư viện cần thiết bằng cách chạy lệnh:
```bash
pip install -r requirements.txt
```

### 2. Thiết lập Biến môi trường (`.env`)
Tạo hoặc chỉnh sửa file `.env` ở thư mục gốc của dự án. File này cấu hình kết nối Database, đường dẫn và tối ưu hóa CPU:
```env
# --- App Server ---
APP_HOST=0.0.0.0
APP_PORT=5001
HUB_URL=http://10.0.9.254:4000

# --- Paths ---
CONFIG_PATH=config/config.yaml
SOP_DEFINITIONS_DIR=projects/sop_monitoring/config
VIOLATIONS_DIR=data/violations
LOGS_DIR=data/logs

# --- CPU Optimization ---
AI_MAX_THREADS=4
AI_FPS_CAP=15
AI_INPUT_SIZE=416

# --- Database ---
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=ai_system
```

### 3. Cấu hình quy trình lắp ráp và camera (`config.yaml`)
Hệ thống được cấu hình hoàn toàn thông qua file `config/config.yaml`.
- Đăng ký camera IP với đường dẫn RTSP tương ứng.
- Chỉ định mã sản phẩm (`engine_id`) và đường dẫn file cấu hình vùng ROI tương ứng (`sop_file`).
- Thiết lập thông số AI (`weights` ONNX, `input_size`, ngưỡng `conf_threshold`).

---

## 🚀 Khởi chạy hệ thống

### Chạy ứng dụng chính
Chạy lệnh sau từ thư mục gốc để khởi chạy toàn bộ luồng giám sát camera cùng máy chủ Flask Web Dashboard:
```bash
python main.py
```
Sau khi hệ thống khởi động thành công, Dashboard hiển thị tại địa chỉ: `http://localhost:5001`.

### Các công cụ bổ trợ phát triển
Dưới thư mục `shared/tools/` cung cấp sẵn một số công cụ để thiết lập và huấn luyện hệ thống:
1. **Chụp ảnh mẫu từ camera**:
   ```bash
   python shared/tools/capture_snapshot.py
   ```
2. **Cấu hình vùng không gian (ROI/Zones)**:
   Sử dụng công cụ chọn tọa độ trên ảnh chụp camera để xuất tọa độ các vùng hoạt động của tay công nhân đưa vào file cấu hình sản phẩm:
   ```bash
   python shared/tools/zone_selector.py
   ```
3. **Đồng bộ giao diện từ xa**:
   ```bash
   python sync_ui.py
   ```
