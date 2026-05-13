# AI Coding Agent Rules — SOP Monitoring System

## Dự án là gì

Hệ thống giám sát thao tác công nhân qua camera IP thời gian thực.
Camera RTSP → phát hiện bàn tay (YOLO ONNX CPU) → trích keypoint (MediaPipe) → phân loại bước SOP (LSTM) → kiểm tra thứ tự (State Machine) → cảnh báo + dashboard web.

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
- **KHÔNG** import bất kỳ thư viện nào liên quan CUDA, TensorRT, hoặc GPU
- **KHÔNG** dùng `device='cuda'` — luôn dùng `device='cpu'`
- **KHÔNG** dùng `onnxruntime-gpu` — dùng `onnxruntime` (CPU-only)
- **PHẢI** export YOLO sang ONNX format để inference bằng ONNX Runtime CPU
- **PHẢI** dùng `InferenceEngine` (singleton): 1 model ONNX duy nhất, inference tuần tự cho từng camera
- YOLO input size mặc định **416**, không phải 640
- `fps_cap = 15` mặc định cho mỗi camera (Xeon 4510 đủ mạnh chạy 15 FPS/camera)
- ONNX Runtime `num_threads = 4` (để lại core cho camera threads và Flask server)
- Khi cần tối ưu: giảm fps_cap, giảm input_size xuống 320 — không thêm model mới
- **Train model trên máy khác có GPU** (PC cá nhân hoặc Google Colab) → export ONNX → copy lên server

### Storage (~900GB)
- **PHẢI** có `StorageCleanup` daemon thread: kiểm tra mỗi 10 phút, xóa clip cũ nhất khi disk > 85%
- Clip video lưu H.264, CRF 28, 480p — không lưu full HD
- `FrameRingBuffer` **luôn chạy liên tục**, không chỉ khi có vi phạm (cần 10s pre-event)
- SQLite WAL mode — bắt buộc để tránh lock khi nhiều thread ghi đồng thời
- Không lưu raw video 24/7 — chỉ lưu clip 10–30s quanh vi phạm

### Thread safety
- Mỗi camera = 1 thread riêng
- Giao tiếp giữa camera thread và `InferenceEngine` (pipelines/) qua `queue.Queue`
- Dùng `threading.Lock` khi ghi SQLite nếu không dùng WAL, hoặc để WAL tự xử lý (db/)
- Dashboard MJPEG frame buffer cần lock khi update (app/)

### Config-driven — KHÔNG hardcode
- Mọi camera URL, SOP steps, ngưỡng confidence, đường dẫn file → đọc từ `config/config.yaml`
- Thêm trạm mới = thêm entry `config.yaml` + file `config/sop_definitions/station_XX.yaml` — không sửa code
- SOP State Machine (core/) đọc steps từ YAML, không hardcode thứ tự bước trong code

### RTSP / Camera
- `integrations/rtsp_stream.py` phải tự reconnect khi mất kết nối: retry sau 5s, tối đa 10 lần, sau đó emit `camera_status: error`
- Camera lỗi không được làm crash các camera khác — mỗi thread độc lập
- Không reconnect vô hạn vòng lặp không có delay

### Sliding Window LSTM
- Dùng `collections.deque(maxlen=30)` — trượt liên tục, không reset sau mỗi prediction
- Predict mỗi khi `len(deque) == 30` VÀ `frame_count % step_size == 0`
- Chỉ push vào State Machine khi `confidence >= 0.7` (đọc từ config)
- Nếu `idle_timeout_frames` liên tiếp không detect được tay → coi là idle, reset tolerance counter nhưng KHÔNG reset SOP progress

### State Machine
- `violation_tolerance` đọc từ SOP YAML (mặc định 3) — cho phép predict sai N lần trước khi báo vi phạm
- Khi detect vi phạm: lưu DB → lưu clip → phát âm thanh → emit SocketIO (theo đúng thứ tự này)
- `reset()` chỉ gọi khi bắt đầu session mới, không tự reset giữa chừng
- **Check jig định kỳ:** Support logic `check_interval` — bước `check_jig` chỉ bắt buộc mỗi N chu kỳ (đọc từ SOP YAML). Các chu kỳ khác bỏ qua bước này mà không báo vi phạm.

---

## Thứ tự implement (PHẢI theo đúng thứ tự này)

```
1. pipelines/inference_engine.py       ← Làm đầu tiên, test với mock frames (ONNX CPU)
2. integrations/hand_detector.py       ← Wrap YOLO ONNX, dùng inference_engine
3. integrations/keypoint_extractor.py  ← MediaPipe Hands, chạy CPU
4. core/feature_engineer.py
5. core/lstm_model.py
6. core/step_classifier.py
7. core/state_machine.py               ← Test kỹ bằng unit test
8. core/violation_detector.py
9. pipelines/frame_buffer.py           ← Ring buffer pre-event
10. integrations/rtsp_stream.py
11. pipelines/frame_processor.py       ← Kết nối tất cả pipeline
12. events/audio_alert.py
13. events/clip_saver.py
14. db/db.py + models.py + queries.py
15. db/cleanup.py                      ← Disk management
16. app/app.py + api_routes.py + socketio_events.py
17. app/templates/ + app/static/       (dashboard, history, stats)
18. main.py                            ← Entry point cuối cùng
```

Mỗi module phải có unit test cơ bản trước khi sang module tiếp theo.  
Test offline bằng video file trước khi test với camera thật.

---

## Stack công nghệ

```
torch>=2.1.0
torchvision>=0.16.0
ultralytics>=8.3.0          # YOLOv11 (dùng để train & export, KHÔNG cần trên server production)
mediapipe>=0.10.0
opencv-python>=4.8.0
onnxruntime>=1.16.0          # ONNX Runtime CPU — KHÔNG dùng onnxruntime-gpu
numpy>=1.24.0
flask>=3.0.0
flask-socketio>=5.3.0
flask-cors>=4.0.0
eventlet>=0.35.0
sounddevice>=0.4.6
soundfile>=0.12.0
pyyaml>=6.0
psutil>=5.9.0
imageio>=2.31.0
imageio-ffmpeg>=0.4.9
```

**Không thêm thư viện ngoài list này** trừ khi hỏi trước.
**Bỏ `gputil`** — không có GPU để monitor. Dùng `psutil` để monitor CPU/RAM/disk.

---

## Cấu trúc thư mục — giữ đúng (theo chuẩn repo công ty)

```
sop_monitoring/
├── .github/
│   └── workflows/
├── app/                        # Flask server, routes, frontend
│   ├── app.py
│   ├── api_routes.py
│   ├── socketio_events.py
│   ├── templates/              # index, station, history, stats
│   └── static/                 # css, js
├── core/                       # Core AI & SOP logic
│   ├── lstm_model.py
│   ├── step_classifier.py
│   ├── feature_engineer.py
│   ├── state_machine.py
│   └── violation_detector.py
├── db/                         # Database layer
│   ├── db.py
│   ├── models.py
│   ├── queries.py
│   └── cleanup.py
├── events/                     # Event handling & alerts
│   ├── audio_alert.py
│   └── clip_saver.py
├── integrations/               # External integrations (camera, models)
│   ├── rtsp_stream.py
│   ├── hand_detector.py
│   └── keypoint_extractor.py
├── pipelines/                  # Processing pipelines
│   ├── inference_engine.py     # ← ĐỔI TÊN từ batch_engine.py (CPU không batch)
│   ├── frame_buffer.py
│   └── frame_processor.py
├── services/                   # Shared services & utilities
│   ├── config_loader.py
│   ├── disk_monitor.py
│   ├── logger.py
│   └── annotator.py
├── config/
│   ├── config.yaml
│   └── sop_definitions/
├── models/
│   ├── yolo/hand_detector.onnx     # ← ONNX format (KHÔNG phải .pt)
│   └── lstm/
│       ├── step_classifier.pt
│       └── label_map.json
├── training/
├── tests/
├── sounds/alert.wav
├── data/violations/ và data/logs/
├── .env.example
├── .gitignore
├── main.py
├── requirements.txt
└── README.md
```

Không tạo file ngoài cấu trúc này. Không đổi tên module.

---

## Interface các module chính

### InferenceEngine (thay BatchInferenceEngine)
```python
class InferenceEngine:
    # Singleton — 1 instance toàn hệ thống
    # Dùng ONNX Runtime CPU thay vì CUDA
    def __init__(self, model_path: str, num_threads: int, input_size: int): ...
    def submit_frame(self, camera_id: str, frame: np.ndarray) -> None: ...
    def get_result(self, camera_id: str, timeout: float = 0.1) -> list[dict] | None:
        # [{"bbox": [x1,y1,x2,y2], "confidence": float}] hoặc None
```

### SOPStateMachine
```python
class SOPStateMachine:
    def __init__(self, sop_config: dict): ...
    def process_step(self, predicted_step: str, confidence: float) -> dict:
        # {"sop_status": str, "violation_type": str|None,
        #  "expected_step": str|None, "progress_percent": float, "completed": bool}
    def reset(self) -> None: ...
```

### FrameRingBuffer
```python
class FrameRingBuffer:
    def __init__(self, fps: int, pre_seconds: int): ...
    def push(self, frame: np.ndarray) -> None: ...
    def get_pre_event_frames(self) -> list[np.ndarray]: ...
```

### ClipSaver
```python
class ClipSaver:
    def __init__(self, output_dir: str, pre_seconds: int, post_seconds: int): ...
    def save_violation_clip(self, camera_id: str, pre_frames: list, rtsp_url: str, fps: float) -> str:
        # Trả về đường dẫn file .mp4 đã lưu
```

### StepClassifier
```python
class StepClassifier:
    def __init__(self, model_path: str, label_map: dict, window_size: int, step_size: int): ...
    def push_frame(self, feature_vector: np.ndarray) -> tuple[str, float] | None:
        # (step_label, confidence) khi đủ window, None nếu chưa đủ
```

---

## Database schema tóm tắt

```sql
PRAGMA journal_mode = WAL;

cameras(id, station_id UNIQUE, name, rtsp_url, status, created_at)
sop_steps(id, station_id, step_order, step_name, step_label, max_duration_ms, is_mandatory)
sessions(id, camera_id, start_time, end_time, total_steps, correct_steps, compliance_rate)
events(id, session_id, camera_id, timestamp, step_detected, confidence,
       sop_status, violation_type, expected_step, clip_path)
violation_clips(id, event_id, camera_id, file_path, file_size_mb, duration_sec, created_at)
system_health(id, camera_id, fps, latency_ms, cpu_usage, ram_used_mb, disk_free_gb, checked_at)
```

Index bắt buộc:
```sql
CREATE INDEX idx_events_camera_time ON events(camera_id, timestamp);
CREATE INDEX idx_events_session ON events(session_id);
```

---

## API endpoints

```
GET  /                              → index.html (dashboard đa trạm)
GET  /station/<station_id>          → station.html
GET  /history                       → history.html
GET  /stats                         → stats.html
GET  /video_feed/<camera_id>        → MJPEG stream (multipart/x-mixed-replace)
GET  /clip/<clip_id>                → serve file .mp4
GET  /api/cameras
GET  /api/events?camera_id=&date=&limit=
GET  /api/stats/compliance?range=week|month
GET  /api/stats/violations?group_by=type|station
GET  /api/system/health
POST /api/session/start
POST /api/session/end
```

SocketIO emit từ server → client:
```
"violation"    → {camera_id, violation_type, expected_step, detected_step, timestamp, clip_path}
"step_update"  → {camera_id, current_step, sop_status, confidence, progress_percent}
"system_stats" → {camera_id, fps, cpu_usage_percent, ram_used_mb, disk_free_gb}
"camera_status"→ {camera_id, status}
```

---

## Coding style

- Python type hints bắt buộc cho tất cả function signature
- Docstring ngắn bằng tiếng Anh cho mỗi class và method public
- Log đầy đủ: INFO khi khởi động module, WARNING khi retry, ERROR khi fail
- Không dùng `print()` — dùng `logging` module
- Không để exception im lặng — phải log hoặc re-raise
- Tên biến, hàm, class bằng tiếng Anh
- Comment giải thích logic phức tạp bằng tiếng Việt được phép

---

## Những thứ KHÔNG làm

- KHÔNG dùng CUDA, TensorRT, hoặc bất kỳ GPU library nào (server không có GPU)
- KHÔNG dùng `onnxruntime-gpu` — chỉ dùng `onnxruntime` (CPU)
- KHÔNG dùng `gputil` — không có GPU để monitor
- KHÔNG load nhiều model YOLO cùng lúc
- KHÔNG lưu video 24/7
- KHÔNG hardcode IP camera, URL, số trạm, bước SOP trong code
- KHÔNG dùng `threading.sleep(0)` vòng lặp bận — dùng queue với timeout
- KHÔNG dùng `global` variable — truyền dependency qua constructor
- KHÔNG implement face recognition / nhận diện danh tính công nhân
- KHÔNG dùng WebRTC hoặc HLS cho video stream — chỉ dùng MJPEG
- KHÔNG thêm authentication / login — dashboard public trong LAN
