# 03 — Code Tour: Đi 1 vòng code theo luồng dữ liệu

> Mục tiêu: đọc hiểu được code đang làm gì, theo đúng 1 frame RTSP từ lúc vào đến lúc hiện lên dashboard.

---

## Quy ước khi đọc

- Đọc từng file theo thứ tự dưới đây, mỗi file 5–10 phút.
- Không cần hiểu hết — chỉ cần biết file đó **làm gì**, **nhận input gì**, **trả output gì**, **bạn có nên đụng vào không**.
- Có biểu tượng gắn ở mỗi file:
  - 🟢 **Đọc thoải mái** — file này bạn sẽ sửa thường xuyên.
  - 🟡 **Đọc để hiểu, sửa thận trọng** — code dùng chung, muốn sửa phải PR review.
  - 🔴 **KHÔNG đụng vào** — code lõi, đã ổn định.

---

## Vòng 1 — Frame RTSP đi vào hệ thống

### 1. [../../shared/rtsp_manager.py](../../shared/rtsp_manager.py) 🟡
- Class `RTSPStream`: mở kết nối RTSP qua OpenCV.
- Tự reconnect khi mất kết nối (retry 5s, tối đa 10 lần).
- Method chính: `start()`, `get_frame()`, `stop()`.
- **Bạn cần biết:** nếu camera "đứng hình", mở file này trước.

### 2. [../../projects/sop_monitoring/processor.py](../../projects/sop_monitoring/processor.py) 🟡
- Class `FrameProcessor`: 1 thread / camera, chạy vòng lặp đọc frame.
- Gọi inference → engine → violation detector → lưu clip / phát âm thanh.
- Đây là "trái tim" của pipeline — phần lớn logic đều đi qua đây.
- **Bạn cần biết:** nó spawn 1 thread, gọi `engine.update()` mỗi frame.

### 3. [../../shared/inference.py](../../shared/inference.py) hoặc `shared/inference_engine.py` 🔴
- Đây là wrapper quanh ONNX Runtime.
- 1 instance duy nhất (singleton), 1 model ONNX dùng chung cho tất cả camera.
- **Bạn KHÔNG nên sửa** trừ khi hiểu rõ ONNX Runtime.

### 4. [../../projects/sop_monitoring/hand_detector.py](../../projects/sop_monitoring/hand_detector.py) 🟡
- Wrapper phát hiện tay + sản phẩm từ output model.
- Lọc nhiễu, lọc theo confidence, tracking tay qua các frame.
- **Bạn cần biết:** đầu ra là danh sách `{"bbox": [x1,y1,x2,y2], "label": "left"|"right", "class": "hand"|"product"}`.

---

## Vòng 2 — Engine xử lý SOP

### 5. [../../projects/sop_monitoring/core/engines/base_engine.py](../../projects/sop_monitoring/core/engines/base_engine.py) 🟢
- Lớp cha cho mọi engine sản phẩm.
- Định nghĩa interface: `update(hands_data)`, `reset()`, `get_status()`.
- **Bạn sẽ đụng vào:** khi viết engine mới, bạn kế thừa class này.

### 6. [../../projects/sop_monitoring/core/engines/loader.py](../../projects/sop_monitoring/core/engines/loader.py) 🟢
- `EngineLoader.create_engine(engine_id, sop_def)`: nạp động class tương ứng.
- Tra cứu map `"TFF4040" → TFF4040Engine`, `"laprap" → laprapEngine`, ...
- **Bạn sẽ đụng vào:** khi thêm sản phẩm mới, thêm entry vào map.

### 7. [../../projects/sop_monitoring/core/engines/TFF4040_engine.py](../../projects/sop_monitoring/core/engines/TFF4040_engine.py) 🟢
- Logic SOP cho sản phẩm TFF4040.
- Quản lý state machine: `current_step_idx`, `hit_count`, `is_failed`, ...
- **Đây là chỗ bạn sẽ sửa nhiều nhất** khi người phụ trách máy 7.

### 8. [../../projects/sop_monitoring/core/engines/laprap_engine.py](../../projects/sop_monitoring/core/engines/laprap_engine.py) 🟢
- Logic SOP cho sản phẩm laprap.
- Tương tự TFF4040 nhưng tham số khác.
- **Đây là chỗ người mới sẽ sửa** khi phụ trách máy 8.

### 9. [../../projects/sop_monitoring/core/spatial_engine.py](../../projects/sop_monitoring/core/spatial_engine.py) 🟡
- Kiểm tra 1 điểm có nằm trong polygon (zone) không — dùng `cv2.pointPolygonTest`.
- Tính dwell time (tay ở trong zone bao lâu).
- **Bạn cần biết:** input là bbox + zones, output là dict chứa thông tin vùng.

### 10. [../../projects/sop_monitoring/core/violation_detector.py](../../projects/sop_monitoring/core/violation_detector.py) 🟡
- So sánh step engine báo với step kỳ vọng → bắn vi phạm.
- Các loại vi phạm: sai bước, bỏ bước, quay lại bước trước.
- **Bạn cần biết:** nó nhận `engine.get_status()` và emit violation event.

---

## Vòng 3 — Sự kiện: lưu clip, phát âm thanh

### 11. [../../shared/events/clip_saver.py](../../shared/events/clip_saver.py) 🔴
- Lưu clip MP4 từ `FrameRingBuffer` khi có vi phạm.
- Video nén H.264 CRF 28 để tiết kiệm dung lượng.

### 12. [../../shared/events/audio_alert.py](../../shared/events/audio_alert.py) 🔴
- Phát file `.wav` qua loa của server.

### 13. [../../projects/sop_monitoring/buffer.py](../../projects/sop_monitoring/buffer.py) 🔴
- Class `FrameRingBuffer`: lưu ~20s frame gần nhất.
- Luôn chạy liên tục, không chỉ khi có vi phạm.

---

## Vòng 4 — Dashboard gửi cho trình duyệt

### 14. [../../app/__init__.py](../../app/__init__.py) 🟡
- Khởi tạo Flask + SocketIO.
- Đăng ký `processors` dict (camera_id → FrameProcessor).

### 15. [../../app/routes.py](../../app/routes.py) 🟡
- REST API endpoints (xem danh sách ở [04_SOP_ENGINE_GUIDE.md](04_SOP_ENGINE_GUIDE.md)).
- SocketIO emit: `violation`, `step_update`, `camera_status`.

### 16. [../../app/templates/](../../app/templates/) 🟡
- `index.html` — dashboard grid camera.
- `station.html` — chi tiết 1 trạm (zones, step list, hands).
- `history.html` — lịch sử vi phạm.
- `stats.html` — biểu đồ tuân thủ.

---

## Vòng 5 — Edge client (chế độ Aggregator)

### 17. [../../edge_client/main.py](../../edge_client/main.py) 🟢
- Vòng lặp đọc RTSP → chạy YOLO → gọi engine → push frame lên Hub.
- Đây là phiên bản thu nhỏ của `processor.py` Hub.

### 18. [../../edge_client/frame_pusher.py](../../edge_client/frame_pusher.py) 🟢
- Class `FramePusher`: HTTP POST frame + status + hands lên Hub.
- Tự đếm `consecutive_errors` → sau 5 lần fail thì mark unhealthy.

### 19. [../../edge_dist/](../../edge_dist/) 🟢
- Script `.bat` / `.sh` đóng gói Edge để chạy trên mini-PC.
- `prepare_edge.bat` — copy source + requirements sang máy mới.

---

## Tóm tắt vai trò — dán lên góc màn hình

```
INPUT                XỬ LÝ                           OUTPUT
─────                ──────                           ──────
RTSP camera  ───►   rtsp_manager.py
                        │
                        ▼
                  inference.py (YOLO ONNX CPU)
                        │
                        ▼
                  hand_detector.py
                        │
                        ▼
                  core/engines/<product>_engine.py  ───►  status
                        │
                        ▼
                  violation_detector.py  ───►  violation event
                        │
                        ▼
                  clip_saver.py + audio_alert.py
                        │
                        ▼
                  app/routes.py (Flask + SocketIO)
                        │
                        ▼
                  Browser Dashboard
```

---

## Bài tập nhỏ (30 phút)

Mở [../../projects/sop_monitoring/core/engines/TFF4040_engine.py](../../projects/sop_monitoring/core/engines/TFF4040_engine.py), đọc và trả lời:
1. Class kế thừa từ đâu?
2. Có bao nhiêu method public?
3. State nào được lưu giữa các frame?
4. Khi nào gọi `super().update()`?

---

**Tiếp theo:** [04_SOP_ENGINE_GUIDE.md](04_SOP_ENGINE_GUIDE.md) — chi tiết về FSM, zones và 4 loại trigger.
