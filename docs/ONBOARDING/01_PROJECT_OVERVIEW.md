# 01 — Tổng quan dự án

## Dự án này là gì?

Hệ thống **giám sát thao tác tay của công nhân trên dây chuyền lắp ráp** qua camera IP, dùng AI (YOLO) phát hiện bàn tay, kiểm tra xem công nhân có làm đúng trình tự SOP không.

Khi phát hiện sai → hệ thống:
1. Phát âm thanh cảnh báo tại chỗ.
2. Lưu 1 đoạn video clip ngắn (10–30s) làm bằng chứng.
3. Ghi log + hiển thị trên dashboard web.

---

## Phần cứng thực tế (PHẢI nhớ)

| | |
|---|---|
| Server | Intel Xeon Silver 4510, 12 cores / 24 threads, RAM 256 GB, ~900 GB SSD, **KHÔNG CÓ GPU** |
| Camera | IP Camera kết nối RTSP qua LAN |
| Edge (tùy chọn) | Mini-PC đặt cạnh camera, chạy YOLO local |
| OS Server | Windows Server |

Vì **không có GPU** nên:
- Tất cả AI chạy bằng CPU qua **ONNX Runtime** (không phải PyTorch CUDA).
- 1 model ONNX duy nhất chạy tuần tự qua **InferenceEngine singleton** (xem `shared/inference_engine.py`).
- Mỗi camera có 1 thread riêng, nhưng inference dùng chung 1 lock → không bị quá tải CPU.

---

## Hai chế độ chạy

### Mode 1 — FULL (mặc định)
```
[Camera] --RTSP--> [Hub: chạy YOLO + SOP engine] --> [Dashboard Flask]
```
- Tất cả chạy trên server.
- Dùng khi test nhanh hoặc chỉ có 1–2 camera.
- Cảnh báo: server CPU lên ~40% mỗi camera → chỉ chạy ổn được 3–4 camera.

### Mode 2 — AGGREGATOR (khuyến nghị cho production)
```
[Camera] --RTSP--> [Edge mini-PC: chạy YOLO] --HTTP--> [Hub: nhận frame + dashboard]
```
- AI chạy trên Edge (mini-PC), Hub chỉ nhận frame đã annotate.
- Server CPU gần như = 0.
- Scale bằng cách thêm Edge → thêm camera tùy ý.
- Chi tiết: xem [../../distributed_setup_guide.md](../../distributed_setup_guide.md).

**Trong cả 2 mode, code Hub giống nhau, chỉ khác `hub.mode` trong `config/config.yaml`.**

---

## Luồng dữ liệu tổng quan (chi tiết Full mode)

```
RTSP camera
   │
   ▼
[shared/rtsp_manager.py]            # Kết nối + tự reconnect RTSP
   │  (raw frame)
   ▼
[projects/sop_monitoring/processor.py]   # FrameProcessor (1 thread / camera)
   │
   ├─> [shared/inference.py]        # YOLO ONNX detect tay + sản phẩm
   ├─> [projects/sop_monitoring/hand_detector.py]
   ├─> [core/engines/<product>_engine.py]   # FSM SOP
   ├─> [core/violation_detector.py] # Phát hiện lỗi SOP
   ├─> [shared/events/clip_saver.py]  # Lưu clip MP4
   └─> [shared/events/audio_alert.py]  # Phát âm thanh cảnh báo
   │
   ▼
[app/routes.py]                     # Flask + SocketIO gửi về dashboard
   │
   ▼
Browser Dashboard (http://hub:5001/sop)
```

Trong mode Aggregator, khối `processor.py` → `core/engines/` được lược bỏ khỏi Hub, thay bằng REST API `POST /api/station/<id>/push_frame` nhận frame từ Edge.

---

## 4 thành phần chính mà bạn sẽ đụng tới

| Thành phần | File | Vai trò | Bạn sửa khi... |
|---|---|---|---|
| **Config camera + SOP** | [../../config/config.yaml](../../config/config.yaml) + [../../projects/sop_monitoring/config/](../../projects/sop_monitoring/config/) | Khai báo camera, file SOP, model | Thêm/sửa máy, đổi RTSP URL |
| **SOP Engine** | [../../projects/sop_monitoring/core/engines/](../../projects/sop_monitoring/core/engines/) | Logic kiểm tra trình tự thao tác | Thêm sản phẩm mới, sửa logic SOP |
| **Edge Client** | [../../edge_client/](../../edge_client/) + [../../edge_dist/](../../edge_dist/) | Chạy AI trên mini-PC, push frame về Hub | Triển khai Edge thật, fix reconnect |
| **Dashboard** | [../../app/](../../app/) + [../../app/templates/](../../app/templates/) | Web UI | Thêm trang monitor Edge, đổi filter |

---

## Phần "không đụng vào" trừ khi bắt buộc

| | |
|---|---|
| `shared/inference_engine.py` | Singleton chạy model — sửa 1 dòng có thể làm crash toàn hệ thống |
| `shared/db/db.py` | Connection pool MySQL |
| `main.py` | Entry point — đã được config ổn định |
| `projects/sop_monitoring/buffer.py` | Ring buffer logic lõi |

---

## Câu hỏi thường gặp ngày đầu

**Hỏi:** Dự án dùng YOLO version nào?
**Đáp:** Tùy model đã export sang ONNX. Không cần biết version gốc.

**Hỏi:** Tại sao không dùng GPU?
**Đáp:** Server không có GPU rời. Toàn bộ AI chạy CPU qua ONNX Runtime.

**Hỏi:** Mỗi sản phẩm có engine riêng à?
**Đáp:** Đúng. Mỗi `engine_id` trong config → 1 file `core/engines/<id>_engine.py` kế thừa `BaseEngine`. Đây là chỗ bạn code logic SOP riêng.

**Hỏi:** Thêm sản phẩm mới có khó không?
**Đáp:** Làm theo file `05_ADD_NEW_CAMERA.md`. Trung bình 2–4 giờ cho người đã quen.

---

**Tiếp theo:** [02_SETUP_AND_RUN.md](02_SETUP_AND_RUN.md) — cài đặt và chạy Hub lần đầu.
