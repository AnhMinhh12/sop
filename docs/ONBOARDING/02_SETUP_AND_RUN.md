# 02 — Cài đặt & Chạy Hub lần đầu

> Mục tiêu: trong ngày 1 chiều, bạn phải chạy được `http://localhost:5001/sop` và thấy được danh sách camera trong config.

---

## Bước 1 — Chuẩn bị Python

Yêu cầu **Python 3.10+**. Kiểm tra:

```bash
python --version
```

Nếu chưa có, tải từ [python.org](https://www.python.org/downloads/) (chọn 3.10 hoặc 3.11).

Khuyến nghị dùng **venv** để cô lập package:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

---

## Bước 2 — Clone & cài package

```bash
git clone <repo-url> AI_Monitoring_Hub
cd AI_Monitoring_Hub
pip install -r requirements.txt
```

Nếu chỉ muốn test phần Edge client (không cần toàn bộ Hub):

```bash
pip install -r edge_client/requirements.txt
```

---

## Bước 3 — Cấu hình `.env`

Tạo file `.env` ở thư mục gốc (KHÔNG commit lên git):

```env
# --- App Server ---
APP_HOST=0.0.0.0
APP_PORT=5001

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

**Lưu ý:**
- Không commit `.env` lên git.
- Nếu chưa có MySQL → cài MySQL local, tạo database `ai_system`, cấp quyền cho user trên.
- Schema tự động tạo khi chạy lần đầu (xem `shared/db/db.py`).

---

## Bước 4 — Cấu hình Hub

Mở [../../config/config.yaml](../../config/config.yaml). Để test trên máy bạn (không có camera thật), có 2 lựa chọn:

### Cách A — Dùng video file thay RTSP

Trong `cameras:`, đổi `rtsp_url` sang đường dẫn file local:

```yaml
cameras:
  - id: "test_cam"
    name: "Test Camera"
    rtsp_url: "D:/videos/sample.mp4"   # đường dẫn tuyệt đối
    sop_file: "projects/sop_monitoring/config/laprap.yaml"
    engine_id: "laprap"
    yolo_model: "shared/models/yolo/laprap.onnx"
    resolution: [640, 480]
    fps_cap: 15
```

### Cách B — Test thật với camera IP trong nhà máy

Để nguyên RTSP. Nếu bạn ở ngoài LAN nhà máy, sẽ không kết nối được — bình thường.

---

## Bước 5 — Chạy Hub

```bash
python main.py
```

**Kỳ vọng log khi khởi động thành công (Full mode):**

```
=== HTMP SOP MONITORING SYSTEM IS STARTING... ===
=== HTMP SOP MONITORING SYSTEM STARTING ===
=== HUB MODE: FULL (Local AI inference) ===
Main: Initializing system services...
Main: Found 2 cameras in config.
Main: Starting station machine_07 setup...
Main: Loading engine 'TFF4040' for machine_07...
Main: Building FrameProcessor for machine_07...
Main: Station machine_07 is now ACTIVE.
====================================================
  DASHBOARD IS READY AT: http://0.0.0.0:5001
====================================================
```

Mở trình duyệt → `http://localhost:5001/sop` → thấy grid camera.

---

## Bước 6 — Chạy Hub ở Aggregator mode (khuyến nghị)

Sửa `config/config.yaml`:

```yaml
hub:
  mode: "aggregator"           # đổi từ "full"
  api_key: "test-key-123"      # bất kỳ, Edge sẽ dùng key này
  frame_cache_ttl_sec: 10
```

Rồi chạy lại `python main.py`. Log kỳ vọng:

```
=== HUB MODE: AGGREGATOR (Edge AI - No local inference) ===
Aggregator: Found 2 cameras in config.
Aggregator: Station machine_07 synced to DB
Aggregator: Station machine_08 synced to DB
====================================================
  AGGREGATOR DASHBOARD READY AT: http://0.0.0.0:5001
  Waiting for Edge servers to push frames...
====================================================
```

Lúc này Hub không load model AI, không có frame nào hiện trên dashboard (vì chưa có Edge push). Camera sẽ hiển thị "offline" — đúng.

---

## Bước 7 — Test push frame thử (giả lập Edge)

Để kiểm tra Aggregator mode có hoạt động không, dùng curl:

```bash
curl -X POST http://localhost:5001/api/station/test_cam/push_frame \
  -H "X-API-Key: test-key-123" \
  -F "image=@test.jpg" \
  -F "status={\"sop_status\":\"idle\"}" \
  -F "hands=[]"
```

Response `{"success": true}` → thành công. Vào `/sop` sẽ thấy ảnh `test.jpg` hiển thị trong ô camera `test_cam`.

Nếu trả về `403` → kiểm tra lại `api_key` trong config khớp với header `X-API-Key`.

---

## Bước 8 — Cài Edge client trên mini-PC (sau khi quen Full mode)

Chi tiết đầy đủ ở [../../distributed_setup_guide.md](../../distributed_setup_guide.md). Tóm tắt:

Trên mini-PC:
```bash
git clone <repo-url>
cd AI_Monitoring_Hub
pip install -r edge_client/requirements.txt
```

Tạo `edge_client/config.yaml`:

```yaml
camera:
  id: "machine_07"
  rtsp_url: "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102"
hub:
  url: "http://<IP_HUB>:5001"
  api_key: "test-key-123"
ai:
  model_path: "shared/models/yolo/TFF4040_roboflow2.onnx"
push:
  interval_sec: 1.0
  quality: 60
```

Chạy:

```bash
cd edge_client
python main.py --config config.yaml
```

---

## Các lỗi thường gặp khi cài lần đầu

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `ModuleNotFoundError: No module named 'onnxruntime'` | Chưa cài requirements | `pip install -r requirements.txt` |
| `[ERROR] Failed to load config.yaml` | File config sai YAML | Kiểm tra indent bằng space, không tab |
| `pymysql.err.OperationalError: (2003, ...)` | MySQL chưa chạy / sai host | Chạy MySQL, kiểm tra `.env` |
| `Cannot open RTSP` | URL sai / camera offline | Test URL trong VLC trước |
| Camera hiển thị "offline" trong Aggregator mode | Chưa có Edge push frame | Chạy Edge client hoặc test với curl ở bước 7 |

Xem thêm ở [08_TROUBLESHOOTING.md](08_TROUBLESHOOTING.md).

---

**Tiếp theo:** [03_CODE_TOUR.md](03_CODE_TOUR.md) — đi 1 vòng code theo luồng dữ liệu thật.