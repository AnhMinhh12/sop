import cv2
import numpy as np
from typing import List, Dict, Optional, Any

class Annotator:
    """
    Utility class to draw AI detections and keypoints on frames.
    """
    COLOR_HAND = (0, 255, 0)
    COLOR_KEYPOINT = (0, 0, 255)
    COLOR_SKELETON = (255, 0, 0)
    COLOR_TEXT = (255, 255, 255)

    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),      # Ngón cái
        (0, 5), (5, 6), (6, 7), (7, 8),      # Ngón trỏ
        (5, 9), (9, 10), (10, 11), (11, 12), # Ngón giữa
        (9, 13), (13, 14), (14, 15), (15, 16), # Ngón nhẫn
        (13, 17), (17, 18), (18, 19), (19, 20), # Ngón út
        (0, 17) # Nối gan bàn tay
    ]

    @staticmethod
    def draw_zones(frame: np.ndarray, zones: Dict[str, Any]):
        """Vẽ các vùng ROI (Chữ nhật hoặc Đa giác) lên màn hình."""
        h, w = frame.shape[:2]
        for name, pts in zones.items():
            color = (255, 100, 0)
            if isinstance(pts[0], list): # Nếu là Đa giác (Polygon)
                poly_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in pts], np.int32)
                cv2.polylines(frame, [poly_pts], True, color, 2)
                cv2.putText(frame, name, (poly_pts[0][0], poly_pts[0][1] - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else: # Nếu là Hình chữ nhật [x, y, w, h]
                zx, zy, zw, zh = pts
                p1 = (int(zx * w), int(zy * h))
                p2 = (int((zx + zw) * w), int((zy + zh) * h))
                cv2.rectangle(frame, p1, p2, color, 2)
                cv2.putText(frame, name, (p1[0], p1[1] - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    @staticmethod
    def draw_keypoints(frame: np.ndarray, landmarks, label: str = "left") -> np.ndarray:
        """Vẽ khung xương tay từ MediaPipe."""
        if landmarks is None:
            return frame
        h, w = frame.shape[:2]
        color = (255, 120, 0) if label == "left" else (0, 230, 20)
        for connection in Annotator.HAND_CONNECTIONS:
            p1_idx, p2_idx = connection
            lm1, lm2 = landmarks.landmark[p1_idx], landmarks.landmark[p2_idx]
            pt1 = (int(lm1.x * w), int(lm1.y * h))
            pt2 = (int(lm2.x * w), int(lm2.y * h))
            cv2.line(frame, pt1, pt2, color, 1)
        for lm in landmarks.landmark:
            px, py = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (px, py), 2, (0, 0, 255), -1)
        return frame

    @staticmethod
    def draw_sop_info(frame: np.ndarray, step_name: str, status: str, progress: float) -> np.ndarray:
        h_bar = 44
        w = frame.shape[1]
        color = (0, 255, 0) if status in ["correct", "completed"] else (0, 0, 255)
        bar_w = int((w - 20) * progress / 100)
        cv2.rectangle(frame, (10, h_bar - 4), (10 + bar_w, h_bar), color, -1)
        return frame
