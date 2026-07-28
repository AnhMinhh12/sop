# 06 — Work per Machine: Mỗi người phụ trách 1 máy

> Nguyên tắc của team: **mỗi người chịu trách nhiệm trọn vẹn 1–2 máy**, từ khi nhận đến khi chạy ổn định ở nhà máy.

---

## Vì sao chia theo máy chứ không theo task?

| Cách chia | Ưu | Nhược |
|---|---|---|
| **Theo máy** (đang dùng) | Mỗi người hiểu sâu máy mình, ít đụng nhau | Nếu 1 người nghỉ → máy đó dễ rơi vào quên |
| Theo task ngang (Frontend / Backend / AI) | Chuyên môn sâu từng tầng | Phải sync nhiều, conflict nhiều, người mới khó bắt nhịp |
| Theo sprint feature | Phù hợp product ngắn hạn | Không phù hợp với bảo trì camera chạy 24/7 |

Chọn **chia theo máy** vì:
- Mỗi máy là 1 mini-project với SOP, YOLO model, công nhân riêng.
- Người phụ trách phải đứng cùng công nhân hiểu quy trình → không thể "xa mặt cách lòng".
- Khi bàn giao: chuyển cả "file máy" + "kinh nghiệm thực tế" → dễ hơn bàn giao code rời rạc.

---

## Phạm vi trách nhiệm của "Owner" 1 máy

Mỗi máy có 1 chủ sở hữu duy nhất. Owner **tự chạy** từ A → Z:

1. Khảo sát quy trình thực tế tại máy (ghi chép, chụp ảnh).
2. Vẽ zone qua `shared/tools/zone_selector.py`.
3. Chuẩn bị/tận dụng model ONNX (train nếu cần — nhờ team có GPU hỗ trợ).
4. Viết/sửa engine logic SOP.
5. Test với video file → test với RTSP thật.
6. Triển khai Edge client nếu dùng Aggregator mode.
7. Theo dõi 1 tuần đầu, fix các trường hợp biên.
8. Viết `docs/machines/<machine_id>.md` để team tham khảo.

---

## Phân công hiện tại

| Máy | Owner | Camera ID | Engine ID | SOP file | YOLO model |
|---|---|---|---|---|---|
| Máy 7 | Bạn | `machine_07` | `TFF4040` | `projects/sop_monitoring/config/TFF4040.yaml` | `TFF4040_roboflow2.onnx` |
| Máy 8 | Người mới | `machine_08` | `laprap` | `config/laprap.yaml` | `laprap.onnx` |
| Máy 9+ | Sẽ phân công khi có yêu cầu | — | — | — | — |

> Trong tháng đầu, người mới tập trung 100% cho Máy 8. Sau đó sẽ phụ trách thêm máy mới.

---

## Phần làm **chung**, không theo máy

| Phần | Ai làm chính | PR review |
|---|---|---|
| `hub/` server, dashboard | Bạn | Người mới review |
| Edge client framework (RTSP, push, reconnect) | Người mới | Bạn review |
| `shared/inference.py`, `shared/inference_engine.py` | Không ai sửa nếu không cần | Cả 2 review kỹ |
| DB schema | Bạn | — |
| `config/config.yaml` (khai báo camera) | Owner của máy đó | Người kia review |

---

## File bàn giao theo máy (rất quan trọng)

Mỗi owner tạo 1 file trong `docs/machines/`:

```
docs/machines/
├── README.md                 ← giải thích cấu trúc folder
├── machine_07.md             ← owner: Bạn
└── machine_08.md             ← owner: Người mới
```

Template có sẵn ở [machine_TEMPLATE.md](../../machines/machine_TEMPLATE.md).

Nội dung gồm:
- Công nhân vận hành, ca làm.
- Link RTSP, IP camera, model WiFi.
- SOP chi tiết (file YAML + giải thích bằng lời).
- Cấu hình zones (ảnh chụp có overlay polygon).
- YOLO model: ngày train, accuracy, classes.
- Issues đã fix: bug, edge case, false positive.
- Lịch sử thay đổi.

Khi bàn giao máy → chuyển file này + đi 1 buổi thực tế tại máy.

---

## Báo cáo hàng tuần

Mỗi tuần gửi 1 message ngắn vào group chat:

```
[Tuần W42 — Machine 08]
- Đã vẽ xong zones cho 2 vùng chính
- Model ONNX test trên 100 ảnh: precision ~85%
- Engine đang handle đúng 4 step cơ bản
- Còn lại: tuning `min_dwell_sec` cho step 3 (false positive nhiều)
- Cần hỗ trợ: thu thập thêm 50 ảnh sản phẩm để train lại class "product"
```

Format: ít nhất 4 dòng, ghi rõ cần hỗ trợ gì.

---

## Quy tắc "1 máy 1 nguồn"

| Đúng ✅ | Sai ❌ |
|---|---|
| Owner tự sửa YAML + engine của máy mình, gửi PR | Người khác tự ý sửa file SOP của máy không phải của mình |
| Cần sửa chỗ khác → báo lên group, chờ owner review | "Sửa nhanh rồi PR" |
| Bàn giao đầy đủ file docs/machines/ + buổi demo | "Viết doc sau" |

---

## Khi có máy mới (ví dụ: Máy 9)

Quy trình chuẩn:

1. Sếp giao "Máy 9 cho người mới".
2. Người mới đọc [05_ADD_NEW_CAMERA.md](05_ADD_NEW_CAMERA.md) (đã thuộc từ bài tập).
3. Khảo sát nhà máy 1–2 buổi.
4. Tạo branch `feature/machine_09-init`, làm theo checklist ở [09_CHECKLIST_PER_MACHINE.md](09_CHECKLIST_PER_MACHINE.md).
5. Demo cho team → merge → triển khai thật.

Ước tính: 2–4 tuần cho 1 máy mới từ đầu đến ổn định.

---

**Tiếp theo:** [07_GIT_AND_PR.md](07_GIT_AND_PR.md) — quy trình git / PR để 2 người không đụng nhau.
