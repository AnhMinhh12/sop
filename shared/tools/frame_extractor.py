import cv2
import os
import time
from pathlib import Path

# --- CẤU HÌNH ---
INPUT_DIR = Path("data/training_collection")
OUTPUT_BASE_DIR = INPUT_DIR / "extracted_data"

def main():
    print("=" * 60)
    print("      CONG CU TRICH XUAT ANH TU VIDEO THEO YEU CAU")
    print("=" * 60)
    
    if not INPUT_DIR.exists():
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        
    # Tim tat ca cac file video trong INPUT_DIR
    video_extensions = ('.mp4', '.avi', '.mkv', '.mov')
    video_files = [f for f in INPUT_DIR.iterdir() if f.is_file() and f.suffix.lower() in video_extensions]
    
    selected_video = None
    
    if video_files:
        print("📋 Danh sach video tim thay trong 'data/training_collection':")
        for i, video_file in enumerate(video_files):
            print(f"  [{i + 1}] {video_file.name}")
        print("  [M] Nhap duong dan video thu cong tu cho khac")
        
        choice = input("\nChon video muon trich xuat (1-{} hoac M): ".format(len(video_files))).strip()
        if choice.lower() == 'm':
            video_path_str = input("Nhap duong dan file video cua ban: ").strip()
            selected_video = Path(video_path_str)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(video_files):
                    selected_video = video_files[idx]
                else:
                    print("❌ Chi so khong hop le.")
                    return
            except ValueError:
                print("❌ Lua chon khong hop le.")
                return
    else:
        print("ℹ️ Khong tim thay file video nao trong 'data/training_collection'.")
        video_path_str = input("Vui long nhap duong dan file video thu cong: ").strip()
        selected_video = Path(video_path_str)
        
    if not selected_video.exists() or not selected_video.is_file():
        print(f"❌ LOI: File video khong ton tai: {selected_video}")
        return

    # Doc thong tin video truoc khi hoi thong so
    cap = cv2.VideoCapture(str(selected_video))
    if not cap.isOpened():
        print(f"❌ LOI: Khong the mo file video {selected_video.name}")
        return
        
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_sec = total_frames / fps if fps > 0 else 0
    
    print(f"\n🎥 Thong tin video da chon:")
    print(f"   - File: {selected_video.name}")
    print(f"   - Resolution: {width}x{height}")
    print(f"   - FPS (Toc do khung hinh): {fps:.1f} frames/giay")
    print(f"   - Tong so frame: {total_frames} frames (~{duration_sec:.1f} giay)")
        
    # Goi y ten folder theo ten video (bo phan hau to sau gach duoi neu co)
    default_folder_name = selected_video.stem.split('_')[0]
    custom_folder = input(f"\nNhap ten folder luu anh (Mac dinh: '{default_folder_name}'): ").strip()
    if not custom_folder:
        custom_folder = default_folder_name
        
    output_dir = OUTPUT_BASE_DIR / custom_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Kiem tra cac file anh dang co trong folder de tim index lon nhat
    start_idx = 1
    expected_prefix = f"img_{custom_folder}_"
    if output_dir.exists():
        for file in output_dir.iterdir():
            if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                name = file.stem
                if name.startswith(expected_prefix):
                    idx_str = name[len(expected_prefix):]
                    if idx_str.isdigit():
                        idx = int(idx_str)
                        if idx >= start_idx:
                            start_idx = idx + 1
                            
    print(f"ℹ️ Tu dong danh so tiep theo tu: {start_idx:06d} (Ten file dang: img_{custom_folder}_XXXXXX.jpg)")
    
    # Cho phep thiet lap Frame Interval
    suggested_interval = int(fps) if fps > 0 else 30
    interval_input = input(f"Nhap khoang cach trich xuat (so frame) (Mac dinh: {suggested_interval} - lay 1 anh/giay): ").strip()
    frame_interval = suggested_interval
    if interval_input:
        try:
            frame_interval = int(interval_input)
            if frame_interval <= 0:
                print(f"❌ Khoang cach phai lon hon 0. Dung mac dinh {suggested_interval}.")
                frame_interval = suggested_interval
        except ValueError:
            print(f"❌ Nhap sai dinh dang. Dung mac dinh {suggested_interval}.")
            
    print(f"\n🎬 Bat dau xu ly: {selected_video.name}")
    print(f"📂 Anh se duoc luu tai: {output_dir.resolve()}")
    
    count = 0
    saved_count = 0
    current_image_idx = start_idx
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if count % frame_interval == 0:
            img_name = f"img_{custom_folder}_{current_image_idx:06d}.jpg"
            file_path = output_dir / img_name
            
            cv2.imwrite(str(file_path), frame)
            saved_count += 1
            current_image_idx += 1
            
            if saved_count % 50 == 0:
                elapsed = time.time() - start_time
                progress = (count / total_frames) * 100 if total_frames > 0 else 0
                print(f"   -> Da luu {saved_count} anh... (Tien do: {progress:.1f}%, Thoi gian: {elapsed:.1f}s)", end="\r")
                
        count += 1
        
    cap.release()
    elapsed = time.time() - start_time
    print(f"\n   -> Da trich xuat xong: {saved_count} anh. (Tien do: 100.0%, Thoi gian: {elapsed:.1f}s)")
    print(f"✅ HOAN TAT: Da luu thanh cong {saved_count} anh (tu index {start_idx:06d} den {(current_image_idx-1):06d}) vao folder '{custom_folder}'")

if __name__ == "__main__":
    main()
