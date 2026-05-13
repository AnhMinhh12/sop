
## 1. Tầng AI & Inference (Xử lý ảnh & Mô hình)
*Đây là các thành phần cốt lõi nhận diện bàn tay và trích xuất thông tin.*
- `pipelines/inference_engine.py`: Engine chạy ONNX bằng CPU, quản lý inference tuần tự (Singleton).
- `integrations/hand_detector.py`: Wrap mô hình YOLOv11 ONNX để detect bàn tay.
- `integrations/keypoint_extractor.py`: Sử dụng MediaPipe Hands trích xuất 21 tọa độ khớp tay.

## 2. Tầng Logic SOP (Spatial Engine & Trạng thái)
*Các module này xử lý logic dựa trên tọa độ vùng (Zones) và trình tự thao tác.*
- `core/spatial_engine.py`: Engine xử lý logic dựa trên sự tương tác của tay với các vùng không gian.
- `core/engines/`: Thư mục chứa logic cụ thể cho từng sản phẩm (Ví dụ: `san_pham_a_engine.py`).
- `core/sop_graph.py`: Định nghĩa cấu trúc và thứ tự các bước SOP.
- `core/tracking_engine.py`: Theo dõi chuyển động và trạng thái ổn định của bàn tay.
- `core/feature_engineer.py`: Chuyển đổi tọa độ thô thành các đặc trưng logic (ví dụ: tay trong vùng, tay chụm).
- `core/violation_detector.py`: Xác định các lỗi vi phạm (sai bước, bỏ bước) dựa trên dữ liệu từ engine.

## 3. Tầng Pipeline Video (Xử lý luồng Camera)
*Cách hệ thống lấy khung hình và điều phối dữ liệu.*
- `pipelines/frame_buffer.py`: Ring buffer lưu khung hình 10-30s phục vụ cắt clip khi có vi phạm.
- `integrations/rtsp_stream.py`: Kết nối, duy trì và tự động reconnect luồng RTSP.
- `pipelines/frame_processor.py`: "Nhạc trưởng" kết nối toàn bộ luồng xử lý cho mỗi camera.

## 4. Tầng Dịch vụ & Tiện ích (Services)
*Các công cụ hỗ trợ hệ thống vận hành ổn định.*
- `services/config_loader.py`: Đọc và quản lý cấu hình từ `config.yaml` và `.env`.
- `services/disk_monitor.py`: Kiểm tra dung lượng ổ cứng để kích hoạt dọn dẹp.
- `services/annotator.py`: Vẽ thông tin AI (box, zones, steps) lên hình ảnh để hiển thị.
- `services/logger.py`: Hệ thống ghi log tập trung.

## 5. Tầng Sự kiện & Dữ liệu (Cảnh báo & Lưu trữ)
*Xử lý kết quả sau khi phát hiện vi phạm.*
- `events/audio_alert.py`: Phát âm thanh cảnh báo (.wav) qua loa máy tính.
- `events/clip_saver.py`: Trích xuất buffer và encode thành video MP4 (H.264).
- `db/models.py`, `db/db.py`, `db/queries.py`: Quản lý SQLite (WAL mode) và truy vấn lịch sử, thống kê.
- `db/cleanup.py`: Tự động xóa các clip cũ nhất khi ổ cứng đầy (>85%).

## 6. Tầng Ứng dụng & Giao diện (Web Dashboard)
- `app/app.py`: Khởi tạo Flask server và SocketIO.
- `app/api_routes.py`: API lấy danh sách camera, lịch sử vi phạm, thống kê.
- `app/socketio_events.py`: Đẩy dữ liệu realtime (tọa độ tay, trạng thái bước) lên web.
- `app/templates/` & `app/static/`: Giao diện Dashboard (HTML/CSS/JS).

## 7. Entry Point
- `main.py`: Khởi tạo toàn bộ hệ thống, load config, chạy các thread camera và Flask server.
