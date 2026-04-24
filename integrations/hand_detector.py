import numpy as np
import cv2
import logging
from typing import List, Dict, Optional
from pipelines.inference_engine import InferenceEngine

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
        """Hậu xử lý YOLOv11 - Bù trừ Letterbox để Box khớp hoàn toàn."""
        output = np.squeeze(result["raw_output"][0]) 
        output = output.T # (8400, 5) -> [cx, cy, w, h, conf]
        
        orig_h, orig_w = orig_shape
        ratio = result["ratio"]
        pad_left, pad_top = result["pad"]

        boxes = []
        confidences = []

        for i in range(len(output)):
            conf = output[i, 4]
            if conf > self.conf_threshold:
                cx, cy, w, h = output[i, :4]
                
                # CÔNG THỨC CHUẨN: (Tọa độ AI - Phần đệm lề) / Tỉ lệ thu phóng
                x1 = (cx - w / 2 - pad_left) / ratio
                y1 = (cy - h / 2 - pad_top) / ratio
                bw = w / ratio
                bh = h / ratio

                # Chỉ lấy các box nằm trong khung hình và có kích thước hợp lý
                if bw > 2 and bh > 2:
                    boxes.append([int(x1), int(y1), int(bw), int(bh)])
                    confidences.append(float(conf))

        if not boxes:
            return []

        # Non-Maximum Suppression
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.iou_threshold)

        final_detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                final_detections.append({
                    "bbox": [x, y, x + w, y + h],
                    "confidence": confidences[i]
                })
            
        return final_detections
