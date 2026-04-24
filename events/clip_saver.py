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
    def __init__(self, output_dir: str = "data/violations", fps: int = 15):
        self.output_dir = output_dir
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

