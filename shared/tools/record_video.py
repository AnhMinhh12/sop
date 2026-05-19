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
            # Kiem tra neu la so webcam
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

    # 4. Ket noi camera (Ep buoc su dung RTSP over TCP de tranh mat goi tin gay loi decode H264)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    print(f"\n⏳ Dang ket noi toi: {source} (Che do RTSP TCP)...")
    
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
        
    # Lay cac tham so video
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 60:
        fps = 15.0 # Fallback
        
    print(f"🎥 Ket noi thanh cong! Resolution: {width}x{height} | FPS: {fps}")
    
    # Khoi tao VideoWriter
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    
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
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Mat tin hieu tu camera!")
                break
                
            # Ghi frame
            out.write(frame)
            frame_count += 1
            
            # Show preview
            if show_preview:
                cv2.imshow("Record Preview (Press 'q' to stop)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("⏹️ Nguoi dung yeu cau dung quay.")
                    break
            else:
                # CPU relief when preview is disabled
                time.sleep(0.001)
                
            # Kiem tra thoi gian
            elapsed = time.time() - start_time
            if max_duration and elapsed >= max_duration:
                print(f"⏱️ Da dat thoi gian gioi han: {max_duration} giay.")
                break
                
            # Cap nhat log giam sat
            if frame_count % 30 == 0:
                print(f"   Recorded: {frame_count} frames | Elapsed: {elapsed:.1f}s", end="\r")
                
    except KeyboardInterrupt:
        print("\n⏹️ Nguoi dung dung chuong trinh.")
    finally:
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
