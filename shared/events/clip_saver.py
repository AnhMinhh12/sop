import os
import time
import logging
import imageio
from typing import Optional, List
import numpy as np
import cv2

logger = logging.getLogger(__name__)

class ClipSaver:
    """
    Handles saving video clips when an SOP violation occurs.
    Combines pre-event buffer frames with post-event frames.
    """
    def __init__(self, output_dir: Optional[str] = None, fps: int = 15):
        self.output_dir = output_dir or os.getenv("VIOLATIONS_DIR", "data/violations")
        self.fps = fps
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"ClipSaver: Created output directory at {output_dir}")

    def save_violation_clip(self, camera_id: str, frames: List[np.ndarray], 
                            timestamp: Optional[float] = None) -> str:
        """
        Saves a list of frames as an MP4 video.
        Returns the path to the saved file.
        """
        if not frames:
            logger.warning(f"ClipSaver [{camera_id}]: No frames provided to save.")
            return ""

        if timestamp is None:
            timestamp = time.time()
            
        time_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(timestamp))
        filename = f"{camera_id}_{time_str}.mp4"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Lấy FPS thực tế từ config hoặc dùng mặc định
            save_fps = self.fps
            logger.info(f"ClipSaver [{camera_id}]: Saving {len(frames)} frames to {filepath} at {save_fps} FPS...")
            
            # Sử dụng preset 'ultrafast' để giảm tải CPU tối đa khi nén (Cực quan trọng cho Laptop)
            # imageio ffmpeg support: https://imageio.readthedocs.io/en/stable/format_ffmpeg.html
            with imageio.get_writer(filepath, fps=save_fps, codec='libx264', 
                                   quality=None,  # Để dùng bitrate/preset
                                   ffmpeg_params=['-preset', 'ultrafast', '-crf', '28'],
                                   pixelformat='yuv420p', # Dùng tham số chính thức của imageio thay vì ép qua ffmpeg_params
                                   macro_block_size=1) as writer:
                for frame in frames:
                    # OpenCV uses BGR, imageio uses RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    writer.append_data(frame_rgb)
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            logger.info(f"ClipSaver [{camera_id}]: Clip saved successfully ({file_size:.2f} MB).")
            return filepath
            
        except Exception as e:
            logger.error(f"ClipSaver [{camera_id}]: Failed to save clip: {e}")
            return ""


class DowntimeRecorder:
    """
    Ghi hình video dừng máy (Downtime) theo luồng streaming nền.
    Ghi hình tối đa max_seconds (mặc định 120s = 2 phút đầu tiên tính từ lúc bắt đầu dừng máy).
    Lưu trực tiếp thành file MP4 định dạng H.264 (libx264) với preset ultrafast để không tốn RAM.
    """
    def __init__(self, camera_id: str, output_dir: Optional[str] = None, fps: int = 15, max_seconds: int = 120):
        import queue
        import threading
        self.camera_id = camera_id
        self.output_dir = output_dir or os.getenv("VIOLATIONS_DIR", "data/violations")
        self.fps = fps
        self.max_seconds = max_seconds
        self.max_frames = fps * max_seconds
        
        self.is_recording = False
        self.filepath = None
        self.start_time = 0.0
        self.frame_count = 0
        self._queue = None
        self._thread = None

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def start(self, start_time: Optional[float] = None) -> str:
        """Bắt đầu phiên ghi hình dừng máy."""
        import queue
        import threading
        if self.is_recording:
            return self.filepath

        self.start_time = start_time or time.time()
        time_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(self.start_time))
        filename = f"{self.camera_id}_downtime_{time_str}.mp4"
        self.filepath = os.path.join(self.output_dir, filename)
        self.frame_count = 0
        self.is_recording = True
        self._queue = queue.Queue(maxsize=60)

        def _worker():
            try:
                with imageio.get_writer(
                    self.filepath, fps=self.fps, codec='libx264',
                    quality=None,
                    ffmpeg_params=['-preset', 'ultrafast', '-crf', '28'],
                    pixelformat='yuv420p',
                    macro_block_size=1
                ) as writer:
                    while True:
                        frame = self._queue.get()
                        if frame is None:
                            break
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        writer.append_data(frame_rgb)
                
                if os.path.exists(self.filepath):
                    sz = os.path.getsize(self.filepath) / (1024 * 1024)
                    logger.info(f"DowntimeRecorder [{self.camera_id}]: Saved clip {self.filepath} ({sz:.2f} MB, {self.frame_count} frames)")
            except Exception as e:
                logger.error(f"DowntimeRecorder [{self.camera_id}] error writing clip: {e}")

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        logger.info(f"DowntimeRecorder [{self.camera_id}]: Started recording downtime (first {self.max_seconds}s) to {self.filepath}")
        return self.filepath

    def push_frame(self, frame: np.ndarray) -> bool:
        """Đẩy một frame vào hàng đợi ghi video. Trả về False nếu đã đủ 2 phút."""
        if not self.is_recording:
            return False
        if self.frame_count >= self.max_frames:
            self.stop()
            return False
        try:
            self._queue.put_nowait(frame.copy())
            self.frame_count += 1
            if self.frame_count >= self.max_frames:
                logger.info(f"DowntimeRecorder [{self.camera_id}]: Reached max frames ({self.max_frames} = {self.max_seconds}s). Stopping recording.")
                self.stop()
                return False
        except Exception:
            pass  # Drop frame nếu writer tạm thời quá tải, không bao giờ chặn main loop
        return True

    def stop(self) -> Optional[str]:
        """Kết thúc ghi hình và đóng file video."""
        if not self.is_recording:
            return self.filepath
        self.is_recording = False
        if self._queue is not None:
            self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        return self.filepath


