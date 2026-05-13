import numpy as np
import cv2
import logging
from typing import List, Dict, Optional
from shared.inference_engine import InferenceEngine

logger = logging.getLogger(__name__)


class HandDetector:
    """
    Wrapper for YOLOv11 hand detection model.
    Uses InferenceEngine for shared, synchronized CPU inference.
    """
    def __init__(self, camera_id: str, confidence_threshold: float = 0.2,
                 iou_threshold: float = 0.3):
        self.camera_id = camera_id
        self.conf_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.engine = InferenceEngine.get_instance()

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Runs synchronous inference and post-processes results.
        Returns a list of detected hands: [{"bbox": [x1, y1, x2, y2], "confidence": float}]
        """
        if self.engine is None:
            logger.warning(f"HandDetector [{self.camera_id}]: No InferenceEngine available.")
            return []

        # Gọi inference đồng bộ — kết quả luôn khớp với frame hiện tại
        result = self.engine.infer(frame)

        if result is None or "raw_output" not in result:
            return []

        # Hậu xử lý
        detections = self._postprocess(result, frame.shape[:2])
        return detections

    def _postprocess(self, result: Dict, orig_shape: tuple) -> List[Dict]:
        """Hậu xử lý YOLOv11 - Tối ưu hóa bằng NumPy Vectorization."""
        output = np.squeeze(result["raw_output"][0])
        output = output.T # (8400, 5) -> [cx, cy, w, h, conf]
        
        # 1. Lọc theo ngưỡng confidence bằng NumPy (Nhanh hơn vòng lặp Python)
        confidences = output[:, 4]
        mask = confidences > self.conf_threshold
        output = output[mask]
        confidences = confidences[mask]

        if len(output) == 0:
            return []

        orig_h, orig_w = orig_shape
        ratio = result["ratio"]
        pad_left, pad_top = result["pad"]

        # 2. Vectorized Box Conversion: (Tọa độ AI - Phần đệm lề) / Tỉ lệ thu phóng
        # x_center = output[:, 0], y_center = output[:, 1], width = output[:, 2], height = output[:, 3]
        x1 = (output[:, 0] - output[:, 2] / 2 - pad_left) / ratio
        y1 = (output[:, 1] - output[:, 3] / 2 - pad_top) / ratio
        w = output[:, 2] / ratio
        h = output[:, 3] / ratio

        # Chuyển thành list [x, y, w, h] cho NMS
        boxes = np.stack([x1, y1, w, h], axis=1).astype(int).tolist()
        conf_list = confidences.astype(float).tolist()

        # 3. Non-Maximum Suppression
        indices = cv2.dnn.NMSBoxes(boxes, conf_list, self.conf_threshold, self.iou_threshold)

        final_detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                box = boxes[i]
                final_detections.append({
                    "bbox": [box[0], box[1], box[0] + box[2], box[1] + box[3]],
                    "confidence": conf_list[i]
                })
            
        return final_detections
