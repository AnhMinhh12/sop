import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """
    Normalizes hand keypoints for training and inference.
    Input: Flat array of 63 values (21 landmarks * 3 coords).
    Output: Normalized vector of 63 values.
    """
    @staticmethod
    def normalize_hand_keypoints(keypoints: np.ndarray) -> Optional[np.ndarray]:
        """
        Normalizes 1 or 2 hands. Input: 63 or 126 values.
        """
        if keypoints is None:
            return None
            
        if len(keypoints) == 63:
            return FeatureEngineer._normalize_single_hand(keypoints)
        elif len(keypoints) == 126:
            # Chuẩn hóa tay trái (0-63) và tay phải (63-126) riêng biệt
            left_hand = FeatureEngineer._normalize_single_hand(keypoints[0:63])
            right_hand = FeatureEngineer._normalize_single_hand(keypoints[63:126])
            
            # Ghép lại thành vector 126
            return np.concatenate([
                left_hand if left_hand is not None else np.zeros(63, dtype=np.float32),
                right_hand if right_hand is not None else np.zeros(63, dtype=np.float32)
            ])
        
        return None

    @staticmethod
    def _normalize_single_hand(hand_vec: np.ndarray) -> Optional[np.ndarray]:
        """Helper to normalize a single 63-dim hand vector."""
        if hand_vec is None or len(hand_vec) != 63 or np.all(hand_vec == 0):
            return None
            
        coords = hand_vec.reshape(21, 3)
        wrist = coords[0]
        normalized_coords = coords - wrist
        
        dist = np.linalg.norm(normalized_coords[9]) # Middle Finger MCP
        if dist > 0:
            normalized_coords = normalized_coords / dist
            
        return normalized_coords.flatten()
