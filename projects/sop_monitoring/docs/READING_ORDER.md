## 1. Tầng AI & Inference (Xử lý ảnh & Mô hình)
*Đây là các thành phần cốt lõi nhận diện bàn tay và chạy mô hình.*
- `shared/inference_engine.py`: Engine chạy ONNX bằng CPU (ONNX Runtime CPU), quản lý inference tuần tự (Singleton).
- `projects/sop_monitoring/hand_detector.py`: Bộ phát hiện bàn tay (sử dụng YOLO ONNX CPU kết hợp bộ lọc chống rung).

## 2. Tầng Logic SOP (Spatial Engine & Trạng thái)
*Các module này xử lý logic dựa trên tọa độ vùng (Zones) và trình tự thao tác.*
- `projects/sop_monitoring/core/spatial_engine.py`: Engine xử lý logic dựa trên sự tương tác của tay với các vùng không gian (ROI).
- `projects/sop_monitoring/core/engines/`: Thư mục chứa logic kiểm tra SOP cụ thể cho từng sản phẩm:
  - `base_engine.py`: Lớp cơ sở định nghĩa interface cho các SOP engine.
  - `loader.py`: Tiện ích nạp động các class engine (`ProductEngine`) tương ứng cho từng mã sản phẩm dựa trên cấu hình.
  - `626287_engine.py`: Logic kiểm tra SOP riêng cho sản phẩm 626287.
  - `TFF4040_engine.py`: Logic kiểm tra SOP riêng cho sản phẩm TFF4040.
- `projects/sop_monitoring/core/sop_graph.py`: Định nghĩa cấu trúc và thứ tự các bước SOP.
- `projects/sop_monitoring/core/tracking_engine.py`: Theo dõi chuyển động và trạng thái ổn định của bàn tay.
- `projects/sop_monitoring/core/violation_detector.py`: Xác định các lỗi vi phạm (sai bước, bỏ bước, quay lại bước trước) dựa trên kết quả phân tích.
- `projects/sop_monitoring/core/action_inference.py`: Nhận diện hành động bổ trợ (nếu có).

## 3. Tầng Pipeline Video (Xử lý luồng Camera)
*Cách hệ thống thu thập khung hình và điều phối luồng.*
- `projects/sop_monitoring/buffer.py`: Quản lý bộ đệm vòng (Ring Buffer) lưu khung hình trước/sau vi phạm.
- `shared/rtsp_manager.py`: Quản lý các kết nối RTSP và tự động kết nối lại khi mất luồng.
- `projects/sop_monitoring/processor.py`: Lớp điều phối (FrameProcessor) kết nối nhận dạng, logic SOP, lưu clip và cảnh báo.

## 4. Tầng Dịch vụ & Tiện ích (Services)
*Các công cụ hỗ trợ hệ thống vận hành ổn định.*
- `shared/services/config_loader.py`: Đọc và quản lý cấu hình từ `config.yaml`.
- `shared/services/disk_monitor.py`: Kiểm tra dung lượng ổ cứng để kích hoạt dọn dẹp dung lượng.
- `shared/services/annotator.py`: Vẽ thông tin AI (box, zones, steps) lên khung hình.
- `shared/services/logger.py`: Hệ thống ghi log tập trung.

## 5. Tầng Sự kiện & Dữ liệu (Cảnh báo & Lưu trữ)
*Xử lý kết quả sau khi phát hiện vi phạm.*
- `shared/events/audio_alert.py`: Phát âm thanh cảnh báo (.wav) qua loa của server (sử dụng sounddevice).
- `shared/events/clip_saver.py`: Lưu clip ghi hình vi phạm (MP4 H.264) từ bộ đệm vòng.
- `shared/db/db.py`: Quản lý kết nối MySQL pool và tự khởi tạo cấu trúc bảng dữ liệu `sop_*`.
- `shared/db/models.py`: Định nghĩa cấu trúc Dataclass đại diện cho từng bảng trong database, đảm bảo type safety.
- `shared/db/queries.py`: Các câu truy vấn lấy danh sách camera, lịch sử sự kiện, thống kê hiệu suất.
- `shared/db/cleanup.py`: Dọn dẹp ổ đĩa (xóa clip cũ nhất khi dung lượng ổ cứng đầy >85%).

## 6. Tầng Ứng dụng & Giao diện (Web Dashboard)
*Cung cấp giao diện tương tác người dùng.*
- `app/__init__.py` & `app/routes.py`: Khởi tạo ứng dụng Flask, định nghĩa các API endpoint trả về dữ liệu lịch sử/thống kê và phục vụ stream video.
- `app/templates/` & `app/static/`: Giao diện Dashboard (HTML/CSS/JS) hỗ trợ SPA mượt mà, đồng bộ bộ lọc Máy & Mã hàng.

## 7. Entry Point
*Điểm khởi chạy ứng dụng.*
- `main.py`: Khởi động toàn bộ hệ thống, đọc config, khởi tạo camera threads và chạy Flask server.

## 8. Công cụ & Hỗ trợ phát triển (Tools & Utilities)
*Các script bổ trợ cho việc chuẩn bị dữ liệu, cấu hình, đồng bộ giao diện và huấn luyện.*
- `sync_ui.py`: Script đồng bộ giao diện người dùng từ AI Monitoring Hub (hỗ trợ cả Offline Mode).
- `shared/tools/capture_snapshot.py`: Công cụ chụp ảnh snapshot từ camera RTSP để cấu hình vùng ROI.
- `shared/tools/zone_selector.py`: Giao diện GUI giúp lựa chọn tọa độ các vùng ROI trên ảnh snapshot.
- `shared/tools/record_video.py`: Ghi hình video mẫu từ RTSP stream phục vụ thu thập tập dữ liệu.
- `shared/tools/frame_extractor.py`: Trích xuất khung hình tự động từ video mẫu để gắn nhãn.
- `shared/tools/prepare_training.py`: Chuẩn bị và phân chia tập dữ liệu train/val phục vụ huấn luyện YOLO.
- `projects/sop_monitoring/training/clean_dataset.py`: Công cụ tự động dọn dẹp các tệp nhãn trống hoặc dữ liệu không hợp lệ.
- `projects/sop_monitoring/training/train_on_colab.py`: Script hỗ trợ nén dữ liệu và tạo môi trường huấn luyện mô hình YOLO trên Google Colab.
