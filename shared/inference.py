import onnxruntime as ort
import numpy as np
import cv2
import threading
import time
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class InferenceEngine:
    """
    Centralized CPU inference helper for ONNX models.
    Thread-safe and optimized for CPU execution.
    """
    def __init__(self, model_path: str, num_threads: int = 4, input_size: int = 640):
        self.model_path = os.path.abspath(model_path)
        self.num_threads = num_threads
        self.input_size = input_size
        self._infer_lock = threading.Lock()

        # Session options for CPU optimization
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = num_threads
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            logger.info(f"Loading ONNX model from {self.model_path}...")
            self.session = ort.InferenceSession(
                self.model_path, sess_options, providers=['CPUExecutionProvider']
            )
            input_info = self.session.get_inputs()[0]
            self.input_name = input_info.name
            
            # Auto-detect input size from model if shape is static
            if isinstance(input_info.shape[2], int):
                self.input_size = input_info.shape[2]
            
            logger.info(f"ONNX model loaded successfully. Input size: {self.input_size}")
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self.session = None

    def infer(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Runs synchronous inference on a frame.
        """
        if self.session is None:
            return None

        with self._infer_lock:
            try:
                blob, ratio, pad = self._preprocess(frame)

                start_time = time.time()
                outputs = self.session.run(None, {self.input_name: blob})
                latency = (time.time() - start_time) * 1000

                return {
                    "raw_output": outputs,
                    "ratio": ratio,
                    "pad": pad,
                    "latency_ms": latency
                }
            except Exception as e:
                logger.error(f"Inference run failed: {e}")
                return None

    def _preprocess(self, frame: np.ndarray) -> tuple:
        """
        Resize image with letterboxing and prepare blob.
        """
        shape = frame.shape[:2] # height, width
        r = min(self.input_size / shape[0], self.input_size / shape[1])

        new_unproc = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw, dh = self.input_size - new_unproc[0], self.input_size - new_unproc[1]
        dw, dh = dw / 2, dh / 2

        if shape[::-1] != new_unproc:
            img = cv2.resize(frame, new_unproc, interpolation=cv2.INTER_LINEAR)
        else:
            img = frame

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right,
                                 cv2.BORDER_CONSTANT, value=(114, 114, 114))

        # Convert to blob: BGR to RGB, scale 1/255.0, HWC to CHW
        blob = cv2.dnn.blobFromImage(img, scalefactor=1.0/255.0, swapRB=True)

        return blob, r, (left, top)
