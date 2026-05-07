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
        # Ưu tiên lấy FPS từ ENV, nếu không có mới lấy từ config/default
        self.fps = int(os.getenv("AI_FPS_CAP", camera_config.get("fps_cap", 15)))
        self.frame_delay = 1.0 / self.fps

        res = camera_config.get("resolution", [1280, 720])
        self._target_w = res[0]
        self._target_h = res[1]

        # Integrations — RTSPStream resize ngay tại nguồn để tiết kiệm CPU
        self.stream = RTSPStream(self.cam_id, self.rtsp_url, self.fps,
                                 target_width=self._target_w, target_height=self._target_h)
        self.hand_detector = HandDetector(self.cam_id, confidence_threshold=0.15)
        # BỎ MediaPipe KeypointExtractor

        # New Engine
        self.spatial_engine = spatial_engine
        self.violation_detector = violation_detector
        
        self.ring_buffer = FrameRingBuffer(self.fps, 10)  # 5s trước + 5s sau = 10s tổng
        self.audio_alert = audio_alert
        self.clip_saver = clip_saver

        self.running = False
        self._completion_logged = False  # Cờ để chặn ghi log thành công nhiều lần
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
                time.sleep(0.05); continue

            # Frame đã được resize trong RTSPStream — KHÔNG resize lại ở đây
            self._target_w = frame.shape[1]
            self._target_h = frame.shape[0]

            # Push frame gốc vào ring buffer (deque tự quản lý bộ nhớ)
            self.ring_buffer.push(frame)
            
            # --- AI PROCESSING (YOLO ONLY) ---
            # Chạy AI mỗi 2 frame (~7.5 FPS) — đã chứng minh chính xác cho SOP detection
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

            # 3. Spatial Logic Update
            self.latest_status = self.spatial_engine.update(hands_data)
            
            # 4. Check Violation
            violation = self.violation_detector.analyze(self.latest_status)
            if violation:
                self._handle_violation(violation)

            # 5. Annotation — TỐI ƯU: Vẽ trực tiếp lên frame đã lấy từ stream (đã là 1 bản copy)
            # Việc này giúp giảm 1 lần copy ảnh mỗi frame và giúp clip vi phạm có sẵn Bbox để đối soát.
            display_frame = frame 
            Annotator.draw_zones(display_frame, self.spatial_engine.zones)
            for h in self._cached_hands:
                bbox = h["bbox"]
                color = (0, 255, 255) if h["label"] == "left" else (0, 230, 20)
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)

            self.current_processed_frame = display_frame
            self._loop_count += 1
            
            # 6. Socket Update — Giảm tần suất xuống 1 lần/giây (mỗi 15 frame)
            is_completed = self.latest_status.get("sop_status") == "completed"
            is_violation = self.latest_status.get("sop_status") == "violation"
            if is_completed:
                if not self._completion_logged:
                    self._handle_completion()
                    self._completion_logged = True
                emit_step_update(self.cam_id, self.latest_status, self.latest_status.get("hands_info", {}))
            else:
                # Reset cờ khi quay lại trạng thái bình thường (processing hoặc violation)
                self._completion_logged = False
                if is_violation or self._loop_count % 15 == 0:
                    emit_step_update(self.cam_id, self.latest_status, self.latest_status.get("hands_info", {}))

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
            logger.info(f"FrameProcessor [{self.cam_id}]: Violation detected. Waiting 5s for post-event frames...")
            time.sleep(5)
            
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

    def _handle_completion(self):
        """Xử lý khi hoàn thành 1 chu kỳ SOP thành công."""
        def background_task():
            logger.info(f"FrameProcessor [{self.cam_id}]: SOP COMPLETED SUCCESSFULLY. Logging to DB.")
            EventQueries.log_event(
                camera_id=self.cam_id,
                violation_type="success",
                sop_status="completed",
                confidence=1.0
            )
        threading.Thread(target=background_task, daemon=True).start()


    def get_latest_frame(self): return self.current_processed_frame
    def stop(self):
        self.running = False
        self.stream.stop()
        if self.thread: self.thread.join()
