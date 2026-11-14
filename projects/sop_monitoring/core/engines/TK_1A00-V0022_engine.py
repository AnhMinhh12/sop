import time
import logging
import os
import cv2
import numpy as np
from typing import Dict, List, Any, Optional
from projects.sop_monitoring.core.engines.base_engine import BaseEngine
from projects.sop_monitoring.core.turntable_counter import TurntableCounter

logger = logging.getLogger(__name__)

class ProductEngine(BaseEngine):
    """
    Engine logic cho mã sản phẩm TK_1A00-V0022 (Trạm 04 - Máy 4).
    Quy trình gồm 3 bước chuẩn hóa theo chuẩn kiến trúc Máy 4 (tham khảo 639957):
    - Bước 1: Lấy sản phẩm ra khỏi khuôn (zone_trigger: mold)
    - Bước 2: Lắp 2 linh kiện vào khuôn (multi_trigger: mold, required_count: 2)
    - Bước 3: 2 tay đồng thời bấm 2 nút (dual_task: button_left & button_right)
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id", "04")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {"w": 640, "h": 480})
        self.product_id = "TK_1A00-V0022"
        self.restart_threshold = self.config.get("restart_allowed_until_step", 1)
        
        # Sắp xếp vùng theo diện tích để ưu tiên kiểm tra vùng nhỏ trước
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
        self._completed_at = 0.0
        self.last_hands = []
        self.last_products = []
        self.hand_dist = -1.0
        
        self.is_failed = False
        self.violation_notified = False
        self.failed_step_idx = -1
        self.violation_type = None
        self.last_completed_zone = None
        self.last_completed_time = 0.0
        self.status_msg = "Sẵn sàng"
        
        self.hand_states = {
            "left": {"zone": None, "entry_time": 0.0},
            "right": {"zone": None, "entry_time": 0.0}
        }
        
        self._zone_last_seen = {}
        self._stay_timer = {}
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        self.hit_count = 0
        self.last_trigger_states = {}
        self.waiting_for_start = True
        self.skip_frames_counter = 0
        self.reset_dwell_start = 0.0
        self.cycle_count = 0
        self.s1_withdrawn = True
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        
        self.both_buttons_pressed = False

        # Khởi tạo bộ đếm mâm xoay TurntableCounter
        self.turntable_counter = TurntableCounter(
            station_id=self.station_id,
            product_id=self.product_id,
            products_per_cycle=1,
            spins_per_product=2,
            require_product_popup=False,
            debounce_sec=3.5,
            wait_spin_timeout_sec=10.0,
            wait_popup_timeout_sec=6.0,
            min_spin_duration=0.7,
            max_spin_duration=4.5,
            max_allowed_spin_sec=5.5
        )

        # Tải số lượng sản phẩm từ DB nếu có
        try:
            from shared.db.queries import EventQueries
            today_str = time.strftime('%Y-%m-%d')
            db_summary = EventQueries.get_daily_summary(today_str, camera_id=self.station_id)
            self.turntable_counter.total_products = int(db_summary.get("total_products", 0))
            logger.info(f"ProductEngine [{self.product_id}]: Loaded today total_products = {self.turntable_counter.total_products}")
        except Exception as e:
            logger.warning(f"ProductEngine [{self.product_id}]: Could not load history from DB: {e}")

        logger.info(f"ProductEngine [{self.product_id}]: Initialized successfully for station {self.station_id}")
        self.log_debug(f"--- NEW ENGINE INITIALIZED ({self.product_id}) ---", self.product_id)

    def update_turntable_motion(self, frame: np.ndarray, curr_time: float) -> None:
        """Được FrameProcessor gọi mỗi frame để theo dõi chuyển động MOG2 trên mâm xoay."""
        turntable_poly = self.zones.get("mold") or self.zones.get("work_area")
        if not turntable_poly:
            return

        popup_poly = self.zones.get("product_popup")
        hand_in_mold = any(self._is_in_zone(side, "mold") for side in ["left", "right"])

        # Cập nhật bộ đếm mâm xoay
        self.turntable_counter.update(
            frame=frame,
            curr_time=curr_time,
            turntable_poly_normalized=turntable_poly,
            popup_poly_normalized=popup_poly,
            is_button_triggered=self.both_buttons_pressed,
            is_hand_in_mold=hand_in_mold
        )

        # Cảnh báo an toàn nếu tay nằm trong khuôn khi mâm đang xoay sau khi ấn nút
        if self.turntable_counter.safety_violation == "hand_in_spinning_turntable" and not self.is_failed:
            self.is_failed = True
            self.violation_type = "hand_in_spinning_turntable"
            self.failed_step_idx = self.current_step_idx
            self.status_msg = "NGUY HIỂM: Đưa tay vào khuôn khi mâm đang quay!"
            logger.warning(f"[{self.product_id}] VIOLATION: Hand in mold while turntable spinning!")

    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
               robot_data: List[Dict] = None) -> Dict[str, Any]:
        now = time.time()
        self.last_hands = hands_data
        self.last_products = products_data if products_data is not None else []
        
        # Cập nhật trạng thái rút tay của bước 1 cho frame sau
        step_1 = self.sop_steps[0] if self.sop_steps else {}
        s1_zones = self._get_all_zones_for_step(step_1)
        is_currently_in_s1 = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in s1_zones)
        if not is_currently_in_s1:
            self.s1_withdrawn = True
        
        # 1. Cập nhật vị trí các tay
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

            # Kiểm tra vùng bước 1 (để bắt lỗi quay lại hoặc reset)
            if not current_zone and self.current_step_idx > 0:
                step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
                for z_name in step_1_zones:
                    if self._is_in_zone(side, z_name):
                        current_zone = z_name
                        break
            
            active_zones[side] = current_zone
            if current_zone != self.hand_states[side]["zone"]:
                self.hand_states[side]["zone"] = current_zone
                self.hand_states[side]["entry_time"] = now

        if self.last_update_time == 0:
            self.last_update_time = now
            self.step_start_time = now
            return self._get_status_result(active_zones, "idle")
            
        self.last_update_time = now
        self.hand_dist = self._get_hand_distance()

        # Hiển thị hoàn thành chu kỳ
        if self._completed_at > 0:
            if now - self._completed_at < 2.0:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0.0
                self.reset(now=now)

        # Xử lý khi đang vi phạm
        if self.is_failed:
            step_1_zones = self._get_all_zones_for_step(self.sop_steps[0]) if self.sop_steps else []
            is_in_s1_zone_sustained = False
            for side in ["left", "right"]:
                for z in step_1_zones:
                    if self._is_in_zone(side, z):
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                        if now - entry >= 0.3:
                            is_in_s1_zone_sustained = True
                            break
                if is_in_s1_zone_sustained:
                    break
                    
            if is_in_s1_zone_sustained:
                self.log_debug("Phát hiện tay quay lại Bước 1 khi đang bị lỗi. Tự động reset và bắt đầu chu kỳ mới.", self.product_id)
                self.reset(now=now)
                self.cycle_count += 1
                self.waiting_for_start = False
                self.cycle_start_time = now
                self.start_zone_entry_time = 0.0
            else:
                return self._get_status_result(active_zones, "violation", violation_type=self.violation_type)

        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            current_zones = self._get_all_zones_for_step(current_step)
            is_in_current_area = any(self._is_in_zone(side, z) for side in ["left", "right"] for z in current_zones)
            
            # Đang chờ kích hoạt chu kỳ mới ở Bước 1
            if self.waiting_for_start:
                if is_in_current_area:
                    if self.start_zone_entry_time == 0:
                        self.start_zone_entry_time = now
                    if now - self.start_zone_entry_time >= 0.2:
                        self.waiting_for_start = False
                        self.cycle_start_time = now
                        self.cycle_count += 1
                        self.step_start_time = now
                        self.last_completed_time = now
                        self.start_zone_entry_time = 0.0
                        self.log_debug(f"CYCLE STARTED (Cycle {self.cycle_count})", self.product_id)
                    else:
                        self.status_msg = "Sẵn sàng (Đang kích hoạt...)"
                        return self._get_status_result(active_zones, "idle")
                else:
                    self.start_zone_entry_time = 0.0
                    self.status_msg = "Sẵn sàng"
                    return self._get_status_result(active_zones, "idle")

            # Lỗi vi phạm quá thời gian chu kỳ (max_cycle_time_sec)
            max_cycle = self.config.get("max_cycle_time_sec", 60.0)
            cycle_elapsed = now - self.cycle_start_time
            if cycle_elapsed > max_cycle:
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                self.log_debug(f"VIOLATION: Cycle Timeout (>{max_cycle}s) at step {self.current_step_idx} ({current_step['step_name']})", self.product_id)
                return self._get_status_result(active_zones, "violation", violation_type="timeout")

            elapsed = now - self.step_start_time
            timeout_limit = current_step.get("timeout_sec", self.config.get("transition_timeout_sec", 60.0))
            if elapsed > timeout_limit:
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                self.log_debug(f"VIOLATION: Step Timeout at step {self.current_step_idx} ({current_step['step_name']})", self.product_id)
                return self._get_status_result(active_zones, "violation", violation_type="timeout")
            
            # Tự động reset chu kỳ mới khi tay quay lại bước 1 ở đầu chu kỳ
            if 0 < self.current_step_idx <= self.restart_threshold and self.s1_withdrawn:
                step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
                if not any(z in current_zones for z in step_1_zones):
                    next_zones = self._get_all_zones_for_step(self.sop_steps[self.current_step_idx + 1]) if self.current_step_idx + 1 < len(self.sop_steps) else []
                    if not any(z in next_zones for z in step_1_zones):
                        is_in_s1_sustained = False
                        for side in ["left", "right"]:
                            for z in step_1_zones:
                                if self._is_in_zone(side, z):
                                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                                    if entry > self.step_start_time and (now - entry >= 0.2):
                                        is_in_s1_sustained = True
                                        break
                            if is_in_s1_sustained:
                                break
                                
                        if is_in_s1_sustained:
                            self.log_debug(f"Quay lại bước 1 phát hiện ở bước {self.current_step_idx}. Tự động reset chu kỳ mới.", self.product_id)
                            self.reset(now=now)
                            self.cycle_count += 1
                            self.waiting_for_start = False
                            self.cycle_start_time = now
                            self.start_zone_entry_time = 0.0
                            self._check_step_logic(self.sop_steps[0], now, update_status=True)
                            return self._get_status_result(active_zones, "processing")

            # Kiểm tra hoàn thành bước hiện tại
            if self._check_step_logic(current_step, now):
                min_dwell = current_step.get("min_dwell_sec", self.config.get("min_step_dwell_sec", 0.2))
                if now - self.step_start_time >= min_dwell:
                    self._complete_current_step(now)

            if is_in_current_area:
                if self.current_step_idx == 1:
                    req_count = current_step.get("required_count", 2)
                    self.status_msg = f"Đang lắp linh kiện: {self.hit_count}/{req_count}"
                else:
                    self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
                return self._get_status_result(active_zones, "processing")
            else:
                if self.current_step_idx == 1:
                    req_count = current_step.get("required_count", 2)
                    self.status_msg = f"Đang lắp linh kiện: {self.hit_count}/{req_count}"
                else:
                    self.status_msg = f"Đang chờ: {current_step['step_name']}"

            # Kiểm tra bỏ bước (Skip Step)
            if (now - self.last_completed_time > 1.2):
                if self.current_step_idx + 1 < len(self.sop_steps):
                    next_step = self.sop_steps[self.current_step_idx + 1]
                    next_zones = self._get_all_zones_for_step(next_step)
                    
                    if not (self.last_completed_zone in next_zones and (now - self.last_completed_time < 2.5)):
                        has_withdrawn = (now - self.last_completed_time > 1.2) or not (
                            self.last_completed_zone and any(self._is_in_zone(side, self.last_completed_zone) for side in ["left", "right"])
                        )
                        if has_withdrawn:
                            if self._check_step_logic(next_step, now, update_status=False, centroid_only=True):
                                self.skip_frames_counter += 1
                                base_tolerance = self.config.get("violation_tolerance", 8)
                                if self.skip_frames_counter >= base_tolerance:
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
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        self.hit_count = 0
        self.last_completed_zone = None
        self.last_completed_time = now if now else time.time()
        self.reset_dwell_start = 0.0
        self.s1_withdrawn = True
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        self.both_buttons_pressed = False
        self.log_debug("ENGINE RESET", self.product_id)

    def get_status(self) -> Dict[str, Any]:
        return self._get_status_result({"left": None, "right": None}, "idle")

    # --- Internal Helpers ---
    def _complete_current_step(self, now: float):
        step = self.sop_steps[self.current_step_idx]
        self.log_debug(f"STEP COMPLETED: {self.current_step_idx + 1}/{len(self.sop_steps)} - {step['step_name']}", self.product_id)
        self.last_completed_zone = step.get("required_zone")
        self.last_completed_time = now
        
        step_1_zones = self._get_all_zones_for_step(self.sop_steps[0])
        if self.last_completed_zone in step_1_zones:
            self.s1_withdrawn = False
            
        self.current_step_idx += 1
        self.step_start_time = now
        self.hit_count = 0
        self.last_trigger_states = {}
        self._stay_timer = {}
        self._zone_last_seen = {}
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
        self._hit_registered = {}
        self.both_buttons_pressed = False
        
        if self.current_step_idx >= len(self.sop_steps):
            self._completed_at = now
            if self.cycle_start_time > 0:
                self.last_cycle_duration = round(now - self.cycle_start_time, 1)
            logger.info(f"[{self.product_id}] SOP Cycle completed in {self.last_cycle_duration}s")

    def _get_status_result(self, active_zones: Dict, status: str, violation_type: str = None) -> Dict:
        step_list = [s["step_name"] for s in self.sop_steps]
        cur_step_name = self.sop_steps[self.current_step_idx]["step_name"] if self.current_step_idx < len(self.sop_steps) else "HOÀN THÀNH"
        
        detected_parts = []
        for side, zone in active_zones.items():
            if zone: detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        max_cycle = self.config.get("max_cycle_time_sec", 60.0)
        if self.waiting_for_start:
            cycle_time_left = max_cycle
        elif self.is_failed or self.current_step_idx >= len(self.sop_steps):
            cycle_time_left = 0.0
        else:
            cycle_time_left = max(0.0, max_cycle - (self.last_update_time - self.cycle_start_time))

        turntable_info = self.turntable_counter.get_status()

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
            "cycle_time_left": round(cycle_time_left, 1),
            "max_cycle_time": max_cycle,
            "total_products": turntable_info["total_products"],
            "turntable_state": turntable_info["turntable_state"],
            "is_turntable_moving": turntable_info["is_turntable_moving"],
            "cycle_rotations": turntable_info["cycle_rotations"]
        }

        # Nếu có sự kiện mâm xoay vừa đếm sản phẩm mới -> nhả ra cho processor xử lý
        prod_ev = self.turntable_counter.pop_pending_product_event()
        if prod_ev:
            res["new_product_event"] = prod_ev

        if self.is_failed:
            if violation_type: self.violation_type = violation_type
            if not self.violation_notified:
                self.violation_notified = True
                status = "violation"
            else:
                status = "failed_silent"
            
            msg = "VI PHẠM - QUAY LẠI BƯỚC 1"
            if self.violation_type == "timeout":
                msg = "VI PHẠM - QUÁ THỜI GIAN"
            elif self.violation_type == "skip_step":
                msg = "VI PHẠM - BỎ BƯỚC"
            elif self.violation_type == "hand_in_spinning_turntable":
                msg = "NGUY HIỂM: TAY TRONG KHUÔN KHI MÂM XOAY"
            
            res.update({
                "detected_label": msg,
                "sop_status": status,
                "violation_type": self.violation_type or "skip_step",
                "step_index": 0,
                "progress_percent": 0,
                "cycle_time_left": 0.0
            })
        return res

    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False) -> bool:
        """
        Chuẩn logic 3 bước kế thừa từ 639957_engine:
        - Bước 1 (zone_trigger): Tay chạm/ở trong mold >= min_dwell
        - Bước 2 (multi_trigger): Đếm số lượt lắp linh kiện vào mold (cả 2 tay hoặc từng tay)
        - Bước 3 (dual_task): 2 tay đồng thời bấm 2 nút button_left & button_right
        """
        logic = step.get("logic")
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            
            if target not in self._zone_triggered:
                self._zone_triggered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                if is_in:
                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                    if entry > 0.0 and (now - entry >= 0.2):
                        if update_status:
                            self._zone_triggered[target][side] = True
                            
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only)
                return any(self._is_in_zone(side, target, centroid_only=centroid_only) for side in ["left", "right"])
                
            if mode == "both":
                return self._zone_triggered[target]["left"] and self._zone_triggered[target]["right"]
            elif mode == "any":
                return self._zone_triggered[target]["left"] or self._zone_triggered[target]["right"]
            else:
                return self._zone_triggered[target].get(mode, False)

        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("required_count", 2)
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hit_registered:
                self._hit_registered[target] = {"left": False, "right": False}
                
            # Đếm số lượng tay cùng lúc vào khuôn để hỗ trợ lắp đồng thời 2 cái trong 1 nhịp
            hands_in_target = sum(1 for side in ["left", "right"] if self._is_in_zone(side, target, centroid_only=centroid_only))

            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
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
                        if entry > 0.0 and (now - entry >= 0.15):
                            if not self._hit_registered.get(target, {}).get(side, False):
                                # Nếu cả 2 tay cùng vào khuôn (mỗi tay cầm 1 cái), cộng đủ luôn
                                inc = 2 if hands_in_target >= 2 else 1
                                self.hit_count = min(count_needed, self.hit_count + inc)
                                self._hit_registered[target][side] = True
                                self.log_debug(f"Multi-trigger hit counted for {side} hand in {target}. Hit count: {self.hit_count}/{count_needed}", self.product_id)
                    else:
                        if target in self._hit_registered:
                            self._hit_registered[target][side] = False
                    self.last_trigger_states[side] = is_in_debounced
                    
            if not update_status:
                return any(self._is_in_zone(side, target, centroid_only=centroid_only) for side in ["left", "right"])
                
            return self.hit_count >= count_needed

        elif logic == "dual_task":
            # 2 tay đồng thời bấm 2 nút: button_left & button_right
            l_zone = step.get("left_zone", "button_left")
            r_zone = step.get("right_zone", "button_right")
            
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("right", r_zone, centroid_only=centroid_only)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("left", r_zone, centroid_only=centroid_only)
                return cond1 or cond2

            # Ghi nhận kích hoạt khi 2 tay vào 2 vùng nút
            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    is_in = self._is_in_zone(side, z, centroid_only=centroid_only)
                    if is_in:
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                        if entry > 0.0 and (now - entry >= 0.15):
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
            
            if normal_match or swapped_match:
                self.both_buttons_pressed = True
                self.turntable_counter.trigger_button_pressed(now)
                return True

            return False

        return False

    def _is_in_zone(self, side: str, zone_name: str, centroid_only: bool = False) -> bool:
        """Kiểm tra bàn tay (trái/phải) có nằm trong hoặc chạm vào vùng đa giác không."""
        zone_pts = self.zones.get(zone_name)
        if not zone_pts:
            return False
        
        w = self.config.get("w", 640)
        h = self.config.get("h", 480)
        for hand in (self.last_hands or []):
            if hand.get("label", "").lower() != side:
                continue
            if self._check_bbox_polygon_intersection(hand["bbox"], zone_pts, hand["centroid"], w, h, centroid_only):
                return True
        return False

    def _get_all_zones_for_step(self, step: Dict) -> List[str]:
        z = []
        if "required_zone" in step: z.append(step["required_zone"])
        if "source_zone" in step: z.append(step["source_zone"])
        if "left_zone" in step: z.append(step["left_zone"])
        if "right_zone" in step: z.append(step["right_zone"])
        return z

    def _get_hand_distance(self) -> float:
        if not self.last_hands or len(self.last_hands) < 2:
            return -1.0
        l_pos, r_pos = None, None
        for h in self.last_hands:
            if h.get("label") == "left": l_pos = h["centroid"]
            if h.get("label") == "right": r_pos = h["centroid"]
        if l_pos and r_pos:
            return float(np.sqrt((l_pos[0]-r_pos[0])**2 + (l_pos[1]-r_pos[1])**2))
        return -1.0
