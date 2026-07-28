# docs/ — Tài liệu dự án

```
docs/
├── README.md                      ← file này
├── ONBOARDING/                    ← bộ tài liệu cho người mới (đọc theo thứ tự)
│   ├── 00_README.md               ← index + lộ trình đọc
│   ├── 01_PROJECT_OVERVIEW.md     ← kiến trúc, luồng dữ liệu
│   ├── 02_SETUP_AND_RUN.md        ← cài đặt & chạy Hub
│   ├── 03_CODE_TOUR.md            ← đi 1 vòng code
│   ├── 04_SOP_ENGINE_GUIDE.md     ← FSM, zones, steps
│   ├── 05_ADD_NEW_CAMERA.md       ← bài tập thêm máy
│   ├── 06_WORK_PER_MACHINE.md     ← phân chia công việc
│   ├── 07_GIT_AND_PR.md           ← quy trình git
│   ├── 08_TROUBLESHOOTING.md      ← lỗi thường gặp
│   └── 09_CHECKLIST_PER_MACHINE.md
└── machines/                      ← hồ sơ từng máy
    ├── README.md
    └── machine_TEMPLATE.md        ← copy ra thành machine_<id>.md
```

## Đối tượng đọc

| Bạn là | Đọc |
|---|---|
| Người mới vào team | Toàn bộ `ONBOARDING/00 → 09`, bắt đầu từ ngày 1 |
| Đã onboard rồi, cần tra cứu | Dùng `08_TROUBLESHOOTING.md` + file `machine_<id>.md` của máy liên quan |
| Muốn thêm máy mới | `09_CHECKLIST_PER_MACHINE.md` + `05_ADD_NEW_CAMERA.md` |
| Cần hiểu kiến trúc | `01_PROJECT_OVERVIEW.md` |

## Liên kết tài liệu đã có trong repo

- [README.md](../README.md) — README dự án chính.
- [../projects/sop_monitoring/docs/READING_ORDER.md](../projects/sop_monitoring/docs/READING_ORDER.md) — thứ tự đọc code (dành cho người quen rồi).
- [../projects/sop_monitoring/docs/RULES.md](../projects/sop_monitoring/docs/RULES.md) — quy chuẩn kỹ thuật bắt buộc.
- [../distributed_setup_guide.md](../distributed_setup_guide.md) — hướng dẫn triển khai Edge chi tiết.
