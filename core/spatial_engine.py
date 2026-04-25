import time
import logging
import cv2
import numpy as np
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class SpatialEngine:
    """
    Hệ thống Logic Không gian HTMP (Phiên bản đồng bộ thời gian):
    - Đảm bảo các bước diễn ra theo đúng trình tự và thời điểm.
    - Ngăn chặn việc hoàn thành bước tức thì bằng mốc thời gian step_start_time.
    - Hỗ trợ đầy đủ logic: zone_trigger, stay_in_zone, interaction, dual_task.
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        # Mặc định dùng 640x480 để khớp với FrameProcessor
        self.config = sop_config.get("config", {"w": 640, "h": 480})
        
        # Sắp xếp vùng theo diện tích để ưu tiên vùng nhỏ
        self.sorted_zones = []
        for name, pts in self.zones.items():
            poly = np.array(pts, np.float32)
            area = cv2.contourArea(poly)
            self.sorted_zones.append({"name": name, "pts": pts, "area": area})
        self.sorted_zones.sort(key=lambda x: x["area"])
        
        # Trạng thái moteur logic
        self.current_step_idx = 0
        self.step_start_time = 0
        self._completed_at = 0  # Cooldown timer sau khi hoàn thành cycle
        self.last_hands = []
        self.hand_dist = -1.0
        
        # Trạng thái chi tiết từng tay (dùng cho display)
        self.hand_states = {
            "left": {"zone": None, "entry_time": 0},
            "right": {"zone": None, "entry_time": 0}
        }
        
        # Timer cho zone_trigger: lần cuối mỗi tay chạm vùng mục tiêu
        self._zone_last_seen = {"left": 0, "right": 0}
        # Timer cho stay_in_zone: thời điểm bắt đầu ở liên tục trong vùng
        self._stay_timer = {"left": 0, "right": 0}
        
        # Lịch sử di chuyển (dùng cho interaction logic)
        self.hand_history = {"left": [], "right": []}
        
        logger.info(f"SpatialEngine: Initialized with {len(self.sorted_zones)} prioritized zones.")

    def update(self, hands_data: List[Dict]) -> Dict[str, Any] | None:
        now = time.time()
        self.last_hands = hands_data
        
        # 1. Cập nhật vị trí và lịch sử
        active_zones = {"left": None, "right": None}
        for hand in hands_data:
            side = hand["label"].lower()
            if side not in ["left", "right"]: continue
            
            # Kiểm tra 5 điểm của Box để tăng độ nhạy
            centroid = hand["centroid"]
            bbox = hand["bbox"] # [x1, y1, x2, y2]
            w, h = self.config.get("w", 1280), self.config.get("h", 720)
            
            test_points = [
                centroid,
                [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h],
                [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]
            ]
            
            current_zone = None
            for z_info in self.sorted_zones:
                poly = np.array(z_info["pts"], np.float32)
                if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                    current_zone = z_info["name"]
                    break
            
            active_zones[side] = current_zone
            
            # Ghi nhận thay đổi vùng
            if current_zone != self.hand_states[side]["zone"]:
                self.hand_states[side]["zone"] = current_zone
                self.hand_states[side]["entry_time"] = now
                if current_zone:
                    self.hand_history[side].append((current_zone, now))
                    # Giữ lịch sử ngắn gọn (~1 phút)
                    if len(self.hand_history[side]) > 50: self.hand_history[side].pop(0)

        # Tính khoảng cách
        self.hand_dist = self._get_hand_distance()

        # DEBUG: In ra chi tiet (moi 15 frame ~ 1 giay)
        self._debug_count = getattr(self, '_debug_count', 0) + 1
        if self._debug_count % 15 == 0 and self.current_step_idx < len(self.sop_steps):
            step = self.sop_steps[self.current_step_idx]
            target = step.get("required_zone", step.get("left_zone", "?"))
            l_in = self._is_in_zone("left", target)
            r_in = self._is_in_zone("right", target)
            # Hien thi toa do tam tay de kiem tra
            coords = ""
            for h in self.last_hands:
                s = h["label"][0].upper()
                c = h["centroid"]
                coords += f" {s}({c[0]:.3f},{c[1]:.3f})"
            logger.info(f"DEBUG: Step={self.current_step_idx+1} zone={target} | L_in={l_in} R_in={r_in} | display: L={active_zones['left']} R={active_zones['right']} |{coords}")

        # 2. Check cooldown sau khi hoàn thành chu kỳ (giữ trạng thái "completed" 3 giây)
        if self._completed_at > 0:
            if now - self._completed_at < 3.0:
                return {
                    "sop_status": "completed",
                    "expected_step": "DONE",
                    "detected_label": "Finished",
                    "step_index": len(self.sop_steps),
                    "step_list": [s["step_name"] for s in self.sop_steps],
                    "progress_percent": 100,
                    "hands_info": active_zones,
                    "dist": self.hand_dist
                }
            else:
                # Hết 3 giây → reset cho chu kỳ mới
                self._completed_at = 0
                self.reset()

        # 3. Kiểm tra logic SOP
        if self.current_step_idx < len(self.sop_steps):
            step = self.sop_steps[self.current_step_idx]
            if self._check_step_logic(step, now):
                step_num = step.get("step_order", self.current_step_idx + 1)
                logger.info(f"SpatialEngine: Step {step_num} COMPLETED.")
                
                self.current_step_idx += 1
                self.step_start_time = time.time()
                # Reset timers cho bước mới
                self._zone_last_seen = {"left": 0, "right": 0}
                self._stay_timer = {"left": 0, "right": 0}
                
                if self.current_step_idx >= len(self.sop_steps):
                    logger.info("SpatialEngine: COMPLETE SOP CYCLE!")
                    self._completed_at = now  # Bắt đầu cooldown 3 giây
                    return {
                        "sop_status": "completed", 
                        "expected_step": "DONE",
                        "detected_label": "Finished",
                        "step_index": len(self.sop_steps),
                        "step_list": [s["step_name"] for s in self.sop_steps],
                        "progress_percent": 100,
                        "hands_info": active_zones,
                        "dist": self.hand_dist
                    }

        # 4. Kết quả trả về cho UI
        cur_step_name = self.sop_steps[self.current_step_idx]["step_name"] if self.current_step_idx < len(self.sop_steps) else "DONE"
        
        # Tạo chuỗi mô tả vùng đang chạm (Để Dashboard hiện AI đang thấy gì)
        detected_parts = []
        for side, zone in active_zones.items():
            if zone: detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        return {
            "expected_step": cur_step_name,     # Tên bước để hiện lên UI
            "detected_label": detected_label,   # Vùng đang chạm để hiện lên UI
            "step_index": self.current_step_idx,
            "step_list": [s["step_name"] for s in self.sop_steps], # DANH SÁCH TẤT CẢ CÁC BƯỚC
            "sop_status": "processing",
            "hands_info": active_zones,
            "dist": self.hand_dist
        }

    def _check_step_logic(self, step: Dict, now: float) -> bool:
        logic = step.get("logic")
        
        # === ZONE TRIGGER: Tay chạm vùng mục tiêu (grace 0.5s) ===
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            grace = 0.5  # Cho phép 2 tay lệch nhau tối đa 0.5s
            
            # Cập nhật timestamp lần cuối mỗi tay chạm vùng mục tiêu
            for side in ["left", "right"]:
                if self._is_in_zone(side, target):
                    self._zone_last_seen[side] = now
            
            if mode == "any":
                return any(now - self._zone_last_seen[s] < grace for s in ["left", "right"])
            elif mode == "both":
                return all(now - self._zone_last_seen[s] < grace for s in ["left", "right"])
            else:
                return now - self._zone_last_seen[mode] < grace

        # === STAY IN ZONE: Giữ tay trong vùng liên tục N giây ===
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            
            for side in ["left", "right"]:
                if self._is_in_zone(side, target):
                    if self._stay_timer[side] == 0:
                        self._stay_timer[side] = now  # Bắt đầu đếm
                else:
                    self._stay_timer[side] = 0  # Rời vùng → reset
            
            if mode == "any":
                return any(self._stay_timer[s] > 0 and (now - self._stay_timer[s]) >= min_dur for s in ["left", "right"])
            elif mode == "both":
                return all(self._stay_timer[s] > 0 and (now - self._stay_timer[s]) >= min_dur for s in ["left", "right"])
            else:
                return self._stay_timer[mode] > 0 and (now - self._stay_timer[mode]) >= min_dur

        # === INTERACTION: 2 tay chạm nhau trong vùng ===
        elif logic == "interaction":
            max_dist = step.get("max_hand_dist", 0.15)
            target = step.get("required_zone")
            is_touching = 0 < self.hand_dist < max_dist
            if target:
                return is_touching and self._is_in_zone("left", target) and self._is_in_zone("right", target)
            return is_touching

        # === DUAL TASK: Tay trái ở vùng A, tay phải ở vùng B ===
        elif logic == "dual_task" or logic == "dual_task_return":
            l_zone = step.get("left_zone")
            r_zone = step.get("right_zone")
            grace = 0.5
            for side, zone in [("left", l_zone), ("right", r_zone)]:
                if self._is_in_zone(side, zone):
                    self._zone_last_seen[side] = now
            return all(now - self._zone_last_seen[s] < grace for s in ["left", "right"])

        return False

    def _is_in_zone(self, side: str, zone_name: str) -> bool:
        """Check if hand directly overlaps with zone polygon. Ignores all other zones."""
        zone_pts = self.zones.get(zone_name)
        if not zone_pts:
            return False
        poly = np.array(zone_pts, np.float32)
        w, h = self.config.get("w", 1280), self.config.get("h", 720)
        
        for hand in self.last_hands:
            if hand["label"].lower() != side:
                continue
            centroid = hand["centroid"]
            bbox = hand["bbox"]
            test_points = [
                centroid,
                [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h],
                [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]
            ]
            if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                return True
        return False

    def _match_seq(self, history: List[str], sequence: List[str]) -> bool:
        """Kiểm tra history có chứa sequence đúng thứ tự không."""
        idx = 0
        for z in history:
            if z == sequence[idx]:
                idx += 1
                if idx == len(sequence): return True
        return False

    def _get_hand_distance(self) -> float:
        """Tính khoảng cách tâm 2 tay (normalized)."""
        if len(self.last_hands) < 2: return -1.0
        # Tìm tâm tay trái và phải
        l_pos, r_pos = None, None
        for h in self.last_hands:
            if h["label"] == "left": l_pos = h["centroid"]
            if h["label"] == "right": r_pos = h["centroid"]
        
        if l_pos and r_pos:
            return np.sqrt((l_pos[0]-r_pos[0])**2 + (l_pos[1]-r_pos[1])**2)
        return -1.0

    def reset(self):
        self.current_step_idx = 0
        self.step_start_time = time.time()
        self._zone_last_seen = {"left": 0, "right": 0}
        self._stay_timer = {"left": 0, "right": 0}
        for side in ["left", "right"]:
            self.hand_states[side] = {"zone": None, "entry_time": time.time()}
            self.hand_history[side].clear()
