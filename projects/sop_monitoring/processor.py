import cv2
import threading
import time
import logging
import os
import numpy as np
import psutil
from typing import Dict, Any, Optional, List, Tuple

from shared.rtsp_manager import RTSPStream
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.buffer import FrameRingBuffer
from projects.sop_monitoring.core.engines.base_engine import BaseEngine
from projects.sop_monitoring.core.engines.loader import EngineLoader
from projects.sop_monitoring.core.violation_detector import ViolationDetector
from shared.services.annotator import Annotator
from shared.events.audio_alert import AudioAlert
from shared.events.clip_saver import ClipSaver
from shared.db.queries import EventQueries

logger = logging.getLogger(__name__)

# Cache process object — tái sử dụng thay vì tạo mới mỗi lần profiling
_process = psutil.Process(os.getpid())



class FrameProcessor:
    """
    Orchestrates the entire pipeline for a single camera.
    Reform: Uses SpatialEngine (Zone-based) instead of LSTM.
    """
    def __init__(self, camera_config: Dict[str, Any],
                 engine: BaseEngine,
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
        model_path = camera_config.get("yolo_model")
        from shared.services.config_loader import ConfigLoader
        config = ConfigLoader.load_config()
        yolo_cfg = config.get("models", {}).get("yolo", {})
        conf_thres = camera_config.get("conf_threshold") or yolo_cfg.get("conf_threshold") or 0.25
        iou_thres = camera_config.get("iou_threshold") or yolo_cfg.get("iou_threshold") or 0.45
        self.hand_detector = HandDetector(
            self.cam_id, 
            confidence_threshold=conf_thres, 
            iou_threshold=iou_thres, 
            model_path=model_path
        )
        # BỎ MediaPipe KeypointExtractor

        # Dynamic Engine
        self.engine = engine
        self.violation_detector = violation_detector
        
        # Load pre/post seconds from config
        from shared.services.config_loader import ConfigLoader
        config = ConfigLoader.load_config()
        storage_cfg = config.get("storage", {})
        self.pre_seconds = int(storage_cfg.get("clip_pre_seconds", 20))
        self.post_seconds = int(storage_cfg.get("clip_post_seconds", 5))
        total_seconds = self.pre_seconds + self.post_seconds
        
        self.ring_buffer = FrameRingBuffer(self.fps, total_seconds)
        self.audio_alert = audio_alert
        self.clip_saver = clip_saver

        self.running = False
        self._completion_logged = False  # Cờ để chặn ghi log thành công nhiều lần
        self.current_processed_frame = None
        self.frame_lock = threading.Lock()  # Bảo vệ current_processed_frame khi đọc từ HTTP generator
        self.latest_status = {"sop_status": "idle", "progress_percent": 0}
        self.sop_config = None
        self._loop_count = 0
        self.last_step_idx = -1
        self._cached_hands = []
        self._cached_products = []
        self._cached_robots = []  # Robot arm detections (class=robot)
        self._last_hands_update_time = 0.0
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
                
                # Phân tách detections thành tay, sản phẩm, và robot
                hand_dets = [
                    d for d in detections 
                    if d.get("class", "hand") == "hand"
                    and (d["bbox"][2] - d["bbox"][0]) <= frame.shape[1] * 0.35
                    and (d["bbox"][3] - d["bbox"][1]) <= frame.shape[0] * 0.35
                ]
                self._cached_products = [d for d in detections if d.get("class") == "sp"]
                self._cached_robots = [d for d in detections if d.get("class") == "robot"]
                
                # 1. Lọc tay ngoài vùng làm việc bằng Dynamic ROI
                filtered_dets = self._filter_detections_by_roi(hand_dets)
                
                # 2. Bám vết và định danh tay Trái/Phải để tránh nhảy box khi có người khác
                hands_data = self._associate_hands(filtered_dets)
                self._cached_hands = hands_data
                self._last_hands_update_time = loop_start

            # --- TAY MA (GHOST HANDS) PROTECTION ---
            # Nếu AI không chạy hoặc detector liên tục không thấy tay trong 0.8s, xóa cache.
            # Điều này ngăn việc engine nhận diện nhầm khi công nhân đã rút tay ra nhưng AI chưa update.
            if loop_start - self._last_hands_update_time > 0.8:
                self._cached_hands = []
                self._cached_products = []
                self._cached_robots = []
                hands_data = []

            # 3. Dynamic Engine Update (truyền thêm robot_data cho TFF4040)
            self.latest_status = self.engine.update(hands_data, self._cached_products, self._cached_robots)
            
            # 4. Check Violation
            violation = self.violation_detector.analyze(self.latest_status)
            if violation:
                self._handle_violation(violation)

            # 5. Annotation — TỐI ƯU: Vẽ trực tiếp lên frame đã lấy từ stream (đã là 1 bản copy)
            # Việc này giúp giảm 1 lần copy ảnh mỗi frame và giúp clip vi phạm có sẵn Bbox để đối soát.
            display_frame = frame 
            # Note: Annotator.draw_zones might need access to current engine's zones
            if hasattr(self.engine, 'zones'):
                Annotator.draw_zones(display_frame, self.engine.zones)
            for h in self._cached_hands:
                bbox = h["bbox"]
                color = (0, 255, 255) if h["label"] == "left" else (0, 230, 20)
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
                
            # Vẽ sản phẩm (nếu được phát hiện) bằng màu cam cho laprap, xanh dương cho các máy khác
            prod_color = (0, 128, 255) if getattr(self.engine, "product_id", None) == "laprap" else (255, 0, 0)
            for p in self._cached_products:
                bbox = p["bbox"]
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), prod_color, 2)
                cv2.putText(display_frame, "Product", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, prod_color, 1, cv2.LINE_AA)

            # Vẽ robot arm (nếu được phát hiện) bằng màu hồng
            for r in self._cached_robots:
                bbox = r["bbox"]
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 100, 180), 2)
                cv2.putText(display_frame, "Robot", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 180), 1, cv2.LINE_AA)

            self.current_processed_frame = display_frame
            with self.frame_lock:
                self._loop_count += 1
            
            # 6. Socket Update — Giảm tần suất xuống 1 lần/giây (mỗi 15 frame) trừ khi hoàn thành hoặc đổi bước
            is_completed = self.latest_status.get("sop_status") == "completed"
            is_violation = self.latest_status.get("sop_status") == "violation"
            step_changed = False
            curr_idx = self.engine.current_step_idx if hasattr(self.engine, 'current_step_idx') else -1
            if curr_idx != self.last_step_idx:
                self.last_step_idx = curr_idx
                step_changed = True

            if is_completed or step_changed:
                if is_completed and not self._completion_logged:
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
        """Xử lý vi phạm: Đợi self.post_seconds để lấy đủ post-event frames rồi mới lưu."""
        def background_task():
            # 1. Phát âm thanh cảnh báo ngay lập tức
            if self.audio_alert: self.audio_alert.trigger()
            
            # 2. Emit SocketIO ngay để dashboard hiển thị đỏ rực và thông báo
            from app import emit_violation
            emit_violation(self.cam_id, violation)
            
            # 3. Đợi post_seconds giây để thu thập phần 'sau lỗi' vào ring buffer
            logger.info(f"FrameProcessor [{self.cam_id}]: Violation detected. Waiting {self.post_seconds}s for post-event frames...")
            time.sleep(self.post_seconds)
            
            # 4. Lấy toàn bộ frames (Lúc này buffer chứa pre_seconds + post_seconds = tổng thời gian)
            frames_to_save = self.ring_buffer.get_all()
            
            # 5. Lưu clip
            clip_path = self.clip_saver.save_violation_clip(self.cam_id, frames_to_save)
            
            # Tính thời gian vi phạm thực tế từ số lượng frame đã thu thập hoặc từ violation dict
            save_fps = self.clip_saver.fps if (hasattr(self.clip_saver, 'fps') and self.clip_saver.fps > 0) else self.fps
            calc_duration = round(len(frames_to_save) / (save_fps if save_fps > 0 else 15), 1) if frames_to_save else 0.0
            actual_duration = violation.get("duration", calc_duration)

            # 6. Ghi log vào DB với đường dẫn clip chính xác và thời gian thực tế
            EventQueries.log_event(
                camera_id=self.cam_id, 
                violation_type=violation.get("violation_type", "unknown"),
                step_detected=violation.get("detected_step", "N/A"), 
                expected_step=violation.get("expected_step"),
                sop_status="violation", 
                confidence=violation.get("confidence", 1.0), 
                clip_path=clip_path,
                duration=actual_duration
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


    def switch_engine(self, product_id: str, sop_config: Dict[str, Any]):
        """Thay đổi engine logic của trạm sang một mã sản phẩm khác."""
        logger.info(f"FrameProcessor [{self.cam_id}]: Switching to product engine '{product_id}'...")
        try:
            new_engine = EngineLoader.create_engine(product_id, sop_config)
            
            # Tạm thời khóa để đổi engine
            old_engine = self.engine
            self.engine = new_engine
            self.sop_config = sop_config
            
            # Reset trạng thái
            self.engine.reset()
            self._completion_logged = False
            self.latest_status = {"sop_status": "idle", "progress_percent": 0}
            
            logger.info(f"FrameProcessor [{self.cam_id}]: Successfully switched to '{product_id}'.")
            return True
        except Exception as e:
            logger.error(f"FrameProcessor [{self.cam_id}]: Failed to switch engine: {e}")
            return False

    def _filter_detections_by_roi(self, detections: List[Dict]) -> List[Dict]:
        """Lọc các box nhận diện tay nằm ngoài vùng làm việc (ROI) của trạm để tránh nhận nhầm người đi qua."""
        if not hasattr(self.engine, 'zones') or not self.engine.zones:
            return detections
        
        xs = []
        ys = []
        for pts in self.engine.zones.values():
            for p in pts:
                xs.append(p[0])
                ys.append(p[1])
        
        if not xs or not ys:
            return detections
            
        # Thêm biên độ an toàn (margin) 15% xung quanh các vùng làm việc
        margin_x = 0.15
        margin_y = 0.15
        
        min_x = max(0.0, min(xs) - margin_x)
        max_x = min(1.0, max(xs) + margin_x)
        min_y = max(0.0, min(ys) - margin_y)
        max_y = min(1.0, max(ys) + margin_y)
        
        filtered = []
        for det in detections:
            bbox = det["bbox"]
            cx = ((bbox[0] + bbox[2]) / 2) / self._target_w
            cy = ((bbox[1] + bbox[3]) / 2) / self._target_h
            
            if min_x <= cx <= max_x and min_y <= cy <= max_y:
                filtered.append(det)
                
        return filtered

    def _associate_hands(self, detections: List[Dict]) -> List[Dict]:
        """
        Bám vết bàn tay bằng khoảng cách Euclid (Temporal Consistency) kết hợp vị trí không gian.
        Giúp định danh chính xác tay Trái/Phải và tránh hiện tượng nhảy box khi có tay lạ hoặc nhiễu.
        """
        new_hands_data = []
        if not detections:
            return []
            
        # Tìm vị trí trước đó của tay Trái/Phải từ cached_hands
        prev_left = None
        prev_right = None
        for h in self._cached_hands:
            if h["label"] == "left":
                prev_left = h["centroid"]
            elif h["label"] == "right":
                prev_right = h["centroid"]
                
        # Ngưỡng dịch chuyển tối đa giữa 2 frame liên tiếp (normalized)
        max_move = 0.25
        
        # Chuẩn bị danh sách ứng viên (candidate detections)
        candidates = []
        for det in detections:
            bbox = det["bbox"]
            cx = (bbox[0] + bbox[2]) / 2 / self._target_w
            cy = (bbox[1] + bbox[3]) / 2 / self._target_h
            candidates.append({
                "centroid": [cx, cy],
                "bbox": bbox,
                "confidence": det.get("confidence", 1.0)
            })
            
        best_left_cand = None
        best_left_dist = max_move
        best_right_cand = None
        best_right_dist = max_move
        
        # Đối sánh với tay đã lưu ở frame trước
        for cand in candidates:
            c = cand["centroid"]
            if prev_left is not None:
                dist_l = float(np.linalg.norm(np.array(c) - np.array(prev_left)))
                if dist_l < best_left_dist:
                    best_left_dist = dist_l
                    best_left_cand = cand
            if prev_right is not None:
                dist_r = float(np.linalg.norm(np.array(c) - np.array(prev_right)))
                if dist_r < best_right_dist:
                    best_right_dist = dist_r
                    best_right_cand = cand
                    
        # Giải quyết xung đột nếu 2 tay cùng đối sánh vào 1 ứng viên
        if best_left_cand and best_right_cand and best_left_cand == best_right_cand:
            if best_left_dist < best_right_dist:
                best_right_cand = None
            else:
                best_left_cand = None
                
        # Ghi nhận các ứng viên đã được khớp
        matched_cands = []
        if best_left_cand:
            new_hands_data.append({
                "label": "left",
                "centroid": best_left_cand["centroid"],
                "bbox": best_left_cand["bbox"]
            })
            matched_cands.append(best_left_cand)
        if best_right_cand:
            new_hands_data.append({
                "label": "right",
                "centroid": best_right_cand["centroid"],
                "bbox": best_right_cand["bbox"]
            })
            matched_cands.append(best_right_cand)
            
        # Các ứng viên còn lại chưa được khớp
        unmatched = [c for c in candidates if c not in matched_cands]
        
        # Nếu có ứng viên chưa khớp, chỉ khởi tạo gán nhãn mới cho các nhãn (left/right) chưa có trong frame này
        # Dựa trên vị trí X của ứng viên: cx < 0.5 -> right hand, cx >= 0.5 -> left hand (mirror mode)
        if unmatched:
            used_labels = {h["label"] for h in new_hands_data}
            for cand in unmatched:
                cx = cand["centroid"][0]
                # Nếu nhãn mặc định chưa bị chiếm bởi tay đã track
                pref_label = "right" if cx < 0.5 else "left"
                alt_label = "left" if pref_label == "right" else "right"
                
                target_label = None
                if pref_label not in used_labels:
                    target_label = pref_label
                elif alt_label not in used_labels:
                    target_label = alt_label
                    
                if target_label:
                    new_hands_data.append({
                        "label": target_label,
                        "centroid": cand["centroid"],
                        "bbox": cand["bbox"]
                    })
                    used_labels.add(target_label)
                
        return new_hands_data

    def get_latest_frame(self): return self.current_processed_frame
    def stop(self):
        self.running = False
        self.stream.stop()
        if self.thread: self.thread.join()
