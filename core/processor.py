import cv2
import time
import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from core.detector import HandDetector
from core.engine import LaprapEngine
from shared.utils import draw_zones

logger = logging.getLogger(__name__)

class FrameProcessor:
    """
    Coordinates frame reading, inference, FSM updates, and visualization.
    Implements active-hand detection: chỉ tay đang di chuyển mới kích hoạt FSM.
    """
    def __init__(self, model_path: str, sop_config: Dict[str, Any], fps: int = 15):
        self.sop_config = sop_config
        self.fps = fps
        self.frame_delay = 1.0 / fps
        
        self.detector = HandDetector(model_path=model_path, confidence_threshold=0.25)
        self.engine = LaprapEngine(sop_config=sop_config)
        self.running = False

        # Active hand tracking — velocity buffer
        cfg = sop_config.get("config", {})
        self._velocity_threshold = cfg.get("active_hand_velocity_threshold", 0.012)
        
        # Bám vết tay Trái/Phải
        self._cached_hands = []
        self._prev_centroids_dict = {"left": None, "right": None}
        self._velocity_history_dict = {"left": [], "right": []}

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Processes a single frame: runs detector, updates engine, and draws UI.
        """
        # 1. Run detector (returns both hands and products)
        all_detections = self.detector.detect(frame)

        # Phân loại tay và sản phẩm riêng biệt
        hands = [
            d for d in all_detections 
            if d.get("class") == "hand"
            and (d["bbox"][2] - d["bbox"][0]) <= frame.shape[1] * 0.35
            and (d["bbox"][3] - d["bbox"][1]) <= frame.shape[0] * 0.35
        ]
        products = [d for d in all_detections if d.get("class") == "sp"]

        # 2. Bám vết và định danh tay Trái/Phải
        hands_data = self._associate_hands(hands)

        # 3. Tính toán velocity và lấy danh sách active hands
        active_hands, velocities = self._classify_active_hands_by_label(hands_data)

        # 4. Update FSM engine — truyền tay đang di chuyển + toàn bộ sản phẩm
        # Nếu không có tay nào di chuyển đủ, truyền tất cả các tay đã định danh
        hands_for_fsm = active_hands if active_hands else hands_data
        fsm_input = hands_for_fsm + products
        status = self.engine.update(fsm_input)

        # 5. Vẽ giao diện
        annotated_frame = self._draw_ui(frame.copy(), all_detections, active_hands, velocities, status)

        return annotated_frame, status

    def _associate_hands(self, detections: List[Dict]) -> List[Dict]:
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
            cx = det["centroid"][0]
            cy = det["centroid"][1]
            candidates.append({
                "centroid": [cx, cy],
                "bbox": bbox,
                "confidence": det.get("confidence", 1.0),
                "fingertip": det.get("fingertip", [cx, cy]),
                "fingertip_detected": det.get("fingertip_detected", False),
                "class": "hand"
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
                "bbox": best_left_cand["bbox"],
                "fingertip": best_left_cand["fingertip"],
                "fingertip_detected": best_left_cand["fingertip_detected"],
                "class": "hand"
            })
            matched_cands.append(best_left_cand)
        if best_right_cand:
            new_hands_data.append({
                "label": "right",
                "centroid": best_right_cand["centroid"],
                "bbox": best_right_cand["bbox"],
                "fingertip": best_right_cand["fingertip"],
                "fingertip_detected": best_right_cand["fingertip_detected"],
                "class": "hand"
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
                        "bbox": cand["bbox"],
                        "fingertip": cand["fingertip"],
                        "fingertip_detected": cand["fingertip_detected"],
                        "class": "hand"
                    })
                    used_labels.add(target_label)
                
        self._cached_hands = new_hands_data
        return new_hands_data

    def _classify_active_hands_by_label(self, hands: List[Dict]) -> Tuple[List[Dict], Dict[str, float]]:
        active_hands = []
        velocities = {"left": 0.0, "right": 0.0}
        
        # Reset previous centroids for missing hands
        present_labels = {h["label"] for h in hands}
        for label in ["left", "right"]:
            if label not in present_labels:
                self._prev_centroids_dict[label] = None
                self._velocity_history_dict[label] = []

        for hand in hands:
            label = hand["label"]
            curr_c = hand["centroid"]
            prev_c = self._prev_centroids_dict[label]
            
            if prev_c is None:
                v = 0.0
            else:
                v = ((curr_c[0] - prev_c[0]) ** 2 + (curr_c[1] - prev_c[1]) ** 2) ** 0.5
            
            self._prev_centroids_dict[label] = curr_c
            
            self._velocity_history_dict[label].append(v)
            if len(self._velocity_history_dict[label]) > 5:
                self._velocity_history_dict[label].pop(0)
                
            smoothed_v = sum(self._velocity_history_dict[label]) / len(self._velocity_history_dict[label])
            velocities[label] = smoothed_v
            
            if smoothed_v >= self._velocity_threshold:
                active_hands.append(hand)
                
        # Nếu cả 2 tay đều đứng yên nhưng có tay xuất hiện, tay có vận tốc lớn nhất được coi là active
        if not active_hands and hands:
            best_hand = max(hands, key=lambda h: velocities[h["label"]])
            active_hands = [best_hand]
            
        return active_hands, velocities

    def _draw_ui(self, frame: np.ndarray, all_detections: List[Dict],
                 active_hands: List[Dict], velocities: Dict[str, float],
                 status: Dict[str, Any]) -> np.ndarray:
        """
        Renders a premium visual interface over the frame, synchronized with AI_Monitoring_Hub.
        """
        h, w = frame.shape[:2]
        active_labels = {ah["label"] for ah in active_hands}

        # Determine active zones to highlight them (chỉ dựa trên tay active)
        active_zones = {}
        for hand in active_hands:
            for zone_name, pts in self.engine.zones.items():
                from shared.utils import is_point_in_zone
                if is_point_in_zone(hand["fingertip"], pts):
                    active_zones[zone_name] = True

        # 1. Draw ROI Polygons
        frame = draw_zones(frame, self.engine.zones, active_zones)

        # 2. Draw all hands — left vs right
        for hand in self._cached_hands:
            bbox = hand["bbox"]
            label = hand["label"]
            is_active = label in active_labels
            v = velocities.get(label, 0.0)
            
            # Cyan for left hand (LH), Green for right hand (RH)
            if label == "left":
                base_color = (255, 230, 0) if is_active else (180, 150, 100)
                text_label = f"LH ACTIVE v={v:.3f}" if is_active else f"LH HOLD v={v:.3f}"
            else:
                base_color = (0, 230, 20) if is_active else (80, 150, 80)
                text_label = f"RH ACTIVE v={v:.3f}" if is_active else f"RH HOLD v={v:.3f}"
                
            cv2.rectangle(frame,
                          (int(bbox[0]), int(bbox[1])),
                          (int(bbox[2]), int(bbox[3])),
                          base_color, 2 if is_active else 1)
                          
            cv2.putText(frame, text_label,
                        (int(bbox[0]), int(bbox[1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, base_color, 1, cv2.LINE_AA)
                        
            # Fingertip dot
            fx = int(hand["fingertip"][0] * w)
            fy = int(hand["fingertip"][1] * h)
            if is_active:
                if hand.get("fingertip_detected", False):
                    cv2.circle(frame, (fx, fy), 8, (255, 255, 255), -1)
                    cv2.circle(frame, (fx, fy), 5, base_color, -1)
                    cv2.putText(frame, "COT", (fx + 10, fy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                else:
                    cv2.circle(frame, (fx, fy), 6, base_color, -1)
            else:
                cv2.circle(frame, (fx, fy), 4, (100, 100, 100), -1)

        # 3. Draw products with orange/cyan border
        products_to_draw = [d for d in all_detections if d.get("class") == "sp"]
        for prod in products_to_draw:
            bbox = prod["bbox"]
            color = (255, 180, 0)
            cv2.rectangle(frame,
                          (int(bbox[0]), int(bbox[1])),
                          (int(bbox[2]), int(bbox[3])),
                          color, 2)
            cv2.putText(frame, "SP",
                        (int(bbox[0]), int(bbox[1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2, cv2.LINE_AA)

        # Draw robot arm if detected
        robots_to_draw = [d for d in all_detections if d.get("class") == "robot"]
        for rob in robots_to_draw:
            bbox = rob["bbox"]
            color = (255, 100, 180)
            cv2.rectangle(frame,
                          (int(bbox[0]), int(bbox[1])),
                          (int(bbox[2]), int(bbox[3])),
                          color, 2)
            cv2.putText(frame, "Robot",
                        (int(bbox[0]), int(bbox[1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2, cv2.LINE_AA)

        # 4. Draw Glassmorphism-style side panel overlay for SOP Steps
        panel_w = 320
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (panel_w, h), (25, 28, 36), -1)
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        
        # Draw Title
        cv2.putText(frame, "SOP MONITORING", (15, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Tram: {self.engine.station_name}", (15, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1, cv2.LINE_AA)
        
        # Draw Bimanual status dots (LH / RH)
        has_left = any(h["label"] == "left" for h in self._cached_hands)
        has_right = any(h["label"] == "right" for h in self._cached_hands)
        
        cv2.putText(frame, "LH", (15, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        lh_color = (0, 230, 20) if has_left else (80, 80, 80)
        cv2.circle(frame, (50, 72), 6, lh_color, -1)
        
        cv2.putText(frame, "RH", (80, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        rh_color = (0, 230, 20) if has_right else (80, 80, 80)
        cv2.circle(frame, (115, 72), 6, rh_color, -1)
        
        cv2.line(frame, (15, 90), (panel_w - 15, 90), (60, 60, 60), 1)

        # Draw Countdown Banner
        sop_status = status.get("sop_status", "idle")
        is_failed = status.get("is_failed", False)
        
        if is_failed or sop_status == "violation":
            banner_color = (40, 40, 200) # Red
        elif sop_status == "completed":
            banner_color = (40, 180, 40) # Green
        elif sop_status == "processing":
            banner_color = (180, 110, 30) # Blueish / Orangeish
        else:
            banner_color = (60, 60, 60) # Grey for idle
            
        cv2.rectangle(frame, (15, 102), (panel_w - 15, 150), banner_color, -1)
        
        import unicodedata
        def remove_accents(input_str):
            nfkd_form = unicodedata.normalize('NFKD', input_str)
            return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
            
        status_msg = status.get("status_msg", "He thong san sang")
        clean_msg = remove_accents(status_msg)
        cv2.putText(frame, clean_msg, (25, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        
        time_left = status.get("cycle_time_left", 38.0)
        time_text = f"Timer: {time_left:.1f}s" if time_left < 999.0 else "Timer: --.-s"
        cv2.putText(frame, time_text, (25, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2, cv2.LINE_AA)

        # Draw Step List
        start_y = 180
        step_idx = status.get("step_index", 0)
        
        for idx, step_name in enumerate(status.get("step_list", [])):
            y = start_y + idx * 45
            
            circle_color = (100, 100, 100)
            text_color = (160, 160, 160)
            thickness = 1
            
            if idx < step_idx:
                circle_color = (0, 230, 20) # Completed
                text_color = (180, 255, 180)
            elif idx == step_idx:
                if is_failed:
                    circle_color = (0, 0, 220) # Failed
                    text_color = (180, 180, 255)
                else:
                    circle_color = (0, 200, 255) # Active
                    text_color = (255, 255, 255)
                    thickness = 2
            
            cv2.circle(frame, (30, y), 8, circle_color, -1)
            cv2.putText(frame, str(idx+1), (26, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1, cv2.LINE_AA)
            
            clean_step_name = remove_accents(step_name)
            cv2.putText(frame, clean_step_name, (50, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, thickness, cv2.LINE_AA)
            
        # Draw bottom metrics
        cv2.line(frame, (15, h - 85), (panel_w - 15, h - 85), (60, 60, 60), 1)
        
        # Cycle count
        cv2.putText(frame, f"Cycle Count: {status.get('cycle_count', 0)}", (15, h - 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
        
        # Progress bar
        progress_ratio = max(0.0, min(1.0, status.get("progress_percent", 0.0) / 100.0))
        bar_len = panel_w - 30
        cv2.rectangle(frame, (15, h - 45), (15 + bar_len, h - 35), (60, 60, 60), 1)
        
        bar_color = (0, 230, 20) if progress_ratio >= 1.0 else ((0, 200, 255) if progress_ratio > 0.0 else (100, 100, 100))
        cv2.rectangle(frame, (16, h - 44), (16 + int((bar_len-2) * progress_ratio), h - 36), bar_color, -1)
        
        cv2.putText(frame, f"Progress: {status.get('progress_percent', 0):.0f}%", (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
        
        return frame
