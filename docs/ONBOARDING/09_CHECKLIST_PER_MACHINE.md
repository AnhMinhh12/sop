# 09 — Checklist mỗi khi nhận máy mới

> In file này ra hoặc copy vào issue template. Mỗi máy mới đều phải chạy hết checklist này.

---

## Giai đoạn 1 — Khảo sát (tuần 1)

### 1.1 Thông tin chung

- [ ] **Mã máy**: ____________
- [ ] **Vị trí**: ____________
- [ ] **IP camera (LAN)**: ____________
- [ ] **Tài khoản camera**: ____________
- [ ] **RTSP URL** (đã test mở được bằng VLC): ____________
- [ ] **Công nhân vận hành**: ____________ (ca: ____________)
- [ ] **Sản phẩm trên máy**: ____________
- [ ] **SOP hiện tại** (bản giấy / PDF): ____________
- [ ] **Số bước SOP**: ____________
- [ ] **Đã có YOLO model chưa**: ☐ Có  ☐ Chưa (cần train)
- [ ] **Model hiện tại** (nếu có): ____________
- [ ] **Classes của model**: ____________

### 1.2 Khảo sát thao tác thực tế

- [ ] Đứng cùng công nhân ít nhất 1 ca để xem hết các bước.
- [ ] Chụp ảnh rõ từng bước (tay ở đâu, đặt sản phẩm ở đâu).
- [ ] Ghi chú các trường hợp "ngoại lệ" (công nhân làm khác SOP vì lý do gì).
- [ ] Hỏi công nhân: "Bước nào dễ sai nhất?" → lưu lại.

---

## Giai đoạn 2 — Chuẩn bị zone & SOP file (tuần 2)

- [ ] Chụp ảnh từ camera đúng góc thực tế.
  ```bash
  python shared/tools/capture_snapshot.py
  ```
- [ ] Vẽ zone bằng GUI:
  ```bash
  python shared/tools/zone_selector.py
  ```
- [ ] Tạo file `projects/sop_monitoring/config/<product>.yaml` với zones + steps.
- [ ] Mỗi step phải có logic rõ ràng: `zone_trigger` / `stay_in_zone` / `multi_trigger` / `dual_task`.
- [ ] Có `active_hand` đúng (`any` / `left` / `right`).
- [ ] Commit file YAML lên branch.

---

## Giai đoạn 3 — Chuẩn bị YOLO model

- [ ] Nếu chưa có model: gửi dataset cho team có GPU train, hoặc nhờ train trên Colab.
  ```bash
  # Xem công cụ chuẩn bị
  python shared/tools/prepare_training.py
  ```
- [ ] Nếu có model rồi: copy vào `shared/models/yolo/<product>.onnx`.
- [ ] Test model trên 30 ảnh mẫu: xem có detect đủ tay + sản phẩm không.
- [ ] Nếu confidence thấp: train lại với dataset bổ sung.

---

## Giai đoạn 4 — Viết Engine

- [ ] Tạo file `core/engines/<product>_engine.py`.
- [ ] Class **bắt buộc** tên `ProductEngine` (không phải `<Product>Engine`).
- [ ] Kế thừa `BaseEngine`.
- [ ] Implement `update()`, `reset()`, `get_status()`.
- [ ] Logic FSM xử lý đầy đủ các step trong YAML.
- [ ] Logic timeout / violation đúng spec.
- [ ] Commit engine lên branch.

---

## Giai đoạn 5 — Tích hợp Hub

- [ ] Thêm 1 block vào `cameras:` trong `config/config.yaml`.
- [ ] Đặt `engine_id` khớp với tên file engine.
- [ ] Đặt `sop_file` đúng đường dẫn tương đối.
- [ ] Test với `rtsp_url` trỏ file `.mp4` trước.
- [ ] Test với RTSP thật.
- [ ] Vào dashboard `/sop`, kiểm tra có camera mới xuất hiện.

---

## Giai đoạn 6 — Test ổn định (tuần 3–4)

- [ ] Theo dõi 1 ca sản xuất: vi phạm có đúng không? Có false positive không?
- [ ] Đếm số lần bắn loạn: > 5 lần/ca → cần tinh chỉnh zone / threshold.
- [ ] Cùng công nhân xem lại clip vi phạm 1–2 ngày đầu.
- [ ] Ghi nhận feedback công nhân → điều chỉnh step logic.
- [ ] Chỉnh `min_dwell_sec` / `violation_tolerance` cho hợp lý.

---

## Giai đoạn 7 — Tài liệu

- [ ] Tạo file `docs/machines/<machine_id>.md` theo template.
- [ ] Dán link RTSP + ảnh zones vào file.
- [ ] Liệt kê issues đã fix.
- [ ] Ghi rõ "Owner: <tên>" + ngày bắt đầu + ngày ổn định.

---

## Giai đoạn 8 — Triển khai Edge (nếu dùng Aggregator mode)

- [ ] Cài Edge client lên mini-PC đặt cạnh camera.
- [ ] Cấu hình `edge_client/config.yaml` đúng camera ID.
- [ ] Test push frame lên dashboard.
- [ ] Test mất mạng → reconnect tự động.
- [ ] Set up auto-start khi mini-PC reboot (Windows Task Scheduler / Linux systemd).

---

## Giai đoạn 9 — Bàn giao

- [ ] Tạo file tổng hợp trong `docs/machines/`.
- [ ] Demo 1 buổi cho team (15–30 phút).
- [ ] PR merge vào main.
- [ ] Xóa branch feature.

---

## Khi có sự cố trong tương lai

Chủ sở hữu là người đầu tiên xử lý. Nếu đã chuyển máy cho người khác:
- Owner mới phải đọc lại `docs/machines/<id>.md`.
- Nếu có bug thuộc code dùng chung → mở issue, gắn cả 2 owner.

---

**Hết bộ onboarding.** Khi đọc xong file này + làm bài tập ở file 05, bạn đã sẵn sàng nhận máy thật.
