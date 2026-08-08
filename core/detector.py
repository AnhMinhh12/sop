import numpy as np
import cv2
import logging
import os
from typing import List, Dict, Optional, Tuple
from shared.inference import InferenceEngine

logger = logging.getLogger(__name__)

class HandDetector:
    """
    Wrapper for YOLOv8/v11 hand detection model.
    Runs ONNX inference and post-processes results,
    extracting precise fingertips based on white finger cots (HSV segmentation).
    """
    def __init__(self, model_path: str, confidence_threshold: float = 0.25, iou_threshold: float = 0.45, hand_class_id: int = 0):
        self.model_path = os.path.abspath(model_path)
        self.conf_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.hand_class_id = hand_class_id
        self.engine = InferenceEngine(model_path=self.model_path, num_threads=4, input_size=640)

    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Runs inference and returns hands with their fingertips, along with products.
        Returns:
            List[Dict]: [
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float,
                    "class": str ("hand" or "sp"),
                    "centroid": [cx, cy],
                    "fingertip": [fx, fy],      # Precise fingertip coordinates (hands only)
                    "fingertip_detected": bool   # Whether white cot was found (hands only)
                }
            ]
        """
        if self.engine is None or self.engine.session is None:
            return []

        result = self.engine.infer(frame)
        if result is None or "raw_output" not in result:
            return []

        detections = self._postprocess(result, frame.shape[:2])
        
        # For each detection, if it's a hand, extract fingertip using white cot HSV segmentation
        h_frame, w_frame = frame.shape[:2]
        for det in detections:
            bbox = det["bbox"]
            if det["class"] != "hand":
                # Đối với sản phẩm, vị trí đầu ngón tay ảo chính là tâm đối tượng
                det["fingertip"] = det["centroid"]
                det["fingertip_detected"] = False
                continue

            x1 = max(0, int(bbox[0]))
            y1 = max(0, int(bbox[1]))
            x2 = min(w_frame, int(bbox[2]))
            y2 = min(h_frame, int(bbox[3]))

            # Crop the hand area
            if (x2 - x1) > 5 and (y2 - y1) > 5:
                hand_crop = frame[y1:y2, x1:x2]
                # Convert to HSV
                hsv = cv2.cvtColor(hand_crop, cv2.COLOR_BGR2HSV)
                
                # White color bounds in HSV
                # Saturation is low, Value (Brightness) is high
                lower_white = np.array([0, 0, 180], dtype=np.uint8)
                upper_white = np.array([180, 60, 255], dtype=np.uint8)
                mask = cv2.inRange(hsv, lower_white, upper_white)
                
                # Find contours in the mask
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                fingertip = None
                hand_area = (x2 - x1) * (y2 - y1)
                
                if contours:
                    # Filter contours to find the white cot
                    valid_cots = []
                    for c in contours:
                        area = cv2.contourArea(c)
                        # A valid cot should be small but not tiny noise, and not the whole hand
                        if 5 < area < 0.4 * hand_area:
                            valid_cots.append((c, area))
                    
                    if valid_cots:
                        # Select the largest valid white blob
                        best_cot, _ = max(valid_cots, key=lambda x: x[1])
                        M = cv2.moments(best_cot)
                        if M["m00"] > 0:
                            cx_crop = M["m10"] / M["m00"]
                            cy_crop = M["m01"] / M["m00"]
                            # Map back to global frame coordinates
                            ft_x = x1 + cx_crop
                            ft_y = y1 + cy_crop
                            fingertip = [ft_x / w_frame, ft_y / h_frame]
                
                if fingertip is not None:
                    det["fingertip"] = fingertip
                    det["fingertip_detected"] = True
                else:
                    # Sử dụng top_center (cạnh trên của bounding box) làm fingertip dự phòng
                    # vì tay công nhân đi từ dưới màn hình lên, ngón tay nằm ở phía trên bbox
                    det["fingertip"] = [det["centroid"][0], y1 / h_frame]
                    det["fingertip_detected"] = False
            else:
                det["fingertip"] = [det["centroid"][0], det["bbox"][1] / h_frame]
                det["fingertip_detected"] = False

        return detections

    def _postprocess(self, result: Dict, orig_shape: tuple) -> List[Dict]:
        """Post-processes YOLOv8/v11 multi-class output."""
        output = np.squeeze(result["raw_output"][0])
        if len(output.shape) == 1:
            output = np.expand_dims(output, axis=1)
        elif output.shape[0] < output.shape[1]:
            output = output.T # Transpose to (8400, 4 + num_classes)

        all_boxes = []
        all_confs = []
        
        orig_h, orig_w = orig_shape
        ratio = result["ratio"]
        pad_left, pad_top = result["pad"]
        
        # Get class scores and determine the highest score per box
        class_scores = output[:, 4:]
        num_classes = class_scores.shape[1]
        
        class_ids = np.argmax(class_scores, axis=1)
        confidences = np.max(class_scores, axis=1)
        
        mask = confidences > self.conf_threshold
        if not np.any(mask):
            return []
            
        class_output = output[mask]
        class_ids = class_ids[mask]
        class_confs = confidences[mask]
        
        # Transform coordinates
        x1 = (class_output[:, 0] - class_output[:, 2] / 2 - pad_left) / ratio
        y1 = (class_output[:, 1] - class_output[:, 3] / 2 - pad_top) / ratio
        w = class_output[:, 2] / ratio
        h = class_output[:, 3] / ratio
        
        boxes = np.stack([x1, y1, w, h], axis=1).astype(int).tolist()
        confs = class_confs.astype(float).tolist()
        c_ids = class_ids.astype(int).tolist()
        
        # Run NMS
        indices = cv2.dnn.NMSBoxes(boxes, confs, self.conf_threshold, self.iou_threshold)
        
        final_detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                c_id = c_ids[i]
                
                # Nếu model có nhiều class, map class_id khác hand_class_id thành product hoặc robot
                c_name = "hand"
                if num_classes == 2:
                    if c_id == 1:
                        c_name = "sp"
                elif num_classes > 2:
                    class_mapping = {0: "hand", 1: "robot", 2: "sp"}
                    c_name = class_mapping.get(c_id, "unknown")
                
                box = boxes[i]
                bbox = [box[0], box[1], box[0] + box[2], box[1] + box[3]]
                # centroid = tâm bbox (dùng để tracking velocity)
                cx = ((bbox[0] + bbox[2]) / 2) / orig_w
                cy = ((bbox[1] + bbox[3]) / 2) / orig_h
                # bottom_center = giữa cạnh dưới bbox
                bx = cx
                by = bbox[3] / orig_h  # cạnh dưới của bbox

                final_detections.append({
                    "bbox": bbox,
                    "confidence": confs[i],
                    "class": c_name,
                    "centroid": [cx, cy],
                    "bottom_center": [bx, by]
                })
                
        return final_detections

