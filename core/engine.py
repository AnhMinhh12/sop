import time
import logging
import cv2
import numpy as np
from typing import Dict, List, Any, Optional
from shared.utils import is_point_in_zone

logger = logging.getLogger(__name__)

class LaprapEngine:
    """
    FSM Engine for laprap assembly process.
    Tracks step progression based on precise fingertip coordinates and zone polygons.
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id", "08")
        self.station_name = sop_config.get("station_name", "Máy 8 - Lắp ráp linh kiện")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {})

        # FSM state variables
        self.current_step_idx = 0
        self.step_start_time = 0.0
        self.cycle_start_time = 0.0
        self.last_update_time = 0.0
        self._completed_at = 0.0
        
        self.is_failed = False
        self.violation_type = None
        self.violation_notified = False
        self.failed_step_idx = -1
        
        self.waiting_for_start = True
        self.cycle_count = 0
        self.start_zone_entry_time = 0.0
        self.status_msg = "Sẵn sàng"
        
        # Debouncing and dwell timers
        self._zone_dwell_start = {}
        self.s1_withdrawn = True
        self.last_hands = []
        # Inter-step withdrawal: tên zone bước hiện tại mà tay phải rời trước khi bắt đầu bước tiếp theo
        self._must_exit_zone = None

        # Cycle prep state (hand goes to left zone, then product in center)
        self.hand_went_to_left = False
        self.left_zone_dwell_start = 0.0

        logger.info(f"Laprap FSM Engine Initialized for Station {self.station_id}")

    def update(self, hands_data: List[Dict]) -> Dict[str, Any]:
        """
        Updates the state machine with the latest hand detections.
        """
        now = time.time()
        self.last_hands = hands_data
        self.last_update_time = now

        # Update s1_withdrawn status: check if no hand is in step 1 zone
        step_1 = self.sop_steps[0]
        s1_zone = step_1.get("required_zone")
        is_currently_in_s1 = any(h.get("class") == "hand" and is_point_in_zone(h["fingertip"], self.zones.get(s1_zone, [])) for h in hands_data)
        if not is_currently_in_s1:
            self.s1_withdrawn = True

        # Handle post-completion cooldown/reset delay
        if self._completed_at > 0:
            if now - self._completed_at < 1.5:
                return self._get_status_result("completed")
            else:
                self._completed_at = 0.0
                self.reset(now=now)

        # Handle failed state and auto-reset when hand goes to thung_trai
        if self.is_failed:
            thung_trai_zone = self.zones.get("thung_trai", [])
            hand_in_left = any(
                h.get("class") == "hand" and (
                    is_point_in_zone(h["fingertip"], thung_trai_zone) or
                    is_point_in_zone(h["centroid"], thung_trai_zone)
                )
                for h in hands_data
            )
            if hand_in_left:
                logger.info("Hand went to thung_trai after failure. Resetting to prep state.")
                self.reset(now=now)
                self.hand_went_to_left = True
            else:
                return self._get_status_result("violation")

        # FSM step processing
        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            target_zone = current_step.get("required_zone")
            min_dwell = current_step.get("min_dwell_sec", self.config.get("min_step_dwell_sec", 0.2))

            # Check if hand/product is in the target zone (considering require_product constraint)
            require_prod = current_step.get("require_product", False)
            hands_in_zone = [
                h for h in hands_data 
                if h.get("class") == "hand" and (
                    is_point_in_zone(h["fingertip"], self.zones.get(target_zone, [])) or
                    is_point_in_zone(h["centroid"], self.zones.get(target_zone, []))
                )
            ]
            prods_in_zone = [p for p in hands_data if p.get("class") == "product" and is_point_in_zone(p["centroid"], self.zones.get(target_zone, []))]

            if current_step.get("step_order") == 4 or target_zone == "thung_phai":
                # Step 4 is completed when there is no longer a product in hop_giua
                hop_giua_zone = self.zones.get("hop_giua", [])
                prods_in_hop_giua = [p for p in hands_data if p.get("class") == "product" and is_point_in_zone(p["centroid"], hop_giua_zone)]
                is_in_target = (len(prods_in_hop_giua) == 0)
            else:
                if require_prod:
                    is_in_target = len(hands_in_zone) > 0 and len(prods_in_zone) > 0
                else:
                    is_in_target = len(hands_in_zone) > 0

            # 1. Waiting for cycle start (Step 1 trigger)
            if self.waiting_for_start:
                thung_trai_zone = self.zones.get("thung_trai", [])
                hand_in_left = any(
                    h.get("class") == "hand" and (
                        is_point_in_zone(h["fingertip"], thung_trai_zone) or
                        is_point_in_zone(h["centroid"], thung_trai_zone)
                    )
                    for h in hands_data
                )

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
                    return self._get_status_result("idle")

                else:
                    # Hand has already gone to left. Now wait for product to reappear in hop_giua
                    hop_giua_zone = self.zones.get("hop_giua", [])
                    prod_in_hop_giua = any(
                        p.get("class") == "product" and is_point_in_zone(p["centroid"], hop_giua_zone)
                        for p in hands_data
                    )

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
                            logger.info(f"Cycle {self.cycle_count} started and Step 1 completed (Product returned to hop_giua).")
                            return self._get_status_result("processing")
                    else:
                        self.start_zone_entry_time = 0.0

                    self.status_msg = "Sẵn sàng (Chờ sản phẩm vào hộp giữa)"
                    return self._get_status_result("idle")

            # 2. No overall cycle timeout limit (removed 38s limit)
            pass

            # 3. Check early cycle restart if hand returns to Step 1 (only before step restart limit)
            if self.current_step_idx > 0 and self.current_step_idx <= self.config.get("restart_allowed_until_step", 1) and self.s1_withdrawn:
                # If hand is in step 1 zone and stays for >= 0.2s, restart cycle
                hands_list = [h for h in hands_data if h.get("class") == "hand"]
                if hands_list and is_point_in_zone(hands_list[0]["fingertip"], self.zones.get(s1_zone, [])):
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
                        # Auto-complete Step 1 of the new cycle
                        self._complete_step(now)
                        return self._get_status_result("processing")
                else:
                    self.start_zone_entry_time = 0.0

            # 4. Check current step progress/completion
            # --- Inter-step Withdrawal Guard ---
            # Nếu vừa hoàn thành bước trước, phải đợi tay rời khỏi zone mục tiêu trước đã
            if self._must_exit_zone is not None:
                exit_pts = self.zones.get(self._must_exit_zone, [])
                still_in_exit_zone = (
                    exit_pts and
                    any(h.get("class") == "hand" and is_point_in_zone(h["fingertip"], exit_pts) for h in hands_data)
                )
                if still_in_exit_zone:
                    # Tay chưa rời — block dwell, hiển cảnh báo
                    self.status_msg = f"⏳ Rời tay khỏi vùng cũ trước khi thực hiện: {current_step['step_name']}"
                    self._zone_dwell_start = {}
                    return self._get_status_result("processing")
                else:
                    # Tay đã rời — xóa cờ
                    logger.debug(f"Inter-step withdrawal cleared for zone '{self._must_exit_zone}'")
                    self._must_exit_zone = None

            if is_in_target:
                if target_zone not in self._zone_dwell_start or self._zone_dwell_start[target_zone] == 0.0:
                    self._zone_dwell_start[target_zone] = now
                elif now - self._zone_dwell_start[target_zone] >= min_dwell:
                    self._complete_step(now)
                    # Kiểm tra ngay nếu vừa hoàn thành bước cuối
                    if self._completed_at > 0:
                        return self._get_status_result("completed")
                self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
            else:
                self._zone_dwell_start[target_zone] = 0.0
                self.status_msg = f"Đang chờ: {current_step['step_name']}"

        return self._get_status_result("processing")

    def _complete_step(self, now: float):
        step = self.sop_steps[self.current_step_idx]
        completed_zone = step.get("required_zone")
        logger.info(f"Completed step {self.current_step_idx + 1}: {step['step_name']}")
        
        # If completing Step 1, mark s1_withdrawn = False until hand leaves
        if self.current_step_idx == 0:
            self.s1_withdrawn = False

        self.current_step_idx += 1
        self.step_start_time = now
        self._zone_dwell_start = {}

        # --- Inter-step Withdrawal Guard ---
        # Bắt buộc tay phải rời khỏi vùng (zone) vừa hoàn thành trước khi bắt đầu đếm dwell của bước tiếp theo
        if self.current_step_idx < len(self.sop_steps):
            self._must_exit_zone = completed_zone
            logger.debug(f"Inter-step withdrawal required: must leave completed zone '{completed_zone}' before step {self.current_step_idx + 1}")

        if self.current_step_idx >= len(self.sop_steps):
            self._completed_at = now
            logger.info("Cycle completed successfully!")

    def reset(self, now: float = None) -> None:
        self.current_step_idx = 0
        self.is_failed = False
        self.violation_type = None
        self.violation_notified = False
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

    def _get_status_result(self, status: str) -> Dict[str, Any]:
        cur_step_name = (
            self.sop_steps[self.current_step_idx]["step_name"]
            if self.current_step_idx < len(self.sop_steps)
            else "HOÀN THÀNH"
        )
        
        if self.waiting_for_start or self.cycle_start_time == 0.0:
            cycle_elapsed = 0.0
            time_left = 999.0
        elif self.is_failed:
            cycle_elapsed = self.last_update_time - self.cycle_start_time
            time_left = 0.0
        elif self.current_step_idx >= len(self.sop_steps):
            cycle_elapsed = self.last_update_time - self.cycle_start_time
            time_left = 0.0
        else:
            cycle_elapsed = self.last_update_time - self.cycle_start_time
            time_left = 999.0

        step_list = [s["step_name"] for s in self.sop_steps]
        
        return {
            "sop_status": status,
            "status_msg": self.status_msg,
            "expected_step": cur_step_name,
            "step_index": self.current_step_idx,
            "progress_percent": (self.current_step_idx / len(self.sop_steps)) * 100 if self.current_step_idx < len(self.sop_steps) else 100.0,
            "is_failed": self.is_failed,
            "failed_step_idx": self.failed_step_idx,
            "cycle_count": self.cycle_count,
            "cycle_time_left": time_left,
            "cycle_elapsed": cycle_elapsed,
            "step_list": step_list,
            "violation_type": self.violation_type
        }
