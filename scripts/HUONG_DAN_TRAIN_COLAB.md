# Hướng dẫn Retrain Model TFF4040 trên Google Colab

> File này hướng dẫn từng bước để retrain model sau khi đã gán nhãn xong dữ liệu.

## Tổng quan quy trình

```
[1] Gán nhãn (Roboflow/LabelImg)  →  [2] Export YOLOv8  →  [3] Upload Drive
                                                                    ↓
[6] Deploy & verify ← [5] Download ONNX ← [4] Train Colab (10-20 phút)
```

---

## Bước 1: Gán nhãn xong (công việc của bạn)

Bạn tự gán nhãn trên Roboflow hoặc LabelImg. Cần đảm bảo:

- **3 classes**: `hand` (0), `robot` (1), `sp` (2)
- **Phạm vi gán nhãn**:
  - `hand`: tay ở mọi vị trí (kể cả khi không cầm gì)
  - `robot`: gán ở **mọi frame robot xuất hiện** trong video (kể cả khi chỉ lộ một phần, đang kéo ra, đang thò vào)
  - `sp`: chỉ gán khi **sản phẩm đang ở trong khuôn** (kể cả khi robot đang gắp). KHÔNG gán khi sản phẩm ở tay, trong thùng, ngoài khuôn.

### Số lượng ảnh tối thiểu khuyến nghị

| Class | Số ảnh tối thiểu | Số ảnh lý tưởng |
|-------|-------------------|------------------|
| `hand` | 400 | 700+ (đã có) |
| `robot` | 300 | 500+ |
| `sp` | 200 | 400+ |

Nếu dataset nhỏ hơn, model vẫn train được nhưng accuracy sẽ kém hơn.

---

## Bước 2: Export dataset từ Roboflow

Trong Roboflow, sau khi label xong:

1. Vào **Generate** → chọn version mới
2. Preprocessing: resize về **640x640** (Stretch)
3. Augmentation: **OFF** (để script Colab tự lo)
4. Chọn format: **YOLOv8**
5. Click **Generate** → Download zip về máy

Hoặc nếu dùng LabelImg thủ công:
- Tự tạo folder `train/images/`, `train/labels/`, `valid/images/`, `valid/labels/`
- Tạo file `data.yaml` theo mẫu bên dưới
- Nén zip

### Cấu trúc dataset YOLOv8 cần có:

```
tff4040.yolov8/
├── data.yaml
├── train/
│   ├── images/   *.jpg
│   └── labels/   *.txt
└── valid/
    ├── images/   *.jpg
    └── labels/   *.txt
```

### File `data.yaml` mẫu:

```yaml
path: /content/drive/MyDrive/tff4040.yolov8
train: train/images
val: valid/images

names:
  0: hand
  1: robot
  2: sp
```

> ⚠️ Nếu export từ Roboflow, file `data.yaml` đã tự generate, không cần sửa.

---

## Bước 3: Upload lên Google Drive

1. Vào https://drive.google.com
2. Upload file `tff4040.yolov8.zip` vào `My Drive/`
3. Đợi upload xong (có thể mất vài phút với dataset lớn)

**Không upload folder trực tiếp** — phải zip lại trước để Colab giải nén nhanh hơn.

Cú pháp nén:
```bash
# Trên Windows PowerShell
Compress-Archive -Path "tff4040.yolov8\*" -DestinationPath "tff4040.yolov8.zip"

# Hoặc click phải → Send to → Compressed (zipped) folder
```

---

## Bước 4: Train trên Google Colab

1. Mở https://colab.research.google.com
2. Tạo notebook mới
3. **Runtime → Change runtime type → GPU: T4** (miễn phí, đủ dùng)
4. Tạo 1 cell mới
5. Mở file `scripts/train_yolov8_colab_v2.py` trong repo
6. **Copy toàn bộ nội dung** → paste vào cell → Run (Shift+Enter)

Script sẽ tự động:
- ✅ Mount Google Drive
- ✅ Cài ultralytics
- ✅ Kiểm tra GPU
- ✅ Giải nén dataset
- ✅ Thống kê class distribution
- ✅ Train (10-20 phút với 1000 ảnh, yolov8n)
- ✅ Validate
- ✅ Export ONNX
- ✅ Backup vào Drive

### Thời gian train ước tính

| Dataset size | GPU T4 | CPU (không khuyến nghị) |
|--------------|--------|------------------------|
| 500 ảnh | ~7 phút | ~3 giờ |
| 1000 ảnh | ~12 phút | ~6 giờ |
| 2000 ảnh | ~25 phút | ~12 giờ |

---

## Bước 5: Tải ONNX về và verify

Sau khi train xong, vào Google Drive → folder `yolo_safe_backup_v2/`:

1. Tải file `tff4040_v2_best.onnx` về máy
2. Copy đè vào `shared/models/yolo/TFF4040.onnx`
3. Chạy test:

```powershell
python scripts/test_video_raw.py `
    --video data/recordings/30_20260730_081531_10min.mp4 `
    --conf 0.25
```

### Mục tiêu kết quả sau retrain

So với kết quả hiện tại:

| Class | Max conf hiện tại | Mục tiêu |
|-------|-------------------|----------|
| hand | 0.96 | ≥ 0.85 |
| robot | 0.78 | ≥ 0.70 |
| sp | 0.64 | ≥ 0.60 |

Và **số lần detection > 0.25** phải tăng ít nhất **2-3 lần** so với baseline:
- hand >0.25: 2628 → ≥ 3000
- robot >0.25: 152 → ≥ 400
- sp >0.25: 28 → ≥ 100

Nếu **sp vẫn chỉ ~30-50 lần >0.25** trong 200 frames → cần label thêm ảnh sp trong khuôn.

---

## Bước 6: Deploy

Nếu kết quả OK:

1. Sửa config (nếu muốn giảm threshold):
   - File `config/config.yaml:34` → `conf_threshold: 0.25` (hoặc giảm xuống 0.15)
2. Test với camera RTSP thật (như đã làm trong CHAT_SUMMARY)

Nếu kết quả vẫn kém:
- Có thể cần label thêm ảnh (đặc biệt class `sp`)
- Có thể đổi `MODEL_SIZE = "yolov8s.pt"` trong script (mạnh hơn, chậm hơn ~3x)
- Có thể đổi `EPOCHS = 200`

---

## Checklist

- [ ] Dataset có ảnh `robot` ở mọi pose (đặc biệt khi lấp ló/kéo ra)
- [ ] Dataset có ảnh `sp` trong khuôn (kể cả khi robot đang gắp)
- [ ] Tỉ lệ class không quá chênh lệch (> 1:5)
- [ ] Export YOLOv8 format từ Roboflow
- [ ] Upload zip lên Drive
- [ ] Train trên Colab với GPU T4
- [ ] Verify kết quả bằng script test_video_raw.py
- [ ] Copy ONNX mới vào shared/models/yolo/

---

## Troubleshooting

### "data.yaml không tồn tại"

Kiểm tra:
- File zip có đúng cấu trúc `tff4040.yolov8/data.yaml` không?
- Nếu Roboflow export zip mà bên trong là folder khác, cần rename folder trong zip thành `tff4040.yolov8`

### "OutOfMemoryError" trên Colab

Giảm `BATCH_SIZE` trong script từ 16 → 8 hoặc 4.

### "Không cải thiện" sau 30 epoch

- Tăng `PATIENCE` lên 50
- Hoặc thêm data cho class yếu nhất

### Model predict OK trên valid nhưng tệ trên video thật

- Video thật có điều kiện khác (ánh sáng, góc camera)
- Cần thêm ảnh từ camera thật vào dataset (không phải ảnh đẹp từ video)