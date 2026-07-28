# 04 — SOP Engine Guide: FSM, Zones, Steps

> Mục tiêu: hiểu được cách SOP engine hoạt động — từ zone, step, đến quyết định "đạt/vi phạm".

---

## SOP là gì?

SOP = **Standard Operating Procedure** — quy trình thao tác chuẩn của công nhân.

Ví dụ cho Máy 7 (sản phẩm TFF4040):
1. Lấy 2 sản phẩm từ khuôn.
2. Đặt sản phẩm vào bàn bên trái.
3. Lấy 2 slider từ khuôn.
4. ...

Mỗi **bước** có **điều kiện hoàn thành** (tay chạm vùng nào, bao lâu, tay trái hay tay phải).

Hệ thống AI kiểm tra công nhân có làm đúng trình tự không. Nếu sai → bắn vi phạm.

---

## 3 khái niệm cốt lõi

### 1. Zone (vùng không gian)

Zone là 1 đa giác (polygon) trong ảnh camera, định nghĩa ở tọa độ chuẩn hóa `[0..1]`.

Ví dụ (xem [../../projects/sop_monitoring/config/laprap.yaml](../../projects/sop_monitoring/config/laprap.yaml)):

```yaml
zones:
  hop_giua:  [[0.598, 0.824], [0.393, 0.856], [0.389, 0.535], [0.551, 0.522]]
  thung_tren: [[0.389, 0.876], [0.083, 0.769], [0.173, 0.414], [0.395, 0.481]]
  thung_phai: [[0.553, 0.517], [0.305, 0.526], [0.312, 0.285], [0.55, 0.285]]
  thung_trai: [[0.364, 0.998], [0.392, 0.865], [0.603, 0.828], [0.631, 0.997]]
```

> Tọa độ `0,0` = góc trên trái, `1,1` = góc dưới phải.
> Tọa độ chuẩn hóa để zone vẫn đúng khi resize ảnh sang resolution khác.

Kiểm tra điểm có nằm trong zone: dùng `cv2.pointPolygonTest()` (xem `core/spatial_engine.py`).

### 2. Step (bước SOP)

```yaml
steps:
  - step_order: 1
    step_name: "Đặt SP1 vào hộp giữa"
    logic: "zone_trigger"
    active_hand: "any"           # "any" | "left" | "right"
    required_zone: "hop_giua"
    require_product: true        # có yêu cầu cả sản phẩm trong zone không
    min_dwell_sec: 0.3           # tay phải ở zone tối thiểu 0.3s
    timeout_sec: -1              # -1 = không giới hạn
```

### 3. Logic (loại trigger)

| Logic | Ý nghĩa | Ví dụ |
|---|---|---|
| `zone_trigger` | Tay chạm zone = hoàn thành | Đặt tay vào `hop_giua` |
| `multi_trigger` | Tay chạm zone N lần = hoàn thành | Lấy 2 SP = chạm `mold` 2 lần |
| `stay_in_zone` | Tay ở trong zone liên tục N giây | Giữ 2 tay tại `middle_table` 3s |
| `dual_task` | Hai tay chạm hai zone (không cần đồng thời) | Tay trái ở `left_table`, tay phải ở `middle_table` |

---

## State Machine (FSM)

Engine giữ trạng thái giữa các frame. Các state chính:

```
          ┌──────────────────────────────────────────┐
          │                                          │
          ▼                                          │
   ┌─────────────┐    step OK    ┌─────────────┐     │
   │  IN_STEP_1  │ ───────────►  │  IN_STEP_N  │     │
   └─────────────┘               └─────────────┘     │
          │                              │           │
          │ timeout/violation            │ timeout   │
          ▼                              ▼           │
   ┌─────────────┐               ┌──────────────┐   │
   │  VIOLATION  │ ─reset──────► │ IDLE / WAIT  │───┘
   └─────────────┘               └──────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  COMPLETE   │ (chu kỳ xong)
                                       └─────────────┘
```

Trong code (`TFF4040_engine.py`):
- `current_step_idx` — đang ở bước nào (0-indexed).
- `hit_count` — đã trigger zone bao nhiêu lần (cho `multi_trigger`).
- `step_start_time` — thời điểm vào step hiện tại (cho `stay_in_zone`).
- `is_failed` — đang trong trạng thái vi phạm.
- `s1_withdrawn` — tay đã rút khỏi zone step 1 chưa (chống restart sớm).

---

## Vòng đời 1 frame trong Engine

```
FrameProcessor gọi engine.update(hands_data, products_data)
        │
        ▼
1. Spatial check (điểm trong polygon?)
   → gắn nhãn "in_zone_X" cho từng hand
        │
        ▼
2. Tracking check (tay có đang "di chuyển" / "giữ"?)
   → phân biệt tay động và tay tĩnh
        │
        ▼
3. State machine eval
   → so sánh active_hand + zone + dwell_time với step hiện tại
        │
        ▼
4. Cập nhật state (current_step_idx, hit_count, …)
        │
        ▼
5. Trả về status
   {
     "sop_status": "in_progress" | "idle" | "violation" | "complete",
     "current_step": 2,
     "progress_percent": 50,
     "step_label": "Đặt slider vào bàn giữa",
     "violation_type": null | "skip_step" | "wrong_zone" | ...,
     "hit_count": 1
   }
```

---

## Cấu trúc 1 Engine file

Mỗi file trong `core/engines/<product>_engine.py` **bắt buộc** có 1 class tên `ProductEngine` (xem `loader.py`):

```python
from projects.sop_monitoring.core.engines.base_engine import BaseEngine

class ProductEngine(BaseEngine):
    def __init__(self, config: dict):
        super().__init__(config)
        self.zones = config["zones"]
        self.steps = config["steps"]
        self.current_step_idx = 0
        self.hit_count = 0
        self.is_failed = False
        # ... khởi tạo state khác

    def update(self, hands_data, products_data=None):
        # Logic FSM ở đây
        # Trả về dict status
        return {
            "sop_status": "in_progress",
            "current_step": self.current_step_idx,
            ...
        }

    def reset(self):
        self.current_step_idx = 0
        self.hit_count = 0
        self.is_failed = False

    def get_status(self):
        return {...}
```

---

## Các tham số tune được trong file SOP

```yaml
config:
  violation_tolerance: 5          # số frame bỏ qua trước khi coi là vi phạm
  idle_timeout_frames: 120        # frame không có tay → idle
  transition_timeout_sec: 25.0    # thời gian tối đa cho 1 step
  min_step_dwell_sec: 0.4         # dwell time tối thiểu
  restart_allowed_until_step: 0   # 0 = không cho restart giữa chừng
  freeze_on_two_hands: false      # có tạm dừng khi 2 tay đứng yên không
  freeze_cooldown_sec: 1.5
  active_hand_velocity_threshold: 0.012   # tay dưới ngưỡng này coi như "giữ"
```

---

## Vẽ zone bằng tool

```bash
python shared/tools/capture_snapshot.py    # chụp ảnh từ camera
python shared/tools/zone_selector.py       # mở GUI, click các điểm → ra polygon
```

Output là block `zones:` trong YAML — copy vào file SOP.

---

## Tổng kết 1 trang

| Cần gì | File | Sửa khi nào |
|---|---|---|
| Danh sách zone | `projects/sop_monitoring/config/<product>.yaml` | Camera thay đổi góc / đổi bàn |
| Danh sách step | cùng file | SOP cập nhật |
| Logic xử lý | `core/engines/<product>_engine.py` | Có yêu cầu SOP mới |
| Vẽ zone | `shared/tools/zone_selector.py` | Cần định nghĩa zone mới |
| Đăng ký sản phẩm | `core/engines/loader.py` (đã tự động theo tên file) | Không cần — chỉ cần file mới tồn tại |

---

## Bài tập nhỏ (1 giờ)

Làm theo từng bước trong [05_ADD_NEW_CAMERA.md](05_ADD_NEW_CAMERA.md) để thêm 1 sản phẩm giả lập `test_product`.

---

**Tiếp theo:** [05_ADD_NEW_CAMERA.md](05_ADD_NEW_CAMERA.md) — bài tập thêm camera mới, thực hành tất cả những gì đã học.
