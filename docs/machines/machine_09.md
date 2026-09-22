# Machine 09 — KOR-H2110

| Item | Value |
|---|---|
| Machine ID | `machine_09` |
| Product code | `KOR-H2110` |
| Model | `shared/models/yolo/KOR-H2110.onnx` |
| Mode | Edge client → Hub |

## SOP

1. Lấy 4 sản phẩm ra khỏi khuôn.
2. Lắp 4 terminal vào khuôn.
3. Bấm nút bên phải.

## Before enabling monitoring

Draw and save the `mold` and `button_right` ROIs in
`projects/sop_monitoring/config/KOR-H2110.yaml` from a current Machine 9 camera frame.
