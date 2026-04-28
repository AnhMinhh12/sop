import cv2
import numpy as np
import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class HandState:
    """Individual hand tracking state with prediction and smoothing."""
    def __init__(self, side: str, max_history: int = 10):
        self.side = side
        self.history = []  # List of normalized coordinates [(x, y), ...]
        self.max_history = max_history
        self.velocity = np.array([0.0, 0.0])
        self.last_seen = time.time()
        self.is_lost = False
        self.prediction_count = 0
        self.max_predictions = 5
        
    def update(self, coord: Optional[Tuple[float, float]]):
        now = time.time()
        if coord:
            if self.history:
                prev = self.history[-1]
                self.velocity = np.array([coord[0] - prev[0], coord[1] - prev[1]])
            
            self.history.append(coord)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            
            self.last_seen = now
            self.is_lost = False
            self.prediction_count = 0
        else:
            if self.history and self.prediction_count < self.max_predictions:
                prev = self.history[-1]
                predicted = (prev[0] + self.velocity[0], prev[1] + self.velocity[1])
                predicted = (max(0.0, min(1.0, predicted[0])), max(0.0, min(1.0, predicted[1])))
                
                self.history.append(predicted)
                if len(self.history) > self.max_history:
                    self.history.pop(0)
                
                self.prediction_count += 1
                self.is_lost = False
            else:
                self.is_lost = True

    @property
    def current_pos(self) -> Optional[Tuple[float, float]]:
        return self.history[-1] if self.history else None

class TrackingEngine:
    """
    Tầng 1: Multi-Zone Mapping & Hand Tracking.
    Hỗ trợ dự đoán quán tính và chống nhiễu.
    """
    def __init__(self, sop_config: dict):
        self.config = sop_config
        self.zones = {}
        self.hands = {
            "left": HandState("left"),
            "right": HandState("right")
        }
        
        raw_zones = sop_config.get("zones", {})
        for name, data in raw_zones.items():
            pts = data.get("pts") if isinstance(data, dict) else data
            if pts:
                self.zones[name] = {"name": name, "poly": np.array(pts, np.float32)}
                
        logger.info(f"TrackingEngine: Đã nạp lại {len(self.zones)} khu vực.")

    def update(self, hands_data: list, frame_w: int = 1280, frame_h: int = 720) -> dict:
        detections = {"left": None, "right": None}
        for hand in hands_data:
            side = hand.get("label", "any").lower()
            bbox = hand.get("bbox")
            if side in detections and bbox:
                cx = (bbox[0] + bbox[2]) / 2 / frame_w
                cy = bbox[3] / frame_h # Wrist centroid logic
                detections[side] = (cx, cy)

        for side in ["left", "right"]:
            self.hands[side].update(detections[side])

        zone_snapshot = {z_name: {"count": 0, "hands": []} for z_name in self.zones}
        for side, state in self.hands.items():
            pos = state.current_pos
            if pos and not state.is_lost:
                for z_name, z_data in self.zones.items():
                    if cv2.pointPolygonTest(z_data["poly"], (pos[0], pos[1]), False) >= 0:
                        zone_snapshot[z_name]["count"] += 1
                        zone_snapshot[z_name]["hands"].append({
                            "label": side, 
                            "predicted": state.prediction_count > 0,
                            "pos": pos
                        })
                    
        return zone_snapshot

    def get_hand_states(self) -> Dict:
        return {
            side: {
                "pos": h.current_pos,
                "is_lost": h.is_lost,
                "is_predicted": h.prediction_count > 0
            } for side, h in self.hands.items()
        }

    def get_zone_polygons(self):
        return {name: z_data["poly"].tolist() for name, z_data in self.zones.items()}
