# AI Coding Agent Rules — SOP Monitoring System

## Dự án là gì

Hệ thống giám sát thao tác công nhân trên dây chuyền lắp ráp qua camera IP thời gian thực (Real-time).
Camera RTSP → phát hiện bàn tay (YOLO ONNX CPU) → xác định vùng tương tác (Spatial Zone ROI) → kiểm tra trình tự & logic SOP (Product Engines) → cảnh báo + dashboard web.

---

## Phần cứng thực tế — PHẢI ghi nhớ

| | |
|---|---|
| CPU | Intel Xeon Silver 4510 (12 cores / 24 threads) |
| RAM | 256 GB DDR5 |
| GPU | **KHÔNG CÓ GPU rời** — chỉ có Microsoft Basic Display Adapter |
| Storage | **~900 GB SSD** (OS + App + Data dùng chung, còn trống ~837 GB) |
| Network | LAN nội bộ |
| OS | Windows Server |
| Camera | IP Camera kết nối RTSP qua LAN |
| Số trạm | 1–5 trạm (phase đầu) |

---

## Quy tắc bắt buộc — KHÔNG được vi phạm

### CPU / Inference (KHÔNG có GPU)
- **KHÔNG** import bất kỳ thư viện nào liên quan CUDA, TensorRT, hoặc GPU.
- **KHÔNG** dùng `device='cuda'` — luôn dùng `device='cpu'`.
- **KHÔNG** dùng `onnxruntime-gpu` — dùng `onnxruntime` (CPU-only).
- **PHẢI** export YOLO sang ONNX format để inference bằng ONNX Runtime CPU.
- **PHẢI** dùng `InferenceEngine` (singleton) tại `shared/inference_engine.py`: 1 model ONNX duy nhất, inference tuần tự cho từng camera bằng cách serialize qua lock.
- YOLO input size mặc định **416**, không phải 640.
- `fps_cap = 15` mặc định cho mỗi camera (Xeon 4510 đủ mạnh chạy 15 FPS/camera).
- ONNX Runtime `num_threads = 4` (để lại core cho camera threads và Flask server).
- Khi cần tối ưu: giảm fps_cap, giảm input_size xuống 320 — không thêm model mới.
- **Train model trên máy khác có GPU** (PC cá nhân hoặc Google Colab) → export ONNX → copy lên server.

### Storage (~900GB)
- **PHẢI** có `StorageCleanup` daemon thread (`shared/db/cleanup.py`): kiểm tra mỗi 10 phút, tự động xóa clip cũ nhất khi dung lượng đĩa > 85%.
- Clip video lưu H.264, CRF 28, 480p — không lưu full HD.
- `FrameRingBuffer` (`projects/sop_monitoring/buffer.py`) **luôn chạy liên tục**, không chỉ khi có vi phạm (cần 20s pre-event và 5s post-event).
- Kết nối cơ sở dữ liệu qua connection pool MySQL (`shared/db/db.py`) để tránh nghẽn khi ghi dữ liệu.
- Không lưu raw video 24/7 — chỉ lưu clip 10–30s quanh vi phạm.

### Thread safety
- Mỗi camera = 1 thread riêng (`FrameProcessor` trong `projects/sop_monitoring/processor.py`).
- Giao tiếp giữa camera thread và `InferenceEngine` (shared/inference_engine.py) qua `queue.Queue` (nếu dùng) hoặc xử lý tuần tự qua khóa Lock đồng bộ.
- Sử dụng Database Connection Pool (`DBUtils.PooledDB`) để quản lý và phân phối kết nối ghi dữ liệu (`shared/db/db.py`).
- Dashboard MJPEG frame buffer cần lock khi update.

### Config-driven — KHÔNG hardcode
- Mọi camera URL, SOP steps, ngưỡng confidence, đường dẫn file → đọc từ `config/config.yaml`.
- Thêm sản phẩm mới = thêm entry trong `config/config.yaml` + file cấu hình SOP tương ứng `projects/sop_monitoring/config/{product_id}.yaml` — không sửa code.
- Mỗi sản phẩm có một Python Engine riêng kế thừa từ `BaseEngine` (được nạp động qua `loader.py`).

### RTSP / Camera
- `shared/rtsp_manager.py` phải tự reconnect khi mất kết nối: retry sau 5s, tối đa 10 lần, sau đó emit `camera_status: error`.
- Camera lỗi không được làm crash các camera khác — mỗi thread độc lập.
- Không reconnect vô hạn vòng lặp không có delay.

### Logic vùng không gian (Spatial Zone ROI)
- Sử dụng tọa độ vùng đa giác (polygon) được chuẩn hóa [0..1] trong file cấu hình SOP YAML.
- Kiểm tra tay nằm trong vùng ROI bằng hàm `cv2.pointPolygonTest`.
- Hỗ trợ 4 loại logic bước SOP chính:
  - `zone_trigger`: Tay chạm vùng tương ứng = hoàn thành bước.
  - `multi_trigger`: Tay chạm vào/ra vùng tương ứng N lần = hoàn thành bước (ví dụ: lấy 2 sản phẩm).
  - `stay_in_zone`: Tay phải ở trong vùng tối thiểu N giây = hoàn thành bước.
  - `dual_task`: Hai tay chạm vào hai vùng tương ứng (không cần đồng thời) = hoàn thành bước.

### SOP Engines & Xử lý vi phạm
- Mỗi sản phẩm được phát triển một engine riêng trong `projects/sop_monitoring/core/engines/` kế thừa `BaseEngine`.
- Engine quản lý trạng thái thao tác: `current_step_idx`, `hit_count`, `waiting_for_start`, `is_failed`, `s1_withdrawn` (tránh premature restart khi tay chưa rút khỏi vùng bước 1).
- Trình tự xử lý khi phát hiện vi phạm:
  1. Phát âm thanh cảnh báo (`audio_alert.py`).
  2. Gửi sự kiện Socket.IO tức thời cho Client (`violation`).
  3. Cắt và lưu clip MP4 từ `FrameRingBuffer` (`clip_saver.py`).
  4. Ghi thông tin vi phạm vào cơ sở dữ liệu MySQL (`sop_events`).

---

## Cấu trúc thư mục — giữ đúng (theo chuẩn repo thực tế)

```
AI_Monitoring_Hub/
├── app/                             # Flask server, routes, frontend
│   ├── __init__.py
│   ├── routes.py                    # REST API & WebSocket endpoints, page routing
│   ├── templates/                   # Giao diện HTML (index, station, history, stats, portal)
│   └── static/                      # css/style.css, js/main.js
├── config/                          # Cấu hình hệ thống
│   └── config.yaml
├── projects/                        # Thư mục các dự án con
│   └── sop_monitoring/              # Dự án SOP Monitoring
│       ├── core/                    # Logic phân tích và SOP engines
│       │   ├── engines/             # Quy trình riêng của từng sản phẩm
│       │   │   ├── base_engine.py
│       │   │   ├── loader.py
│       │   │   ├── 626287_engine.py
│       │   │   └── TFF4040_engine.py
│       │   ├── spatial_engine.py
│       │   ├── tracking_engine.py
│       │   ├── sop_graph.py
│       │   ├── violation_detector.py
│       │   └── action_inference.py
│       ├── docs/                    # Tài liệu đặc tả hệ thống
│       │   ├── READING_ORDER.md
│       │   ├── RULES.md
│       │   └── SOP_MONITORING_PLAN_v2.md
│       ├── config/                  # Định nghĩa SOP/ROI (TFF4040.yaml, 626287.yaml)
│       ├── training/                # Scripts training & dọn dẹp dataset
│       ├── buffer.py                # Frame Ring Buffer
│       ├── hand_detector.py         # Hand Detection wrap YOLO ONNX
│       └── processor.py             # Frame Processor điều phối camera stream
├── shared/                          # Module dùng chung cho toàn hệ thống
│   ├── db/                          # Tầng Database MySQL
│   │   ├── db.py                    # Cấu hình pool và bảng
│   │   ├── queries.py               # Lớp truy vấn SQL
│   │   └── cleanup.py               # Daemon thread dọn dẹp ổ đĩa
│   ├── events/                      # Xử lý âm thanh & cắt clip
│   │   ├── audio_alert.py
│   │   └── clip_saver.py
│   ├── services/                    # Dịch vụ nền (annotator, config_loader, disk_monitor, logger)
│   ├── tools/                       # Tool cấu hình ROI & thu thập video
│   ├── inference_engine.py          # Singleton ONNX Inference Engine (CPU-only)
│   └── rtsp_manager.py              # RTSP Reconnecting Stream manager
├── main.py                          # Entry point khởi chạy ứng dụng
├── requirements.txt
└── .env
```

Không tạo file ngoài cấu trúc này. Không đổi tên module.

---

## Interface các module chính

### InferenceEngine (Singleton)
```python
class InferenceEngine:
    # Singleton — 1 instance toàn hệ thống, chạy trên CPU execution provider
    def __init__(self): ...
    def infer(self, frame: np.ndarray) -> dict:
        # Trả về {"raw_output": array, "ratio": float, "pad": list, "latency_ms": float}
```

### BaseEngine
```python
class BaseEngine:
    def __init__(self, product_id: str, sop_config: dict): ...
    def update(self, hands_data: list) -> dict: ...
    def reset(self) -> None: ...
    def get_status(self) -> dict: ...
```

### FrameRingBuffer
```python
class FrameRingBuffer:
    def __init__(self, max_len: int): ...
    def push(self, frame: np.ndarray) -> None: ...
    def get_all(self) -> list[np.ndarray]: ...
```

### ClipSaver
```python
class ClipSaver:
    def __init__(self, output_dir: str): ...
    def save_violation_clip(self, camera_id: str, frames: list, filename: str, fps: float) -> str:
        # Trả về đường dẫn file .mp4 đã lưu
```

---

## Database schema tóm tắt (MySQL)

```sql
sop_definitions(id, name, description, total_steps, version, is_active, created_at, updated_at)
sop_steps(id, definition_id, step_order, step_name, step_label, max_duration_ms, is_mandatory)
sop_cameras(id, station_id UNIQUE, name, rtsp_url, definition_id, status, created_at)
sop_sessions(id, camera_id, definition_id, start_time, end_time, total_steps, correct_steps, compliance_rate)
sop_events(id, session_id, camera_id, definition_id, timestamp, step_detected, confidence, sop_status, violation_type, expected_step, clip_path)
sop_clips(id, event_id, camera_id, file_path, file_size_mb, duration_sec, created_at)
sop_health(id, camera_id, fps, latency_ms, cpu_usage, ram_used_mb, disk_free_gb, checked_at)
```

Index bắt buộc:
```sql
CREATE INDEX idx_sop_events_camera_time ON sop_events(camera_id, timestamp);
CREATE INDEX idx_sop_events_session ON sop_events(session_id);
```

---

## API endpoints

```
GET  /                              → portal.html (Trang tổng hợp các dự án)
GET  /sop                           → index.html (Dashboard grid camera)
GET  /station/<station_id>          → station.html (Chi tiết trạm)
GET  /history                       → history.html (Nhật ký vi phạm)
GET  /stats                         → stats.html (Thống kê & biểu đồ)
GET  /video_feed/<camera_id>        → MJPEG livestream
GET  /clip/<event_id>               → serve clip video vi phạm .mp4
GET  /api/cameras                   → Danh sách camera cấu hình
GET  /api/events                    → Lịch sử vi phạm (filter: camera_id, product_id, date, limit)
GET  /api/products                  → Danh sách tất cả mã sản phẩm
GET  /api/station/<id>/products     → Mã sản phẩm khả dụng cho trạm
GET  /api/station/<id>/sop          → Các bước SOP hiện tại của trạm
POST /api/station/<id>/switch_product  → Chuyển đổi mã sản phẩm runtime
GET  /api/stats/summary             → Tóm tắt thống kê ngày (compliance, total_cycles, violations)
GET  /api/stats/trend               → Xu hướng tỷ lệ tuân thủ trong tuần
GET  /api/stats/distribution        → Phân bố số lượng vi phạm theo trạm
GET  /api/system/health             → CPU/RAM/Disk stats
```

SocketIO emit từ server → client:
```
"violation"    → {camera_id, violation_type, expected_step, detected_step, timestamp}
"step_update"  → {camera_id, cycle_count, current_step, detected_step, status_msg, hit_count, step_index, step_list, confidence, sop_status, progress_percent, hands_detected}
"camera_status"→ {camera_id, status}
```

---

## Coding style

- Python type hints bắt buộc cho tất cả function signature.
- Docstring ngắn bằng tiếng Anh cho mỗi class và method public.
- Log đầy đủ: INFO khi khởi động module, WARNING khi retry, ERROR khi fail.
- Không dùng `print()` — dùng `logging` module.
- Không để exception im lặng — phải log hoặc re-raise.
- Tên biến, hàm, class bằng tiếng Anh.
- Comment giải thích logic phức tạp bằng tiếng Việt được phép.

---

## Những thứ KHÔNG làm

- KHÔNG dùng CUDA, TensorRT, hoặc bất kỳ GPU library nào (server không có GPU).
- KHÔNG dùng `onnxruntime-gpu` — chỉ dùng `onnxruntime` (CPU).
- KHÔNG dùng `gputil` — không có GPU để monitor.
- KHÔNG load nhiều model YOLO cùng lúc.
- KHÔNG lưu video 24/7.
- KHÔNG hardcode IP camera, URL, số trạm, bước SOP trong code.
- KHÔNG dùng `threading.sleep(0)` vòng lặp bận — dùng queue hoặc sleep có delay.
- KHÔNG dùng `global` variable — truyền dependency qua constructor hoặc dùng Singleton đúng cách.
- KHÔNG implement face recognition / nhận diện danh tính công nhân.
- KHÔNG dùng WebRTC hoặc HLS cho video stream — chỉ dùng MJPEG.
- KHÔNG thêm authentication / login — dashboard public trong LAN.
