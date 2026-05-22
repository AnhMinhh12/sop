import cv2
import numpy as np
from typing import List, Dict, Optional, Any

class Annotator:
    """
    Utility class to draw AI detections and keypoints on frames.
    """
    COLOR_HAND = (0, 255, 0)
    COLOR_TEXT = (255, 255, 255)

    @staticmethod
    def draw_zones(frame: np.ndarray, zones: Dict[str, Any]):
        """Vẽ các vùng ROI (Chữ nhật hoặc Đa giác) lên màn hình."""
        h, w = frame.shape[:2]
        for name, pts in zones.items():
            color = (255, 100, 0)
            if isinstance(pts[0], list): # Nếu là Đa giác (Polygon)
                poly_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts], np.int32)
                cv2.polylines(frame, [poly_pts], True, color, 2)
            else: # Nếu là Hình chữ nhật [x, y, w, h]
                zx, zy, zw, zh = pts
                p1 = (int(zx * w), int(zy * h))
                p2 = (int((zx + zw) * w), int((zy + zh) * h))
                cv2.rectangle(frame, p1, p2, color, 2)

    @staticmethod
    def draw_sop_info(frame: np.ndarray, step_name: str, status: str, progress: float) -> np.ndarray:
        h_bar = 44
        w = frame.shape[1]
        color = (0, 255, 0) if status in ["correct", "completed"] else (0, 0, 255)
        bar_w = int((w - 20) * progress / 100)
        cv2.rectangle(frame, (10, h_bar - 4), (10 + bar_w, h_bar), color, -1)
        return frame
