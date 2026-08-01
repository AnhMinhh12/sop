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
    Engine logic cho mã sản phẩm laprap.
    Thực hiện logic không gian dựa trên vùng (Zone).
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        if not self.sop_steps:
            raise ValueError(f"ProductEngine [laprap]: Steps list is empty! Check if the SOP definition yaml file exists and is populated.")
        self.config = sop_config.get("config", {"w": 640, "h": 480})
        self.product_id = "laprap" # ID này được truyền từ loader
        
        # Trạng thái moteur logic
        self.current_step_idx = 0
        self.step_start_time = 0.0
        self.last_update_time = 0.0
        self._completed_at = 0.0
        self.last_hands = []
        self.last_products = []
        
        self.is_failed = False
        self.violation_notified = False
        self.failed_step_idx = -1
        self.violation_type = None
        self.status_msg = "Sẵn sàng"
        
        self.waiting_for_start = True
        self.cycle_count = 0
        self.s1_withdrawn = True
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        
        # Debouncing and dwell timers
        self._zone_dwell_start = {}
        self._must_exit_zone = None

        # Cycle prep state (hand goes to left zone, then product in center)
        self.hand_went_to_left = False
        self.left_zone_dwell_start = 0.0
        
        logger.info(f"ProductEngine [laprap]: Initialized for station {self.station_id}")

    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
               robot_data: List[Dict] = None) -> Dict[str, Any]:
        now = time.time()
        self.last_hands = hands_data
        self.last_products = products_data if products_data is not None else []
        self.last_update_time = now

        # Update active_zones for bimanual status
        active_zones = {"left": None, "right": None}
        for hand in hands_data:
            side = hand["label"].lower()
            if side not in ["left", "right"]: continue
            
            centroid = hand["centroid"]
            bbox = hand["bbox"]
            w, h = self.config.get("w", 640), self.config.get("h", 480)
            test_points = [centroid, [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], 
                           [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]]
            
            for z_name, z_pts in self.zones.items():
                poly = np.array(z_pts, np.float32)
                if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                    active_zones[side] = z_name
                    break

        # Check s1_withdrawn status: check if no hand is in step 1 zone
        step_1 = self.sop_steps[0]
        s1_zone = step_1.get("required_zone")
        is_currently_in_s1 = any(self._is_in_zone(side, s1_zone) for side in ["left", "right"])
        if not is_currently_in_s1:
            self.s1_withdrawn = True

        # Handle post-completion cooldown/reset delay
        if self._completed_at > 0:
            if now - self._completed_at < 1.5:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0.0
                self.reset(now=now)

        # Handle failed state and auto-reset when hand goes to thung_trai
        if self.is_failed:
            hand_in_left = any(self._is_in_zone(side, "thung_trai") for side in ["left", "right"])
            if hand_in_left:
                logger.info("Hand went to thung_trai after failure. Resetting to prep state.")
                self.reset(now=now)
                self.hand_went_to_left = True
            else:
                return self._get_status_result(active_zones, "violation", violation_type=self.violation_type)

        # FSM step processing
        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            target_zone = current_step.get("required_zone")
            min_dwell = current_step.get("min_dwell_sec", self.config.get("min_step_dwell_sec", 0.2))

            # Check if hand/product is in target zone
            require_prod = current_step.get("require_product", False)
            
            if current_step.get("step_order") == 4 or target_zone == "thung_phai":
                is_in_target = not self._is_product_in_zone("hop_giua")
            else:
                if require_prod:
                    is_in_target = any(self._is_in_zone(side, target_zone) for side in ["left", "right"]) and self._is_product_in_zone(target_zone)
                else:
                    is_in_target = any(self._is_in_zone(side, target_zone) for side in ["left", "right"])

            # 1. Waiting for cycle start
            if self.waiting_for_start:
                hand_in_left = any(self._is_in_zone(side, "thung_trai") for side in ["left", "right"])

                if not self.hand_went_to_left:
                    if hand_in_left:
                        if self.left_zone_dwell_start == 0.0:
                            self.left_zone_dwell_start = now
                        elif now - self.left_zone_dwell_start >= 0.2:
                            self.hand_went_to_left = True
                            logger.info("New cycle signal: Hand detected in thung_trai.")
                    else:
                        self.left_zone_dwell_start = 0.0
                    
                    self.status_msg = "Sẵn sàng (Chờ tay chạm vùng trái)"
                    return self._get_status_result(active_zones, "idle")

                else:
                    # Hand went to left. Now wait for product in hop_giua
                    prod_in_hop_giua = self._is_product_in_zone("hop_giua")
                    if prod_in_hop_giua:
                        if self.start_zone_entry_time == 0.0:
                            self.start_zone_entry_time = now
                        elif now - self.start_zone_entry_time >= 0.3:
                            self.waiting_for_start = False
                            self.cycle_start_time = now
                            self.cycle_count += 1
                            self.step_start_time = now
                            self.start_zone_entry_time = 0.0
                            self.hand_went_to_left = False
                            self.left_zone_dwell_start = 0.0
                            self._complete_step(now)
                            logger.info(f"Cycle {self.cycle_count} started and Step 1 completed.")
                            return self._get_status_result(active_zones, "processing")
                    else:
                        self.start_zone_entry_time = 0.0

                    self.status_msg = "Sẵn sàng (Chờ sản phẩm vào hộp giữa)"
                    return self._get_status_result(active_zones, "idle")

            # 2. Check early cycle restart if hand returns to Step 1
            if self.current_step_idx > 0 and self.current_step_idx <= self.config.get("restart_allowed_until_step", 1) and self.s1_withdrawn:
                if any(self._is_in_zone(side, s1_zone) for side in ["left", "right"]):
                    if self.start_zone_entry_time == 0.0:
                        self.start_zone_entry_time = now
                    elif now - self.start_zone_entry_time >= 0.2:
                        logger.info(f"Hand returned to Step 1 at step {self.current_step_idx + 1}. Auto-restarting cycle.")
                        self.reset(now=now)
                        self.cycle_count += 1
                        self.waiting_for_start = False
                        self.cycle_start_time = now
                        self.step_start_time = now
                        self.start_zone_entry_time = 0.0
                        self._complete_step(now)
                        return self._get_status_result(active_zones, "processing")
                else:
                    self.start_zone_entry_time = 0.0

            # 3. Check current step progress/completion
            # --- Inter-step Withdrawal Guard ---
            if self._must_exit_zone is not None:
                still_in_exit_zone = any(self._is_in_zone(side, self._must_exit_zone) for side in ["left", "right"])
                if still_in_exit_zone:
                    self.status_msg = f"⏳ Rời tay khỏi vùng cũ trước khi thực hiện: {current_step['step_name']}"
                    self._zone_dwell_start = {}
                    return self._get_status_result(active_zones, "processing")
                else:
                    self._must_exit_zone = None

            if is_in_target:
                if target_zone not in self._zone_dwell_start or self._zone_dwell_start[target_zone] == 0.0:
                    self._zone_dwell_start[target_zone] = now
                elif now - self._zone_dwell_start[target_zone] >= min_dwell:
                    self._complete_step(now)
                    if self._completed_at > 0:
                        return self._get_status_result(active_zones, "completed")
                self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
            else:
                self._zone_dwell_start[target_zone] = 0.0
                self.status_msg = f"Đang chờ: {current_step['step_name']}"

        return self._get_status_result(active_zones, "processing")

    def _complete_step(self, now: float):
        step = self.sop_steps[self.current_step_idx]
        completed_zone = step.get("required_zone")
        logger.info(f"Completed step {self.current_step_idx + 1}: {step['step_name']}")
        
        if self.current_step_idx == 0:
            self.s1_withdrawn = False

        self.current_step_idx += 1
        self.step_start_time = now
        self._zone_dwell_start = {}

        if self.current_step_idx < len(self.sop_steps):
            self._must_exit_zone = completed_zone

        if self.current_step_idx >= len(self.sop_steps):
            self._completed_at = now
            logger.info("Cycle completed successfully!")

    def reset(self, now: float = None) -> None:
        self.current_step_idx = 0
        self.is_failed = False
        self.violation_notified = False
        self.violation_type = None
        self.failed_step_idx = -1
        self.step_start_time = now if now else time.time()
        self.waiting_for_start = True
        self.start_zone_entry_time = 0.0
        self.cycle_start_time = 0.0
        self._zone_dwell_start = {}
        self.s1_withdrawn = True
        self.status_msg = "Sẵn sàng"
        self._must_exit_zone = None
        self.hand_went_to_left = False
        self.left_zone_dwell_start = 0.0
        self.log_debug("ENGINE RESET", self.product_id)

    def get_status(self) -> Dict[str, Any]:
        return self._get_status_result({"left": None, "right": None}, "idle")

    # --- Internal Helpers ---
    def _complete_current_step(self, now: float):
        step = self.sop_steps[self.current_step_idx]
        self.log_debug(f"STEP COMPLETED: {self.current_step_idx + 1}/{len(self.sop_steps)} - {step['step_name']}", self.product_id)
        self.last_completed_zone = step.get("required_zone")
        self.last_completed_time = now
        
        # Nếu bước vừa hoàn thành là bước vô hạn thời gian (timeout_sec == -1), ta bù lại thời gian đã tiêu tốn cho chu kỳ
        if step.get("timeout_sec") == -1:
            time_spent = now - self.step_start_time
            self.cycle_start_time += time_spent
            self.log_debug(f"Infinite step completed. Adjusting cycle_start_time by +{time_spent:.2f}s", self.product_id)
            
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
        self._zone_entry_time = {}
        self._zone_triggered = {}
        self._hand_entry_time = {}
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
            cycle_time_left = 38.0
        elif self.is_failed:
            cycle_time_left = 0.0
        elif self.current_step_idx >= len(self.sop_steps):
            cycle_time_left = 0.0
        else:
            cycle_time_left = max(0.0, 38.0 - (self.last_update_time - self.cycle_start_time))

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
            "cycle_time_left": cycle_time_left
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
        return res

    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False) -> bool:
        logic = step.get("logic")
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            
            if target not in self._zone_triggered:
                self._zone_triggered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                if is_in and step.get("require_product", False):
                    if not self._is_product_in_zone(target):
                        is_in = False
                if is_in:
                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                    if entry > 0.0 and (now - entry >= 0.2):
                        if update_status:
                            self._zone_triggered[target][side] = True
                            
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and                            self._is_in_zone("right", target, centroid_only=centroid_only)
                return any(self._is_in_zone(side, target, centroid_only=centroid_only) for side in ["left", "right"])
                
            if mode == "both":
                return self._zone_triggered[target]["left"] and self._zone_triggered[target]["right"]
            elif mode == "any":
                return self._zone_triggered[target]["left"] or self._zone_triggered[target]["right"]
            else:
                return self._zone_triggered[target].get(mode, False)
                
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            if target not in self._stay_timer: self._stay_timer[target] = {"left": 0, "right": 0}
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
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
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hit_registered:
                self._hit_registered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
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
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and                            self._is_in_zone("right", target, centroid_only=centroid_only)
                return any_in
                
            return self.hit_count >= count_needed
            
        elif logic == "dual_task":
            l_zone, r_zone = step.get("left_zone"), step.get("right_zone")
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only) and                         self._is_in_zone("right", r_zone, centroid_only=centroid_only)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only) and                         self._is_in_zone("left", r_zone, centroid_only=centroid_only)
                return cond1 or cond2

            # Chỉ ghi nhận kích hoạt khi tay giữ trong vùng ít nhất 0.2s
            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    is_in = self._is_in_zone(side, z, centroid_only=centroid_only)
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
