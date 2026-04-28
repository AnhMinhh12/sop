import cv2
import threading
import time
import logging
import os
import numpy as np
import psutil
from typing import Dict, Any, Optional

from integrations.rtsp_stream import RTSPStream
from integrations.hand_detector import HandDetector
from pipelines.frame_buffer import FrameRingBuffer
from core.spatial_engine import SpatialEngine
from core.violation_detector import ViolationDetector
from services.annotator import Annotator
from events.audio_alert import AudioAlert
from events.clip_saver import ClipSaver
from db.queries import EventQueries

logger = logging.getLogger(__name__)

# Cache process object — tái sử dụng thay vì tạo mới mỗi lần profiling
_process = psutil.Process(os.getpid())


from core.spatial_engine import SpatialEngine

class FrameProcessor:
    """
    Orchestrates the entire pipeline for a single camera.
    Reform: Uses SpatialEngine (Zone-based) instead of LSTM.
    """
    def __init__(self, camera_config: Dict[str, Any],
                 spatial_engine: SpatialEngine,
                 violation_detector: ViolationDetector,
                 audio_alert: Optional[AudioAlert],
                 clip_saver: ClipSaver):

        self.cam_id = camera_config["id"]
        self.rtsp_url = camera_config["rtsp_url"]
        self.fps = camera_config.get("fps_cap", 25)
        self.frame_delay = 1.0 / self.fps

        res = camera_config.get("resolution", [1280, 720])
        self._target_w = res[0]
        self._target_h = res[1]

        # Integrations
        self.stream = RTSPStream(self.cam_id, self.rtsp_url, self.fps)
        self.hand_detector = HandDetector(self.cam_id, confidence_threshold=0.15)
        # BỎ MediaPipe KeypointExtractor

        # New Engine
        self.spatial_engine = spatial_engine
        self.violation_detector = violation_detector
        
        self.ring_buffer = FrameRingBuffer(self.fps, 20)  # Tăng lên 20s để chứa 10s trước và 10s sau
        self.audio_alert = audio_alert
        self.clip_saver = clip_saver

        self.running = False
        self.current_processed_frame = None
        self.latest_status = {"sop_status": "idle", "progress_percent": 0}
        self._loop_count = 0
        self._cached_hands = []
        self.thread = None

    def start(self):
        if self.running: return
        self.running = True
        self.stream.start()
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
        logger.info(f"FrameProcessor [{self.cam_id}]: YOLO-ONLY Engine Started.")

    def _process_loop(self):
        from app import emit_step_update

        while self.running:
            loop_start = time.time()
            frame = self.stream.get_frame()
            if frame is None:
                time.sleep(0.01); continue

            # --- OPTIMIZATION: Hạ độ phân giải xuống HD để mượt mà (Lag fix) ---
            frame = cv2.resize(frame, (1280, 720))
            self._target_w, self._target_h = 1280, 720

            self.ring_buffer.push(frame)
            display_frame = frame.copy()
            
            # --- AI PROCESSING (YOLO ONLY) ---
            # Tối ưu: Chỉ chạy AI mỗi 2 frame để đảm bảo video mượt mà (Skip frame)
            hands_data = self._cached_hands
            
            if self._loop_count % 2 == 0:
                detections = self.hand_detector.detect(frame)
                
                # 2. Phân loại Trái/Phải dựa trên tọa độ X
                new_hands_data = []
                if detections:
                    # Sắp xếp các box theo thứ tự từ trái sang phải
                    sorted_dets = sorted(detections, key=lambda x: x["bbox"][0])
                    
                    if len(sorted_dets) == 1:
                        # Nếu chỉ thấy 1 tay, dựa vào vị trí so với tâm màn hình (Đã đảo ngược)
                        cx = (sorted_dets[0]["bbox"][0] + sorted_dets[0]["bbox"][2]) / 2
                        label = "right" if cx < (self._target_w / 2) else "left"
                        new_hands_data.append({
                            "label": label,
                            "centroid": [cx / self._target_w, (sorted_dets[0]["bbox"][1] + sorted_dets[0]["bbox"][3]) / (2 * self._target_h)],
                            "bbox": sorted_dets[0]["bbox"]
                        })
                    elif len(sorted_dets) >= 2:
                        # Nếu thấy 2 tay trở lên (Đã đảo ngược)
                        for i, det in enumerate([sorted_dets[0], sorted_dets[-1]]):
                            label = "right" if i == 0 else "left"
                            cx = (det["bbox"][0] + det["bbox"][2]) / 2
                            cy = (det["bbox"][1] + det["bbox"][3]) / 2
                            new_hands_data.append({
                                "label": label,
                                "centroid": [cx / self._target_w, cy / self._target_h],
                                "bbox": det["bbox"]
                            })
                
                hands_data = new_hands_data
                self._cached_hands = hands_data

            self._cached_hands = hands_data

            # 3. Spatial Logic Update
            self.latest_status = self.spatial_engine.update(hands_data)
            
            # 4. Check Violation
            violation = self.violation_detector.analyze(self.latest_status)
            if violation:
                self._handle_violation(violation)

            # 5. Annotation (Vẽ Box thay vì Xương)
            Annotator.draw_zones(display_frame, self.spatial_engine.zones)
            for h in self._cached_hands:
                bbox = h["bbox"]
                color = (0, 255, 255) if h["label"] == "left" else (0, 230, 20)
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
                cv2.putText(display_frame, h["label"].upper(), (int(bbox[0]), int(bbox[1])-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            self.current_processed_frame = display_frame
            self._loop_count += 1
            
            # 6. Socket Update - emit ngay khi cycle completed, khong cho moi 5 frame
            is_completed = self.latest_status.get("sop_status") == "completed"
            if is_completed or self._loop_count % 5 == 0:
                emit_step_update(self.cam_id, self.latest_status, self.latest_status["hands_info"])

            elapsed = time.time() - loop_start
            time.sleep(max(0, self.frame_delay - elapsed))

    def _handle_violation(self, violation: Dict):
        """Xử lý vi phạm: Đợi 10s để lấy đủ post-event frames rồi mới lưu."""
        def background_task():
            # 1. Phát âm thanh cảnh báo ngay lập tức
            if self.audio_alert: self.audio_alert.trigger()
            
            # 2. Emit SocketIO ngay để dashboard hiển thị đỏ rực và thông báo
            from app import emit_violation
            emit_violation(self.cam_id, violation)
            
            # 3. Đợi 10 giây để thu thập phần 'sau lỗi' vào ring buffer
            logger.info(f"FrameProcessor [{self.cam_id}]: Violation detected. Waiting 10s for post-event frames...")
            time.sleep(10)
            
            # 4. Lấy toàn bộ frames (Lúc này buffer chứa 10s trước + 10s sau)
            frames_to_save = self.ring_buffer.get_all()
            
            # 5. Lưu clip
            clip_path = self.clip_saver.save_violation_clip(self.cam_id, frames_to_save)
            
            # 6. Ghi log vào DB với đường dẫn clip chính xác
            EventQueries.log_event(
                camera_id=self.cam_id, 
                violation_type=violation.get("violation_type", "unknown"),
                step_detected=violation.get("detected_step", "N/A"), 
                expected_step=violation.get("expected_step"),
                sop_status="violation", 
                confidence=violation.get("confidence", 1.0), 
                clip_path=clip_path
            )
            
        threading.Thread(target=background_task, daemon=True).start()


    def get_latest_frame(self): return self.current_processed_frame
    def stop(self):
        self.running = False
        self.stream.stop()
        if self.thread: self.thread.join()
