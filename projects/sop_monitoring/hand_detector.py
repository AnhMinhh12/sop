import numpy as np
import cv2
import logging
import os
from typing import List, Dict, Optional
from shared.inference_engine import InferenceEngine

logger = logging.getLogger(__name__)


class HandDetector:
    """
    Wrapper for YOLOv11 hand detection model.
    Uses InferenceEngine for shared, synchronized CPU inference.
    """
    def __init__(self, camera_id: str, confidence_threshold: Optional[float] = None,
                 iou_threshold: Optional[float] = None, model_path: Optional[str] = None):
        self.camera_id = camera_id
        
        from shared.services.config_loader import ConfigLoader
        config = ConfigLoader.load_config()
        yolo_cfg = config.get("models", {}).get("yolo", {})
        inference_cfg = config.get("inference", {})
        
        # Check camera specific config
        cameras = config.get("cameras", [])
        cam_cfg = {}
        for c in cameras:
            if c.get("id") == camera_id:
                cam_cfg = c
                break
                
        # Resolve confidence threshold
        if confidence_threshold is None or confidence_threshold == 0.15:
            confidence_threshold = cam_cfg.get("conf_threshold") or yolo_cfg.get("conf_threshold") or 0.25
            
        # Resolve IOU threshold
        if iou_threshold is None or iou_threshold == 0.3:
            iou_threshold = cam_cfg.get("iou_threshold") or yolo_cfg.get("iou_threshold") or 0.45
            
        self.conf_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        
        if model_path is None:
            model_path = yolo_cfg.get("weights")
            
        self.model_path = model_path
        
        num_threads = int(os.getenv("AI_MAX_THREADS", inference_cfg.get("num_threads", 4)))
        input_size = int(os.getenv("AI_INPUT_SIZE", yolo_cfg.get("input_size", 416)))
        
        self.engine = InferenceEngine(model_path=self.model_path, num_threads=num_threads, input_size=input_size)

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
        """Hậu xử lý YOLOv11 - Hỗ trợ cả 1 class (hand) và nhiều class (hand, product)."""
        output = np.squeeze(result["raw_output"][0])
        output = output.T # (8400, 4 + num_classes) -> [cx, cy, w, h, class0_conf, class1_conf, ...]
        
        num_classes = output.shape[1] - 4
        # Class mapping: 0=hand, 1=robot (arm công nghiệp), 2=sp (sản phẩm)
        if num_classes == 2:
            class_mapping = {0: "hand", 1: "sp"}
        else:
            class_mapping = {0: "hand", 1: "robot", 2: "sp"}
        
        all_boxes = []
        all_confs = []
        all_class_ids = []
        
        orig_h, orig_w = orig_shape
        ratio = result["ratio"]
        pad_left, pad_top = result["pad"]
        
        # Lọc và NMS riêng cho từng class
        for class_idx in range(num_classes):
            confidences = output[:, 4 + class_idx]
            mask = confidences > self.conf_threshold
            if not np.any(mask):
                continue
                
            class_output = output[mask]
            class_confs = confidences[mask]
            
            # Tọa độ hộp bao
            x1 = (class_output[:, 0] - class_output[:, 2] / 2 - pad_left) / ratio
            y1 = (class_output[:, 1] - class_output[:, 3] / 2 - pad_top) / ratio
            w = class_output[:, 2] / ratio
            h = class_output[:, 3] / ratio
            
            boxes = np.stack([x1, y1, w, h], axis=1).astype(int).tolist()
            confs = class_confs.astype(float).tolist()
            
            # NMS riêng cho từng lớp đối tượng
            indices = cv2.dnn.NMSBoxes(boxes, confs, self.conf_threshold, self.iou_threshold)
            if len(indices) > 0:
                for i in indices.flatten():
                    box = boxes[i]
                    all_boxes.append([box[0], box[1], box[0] + box[2], box[1] + box[3]])
                    all_confs.append(confs[i])
                    all_class_ids.append(class_idx)
                    
        final_detections = []
        for bbox, conf, class_idx in zip(all_boxes, all_confs, all_class_ids):
            cx = ((bbox[0] + bbox[2]) / 2) / orig_w
            cy = ((bbox[1] + bbox[3]) / 2) / orig_h
            final_detections.append({
                "bbox": bbox,
                "confidence": conf,
                "class": class_mapping.get(class_idx, "unknown"),
                "centroid": [cx, cy]
            })
            
        return final_detections
