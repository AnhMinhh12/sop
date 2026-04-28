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
        self.step_start_time = 0.0  # Sẽ được set khi nhận frame đầu tiên
        self.active_step_time = 0.0
        self.last_update_time = 0.0
        self._completed_at = 0
        self.last_hands = []
        self.hand_dist = -1.0
        
        # New: Quản lý lỗi và Reset
        self.is_failed = False
        self.failed_step_idx = -1
        self.last_completed_zone = None
        self.last_completed_time = 0.0
        self.status_msg = "Sẵn sàng"
        
        # Trạng thái chi tiết từng tay (dùng cho display)
        self.hand_states = {
            "left": {"zone": None, "entry_time": 0},
            "right": {"zone": None, "entry_time": 0}
        }
        
        # Timer cho zone_trigger: LƯU TRỮ THEO TỪNG VÙNG: {zone_name: {left: ts, right: ts}}
        self._zone_last_seen = {}
        # Timer cho stay_in_zone: LƯU TRỮ THEO TỪNG VÙNG
        self._stay_timer = {}
        
        # Lịch sử di chuyển (dùng cho interaction logic)
        self.hand_history = {"left": [], "right": []}
        
        # Bộ đếm cho logic multi_trigger
        self.hit_count = 0
        self.last_trigger_states = {"left": False, "right": False} # Track per-hand for multi_trigger
        
        # New: Stability Counters
        self.skip_frames_counter = 0
        self.reset_dwell_start = 0.0
        
        logger.info(f"SpatialEngine: Initialized with {len(self.sorted_zones)} prioritized zones. Mode: STRICT_ENFORCEMENT")

    def update(self, hands_data: List[Dict]) -> Dict[str, Any] | None:
        now = time.time()
        self.last_hands = hands_data  # Cập nhật ngay để các hàm logic dùng đúng frame hiện tại
        
        # 1. Cập nhật vị trí và lịch sử (Cần làm sớm để dùng cho cả error_mode và logic chính)
        active_zones = {"left": None, "right": None}
        for hand in hands_data:
            side = hand["label"].lower()
            if side not in ["left", "right"]: continue
            
            centroid = hand["centroid"]
            bbox = hand["bbox"]
            w, h = self.config.get("w", 1280), self.config.get("h", 720)
            
            test_points = [centroid, [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], 
                           [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]]
            
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
                    if len(self.hand_history[side]) > 50: self.hand_history[side].pop(0)

        # 2. FIX: Tránh tính thời gian chờ load model
        if self.last_update_time == 0:
            self.last_update_time = now
            self.step_start_time = now
            return {"sop_status": "idle", "expected_step": "Initializing", "step_index": 0, "hands_info": active_zones}
            
        dt = now - self.last_update_time
        self.last_update_time = now
        
        self.hand_dist = self._get_hand_distance()

        # 2. Check cooldown sau khi hoàn thành chu kỳ (giữ trạng thái "completed" 1 giây)
        if self._completed_at > 0:
            if now - self._completed_at < 1.0:
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

        # 2. XỬ LÝ TRẠNG THÁI LỖI (WAIT FOR RESET)
        if self.is_failed:
            # Ở trạng thái lỗi, CHỈ chờ Bước 1 để làm lại từ đầu
            step_1 = self.sop_steps[0]
            if self._check_step_logic(step_1, now):
                # Dwell time 1.0s để tránh vung tay qua là reset ngay
                if self.reset_dwell_start == 0:
                    self.reset_dwell_start = now
                elif now - self.reset_dwell_start >= 1.0:
                    logger.info("SpatialEngine: Hand detected at Step 1 (Stable). Resetting Cycle...")
                    self.reset()
                    # Sau khi reset, hoàn thành luôn Bước 1 cho chu kỳ mới
                    self._complete_current_step(now)
            else:
                self.reset_dwell_start = 0.0
            
            return self._get_status_result(active_zones, "violation")

        # 3. KIỂM TRA LOGIC SOP CHÍNH
        if self.current_step_idx < len(self.sop_steps):
            current_step = self.sop_steps[self.current_step_idx]
            elapsed = now - self.step_start_time
            
            # --- TÍNH NĂNG MỚI: Kiểm tra quá thời gian chờ (Transition Timeout) ---
            # Ưu tiên cấu hình trong YAML nhưng không thấp hơn 10.0s (theo yêu cầu mới)
            timeout_limit = max(10.0, self.config.get("transition_timeout_sec", 10.0))
            if elapsed > timeout_limit:
                logger.warning(f"!!! [TIMEOUT] Step {self.current_step_idx+1} timed out after {elapsed:.1f}s")
                self.is_failed = True
                self.violation_type = "timeout"
                self.failed_step_idx = self.current_step_idx
                return self._get_status_result(active_zones, "violation", violation_type="timeout")
            
            # --- ƯU TIÊN 1: Kiểm tra bước hiện tại ---
            # Lấy tất cả vùng liên quan đến bước hiện tại
            current_zones = self._get_all_zones_for_step(current_step)
            # Kiểm tra xem có bàn tay nào đang ở trong vùng của bước hiện tại không
            is_in_current_area = any(self._is_in_zone("left", z) or self._is_in_zone("right", z) for z in current_zones)

            if is_in_current_area:
                self.status_msg = f"Đang thực hiện: {current_step['step_name']}"
                # Nếu đang ở đúng vùng, kiểm tra xem đã thỏa mãn logic chốt bước chưa
                if elapsed >= 0.8 and self._check_step_logic(current_step, now):
                    self._complete_current_step(now)
                # QUAN TRỌNG: Nếu tay còn ở vùng đúng, TUYỆT ĐỐI không check Skip bước tương lai
                return self._get_status_result(active_zones, "processing")
            else:
                self.status_msg = f"Đang chờ: {current_step['step_name']}"
                
                # --- PHÁT HIỆN RESTART CHU KỲ SỚM (Khi đang không ở vùng đúng và đã qua nửa SOP) ---
                if self.current_step_idx > (len(self.sop_steps) // 2):
                    step_1 = self.sop_steps[0]
                    # Chỉ check nếu vùng Step 1 khác vùng hiện tại (hoặc nếu tay thực sự ở vùng Step 1 mà không phải vùng hiện tại)
                    if step_1.get("required_zone") not in current_zones:
                        # CHẶN LỖI OAN: Không báo restart nếu đây là vùng vừa làm xong (đang rút tay ra)
                        if step_1.get("required_zone") == self.last_completed_zone and (now - self.last_completed_time < 2.5):
                             pass
                        elif self._check_step_logic(step_1, now, update_status=False, centroid_only=True):
                            logger.warning(f"!!! [PREMATURE RESTART] Cycle restarted at Step 1 while current at Step {self.current_step_idx+1}")
                            self.is_failed = True
                            self.failed_step_idx = self.current_step_idx
                            return self._get_status_result(active_zones, "violation", violation_type="premature_restart")

            # --- ƯU TIÊN 2: Chỉ khi THỰC SỰ KHÔNG ở vùng đúng, mới check xem có Skip không ---
            
            # --- GLOBAL SKIP LOCKOUT ---
            # Sau khi vừa xong 1 bước, khóa bắt lỗi Skip toàn bộ hệ thống trong 1.5s để công nhân di chuyển tay
            if (now - self.last_completed_time < 1.5):
                return self._get_status_result(active_zones, "processing")
            
            future_step_detected = False
            for i in range(self.current_step_idx + 1, len(self.sop_steps)):
                future_step = self.sop_steps[i]
                
                # FIX LỖI NHẬN NHẦM (STICKY ZONES)
                future_zones = self._get_all_zones_for_step(future_step)
                if self.last_completed_zone in future_zones and (now - self.last_completed_time < 3.0):
                    continue 
                
                # KHÔNG check skip nếu tay vẫn còn ở vùng vừa làm xong (đang thu tay về)
                if self.last_completed_zone and (self._is_in_zone("left", self.last_completed_zone) or self._is_in_zone("right", self.last_completed_zone)):
                    continue
                
                # Logic bổ sung: Check skip dùng CENTROID ONLY để tránh chạm nhẹ góc BBox
                if self._check_step_logic(future_step, now, update_status=False, centroid_only=True):
                    future_step_detected = True
                    self.skip_frames_counter += 1
                    
                    # Tăng độ trễ cho bắt lỗi Skip (gấp đôi tolerance thông thường)
                    tolerance = self.config.get("violation_tolerance", 3) * 2
                    if self.skip_frames_counter >= tolerance:
                        logger.warning(f"!!! [SKIP DETECTED] Step {self.current_step_idx+1} skipped. Direct to Step {i+1}")
                        self.is_failed = True
                        self.failed_step_idx = self.current_step_idx
                        return self._get_status_result(active_zones, "violation", violation_type="skip_step")
                    break 
            
            if not future_step_detected:
                self.skip_frames_counter = 0

        # LOGGING CHI TIẾT (Mỗi 15 frames để theo dõi trên console)
        if not hasattr(self, '_loop_count'): self._loop_count = 0
        self._loop_count += 1
        if self._loop_count % 15 == 0:
            # Dịch phỏng sang tiếng Anh cho console để tránh lỗi Unicode Windows
            console_msg = self.status_msg
            if "Đang thực hiện" in console_msg: console_msg = console_msg.replace("Đang thực hiện", "Doing")
            if "Đang chờ" in console_msg: console_msg = console_msg.replace("Đang chờ", "Waiting")
            if "Đợi tay TRÁI" in console_msg: console_msg = console_msg.replace("Đợi tay TRÁI vào", "Wait LH in")
            if "Đợi tay PHẢI" in console_msg: console_msg = console_msg.replace("Đợi tay PHẢI vào", "Wait RH in")
            if "Đợi cả 2 tay" in console_msg: console_msg = console_msg.replace("Đợi cả 2 tay vào", "Wait both hands in")
            if "Đã nhận" in console_msg: console_msg = console_msg.replace("Đã nhận", "Received").replace("lần dập", "hits")
            if "Mời dập tiếp" in console_msg: console_msg = "Next hit needed"
            if "Đã xong bước" in console_msg: console_msg = console_msg.replace("Đã xong bước", "Completed step")
            if "Đưa 2 Slider vào khuôn" in console_msg: console_msg = console_msg.replace("Đưa 2 Slider vào khuôn", "Put 2 Sliders in mold")
            
            logger.info(f"SOP: Step {self.current_step_idx+1} | {console_msg} | L:{active_zones['left']} R:{active_zones['right']}")

        return self._get_status_result(active_zones, "processing")

    def _complete_current_step(self, now: float):
        """Hỗ trợ chốt bước và chuyển trạng thái"""
        step = self.sop_steps[self.current_step_idx]
        step_num = step.get("step_order", self.current_step_idx + 1)
        logger.info(f"SpatialEngine: Step {step_num} COMPLETED.")
        
        self.last_completed_zone = step.get("required_zone")
        self.last_completed_time = now
        
        self.current_step_idx += 1
        self.step_start_time = now
        self.active_step_time = 0.0
        self.hit_count = 0  # Reset cho bước mới
        self.last_trigger_states = {"left": False, "right": False}
        self.status_msg = f"Đã xong bước {step_num}"
        
        # New: Reset các bộ đếm thời gian để bước tiếp theo không bị "kế thừa" thời gian từ bước cũ
        self._stay_timer = {}
        self._zone_last_seen = {}
        
        if self.current_step_idx >= len(self.sop_steps):
            logger.info("SpatialEngine: COMPLETE SOP CYCLE!")
            self._completed_at = now

    def _get_all_zones_for_step(self, step: Dict) -> List[str]:
        """Lấy tất cả các vùng liên quan đến một bước (xử lý cả dual_task)"""
        zones = []
        if "required_zone" in step:
            zones.append(step["required_zone"])
        if "left_zone" in step:
            zones.append(step["left_zone"])
        if "right_zone" in step:
            zones.append(step["right_zone"])
        return zones

    def _get_status_result(self, active_zones: Dict, status: str, violation_type: str = None) -> Dict:
        """Helper để đóng gói kết quả UI kèm logic X-mark và Blank"""
        step_list = [s["step_name"] for s in self.sop_steps]
        
        cur_step_name = self.sop_steps[self.current_step_idx]["step_name"] if self.current_step_idx < len(self.sop_steps) else "DONE"
        
        detected_parts = []
        for side, zone in active_zones.items():
            if zone: detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        base_res = {
            "sop_status": status,
            "status_msg": self.status_msg,
            "expected_step": cur_step_name,
            "detected_label": detected_label,
            "step_index": self.current_step_idx,
            "progress_percent": (self.current_step_idx / len(self.sop_steps)) * 100 if self.current_step_idx < len(self.sop_steps) else 100,
            "is_failed": self.is_failed,
            "failed_step_idx": self.failed_step_idx,
            "hit_count": self.hit_count,
            "hands_info": active_zones,
            "step_list": step_list
        }

        # Nếu đang ở trạng thái lỗi
        if self.is_failed:
            # Ghi lại loại lỗi nếu mới được truyền vào
            if violation_type: self.violation_type = violation_type
            base_res.update({
                "detected_label": "VIOLATION - RESTART AT STEP 1",
                "sop_status": "violation",
                "violation_type": self.violation_type or "skip_step"
            })
            return base_res

        # Nếu đã hoàn thành toàn bộ chu kỳ
        if self.current_step_idx >= len(self.sop_steps):
            base_res.update({"sop_status": "completed", "detected_label": "Finished"})
            return base_res

        return base_res

    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False) -> bool:
        logic = step.get("logic")
        
        # === ZONE TRIGGER: Tay chạm vùng mục tiêu (grace 0.5s) ===
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            grace = 1.5
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0, "right": 0}
            
            # Cập nhật timestamp lần cuối mỗi tay chạm vùng mục tiêu
            for side in ["left", "right"]:
                if self._is_in_zone(side, target, centroid_only=centroid_only):
                    self._zone_last_seen[target][side] = now
            
            if mode == "both":
                is_left_in = now - self._zone_last_seen[target]["left"] < grace
                is_right_in = now - self._zone_last_seen[target]["right"] < grace
                if update_status:
                    if not is_left_in and not is_right_in: self.status_msg = f"Đợi cả 2 tay vào {target}"
                    elif not is_left_in: self.status_msg = f"Đợi tay TRÁI vào {target}"
                    elif not is_right_in: self.status_msg = f"Đợi tay PHẢI vào {target}"
                return is_left_in and is_right_in
            
            if mode == "any":
                return any(now - self._zone_last_seen[target][s] < grace for s in ["left", "right"])
            else:
                return now - self._zone_last_seen[target][mode] < grace

        # === STAY IN ZONE: Giữ tay trong vùng liên tục N giây ===
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            
            if target not in self._stay_timer:
                self._stay_timer[target] = {"left": 0, "right": 0}
            
            for side in ["left", "right"]:
                if self._is_in_zone(side, target, centroid_only=centroid_only):
                    # CHỈ cập nhật timer nếu là bước hiện tại (tránh "đếm lén" khi check skip)
                    if self._stay_timer[target][side] == 0 and update_status:
                        self._stay_timer[target][side] = now  
                else:
                    if update_status: # Chỉ reset nếu là bước hiện tại
                        self._stay_timer[target][side] = 0 
            
            if mode == "any":
                return any(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            elif mode == "both":
                return all(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            else:
                return self._stay_timer[target][mode] > 0 and (now - self._stay_timer[target][mode]) >= min_dur

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
            grace = 1.5
            for side, zone in [("left", l_zone), ("right", r_zone)]:
                if zone not in self._zone_last_seen:
                    self._zone_last_seen[zone] = {"left": 0, "right": 0}
                if self._is_in_zone(side, zone):
                    self._zone_last_seen[zone][side] = now
            
            l_met = now - self._zone_last_seen.get(l_zone, {}).get("left", 0) < grace
            r_met = now - self._zone_last_seen.get(r_zone, {}).get("right", 0) < grace
            
            if update_status:
                if not l_met and not r_met: self.status_msg = f"Đợi cả 2 tay vào vùng"
                elif not l_met: self.status_msg = f"Đợi tay TRÁI vào {l_zone}"
                elif not r_met: self.status_msg = f"Đợi tay PHẢI vào {r_zone}"
            
            return l_met and r_met

        # === MULTI TRIGGER: Phải chạm vùng N lần (Entry events) ===
        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("count") or step.get("required_count", 1)
            mode = step.get("active_hand", "any") # 'left', 'right', 'any', or 'both'
            
            # Tính toán trạng thái "đang đạt yêu cầu" hiện tại
            current_state = False
            if mode == "any":
                # 'any' đếm độc lập từng tay (dùng cho các bước dập nhanh từng tay)
                for side in ["left", "right"]:
                    is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                    if is_in and not self.last_trigger_states.get(side, False):
                        self.hit_count += 1
                        logger.info(f"SpatialEngine: Step {self.current_step_idx+1} hit {self.hit_count}/{count_needed} (Hand: {side})")
                    self.last_trigger_states[side] = is_in
                current_state = self.hit_count >= count_needed
            
            elif mode == "both":
                # 'both' yêu cầu cả 2 tay cùng đồng thời mới tính là 1 lần dập
                is_left = self._is_in_zone("left", target, centroid_only=centroid_only)
                is_right = self._is_in_zone("right", target, centroid_only=centroid_only)
                combined_in = is_left and is_right
                
                # Chỉ đếm khi trạng thái chuyển từ (không đủ 2 tay) sang (đủ 2 tay)
                # Dùng key 'both' giả lập trong last_trigger_states
                if combined_in and not self.last_trigger_states.get("both", False):
                    self.hit_count += 1
                    logger.info(f"SpatialEngine: Step {self.current_step_idx+1} hit {self.hit_count}/{count_needed} (Both hands)")
                
                self.last_trigger_states["both"] = combined_in
                current_state = self.hit_count >= count_needed
            
            else:
                # Chế độ 1 tay duy nhất (left hoặc right)
                is_in = self._is_in_zone(mode, target, centroid_only=centroid_only)
                if is_in and not self.last_trigger_states.get(mode, False):
                    self.hit_count += 1
                    logger.info(f"SpatialEngine: Step {self.current_step_idx+1} hit {self.hit_count}/{count_needed} (Hand: {mode})")
                self.last_trigger_states[mode] = is_in
                current_state = self.hit_count >= count_needed

            if update_status:
                if self.hit_count < count_needed:
                    if self.hit_count == 0:
                        self.status_msg = f"Đang chờ: {step['step_name']}"
                    else:
                        self.status_msg = f"Đã nhận {self.hit_count}/{count_needed} lần dập"
                else:
                    self.status_msg = f"Đã xong {count_needed}/{count_needed} lần"

            return current_state

    def _is_in_zone(self, side: str, zone_name: str, centroid_only: bool = False) -> bool:
        """Check if hand overlaps with zone. centroid_only=True used for stability."""
        zone_pts = self.zones.get(zone_name)
        if not zone_pts:
            return False
        poly = np.array(zone_pts, np.float32)
        w, h = self.config.get("w", 1280), self.config.get("h", 720)
        
        for hand in self.last_hands:
            if hand["label"].lower() != side:
                continue
            
            centroid = hand["centroid"]
            
            if centroid_only:
                test_points = [centroid]
            else:
                bbox = hand["bbox"]  # [x1, y1, x2, y2]
                # Kiểm tra 5 điểm (Tâm + 4 góc) để tăng độ nhạy tối đa
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
        self.active_step_time = 0.0
        self.last_update_time = time.time()
        self._zone_last_seen = {}
        self._stay_timer = {}
        self.hit_count = 0
        self.last_trigger_state = False
        self.is_failed = False
        self.failed_step_idx = -1
        self.violation_type = None
        self.last_completed_zone = None
        self.last_completed_time = 0.0
        self.skip_frames_counter = 0
        self.reset_dwell_start = 0.0
        for side in ["left", "right"]:
            self.hand_states[side] = {"zone": None, "entry_time": time.time()}
            self.hand_history[side].clear()
