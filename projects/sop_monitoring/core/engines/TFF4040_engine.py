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
    Engine logic cho mã sản phẩm TFF4040.
    Thực hiện logic không gian dựa trên vùng (Zones).
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {"w": 640, "h": 480})
        self.product_id = "TFF4040" # ID này nên được truyền từ loader
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
        self.last_products = []
        self.last_robots = []
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
        self.hand_last_seen = {"left": 0.0, "right": 0.0}
        self.robot_entered_zone = {}
        
        self._zone_last_seen = {}
        self._stay_timer = {}
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        self.hand_history = {"left": [], "right": []}
        self.hit_count = 0
        self.last_trigger_states = {}
        self.waiting_for_start = True
        self.skip_frames_counter = 0
        self.reset_dwell_start = 0.0
        self.cycle_count = 0
        self.in_delayed_restart = False
        self.restart_step_idx = 0
        self.s1_withdrawn = True
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        self.robot_in_mold_start_time = 0.0
        
        logger.info(f"ProductEngine [TFF4040]: Initialized for station {self.station_id}")
        self.log_debug("--- NEW ENGINE INITIALIZED ---", self.product_id)

    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
               robot_data: List[Dict] = None) -> Dict[str, Any]:
        now = time.time()
        self.last_hands = hands_data
        self.last_products = products_data if products_data is not None else []
        self.last_robots = robot_data if robot_data is not None else []

        # Nếu có cờ chờ khởi động lại từ Robot ở frame trước
        if getattr(self, "pending_robot_restart", False):
            self.pending_robot_restart = False
            if hasattr(self, "missing_steps_str"):
                delattr(self, "missing_steps_str")
            self.reset(now=now)
            self.cycle_count += 1
            self.waiting_for_start = False
            self.cycle_start_time = now
            self.start_zone_entry_time = 0.0
            self.robot_in_mold_start_time = now
            
            # Tính luôn bước 1 của chu kỳ mới cho frame này
            step_1 = self.sop_steps[0]
            self._check_step_logic(step_1, now, update_status=True)
            
            active_zones_new = {"left": None, "right": None}
            for side in ["left", "right"]:
                current_zone = None
                current_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx]) if self.current_step_idx < len(self.sop_steps) else []
                for z_name in current_step_zones:
                    if self._is_in_zone(side, z_name):
                        current_zone = z_name
                        break
                active_zones_new[side] = current_zone
                self.hand_states[side]["zone"] = current_zone
                self.hand_states[side]["entry_time"] = now
            
            return self._get_status_result(active_zones_new, "processing")
        
        # Cập nhật trạng thái rút tay của bước 1 cho frame sau, lưu trạng thái trước đó lại
        was_s1_withdrawn = self.s1_withdrawn
        step_1 = self.sop_steps[0]
        s1_zones = self._get_all_zones_for_step(step_1)
        is_currently_in_s1 = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in s1_zones)
        if not is_currently_in_s1:
            self.s1_withdrawn = True

        # Tự động bắt đầu chu kỳ mới nếu robot được đưa vào khuôn (giữ vững >= min_dwell_sec)
        # Kể cả khi chu kỳ cũ chưa hoàn thành hoặc đang bị lỗi (is_failed)
        robot_in_mold = self._is_object_in_zone(self.last_robots, "mold")
        if robot_in_mold:
            if self.robot_in_mold_start_time == 0.0:
                self.robot_in_mold_start_time = now
            min_dwell = step_1.get("min_dwell_sec", 0.3)
            if now - self.robot_in_mold_start_time >= min_dwell:
                # Nếu chu kỳ cũ chưa hoàn thành (và chưa ở trạng thái lỗi)
                if self.current_step_idx > 0 and not self.waiting_for_start and not self.is_failed:
                    # Báo thiếu các bước chưa làm xong của chu kỳ cũ
                    missing_steps = [s["step_name"] for s in self.sop_steps[self.current_step_idx:]]
                    self.missing_steps_str = f"Thiếu: {', '.join(missing_steps)}"
                    self.is_failed = True
                    self.violation_type = "skip_step"
                    self.failed_step_idx = self.current_step_idx
                    self.pending_robot_restart = True
                    
                    self.log_debug(
                        f"Phát hiện Robot trong khuôn (>= {min_dwell}s) khi chu kỳ cũ chưa xong (Step {self.current_step_idx}). "
                        f"Báo lỗi thiếu các bước: {missing_steps}. Sẽ khởi động chu kỳ mới ở frame tiếp theo.", 
                        self.product_id
                    )
                    active_zones = {"left": None, "right": None}
                    return self._get_status_result(active_zones, "violation", violation_type="skip_step")
                
                # Nếu đang ở trạng thái lỗi sẵn rồi, hoặc robot vào khuôn để bắt đầu lại
                elif self.is_failed or (self.current_step_idx > 0 and not self.waiting_for_start):
                    self.log_debug(
                        f"Phát hiện Robot trong khuôn (>= {min_dwell}s) khi đang bị lỗi hoặc chu kỳ cũ chưa xong. Bắt đầu chu kỳ mới lập tức.", 
                        self.product_id
                    )
                    self.reset(now=now)
                    self.cycle_count += 1
                    self.waiting_for_start = False
                    self.cycle_start_time = now
                    self.start_zone_entry_time = 0.0
                    self.robot_in_mold_start_time = now
                    
                    # Tính luôn bước 1 của chu kỳ mới cho frame này
                    self._check_step_logic(step_1, now, update_status=True)
                    
                    active_zones_new = {"left": None, "right": None}
                    for side in ["left", "right"]:
                        current_zone = None
                        current_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx]) if self.current_step_idx < len(self.sop_steps) else []
                        for z_name in current_step_zones:
                            if self._is_in_zone(side, z_name):
                                current_zone = z_name
                                break
                        active_zones_new[side] = current_zone
                        self.hand_states[side]["zone"] = current_zone
                        self.hand_states[side]["entry_time"] = now
                    
                    return self._get_status_result(active_zones_new, "processing")
        else:
            self.robot_in_mold_start_time = 0.0
            
        # Cập nhật thời gian nhìn thấy tay và xóa vùng nếu không xuất hiện quá 0.3s
        seen_sides = set()
        for hand in hands_data:
            side = hand["label"].lower()
            if side in ["left", "right"]:
                self.hand_last_seen[side] = now
                seen_sides.add(side)
                
        for side in ["left", "right"]:
            if side not in seen_sides:
                if self.hand_last_seen[side] > 0.0 and (now - self.hand_last_seen[side] > 0.8):
                    if self.hand_states[side]["zone"] is not None:
                        self.log_debug(f"Hand {side.upper()} lost for >0.8s. Clearing zone {self.hand_states[side]['zone']}.", self.product_id)
                        self.hand_states[side]["zone"] = None
                        self.hand_states[side]["entry_time"] = 0.0
        
        # 1. Cập nhật vị trí
        active_zones = {"left": None, "right": None}
        for side in ["left", "right"]:
            current_zone = None
            
            # Kiểm tra vùng của bước hiện tại trước (ưu tiên)
            current_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx]) if self.current_step_idx < len(self.sop_steps) else []
            for z_name in current_step_zones:
                if self._is_in_zone(side, z_name):
                    current_zone = z_name
                    break

            # Kiểm tra vùng của bước tiếp theo
            if not current_zone and self.current_step_idx + 1 < len(self.sop_steps):
                next_step_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1])
                for z_name in next_step_zones:
                    if self._is_in_zone(side, z_name):
                        current_zone = z_name
                        break

            # Kiểm tra vùng bước 1 (để bắt lỗi quay lại)
            if not current_zone and self.current_step_idx > 0:
                step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
                for z_name in step_1_zones:
                    if self._is_in_zone(side, z_name):
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

        if self._completed_at > 0:
            if now - self._completed_at < 1.5:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0
                self.reset(now=now)

        if self.is_failed:
            # Khi đang bị lỗi, chỉ cho phép Robot vào khuôn tự động reset (đã xử lý ở phần check robot).
            # Tay công nhân quay lại bước 1 không được tính để reset chu kỳ.
            return self._get_status_result(active_zones, "violation", violation_type=self.violation_type)

        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            current_zones = self._get_all_zones_for_step(current_step)
            if current_step.get("logic") == "robot_and_zone_absent":
                target = current_step.get("required_zone")
                is_in_current_area = self._is_object_in_zone(self.last_robots, target)
            else:
                is_in_current_area = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in current_zones)
            
            # Nới lỏng Bước 5: Nếu phát hiện tay ở vùng Bước 2 (mold) và giữ vững >= 0.2s, tự động hoàn thành Bước 5
            # (Fallback: cho phép tay quay lại mold sau khi bấm nút — bước này không còn cần shortcut nữa vì
            # step 5 chỉ cần tay phải bấm button_right đúng 1 lần)
            # Đã xóa shortcut vì quy trình mới không có bước phụ sau nút
            
            if self.waiting_for_start:
                if is_in_current_area:
                    if self.start_zone_entry_time == 0:
                        self.start_zone_entry_time = now
                    if now - self.start_zone_entry_time >= 0.3:
                        self.waiting_for_start = False
                        self.cycle_start_time = now
                        self.cycle_count += 1
                        self.step_start_time = now
                        self.last_completed_time = now
                        self.start_zone_entry_time = 0
                        self.log_debug(f"CYCLE STARTED (Cycle {self.cycle_count})", self.product_id)
                    else:
                        self.status_msg = "Sẵn sàng (Đang kích hoạt...)"
                        return self._get_status_result(active_zones, "idle")
                else:
                    self.start_zone_entry_time = 0
                    self.status_msg = "Sẵn sàng"
                    return self._get_status_result(active_zones, "idle")

            # Lỗi vi phạm quá thời gian chu kỳ (36 giây kể từ lúc bắt đầu chu kỳ)
            cycle_elapsed = now - self.cycle_start_time
            if cycle_elapsed > 36.0:
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                self.log_debug(f"VIOLATION: Cycle Timeout (>36s) at step {self.current_step_idx} ({current_step['step_name']})", self.product_id)
                return self._get_status_result(active_zones, "violation", violation_type="timeout")
            
            # --- TỰ ĐỘNG RESET CHU KỲ MỚI LẬP TỨC KHI TAY QUAY LẠI BƯỚC 1 (KHÔNG BÁO LỖI) ---
            # ĐÃ BỎ: Chỉ đếm chu kỳ khi tay robot vào khuôn, không cho phép tay công nhân reset chu kỳ mới.
            if self.current_step_idx > self.restart_threshold and self.current_step_idx < len(self.sop_steps) - 1 and self.s1_withdrawn and (now - self.last_completed_time > 2.5) and not is_in_current_area:
                step_1 = self.sop_steps[0]
                s1_zones = self._get_all_zones_for_step(step_1)
                
                # Chỉ check nếu vùng Bước 1 không nằm trong các vùng bước hiện tại và vùng bước tiếp theo
                if not any(z in current_zones for z in s1_zones):
                    next_zones = []
                    if self.current_step_idx + 1 < len(self.sop_steps):
                        next_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1])
                    
                    if not any(z in next_zones for z in s1_zones):
                        # Tránh trùng lặp khi vừa hoàn thành bước trước
                        if not any(z == self.last_completed_zone and (now - self.last_completed_time < 1.0) for z in s1_zones):
                            is_in_s1 = any(self._is_in_zone(side, z, centroid_only=False) for side in ["left", "right"] for z in s1_zones)
                            is_in_s1_sustained = False
                            for side in ["left", "right"]:
                                for z in s1_zones:
                                    if self._is_in_zone(side, z):
                                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                                        if entry > self.step_start_time and (now - entry >= 0.2):
                                            is_in_s1_sustained = True
                                            break
                                if is_in_s1_sustained:
                                    break
                                    
                            if is_in_s1_sustained:
                                self.is_failed = True
                                self.violation_type = "skip_step"
                                self.failed_step_idx = self.current_step_idx
                                self.log_debug(f"VIOLATION: Skip Step detected. Returned to Step 1 (mold) at step {self.current_step_idx}", self.product_id)
                                return self._get_status_result(active_zones, "violation", violation_type="skip_step")
                            else:
                                if not is_in_s1:
                                    self.start_zone_entry_time = 0

            if self._check_step_logic(current_step, now):
                min_dwell = current_step.get("min_dwell_sec", self.config.get("min_step_dwell_sec", 0.3))
                if now - self.step_start_time >= min_dwell:
                    self._complete_current_step(now)

            if is_in_current_area:
                self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
                return self._get_status_result(active_zones, "processing")
            else:
                self.status_msg = f"Đang chờ: {current_step['step_name']}"

            pass

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
        self.robot_entered_zone = {}
        self._zone_last_seen = {}
        self._stay_timer = {}
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        self.hit_count = 0
        self.last_completed_zone = None
        self.last_completed_time = now if now else time.time()
        self.reset_dwell_start = 0
        self.in_delayed_restart = False
        self.restart_step_idx = 0
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        self.robot_in_mold_start_time = 0.0
        if hasattr(self, "missing_steps_str"):
            delattr(self, "missing_steps_str")
        self.hand_states = {
            "left": {"zone": None, "entry_time": 0.0},
            "right": {"zone": None, "entry_time": 0.0}
        }
        self.hand_last_seen = {"left": 0.0, "right": 0.0}
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
        self.last_trigger_states = {} # Reset trigger states to allow immediate detection in next step
        self._stay_timer = {}
        # Xóa lịch sử vùng của bước tiếp theo để tránh kích hoạt tức thì
        if self.current_step_idx < len(self.sop_steps):
            next_step = self.sop_steps[self.current_step_idx]
            next_zones = self._get_all_zones_for_step(next_step)
            for nz in next_zones:
                if nz in self._zone_last_seen:
                    self._zone_last_seen[nz] = {"left": 0, "right": 0}
        
        self._zone_last_seen = {} # Reset toàn bộ cho chắc chắn
        self.robot_entered_zone = {}
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        if self.current_step_idx >= len(self.sop_steps):
            self._completed_at = now

    def _get_status_result(self, active_zones: Dict, status: str, violation_type: str = None) -> Dict:
        step_list = [s["step_name"] for s in self.sop_steps]
        cur_step_name = self.sop_steps[self.current_step_idx]["step_name"] if self.current_step_idx < len(self.sop_steps) else "HOÀN THÀNH"
        
        detected_parts = []
        for side, zone in active_zones.items():
            if zone: detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        if self.waiting_for_start:
            cycle_time_left = 36.0
        elif self.is_failed:
            cycle_time_left = 0.0
        elif self.current_step_idx >= len(self.sop_steps):
            cycle_time_left = 0.0
        else:
            cycle_time_left = max(0.0, 36.0 - (self.last_update_time - self.cycle_start_time))

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
            "step_list": step_list,
            "cycle_time_left": cycle_time_left,
            "max_cycle_time": 36.0
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
                "progress_percent": 0,
                "cycle_time_left": 0.0
            })
            if hasattr(self, "missing_steps_str") and self.missing_steps_str:
                res["expected_step"] = self.missing_steps_str
        return res

    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False, shrink_factor: float = 0.0) -> bool:
        logic = step.get("logic")

        # --- LOGIC MỚI: Robot lấy SP hoàn thành khi robot in mold + mold trống ---
        if logic == "robot_and_zone_absent":
            target = step.get("required_zone")
            require_robot = step.get("require_robot", False)
            require_absent = step.get("require_product_absent", False)
            min_dwell = step.get("min_dwell_sec", 0.3)

            robot_in_zone = self._is_object_in_zone(self.last_robots, target)
            product_gone = not self._is_product_in_zone(target)

            # Dwell timer cho robot trong zone
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if robot_in_zone:
                if self._zone_last_seen[target]["left"] == 0.0:
                    self._zone_last_seen[target]["left"] = now
                dwell_ok = (now - self._zone_last_seen[target]["left"]) >= min_dwell
                if dwell_ok:
                    self.robot_entered_zone[target] = True
            else:
                self._zone_last_seen[target]["left"] = 0.0

            if require_robot:
                if not self.robot_entered_zone.get(target, False):
                    return False
                if robot_in_zone:
                    return False

            if require_absent and not product_gone:
                return False
            return True

        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            
            if target not in self._zone_triggered:
                self._zone_triggered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                if is_in and step.get("require_product", False):
                    if not self._is_product_in_zone(target):
                        is_in = False
                if is_in:
                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                    required_dwell = step.get("min_dwell_sec", 0.2)
                    if entry > 0.0 and (now - entry >= required_dwell):
                        if update_status:
                            self._zone_triggered[target][side] = True
                            
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                elif mode == "nearest_2":
                    nearest = self._select_nearest_hands(self.last_hands, "work_area", n=2)
                    return any(self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                               for side in nearest)
                return any(self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor) for side in ["left", "right"])

            if mode == "both":
                return self._zone_triggered[target]["left"] and self._zone_triggered[target]["right"]
            elif mode == "nearest_2":
                nearest = self._select_nearest_hands(self.last_hands, "work_area", n=2)
                return any(self._zone_triggered[target].get(s, False) for s in nearest)
            elif mode == "any":
                return self._zone_triggered[target]["left"] or self._zone_triggered[target]["right"]
            else:
                return self._zone_triggered[target].get(mode, False)
                
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            if target not in self._stay_timer: self._stay_timer[target] = {"left": 0, "right": 0}

            # nearest_2: chỉ lấy 2 tay gần work_area nhất
            if mode == "nearest_2":
                nearest = self._select_nearest_hands(self.last_hands, "work_area", n=2)
                for side in nearest:
                    is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                    if is_in and step.get("require_product", False):
                        if not self._is_product_in_zone(target):
                            is_in = False
                    if is_in:
                        if self._stay_timer[target][side] == 0 and update_status:
                            self._stay_timer[target][side] = now
                    elif update_status:
                        self._stay_timer[target][side] = 0
                return all(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in nearest)
            else:
                for side in ["left", "right"]:
                    is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                    if is_in and step.get("require_product", False):
                        if not self._is_product_in_zone(target):
                            is_in = False
                    if is_in:
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

            # nearest_2: chỉ lấy 2 tay gần work_area nhất
            if mode == "nearest_2":
                nearest = self._select_nearest_hands(self.last_hands, "work_area", n=2)
            else:
                nearest = {"left", "right"}

            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hit_registered:
                self._hit_registered[target] = {"left": False, "right": False}

            for side in ["left", "right"]:
                # nearest_2: bỏ qua tay không trong nearest set
                if mode == "nearest_2" and side not in nearest:
                    continue

                is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                if is_in and step.get("require_product", False):
                    if not self._is_product_in_zone(target):
                        is_in = False
                is_in_debounced = is_in
                if not is_in and update_status:
                    last_seen = self._zone_last_seen[target].get(side, 0.0)
                    if last_seen > 0 and (now - last_seen < 0.3):
                        is_in_debounced = True

                if update_status:
                    if is_in:
                        self._zone_last_seen[target][side] = now

                if side not in self.last_trigger_states:
                    was_already_in = (
                        self.current_step_idx > 0 and
                        self.hand_states[side]["zone"] == target and
                        self.hand_states[side]["entry_time"] < self.step_start_time
                    )
                    self.last_trigger_states[side] = was_already_in

                if update_status:
                    if is_in_debounced:
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if not self._hit_registered.get(target, {}).get(side, False):
                                self.hit_count += 1
                                if target not in self._hit_registered:
                                    self._hit_registered[target] = {"left": False, "right": False}
                                self._hit_registered[target][side] = True
                                self.log_debug(f"Multi-trigger hit counted for {side} hand in {target}. Hit count: {self.hit_count}/{count_needed}", self.product_id)
                    else:
                        if target in self._hit_registered:
                            self._hit_registered[target][side] = False
                    self.last_trigger_states[side] = is_in_debounced

            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                elif mode == "nearest_2":
                    return any(self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor) for side in nearest)
                return any_in

            # Cho phép hoàn thành bước 1 (robot lấy SP) bằng 1 trigger + withdrawal
            # Bước 2, 4 (multi_trigger với nearest_2) không cần shortcut này
            if self.current_step_idx == 0:
                if self.hit_count >= count_needed:
                    return True
                s1_any_in = False
                for side in ["left", "right"]:
                    if self.last_trigger_states.get(side, False):
                        s1_any_in = True
                if self.hit_count >= 1 and not s1_any_in:
                    return True
                return False

            return self.hit_count >= count_needed
            
        elif logic == "dual_task":
            l_zone, r_zone = step.get("left_zone"), step.get("right_zone")
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only, shrink_factor=shrink_factor) and                         self._is_in_zone("right", r_zone, centroid_only=centroid_only, shrink_factor=shrink_factor)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only, shrink_factor=shrink_factor) and                         self._is_in_zone("left", r_zone, centroid_only=centroid_only, shrink_factor=shrink_factor)
                return cond1 or cond2

            # Chỉ ghi nhận kích hoạt khi tay giữ trong vùng ít nhất 0.2s
            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    is_in = self._is_in_zone(side, z, centroid_only=centroid_only, shrink_factor=shrink_factor)
                    if is_in and step.get("require_product", False):
                        if not self._is_product_in_zone(z):
                            is_in = False
                    if is_in:
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if side == "left" and z == l_zone:
                                self.last_trigger_states["dual_left_in_l"] = True
                            if side == "right" and z == r_zone:
                                self.last_trigger_states["dual_right_in_r"] = True
                            if side == "right" and z == l_zone:
                                self.last_trigger_states["dual_right_in_l"] = True
                            if side == "left" and z == r_zone:
                                self.last_trigger_states["dual_left_in_r"] = True

            normal_match = self.last_trigger_states.get("dual_left_in_l", False) and self.last_trigger_states.get("dual_right_in_r", False)
            swapped_match = self.last_trigger_states.get("dual_right_in_l", False) and self.last_trigger_states.get("dual_left_in_r", False)
            return normal_match or swapped_match
        return False
    def _is_product_in_zone(self, zone_name: str) -> bool:
        if not hasattr(self, 'last_products') or not self.last_products:
            return False
            
        zone_pts = self.zones.get(zone_name)
        if not zone_pts: return False
        
        poly = np.array(zone_pts, np.float32)
        w, h = self.config.get("w", 640), self.config.get("h", 480)
        for prod in self.last_products:
            centroid = prod.get("centroid")
            if not centroid:
                bbox = prod["bbox"]
                centroid = [(bbox[0] + bbox[2]) / 2 / w, (bbox[1] + bbox[3]) / 2 / h]
            if cv2.pointPolygonTest(poly, (centroid[0], centroid[1]), False) >= 0:
                return True
            bbox = prod["bbox"]
            points = [
                [bbox[0]/w, bbox[1]/h],
                [bbox[2]/w, bbox[1]/h],
                [bbox[0]/w, bbox[3]/h],
                [bbox[2]/w, bbox[3]/h]
            ]
            if any(cv2.pointPolygonTest(poly, (pt[0], pt[1]), False) >= 0 for pt in points):
                return True
        return False

    def _is_in_zone(self, side: str, zone_name: str, centroid_only: bool = False, shrink_factor: float = 0.0) -> bool:
        zone_pts = self.zones.get(zone_name)
        if not zone_pts: return False
        
        # Cơ chế Shrink: Thu nhỏ đa giác để kiểm tra vi phạm khắt khe hơn
        if shrink_factor > 0:
            poly = np.array(zone_pts, np.float32)
            M = cv2.moments(poly)
            if M["m00"] != 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                # Di chuyển các điểm về phía tâm
                shrunk_poly = []
                for pt in zone_pts:
                    px = pt[0] + (cx - pt[0]) * shrink_factor
                    py = pt[1] + (cy - pt[1]) * shrink_factor
                    shrunk_poly.append([px, py])
                zone_pts = shrunk_poly

        w, h = self.config.get("w", 640), self.config.get("h", 480)
        for hand in self.last_hands:
            if hand["label"].lower() != side: continue
            if self._check_bbox_polygon_intersection(hand["bbox"], zone_pts, hand["centroid"], w, h, centroid_only):
                return True
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
