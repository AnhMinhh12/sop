# 08 — Troubleshooting: Lỗi thường gặp & cách xử lý

---

## Bảng tra nhanh

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `ModuleNotFoundError: No module named 'onnxruntime'` | Chưa cài requirements | `pip install -r requirements.txt` |
| `[ERROR] Failed to load config.yaml` | File YAML sai indent / tab | Mở bằng editor hiển thị whitespace, đổi tab → space |
| `pymysql.err.OperationalError: (2003, ...)` | MySQL chưa chạy hoặc sai host | Kiểm tra `.env`, chạy `mysql --user=... --password=... -e 'SHOW DATABASES'` |
| Camera hiển thị "offline" trên dashboard | Không có Edge push / mất kết nối | Kiểm tra Edge log, gõ `curl` test trực tiếp Hub |
| `RTSP` không mở được | URL sai, firewall, codec | Test URL trong VLC |
| Hub log spam `Push failed, consecutive errors: 5` | Edge mất kết nối Hub | Kiểm tra network, restart Edge |
| Camera bị "đứng hình" | RTSP reconnect chưa trigger | Restart camera hoặc `rtsp_manager` retry |
| Vi phạm bắn loạn | Zone vẽ sai / threshold không hợp | Mở `zone_selector.py`, vẽ lại; review `min_dwell_sec` |
| `403` từ Hub | `X-API-Key` không khớp | Sửa `api_key` cho khớp giữa Hub và Edge |
| `KeyError: 'product_id'` | Engine class không tên `ProductEngine` | Sửa tên class theo đúng |
| `ImportError: cannot import name 'ProductEngine'` | Tên file engine không khớp `<id>_engine.py` | Đổi tên file theo product_id |
| Hub log full `OMP warning` | ENV chưa đặt | Đã set trong `main.py`, nếu vẫn báo thì kiểm tra phiên bản numpy |
| `Latency > 1s` | Disk đầy / model quá nặng | Xem [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md), giảm input size |

---

## Chi tiết 5 lỗi hay gặp nhất

### 1. Camera hiển thị "offline"

**Triệu chứng:** Trên dashboard `/sop`, ô camera báo "offline" hoặc trắng.

**Cách debug:**

```bash
# Bước 1: kiểm tra Edge còn chạy không
ssh edge-minipc "ps aux | grep edge_client"

# Bước 2: xem log Edge
ssh edge-minipc "tail -100 /path/to/system.log"

# Bước 3: thử push frame thủ công từ chính máy Hub
curl -X POST http://localhost:5001/api/station/machine_07/push_frame \
  -H "X-API-Key: <api_key>" \
  -F "image=@test.jpg" \
  -F "status={\"sop_status\":\"idle\"}" \
  -F "hands=[]"
```

Nếu lệnh curl trả `{"success": true}` → Hub OK, vấn đề ở Edge. Nếu trả timeout → Hub hoặc network.

### 2. RTSP không kết nối

**Triệu chứng:** Log `Cannot open RTSP stream` hoặc `camera_status: error`.

**Cách debug:**

```bash
# Test URL RTSP
ffplay "rtsp://user:pass@ip:554/Streaming/Channels/101"

# Hoặc dùng Python
python -c "import cv2; print(cv2.VideoCapture('rtsp://...').isOpened())"
```

Nguyên nhân thường gặp:
- Sai `user:password` (lưu ý ký tự đặc biệt phải URL-encode, ví dụ `@` → `%40`).
- Camera chưa bật RTSP trong phần cài đặt.
- Firewall chặn port 554 trên máy.

### 3. Vi phạm bắn loạn (false positive)

**Triệu chứng:** Hệ thống báo vi phạm liên tục dù công nhân làm đúng.

**Checklist:**

1. Vẽ lại zone — thường do zone quá rộng hoặc polygon bị ngược.
   ```bash
   python shared/tools/zone_selector.py
   ```
2. Tăng `min_dwell_sec` (từ 0.3 lên 0.6).
3. Tăng `violation_tolerance` (số frame sai trước khi coi là vi phạm).
4. Kiểm tra class `hand` vs `product` của YOLO — đảm bảo model không nhận nhầm.

### 4. Lỗi YOLO load model

**Triệu chứng:** `onnxruntime.capi.onnxruntime_pybind11_state.Fail: [ONNXRuntimeError]`.

**Cách debug:**

```python
import onnxruntime as ort
sess = ort.InferenceSession("shared/models/yolo/laprap.onnx")
print(sess.get_inputs())    # xem input
print(sess.get_outputs())   # xem output
```

Lỗi thường gặp:
- File ONNX bị hỏng khi copy (re-download hoặc copy lại).
- Phiên bản onnxruntime không tương thích (cài lại đúng phiên bản CPU).

### 5. Database không ghi được

**Triệu chứng:** Log `Lost connection to MySQL` hoặc vi phạm không xuất hiện trong trang `/history`.

**Cách debug:**

```bash
# Kết nối thử
mysql -h 127.0.0.1 -u your_user -p

# Kiểm tra table
mysql> USE ai_system;
mysql> SHOW TABLES;
mysql> SELECT COUNT(*) FROM sop_events;
```

Nguyên nhân:
- Connection pool đầy (giảm `num_threads`).
- Schema chưa được tạo — chạy lại Hub lần đầu để auto-create.
- Ổ đĩa DB đầy → `DiskMonitor` (`shared/services/disk_monitor.py`) không cho ghi.

---

## Khi nào cần hỏi người khác

| Câu hỏi | Hỏi ai |
|---|---|
| Camera nào cần thêm, SOP mới? | Sếp / leader |
| YOLO model class, dataset? | Người train model (hiện có thể bạn đang lo) |
| MySQL config, port? | Team hạ tầng |
| Logic SOP đúng hay sai? | Owner máy đó + công nhân vận hành |

---

## Checklist khi báo lỗi cho người khác

Gửi kèm:
1. **Camera ID** liên quan.
2. **Log** (khoảng 20–30 dòng quanh lúc lỗi).
3. **Bước tái hiện** (làm gì → thấy gì).
4. **Kết quả mong đợi** vs **thực tế**.
5. **Đã thử gì** rồi.

Không gửi: chỉ "nó bị lỗi" — thiếu thông tin sẽ tốn thời gian cả 2 bên.

---

**Tiếp theo:** [09_CHECKLIST_PER_MACHINE.md](09_CHECKLIST_PER_MACHINE.md) — checklist dùng mỗi khi nhận máy mới.
