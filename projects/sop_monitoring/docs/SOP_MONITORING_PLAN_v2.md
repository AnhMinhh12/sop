# Kế hoạch phần mềm: Hệ thống giám sát thao tác SOP theo camera thời gian thực
**Phiên bản:** 3.0 — Cập nhật theo cấu hình phần cứng thực tế (CPU-only, Windows Server)  
**Ngày:** 2026-04-22

---

## 1. Thông số phần cứng thực tế (Server)

| Thành phần | Thông số |
|---|---|
| **CPU** | Intel Xeon Silver 4510 (12 cores / 24 threads) |
| **RAM** | 256 GB DDR5 |
| **GPU** | **KHÔNG CÓ GPU rời** — chỉ có Microsoft Basic Display Adapter |
| **Storage** | ~900 GB SSD (OS + App trên cùng 1 ổ, còn trống ~837 GB) |
| **Network** | LAN nội bộ |
| **OS** | Windows Server |

### Giới hạn phần cứng cần thiết kế phần mềm tránh vượt qua

| Tài nguyên | Giới hạn | Ảnh hưởng thiết kế |
|---|---|---|
| Không có GPU | Tất cả inference chạy trên CPU | Dùng ONNX Runtime CPU, tối ưu model size nhỏ (YOLOv11n) |
| CPU 12 cores / 24 threads | Phải chia thread hợp lý giữa inference và camera | Không chạy quá nhiều inference song song |
| Storage ~900 GB | Thoải mái lưu clip | Vẫn cần auto-cleanup nhưng ngưỡng nới lỏng hơn |
| RAM 256 GB | Rất dư dả | Có thể cache nhiều frame hơn, buffer lớn hơn |

### Ước tính năng lực tối đa với Xeon 4510 (CPU-only)

| Số trạm | FPS/trạm | CPU usage ước tính | Khả thi? |
|---|---|---|---|
| 1–2 trạm | 15 FPS | ~10–15% | ✅ Rất tốt |
| 3–4 trạm | 15 FPS | ~20–30% | ✅ Tốt |
| 5 trạm | 15 FPS | ~25–35% | ✅ Vẫn thoải mái |
| 8–10 trạm | 10–15 FPS | ~50–60% | ⚠️ Cần benchmark thực tế |
| 12+ trạm | < 10 FPS | > 70% | ❌ Cần thêm server hoặc GPU |

> **Phân tích:** Xeon 4510 có 12 cores / 24 threads. YOLOv11n ONNX (~10–15ms/frame), MediaPipe (~15ms/frame), LSTM (~2ms/frame) — tổng ~30ms/frame/camera. Ở 15 FPS, mỗi camera chiếm ~3–4 cores-equivalent → 5 trạm chỉ dùng ~25–35% CPU. Server còn rất nhiều headroom.
>
> **Quyết định thiết kế:** Phase 1 nhắm 1–5 trạm, có thể mở rộng tới 8–10 trạm mà không cần GPU. Export model sang ONNX để tận dụng tối ưu hóa CPU (AVX-512) của ONNX Runtime.

---

## 2. Tổng quan hệ thống

**Mục tiêu:** Giám sát công nhân thực hiện thao tác tay đúng bước, đúng thứ tự, đúng quy trình SOP qua RTSP IP camera. Phát hiện vi phạm và cảnh báo real-time.

**Phạm vi triển khai:**
- Giai đoạn đầu: 1–5 trạm
- Mở rộng dần theo thực tế (cần thêm server hoặc GPU nếu > 5 trạm)
- Camera: IP camera kết nối RTSP qua LAN
- Dashboard: Truy cập qua trình duyệt trên bất kỳ máy nào trong LAN (chia link là vào được)
- Cảnh báo: Âm thanh (loa kết nối server)
- Lưu bằng chứng: Clip video 10–30 giây quanh thời điểm vi phạm
- Báo cáo: Tab thống kê + lịch sử sự kiện trong dashboard

**Không cần:** Nhận diện danh tính công nhân (face ID / thẻ từ)

---

## 3. Kiến trúc hệ thống (3 lớp — CPU-only)

```
[IP Camera 1..N] ──RTSP──► [Server: Xeon 4510 — CPU-only]
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
             [Lớp 1]              [Lớp 2]              [Lớp 3]
          Thu nhận &          Phân loại &           Dashboard &
           Phát hiện          Kiểm tra SOP           Cảnh báo
                    │                   │                   │
             YOLOv11n             LSTM +              Flask +
           MediaPipe          State Machine          SocketIO
           (CPU ONNX)           (CPU PyTorch)       MJPEG stream
                                                    Audio Alert
                                                     MySQL Pool
                                                         │
                                          [Trình duyệt LAN]
                                      PC giám sát / Tablet / PC khác
```

### Luồng xử lý mỗi frame

```
Camera RTSP
    │
    ▼
Frame Queue (per camera thread)
    │
    ▼
[CPU Inference — ONNX Runtime]
  YOLOv11n: detect bounding box bàn tay (tuần tự từng camera)
    │
    ▼
MediaPipe Hands (CPU, per camera)
  → 21 keypoints (x, y, z) per hand
    │
    ▼
Feature Engineer
  → Normalize relative to wrist → vector 63 chiều
    │
    ▼
Sliding Window Buffer (deque maxlen=30)
  → Khi đủ 30 frame → LSTM inference (CPU)
    │
    ▼
Step Label + Confidence
  → Nếu confidence < 0.7: bỏ qua frame này
    │
    ▼
SOP State Machine
  → So sánh với SOP YAML
  → Kết quả: correct / wrong_order / skipped / unexpected
    │
    ├── Đúng SOP → cập nhật progress bar dashboard
    │
    └── Vi phạm → ViolationHandler
                    ├── Lưu clip video 10–30s (buffer pre/post event)
                    ├── Lưu event vào MySQL
                    ├── Phát âm thanh cảnh báo (sounddevice)
                    └── Emit SocketIO → dashboard real-time
```

### Thiết kế CPU Inference (quan trọng khi không có GPU)

```python
# Chiến lược: Export YOLOv11n sang ONNX → dùng ONNX Runtime CPU
# ONNX Runtime tự tối ưu cho kiến trúc Xeon (AVX-512, VNNI)
#
# Mỗi camera thread gửi frame vào shared queue
# Inference Thread đọc frame từ queue, inference tuần tự, trả kết quả về từng camera
# Không cần batch — CPU không hưởng lợi từ batching như GPU

class InferenceEngine:
    """
    1 instance duy nhất cho toàn server.
    Load 1 model ONNX, inference tuần tự cho từng camera.
    Tận dụng multi-thread của ONNX Runtime trên Xeon.
    """
```

---

## 4. Cấu trúc thư mục dự án (theo chuẩn repo thực tế)

```
AI_Monitoring_Hub/
|-- app/                             # Flask server, routes, frontend
|   |-- __init__.py
|   |-- routes.py                    # REST API & WebSocket endpoints, page routing
|   |-- templates/                   # Giao diện HTML (index, station, history, stats, portal)
|   +-- static/                      # css/style.css, js/main.js
|-- config/                          # Cấu hình dự án
|   +-- config.yaml
|-- projects/                        # Thư mục các dự án con
|   +-- sop_monitoring/              # Dự án SOP Monitoring
|       |-- core/                    # Logic phân tích và SOP engines
|       |   |-- engines/             # Quy trình riêng của từng sản phẩm (TFF4040, 626287)
|       |   |   |-- base_engine.py
|       |   |   |-- loader.py
|       |   |   |-- 626287_engine.py
|       |   |   +-- TFF4040_engine.py
|       |   |-- action_inference.py
|       |   |-- sop_graph.py
|       |   |-- spatial_engine.py
|       |   |-- tracking_engine.py
|       |   +-- violation_detector.py
|       |-- docs/                    # Tài liệu đặc tả hệ thống
|       |   |-- READING_ORDER.md
|       |   |-- RULES.md
|       |   +-- SOP_MONITORING_PLAN_v2.md
|       |-- buffer.py                # Frame Ring Buffer
|       |-- hand_detector.py         # Hand Detection wrap YOLO ONNX
|       +-- processor.py             # Frame Processor điều phối camera stream
|-- shared/                          # Module dùng chung cho toàn hệ thống
|   |-- db/                          # Tầng Database MySQL
|   |   |-- db.py                    # Cấu hình pool và bảng
|   |   |-- queries.py               # Lớp truy vấn SQL
|   |   +-- cleanup.py               # Daemon thread dọn dẹp ổ đĩa
|   |-- events/                      # Xử lý âm thanh & cắt clip
|   |   |-- audio_alert.py
|   |   +-- clip_saver.py
|   |-- services/                    # Dịch vụ nền
|   |   |-- annotator.py
|   |   |-- config_loader.py
|   |   |-- disk_monitor.py
|   |   +-- logger.py
|   |-- inference_engine.py          # Singleton ONNX Inference Engine (CPU-only)
|   +-- rtsp_manager.py              # RTSP Reconnecting Stream manager
|-- main.py                          # Entry point khởi động ứng dụng
|-- requirements.txt
+-- .env
```

---

## 5. File cấu hình (config.yaml)

```yaml
server:
  host: "0.0.0.0"        # Lắng nghe tất cả interface → truy cập từ LAN được
  port: 5001
  debug: false
  secret_key: "change-me-in-production"

inference:
  device: "cpu"                     # Xeon 4510 — CPU-only
  model_format: "onnx"             # Dùng ONNX Runtime cho tối ưu CPU
  num_threads: 4                    # Số thread ONNX Runtime dùng cho inference (để lại core cho camera threads)
  max_concurrent_inference: 2       # Tối đa 2 camera inference cùng lúc

models:
  yolo:
    weights: "models/yolo/hand_detector.onnx"   # ONNX format cho CPU
    confidence: 0.5
    iou_threshold: 0.45
    input_size: 416       # 416 để giảm tải CPU
  lstm:
    weights: "models/lstm/step_classifier.pt"
    label_map: "models/lstm/label_map.json"
    window_size: 30        # Số frame / prediction
    step_size: 5           # Predict mỗi 5 frame
    confidence_threshold: 0.7
    idle_timeout_frames: 90  # 3s không detect tay → coi là idle

cameras:
  - id: "station_01"
    name: "Trạm lắp ráp 1"
    rtsp_url: "rtsp://192.168.1.101:554/stream"
    sop_file: "config/sop_definitions/station_01.yaml"
    resolution: [640, 480]   # 480p để giảm tải CPU
    fps_cap: 15              # Xeon 4510 đủ mạnh để chạy 15 FPS/camera

  - id: "station_02"
    name: "Trạm lắp ráp 2"
    rtsp_url: "rtsp://192.168.1.102:554/stream"
    sop_file: "config/sop_definitions/station_02.yaml"
    resolution: [640, 480]
    fps_cap: 15

alerts:
  audio:
    enabled: true
    sound_file: "sounds/alert.wav"
    volume: 0.8
    cooldown_sec: 10         # Không báo lại cùng vi phạm trong 10 giây

storage:
  violations_dir: "data/violations/"
  clip_pre_seconds: 10       # Ghi lại 10s trước vi phạm
  clip_post_seconds: 20      # Ghi thêm 20s sau vi phạm
  max_disk_usage_percent: 85 # Khi SSD > 85% → tự xóa clip cũ nhất (nới lỏng vì 900GB)
  min_free_gb: 50            # Luôn giữ tối thiểu 50GB trống

logging:
  level: "INFO"
  log_file: "data/logs/system.log"
  max_log_mb: 100
```

---

## 6. File định nghĩa SOP mẫu (config/sop_definitions/station_01.yaml)

```yaml
station_id: "station_01"
station_name: "Trạm lắp ráp slider-terminal"
description: "Quy trình lắp ráp slider và terminal trên khuôn"

violation_tolerance: 3   # Cho phép predict sai N lần liên tiếp trước khi báo vi phạm
check_jig_interval: 2    # Check jig mỗi N chu kỳ (2 chu kỳ check 1 lần)

steps:
  - order: 1
    name: "Lấy sản phẩm ra khỏi khuôn"
    label: "take_product"
    is_mandatory: true
    max_duration_ms: 5000

  - order: 2
    name: "Lấy 2 slider ra khỏi khuôn"
    label: "take_sliders"
    is_mandatory: true
    max_duration_ms: 5000

  - order: 3
    name: "Lắp terminal vào slider"
    label: "install_terminal"
    is_mandatory: true
    max_duration_ms: 10000

  - order: 4
    name: "Để 2 slider vào lại khuôn (trái trước, phải sau)"
    label: "return_sliders"
    is_mandatory: true
    max_duration_ms: 8000

  - order: 5
    name: "Bấm nút chạy máy"
    label: "press_start"
    is_mandatory: true
    max_duration_ms: 3000

  - order: 6
    name: "Check jig sắt sản phẩm"
    label: "check_jig"
    is_mandatory: false       # Điều kiện đặc biệt: chỉ bắt buộc mỗi N chu kỳ
    check_interval: 2         # 2 chu kỳ check 1 lần
    max_duration_ms: 8000
```

---

## 7. Schema database (MySQL Pool)

```sql
-- 1. sop_definitions — Template quy trình SOP
CREATE TABLE IF NOT EXISTS sop_definitions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    description     TEXT DEFAULT NULL,
    total_steps     INT NOT NULL DEFAULT 0,
    version         VARCHAR(20) DEFAULT '1.0',
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. sop_steps — Các bước thuộc 1 definition
CREATE TABLE IF NOT EXISTS sop_steps (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    definition_id   INT NOT NULL,
    step_order      INT NOT NULL,
    step_name       VARCHAR(255) NOT NULL,
    step_label      VARCHAR(100) NOT NULL,
    max_duration_ms INT DEFAULT NULL,
    is_mandatory    TINYINT(1) DEFAULT 1,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE,
    UNIQUE(definition_id, step_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. sop_cameras — Camera gắn với 1 definition
CREATE TABLE IF NOT EXISTS sop_cameras (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    station_id      VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    rtsp_url        TEXT NOT NULL,
    definition_id   INT DEFAULT NULL,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. sop_sessions — Phiên làm việc
CREATE TABLE IF NOT EXISTS sop_sessions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    definition_id   INT NOT NULL,
    start_time      DATETIME NOT NULL,
    end_time        DATETIME DEFAULT NULL,
    total_steps     INT DEFAULT 0,
    correct_steps   INT DEFAULT 0,
    compliance_rate FLOAT DEFAULT NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. sop_events — Sự kiện vi phạm
CREATE TABLE IF NOT EXISTS sop_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      INT DEFAULT NULL,
    camera_id       INT NOT NULL,
    definition_id   INT DEFAULT NULL,
    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
    step_detected   VARCHAR(255) NOT NULL,
    confidence      FLOAT DEFAULT NULL,
    sop_status      VARCHAR(50) NOT NULL,
    violation_type  VARCHAR(100) DEFAULT NULL,
    expected_step   VARCHAR(255) DEFAULT NULL,
    clip_path       TEXT DEFAULT NULL,
    FOREIGN KEY (session_id) REFERENCES sop_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. sop_clips — Clip video vi phạm
CREATE TABLE IF NOT EXISTS sop_clips (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    event_id        BIGINT DEFAULT NULL,
    camera_id       INT NOT NULL,
    file_path       TEXT NOT NULL,
    file_size_mb    FLOAT DEFAULT NULL,
    duration_sec    INT DEFAULT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES sop_events(id) ON DELETE SET NULL,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. sop_health — Monitor hệ thống
CREATE TABLE IF NOT EXISTS sop_health (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    camera_id       INT NOT NULL,
    fps             FLOAT DEFAULT NULL,
    latency_ms      FLOAT DEFAULT NULL,
    cpu_usage       FLOAT DEFAULT NULL,
    ram_used_mb     INT DEFAULT NULL,
    disk_free_gb    FLOAT DEFAULT NULL,
    checked_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --- Indexes ---
CREATE INDEX idx_sop_events_camera_time ON sop_events(camera_id, timestamp);
CREATE INDEX idx_sop_events_session ON sop_events(session_id);
CREATE INDEX idx_sop_sessions_camera ON sop_sessions(camera_id);
CREATE INDEX idx_sop_sessions_def ON sop_sessions(definition_id);
CREATE INDEX idx_sop_health_time ON sop_health(checked_at);
CREATE INDEX idx_sop_health_camera ON sop_health(camera_id);
CREATE INDEX idx_sop_clips_created ON sop_clips(created_at);
CREATE INDEX idx_sop_steps_def ON sop_steps(definition_id);
```

---

## 8. Mô tả các module cần implement

### 8.1 `pipelines/inference_engine.py` ⭐ Module quan trọng nhất

**Nhiệm vụ:** Quản lý 1 model YOLO ONNX duy nhất trên CPU, nhận frames từ nhiều camera qua queue, inference tuần tự, trả kết quả về đúng camera.

```python
class InferenceEngine:
    """
    Singleton — chỉ tồn tại 1 instance toàn hệ thống.
    Chạy trong thread riêng, đọc frames từ queue và inference trên CPU.
    Dùng ONNX Runtime với tối ưu cho Intel Xeon.
    """
    def __init__(self, model_path: str, num_threads: int, input_size: int): ...

    def submit_frame(self, camera_id: str, frame: np.ndarray) -> None:
        """Camera thread gọi hàm này để gửi frame vào queue."""

    def get_result(self, camera_id: str, timeout: float = 0.1) -> list[dict] | None:
        """Camera thread gọi để nhận kết quả bbox bàn tay."""
        # Trả về: [{"bbox": [x1,y1,x2,y2], "confidence": float}] hoặc None
```

### 8.2 `pipelines/frame_buffer.py` ⭐ Cần cho lưu clip

**Nhiệm vụ:** Ring buffer lưu N giây frame gần nhất. Khi có vi phạm, xuất clip pre+post event.

```python
class FrameRingBuffer:
    def __init__(self, fps: int, pre_seconds: int):
        """Giữ sẵn `pre_seconds` giây frame trong bộ nhớ."""

    def push(self, frame: np.ndarray) -> None: ...

    def get_pre_event_frames(self) -> list[np.ndarray]:
        """Trả về tất cả frame đã lưu (10s trước vi phạm)."""
```

### 8.3 `events/clip_saver.py`

**Nhiệm vụ:** Nhận pre-event frames + tiếp tục record post-event, ghép và lưu thành file .mp4.

```python
class ClipSaver:
    def __init__(self, output_dir: str, pre_seconds: int, post_seconds: int): ...

    def save_violation_clip(
        self,
        camera_id: str,
        pre_frames: list[np.ndarray],
        rtsp_url: str,
        fps: float
    ) -> str:
        """
        Ghép pre_frames + record thêm post_seconds giây từ camera.
        Lưu file: data/violations/{camera_id}_{timestamp}.mp4
        Trả về: đường dẫn file đã lưu.
        """
```

### 8.4 `events/audio_alert.py`

**Nhiệm vụ:** Phát file .wav qua loa server khi có vi phạm. Có cooldown tránh spam.

```python
class AudioAlert:
    def __init__(self, sound_file: str, volume: float, cooldown_sec: int): ...

    def trigger(self, camera_id: str, violation_type: str) -> None:
        """Phát âm thanh nếu không trong cooldown."""
        # Dùng: sounddevice
```

### 8.5 `db/cleanup.py` ⭐ Quản lý disk

**Nhiệm vụ:** Chạy background thread, giám sát disk usage, tự xóa clip cũ khi vượt ngưỡng.

```python
class StorageCleanup:
    def __init__(self, violations_dir: str, max_usage_percent: float, min_free_gb: float): ...

    def start(self) -> None:
        """Chạy trong daemon thread, kiểm tra mỗi 10 phút."""

    def _cleanup_old_clips(self) -> None:
        """Xóa clip cũ nhất (theo created_at trong DB) cho đến khi đủ dung lượng."""
```

### 8.6 `core/state_machine.py`

```python
class SOPStateMachine:
    def __init__(self, sop_config: dict): ...

    def process_step(self, predicted_step: str, confidence: float) -> dict:
        """
        Trả về:
        {
            "sop_status": "correct" | "wrong_order" | "skipped" | "unexpected",
            "violation_type": None | "wrong_order" | "skipped_step" | "repeated_step" | "timeout",
            "expected_step": str | None,
            "current_step_index": int,
            "progress_percent": float,   # % hoàn thành SOP
            "completed": bool
        }
        """

    def reset(self) -> None:
        """Reset về bước đầu khi bắt đầu session mới."""
```

### 8.7 `app/app.py`

**REST API endpoints:**
```
GET  /                              → Dashboard đa trạm (index.html)
GET  /station/<station_id>          → Chi tiết 1 trạm (station.html)
GET  /history                       → Lịch sử vi phạm (history.html)
GET  /stats                         → Thống kê (stats.html)
GET  /video_feed/<camera_id>        → MJPEG stream có annotation
GET  /clip/<clip_id>                → Serve file video clip vi phạm
GET  /api/cameras                   → Danh sách camera + trạng thái
GET  /api/events?camera_id=&date=&limit=  → Lịch sử sự kiện
GET  /api/stats/compliance?range=week|month  → Compliance rate theo thời gian
GET  /api/stats/violations?group_by=type|station  → Thống kê vi phạm
GET  /api/system/health             → CPU, FPS, disk usage hiện tại
POST /api/session/start             → Bắt đầu session mới
POST /api/session/end               → Kết thúc session
```

**SocketIO events (server → client):**
```
"violation"     → { camera_id, violation_type, expected_step, detected_step, timestamp, clip_path }
"step_update"   → { camera_id, current_step, sop_status, confidence, progress_percent }
"system_stats"  → { camera_id, fps, cpu_usage_percent, ram_used_mb, disk_free_gb }
"camera_status" → { camera_id, status }   -- khi camera mất kết nối / reconnect
```

---

## 9. Giao diện Dashboard (Frontend)

### Tab 1: Giám sát trực tiếp (index.html)
- Grid hiển thị MJPEG stream từ tất cả camera đang hoạt động
- Mỗi camera: tên trạm, bước SOP hiện tại, progress bar, trạng thái (Đúng/Vi phạm)
- Badge màu đỏ nhấp nháy khi có vi phạm
- Kết nối qua SocketIO, cập nhật real-time không cần reload

### Tab 2: Chi tiết trạm (station.html)
- MJPEG stream lớn với annotation (bbox tay, tên bước, confidence score)
- Timeline bước SOP: ✅ Đúng / ❌ Vi phạm / ⏳ Chờ
- Log vi phạm gần nhất trong ngày

### Tab 3: Lịch sử (history.html)
- Bảng danh sách vi phạm: thời gian, trạm, loại vi phạm, bước kỳ vọng vs thực tế
- Nút xem clip video nhúng trực tiếp trong trang
- Filter theo: trạm, loại vi phạm, khoảng thời gian

### Tab 4: Thống kê (stats.html)
- **Compliance rate theo ngày** — Line chart (Chart.js)
- **Vi phạm theo loại** — Pie chart (wrong_order / skipped / unexpected)
- **Vi phạm theo trạm** — Bar chart so sánh các trạm
- **Bảng top vi phạm thường gặp nhất** theo bước SOP

---

## 10. Kiến trúc LSTM Model

```python
# core/lstm_model.py
import torch.nn as nn

class SOPLSTMClassifier(nn.Module):
    def __init__(self, input_size=63, hidden_size=128, num_layers=2, num_classes=7):
        # num_classes = 7: take_product, take_sliders, install_terminal,
        #                  return_sliders, press_start, check_jig, idle
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,    # 63 = 21 keypoints × 3 (x,y,z)
            hidden_size=hidden_size,   # 128 hidden units
            num_layers=num_layers,     # 2 lớp LSTM
            batch_first=True,
            dropout=0.3
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        # x shape: (batch, window_size=30, features=63)
        out, _ = self.lstm(x)
        return self.classifier(out[:, -1, :])  # Lấy output frame cuối cùng
```

**Sliding Window:**
- `window_size = 30` frame (3 giây ở 10 FPS)
- `step_size = 5` frame → predict mỗi 5 frame mới
- Implement bằng `collections.deque(maxlen=30)`

**Inference trên CPU:** LSTM model rất nhỏ (~1MB), inference trên CPU chỉ mất ~1–2ms. Không cần tối ưu thêm.

---

## 11. Quy trình huấn luyện

> **Lưu ý quan trọng:** Server production không có GPU → không train model trên server.
> Train trên máy có GPU (PC cá nhân có GTX 1660 hoặc Google Colab miễn phí).
> Sau khi train xong → export ONNX → copy file .onnx lên server.

### Bước 1: Thu thập video thao tác ✅ (ĐÃ LÀM)
- Đã quay video và chia thành các folder hành động
- Các folder: lấy sản phẩm, lấy slider, lắp terminal vào slider, để slider vào, bấm nút, check jig, idle

### Bước 2: Trích xuất ảnh cho YOLO dataset
```bash
python training/extract_frames.py \
  --video_dir training/data/ \
  --output training/data/yolo_images/ \
  --interval 2    # Mỗi 2 giây lấy 1 ảnh
```

### Bước 3: Gán nhãn bounding box bàn tay
- Dùng Grounding DINO trên Colab hoặc gán nhãn thủ công bằng LabelImg
- Chỉ cần 1 class: "hand"

### Bước 4: Train YOLOv11n phát hiện bàn tay
```bash
# Chạy trên máy có GPU hoặc Google Colab
python training/train_yolo.py \
  --data training/data/yolo_dataset/ \
  --epochs 100 \
  --imgsz 416 \
  --batch 16 \
  --device cuda:0        # Chỉ khi train, không phải trên server
# Mục tiêu: mAP50 ≥ 0.90
```

### Bước 5: Export YOLO sang ONNX (chạy trên máy train)
```bash
python training/export_onnx.py \
  --weights models/yolo/hand_detector.pt \
  --output models/yolo/hand_detector.onnx \
  --imgsz 416
# Copy file .onnx lên server production
```

### Bước 6: Trích xuất keypoints → dataset LSTM
```bash
python training/extract_keypoints.py \
  --video_dir training/data/ \
  --output training/data/keypoints/
# Output: .npy files chứa sequences (N, 30, 63)
```

### Bước 7: Train LSTM classifier
```bash
# Chạy trên máy có GPU hoặc Google Colab
python training/train_lstm.py \
  --data training/data/keypoints/ \
  --epochs 200 \
  --hidden_size 128 \
  --window_size 30 \
  --device cuda:0        # Chỉ khi train
# Mục tiêu: accuracy ≥ 90% trên validation set
# Copy file .pt lên server production
```

---

## 12. Kế hoạch phát triển theo tuần

### Giai đoạn 1 — Nền tảng & dữ liệu (Tuần 1–3)
- [x] Cài đặt môi trường trên server (Windows Server)
- [x] Quay video thao tác và chia thành các folder hành động
- [ ] Trích xuất ảnh từ video cho YOLO dataset
- [ ] Gán nhãn bounding box bàn tay (Grounding DINO hoặc LabelImg)
- [ ] Train YOLOv11n detect tay trên máy có GPU → mAP50 ≥ 0.90
- [ ] Export YOLO sang ONNX → copy lên server
- [ ] Test kết nối RTSP camera qua LAN

### Giai đoạn 2 — AI core pipeline (Tuần 4–6)
- [ ] Implement `pipelines/inference_engine.py` (ONNX CPU inference)
- [ ] Implement `integrations/keypoint_extractor.py` (MediaPipe CPU)
- [ ] Implement `core/feature_engineer.py` + `core/step_classifier.py`
- [ ] Trích xuất keypoints → train LSTM trên máy có GPU → accuracy ≥ 90%
- [ ] Implement `core/state_machine.py` + `core/violation_detector.py`
- [ ] Test pipeline offline với video file (không cần camera thật)

### Giai đoạn 3 — Camera thật + Alert (Tuần 7–9)
- [ ] Implement `integrations/rtsp_stream.py` + `pipelines/frame_buffer.py`
- [ ] Implement `events/clip_saver.py` lưu clip 10–30s
- [ ] Implement `events/audio_alert.py` phát âm thanh
- [ ] Implement `db/cleanup.py` quản lý disk tự động
- [ ] Flask server (`app/`) + MJPEG stream + SocketIO
- [ ] Test real-time với 1–2 camera thật

### Giai đoạn 4 — Dashboard đầy đủ + Scale (Tuần 10–12)
- [ ] Implement đầy đủ 4 tab dashboard (`app/templates/` + `app/static/js/`)
- [ ] REST API (`app/api_routes.py`) + biểu đồ thống kê (Chart.js)
- [ ] Lịch sử vi phạm + xem clip inline
- [ ] Test với 3–5 camera đồng thời, đo FPS và CPU usage
- [ ] Fine-tune model với dữ liệu thực tế nhà máy
- [ ] Tài liệu vận hành + hướng dẫn thêm trạm mới

---

## 13. Rủi ro & Giải pháp

| Rủi ro | Mức độ | Giải pháp |
|---|---|---|
| CPU không đủ nhanh cho 5 trạm đồng thời | Cao | Export ONNX tối ưu. Giảm fps_cap xuống 8. Giảm input_size YOLO xuống 320. Xem xét thêm GPU sau. |
| Công nhân đeo găng tay → mất keypoint | Cao | Train thêm dataset có găng. Fallback: dùng object detection (slider, terminal, khuôn) thay keypoint. |
| RTSP stream không ổn định / ngắt | Trung bình | Auto-reconnect với backoff. Camera status monitor. Emit "camera_offline" event tới dashboard. |
| Biến thể tốc độ thao tác mỗi người | Trung bình | `violation_tolerance: 3` trong SOP YAML. LSTM window 30 frame tự co dãn. |
| Latency cao khi nhiều camera cùng inference | Trung bình | Hạn chế concurrent inference (max 2). Dùng queue + priority. Giảm fps_cap. |
| Train model cần GPU nhưng server không có | Thấp | Train trên Google Colab (miễn phí) hoặc PC có GPU. Export ONNX → copy lên server. |

---

## 14. Ước tính dung lượng storage

| Loại dữ liệu | Ước tính | Ghi chú |
|---|---|---|
| OS + phần mềm | ~60 GB | Windows Server cố định |
| Model weights (ONNX + LSTM) | ~50 MB | Nhỏ |
| Dataset training | ~10–30 GB | Có thể xóa sau khi train xong |
| MySQL database | ~1–5 GB / năm | Log events + metadata |
| Clip vi phạm (H.264 CRF 28) | ~50–150 MB / clip | 30s @ 480p ≈ 80–120 MB |
| **Tổng khả dụng cho clip** | ~700–750 GB | Tự động xóa clip cũ khi > 85% |
| **Số clip lưu được** | ~5.000–9.000 clip | Rất thoải mái |

---

## 15. Requirements (requirements.txt)

```
# AI / CV
torch>=2.1.0
torchvision>=0.16.0
ultralytics>=8.3.0          # YOLOv11 (dùng để train, export)
mediapipe>=0.10.0
opencv-python>=4.8.0
onnxruntime>=1.16.0          # ONNX Runtime CPU (KHÔNG dùng onnxruntime-gpu)
numpy>=1.24.0

# Server
flask>=3.0.0
flask-socketio>=5.3.0
flask-cors>=4.0.0
eventlet>=0.35.0             # WSGI server

# Alert
sounddevice>=0.4.6           # Phát âm thanh qua loa server
soundfile>=0.12.0            # Đọc file WAV

# Utils
pyyaml>=6.0
psutil>=5.9.0                # Monitor CPU/RAM/disk

# Video
imageio>=2.31.0              # Ghi video clip
imageio-ffmpeg>=0.4.9        # FFmpeg backend cho imageio
```

> **Thay đổi so với v2:**
> - `onnxruntime-gpu` → `onnxruntime` (CPU-only)
> - Bỏ `gputil` (không có GPU để monitor)
> - `torch` + `ultralytics` chỉ cần trên máy train, trên server chỉ cần `onnxruntime`

---

## 16. Ghi chú quan trọng cho AI coding agent

1. **Server KHÔNG CÓ GPU.** Tất cả inference (YOLO, LSTM, MediaPipe) đều chạy trên CPU (Intel Xeon Silver 4510). Dùng ONNX Runtime CPU cho YOLO inference. Không import bất kỳ thư viện nào liên quan CUDA.

2. **ONNX Runtime là bắt buộc cho YOLO inference.** Export YOLOv11n sang `.onnx` format. ONNX Runtime tự tối ưu cho Xeon (AVX-512). Cấu hình `num_threads` trong config.yaml.

3. **Thread architecture:** Mỗi camera = 1 thread. Tất cả đều share 1 `InferenceEngine` (pipelines/). Dùng `queue.Queue` để giao tiếp. Inference tuần tự (không batch) — CPU không hưởng lợi từ batching.

4. **fps_cap = 15 là mặc định.** Xeon 4510 đủ mạnh chạy 15 FPS/camera. LSTM window 30 frame ở 15 FPS = 2 giây — đủ để nhận diện thao tác tay.

5. **Frame ring buffer (`pipelines/frame_buffer.py`) phải luôn chạy,** không chỉ khi có vi phạm. Buffer 10s pre-event phải được nạp liên tục để khi vi phạm xảy ra, có ngay 10s trước đó để lưu clip.

6. **MJPEG stream (`app/app.py`):** Dùng `multipart/x-mixed-replace` của Flask. Giảm JPEG quality xuống 70–80% để tiết kiệm băng thông.

7. **Disk cleanup (`db/cleanup.py`) phải là daemon thread** chạy nền mỗi 10 phút. Ngưỡng 85% (nới lỏng hơn vì 900GB). Không xóa clip đang được record.

8. **Config-driven hoàn toàn (services/config_loader.py).** Không hardcode bất kỳ thứ gì trong code. Thêm trạm mới = thêm entry trong `config/config.yaml` + thêm file SOP YAML.

9. **RTSP auto-reconnect:** `integrations/rtsp_stream.py` phải tự reconnect sau 5 giây, tối đa 10 lần, sau đó emit `camera_status: error` và dừng thread camera đó.

10. **Sliding window dùng `collections.deque(maxlen=30)`.** Trượt liên tục. Predict mỗi khi `len(deque) == 30` và `frame_count % step_size == 0`.

11. **Train trên máy khác, deploy trên server.** Server chỉ cần file `.onnx` (YOLO) và `.pt` (LSTM). Không cần cài `ultralytics` trên server production nếu chỉ dùng ONNX Runtime.

12. **Check jig định kỳ:** State Machine phải support logic `check_interval` — bước `check_jig` chỉ bắt buộc mỗi N chu kỳ (đọc từ SOP YAML). Các chu kỳ khác bỏ qua bước này mà không báo vi phạm.

13. **System health monitor dùng `psutil`** thay vì `gputil`. Theo dõi CPU usage, RAM, disk free. Emit qua SocketIO mỗi 30 giây.
