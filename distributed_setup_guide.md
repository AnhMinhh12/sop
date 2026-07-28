# Hướng dẫn Triển khai Distributed Edge Architecture

Tài liệu này hướng dẫn cách mở rộng hệ thống AI Monitoring Hub bằng kiến trúc **Distributed Edge** — Hub chỉ làm dashboard, AI chạy trên các máy trạm con (mini-PC).

---

## Tổng quan Kiến trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                     HUB (Central Server)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Flask/Socket│  │   MySQL     │  │   Frame Cache           │ │
│  │ Dashboard   │  │   Database  │  │   (external_frames)     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│         ↑               ↑                      ↑                │
└─────────┼───────────────┼──────────────────────┼────────────────┘
          │               │                      │
    Web Browser     Violation Logs        HTTP POST
          │                                    │
          │        ┌────────────────────────────┴──────────────────┐
          │        │                 NETWORK                       │
          │        └──────────────────────────────────────────────┘
          │                      ↑           ↑           ↑
    ┌─────┴─────┐       ┌───────┴───┐ ┌────┴────┐ ┌───┴────┐
    │  Browser  │       │  Edge 1   │ │ Edge 2  │ │ Edge N │
    │  (View)   │       │ (machine_07)│ │(machine_08)||(machine_09)
    └───────────┘       └──────┬────┘ └────┬────┘ └───┬────┘
                               │            │          │
                          RTSP+CAM    RTSP+CAM   RTSP+CAM
                          +YOLO       +YOLO      +YOLO
```

---

## Hai Chế độ Hoạt động

### Mode 1: FULL (Mặc định - giữ nguyên)
Hub chạy AI local cho tất cả cameras.
```yaml
hub:
  mode: "full"  # Mặc định
```
→ Dùng khi Hub có đủ CPU hoặc cần test nhanh.

### Mode 2: AGGREGATOR (Khuyến nghị cho production)
Hub **không chạy AI**, chỉ nhận frame từ Edge servers.
```yaml
hub:
  mode: "aggregator"
  api_key: "your-secret-key-here"  # Quan trọng: bảo mật
```
→ CPU Hub gần như 0, scale bằng cách thêm Edge.

---

## Bước 1: Cấu hình Hub (Aggregator Mode)

### 1.1 Cập nhật `config/config.yaml`

```yaml
hub:
  mode: "aggregator"
  api_key: "change-me-in-production"
  frame_cache_ttl_sec: 10

cameras:
  - id: "machine_07"
    name: "Máy 7"
    rtsp_url: "rtsp://..."
    sop_file: "projects/sop_monitoring/config/TFF4040.yaml"
    engine_id: "TFF4040"
    # is_external: true sẽ được tự động áp dụng trong aggregator mode

  - id: "machine_09"
    name: "Máy 9"
    rtsp_url: "rtsp://..."
    sop_file: "projects/sop_monitoring/config/laprap.yaml"
    engine_id: "laprap"
```

### 1.2 Khởi chạy Hub

```bash
# Cách 1: Qua config
# Sửa hub.mode = "aggregator" trong config.yaml

# Cách 2: Qua env var (override config)
set HUB_MODE=aggregator
set HUB_API_KEY=my-secret-key
python main.py
```

**Log khi khởi động thành công:**
```
=== HTMP SOP MONITORING SYSTEM STARTING ===
=== HUB MODE: AGGREGATOR (Edge AI - No local inference) ===
Aggregator: Found 2 cameras in config.
Aggregator: Station machine_07 synced to DB
Aggregator: Station machine_09 synced to DB
====================================================
  AGGREGATOR DASHBOARD READY AT: http://0.0.0.0:5001
  Waiting for Edge servers to push frames...
====================================================
```

---

## Bước 2: Triển khai Edge Client

### 2.1 Chuẩn bị máy Edge (mini-PC)

Yêu cầu:
- OS: Windows 10/11 hoặc Ubuntu 20.04+
- Python 3.8+
- CPU: Intel Celeron/Pentium hoặc tương đương (YOLO inference nhẹ)
- RAM: 4GB

### 2.2 Cài đặt Dependencies

```bash
cd AI_Monitoring_Hub
pip install -r edge_client/requirements.txt
```

### 2.3 Cấu hình Edge Client

Tạo file `edge_client/config.yaml`:

```yaml
camera:
  id: "machine_07"
  name: "Máy 7"
  rtsp_url: "rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101"
  resolution: [640, 480]

hub:
  url: "http://10.0.10.100:5001"  # IP của Hub
  api_key: "change-me-in-production"  # Phải khớp với Hub

ai:
  model_path: "shared/models/yolo/TFF4040.onnx"
  input_size: 416

sop:
  file: "config/TFF4040.yaml"

push:
  interval_sec: 1.0
  quality: 60
```

### 2.4 Khởi chạy Edge Client

```bash
cd edge_client

# Cách 1: Qua config file
python main.py --config config.yaml

# Cách 2: Qua env vars
set HUB_URL=http://10.0.10.100:5001
set HUB_API_KEY=my-secret-key
set CAMERA_ID=machine_07
set RTSP_URL=rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
python main.py
```

**Log khi khởi động thành công:**
```
=== EDGE CLIENT STARTING ===
Camera ID: machine_07
Hub URL: http://10.0.10.100:5001
RTSP: rtsp://192.168.1.100:554/...
Loading model: shared/models/yolo/TFF4040.onnx
Loading engine: TFF4040
Push interval: 1.0s
=== EDGE CLIENT READY ===
Pushing to: http://10.0.10.100:5001/api/station/machine_07/push_frame
```

---

## Bước 3: Kiểm tra

### 3.1 Test push_frame API

```bash
# Test manual với curl
curl -X POST http://localhost:5001/api/station/machine_07/push_frame \
  -H "X-API-Key: change-me-in-production" \
  -F "image=@test.jpg" \
  -F "status={\"sop_status\":\"idle\"}" \
  -F "hands=[]"
```

Response `{"success": true}` = thành công.

### 3.2 Kiểm tra Dashboard

1. Mở trình duyệt: `http://<hub-ip>:5001/sop`
2. Camera nào có Edge push frame sẽ hiển thị video
3. Camera không có Edge sẽ hiển thị trạng thái "offline"

### 3.3 Theo dõi CPU Usage

```bash
# Trên Hub (phải gần như 0 CPU)
# Trên Edge (chạy AI)
```

---

## Bước 4: Mở rộng (Scale)

### Thêm Edge mới

1. Thêm camera vào `config.yaml` trên Hub
2. Cài đặt Edge Client trên máy mới
3. Cấu hình `camera_id` khớp với Hub
4. Khởi chạy — dashboard tự nhận diện

### Monitoring nhiều Edges

Có thể thêm bảng `edge_servers` trong DB để tracking:

```sql
CREATE TABLE edge_servers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    edge_id VARCHAR(50) UNIQUE,
    ip_address VARCHAR(45),
    last_heartbeat DATETIME,
    camera_count INT,
    status VARCHAR(20) DEFAULT 'online'
);
```

---

## Troubleshooting

### Edge không push được
1. Kiểm tra `HUB_API_KEY` khớp nhau
2. Kiểm tra firewall: port 5001 mở chưa
3. Kiểm tra Hub có đang chạy không

### Dashboard hiển thị "stale"
- Frame cache có TTL 10 giây
- Nếu Edge push chậm >10s, Hub sẽ hiển thị offline
- Tăng `hub.frame_cache_ttl_sec` nếu cần

### Camera bị "frozen"
- Edge có thể đã mất kết nối
- Kiểm tra log Edge: `Push failed, consecutive errors`

---

## So sánh Performance

| Metric | Full Mode | Aggregator Mode |
|--------|-----------|-----------------|
| CPU Hub | N × 40% | ~2% (Flask only) |
| CPU Edge | 0% | 30-50% per camera |
| Max Cameras | 3-4 (CPU limited) | Unlimited (scale horizontally) |
| Latency | <100ms local | 1-2s (network) |

---

## Security Notes

1. **API Key**: Đổi `change-me-in-production` bằng key thật
2. **HTTPS**: Trong production, dùng HTTPS để mã hóa traffic
3. **Firewall**: Chỉ mở port 5001 cho các IP edge được phép
4. **API Key Rotation**: Đổi key định kỳ bằng cách restart cả Hub và Edge
