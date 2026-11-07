import os
import sys
import cv2
import numpy as np
import onnxruntime as ort

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

MODEL_PATH = "shared/models/yolo/laprap_8_oc.onnx"
VIDEO_PATH = "data/recordings/laprap_20261103_131237_10min.mp4"
OUTPUT_VIDEO = "data/training_collection/laprap_8_oc/demo_cycle_result.mp4"
OUTPUT_DIR = "data/training_collection/laprap_8_oc/demo_snapshots"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

# 1. Khởi tạo model ONNX
sess = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
classes = ["hand", "part_hand", "part_tray", "screw"]

cap = cv2.VideoCapture(VIDEO_PATH)
fps = int(cap.get(cv2.CAP_PROP_FPS) or 20)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

# Chạy thử nghiệm trong khoảng giây 25 đến 80 (chứa trọn vẹn 1 chu kỳ hoàn chỉnh)
START_SEC = 25
END_SEC = 85
cap.set(cv2.CAP_PROP_POS_FRAMES, START_SEC * fps)
total_frames = (END_SEC - START_SEC) * fps

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, fps, (w, h))

print(f"[*] Bat dau chay thu nghiem tu {START_SEC}s den {END_SEC}s ({total_frames} frames)...")

# Bộ lọc NMS
def nms(boxes, scores, iou_thresh=0.45):
    if len(boxes) == 0:
        return []
    boxes = np.array(boxes)
    scores = np.array(scores)
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w_inter = np.maximum(0.0, xx2 - xx1)
        h_inter = np.maximum(0.0, yy2 - yy1)
        inter = w_inter * h_inter
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= iou_thresh)[0]
        order = order[inds + 1]
    return keep

# Quản lý trạng thái chu kỳ (Cycle State Machine)
state = "IDLE"  # IDLE, ASSEMBLING, RESULT
cycle_id = 0
slots = [False] * 8
max_simultaneous = 0
part_present_count = 0
missing_part_count = 0
total_good = 0
total_ng = 0
last_result_banner = None
result_banner_timer = 0

frame_idx = 0
saved_snapshots = []

while cap.isOpened() and frame_idx < total_frames:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1
    current_sec = START_SEC + (frame_idx / fps)

    # Tiền xử lý cho YOLO 640x640
    img = cv2.resize(frame, (640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).transpose(2, 0, 1).astype(np.float32) / 255.0
    img = np.expand_dims(img, 0)

    # Inference ONNX
    preds = sess.run(None, {"images": img})[0][0]  # (8, 8400)

    raw_boxes, raw_scores, raw_classes = [], [], []
    for i in range(8400):
        scores = preds[4:, i]
        c_id = int(np.argmax(scores))
        conf = float(scores[c_id])
        if conf > 0.35:
            cx, cy, bw, bh = preds[:4, i]
            x1 = int((cx - bw / 2) * w / 640)
            y1 = int((cy - bh / 2) * h / 640)
            x2 = int((cx + bw / 2) * w / 640)
            y2 = int((cy + bh / 2) * h / 640)
            raw_boxes.append([x1, y1, x2, y2])
            raw_scores.append(conf)
            raw_classes.append(c_id)

    # NMS theo từng class
    keep_indices = []
    for c_id in range(4):
        c_idxs = [idx for idx, c in enumerate(raw_classes) if c == c_id]
        if c_idxs:
            c_boxes = [raw_boxes[i] for i in c_idxs]
            c_scores = [raw_scores[i] for i in c_idxs]
            kept = nms(c_boxes, c_scores, iou_thresh=0.4)
            keep_indices.extend([c_idxs[k] for k in kept])

    # Phân loại đối tượng đã lọc NMS
    part_hand_box = None
    part_hand_score = 0.0
    screws = []
    hands = []
    trays = []

    for idx in keep_indices:
        cls_name = classes[raw_classes[idx]]
        box = raw_boxes[idx]
        conf = raw_scores[idx]
        if cls_name == "part_hand":
            # Ưu tiên box part_hand có độ tin cậy cao nhất ở khu vực thao tác
            if conf > part_hand_score and 350 < (box[0] + box[2]) / 2 < 850:
                part_hand_box = box
                part_hand_score = conf
        elif cls_name == "screw":
            screws.append((box, conf))
        elif cls_name == "hand":
            hands.append((box, conf))
        elif cls_name == "part_tray":
            trays.append((box, conf))

    # Xử lý Logic Chu Kỳ & Tích lũy 8 Slot
    current_frame_screws_on_part = []
    if part_hand_box is not None:
        part_present_count += 1
        missing_part_count = 0
        px1, py1, px2, py2 = part_hand_box
        pw = max(1, px2 - px1)
        ph = max(1, py2 - py1)

        # Lọc các ốc nằm bên trong part_hand
        for s_box, s_conf in screws:
            scx = (s_box[0] + s_box[2]) / 2
            scy = (s_box[1] + s_box[3]) / 2
            # Mở rộng biên nhẹ 10px để bắt các ốc ở sát mép
            if (px1 - 10) <= scx <= (px2 + 10) and (py1 - 10) <= scy <= (py2 + 10):
                # Tính vị trí tương đối dọc theo trục chính (thường là trục dọc hoặc trục dài)
                if ph >= pw:
                    rel_pos = (scy - py1) / ph
                else:
                    rel_pos = (scx - px1) / pw
                rel_pos = min(0.999, max(0.0, rel_pos))
                slot_idx = int(rel_pos * 8)
                current_frame_screws_on_part.append((s_box, s_conf, slot_idx))

        # Cập nhật số ốc đồng thời trong frame
        n_now = len(current_frame_screws_on_part)
        if n_now > max_simultaneous:
            max_simultaneous = n_now

        # Nếu đang IDLE mà thấy part_hand liên tục 3 frame -> Bắt đầu chu kỳ
        if state == "IDLE" and part_present_count >= 3:
            state = "ASSEMBLING"
            cycle_id += 1
            slots = [False] * 8
            max_simultaneous = 0
            print(f"[{current_sec:.1f}s] [START] BAT DAU CHU KY #{cycle_id}")

        # Trong trạng thái ASSEMBLING -> Tích lũy slot
        if state == "ASSEMBLING":
            for _, _, slot_idx in current_frame_screws_on_part:
                slots[slot_idx] = True

    else:
        part_present_count = 0
        if state == "ASSEMBLING":
            missing_part_count += 1
            # Nếu vắng mặt quá 25 frame (~1.25 giây) -> Chốt kết thúc chu kỳ
            if missing_part_count > 25:
                # Đánh giá kết quả
                slot_count = sum(slots)
                final_screw_count = max(slot_count, max_simultaneous)
                if final_screw_count >= 8:
                    total_good += 1
                    status_text = f"CHU KY #{cycle_id}: PASS ({final_screw_count}/8 OC)"
                    is_pass = True
                    print(f"[{current_sec:.1f}s] [PASS] {status_text}")
                else:
                    total_ng += 1
                    status_text = f"CHU KY #{cycle_id}: VIOLATION (THIEU OC: {final_screw_count}/8)"
                    is_pass = False
                    print(f"[{current_sec:.1f}s] [VIOLATION] {status_text}")

                last_result_banner = (status_text, is_pass)
                result_banner_timer = fps * 3  # Giữ banner 3 giây
                state = "IDLE"

    # ==================== VẼ OVERLAY TRỰC QUAN ====================
    vis = frame.copy()

    # 1. Vẽ các chi tiết dưới khay (màu xanh dương mờ)
    for t_box, t_conf in trays:
        cv2.rectangle(vis, (t_box[0], t_box[1]), (t_box[2], t_box[3]), (220, 100, 50), 1)

    # 2. Vẽ bàn tay (màu xanh lá)
    for h_box, h_conf in hands:
        cv2.rectangle(vis, (h_box[0], h_box[1]), (h_box[2], h_box[3]), (0, 255, 0), 2)

    # 3. Vẽ part_hand (màu cam đậm)
    if part_hand_box is not None:
        px1, py1, px2, py2 = part_hand_box
        cv2.rectangle(vis, (px1, py1), (px2, py2), (0, 140, 255), 3)
        cv2.putText(vis, f"SAN PHAM (part_hand) {part_hand_score:.2f}",
                    (px1, max(20, py1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 2)

    # 4. Vẽ các ốc trên thân chi tiết (màu vàng rực + số slot)
    for s_box, s_conf, slot_idx in current_frame_screws_on_part:
        cv2.rectangle(vis, (s_box[0], s_box[1]), (s_box[2], s_box[3]), (0, 255, 255), 2)
        cv2.putText(vis, f"#{slot_idx+1}", (s_box[0], max(15, s_box[1] - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 2)

    # 5. HUD Dashboard trên đỉnh
    overlay = vis.copy()
    cv2.rectangle(overlay, (20, 15), (780, 115), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.8, vis, 0.2, 0, vis)

    # Dòng 1: Trạng thái chu kỳ & Thống kê OK/NG
    if state == "ASSEMBLING":
        state_color = (0, 255, 255)
        state_str = f"CHU KY #{cycle_id}: DANG LAP RAP..."
    else:
        state_color = (180, 180, 180)
        state_str = "TRANG THAI: CHO SAN PHAM MOI (IDLE)"

    cv2.putText(vis, state_str, (35, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, state_color, 2)
    cv2.putText(vis, f"PASS: {total_good} | NG: {total_ng}", (580, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # Dòng 2: Thanh tiến trình 8 Slot ốc
    current_slots_count = sum(slots)
    cv2.putText(vis, f"Tich luy oc: {current_slots_count}/8", (35, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

    bar_x = 220
    bar_y = 60
    box_size = 28
    spacing = 8
    for i in range(8):
        bx = bar_x + i * (box_size + spacing)
        by = bar_y
        if slots[i]:
            # Đã có ốc ở slot này -> Màu xanh lá
            cv2.rectangle(vis, (bx, by), (bx + box_size, by + box_size), (0, 220, 0), -1)
            cv2.putText(vis, str(i + 1), (bx + 8, by + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        else:
            # Chưa có -> Viền xám rỗng
            cv2.rectangle(vis, (bx, by), (bx + box_size, by + box_size), (80, 80, 80), 2)
            cv2.putText(vis, str(i + 1), (bx + 8, by + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)

    # 6. Hiển thị Banner kết quả lớn (PASS/NG) khi chốt chu kỳ
    if result_banner_timer > 0 and last_result_banner:
        result_banner_timer -= 1
        res_text, is_p = last_result_banner
        b_color = (0, 200, 0) if is_p else (0, 0, 230)
        cv2.rectangle(vis, (250, 300), (1030, 380), b_color, -1)
        cv2.putText(vis, res_text, (270, 355),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    out.write(vis)

    # Chụp lại vài snapshot tiêu biểu để người dùng xem ngay
    if int(current_sec * 2) % 20 == 0:  # mỗi 10 giây
        snap_path = os.path.join(OUTPUT_DIR, f"snap_{int(current_sec)}s.jpg")
        cv2.imwrite(snap_path, vis)
        saved_snapshots.append(snap_path)

cap.release()
out.release()
print(f"[DONE] DA HOAN TAT CHAY THU NGHIEM!")
print(f"[*] Video ket qua: {OUTPUT_VIDEO}")
print(f"[*] Ket qua tong: PASS={total_good}, NG={total_ng}")
