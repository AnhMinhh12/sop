# Machine <XX> — <Tên máy>

> **Template** cho mỗi máy. Copy file này ra `machine_<id>.md` rồi điền.

---

## Thông tin chung

| | |
|---|---|
| **Mã máy** | `<machine_id>` (ví dụ: `machine_07`) |
| **Vị trí** | <Xưởng, dây chuyền> |
| **IP camera (LAN)** | <10.0.x.x> |
| **RTSP URL** | `rtsp://...` |
| **Công nhân vận hành** | <Tên, ca làm> |
| **Owner** | <Tên người phụ trách> |
| **Ngày bắt đầu** | YYYY-MM-DD |
| **Ngày ổn định** | YYYY-MM-DD |
| **Trạng thái** | 🔧 Khảo sát / 🟡 Test / 🟢 Production |

---

## Sản phẩm & SOP

- **Mã sản phẩm**: `<product_id>`
- **File SOP**: `projects/sop_monitoring/config/<file>.yaml`
- **File Engine**: `projects/sop_monitoring/core/engines/<product>_engine.py`
- **Số bước SOP**: <N>
- **Liên kết SOP gốc** (file giấy/PDF): <link>

### Tóm tắt SOP (mô tả bằng lời)

1. <Bước 1: ...>
2. <Bước 2: ...>
3. ...

---

## Zones (vùng không gian)

Ảnh chụp có overlay polygon (đính kèm `<machine_id>_zones.png`).

| Tên zone | Mô tả | Hình dạng |
|---|---|---|
| `zone_a` | <Mô tả: vùng đặt tay khi...> | Đa giác N đỉnh |
| `zone_b` | <Mô tả> | Đa giác N đỉnh |

---

## AI Model

| | |
|---|---|
| **Model ONNX** | `shared/models/yolo/<model>.onnx` |
| **Input size** | <416> |
| **Classes** | `["hand", "product"]` |
| **Train ngày** | YYYY-MM-DD |
| **Trainer** | <Tên> |
| **Train data** | <Số ảnh, nguồn> |
| **Accuracy (test set)** | <mAP@0.5 = ..> |
| **False positive rate** | <%/ca> |

---

## Cấu hình trong `config/config.yaml`

```yaml
- id: "<machine_id>"
  name: "<Tên hiển thị>"
  rtsp_url: "rtsp://..."
  sop_file: "projects/sop_monitoring/config/<file>.yaml"
  engine_id: "<product_id>"
  yolo_model: "shared/models/yolo/<model>.onnx"
  resolution: [640, 480]
  fps_cap: 15
```

---

## Triển khai

### Chế độ chạy
- ☐ Hub Full mode (AI chạy trên server)
- ☐ Hub Aggregator + Edge mini-PC

### Edge (nếu có)
- **Hostname**: `edge-<id>`
- **IP**: `10.0.x.x`
- **OS**: Win 10 / Ubuntu 22.04
- **Auto-start**: ☐ Có  ☐ Chưa

---

## Lịch sử thay đổi

| Ngày | Thay đổi | Người |
|---|---|---|
| YYYY-MM-DD | Khởi tạo máy | <Tên> |
| YYYY-MM-DD | Sửa zone A do camera lệch góc | <Tên> |
| YYYY-MM-DD | Tăng `min_dwell_sec` step 3 do false positive | <Tên> |

---

## Issues đã fix

| Ngày | Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|---|
| YYYY-MM-DD | Bắn vi phạm ầm ầm | Zone quá rộng | Vẽ lại zone |
| YYYY-MM-DD | Step 3 false positive | Threshold quá thấp | Tăng lên 0.5s |

---

## Issues đang mở

- [ ] Còn false positive khi công nhân dùng tay trái cầm sản phẩm dài >5s
- [ ] ...

---

## Hình ảnh

- ![zones overlay](./machine_<id>_zones.png)
- ![dashboard thực tế](./machine_<id>_dashboard.png)

---

## Liên hệ khi có sự cố

- **Owner hiện tại**: <Tên, SĐT, email>
- **Backup**: <Tên khác>
- **Camera vendor / nhà cung cấp**: <tên, SĐT>
