# Hướng dẫn Git: máy local và server Ubuntu

Repo công ty: https://github.com/htmp-it/sop

- **Máy local**: nơi sửa code và đưa thay đổi lên Git.
- **Máy Ubuntu**: server lấy code từ nhánh `main` của Git công ty.
- **Git cá nhân**: remote `origin` (`https://github.com/AnhMinhh12/sop`).
- **Git công ty**: remote `company`, gồm nhánh làm việc `minh` và nhánh chính `main`.

Kiểm tra tên và địa chỉ remote trên từng máy bằng `git remote -v`. Các remote không tự đồng bộ với nhau.

## 1. Tạo nhánh `minh` trên máy local (một lần)

Kiểm tra `git status` và lưu hoặc commit thay đổi trước khi chuyển nhánh. Nếu `company` chưa có, thêm remote: `git remote add company https://github.com/htmp-it/sop.git`.

```bash
git switch main
git pull company main
git switch -c minh
git push -u company minh
```

Nếu nhánh đã tồn tại trên GitHub nhưng chưa có trên máy:

```bash
git fetch company
git switch --track company/minh
```

## 2. Cập nhật `main` vào nhánh của mình

Trên máy local, thực hiện trước khi sửa code hoặc khi muốn lấy thay đổi mới từ `main`. Commit hoặc cất tạm (`git stash`) các thay đổi đang làm trước.

```bash
git switch minh
git fetch company
git merge company/main
```

Nếu có conflict, sửa các file bị xung đột, chạy `git add <ten-file>` rồi `git commit` để hoàn tất merge. Sau đó chạy `git push company minh` nếu muốn cập nhật nhánh trên GitHub. Việc này **chưa đưa code lên `main`**.

## 3. Sửa code và đưa lên `main`

Trên máy local, ở nhánh `minh`, sửa code rồi kiểm tra và commit:

```bash
git status
git add .
git commit -m "Update code"
git push company minh
```

Chỉ dùng `git add .` sau khi kiểm tra các file cần đưa vào commit. Lệnh push trên chỉ đưa code lên nhánh `minh`, **chưa lên `main`**.

Để đưa code lên `main`, vào [GitHub công ty](https://github.com/htmp-it/sop/pull/new/minh), tạo Pull Request với **base: `main`**, **compare: `minh`**. Sau khi kiểm tra và đáp ứng yêu cầu review của repo, chọn **Merge pull request** → **Confirm merge**. Khi PR được merge, code mới có trên `main`.

### Ví dụ: đồng nghiệp merge trước, mình merge sau

1. Đồng nghiệp sửa trên nhánh riêng và merge Pull Request của họ vào `main`.
2. Bạn đã sửa trên nhánh `minh`: commit thay đổi của mình, rồi lấy `main` mới vào nhánh:

   ```bash
   git switch minh
   git add .
   git commit -m "Update code"
   git fetch company
   git merge company/main
   ```

   Kiểm tra `git status` trước khi dùng `git add .`. Nếu đã commit hết thì bỏ qua hai lệnh `git add` và `git commit` đầu tiên.
3. Nếu có conflict, sửa các file xung đột, chạy `git add <ten-file>` rồi `git commit` để hoàn tất merge. Kiểm tra lại code của cả hai người.
4. Chạy `git push company minh`, sau đó tạo hoặc cập nhật Pull Request từ `minh` vào `main` và merge khi sẵn sàng. Nếu `main` tiếp tục thay đổi trước khi merge, cập nhật và kiểm tra lại khi cần.

## 4. Đẩy lên Git cá nhân (nếu cần)

Nếu được phép đưa code công ty lên Git cá nhân, trên máy local chạy:

```bash
git push origin minh
```

Lệnh này chỉ cập nhật nhánh `minh` trên Git cá nhân; Git công ty không tự cập nhật theo.

## 5. Cập nhật máy Ubuntu

Server nên chạy nhánh `main`. Kiểm tra `git status`; nếu có thay đổi trên server, lưu hoặc xử lý chúng trước khi pull.

```bash
git switch main
git pull company main
```

Trên máy Ubuntu, `company` cũng cần trỏ tới repo công ty. Nếu chưa có, thêm bằng `git remote add company https://github.com/htmp-it/sop.git`.

## 6. Lấy code về máy local

### Trường hợp 1: Máy mới tinh (chưa tải code về bao giờ)

Mở terminal tại thư mục muốn lưu dự án:

```bash
# 1. Clone từ repo công ty về máy
git clone https://github.com/htmp-it/sop.git AI_Monitoring_Hub
cd AI_Monitoring_Hub

# 2. Đổi remote mặc định 'origin' thành 'company' (đúng quy chuẩn tài liệu)
git remote rename origin company

# 3. Thêm Git cá nhân làm 'origin' (nếu cần dùng backup cá nhân)
git remote add origin https://github.com/AnhMinhh12/sop.git

# 4. Chuyển sang nhánh 'minh' để làm việc
git fetch company
git switch --track company/minh
```

### Trường hợp 2: Máy đã có sẵn dự án (cập nhật code mới nhất từ GitHub)

**Cách A: Kéo cập nhật từ nhánh `main` công ty vào nhánh `minh` của mình (khi đồng nghiệp vừa merge code mới)**
```bash
# Lưu hoặc commit thay đổi đang làm dở trước
git status
git add .
git commit -m "Luu tam thay doi"

# Kéo main mới nhất đắp vào nhánh minh
git switch minh
git fetch company
git merge company/main
```

**Cách B: Đồng bộ code của chính nhánh `minh` từ GitHub về máy (ví dụ vừa làm việc từ máy khác hoặc server push lên)**
```bash
git switch minh
git pull company minh
```

**Cách C: Đồng bộ nhánh `main` ở máy local cho bằng với `main` công ty**
```bash
git switch main
git pull company main
```
