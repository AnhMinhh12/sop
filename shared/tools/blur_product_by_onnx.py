import cv2
import numpy as np
import onnxruntime as ort
import os
import time
from pathlib import Path

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    # Resize and pad image while meeting stride-multiple constraints
    shape = img.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    # Compute padding
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding
    dw, dh = dw / 2, dh / 2  # divide padding into 2 sides

    if shape[::-1] != new_unpad:  # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return img, r, (left, top)

def main():
    print("="*60)
    print("      CONG CU TU DONG CHE MO SAN PHAM BANG MODEL YOLO ONNX")
    print("="*60)

    # 1. Nhap duong dan video va model ONNX
    video_path = input("Nhap duong dan file video: ").strip().strip('"').strip("'")
    if not os.path.exists(video_path):
        print(f"❌ LOI: Video khong ton tai tai: {video_path}")
        return

    model_path = input("Nhap duong dan file model (.onnx): ").strip().strip('"').strip("'")
    if not os.path.exists(model_path):
        print(f"❌ LOI: File model khong ton tai tai: {model_path}")
        return

    conf_threshold = input("Nhap nguong tin cay (0.1 - 0.9, mac dinh: 0.25): ").strip()
    conf_thresh = 0.25
    if conf_threshold:
        try:
            conf_thresh = float(conf_threshold)
        except ValueError:
            pass

    # Khoi tao session ONNX Runtime
    print(f"⏳ Dang load model ONNX tu: {model_path}...")
    try:
        session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        # input_shape: [batch, channels, height, width]
        img_size = input_shape[2] if isinstance(input_shape[2], int) else 640
        print(f"✅ Load model thanh cong. Kich thuoc input model: {img_size}x{img_size}")
    except Exception as e:
        print(f"❌ LOI load model ONNX: {e}")
        return

    # Mo video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ LOI: Khong the mo video: {video_path}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"🎥 Video info: {width}x{height} | {fps} FPS | Tong so: {total_frames} frames")

    # Nhap do mo rong vung lam mo (Padding)
    pad_ratio_input = input("Nhap ty le mo rong vung lam mo (%, mac dinh: 10): ").strip()
    pad_ratio = 0.10
    if pad_ratio_input.isdigit():
        pad_ratio = float(pad_ratio_input) / 100.0

    # Nhap do mo lam mo (1-10)
    blur_level_input = input("Nhap muc do che mo (1-10, mac dinh 5): ").strip()
    blur_intensity = 5
    if blur_level_input.isdigit():
        blur_intensity = max(1, min(10, int(blur_level_input)))
    ksize = blur_intensity * 18 + 1

    # Thiet lap video dau ra
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    video_name = Path(video_path).stem
    out_path = out_dir / f"{video_name}_ai_blurred.mp4"

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

    print("\n" + "="*50)
    print("🔴 DANG TU DONG NHAN DIEN VA CHE MO VIDEO...")
    print(f"📍 Video dau ra: {out_path.resolve()}")
    print("="*50 + "\n")

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Preprocessing
            padded_img, ratio, (pad_left, pad_top) = letterbox(frame, new_shape=(img_size, img_size))
            # BGR -> RGB & HWC -> CHW & Normalize
            blob = cv2.dnn.blobFromImage(padded_img, scalefactor=1.0/255.0, swapRB=True)

            # Inference
            outputs = session.run(None, {input_name: blob})
            output = outputs[0]  # output shape: [1, 4 + num_classes, num_proposals (8400)]

            # Post-processing (YOLOv8/v11 format)
            predictions = np.squeeze(output)  # shape: [4 + num_classes, 8400]
            
            # Neu so chieu bi nguoc (shape[0] < shape[1]), ta transpoe de de lam viec
            if predictions.shape[0] > predictions.shape[1]:
                predictions = predictions.T

            boxes = []
            confidences = []
            
            # YOLOv8 format: [x_center, y_center, width, height, class0_score, class1_score, ...]
            # Do ta chi gao nhan 1 class san pham (class 0), score se o cot index 4
            for pred in predictions:
                scores = pred[4:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                if confidence > conf_thresh:
                    # Chuyen tu coordinate he model ve coord he letterbox
                    xc, yc, w, h = pred[0], pred[1], pred[2], pred[3]
                    
                    x1 = xc - w / 2
                    y1 = yc - h / 2
                    
                    # Chuyen tu coord letterbox ve original image coords
                    x1_orig = (x1 - pad_left) / ratio
                    y1_orig = (y1 - pad_top) / ratio
                    w_orig = w / ratio
                    h_orig = h / ratio
                    
                    boxes.append([int(x1_orig), int(y1_orig), int(w_orig), int(h_orig)])
                    confidences.append(float(confidence))

            # Ap dung Non-Maximum Suppression (NMS) de loai bo cac hop bao trung lap
            indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_thresh, 0.45)
            
            # Tao mask de lam mo
            mask = np.zeros((height, width), dtype=np.uint8)

            if len(indices) > 0:
                for idx in indices.flatten():
                    x, y, w, h = boxes[idx]
                    
                    # Mo rong hop theo padding ratio an toan
                    pad_w = int(w * pad_ratio)
                    pad_h = int(h * pad_ratio)
                    
                    x1_pad = max(0, x - pad_w)
                    y1_pad = max(0, y - pad_h)
                    x2_pad = min(width, x + w + pad_w)
                    y2_pad = min(height, y + h + pad_h)
                    
                    cv2.rectangle(mask, (x1_pad, y1_pad), (x2_pad, y2_pad), 255, -1)

            # Ap dung GaussianBlur len vung duoc detect
            blurred_region = cv2.GaussianBlur(frame, (ksize, ksize), 0)
            processed_frame = np.where(mask[..., None] == 255, blurred_region, frame)

            # Ghi video
            out_writer.write(processed_frame)
            frame_count += 1

            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                percent = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                print(f"   Processed: {frame_count}/{total_frames} frames ({percent:.1f}%) | Elapsed: {elapsed:.1f}s", end="\r")

    except KeyboardInterrupt:
        print("\n⏹️ Nguoi dung dung chuong trinh.")
    finally:
        cap.release()
        out_writer.release()

    actual_duration = time.time() - start_time
    print("\n" + "="*50)
    print("✅ HOAN THANH TU DONG CHE MO SAN PHAM!")
    print(f"📍 File da luu: {out_path.resolve()}")
    print(f"⏱️ Thoi gian xu ly: {actual_duration:.1f} giay")
    print(f"🖼️ Tong so frame: {frame_count}")
    print("="*50)

if __name__ == "__main__":
    main()
