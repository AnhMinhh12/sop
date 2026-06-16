import cv2
import numpy as np
import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to sys.path to support imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Get information about the input video file.
    
    Args:
        video_path: Absolute or relative path to the video file.
        
    Returns:
        A dictionary containing video metadata.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video file: {video_path}")
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    file_size_bytes = os.path.getsize(video_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    cap.release()
    
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "duration": duration,
        "file_size_mb": file_size_mb
    }

def main() -> None:
    print("=" * 65)
    print("        CÔNG CỤ GIẢM ĐỘ PHÂN GIẢI VIDEO (CPU)")
    print("=" * 65)
    
    # 1. Nhập đường dẫn video thủ công
    default_path = r"C:\Users\it07\Downloads\AI_Monitoring_Hub\shared\tools\data\raw\tff4040.mp4"
    video_path_input = input(f"Nhập đường dẫn file video (Mặc định: {default_path}): ").strip()
    
    if not video_path_input:
        video_path = default_path
    else:
        video_path = video_path_input.strip('"\'')
        
    if not os.path.exists(video_path):
        logger.error(f"File video không tồn tại tại: {video_path}")
        return
        
    # 2. Đọc thông tin video
    logger.info("Đang đọc thông tin chi tiết video đầu vào...")
    try:
        info = get_video_info(video_path)
    except Exception as e:
        logger.error(f"Không thể đọc thông tin video: {e}")
        return
        
    print("\n🎥 THÔNG TIN VIDEO GỐC:")
    print(f"   - Đường dẫn: {video_path}")
    print(f"   - Độ phân giải: {info['width']}x{info['height']}")
    print(f"   - FPS: {info['fps']:.2f}")
    print(f"   - Tổng số frame: {info['total_frames']}")
    print(f"   - Thời lượng: {info['duration']:.2f} giây")
    print(f"   - Dung lượng: {info['file_size_mb']:.2f} MB")
    
    # 3. Chọn độ phân giải đầu ra
    print("\n⚙️ BƯỚC 1: CHỌN ĐỘ PHÂN GIẢI ĐẦU RA")
    print("   [1] 4320p (8K)")
    print("   [2] 2160p (4K)")
    print("   [3] 1080p (Full HD)")
    print("   [4] 720p (HD)")
    print("   [5] 480p (SD)")
    print("   [6] 360p")
    print("   [7] 240p")
    print("   [8] Nhập chiều cao (Height) mong muốn khác")
    print("   [9] Giảm theo tỉ lệ (Scale factor)")
    
    choice = input("Chọn mục (1-9, Mặc định: 5 [480p]): ").strip()
    if not choice:
        choice = "5"
        
    new_width = info['width']
    new_height = info['height']
    aspect_ratio = info['width'] / info['height']
    
    target_height = None
    
    if choice == "1":
        target_height = 4320
    elif choice == "2":
        target_height = 2160
    elif choice == "3":
        target_height = 1080
    elif choice == "4":
        target_height = 720
    elif choice == "5":
        target_height = 480
    elif choice == "6":
        target_height = 360
    elif choice == "7":
        target_height = 240
    elif choice == "8":
        custom_h_input = input("Nhập chiều cao (Height) mong muốn (ví dụ: 120): ").strip()
        try:
            target_height = int(custom_h_input)
            if target_height <= 0:
                logger.warning("Chiều cao không hợp lệ. Sử dụng mặc định: 480")
                target_height = 480
        except ValueError:
            logger.warning("Giá trị không hợp lệ. Sử dụng mặc định: 480")
            target_height = 480
    elif choice == "9":
        scale_input = input("Nhập tỉ lệ scale (ví dụ: 0.5 để giảm một nửa, mặc định: 0.5): ").strip()
        scale = 0.5
        if scale_input:
            try:
                scale = float(scale_input)
                if scale <= 0 or scale > 1:
                    logger.warning("Tỉ lệ scale phải nằm trong khoảng (0, 1]. Dùng mặc định: 0.5")
                    scale = 0.5
            except ValueError:
                logger.warning("Định dạng tỉ lệ scale không hợp lệ. Dùng mặc định: 0.5")
        
        # Đảm bảo chia hết cho 2 để tránh lỗi codec libx264
        new_width = int((info['width'] * scale) // 2) * 2
        new_height = int((info['height'] * scale) // 2) * 2
        
    if target_height is not None:
        new_height = target_height
        new_width = int((new_height * aspect_ratio) // 2) * 2
        # Làm tròn new_height về số chẵn luôn
        new_height = (new_height // 2) * 2
        
    # Đảm bảo kích thước tối thiểu là 4x4
    new_width = max(4, new_width)
    new_height = max(4, new_height)
    print(f"👉 Kích thước đầu ra được thiết lập: {new_width}x{new_height}")
    
    # 4. Chọn Video Writer Engine và đường dẫn file đầu ra
    input_path_obj = Path(video_path)
    output_dir = input_path_obj.parent
    
    # Gợi ý tên file đầu ra
    suffix = f"_{new_width}x{new_height}"
    default_out_name = f"{input_path_obj.stem}{suffix}.mp4"
    
    print(f"\n⚙️ BƯỚC 2: THIẾT LẬP FILE ĐẦU RA")
    out_name_input = input(f"Nhập tên file đầu ra (Lưu cùng thư mục gốc, mặc định: {default_out_name}): ").strip()
    
    if not out_name_input:
        out_name = default_out_name
    else:
        out_name = out_name_input
        if not out_name.endswith('.mp4'):
            out_name += '.mp4'
            
    out_path = output_dir / out_name
    
    print("\n   Chọn công cụ nén video:")
    print("   [1] ImageIO FFMPEG (libx264, nén cực tốt, dung lượng siêu nhỏ, mặc định)")
    print("   [2] OpenCV VideoWriter (mp4v, xử lý nhanh trên Windows)")
    
    engine_choice = input("Chọn công cụ (1-2, Mặc định: 1): ").strip()
    if not engine_choice:
        engine_choice = "1"
        
    logger.info(f"Đang bắt đầu xử lý video...")
    logger.info(f"File đầu ra: {out_path.resolve()}")
    
    # 5. Tiến hành xử lý frame-by-frame
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Không thể mở lại video đầu vào để xử lý.")
        return
        
    start_time = time.time()
    frame_count = 0
    total_frames = info['total_frames']
    fps = info['fps']
    
    # Khởi tạo writer tương ứng
    writer = None
    
    try:
        if engine_choice == "1":
            import imageio
            # Sử dụng H.264 với CRF=28 và preset ultrafast để tối ưu dung lượng và CPU
            writer = imageio.get_writer(
                str(out_path),
                fps=fps,
                codec='libx264',
                quality=None,
                ffmpeg_params=['-preset', 'ultrafast', '-crf', '28'],
                pixelformat='yuv420p',
                macro_block_size=1
            )
        else:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(out_path), fourcc, fps, (new_width, new_height))
            
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Resize
            if new_width != info['width'] or new_height != info['height']:
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
            # Ghi frame
            if engine_choice == "1":
                # OpenCV dùng BGR, ImageIO dùng RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                writer.append_data(frame_rgb)
            else:
                writer.write(frame)
                
            frame_count += 1
            if frame_count % 50 == 0 or frame_count == total_frames:
                elapsed = time.time() - start_time
                percent = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                avg_fps = frame_count / elapsed if elapsed > 0 else 0
                eta = (total_frames - frame_count) / avg_fps if avg_fps > 0 else 0
                sys.stdout.write(
                    f"\r   ⏳ Tiến độ: {frame_count}/{total_frames} frames ({percent:.1f}%) | "
                    f"Tốc độ: {avg_fps:.1f} FPS | Đã qua: {elapsed:.1f}s | ETA: {eta:.1f}s"
                )
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        print("\n⏹️ Bị dừng bởi người dùng!")
    except Exception as e:
        logger.error(f"\n❌ Lỗi trong quá trình xử lý: {e}")
    finally:
        cap.release()
        if writer is not None:
            if engine_choice == "1":
                writer.close()
            else:
                writer.release()
                
    elapsed_total = time.time() - start_time
    
    if os.path.exists(out_path):
        out_size_bytes = os.path.getsize(out_path)
        out_size_mb = out_size_bytes / (1024 * 1024)
        compression_ratio = (1 - (out_size_mb / info['file_size_mb'])) * 100 if info['file_size_mb'] > 0 else 0
        
        print("\n" + "=" * 65)
        print("✅ QUÁ TRÌNH XỬ LÝ HOÀN TẤT THÀNH CÔNG!")
        print(f"   - Video đầu ra: {out_path.resolve()}")
        print(f"   - Kích thước mới: {new_width}x{new_height}")
        print(f"   - Dung lượng cũ: {info['file_size_mb']:.2f} MB")
        print(f"   - Dung lượng mới: {out_size_mb:.2f} MB")
        print(f"   - Tỉ lệ nén giảm: {compression_ratio:.2f}% dung lượng gốc")
        print(f"   - Thời gian thực hiện: {elapsed_total:.1f} giây")
        print(f"   - Tốc độ trung bình: {frame_count / elapsed_total:.1f} FPS")
        print("=" * 65)
    else:
        logger.error("\n❌ Không thể tìm thấy file đầu ra. Có thể quá trình ghi đã thất bại.")

if __name__ == "__main__":
    main()

