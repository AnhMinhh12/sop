# Tài liệu Chi tiết Quy trình SOP - Trạm 01
**Hệ thống:** HTMP SOP Monitoring
**Trạm:** Station 01 - Lắp & Check Jig
**Phiên bản logic:** 2.0 (Spatial Logic - Bimanual)

---

## 1. Danh sách 10 Bước SOP

| Bước | Tên hành động | Logic kiểm tra | Vùng quy định | Yêu cầu tay | Điều kiện hoàn thành |
|:---:|:---|:---|:---|:---:|:---|
| **1** | Lấy 2 SP từ khuôn | `interaction` | `mold` | 2 tay | Lấy SP và gộp tay rời khuôn |
| **2** | Đặt SP vào bàn bên trái | `zone_trigger` | `left_table` | Bất kỳ | Đặt sản phẩm vào bàn trái |
| **3** | Lấy 2 Slider từ khuôn | `zone_trigger` | `mold` | 2 tay | Cả 2 tay cùng thò vào khuôn |
| **4** | Đặt Slider vào bàn giữa | `zone_trigger` | `middle_table` | 2 tay | Cả 2 tay cùng đưa Slider về bàn giữa |
| **5** | Lắp Terminal vào Slider | `stay_in_zone` | `middle_table` | 2 tay | Duy trì 2 tay tại bàn giữa 3 giây |
| **6** | Đưa 2 Slider vào khuôn | `zone_trigger` | `mold` | 2 tay | Cả 2 tay cùng đưa slider vào khuôn |
| **7** | Tay PHẢI bấm nút PHẢI | `zone_trigger` | `button_right` | Tay Phải | Chỉ tay phải chạm vùng Nút bấm |
| **8** | Lấy Jig & Sản phẩm | `dual_task` | `left_table` & `middle_table` | 2 tay | Lấy cả 2 thứ (thứ tự tùy ý) |
| **9** | Check Jig | `interaction` | `jig_zone` | 2 tay | 2 tay chạm nhau trong vùng Jig 1.5 giây |
| **10** | Trả Jig & Sản phẩm về vị trí | `dual_task` | `middle_table` & `left_table` | 2 tay | Trả 2 vật về vị trí cũ (thứ tự tùy ý) |

---

## 2. Giải thích các loại Logic (Dành cho quản lý)

### 🧩 `interaction` (Tương tác/Gộp tay)
Máy sẽ tính toán khoảng cách giữa 2 tâm bàn tay. Nếu khoảng cách này nhỏ hơn 12% chiều rộng màn hình, máy coi như 2 tay đang chạm nhau hoặc đang gộp sản phẩm. Bước này cực kỳ nhạy để bắt các hành động lắp ráp nhỏ.

### 🛤️ `sync_move` (Di chuyển đồng bộ)
Yêu cầu cả 2 tay phải đi đúng lộ trình. Ví dụ: Nếu tay trái đi từ Khuôn sang Bàn, nhưng tay phải lại bỏ đi chỗ khác, máy sẽ coi là sai thao tác.

### ⏱️ `stay_in_zone` (Hành động duy trì)
Dùng để bắt các bước cần thời gian thực hiện (như lắp terminal, xoáy vít). Nếu công nhân chỉ quẹt tay qua vùng rồi rút ra ngay, máy sẽ không công nhận bước đó.

### 🎯 `zone_trigger` (Kích hoạt điểm)
Dùng cho các hành động đơn giản bằng 1 tay như bấm nút, lấy linh kiện đơn lẻ.

---

## 3. Cấu hình vùng ROI (Tọa độ Virtual)
Mọi tọa độ vùng (Polygon) đều được chuẩn hóa về thang `0.0` đến `1.0`. Nếu bạn thay đổi góc camera, chỉ cần chạy `tools/zone_selector.py` để lấy lại tọa độ mới và dán vào file cấu hình.

---
**Ghi chú:** Nếu có bất kỳ bước nào báo lỗi oan hoặc quá nhạy, hãy điều chỉnh thông số `violation_tolerance` trong file cấu hình.
