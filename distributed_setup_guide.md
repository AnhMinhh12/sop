# Quy Chuẩn Cấu Hình Camera Phân Tán (Push-Frame Mode)

Tài liệu này hướng dẫn cách cấu hình chạy camera phân tán ở máy trạm con (Edge Server) và đẩy kết quả nhận diện (gồm hình ảnh có vẽ khung và trạng thái FSM) về Hub trung tâm để hiển thị đồng nhất.

---

## 1. Nguyên Tắc Hoạt Động (Push-Frame)

* **Hub Trung tâm (Central Hub):**
  * Quản lý tập trung cơ sở dữ liệu, lịch sử vi phạm, thống kê và giao diện Web UI chính.
  * Cấu hình camera ngoại vi với `is_external: true` và `yolo_model: ""` để Hub không tự chạy luồng AI nội bộ (giảm tải CPU Hub).
  * Cung cấp HTTP POST API tại `/api/station/<camera_id>/push_frame` để nhận ảnh JPEG đã vẽ khung và trạng thái FSM từ máy trạm con.
  * Tự động phát WebSocket cập nhật giao diện thời gian thực khi nhận được dữ liệu đẩy về.

* **Máy trạm con (Edge Server - ví dụ: `laprap_htmp`):**
  * Chạy cực kỳ nhẹ nhàng (không cần Web Server Flask độc lập).
  * Tự động đọc luồng RTSP camera, chạy model YOLO và kiểm tra FSM cục bộ.
  * Nén ảnh kết quả thành JPEG và gửi HTTP POST đẩy thẳng lên Hub trung tâm thông qua luồng chạy ngầm (không gây trễ cho pipeline AI chính).

---

## 2. Các Bước Cấu Hình & Chạy Thực Tế

### Bước 1: Cấu hình trên Hub trung tâm (`AI_Monitoring_Hub/config/config.yaml`)
Khai báo camera của Máy 8 dạng ngoại vi nhận dữ liệu đẩy về:
```yaml
  - id: "machine_08"
    name: "Máy 8"
    illustration: "/static/illustration/may_8.png"
    rtsp_url: "rtsp://admin:Htmp%402019@192.168.103.18:554/Streaming/Channels/101"
    sop_file: "projects/sop_monitoring/config/laprap.yaml" # Lưu bản sao SOP tại Hub để lấy checklist
    engine_id: "laprap"
    yolo_model: "" # Không chạy AI cục bộ tại Hub
    resolution: [640, 480]
    fps_cap: 15
    is_external: true # Nhận frame push trực tiếp từ máy trạm con qua HTTP API
```

### Bước 2: Chạy Hub trung tâm
Trên server chính, mở terminal tại thư mục `AI_Monitoring_Hub` và khởi chạy:
```bash
python main.py
```
*(Hub sẽ khởi động, mở cổng Web Dashboard và sẵn sàng nhận dữ liệu từ các máy trạm).*

### Bước 3: Khởi chạy máy trạm con (`laprap_htmp`)
Cấu hình địa chỉ Hub ngay trong file `laprap.yaml` (hoặc `config/laprap.yaml`) của máy con:
```yaml
hub_url: "http://<IP_CUA_HUB>:5001" # Địa chỉ máy chủ Hub
camera_id: "machine_08"          # ID tương ứng trên Hub
```

Sau đó, chỉ cần chạy lệnh cực kỳ ngắn gọn:
```bash
python main.py
```

*(Nếu muốn ghi đè cấu hình Hub từ dòng lệnh, bạn vẫn có thể truyền thêm tham số: `python main.py --hub-url http://localhost:5001 --camera-id machine_08`)*

*(Máy trạm con sẽ tự chạy AI nhận diện và đẩy trực tiếp video kèm checklist vẽ khung lên Dashboard của Hub trung tâm. Giao diện Web của Hub sẽ cập nhật mượt mà mọi thay đổi mà không cần tải model AI nội bộ).*
