import cv2
import numpy as np
import yaml
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path to support imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def get_polygon_pts(zone_pts, width, height):
    return np.array([[int(p[0] * width), int(p[1] * height)] for p in zone_pts], dtype=np.int32)

def select_from_yaml(width, height):
    polygons = []
    config_dir = os.path.join(project_root, "projects/sop_monitoring/config")
    configs = []
    if os.path.exists(config_dir):
        configs = [f for f in os.listdir(config_dir) if f.endswith(('.yaml', '.yml'))]
        
    if not configs:
        print("⚠️ Khong tim thay file config YAML nao trong projects/sop_monitoring/config!")
        return polygons
        
    print("\nCac file config YAML tim thay:")
    for idx, cfg in enumerate(configs):
        print(f"  [{idx + 1}] {cfg}")
    cfg_choice = input(f"Chon file config (1-{len(configs)}): ").strip()
    try:
        cfg_idx = int(cfg_choice) - 1
        cfg_path = os.path.join(config_dir, configs[cfg_idx])
        with open(cfg_path, "r", encoding="utf-8") as f:
            sop_config = yaml.safe_load(f)
        
        zones = sop_config.get("zones", {})
        if not zones:
            print("⚠️ File config khong chua định nghĩa vung (zones)!")
            return polygons
            
        print("\nCac vung co san trong config:")
        zone_list = list(zones.keys())
        for idx, zone_name in enumerate(zone_list):
            print(f"  [{idx + 1}] Vung: {zone_name} -> {zones[zone_name]}")
            
        zone_choices = input("Nhap cac so tuong ung voi vung muon che (cach nhau bang dau phay, vd: 1,3): ").strip()
        selected_idxs = [int(x.strip()) - 1 for x in zone_choices.split(",") if x.strip().isdigit()]
        
        for s_idx in selected_idxs:
            if 0 <= s_idx < len(zone_list):
                z_name = zone_list[s_idx]
                pts = get_polygon_pts(zones[z_name], width, height)
                polygons.append(pts)
                print(f"✅ Da chon vung: {z_name}")
    except Exception as e:
        print(f"❌ LOI khi doc config: {e}")
    return polygons

def select_by_mouse(first_frame):
    print("\n=== HUONG DAN VE NHIEU POLYGON (DA GIAC 4 DIEM HOAC TUY Y) ===")
    print("  - CLICK CHUOT TRAI de tao cac diem cua da giac (click 4 diem de tao khoi vuong/chu nhat nghieng).")
    print("  - Nhan phim 's' de LUU vung hien tai va bat dau ve vung tiep theo.")
    print("  - Nhan phim 'c' de XOA diem cuoi cung cua hinh dang ve.")
    print("  - Nhan phim 'Enter' hoac 'Space' de HOAN THANH toan bo va bat dau xu ly.")
    print("  - Nhan 'q' de thoat.")
    
    saved_polygons = []
    points = []
    
    def redraw():
        img = first_frame.copy()
        for idx, poly in enumerate(saved_polygons):
            cv2.polylines(img, [poly], True, (255, 0, 0), 2)
            centroid = np.mean(poly, axis=0).astype(int)
            cv2.putText(img, f"#{idx+1}", (centroid[0]-10, centroid[1]+5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        
        for idx, pt in enumerate(points):
            cv2.circle(img, pt, 5, (0, 0, 255), -1)
            if idx > 0:
                cv2.line(img, points[idx-1], pt, (0, 255, 0), 2)
        return img
        
    def mouse_callback(event, x, y, flags, param):
        nonlocal points
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
            cv2.imshow("Ve cac vung can che mo", redraw())
    
    cv2.namedWindow("Ve cac vung can che mo", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Ve cac vung can che mo", 1280, 720)
    cv2.setMouseCallback("Ve cac vung can che mo", mouse_callback)
    cv2.imshow("Ve cac vung can che mo", redraw())
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            print("❌ Huy bo ve.")
            return []
        elif key == ord('s'):
            if len(points) >= 3:
                saved_polygons.append(np.array(points, dtype=np.int32))
                print(f"✅ Da luu vung #{len(saved_polygons)} voi {len(points)} diem.")
                points = []
                cv2.imshow("Ve cac vung can che mo", redraw())
            else:
                print("⚠️ Hinh dang ve can it nhat 3 diem de luu!")
        elif key == ord('c') or key == ord('z'):
            if points:
                points.pop()
                cv2.imshow("Ve cac vung can che mo", redraw())
                print("Da xoa diem cuoi cung.")
            elif saved_polygons:
                saved_polygons.pop()
                cv2.imshow("Ve cac vung can che mo", redraw())
                print("Da xoa vung da luu gan nhat.")
        elif key == 13 or key == 32: # Enter hoặc Space
            if len(points) >= 3:
                saved_polygons.append(np.array(points, dtype=np.int32))
                print(f"✅ Da luu vung cuoi cung #{len(saved_polygons)}.")
                points = []
            elif len(points) > 0:
                print("⚠️ Vung dang ve do dang khong du 3 diem nen bi bo qua.")
            
            if saved_polygons:
                cv2.destroyAllWindows()
                return saved_polygons
            else:
                print("⚠️ Chua co vung nao duoc luu! Hay nhan 's' de luu it nhat 1 vung.")

def create_single_tracker():
    tracker_names = ["CSRT", "KCF", "MIL"]
    for name in tracker_names:
        if name == "CSRT":
            creator = getattr(cv2, 'TrackerCSRT_create', None) or (getattr(cv2, 'legacy', None) and getattr(cv2.legacy, 'TrackerCSRT_create', None))
        elif name == "KCF":
            creator = getattr(cv2, 'TrackerKCF_create', None) or (getattr(cv2, 'legacy', None) and getattr(cv2.legacy, 'TrackerKCF_create', None))
        else:
            creator = getattr(cv2, 'TrackerMIL_create', None) or (getattr(cv2, 'legacy', None) and getattr(cv2.legacy, 'TrackerMIL_create', None))
        
        if creator:
            try:
                tracker = creator()
                if tracker is not None:
                    return tracker, name
            except Exception:
                pass
    return None, None

def main():
    print("="*60)
    print("           CONG CU CHE MO SAN PHAM / JIG TRONG VIDEO")
    print("="*60)
    
    # 1. Nhap duong dan video nguon
    video_path = input("Nhap duong dan file video cua ban: ").strip().strip('"').strip("'")
    if not os.path.exists(video_path):
        print(f"❌ LOI: File video khong ton tai tai: {video_path}")
        return
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ LOI: Khong the mo video: {video_path}")
        return
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"🎥 Thong tin video: {width}x{height} | {fps} FPS | Tong so: {total_frames} frames")
    
    # Doc frame dau tien de xem truoc/chon vung
    ret, first_frame = cap.read()
    if not ret:
        print("❌ LOI: Khong the doc frame dau tien cua video!")
        cap.release()
        return
        
    # Reset video capture ve frame dau
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    # 2. Lua chon cach lay vung de che mo
    print("\nChon cach xac dinh vung san pham can che mo:")
    print("  [1] Chon vung (Polygon) tu file config YAML cua he thong")
    print("  [2] Tu ve vung da giac (Polygon) bang cach click chuot")
    print("  [3] Tu ve vung hinh chu nhat (Rectangle) dung chuot")
    print("  [4] Che mo DONG theo tay (YOLO ONNX) + Vung co dinh (Tuy chon)")
    print("  [5] Bam vet va che mo DONG doi tuong (OpenCV Object Tracking)")
    
    choice = input("Nhap lua chon (1-5): ").strip()
    
    polygons_to_blur = []
    detector = None
    trackers = []
    tracked_bboxes = []
    pad_ratio = 0.40
    
    if choice == '1':
        polygons_to_blur = select_from_yaml(width, height)
    elif choice == '2':
        polygons_to_blur = select_by_mouse(first_frame)
    elif choice == '3':
        print("\n=== HUONG DAN VE ROI HINH CHU NHAT ===")
        print("  - Keo chuot de tao hinh chu nhat.")
        print("  - Nhan 'Enter' hoac 'Space' de xac nhan.")
        print("  - Nhan 'c' de chon lai.")
        
        cv2.namedWindow("Chon vung hinh chu nhat", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Chon vung hinh chu nhat", 800, 600)
        
        roi = cv2.selectROI("Chon vung hinh chu nhat", first_frame, fromCenter=False, showCrosshair=True)
        cv2.destroyAllWindows()
        
        x, y, w, h = roi
        if w > 0 and h > 0:
            pts = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32)
            polygons_to_blur.append(pts)
            print(f"✅ Da chon vung chu nhat: x={x}, y={y}, w={w}, h={h}")
        else:
            print("❌ Vung chon khong hop le!")
            cap.release()
            return
            
    elif choice == '4':
        # Khoi tao YOLO detector de tracking tay
        try:
            from shared.inference_engine import InferenceEngine
            from projects.sop_monitoring.hand_detector import HandDetector
        except ImportError as e:
            print(f"❌ LOI: Khong the import module he thong: {e}")
            cap.release()
            return
            
        # Load weights tu config.yaml
        config_path = os.path.join(project_root, "config", "config.yaml")
        yolo_weights = "shared/models/yolo/TFF4040_roboflow2.onnx"
        input_size = 416
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                yolo_weights = cfg.get("models", {}).get("yolo", {}).get("weights", yolo_weights)
                input_size = cfg.get("models", {}).get("yolo", {}).get("input_size", input_size)
            except Exception as e:
                print(f"⚠️ Khong the doc config.yaml: {e}. Dung mac dinh.")
                
        abs_weights = os.path.abspath(os.path.join(project_root, yolo_weights))
        if not os.path.exists(abs_weights):
            yolo_dir = os.path.join(project_root, "shared", "models", "yolo")
            if os.path.exists(yolo_dir):
                onnx_files = [f for f in os.listdir(yolo_dir) if f.endswith(".onnx")]
                if onnx_files:
                    abs_weights = os.path.join(yolo_dir, onnx_files[0])
                    
        print(f"⏳ Dang khoi tao YOLO ONNX Engine tu: {abs_weights}...")
        InferenceEngine(model_path=abs_weights, num_threads=4, input_size=input_size)
        detector = HandDetector(camera_id="blur_tool", confidence_threshold=0.15, model_path=abs_weights)
        
        # Nhap do mo rong vung lam mo quanh tay
        print("\nNhap do mo rong vung lam mo quanh tay (%, mac dinh: 40):")
        pad_input = input("Phan tram (0-200): ").strip()
        if pad_input.isdigit():
            pad_ratio = float(pad_input) / 100.0
            
        # Lua chon che them vung co dinh (khi tay khong cham vao san pham)
        print("\nBan co muon che them vung co dinh (jig/khuon co dinh) khong?")
        print("  [1] Khong (chi che mo dong theo tay)")
        print("  [2] Lay vung co dinh tu file config YAML")
        print("  [3] Tu ve vung da giac co dinh bang chuot")
        static_choice = input("Nhap lua chon (1-3, mac dinh: 1): ").strip()
        
        if static_choice == '2':
            polygons_to_blur = select_from_yaml(width, height)
        elif static_choice == '3':
            polygons_to_blur = select_by_mouse(first_frame)
            
    elif choice == '5':
        # Khoi tao danh sach Object Tracker de bam vet va che mo dong theo nhieu doi tuong (san pham)
        print("\nNhap so luong san pham muon bam vet (vi du: 2):")
        num_input = input("So luong (mac dinh: 1): ").strip()
        num_objects = 1
        if num_input.isdigit():
            num_objects = max(1, int(num_input))
            
        print("\n=== HUONG DAN VE ROI DE BAM VET SAN PHAM ===")
        print("  - Keo chuot de tao hinh chu nhat bao quanh tung san pham.")
        print("  - Nhan 'Enter' hoac 'Space' de xac nhan cho moi san pham.")
        print("  - Nhan 'c' de chon lai.")
        
        for idx in range(num_objects):
            window_title = f"Chon san pham thu {idx + 1} cua {num_objects}"
            cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_title, 800, 600)
            
            roi = cv2.selectROI(window_title, first_frame, fromCenter=False, showCrosshair=True)
            cv2.destroyWindow(window_title)
            
            x, y, w, h = roi
            if w > 0 and h > 0:
                tracker, tracker_name = create_single_tracker()
                if tracker is None:
                    print("❌ LOI: Khong the khoi tao tracker tu OpenCV!")
                    cap.release()
                    return
                    
                tracker.init(first_frame, roi)
                trackers.append(tracker)
                tracked_bboxes.append(roi)
                
                # Giu mo co dinh vi tri ban dau de tranh lo jig/khuon khi thao san pham
                pts = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.int32)
                polygons_to_blur.append(pts)
                
                print(f"✅ Da thiet lap tracker {tracker_name} cho san pham {idx + 1}: x={x}, y={y}, w={w}, h={h}")
            else:
                print(f"⚠️ Bo qua san pham thu {idx + 1} vi vung chon khong hop le!")
                
        if not trackers:
            print("❌ LOI: Khong co san pham nao duoc chon de bam vet!")
            cap.release()
            return
            
    else:
        print("❌ Lua chon khong hop le!")
        cap.release()
        return

    # 3. Thiet lap muc do che mo (Blur intensity)
    print("\nNhap muc do che mo (1-10, mac dinh 5): ")
    blur_level_input = input("Muc do: ").strip()
    blur_intensity = 5
    if blur_level_input.isdigit():
        blur_intensity = max(1, min(10, int(blur_level_input)))
        
    # Tinh kernel size cho GaussianBlur (phai la so le)
    ksize = blur_intensity * 18 + 1 # vd: 5 -> 91, 10 -> 181
    
    # 4. Thiet lap file dau ra
    out_dir = Path(os.path.join(project_root, "data/processed"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    video_name = Path(video_path).stem
    default_out_file = f"{video_name}_blurred.mp4"
    out_file = input(f"Nhap ten file video dau ra (Mac dinh: {default_out_file}): ").strip()
    if not out_file:
        out_file = default_out_file
    if not out_file.endswith(('.mp4', '.avi')):
        out_file += '.mp4'
        
    out_path = out_dir / out_file
    
    # 5. Khoi tao VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    
    print("\n" + "="*50)
    print("🔴 DANG XU LY VIDEO...")
    print(f"📍 File dau ra: {out_path.resolve()}")
    print("="*50 + "\n")
    
    # Tao mat na tinh (static mask) cho cac vung duoc chon
    static_mask = np.zeros((height, width), dtype=np.uint8)
    for poly in polygons_to_blur:
        cv2.fillPoly(static_mask, [poly], 255)
        
    frame_count = 0
    start_time = time.time()
    
    # Cache cho bám vết tay mượt mà (tránh nhấp nháy khi mất frame ngắn)
    last_hands = []
    frames_since_detect = 0
    max_history_frames = 5
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            mask = static_mask.copy()
            
            if choice == '4' and detector is not None:
                # Chạy AI tìm tay và sản phẩm trên frame hiện tại
                hands = detector.detect(frame)
                
                if hands:
                    last_hands = hands
                    frames_since_detect = 0
                else:
                    frames_since_detect += 1
                    
                # Sử dụng thông tin tay/sản phẩm (bao gồm cả cache nếu mới mất frame)
                if last_hands and frames_since_detect <= max_history_frames:
                    for h in last_hands:
                        bbox = h["bbox"] # [x1, y1, x2, y2]
                        x1, y1, x2, y2 = bbox
                        
                        # Nếu là sản phẩm detected trực tiếp, che chính xác bbox sản phẩm
                        if h.get("class") == "product":
                            cv2.rectangle(mask, (int(x1), int(y1)), (int(x2), int(y2)), 255, -1)
                        else:
                            # Nếu là tay, mở rộng hộp để che phủ sản phẩm đang cầm
                            w_box = x2 - x1
                            h_box = y2 - y1
                            pad_w = int(w_box * pad_ratio)
                            pad_h = int(h_box * pad_ratio)
                            
                            x1_pad = max(0, int(x1 - pad_w))
                            y1_pad = max(0, int(y1 - pad_h))
                            x2_pad = min(width, int(x2 + pad_w))
                            y2_pad = min(height, int(y2 + pad_h))
                            cv2.rectangle(mask, (x1_pad, y1_pad), (x2_pad, y2_pad), 255, -1)
                        
                    # Nếu thấy từ 2 bàn tay trở lên, che cả khoảng không ở giữa (nơi thường là sản phẩm)
                    # Chỉ áp dụng cho nhãn tay ('hand')
                    only_hands = [h for h in last_hands if h.get("class", "hand") == "hand"]
                    if len(only_hands) >= 2:
                        all_x1 = [h["bbox"][0] for h in only_hands]
                        all_y1 = [h["bbox"][1] for h in only_hands]
                        all_x2 = [h["bbox"][2] for h in only_hands]
                        all_y2 = [h["bbox"][3] for h in only_hands]
                        
                        min_x = max(0, int(min(all_x1)))
                        min_y = max(0, int(min(all_y1)))
                        max_x = min(width, int(max(all_x2)))
                        max_y = min(height, int(max(all_y2)))
                        
                        cv2.rectangle(mask, (min_x, min_y), (max_x, max_y), 255, -1)
                        
            elif choice == '5' and trackers:
                for idx, (t, old_bbox) in enumerate(zip(trackers, tracked_bboxes)):
                    success, bbox = t.update(frame)
                    if success:
                        tracked_bboxes[idx] = bbox
                    else:
                        if frame_count % 30 == 0:
                            print(f"⚠️ Mat dau vet san pham {idx + 1} tai frame {frame_count}, giu nguyen vi tri cu.")
                    
                    tx, ty, tw, th = [int(v) for v in tracked_bboxes[idx]]
                    # Mo rong vung che mo 10% moi ben de dam bao bao mat rieng tu cho san pham
                    pad_w = int(tw * 0.1)
                    pad_h = int(th * 0.1)
                    tx1 = max(0, tx - pad_w)
                    ty1 = max(0, ty - pad_h)
                    tx2 = min(width, tx + tw + pad_w)
                    ty2 = min(height, ty + th + pad_h)
                    cv2.rectangle(mask, (tx1, ty1), (tx2, ty2), 255, -1)
            
            # Che mo
            blurred_region = cv2.GaussianBlur(frame, (ksize, ksize), 0)
            processed_frame = np.where(mask[..., None] == 255, blurred_region, frame)
            
            # Ghi ra file
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
    print("✅ HOAN THANH CHE MO VIDEO!")
    print(f"📍 File da luu: {out_path.resolve()}")
    print(f"⏱️ Thoi gian xu ly: {actual_duration:.1f} giay")
    print(f"🖼️ Tong so frame: {frame_count}")
    print("="*50)

if __name__ == "__main__":
    main()
