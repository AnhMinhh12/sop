# 07 — Git & PR: Quy trình làm việc nhóm

---

## Tổng quan

| Quy tắc | Mục đích |
|---|---|
| 1 branch / 1 thay đổi | Dễ review, dễ rollback |
| Tên branch có prefix (`feature/`, `fix/`, `edge/`, `hub/`) | Đọc là biết đang làm gì |
| Không commit trực tiếp vào `main` | Tránh break hệ thống đang chạy |
| PR phải có 1 người review | Bắt bug, chia sẻ kiến thức |
| Merge bằng squash hoặc merge commit | Lịch sử dễ đọc |

---

## Quy trình 1 task

```
1. git checkout main
2. git pull
3. git checkout -b feature/<short-desc>     # tạo branch mới
4. ... sửa code ...
5. git add <files>
6. git commit -m "feat: <mô tả ngắn>"
7. git push origin feature/<short-desc>
8. Tạo PR trên GitHub
9. Chờ review
10. Merge sau khi approved
11. Xóa branch
```

---

## Tên branch theo concern

| Prefix | Khi nào | Ví dụ |
|---|---|---|
| `feature/` | Thêm tính năng mới | `feature/machine-09-init` |
| `fix/` | Sửa bug | `fix/laprap-step3-false-positive` |
| `edge/` | Sửa Edge client | `edge/auto-reconnect` |
| `hub/` | Sửa Hub | `hub/edge-dashboard` |
| `sop/` | Sửa logic SOP / engine | `sop/tff4040-rewrite-step5` |
| `docs/` | Chỉ thay đổi tài liệu | `docs/onboarding-guide` |
| `refactor/` | Refactor không đổi behavior | `refactor/cleanup-old-scratch` |

---

## Commit message

Convention `<type>: <message>`:

| Type | Dùng khi |
|---|---|
| `feat:` | Thêm feature |
| `fix:` | Sửa bug |
| `refactor:` | Refactor code |
| `docs:` | Chỉ thay đổi tài liệu |
| `test:` | Thêm/sửa test |
| `chore:` | Build, CI, dependency |

Ví dụ:
```
feat(machine_07): add zone for jig_area
fix(laprap): false positive on step 3 when hand dwells > 2s
refactor(buffer): simplify FrameRingBuffer.push
docs(onboarding): add 06-work-per-machine.md
```

Co-author (nếu làm chung):
```
feat: add edge auto-reconnect

Sử dụng backoff 5s với tối đa 10 retry.

Co-authored-by: Nguyễn Văn B <b@congty.com>
```

---

## Phân vùng file để 2 người không conflict

Vì mỗi owner phụ trách 1 máy, mỗi người sửa file **khác nhau** cho phần lớn task:

| Owner | Files chủ yếu đụng |
|---|---|
| Owner máy 7 | `projects/sop_monitoring/config/TFF4040.yaml`, `core/engines/TFF4040_engine.py`, `docs/machines/machine_07.md` |
| Owner máy 8 | `projects/sop_monitoring/config/laprap.yaml`, `core/engines/laprap_engine.py`, `docs/machines/machine_08.md` |

**File hay conflict nhất: `config/config.yaml`** (vì cả 2 cùng sửa khi thêm camera).
Giải pháp: chỉ 1 người sửa 1 lúc. Trước khi sửa → báo lên group chat.

---

## Review PR

Khi review, kiểm tra:
- [ ] Code chạy được (clone branch về test thử).
- [ ] Không hardcode (IP, password, threshold vào code).
- [ ] Có log INFO/WARNING/ERROR hợp lý.
- [ ] Không có file debug lẫn vào commit (`__pycache__`, `test.py`, ...).
- [ ] Nếu liên quan SOP: đã test với video file.
- [ ] Không sửa file SOP của máy người khác (trừ khi review và họ đồng ý).

Khi comment, dùng prefix:
- `nit:` — góp ý nhỏ, không bắt buộc sửa.
- `question:` — hỏi để hiểu thêm.
- `blocking:` — phải sửa trước khi merge.

---

## Quy tắc bảo vệ file nhạy cảm

Các file **KHÔNG** được commit:
- `.env` — chứa password DB, IP nội bộ.
- `*.onnx` mới train nếu > 50MB — dùng Git LFS hoặc chia sẻ qua mạng nội bộ.
- File video mẫu lớn (> 100MB).
- `__pycache__/`, `.vscode/`, `.idea/`.

Đảm bảo `.gitignore` đã có:
```
.env
__pycache__/
*.pyc
data/violations/
data/logs/
.venv/
.vscode/
.idea/
```

---

## Ví dụ 1 PR hoàn chỉnh

PR title: `feat(machine_07): add jig_zone with stay_in_zone logic 3s`

PR body:
```
## Mục đích
Thêm step "check jig" vào SOP máy 7, yêu cầu tay ở jig_zone tối thiểu 3 giây.

## Test
- [x] Test trên video mẫu 5 phút: 100% step match
- [ ] Test với RTSP thật (chưa, máy bận)
- [x] Không ảnh hưởng các step khác

## Ảnh hưởng
- `projects/sop_monitoring/config/TFF4040.yaml`: thêm `jig_zone` + step mới.
- `core/engines/TFF4040_engine.py`: handle step mới + transition.
- Không sửa file dùng chung.

## Ảnh overlay
<đính kèm ảnh có vẽ zone mới>
```

---

## Khi cần revert nhanh

```bash
git revert <commit-hash>     # tạo commit đảo ngược
git push origin main
```

Hoặc revert 1 PR đã merge: trên GitHub → Revert button.

---

## Câu hỏi thường gặp

**Hỏi:** Sửa typo README có cần PR không?
**Đáp:** Có, nhưng 1 commit nhỏ trong branch `docs/fix-typo-...` là được.

**Hỏi:** Đang làm dở thì có máy mới gấp phải chuyển sang?
**Đáp:** Commit những gì đã xong trước, push branch lên (dù chưa review), rồi checkout branch khác.

**Hỏi:** 2 người cùng sửa `core/engines/loader.py`?
**Đáp:** File đó gần như không sửa, vì loader đã động. Cần thêm helper thì PR chung, cả 2 review.

---

**Tiếp theo:** [08_TROUBLESHOOTING.md](08_TROUBLESHOOTING.md) — lỗi thường gặp và cách xử lý.
