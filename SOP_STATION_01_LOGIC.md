# HTMP SOP Monitoring - Station 01 Logic (Optimized)

Station 01 handles assembly, picking parts from mold/tables, and final check.

## SOP Sequence (9 Steps)

1.  **Lấy 2 SP từ khuôn**: Cần ghé vùng `mold`, sau đó chụm tay lấy sản phẩm.
2.  **Đặt SP vào bàn bên trái**: Di chuyển tay bất kỳ vào vùng `left_table`.
3.  **Lấy 2 Slider từ khuôn**: Cả 2 tay vào vùng `mold`.
4.  **Đặt Slider vào bàn giữa**: Cả 2 tay vào vùng `middle_table`.
5.  **Lắp Terminal vào Slider**: Giữ cả 2 tay tại `middle_table` trong 3 giây.
6.  **Đưa 2 Slider vào khuôn**: Cả 2 tay vào vùng `mold`.
7.  **Tay PHẢI bấm nút bên PHẢI**: Chỉ tay phải vào vùng `button_right`.
8.  **Lấy Jig & Sản phẩm**: Tay trái ở `left_table`, tay phải ở `middle_table`.
9.  **Check Jig & Hoàn thành**: Đưa ít nhất một tay vào vùng `jig_zone` (Bàn đỏ) trong **2 giây**. Chu kỳ tự động kết thúc.

## Logic Implementation
- **stay_in_zone**: Time-aware monitoring.
- **dual_task**: Simultaneous bimanual zone verification.
- **interaction**: Sequence-aware hand chụm (touching) detection.
