# 05 — Bài tập: Thêm 1 camera / sản phẩm mới

> Bài tập này bắt buộc với người mới. Mục tiêu: sau khi làm xong, bạn tự tin thêm được 1 máy thật vào hệ thống.

## Câu hỏi thường gặp đầu tiên

**"Có cần copy cả folder dự án không?"** — **KHÔNG**.
Mỗi camera / sản phẩm chỉ là **1 entry mới** trong config + vài file YAML/ONNX mới. Folder dự án là 1, dùng chung.

## Quy tắc vàng

- ❌ **KHÔNG copy folder** để làm project riêng.
- ✅ **Sửa trực tiếp** file config + thêm file SOP/model mới.
- ✅ **1 PR / 1 thay đổi** — dễ review, dễ rollback.

---

## Bài tập: Thêm camera `test_cam` sản phẩm `test_product`

Giả sử máy test của bạn có 1 webcam laptop, gắn vào 1 máy giả lập trong nhà. Chúng ta sẽ thêm nó vào Hub.

### Bước 1 — Chuẩn bị file SOP

Tạo file `projects/sop_monitoring/config/test_product.yaml`:

```yaml
station_id: "test"
station_name: "Test Station (bài tập)"

zones:
  work_area: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]

steps:
  - step_order: 1
    step_name: "Đặt tay vào vùng work_area"
    logic: "zone_trigger"
    active_hand: "any"
    required_zone: "work_area"
    require_product: false
    min_dwell_sec: 0.3

config:
  violation_tolerance: 5
  idle_timeout_frames: 120
  transition_timeout_sec: 25.0
  min_step_dwell_sec: 0.4
  restart_allowed_until_step: 0
  ignore_zones: []
  freeze_on_two_hands: false
  freeze_cooldown_sec: 1.5
  active_hand_velocity_threshold: 0.012
```

### Bước 2 — Copy 1 model ONNX có sẵn để test

Bạn chưa cần model mới. Dùng tạm 1 model hiện có:

```bash
copy shared\models\yolo\laprap.onnx shared\models\yolo\test_product.onnx
```

### Bước 3 — Tạo engine file

Tạo file `projects/sop_monitoring/core/engines/test_product_engine.py`:

```python
"""
Engine cho sản phẩm test_product (bài tập onboarding).
Đơn giản: 1 bước duy nhất, tay vào work_area = xong.
"""
import time
from projects.sop_monitoring.core.engines.base_engine import BaseEngine


class ProductEngine(BaseEngine):
    def __init__(self, config: dict):
        super().__init__(config)
        self.zones = config.get("zones", {})
        self.steps = config.get("steps", [])
        self.current_step_idx = 0
        self.hit_count = 0
        self.is_failed = False
        self.cycle_count = 0
        self.last_transition_time = time.time()

    def update(self, hands_data, products_data=None):
        # Logic đơn giản: nếu có tay nào ở work_area -> hoàn thành step 1
        in_zone = False
        for hand in hands_data or []:
            bbox = hand.get("bbox", [0, 0, 0, 0])
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            # So sánh normalized: cần biết width, height -> ta assume 640x480
            # Engine thật sẽ dùng FrameW/FrameH do processor truyền vào
            # Đây là bài tập nên dùng tạm:
            zone = self.zones.get("work_area", [])
            if len(zone) == 4:
                # Đơn giản: check bbox nằm trong hình chữ nhật zone
                xs = [p[0] * 640 for p in zone]
                ys = [p[1] * 480 for p in zone]
                if min(xs) <= cx <= max(xs) and min(ys) <= cy <= max(ys):
                    in_zone = True
                    break

        status = {
            "sop_status": "in_progress",
            "current_step": self.current_step_idx,
            "step_label": self.steps[0]["step_name"] if self.steps else "",
            "progress_percent": 0,
            "hit_count": self.hit_count,
            "violation_type": None,
            "step_list": [s["step_name"] for s in self.steps],
        }

        if in_zone and self.current_step_idx == 0:
            self.hit_count += 1
            if self.hit_count >= 3:  # 3 frame liên tiếp
                self.current_step_idx = 1
                self.cycle_count += 1
                self.hit_count = 0
                self.last_transition_time = time.time()
                status["sop_status"] = "complete"
                status["progress_percent"] = 100

        return status

    def reset(self):
        self.current_step_idx = 0
        self.hit_count = 0
        self.is_failed = False

    def get_status(self):
        return {
            "current_step": self.current_step_idx,
            "cycle_count": self.cycle_count,
            "is_failed": self.is_failed,
        }
```

### Bước 4 — Khai báo trong `config/config.yaml`

Mở [../../config/config.yaml](../../config/config.yaml), thêm 1 block vào `cameras:`:

```yaml
cameras:
  # ... các camera cũ giữ nguyên ...

  - id: "test_cam"
    name: "Test Camera (bài tập)"
    rtsp_url: "0"   # 0 = webcam laptop, hoặc đường dẫn file .mp4
    sop_file: "projects/sop_monitoring/config/test_product.yaml"
    engine_id: "test_product"
    yolo_model: "shared/models/yolo/test_product.onnx"
    resolution: [640, 480]
    fps_cap: 15
```

### Bước 5 — Chạy và kiểm tra

```bash
python main.py
```

Kỳ vọng log:

```
Main: Found 3 cameras in config.
Main: Starting station test_cam setup...
Main: Loading engine 'test_product' for test_cam...
```

Mở `http://localhost:5001/sop` — nếu thấy ô camera `test_cam` xuất hiện → thành công.

### Bước 6 — Commit

```bash
git checkout -b feature/add-test-cam
git add projects/sop_monitoring/config/test_product.yaml
git add projects/sop_monitoring/core/engines/test_product_engine.py
git add config/config.yaml
git add shared/models/yolo/test_product.onnx
git commit -m "feat(test): add test_cam with onboarding SOP engine"
git push origin feature/add-test-cam
```

Tạo PR, người review sẽ góp ý.

---

## Khi áp dụng cho máy thật

Thay vì test trên máy bạn, thay 2 thứ:

1. `rtsp_url: "rtsp://admin:password@<ip-camera>:554/..."`
2. `yolo_model: "shared/models/yolo/<real_model>.onnx"` (model đã train cho sản phẩm đó)
3. Sửa nội dung `steps:` trong YAML cho đúng SOP mà công nhân đang làm.

Cấu trúc các bước tương tự, chỉ đổi nội dung.

---

## Checklist khi thêm 1 camera thật

- [ ] File YAML SOP đúng zones + steps (đã vẽ zone bằng `zone_selector.py`)
- [ ] Model ONNX đã có class `hand` và `product` (test trên ảnh tĩnh trước)
- [ ] RTSP URL test được qua VLC / `ffplay`
- [ ] Engine class tên `ProductEngine` kế thừa `BaseEngine`
- [ ] Đã khai báo trong `config/config.yaml`
- [ ] Test với video file trước khi nối RTSP
- [ ] Đứng cùng công nhân 1 ca để xác nhận step logic đúng
- [ ] PR review xong, merge vào main
- [ ] Đã tạo file `docs/machines/<machine_id>.md` để người sau tiếp tục

Xem thêm [09_CHECKLIST_PER_MACHINE.md](09_CHECKLIST_PER_MACHINE.md).

---

## Câu hỏi thường gặp

**Hỏi:** Tên class phải là `<id>Engine` hay `ProductEngine`?
**Đáp:** Bắt buộc `ProductEngine`. Xem `core/engines/loader.py` dòng `getattr(module, "ProductEngine")`.

**Hỏi:** File engine đặt tên khác được không?
**Đáp:** Phải đặt `<product_id>_engine.py` (snake_case). Loader tự tìm theo `product_id`.

**Hỏi:** Thêm field mới vào step có cần sửa gì khác?
**Đáp:** Sửa file YAML + đọc `step["new_field"]` trong engine của bạn. Không cần đụng BaseEngine.

**Hỏi:** Zone đặt trùng nhau có sao không?
**Đáp:** Không sao về mặt kỹ thuật, nhưng nên tránh để dễ debug.

---

**Tiếp theo:** [06_WORK_PER_MACHINE.md](06_WORK_PER_MACHINE.md) — cách team phân chia mỗi người 1 máy.
