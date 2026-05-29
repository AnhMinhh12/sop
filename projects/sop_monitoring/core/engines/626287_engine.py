import time
import logging
import os
import cv2
import numpy as np
from typing import Dict, List, Any, Optional
from projects.sop_monitoring.core.engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)

class ProductEngine(BaseEngine):
    """
    Engine logic cho mã sản phẩm 626287.
    Thực hiện logic không gian dựa trên vùng (Zones).
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {"w": 640, "h": 480})
        self.product_id = "626287" # ID này được truyền từ loader
        self.restart_threshold = self.config.get("restart_allowed_until_step", len(self.sop_steps) // 2)
        
        # Sắp xếp vùng theo diện tích để ưu tiên vùng nhỏ
        self.sorted_zones = []
        for name, pts in self.zones.items():
            poly = np.array(pts, np.float32)
            area = cv2.contourArea(poly)
            self.sorted_zones.append({"name": name, "pts": pts, "area": area})
        self.sorted_zones.sort(key=lambda x: x["area"])
        
        # Trạng thái moteur logic
        self.current_step_idx = 0
        self.step_start_time = 0.0
        self.active_step_time = 0.0
        self.last_update_time = 0.0
        self._completed_at = 0
        self.last_hands = []
        self.hand_dist = -1.0
        
        self.is_failed = False
        self.violation_notified = False
        self.failed_step_idx = -1
        self.violation_type = None
        self.last_completed_zone = None
        self.last_completed_time = 0.0
        self.status_msg = "Sẵn sàng"
        
        self.hand_states = {
            "left": {"zone": None, "entry_time": 0},
            "right": {"zone": None, "entry_time": 0}
        }
        
        self._zone_last_seen = {}
        self._stay_timer = {}
        self.hand_history = {"left": [], "right": []}
        self.hit_count = 0
        self.last_trigger_states = {}
        self.waiting_for_start = True
        self.skip_frames_counter = 0
        self.reset_dwell_start = 0.0
        self.cycle_count = 0
        self.s1_withdrawn = True
        
        logger.info(f"ProductEngine [626287]: Initialized for station {self.station_id}")
        self.log_debug("--- NEW ENGINE INITIALIZED ---", self.product_id)

    def update(self, hands_data: List[Dict]) -> Dict[str, Any]:
        now = time.time()
        self.last_hands = hands_data
        
        # 1. Cập nhật vị trí
        active_zones = {"left": None, "right": None}
        for hand in hands_data:
            side = hand["label"].lower()
            if side not in ["left", "right"]: continue
            
            centroid = hand["centroid"]
            bbox = hand["bbox"]
            w, h = self.config.get("w", 640), self.config.get("h", 480)
            
            test_points = [centroid, [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], 
                           [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]]
            
            current_zone = None
            
            # Kiểm tra vùng của bước hiện tại trước (ưu tiên)
            current_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx]) if self.current_step_idx < len(self.sop_steps) else []
            for z_name in current_step_zones:
                z_pts = self.zones.get(z_name)
                if z_pts:
                    poly = np.array(z_pts, np.float32)
                    if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                        current_zone = z_name
                        break

            # Kiểm tra vùng của bước tiếp theo
            if not current_zone and self.current_step_idx + 1 < len(self.sop_steps):
                next_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1])
                for z_name in next_step_zones:
                    z_pts = self.zones.get(z_name)
                    if z_pts:
                        poly = np.array(z_pts, np.float32)
                        if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                            current_zone = z_name
                            break

            # Kiểm tra vùng bước 1 (để bắt lỗi quay lại)
            if not current_zone and self.current_step_idx > 0:
                step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
                for z_name in step_1_zones:
                    z_pts = self.zones.get(z_name)
                    if z_pts:
                        poly = np.array(z_pts, np.float32)
                        if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                            current_zone = z_name
                            break
            
            active_zones[side] = current_zone
            if current_zone != self.hand_states[side]["zone"]:
                self.log_debug(f"Hand {side.upper()} changed zone: {self.hand_states[side]['zone']} -> {current_zone}", self.product_id)
                self.hand_states[side]["zone"] = current_zone
                self.hand_states[side]["entry_time"] = now

        if self.last_update_time == 0:
            self.last_update_time = now
            self.step_start_time = now
            return self._get_status_result(active_zones, "idle")
            
        self.last_update_time = now
        self.hand_dist = self._get_hand_distance()

        # Cập nhật trạng thái s1_withdrawn
        step_1 = self.sop_steps[0]
        s1_zones = self._get_all_zones_for_step(step_1)
        is_currently_in_s1 = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in s1_zones)
        if not is_currently_in_s1:
            self.s1_withdrawn = True

        if self._completed_at > 0:
            step_1 = self.sop_steps[0]
            step_1_zones = self._get_all_zones_for_step(step_1)
            is_in_s1_zone = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in step_1_zones)
            
            if is_in_s1_zone:
                self._completed_at = 0
                self.reset(now=now)
                self.cycle_count += 1
                self.waiting_for_start = False
            elif now - self._completed_at < 1.0:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0
                self.reset()

        if self.is_failed:
            step_1 = self.sop_steps[0]
            step_1_zones = self._get_all_zones_for_step(step_1)
            is_in_s1_zone = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in step_1_zones)
            if is_in_s1_zone:
                # Reset ngay lập tức khi phát hiện tay đã quay lại bước 1
                self.reset(now=now)
                self.cycle_count += 1
                self.waiting_for_start = False
            else:
                return self._get_status_result(active_zones, "violation")

        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            current_zones = self._get_all_zones_for_step(current_step)
            is_in_current_area = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in current_zones)
            
            if self.waiting_for_start:
                if is_in_current_area:
                    self.waiting_for_start = False
                    self.cycle_count += 1
                    self.step_start_time = now
                    self.last_completed_time = now
                    self.log_debug(f"CYCLE STARTED (Cycle {self.cycle_count})", self.product_id)
                else:
                    self.status_msg = "Sẵn sàng"
                    return self._get_status_result(active_zones, "idle")

            elapsed = now - self.step_start_time
            timeout_limit = current_step.get("timeout_sec", self.config.get("transition_timeout_sec", 15.0))
            if elapsed > timeout_limit:
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                self.log_debug(f"VIOLATION: Timeout at step {self.current_step_idx} ({current_step['step_name']})", self.product_id)
                return self._get_status_result(active_zones, "violation", violation_type="timeout")
            
            # --- KIỂM TRA QUAY LẠI BƯỚC 1 SỚM (PREMATURE RESTART) ĐỂ RESET CHU KỲ MỚI LẬP TỨC ---
            if self.current_step_idx > 0:
                step_1 = self.sop_steps[0]
                s1_zones = self._get_all_zones_for_step(step_1)
                
                # Chỉ check nếu vùng Bước 1 không nằm trong các vùng bước hiện tại
                if not any(z in current_zones for z in s1_zones):
                    # Và chỉ check nếu vùng Bước 1 không nằm trong các vùng của bước tiếp theo (tránh nhầm với skip step sang bước sau)
                    next_zones = []
                    if self.current_step_idx + 1 < len(self.sop_steps):
                        next_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1])
                    
                    if not any(z in next_zones for z in s1_zones):
                        # Tránh báo lỗi khi tay vừa làm xong bước trước đó ở vùng trùng bước 1
                        # Giảm từ 5.0s xuống 1.0s để tăng độ nhạy
                        if not any(z == self.last_completed_zone and (now - self.last_completed_time < 1.0) for z in s1_zones):
                            # Dùng centroid_only=False để phát hiện nhạy nhất (mép tay chạm vào cũng nhận)
                            is_in_s1 = any(self._is_in_zone(side, z, centroid_only=False) for side in ["left", "right"] for z in s1_zones)
                            if is_in_s1 and self.s1_withdrawn:
                                self.is_failed = True
                                self.failed_step_idx = self.current_step_idx
                                self.log_debug(f"VIOLATION: Premature Restart detected at step {self.current_step_idx}", self.product_id)
                                
                                # Trả về lỗi vi phạm cho frame này để kích hoạt loa/clip và hiển thị cảnh báo
                                res = self._get_status_result(active_zones, "violation", violation_type="skip_step")
                                
                                # Reset trạng thái động cơ logic về chu kỳ mới lập tức
                                self.reset(now=now)
                                self.cycle_count += 1
                                self.waiting_for_start = False
                                
                                # Tính luôn bước 1 của chu kỳ mới cho frame này từ chính hands_data hiện tại
                                self._check_step_logic(step_1, now, update_status=True)
                                
                                return res

            if self._check_step_logic(current_step, now):
                min_dwell = current_step.get("min_dwell_sec", self.config.get("min_step_dwell_sec", 0.3))
                if now - self.step_start_time >= min_dwell:
                    self._complete_current_step(now)

            if is_in_current_area:
                self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
                return self._get_status_result(active_zones, "processing")
            else:
                self.status_msg = f"Đang chờ: {current_step['step_name']}"

            # Kiểm tra bỏ bước (Skip Step): Chỉ quan tâm đến bước tiếp theo
            if (now - self.last_completed_time > 1.5):
                if self.current_step_idx + 1 < len(self.sop_steps):
                    next_step = self.sop_steps[self.current_step_idx + 1]
                    next_zones = self._get_all_zones_for_step(next_step)
                    
                    if not (self.last_completed_zone in next_zones and (now - self.last_completed_time < 3.0)):
                        # Cho phép check skip step nếu đã qua thời gian rút tay (1.5s) hoặc tay đã rời khỏi vùng đó
                        has_withdrawn = (now - self.last_completed_time > 1.5) or not (self.last_completed_zone and any(self._is_in_zone(side, self.last_completed_zone) for side in ["left", "right"]))
                        if has_withdrawn:
                            if self._check_step_logic(next_step, now, update_status=False, centroid_only=True):
                                self.skip_frames_counter += 1
                                base_tolerance = self.config.get("violation_tolerance", 3)
                                effective_tolerance = base_tolerance * 1.5
                                
                                if self.skip_frames_counter >= effective_tolerance:
                                    self.is_failed = True
                                    self.failed_step_idx = self.current_step_idx
                                    self.log_debug(f"VIOLATION: Skip Step detected. Next step ({next_step['step_name']}) seen while at step {self.current_step_idx}", self.product_id)
                                    return self._get_status_result(active_zones, "violation", violation_type="skip_step")
                            else:
                                self.skip_frames_counter = 0

        return self._get_status_result(active_zones, "processing")

    def reset(self, now: float = None) -> None:
        self.current_step_idx = 0
        self.is_failed = False
        self.violation_notified = False
        self.violation_type = None
        self.failed_step_idx = -1
        self.step_start_time = now if now else time.time()
        self.last_trigger_states = {}
        self.waiting_for_start = True
        self.active_step_time = 0.0
        self.last_update_time = time.time()
        self._zone_last_seen = {}
        self._stay_timer = {}
        self.hit_count = 0
        self.last_completed_zone = None
        self.last_completed_time = time.time()
        self.reset_dwell_start = 0
        self.s1_withdrawn = True
        self.log_debug("ENGINE RESET", self.product_id)

    def get_status(self) -> Dict[str, Any]:
        return self._get_status_result({"left": None, "right": None}, "idle")

    # --- Internal Helpers ---
    def _complete_current_step(self, now: float):
        step = self.sop_steps[self.current_step_idx]
        self.log_debug(f"STEP COMPLETED: {self.current_step_idx + 1}/{len(self.sop_steps)} - {step['step_name']}", self.product_id)
        self.last_completed_zone = step.get("required_zone")
        self.last_completed_time = now
        
        # Nếu bước vừa hoàn thành có vùng trùng với Bước 1 thì đánh dấu s1_withdrawn = False
        step_1 = self.sop_steps[0]
        s1_zones = self._get_all_zones_for_step(step_1)
        if self.last_completed_zone in s1_zones:
            self.s1_withdrawn = False
            
        self.current_step_idx += 1
        self.step_start_time = now
        self.hit_count = 0
        self.last_trigger_states = {}
        self._stay_timer = {}
        
        self._zone_last_seen = {}
        if self.current_step_idx >= len(self.sop_steps):
            self._completed_at = now

    def _get_status_result(self, active_zones: Dict, status: str, violation_type: str = None) -> Dict:
        step_list = [s["step_name"] for s in self.sop_steps]
        cur_step_name = self.sop_steps[self.current_step_idx]["step_name"] if self.current_step_idx < len(self.sop_steps) else "HOÀN THÀNH"
        
        detected_parts = []
        for side, zone in active_zones.items():
            if zone: detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        res = {
            "sop_status": status,
            "status_msg": self.status_msg,
            "expected_step": cur_step_name,
            "detected_label": detected_label,
            "step_index": self.current_step_idx,
            "progress_percent": (self.current_step_idx / len(self.sop_steps)) * 100 if self.current_step_idx < len(self.sop_steps) else 100,
            "is_failed": self.is_failed,
            "failed_step_idx": self.failed_step_idx,
            "hit_count": self.hit_count,
            "cycle_count": self.cycle_count,
            "hands_info": active_zones,
            "step_list": step_list
        }

        if self.is_failed:
            if violation_type: self.violation_type = violation_type
            if not self.violation_notified:
                self.violation_notified = True
                status = "violation"
            else:
                status = "failed_silent"
            
            msg = "VI PHẠM - QUAY LẠI BƯỚC 1"
            if self.violation_type == "timeout":
                msg = "VI PHẠM - QUÁ THỜI GIAN CHỜ"
            elif self.violation_type == "skip_step":
                msg = "VI PHẠM - BỎ BƯỚC"
            
            res.update({
                "detected_label": msg,
                "sop_status": status,
                "violation_type": self.violation_type or "skip_step",
                "step_index": 0,
                "progress_percent": 0
            })
        return res

    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False) -> bool:
        logic = step.get("logic")
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            grace = 1.5
            if target not in self._zone_last_seen: self._zone_last_seen[target] = {"left": 0, "right": 0}
            if update_status:
                for side in ["left", "right"]:
                    if self._is_in_zone(side, target, centroid_only=centroid_only): self._zone_last_seen[target][side] = now
            time_limit = self.step_start_time
            effective_left = (self._zone_last_seen[target]["left"] > time_limit and now - self._zone_last_seen[target]["left"] < grace)
            effective_right = (self._zone_last_seen[target]["right"] > time_limit and now - self._zone_last_seen[target]["right"] < grace)
            if mode == "both": return effective_left and effective_right
            if mode == "any": return effective_left or effective_right
            return effective_left if mode == "left" else effective_right
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            if target not in self._stay_timer: self._stay_timer[target] = {"left": 0, "right": 0}
            for side in ["left", "right"]:
                if self._is_in_zone(side, target, centroid_only=centroid_only):
                    if self._stay_timer[target][side] == 0 and update_status: self._stay_timer[target][side] = now  
                elif update_status: self._stay_timer[target][side] = 0 
            if mode == "any": return any(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            elif mode == "both": return all(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            return self._stay_timer[target][mode] > 0 and (now - self._stay_timer[target][mode]) >= min_dur
        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("required_count", 1)
            mode = step.get("active_hand", "any")
            any_in = False
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                if is_in:
                    if mode == "any" or mode == side:
                        any_in = True
                if update_status:
                    if is_in and not self.last_trigger_states.get(side, False): self.hit_count += 1
                    self.last_trigger_states[side] = is_in
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only)
                return any_in
            return self.hit_count >= count_needed
        elif logic == "dual_task":
            l_zone, r_zone = step.get("left_zone"), step.get("right_zone")
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("right", r_zone, centroid_only=centroid_only)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("left", r_zone, centroid_only=centroid_only)
                return cond1 or cond2

            # Khởi tạo trạng thái tích lũy nếu chưa có trong last_trigger_states
            if "dual_left_in_l" not in self.last_trigger_states:
                self.last_trigger_states["dual_left_in_l"] = False
                self.last_trigger_states["dual_right_in_r"] = False
                self.last_trigger_states["dual_right_in_l"] = False
                self.last_trigger_states["dual_left_in_r"] = False

            # Cập nhật trạng thái khi phát hiện tay trong vùng
            if self._is_in_zone("left", l_zone, centroid_only=centroid_only):
                self.last_trigger_states["dual_left_in_l"] = True
            if self._is_in_zone("right", r_zone, centroid_only=centroid_only):
                self.last_trigger_states["dual_right_in_r"] = True
            if self._is_in_zone("right", l_zone, centroid_only=centroid_only):
                self.last_trigger_states["dual_right_in_l"] = True
            if self._is_in_zone("left", r_zone, centroid_only=centroid_only):
                self.last_trigger_states["dual_left_in_r"] = True

            # Trạng thái hoàn thành: hoặc đúng chiều (Trái-Trái và Phải-Giữa), hoặc ngược chiều (Phải-Trái và Trái-Giữa)
            normal_match = self.last_trigger_states["dual_left_in_l"] and self.last_trigger_states["dual_right_in_r"]
            swapped_match = self.last_trigger_states["dual_right_in_l"] and self.last_trigger_states["dual_left_in_r"]
            
            return normal_match or swapped_match
        return False

    def _is_in_zone(self, side: str, zone_name: str, centroid_only: bool = False) -> bool:
        zone_pts = self.zones.get(zone_name)
        if not zone_pts: return False
        
        poly = np.array(zone_pts, np.float32)
        w, h = self.config.get("w", 640), self.config.get("h", 480)
        for hand in self.last_hands:
            if hand["label"].lower() != side: continue
            centroid = hand["centroid"]
            if centroid_only: test_points = [centroid]
            else:
                bbox = hand["bbox"]
                test_points = [centroid, [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]]
            if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points): return True
        return False

    def _get_all_zones_for_step(self, step: Dict) -> List[str]:
        z = []
        if "required_zone" in step: z.append(step["required_zone"])
        if "left_zone" in step: z.append(step["left_zone"])
        if "right_zone" in step: z.append(step["right_zone"])
        return z

    def _get_hand_distance(self) -> float:
        if len(self.last_hands) < 2: return -1.0
        l_pos, r_pos = None, None
        for h in self.last_hands:
            if h["label"] == "left": l_pos = h["centroid"]
            if h["label"] == "right": r_pos = h["centroid"]
        if l_pos and r_pos: return np.sqrt((l_pos[0]-r_pos[0])**2 + (l_pos[1]-r_pos[1])**2)
        return -1.0
