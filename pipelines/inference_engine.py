import onnxruntime as ort
import numpy as np
import cv2
import threading
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    Singleton class to handle centralized CPU inference for all cameras.
    Uses a threading lock to serialize ONNX inference calls (no queue race condition).
    Optimized for Intel Xeon processors using ONNX Runtime.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InferenceEngine, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional["InferenceEngine"]:
        """Returns the singleton instance, or None if not yet initialized."""
        return cls._instance

    def __init__(self, model_path: Optional[str] = None, num_threads: int = 4, input_size: int = 416):
        if self._initialized:
            return

        if model_path is None:
            logger.error("InferenceEngine: model_path is required for initialization")
            return

        self.model_path = model_path
        self.num_threads = num_threads
        self.input_size = input_size
        self._infer_lock = threading.Lock()

        # Cấu hình ONNX Runtime cho Intel Xeon
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = num_threads
        sess_options.inter_op_num_threads = 1  # Chỉ 1 inter-op thread vì đã serialize bằng lock
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        try:
            logger.info(f"InferenceEngine: Loading model from {model_path}...")
            self.session = ort.InferenceSession(
                model_path, sess_options, providers=['CPUExecutionProvider']
            )
            # TỰ ĐỘNG LẤY KÍCH THƯỚC TỪ MODEL
            input_info = self.session.get_inputs()[0]
            self.input_name = input_info.name
            # Thường input là [1, 3, 640, 640]
            self.input_size = input_info.shape[2] 
            
            logger.info(f"InferenceEngine: Model loaded. AUTO-DETECTED Input Size: {self.input_size}")
        except Exception as e:
            logger.error(f"InferenceEngine: Failed to load model: {e}")
            self.session = None

        self._initialized = True

    def infer(self, frame: np.ndarray) -> Optional[Dict]:
        """
        Runs synchronous inference on a single frame.
        Thread-safe via lock — only one inference runs at a time across all cameras.
        Returns: {"raw_output": list, "ratio": float, "pad": tuple, "latency_ms": float}
        """
        if self.session is None:
            return None

        with self._infer_lock:
            try:
                blob, ratio, pad = self._preprocess(frame)

                start_time = time.time()
                outputs = self.session.run(None, {self.input_name: blob})
                infer_time = (time.time() - start_time) * 1000

                return {
                    "raw_output": outputs,
                    "ratio": ratio,
                    "pad": pad,
                    "latency_ms": infer_time,
                }
            except Exception as e:
                logger.error(f"InferenceEngine: Inference error: {e}")
                return None

    def _preprocess(self, frame: np.ndarray) -> tuple:
        """
        Resize with Letterbox (keep aspect ratio) and normalize.
        Returns: (processed_img, ratio, (pad_left, pad_top))
        """
        shape = frame.shape[:2]  # height, width
        r = min(self.input_size / shape[0], self.input_size / shape[1])

        new_unproc = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw, dh = self.input_size - new_unproc[0], self.input_size - new_unproc[1]
        dw, dh = dw / 2, dh / 2  # split padding

        if shape[::-1] != new_unproc:
            img = cv2.resize(frame, new_unproc, interpolation=cv2.INTER_LINEAR)
        else:
            img = frame

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right,
                                 cv2.BORDER_CONSTANT, value=(114, 114, 114))

        # Color space and normalize
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)

        return img, r, (left, top)

    def stop(self):
        """Cleanup (no background thread to stop in synchronous mode)."""
        logger.info("InferenceEngine: Stopped.")
