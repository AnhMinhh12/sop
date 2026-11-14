# 🐳 Sổ Tay Các Lệnh Thao Tác Docker Tiêu Biểu (Docker Operational Guide)

Tài liệu tổng hợp các lệnh thao tác Docker và Docker Compose thường dùng nhất cho việc vận hành, bảo trì và xử lý sự cố hệ thống **AI Monitoring Hub**.

---

## 📑 Mục lục
1. [Quản trị Dự án bằng Docker Compose](#1-quản-trị-dự-án-bằng-docker-compose-thường-dùng-nhất)
2. [Quản lý Container (Docker CLI)](#2-quản-lý-container-docker-cli)
3. [Quản lý Image (Hình ảnh Docker)](#3-quản-lý-image-hình-ảnh-docker)
4. [Kiểm tra Tài nguyên & Hiệu năng](#4-kiểm-tra-tài-nguyên--hiệu-năng)
5. [Dọn dẹp Bộ nhớ & Giải phóng Ổ đĩa](#5-dọn-dẹp-bộ-nhớ--giải-phóng-ổ-đĩa)
6. [Xử lý Sự cố Thường gặp (Troubleshooting)](#6-xử-lý-sự-cố-thường-gặp-troubleshooting)

---

## 1. Quản trị Dự án bằng Docker Compose (Thường dùng nhất)

Chạy các lệnh này tại thư mục gốc của dự án: `/home/admin/AI_Monitoring_Hub`

### 🚀 Khởi động & Dừng dịch vụ

```bash
# Khởi chạy toàn bộ hệ thống dưới dạng tiến trình nền (Daemon/Service)
docker compose up -d

# Xem log khởi động ngay lập tức (không chạy nền)
docker compose up

# Dừng và gỡ bỏ container của dự án
docker compose down

# Dừng tạm thời container (không xóa container)
docker compose stop

# Tiếp tục chạy container đã dừng
docker compose start

# Khởi động lại dịch vụ (Reload sau khi sửa file config hoặc .env)
docker compose restart
```

### 📋 Xem Log & Trạng thái

```bash
# Xem log trực tiếp theo thời gian thực (nhấn Ctrl+C để thoát)
docker compose logs -f

# Xem 100 dòng log gần nhất và theo dõi tiếp
docker compose logs -f --tail=100

# Kiểm tra trạng thái hoạt động của container
docker compose ps
```

### 🔄 Cập nhật Code & Rebuild Image

```bash
# Khi bạn chỉnh sửa code Python hoặc cài thêm thư viện vào requirements.txt:
docker compose build

# Rebuild và khởi động lại container mới ngay lập tức
docker compose up -d --build
```

### 💻 Truy cập Terminal bên trong Container

```bash
# Mở một phiên bash bên trong container đang chạy để kiểm tra file/thư viện
docker compose exec ai-monitoring bash

# Chạy trực tiếp một lệnh Python bên trong container
docker compose exec ai-monitoring python -c "import onnxruntime; print(onnxruntime.__version__)"
```

---

## 2. Quản lý Container (Docker CLI)

Dùng khi muốn thao tác trực tiếp với container qua Docker engine:

| Thao tác | Câu lệnh | Giải thích |
| :--- | :--- | :--- |
| **Xem container đang chạy** | `docker ps` | Hiển thị ID, tên, cổng, trạng thái |
| **Xem toàn bộ container** | `docker ps -a` | Hiển thị cả các container đã dừng/bị lỗi |
| **Xem log container cụ thể** | `docker logs -f ai_monitoring_hub` | Theo dõi luồng log của container |
| **Xem 50 dòng log cuối** | `docker logs --tail 50 ai_monitoring_hub` | Tra cứu nhanh lỗi vừa xảy ra |
| **Khởi động lại** | `docker restart ai_monitoring_hub` | Tương đương restart Windows Service |
| **Dừng container** | `docker stop ai_monitoring_hub` | Dừng an toàn (gửi tín hiệu SIGTERM) |
| **Dừng khẩn cấp** | `docker kill ai_monitoring_hub` | Ép tắt ngay lập tức (SIGKILL) |
| **Xóa container** | `docker rm ai_monitoring_hub` | Xóa container (phải dừng trước khi xóa) |

---

## 3. Quản lý Image (Hình ảnh Docker)

| Thao tác | Câu lệnh | Giải thích |
| :--- | :--- | :--- |
| **Danh sách Images** | `docker images` | Xem dung lượng, tag và ID của các image trên máy |
| **Xóa Image cụ thể** | `docker rmi ai_monitoring_hub:latest` | Xóa image khi không còn container nào dùng |
| **Build image độc lập** | `docker build -t ai_monitoring_hub:latest .` | Build trực tiếp từ `Dockerfile` |

---

## 4. Kiểm tra Tài nguyên & Hiệu năng

Đối với hệ thống AI chạy liên tục và xử lý nhiều camera, việc giám sát tài nguyên rất quan trọng:

```bash
# Xem mức sử dụng CPU, RAM, Network I/O thời gian thực của container
docker stats ai_monitoring_hub

# Xem tất cả container cùng lúc
docker stats --no-stream
```

> [!TIP]
> Nếu thấy CPU tăng quá cao (>90%), hãy kiểm tra các biến môi trường sau trong file `.env`:
> - `AI_MAX_THREADS`: Số luồng tối đa cho inference (khuyến nghị: 4)
> - `AI_FPS_CAP`: Giới hạn FPS phân tích hình ảnh (khuyến nghị: 10 - 15)
> - `OMP_NUM_THREADS=1` và `MKL_NUM_THREADS=1`

---

## 5. Dọn dẹp Bộ nhớ & Giải phóng Ổ đĩa

Khi làm việc với Docker lâu ngày, cache build và image cũ có thể chiếm dụng nhiều dung lượng:

```bash
# Xem dung lượng Docker đang chiếm dụng trên ổ cứng
docker system df

# Dọn dẹp build cache thừa (an toàn, không ảnh hưởng container đang chạy)
docker builder prune -f

# Xóa các image "dangling" (image cũ bị mất tag sau khi build lại)
docker image prune -f

# DỌN DẸP TOÀN BỘ (Chỉ chạy khi cần giải phóng tối đa bộ nhớ):
# Xóa toàn bộ container đã tắt, mạng không dùng và cache
docker system prune -f
```

---

## 6. Xử lý Sự cố Thường gặp (Troubleshooting)

### 🔴 Sự cố 1: Container bị tắt ngay sau khi chạy (`Exited (1)`)
- **Cách kiểm tra:**
  ```bash
  docker logs --tail 100 ai_monitoring_hub
  ```
- **Nguyên nhân phổ biến:**
  1. Sai cú pháp file `config/config.yaml` hoặc thiếu biến môi trường trong `.env`.
  2. Xung đột cổng: Cổng Web (`4000` hoặc `5001`) đang bị một tiến trình khác trên máy chiếm dụng.
     - Kiểm tra cổng: `ss -tuln | grep -E "4000|5001"`

### 🔴 Sự cố 2: Không bắt được luồng RTSP từ Camera
- **Cách kiểm tra từ bên trong container:**
  ```bash
  # Vào bên trong container kiểm tra ping đến camera:
  docker compose exec ai-monitoring ping -c 3 10.0.7.210
  
  # Hoặc kiểm tra kết nối cổng RTSP 554:
  docker compose exec ai-monitoring curl -v -m 3 telnet://10.0.7.210:554
  ```
- **Khắc phục:** Đảm bảo `network_mode: host` luôn được bật trong `docker-compose.yml` để container nhận diện đầy đủ card mạng của máy chủ.

### 🔴 Sự cố 3: Lỗi quyền ghi dữ liệu (Permission Denied) ở `data/`
- Nếu container báo lỗi không ghi được clip vi phạm hoặc log:
  ```bash
  sudo chown -R admin:admin data/
  chmod -R 775 data/
  ```

### 🔴 Sự cố 4: Chỉnh sửa cấu hình nhưng container không nhận
- Vì file `.env`, `config/config.yaml` đã được mount trực tiếp vào container, khi sửa file xong bạn chỉ cần restart container mà **không cần build lại image**:
  ```bash
  docker compose restart
  ```

