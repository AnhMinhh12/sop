# Tài liệu kỹ thuật: Hệ thống giám sát SOP — AI Monitoring Hub

**Phiên bản:** 4.0 — Cập nhật theo hiện trạng triển khai thực tế  
**Ngày cập nhật:** 2026-05-29  
**Trạng thái:** Đang vận hành trên dây chuyền sản xuất (Production)

---

## 1. Giới thiệu tổng quan

### 1.1 Hệ thống này là gì?

**AI Monitoring Hub** là hệ thống giám sát thao tác công nhân trên dây chuyền lắp ráp theo thời gian thực. Hệ thống sử dụng camera IP kết nối RTSP để theo dõi bàn tay công nhân, phát hiện xem họ có thực hiện đúng quy trình SOP (Standard Operating Procedure) hay không.

**Ý tưởng cốt lõi:** Thay vì dùng LSTM/keypoint phức tạp, hệ thống sử dụng **phương pháp Spatial Zone** — chia khung hình thành các vùng đa giác (polygon zones), dùng YOLO phát hiện bàn tay, rồi kiểm tra tay nằm ở vùng nào, theo thứ tự nào → so khớp với quy trình SOP đã định nghĩa trong file YAML.

### 1.2 Kiến trúc tổng thể

```
[IP Camera] ──RTSP──► [Windows Server: Intel Xeon 4510 — CPU-only]
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
             [Lớp 1: AI]    [Lớp 2: Logic]   [Lớp 3: UI]
              YOLO ONNX       Zone-based       Flask +
             Hand Detect     State Machine     SocketIO
              (CPU-only)      per Product      MJPEG stream
                                               MySQL + Charts
                                                    │
                                          [Trình duyệt LAN]
```

### 1.3 Phần cứng server

| Thành phần | Thông số |
|---|---|
| CPU | Intel Xeon Silver 4510 (12 cores / 24 threads) |
| RAM | 256 GB DDR5 |
| GPU | **KHÔNG CÓ** — chỉ Microsoft Basic Display Adapter |
| Storage | ~900 GB SSD |
| OS | Windows Server |
| DB | MySQL trên server riêng (10.0.10.13) |

### 1.4 Quy tắc bất biến

- **KHÔNG dùng GPU/CUDA** — tất cả inference chạy CPU qua ONNX Runtime
- **KHÔNG dùng LSTM/MediaPipe** — đã loại bỏ, thay bằng Zone-based spatial logic
- **Config-driven** — thêm trạm/sản phẩm mới = thêm file YAML, không sửa code
- **Mỗi mã sản phẩm = 1 file engine Python riêng** (kế thừa BaseEngine)

---

## 2. Luồng xử lý chính (Pipeline)

```
Camera RTSP
    │
    ▼
RTSPStream (shared/rtsp_manager.py)
  → Đọc frame, resize về resolution cấu hình (640x480), auto-reconnect
    │
    ▼
FrameProcessor (projects/sop_monitoring/processor.py)
  → Orchestrator chính cho 1 camera, chạy trong 1 thread riêng
    │
    ├── HandDetector (projects/sop_monitoring/hand_detector.py)
    │     → Gọi InferenceEngine (YOLO ONNX) → Bounding box bàn tay
    │     → Chạy mỗi 2 frame (~7.5 FPS AI) để tiết kiệm CPU
    │
    ├── _filter_detections_by_roi()
    │     → Lọc bỏ tay người đi ngang qua (ngoài vùng làm việc)
    │
    ├── _associate_hands()
    │     → Bám vết tay Trái/Phải bằng khoảng cách Euclid giữa các frame
    │     → Mirror logic: bên trái camera = tay phải (do camera đối diện)
    │
    ├── ProductEngine.update(hands_data)  ← TRÁI TIM HỆ THỐNG
    │     → Kiểm tra tay đang ở vùng nào (pointPolygonTest)
    │     → So khớp với bước SOP hiện tại (zone_trigger/multi_trigger/stay_in_zone/dual_task)
    │     → Phát hiện vi phạm: timeout, skip_step, premature_restart
    │     → Trả về: {sop_status, step_index, progress_percent, violation_type, ...}
    │
    ├── ViolationDetector.analyze()
    │     → Nếu có vi phạm: phát loa + lưu clip + ghi DB + emit SocketIO
    │
    └── Annotator.draw_zones() + vẽ bbox tay
          → Ghi lên frame → phục vụ MJPEG stream cho dashboard
```

---

## 3. Cấu trúc thư mục (thực tế)

```
AI_Monitoring_Hub/
├── main.py                              # Entry point — khởi động toàn bộ hệ thống
├── requirements.txt                     # Dependencies (pip install -r requirements.txt)
├── .env                                 # Biến môi trường (DB, port, paths, CPU threads)
├── config/
│   └── config.yaml                      # Cấu hình chính: cameras, models, alerts, storage
├── app/                                 # Flask web server + Dashboard
│   ├── __init__.py                      # Khởi tạo Flask, SocketIO, emit functions
│   ├── routes.py                        # Tất cả REST API + MJPEG stream + SocketIO
│   ├── templates/                       # Giao diện HTML (Jinja2)
│   │   ├── base.html                    # Layout chung (sidebar, header)
│   │   ├── portal.html                  # Trang chủ AI Hub (tổng hợp các dự án)
│   │   ├── index.html                   # Grid camera SOP monitoring
│   │   ├── station.html                 # Chi tiết 1 trạm
│   │   ├── history.html                 # Lịch sử vi phạm
│   │   └── stats.html                   # Thống kê + biểu đồ
│   └── static/
│       ├── css/style.css
│       └── js/main.js                   # Frontend logic (SocketIO client, Chart.js)
├── projects/sop_monitoring/             # DỰ ÁN SOP MONITORING
│   ├── processor.py                     # FrameProcessor — orchestrator pipeline
│   ├── hand_detector.py                 # Wrap YOLO ONNX → bbox bàn tay
│   ├── buffer.py                        # FrameRingBuffer — lưu N giây frame gần nhất
│   ├── config/                          # Định nghĩa SOP theo mã sản phẩm
│   │   ├── TFF4040.yaml                 # 9 bước SOP cho TFF4040
│   │   └── 626287.yaml                  # 7 bước SOP cho 626287
│   ├── core/
│   │   ├── violation_detector.py        # Phân tích kết quả engine → phát hiện vi phạm
│   │   └── engines/                     # MỖI MÃ HÀNG = 1 FILE ENGINE
│   │       ├── base_engine.py           # Abstract class: update(), reset(), get_status()
│   │       ├── loader.py                # Dynamic import engine theo product_id
│   │       ├── TFF4040_engine.py        # Logic SOP cho TFF4040 (~500 dòng)
│   │       └── 626287_engine.py         # Logic SOP cho 626287 (~470 dòng)
│   ├── docs/                            # Tài liệu (file này)
│   └── training/                        # Scripts huấn luyện model
├── shared/                              # Module dùng chung
│   ├── inference_engine.py              # Singleton ONNX Runtime CPU inference
│   ├── rtsp_manager.py                  # RTSP stream + auto-reconnect
│   ├── models/yolo/                     # File .onnx cho từng mã hàng
│   │   ├── TFF4040_roboflow2.onnx       # Model YOLO đang dùng (~10MB)
│   │   └── 626287.onnx
│   ├── db/
│   │   ├── db.py                        # MySQL connection pool (DBUtils)
│   │   ├── queries.py                   # Lớp truy vấn: EventQueries, CameraQueries, ...
│   │   └── cleanup.py                   # Daemon xóa clip cũ khi disk > 85%
│   ├── events/
│   │   ├── audio_alert.py               # Phát âm thanh cảnh báo qua loa server
│   │   └── clip_saver.py                # Cắt và lưu clip vi phạm (.mp4)
│   ├── services/
│   │   ├── config_loader.py             # Load config.yaml + SOP YAML
│   │   ├── annotator.py                 # Vẽ zones, bbox lên frame
│   │   ├── disk_monitor.py              # Đọc CPU/RAM/Disk bằng psutil
│   │   └── logger.py                    # Cấu hình logging
│   ├── assets/sounds/alert.wav
│   └── tools/                           # Công cụ hỗ trợ (chạy thủ công)
│       ├── record_video.py              # Quay video thu thập dữ liệu training
│       ├── frame_extractor.py           # Trích xuất frame từ video
│       ├── zone_selector.py             # Vẽ zones trên dashboard
│       ├── capture_snapshot.py          # Chụp ảnh từ camera
│       └── blur_product.py              # Che mờ sản phẩm trong video
└── data/
    ├── violations/                      # Clip vi phạm (.mp4)
    └── logs/                            # system.log + {product}_debug.txt
```

---

## 4. Các module quan trọng — Chi tiết

### 4.1 InferenceEngine (`shared/inference_engine.py`)

**Singleton** — chỉ 1 instance cho toàn server. Load model YOLO ONNX, inference đồng bộ.

```python
class InferenceEngine:
    # Singleton pattern qua __new__
    # Thread-safe qua threading.Lock (serialize inference)
    # ONNX Runtime: CPUExecutionProvider, intra_op_num_threads=4
    
    def infer(frame) -> {"raw_output", "ratio", "pad", "latency_ms"}
    # Preprocess: Letterbox resize → cv2.dnn.blobFromImage (BGR→RGB + normalize + transpose)
    # Postprocess: Xử lý ở HandDetector
```

### 4.2 ProductEngine (`core/engines/TFF4040_engine.py`)

Đây là **trái tim logic** của hệ thống. Mỗi mã hàng có 1 file engine riêng.

**Các loại logic bước SOP được hỗ trợ:**

| Logic | Mô tả | Ví dụ |
|---|---|---|
| `zone_trigger` | Tay chạm vào vùng = hoàn thành | Đặt SP vào bàn trái |
| `multi_trigger` | Tay vào/ra vùng N lần = hoàn thành | Lấy 2 SP từ khuôn (count=2) |
| `stay_in_zone` | Tay ở trong vùng >= N giây | Lắp terminal (min_duration=2s) |
| `dual_task` | 2 tay vào 2 vùng khác nhau (không cần đồng thời) | Lấy jig (trái) & SP (phải) |

**State Machine bên trong:**
- `current_step_idx`: Bước hiện tại (0-based)
- `hit_count`: Số lần tay chạm vùng (cho multi_trigger)
- `last_trigger_states`: Trạng thái tích lũy (cho dual_task)
- `waiting_for_start`: Chờ tay vào vùng bước 1 để bắt đầu chu kỳ
- `is_failed`: Đã phát hiện vi phạm
- `cycle_count`: Số chu kỳ đã hoàn thành
- `s1_withdrawn`: Tay đã rời vùng bước 1 (tránh false-positive premature restart)

**Phát hiện vi phạm:**
- `timeout`: Quá thời gian cho phép ở 1 bước
- `skip_step`: Tay nhảy sang vùng bước tiếp theo mà chưa hoàn thành bước hiện tại
- `premature_restart` (gộp vào `skip_step`): Tay quay lại vùng bước 1 khi chưa hoàn thành

### 4.3 FrameProcessor (`processor.py`)

Orchestrator cho 1 camera. Chạy trong 1 daemon thread.

**Luồng chính (`_process_loop`):**
1. Đọc frame từ RTSPStream
2. Push frame vào FrameRingBuffer
3. Mỗi 2 frame: chạy YOLO detect → lọc ROI → bám vết tay
4. Ghost hand protection: xóa cache nếu > 0.3s không update AI
5. Gọi `engine.update(hands_data)` → nhận status
6. Nếu vi phạm: background thread xử lý (loa → SocketIO → đợi post_seconds → lưu clip → ghi DB)
7. Annotate frame → cập nhật `current_processed_frame` cho MJPEG
8. Emit SocketIO mỗi 15 frame (~1 lần/giây)

### 4.4 SOP YAML Config (`projects/sop_monitoring/config/TFF4040.yaml`)

```yaml
zones:                    # Tọa độ normalized [0..1] — polygon points
  mold: [[0.303, 0.606], [0.453, 0.761], ...]
  left_table: [...]
  middle_table: [...]
  button_right: [...]
  jig_zone: [...]

steps:                    # Thứ tự các bước SOP
  - step_order: 1
    step_name: "Lấy 2 SP từ khuôn"
    logic: "multi_trigger"        # Loại logic
    required_zone: "mold"         # Vùng cần chạm
    required_count: 2             # Số lần vào/ra
    active_hand: "any"            # any | left | right | both
  # ...

config:
  violation_tolerance: 8          # Ngưỡng dung sai
  transition_timeout_sec: 15.0    # Timeout mỗi bước
  min_step_dwell_sec: 0.8        # Thời gian tối thiểu ở 1 bước
  restart_allowed_until_step: 1   # Bước bắt đầu kiểm tra premature restart
```

---

## 5. Database (MySQL)

**Server:** 10.0.10.13:3306 | **DB:** ai_system | **Pool:** DBUtils.PooledDB (max 10 connections)

### Bảng chính:

| Bảng | Mục đích |
|---|---|
| `sop_definitions` | Template quy trình SOP (tên, số bước, version) |
| `sop_steps` | Các bước thuộc 1 definition |
| `sop_cameras` | Camera gắn với definition |
| `sop_sessions` | Phiên làm việc (start/end time, compliance_rate) |
| `sop_events` | **Bảng chính** — mỗi vi phạm/success = 1 record |
| `sop_clips` | Metadata clip video vi phạm |
| `sop_health` | Monitor CPU/RAM/Disk |

---

## 6. API Endpoints

| Method | Path | Mô tả |
|---|---|---|
| GET | `/` | Portal trang chủ AI Hub |
| GET | `/sop` | Dashboard grid camera |
| GET | `/station/<camera_id>` | Chi tiết trạm |
| GET | `/history` | Lịch sử vi phạm |
| GET | `/stats` | Thống kê + biểu đồ |
| GET | `/video_feed/<camera_id>` | MJPEG livestream |
| GET | `/clip/<event_id>` | Serve clip vi phạm |
| GET | `/api/cameras` | Danh sách camera |
| GET | `/api/events` | Lịch sử (filter: camera_id, product_id, date) |
| GET | `/api/products` | Danh sách mã sản phẩm |
| GET | `/api/station/<id>/products` | Sản phẩm của trạm |
| GET | `/api/station/<id>/sop` | Các bước SOP hiện tại |
| POST | `/api/station/<id>/switch_product` | Chuyển mã hàng runtime |
| GET | `/api/stats/summary` | Tóm tắt ngày |
| GET | `/api/stats/trend` | Xu hướng tuần |
| GET | `/api/stats/distribution` | Phân bố vi phạm |
| GET | `/api/system/health` | CPU/RAM/Disk |

**SocketIO events (server → client):**
- `step_update` → cập nhật bước SOP real-time
- `violation` → cảnh báo vi phạm
- `camera_status` → trạng thái camera

---

## 7. Cách thêm mã sản phẩm mới

### Bước 1: Tạo file SOP YAML
```
projects/sop_monitoring/config/NEW_PRODUCT.yaml
```
Định nghĩa zones (polygon) và steps (logic, required_zone, ...).

### Bước 2: Tạo file engine
```
projects/sop_monitoring/core/engines/NEW_PRODUCT_engine.py
```
Copy từ `TFF4040_engine.py`, class phải tên `ProductEngine`, kế thừa `BaseEngine`.

### Bước 3: Cập nhật config.yaml
```yaml
products:
  - id: "NEW_PRODUCT"
    name: "New Product Name"
    sop_file: "projects/sop_monitoring/config/NEW_PRODUCT.yaml"
```

### Bước 4: (Nếu cần) Train model YOLO riêng
Nếu bố trí bàn làm việc khác → cần model detect tay riêng. Train trên máy có GPU → export ONNX → đặt vào `shared/models/yolo/`.

---

## 8. Cách khởi động hệ thống

```powershell
# 1. Cài dependencies
pip install -r requirements.txt

# 2. Cấu hình .env (DB, port, camera URL, ...)

# 3. Chạy hệ thống
python main.py

# Dashboard: http://<server_ip>:4000
```

**Luồng khởi động main.py:**
1. Load `config/config.yaml`
2. Khởi tạo MySQL connection pool → tạo bảng nếu chưa có
3. Khởi tạo `InferenceEngine` (Singleton, ONNX Runtime CPU)
4. Khởi tạo `StorageCleanup` daemon, `ClipSaver`, `AudioAlert`
5. Với mỗi camera trong config: load SOP YAML → sync DB → tạo Engine → tạo `FrameProcessor` → start thread
6. Chạy Flask + SocketIO server

---

## 9. Công cụ hỗ trợ (`shared/tools/`)

| Tool | Mục đích | Cách chạy |
|---|---|---|
| `record_video.py` | Quay video từ camera để thu thập dữ liệu training | `python shared/tools/record_video.py` |
| `frame_extractor.py` | Trích xuất frame từ video thành ảnh | `python shared/tools/frame_extractor.py` |
| `zone_selector.py` | Vẽ và chọn zones trên ảnh camera | `python shared/tools/zone_selector.py` |
| `blur_product.py` | Che mờ sản phẩm trong video (bảo mật) | `python shared/tools/blur_product.py` |
| `capture_snapshot.py` | Chụp 1 ảnh từ camera RTSP | `python shared/tools/capture_snapshot.py` |

---

## 10. Rủi ro & Giải pháp

| Rủi ro | Giải pháp |
|---|---|
| CPU quá tải khi thêm camera | Giảm fps_cap, giảm input_size, chạy AI mỗi 3-4 frame |
| Tay bị nhận nhầm (người đi ngang) | Dynamic ROI filter + Temporal tracking |
| RTSP mất kết nối | Auto-reconnect (RTSPStream, retry 5s, max 10 lần) |
| False-positive premature restart | `s1_withdrawn` flag + grace period 1.0s |
| Disk đầy clip vi phạm | StorageCleanup daemon (mỗi 10 phút, xóa khi > 85%) |
| DB mất kết nối | Hệ thống vẫn chạy AI, chỉ disable logging (graceful degradation) |

---

## 11. Thông tin liên hệ & Tham khảo

- **Repository:** `AI_Monitoring_Hub` trên server nội bộ
- **Database:** MySQL `ai_system` @ 10.0.10.13
- **Dashboard:** http://10.0.9.254:4000
- **Model training:** Google Colab hoặc PC có GPU → export ONNX → copy lên server
