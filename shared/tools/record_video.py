import cv2
import yaml
import os
import time
import sys
from pathlib import Path

def load_config():
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None

def main():
    print("="*60)
    print("        CONG CU QUAY VIDEO THU THAP DU LIEU (RECORD)")
    print("="*60)
    
    # 1. Tai thong tin camera tu config.yaml
    config = load_config()
    cameras = []
    if config and 'cameras' in config:
        cameras = config['cameras']
        
    print("\n[DS camera tu config.yaml]:")
    for i, cam in enumerate(cameras):
        cam_id = cam.get('id', 'unknown')
        name = cam.get('name', 'N/A')
        url = cam.get('rtsp_url', 'N/A')
        print(f"  [{i + 1}] ID: {cam_id} | Ten: {name} | URL: {url}")
        
    print(f"  [{len(cameras) + 1}] Nhap camera/webcam thu cong (Webcam nhap: 0 hoặc 1)")
    print(f"  [Q] Thoat")
    
    # Choice
    choice = input("\nChon camera muon quay (1-{0}): ".format(len(cameras) + 1)).strip().lower()
    if choice == 'q':
        sys.exit(0)
        
    source = None
    cam_name = "Custom_Camera"
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(cameras):
            source = cameras[idx].get('rtsp_url')
            cam_name = cameras[idx].get('id', 'camera')
        elif idx == len(cameras):
            source_input = input("Nhap URL RTSP hoac so ID webcam (0, 1...): ").strip()
            # Tự động làm sạch input nếu người dùng copy-paste từ file yaml
            if "rtsp_url" in source_input:
                import re
                urls = re.findall(r'rtsp://[^\s"\']+', source_input)
                if urls:
                    source_input = urls[0]
                else:
                    parts = source_input.split(":", 1)
                    if len(parts) > 1:
                        source_input = parts[1].strip()
            
            # Loại bỏ dấu nháy kép hoặc đơn thừa ở hai đầu
            source_input = source_input.strip('"').strip("'")
            
            if source_input.isdigit():
                source = int(source_input)
            else:
                source = source_input
            cam_name = "custom"
        else:
            print("❌ Lựa chọn không hợp lệ!")
            return
    except ValueError:
        print("❌ Lựa chọn không hợp lệ!")
        return

    if source is None:
        print("❌ Không xác định được nguồn video!")
        return
        
    # 2. Cau hinh dau ra
    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(time.time())
    default_filename = f"record_{cam_name}_{timestamp}.mp4"
    out_file = input(f"Nhap ten file luu (Mac dinh: {default_filename}): ").strip()
    if not out_file:
        out_file = default_filename
    if not out_file.endswith(('.mp4', '.avi')):
        out_file += '.mp4'
        
    out_path = out_dir / out_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 3. Thiet lap thoi gian quay va preview
    duration_input = input("Nhap thoi gian quay (giay) - De trong neu muon quay vo han va nhan 'q' de dung: ").strip()
    max_duration = None
    if duration_input:
        try:
            max_duration = float(duration_input)
        except ValueError:
            print("⚠️ Thoi gian khong hop le, se quay vo han.")

    preview_input = input("Ban co muon hien thi cua so Preview khong? (Y/N, mac dinh Y): ").strip().lower()
    show_preview = preview_input != 'n'

    # Lua chon do phan gia
    print("\nChon do phan giai muon quay:")
    print("  [1] 1920x1080 (1080p - Full HD)")
    print("  [2] 1280x720 (720p - HD)")
    print("  [3] 854x480 (480p - SD)")
    print("  [4] 640x480 (VGA)")
    print("  [5] 480x360")
    print("  [6] 320x240 (QVGA)")
    print("  [7] Giu nguyen do phan giai goc cua camera (Mac dinh)")
    
    res_choice = input("Nhap lua chon (1-7, mac dinh 7): ").strip()
    target_width, target_height = None, None
    if res_choice == '1':
        target_width, target_height = 1920, 1080
    elif res_choice == '2':
        target_width, target_height = 1280, 720
    elif res_choice == '3':
        target_width, target_height = 854, 480
    elif res_choice == '4':
        target_width, target_height = 640, 480
    elif res_choice == '5':
        target_width, target_height = 480, 360
    elif res_choice == '6':
        target_width, target_height = 320, 240

    # 4. Ket noi camera (Ep buoc su dung RTSP over TCP de tranh mat goi tin gay loi decode H264)
    if isinstance(source, str) and source.startswith("rtsp://"):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|rw_timeout;5000000"
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        
    print(f"\n⏳ Dang ket noi toi: {source}...")
    
    # Neu nguon la duong dan file cuc bo (khong phai rtsp:// hay webcam index)
    if isinstance(source, str) and not source.startswith("rtsp://") and not source.startswith("http://"):
        file_path = Path(source)
        if not file_path.exists():
            print(f"❌ LOI: File nguon khong ton tai tren server!")
            print(f"   📍 Duong dan duoc cau hinh: {file_path.resolve()}")
            print("   💡 Vui long kiem tra lai duong dan file hoac chon nhap Webcam (0) / RTSP URL hop le.")
            return
            
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ LOI: Khong the ket noi toi nguon video: {source}")
        return

    # Thu thiet lap do phan giai tren camera phan cung
    if target_width and target_height:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
        
    # Lay cac tham so video goc tu camera
    orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 60:
        fps = 15.0 # Fallback
        
    # Xac dinh do phan giai thuc te se ghi
    write_width = target_width if target_width else orig_width
    write_height = target_height if target_height else orig_height
        
    print(f"🎥 Ket noi thanh cong! Original: {orig_width}x{orig_height} | Target: {write_width}x{write_height} | FPS: {fps}")
    
    # Khoi tao VideoWriter (Uu tien chat luong nén cao nhat de tranh mo file dau ra)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    try:
        out = cv2.VideoWriter(str(out_path), fourcc, fps, (write_width, write_height), [cv2.VIDEOWRITER_PROP_QUALITY, 95])
    except Exception:
        out = cv2.VideoWriter(str(out_path), fourcc, fps, (write_width, write_height))
        
    if not out.isOpened():
        print(f"❌ LOI: Khong the khoi tao VideoWriter! Vui long kiem tra lai quyen ghi hoac duong dan: {out_path.resolve()}")
        cap.release()
        return
    
    import queue
    import threading
    
    frame_queue = queue.Queue(maxsize=300)
    running = True
    connection_lost = False
    
    def receiver_loop():
        nonlocal running, connection_lost
        while running:
            ret, frame = cap.read()
            if not ret:
                print("\n⚠️ Mat tin hieu tu camera!")
                connection_lost = True
                running = False
                break
            try:
                frame_queue.put(frame, timeout=0.1)
            except queue.Full:
                # Nếu hàng đợi đầy, bỏ bớt frame cũ nhất để đảm bảo realtime
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    frame_queue.put_nowait(frame)
                except queue.Full:
                    pass

    # Chạy luồng đọc tin hiệu camera riêng biệt
    recv_thread = threading.Thread(target=receiver_loop, daemon=True)
    recv_thread.start()
    
    print("\n" + "="*50)
    print("🔴 DANG QUAY VIDEO...")
    print(f"📍 File luu tai: {out_path.resolve()}")
    if max_duration:
        print(f"⏱️ Thoi gian quay: {max_duration} giay")
    if show_preview:
        print("👉 Bam phim 'q' trong cua so Preview de DUNG QUAY bat ky luc nao.")
    else:
        print("👉 Nhan Ctrl+C tai terminal nay de DUNG QUAY bat ky luc nao.")
    print("="*50 + "\n")
    
    start_time = time.time()
    frame_count = 0
    
    if show_preview:
        cv2.namedWindow("Record Preview (Press 'q' to stop)", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Record Preview (Press 'q' to stop)", 800, 600)
    
    try:
        while running:
            try:
                frame = frame_queue.get(timeout=0.1)
            except queue.Empty:
                if connection_lost:
                    break
                continue
                
            # Resize frame neu khong khop voi do phan giai ghi
            if frame.shape[1] != write_width or frame.shape[0] != write_height:
                frame = cv2.resize(frame, (write_width, write_height))
                
            # Ghi frame xuống đĩa ở luồng ghi riêng (luồng chính)
            out.write(frame)
            frame_count += 1
            
            # Show preview
            if show_preview:
                cv2.imshow("Record Preview (Press 'q' to stop)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("⏹️ Nguoi dung yeu cau dung quay.")
                    running = False
                    break
                
            # Kiem tra thoi gian
            elapsed = time.time() - start_time
            if max_duration and elapsed >= max_duration:
                print(f"⏱️ Da dat thoi gian gioi han: {max_duration} giay.")
                running = False
                break
                
            # Cap nhat log giam sat
            if frame_count % 30 == 0:
                print(f"   Recorded: {frame_count} frames | Queue: {frame_queue.qsize()} | Elapsed: {elapsed:.1f}s", end="\r")
                
        # Xử lý nốt các frame còn sót lại trong hàng đợi sau khi dừng luồng đọc
        print("\n⏳ Dang ghi not cac frame con lai trong hang doi...")
        while not frame_queue.empty():
            try:
                frame = frame_queue.get_nowait()
                # Resize frame neu khong khop voi do phan giai ghi
                if frame.shape[1] != write_width or frame.shape[0] != write_height:
                    frame = cv2.resize(frame, (write_width, write_height))
                out.write(frame)
                frame_count += 1
            except queue.Empty:
                break
                
    except KeyboardInterrupt:
        print("\n⏹️ Nguoi dung dung chuong trinh.")
        running = False
    finally:
        running = False
        # Don dep tai nguyen
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        
        actual_duration = time.time() - start_time
        print("\n" + "="*50)
        print("✅ HOAN THANH QUAY VIDEO!")
        print(f"📍 File da luu: {out_path.resolve()}")
        print(f"⏱️ Thoi gian: {actual_duration:.1f} giay")
        print(f"🖼️ So frame ghi duoc: {frame_count} frames")
        print("="*50)

if __name__ == "__main__":
    main()
