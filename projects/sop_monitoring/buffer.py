import numpy as np
import logging
from collections import deque
from typing import List

logger = logging.getLogger(__name__)

class FrameRingBuffer:
    """
    A synchronized ring buffer to store the last N seconds of frames in memory.
    Used for pre-event video recording.
    """
    def __init__(self, fps: int, seconds: int):
        self.fps = fps
        self.seconds = seconds
        self.max_frames = fps * seconds
        
        # Hàng đợi vòng với độ dài cố định
        self.buffer = deque(maxlen=self.max_frames)
        logger.info(f"FrameRingBuffer: Initialized for {seconds}s at {fps}fps (max {self.max_frames} frames).")

    def push(self, frame: np.ndarray):
        """Adds a new frame to the buffer. Older frames are automatically dropped."""
        # Lưu ý: OpenCV frames nên được copy nếu buffer được truy cập từ nhiều thread,
        # nhưng ở đây ta copy khi trích xuất sẽ hiệu quả hơn.
        self.buffer.append(frame)

    def get_all(self) -> List[np.ndarray]:
        """Returns all frames currently in the buffer as a list."""
        return list(self.buffer)

    def clear(self):
        """Clears the buffer."""
        self.buffer.clear()

    def __len__(self):
        return len(self.buffer)
