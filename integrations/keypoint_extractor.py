import cv2
import mediapipe as mp
import numpy as np
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class KeypointExtractor:
    """
    Wrapper for MediaPipe Hands to extract 21 keypoints from a hand image.
    Optimized for high-performance CPU (Xeon).
    """
    def __init__(self, static_image_mode: bool = False, max_num_hands: int = 2):
        self.mp_hands = mp.solutions.hands
        # Model Complexity 1 cho độ chính xác cao nhất trên CPU
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            model_complexity=1,
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3
        )

    def extract(self, frame: np.ndarray, detections: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Trích xuất Tâm bàn tay và phân loại Trái/Phải.
        Trả về: [{'label': 'left'/'right', 'centroid': [x, y], 'landmarks': ...}]
        """
        if frame is None:
            return []
            
        h, w = frame.shape[:2]
        # Chuyển sang RGB cho MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)

        extracted_hands = []
        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Lấy nhãn Trái/Phải (MediaPipe bị ngược nên ta đảo lại cho đúng thực tế camera)
                label = results.multi_handedness[idx].classification[0].label.lower()
                # MediaPipe mặc định coi ảnh soi gương, ta đảo lại cho đúng với góc nhìn camera
                label = "right" if label == "left" else "left"
                
                # Tính tâm bàn tay (wrist và middle finger base)
                wrist = hand_landmarks.landmark[0]
                middle_base = hand_landmarks.landmark[9]
                
                cx = (wrist.x + middle_base.x) / 2
                cy = (wrist.y + middle_base.y) / 2
                
                extracted_hands.append({
                    "label": label,
                    "centroid": [cx, cy],
                    "landmarks": hand_landmarks
                })

        return extracted_hands

    def close(self):
        self.hands.close()
