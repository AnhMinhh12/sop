# Hướng dẫn Git cho 2 người cùng phát triển dự án

## 1. Cấu trúc repository

Repo công ty: `https://github.com/htmp-it/sop`

```text
company (remote Git công ty)
├── main          # Nhánh chính, code đã kiểm tra
├── minh          # Nhánh làm việc của Minh
└── dongnghiep    # Nhánh làm việc của đồng nghiệp
```

- `origin`: remote GitHub cá nhân (`https://github.com/AnhMinhh12/sop`).
- `company`: remote GitHub công ty (`https://github.com/htmp-it/sop`).
- `main`, `minh`, `dongnghiep`: tên **branch**, không phải remote.

## 2. Thiết lập branch riêng (chỉ làm một lần)

Trước tiên kiểm tra trạng thái trên máy dev:

```bash
git status
git remote -v
```

Nếu đang có thay đổi chưa commit, hãy commit hoặc cất tạm bằng `git stash` trước khi tạo hoặc đổi nhánh:
```bash
git stash push -m "tam_cat_thay_doi"
```

Bạn có thể chọn **Cách 1** (nhanh và tiện nhất) hoặc **Cách 2**:

### Cách 1: Tạo branch từ máy dev rồi đẩy lên GitHub (Khuyên dùng)
Không cần phải lên web tạo trước:

```bash
# 1. Đảm bảo đang ở main và lấy code mới nhất về
git switch main
git pull company main

# 2. Tạo và chuyển sang branch riêng từ main
git switch -c minh

# 3. Đẩy branch lên GitHub công ty và đặt theo dõi mặc định
git push -u company minh
```

### Cách 2: Nếu đã tạo branch trên GitHub công ty trước đó
Nếu đã tạo nhánh trên giao diện web GitHub, bạn phải chạy lệnh `fetch` để máy tính cập nhật danh sách branch trước khi switch:

```bash
# 1. Tải thông tin các branch mới từ công ty về máy
git fetch company

# 2. Tạo local branch theo dõi remote branch đó
git switch --track company/minh
```

> [!WARNING]
> Nếu gõ `git switch --track company/minh` mà gặp lỗi:
> `fatal: invalid reference: company/minh`
> Lý do: Branch `minh` chưa tồn tại trên GitHub hoặc bạn chưa chạy `git fetch company`. Hãy dùng **Cách 1** ở trên để tạo trực tiếp từ máy.

Nếu sau này đã có sẵn branch `minh` trên máy, chỉ cần:
```bash
git switch minh
```

## 3. Quy trình làm việc hằng ngày

Trên **máy dev**, sửa code ở branch riêng, sau đó:

```bash
git switch minh
git status
git add .
git commit -m "Update code"
git push company minh
```

Đồng nghiệp thực hiện tương tự với branch của họ. Chỉ `git add .` khi đã kiểm tra các file được đưa vào commit.

## 4. Gộp code vào `main` bằng Pull Request

Sau khi `git push company minh`, bạn tạo Pull Request (PR) theo 1 trong 2 cách:

### Cách 1: Bấm trực tiếp vào link trong Terminal (Nhanh nhất - Khuyên dùng)
Mỗi khi bạn chạy `git push company minh`, GitHub sẽ tự động in ra đường link tạo PR ngay tại terminal, dạng:
```text
remote: Create a pull request for 'minh' on GitHub by visiting:
remote:      https://github.com/htmp-it/sop/pull/new/minh
```
👉 Bạn chỉ cần giữ phím **`Ctrl` và click chuột vào link đó**, trình duyệt sẽ mở thẳng form tạo PR với `base: main` và `compare: minh` đã được chọn sẵn.

### Cách 2: Tạo thủ công trên giao diện web GitHub
1. Vào repository trên GitHub: `https://github.com/htmp-it/sop`.
2. Vào tab **Pull requests → New pull request**.
3. Chọn:
   - **base**: `main`
   - **compare**: `minh`

---

### Sau khi mở trang tạo PR:
1. Nhấn **Create pull request**.
2. Đồng nghiệp có thể vào xem, review hoặc góp ý code.
3. Khi đã sẵn sàng, nhấn **Merge pull request** → **Confirm merge** để gộp code vào `main`.

> [!NOTE]
> Pull Request (PR) là yêu cầu gộp code giữa hai branch trên GitHub. Không bắt buộc phải có người Approve nếu repository chưa bật quy tắc bắt buộc phê duyệt. PR **không tự động xuất hiện** chỉ bằng việc `git push` mà bạn cần mở link/tạo PR như trên.

## 5. Đồng bộ branch riêng sau khi `main` đã được merge

Trên máy dev, khi không có thay đổi chưa commit:

```bash
git switch minh
git fetch company
git merge company/main
```

Nếu xảy ra conflict, xử lý các đoạn xung đột rồi hoàn tất merge. Sau đó có thể `git push company minh` để cập nhật branch từ xa.

## 6. Cập nhật code trên server Ubuntu

Server nên chạy code từ `company/main`, hạn chế sửa trực tiếp source trên server.

```bash
git switch main
git status
git pull company main
```

Nếu `git status` cho thấy file đã bị sửa trên server, **không pull ngay**. Có thể lưu tạm trước:

```bash
git stash push -m "Backup server changes before pull"
git pull company main
git stash apply
```

Kiểm tra `git status` và xử lý conflict nếu có. Dùng `stash apply` để vẫn giữ bản lưu tạm; chỉ `git stash drop` khi đã xác nhận mọi thứ ổn.

## 7. Bảng lệnh nhanh

| Công việc | Lệnh |
|---|---|
| Xem branch hiện tại | `git branch` |
| Xem trạng thái file | `git status` |
| Xem remote | `git remote -v` |
| Chuyển sang branch của mình | `git switch minh` |
| Commit thay đổi | `git add .` rồi `git commit -m "Update"` |
| Push lên Git công ty | `git push company minh` |
| Lấy thông tin mới từ công ty | `git fetch company` |
| Đồng bộ `main` vào branch riêng | `git merge company/main` |
| Pull code `main` về server | `git pull company main` |

## 8. Ghi nhớ

**Sửa code trên branch riêng → Commit → Push → Tạo Pull Request → Review (nếu cần) → Merge vào `main` → Cập nhật server.**

Hai repo `origin` và `company` không tự đồng bộ với nhau. Chỉ đẩy source code công ty lên GitHub cá nhân nếu chính sách công ty cho phép.
