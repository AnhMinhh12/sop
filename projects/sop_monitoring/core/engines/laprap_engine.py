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
    Product-Centric Lifecycle Engine cho trạm Máy IN-HOT-LAPRAP (Lắp ráp 8 ốc).
    Tích hợp 2 vùng ROI riêng biệt:
      - vung_lay: Vùng lấy phôi chi tiết (Khay trong suốt bên phải)
      - vung_cat: Vùng cất thành phẩm hoàn thiện (Khay phân chia bên trái)
      
    Quy tắc quản lý chu kỳ:
      - Khi công nhân tạm dừng, ngoảnh nói chuyện, lấy đồ:
        TUYỆT ĐỐI KHÔNG BÁO LỖI (NG), giữ nguyên chu kỳ và tiến độ ốc để công nhân tiếp tục.
      - Chỉ chốt LỖI (NG) khi:
        1. Công nhân cất chi tiết thiếu ốc (< 8 ốc) vào VÙNG CẤT thành phẩm bên trái.
        2. Công nhân bỏ dở chi tiết (1-7 ốc) trên bàn để sang VÙNG LẤY nhặt phôi mới.
        3. Bỏ rơi trạm quá thời gian tối đa (> 50s và vắng mặt > 20s).
      - Chỉ chốt PASS khi:
        Đã đủ 8 ốc, đưa vào VÙNG CẤT và buông 2 tay khỏi chi tiết.
    """
    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id", "machine_08")
        self.station_name = sop_config.get("station_name", "Máy IN-HOT-LAPRAP")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {"w": 1280, "h": 720})
        self.product_id = "laprap"
        self.custom_draw_zones = True  # Tự vẽ vùng ROI trực quan theo phong cách hiện đại
        
        # Cấu hình chu kỳ
        self.target_screws = int(sop_config.get("target_screws", 8))
        self.missing_dwell_sec = float(sop_config.get("missing_dwell_sec", 15.0))
        self.max_cycle_time = float(sop_config.get("config", {}).get("max_cycle_time_sec") or sop_config.get("max_cycle_time_sec", 50.0))
        
        # State machine
        self.state = "IDLE"  # "IDLE", "ASSEMBLING", "COMPLETED", "VIOLATION"
        self.cycle_count = 0
        self.total_good = 0
        self.total_ng = 0
        
        # Dữ liệu chu kỳ hiện tại
        self.slots = [False] * self.target_screws
        self.slot_hits = [0] * self.target_screws  # Bộ đếm xác nhận: chỉ chốt slot khi xuất hiện ổn định (>= 3 frames)
        self.has_completed_screws = False
        self.max_simultaneous = 0
        self.cycle_start_time = 0.0
        self.last_cycle_duration = 0.0
        self.last_seen_part_time = 0.0
        self.part_present_streak = 0
        self.last_update_time = time.time()
        
        # Tracking vùng ROI
        self.in_vung_lay = False
        self.in_vung_cat = False
        self.last_seen_lay_time = 0.0
        self.last_seen_cat_time = 0.0
        
        # Tracking điều kiện chốt hoàn thành trong vung_cat
        self.entered_cat_zone = False
        self.entered_cat_incomplete = False
        self.cat_release_start = 0.0
        
        # Tracking chuyển động để lọc găng tay tĩnh (Static Glove Filter)
        self.pos_history = []
        self.is_part_moving = False
        
        # Tiến độ bước SOP (6 bước)
        self.current_step_idx = 0
        
        # Trạng thái kết quả
        self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
        self.sop_status = "idle"
        self.is_failed = False
        self.violation_type = None
        self.banner_until = 0.0
        self.last_result_banner = None
        
        # Cache detections cho visualization
        self.last_part_hand_box = None
        self.last_screws_on_part = []
        self.has_hand_holding = False
        self.part_absent_start = 0.0
        self.last_absent_duration = 999.0
        self.last_completed_time = 0.0
        
        logger.info(f"ProductEngine [laprap]: Initialized (Target: {self.target_screws} screws, Max cycle: {self.max_cycle_time}s)")

    def _is_point_in_zone(self, point: tuple, zone_name: str) -> bool:
        """Kiểm tra tọa độ normalized (x, y) có nằm trong polygon của zone không."""
        pts = self.zones.get(zone_name)
        if not pts:
            return False
        poly = np.array(pts, np.float32)
        return cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False) >= 0

    def _is_box_in_zone(self, box: Optional[List[float]], zone_name: str, w: int, h: int) -> bool:
        """Kiểm tra tâm của bounding box có nằm trong zone không."""
        if not box:
            return False
        cx = ((box[0] + box[2]) / 2.0) / float(w)
        cy = ((box[1] + box[3]) / 2.0) / float(h)
        return self._is_point_in_zone((cx, cy), zone_name)

    def _is_hand_in_zone(self, hands_data: List[Dict], zone_name: str, w: int, h: int) -> bool:
        """Kiểm tra có bàn tay nào nằm trong zone không."""
        if not hands_data:
            return False
        for h_data in hands_data:
            hb = h_data.get("bbox")
            if not hb:
                continue
            if self._is_box_in_zone(hb, zone_name, w, h):
                return True
        return False

    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
               robot_data: List[Dict] = None) -> Dict[str, Any]:
        now = time.time()
        self.last_update_time = now
        products_data = products_data or []
        hands_data = hands_data or []
        
        w_frame = self.config.get("w", 1280)
        h_frame = self.config.get("h", 720)
        
        # 1. Phân loại detections
        part_hand_box = None
        part_hand_score = 0.0
        screws = []
        
        for p in products_data:
            c = p.get("class")
            b = p.get("bbox")
            conf = p.get("confidence", 0.0)
            if not b:
                continue
                
            if c == "part_hand":
                bcx = (b[0] + b[2]) / 2
                if conf > part_hand_score and (0.02 * w_frame <= bcx <= 0.98 * w_frame):
                    part_hand_box = b
                    part_hand_score = conf
            elif c == "screw":
                # Lọc độ tin cậy >= 0.35 để loại bỏ nhiễu lỗ phôi trống, phản xạ ánh kim và găng tay trắng
                if conf >= 0.35:
                    screws.append((b, conf))
                
        # 2. Kiểm tra bàn tay công nhân tương tác với chi tiết
        has_hand_holding = False
        if part_hand_box is not None and hands_data:
            px1, py1, px2, py2 = part_hand_box
            epx1, epy1 = px1 - 30, py1 - 30
            epx2, epy2 = px2 + 30, py2 + 30
            for h in hands_data:
                hb = h.get("bbox")
                if not hb:
                    continue
                hx1, hy1, hx2, hy2 = hb
                if max(epx1, hx1) < min(epx2, hx2) and max(epy1, hy1) < min(epy2, hy2):
                    has_hand_holding = True
                    break

        self.has_hand_holding = has_hand_holding
        
        # 3. Kiểm tra tương tác với 2 vùng ROI
        hand_in_lay = self._is_hand_in_zone(hands_data, "vung_lay", w_frame, h_frame)
        hand_in_cat = self._is_hand_in_zone(hands_data, "vung_cat", w_frame, h_frame)
        part_in_lay = self._is_box_in_zone(part_hand_box, "vung_lay", w_frame, h_frame)
        part_in_cat = self._is_box_in_zone(part_hand_box, "vung_cat", w_frame, h_frame)
        
        self.in_vung_lay = hand_in_lay or part_in_lay
        self.in_vung_cat = hand_in_cat or part_in_cat
        
        if self.in_vung_lay:
            self.last_seen_lay_time = now
        if self.in_vung_cat:
            self.last_seen_cat_time = now
            
        # 4. Lọc găng tay tĩnh (Static Glove Filter)
        is_moving = False
        if part_hand_box is not None and has_hand_holding:
            pcx = (part_hand_box[0] + part_hand_box[2]) / 2.0
            pcy = (part_hand_box[1] + part_hand_box[3]) / 2.0
            self.pos_history.append((now, pcx, pcy))
            self.pos_history = [p for p in self.pos_history if now - p[0] <= 1.2]
            
            if len(self.pos_history) >= 4:
                xs = [p[1] for p in self.pos_history]
                ys = [p[2] for p in self.pos_history]
                displacement = max(max(xs) - min(xs), max(ys) - min(ys))
                is_moving = (displacement >= 18.0)
            else:
                is_moving = False
        else:
            self.pos_history = []
            
        self.is_part_moving = is_moving
        
        # Chỉ vẽ bbox sản phẩm khi có tay cầm và không phải găng tay tĩnh ở trạng thái IDLE
        is_static_idle = (self.state == "IDLE" and not is_moving and not self.in_vung_lay and (now - self.last_seen_lay_time > 3.0))
        self.last_part_hand_box = None if is_static_idle else (part_hand_box if has_hand_holding else None)
        
        # 5. Xử lý Logic Chu kỳ & Phân bổ ốc
        current_frame_screws_on_part = []
        
        if part_hand_box is not None and has_hand_holding:
            if self.part_absent_start > 0.0:
                self.last_absent_duration = now - self.part_absent_start
                self.part_absent_start = 0.0
            self.part_present_streak += 1
            self.last_seen_part_time = now
            
            px1, py1, px2, py2 = part_hand_box
            pw = max(1, px2 - px1)
            ph = max(1, py2 - py1)
            
            # Lọc ốc nằm trong phạm vi chi tiết
            tier_screws = {0: [], 1: [], 2: [], 3: []}
            for s_box, s_conf in screws:
                scx = (s_box[0] + s_box[2]) / 2
                scy = (s_box[1] + s_box[3]) / 2
                if (px1 - 20) <= scx <= (px2 + 20) and (py1 - 20) <= scy <= (py2 + 20):
                    if ph >= pw:
                        rel_long = (scy - py1) / ph
                        rel_lat = (scx - px1) / pw
                    else:
                        rel_long = (scx - px1) / pw
                        rel_lat = (scy - py1) / ph
                    
                    rel_long = min(0.999, max(0.0, rel_long))
                    
                    # 4 tầng hình học dọc của chi tiết
                    if rel_long <= 0.27:
                        t = 0
                    elif rel_long <= 0.48:
                        t = 1
                    elif rel_long <= 0.70:
                        t = 2
                    else:
                        t = 3
                        
                    tier_screws[t].append((s_box, s_conf, rel_lat, scx))

            visible_screws = sum(len(tier_screws[t]) for t in range(4))
            has_all_screws = (self.has_completed_screws or visible_screws >= self.target_screws or sum(self.slots) >= self.target_screws)

            # Đánh dấu chi tiết vào VÙNG CẤT (vung_cat) bên trái
            # CHỈ kích hoạt khi chính bounding box của chi tiết (part_hand) nằm trong khay cất
            if self.state == "ASSEMBLING":
                if part_in_cat:
                    if has_all_screws:
                        self.entered_cat_zone = True
                    elif max(sum(self.slots), self.max_simultaneous) > 0:
                        self.entered_cat_incomplete = True
                else:
                    # Chi tiết đang ở giữa bàn làm việc hoặc vùng lấy -> Đang lắp ráp bình thường!
                    # Hủy bỏ ngay cờ cất nếu chi tiết quay lại hoặc đang ở trên bàn
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0

            # TRƯỜNG HỢP 1A: Chi tiết ĐỦ 8 ỐC vào VÙNG CẤT -> Chờ buông 2 tay mới chốt PASS
            if self.state == "ASSEMBLING" and self.entered_cat_zone:
                hands_released = (not has_hand_holding) or (not hand_in_cat)
                
                if hands_released:
                    if self.cat_release_start == 0.0:
                        self.cat_release_start = now
                    if now - self.cat_release_start >= 0.35:
                        self.total_good += 1
                        self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                        self.state = "COMPLETED"
                        self.sop_status = "completed"
                        self.is_failed = False
                        self.current_step_idx = 5
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: PASS (Đã buông tay cất vào khay trái)"
                        self.last_result_banner = (f"CHU KY #{self.cycle_count}: PASS (DU 8 OC)", True)
                        self.banner_until = now + 1.5
                        self.last_completed_time = now
                        self.entered_cat_zone = False
                        self.entered_cat_incomplete = False
                        self.cat_release_start = 0.0
                        logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} PASS -> Released hands in vung_cat.")
                else:
                    self.cat_release_start = 0.0
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."

            # TRƯỜNG HỢP 1B: Chi tiết THIẾU ỐC (<8 ốc) mà công nhân đã cất vào VÙNG CẤT và buông tay -> VI PHẠM (NG)
            # CHỈ BẮT LỖI KHI HẾT CHU KỲ (ĐÃ CẤT VÀO KHAY TRÁI VÀ BUÔNG TAY >= 0.35s)
            elif self.state == "ASSEMBLING" and self.entered_cat_incomplete:
                hands_released = (not has_hand_holding) or (not hand_in_cat)
                if hands_released:
                    if self.cat_release_start == 0.0:
                        self.cat_release_start = now
                    if now - self.cat_release_start >= 0.35:
                        curr_count = max(sum(self.slots), self.max_simultaneous)
                        self.total_ng += 1
                        self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                        self.state = "VIOLATION"
                        self.sop_status = "violation"
                        self.is_failed = True
                        self.violation_type = f"Thiếu ốc ({curr_count}/{self.target_screws}) đã cất khay trái"
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: NG - Thiếu ốc ({curr_count}/{self.target_screws})"
                        self.last_result_banner = (f"CHU KY #{self.cycle_count}: THIEU OC ({curr_count}/{self.target_screws})", False)
                        self.banner_until = now + 2.5
                        self.last_completed_time = now
                        self.entered_cat_zone = False
                        self.entered_cat_incomplete = False
                        self.cat_release_start = 0.0
                        logger.warning(f"ProductEngine [laprap]: Cycle #{self.cycle_count} VIOLATION - Incomplete stored in vung_cat.")
                else:
                    self.cat_release_start = 0.0
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."

            # TRƯỜNG HỢP 2: Bắt đầu chu kỳ mới từ IDLE / COMPLETED / VIOLATION
            # Yêu cầu: Phôi mới (<= 2 ốc) VÀ (phải được lấy từ vung_lay HOẶC đang có thao tác cầm nắm chuyển động thực tế)
            elif self.state in ["IDLE", "COMPLETED", "VIOLATION"] and self.part_present_streak >= 3:
                if self.in_vung_cat or self.entered_cat_zone or part_in_cat:
                    self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
                else:
                    is_fresh_part = (visible_screws <= 2)
                    is_from_lay_zone = (self.in_vung_lay or (now - self.last_seen_lay_time < 3.0))
                    is_active_holding = (is_moving and has_hand_holding)
                    
                    if is_fresh_part and (is_from_lay_zone or is_active_holding):
                        self.state = "ASSEMBLING"
                        self.sop_status = "processing"
                        self.cycle_count += 1
                        self.cycle_start_time = now
                        self.last_cycle_duration = 0.0
                        self.slots = [False] * self.target_screws
                        self.slot_hits = [0] * self.target_screws
                        self.has_completed_screws = False
                        self.max_simultaneous = 0
                        self.is_failed = False
                        self.violation_type = None
                        self.banner_until = 0.0
                        self.last_result_banner = None
                        self.entered_cat_zone = False
                        self.entered_cat_incomplete = False
                        self.cat_release_start = 0.0
                        self.current_step_idx = 1
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc (0/{self.target_screws})"
                        logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} started (lay_zone={is_from_lay_zone}, moving={is_moving}).")
                    else:
                        if not is_fresh_part:
                            self.status_msg = f"Chờ cất chi tiết cũ ({visible_screws} ốc) vào khay trái"
                        else:
                            self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"

            # Gán slot cho từng con ốc theo 2D Tier Accumulator (Trái / Phải) với bộ lọc xác nhận chống nhiễu
            for t in range(4):
                s_list = tier_screws[t]
                slot_base = t * 2
                
                if len(s_list) >= 2:
                    s_list.sort(key=lambda item: item[2])
                    current_frame_screws_on_part.append((s_list[0][0], s_list[0][1], slot_base))
                    current_frame_screws_on_part.append((s_list[1][0], s_list[1][1], slot_base + 1))
                    for extra in s_list[2:]:
                        current_frame_screws_on_part.append((extra[0], extra[1], slot_base + 1))
                        
                    if self.state == "ASSEMBLING":
                        self.slot_hits[slot_base] += 1
                        self.slot_hits[slot_base + 1] += 1
                        if self.slot_hits[slot_base] >= 3:
                            self.slots[slot_base] = True
                        if self.slot_hits[slot_base + 1] >= 3:
                            self.slots[slot_base + 1] = True
                elif len(s_list) == 1:
                    rel_lat = s_list[0][2]
                    assigned_slot = slot_base if rel_lat < 0.65 else (slot_base + 1)
                    current_frame_screws_on_part.append((s_list[0][0], s_list[0][1], assigned_slot))
                    
                    if self.state == "ASSEMBLING":
                        self.slot_hits[assigned_slot] += 1
                        if self.slot_hits[assigned_slot] >= 3:
                            self.slots[assigned_slot] = True

            self.last_screws_on_part = current_frame_screws_on_part
            
            # Cập nhật số ốc đồng thời trong frame
            n_sim = len(current_frame_screws_on_part)
            if n_sim > self.max_simultaneous:
                self.max_simultaneous = n_sim
                
            if self.state == "ASSEMBLING":
                curr_count = max(sum(self.slots), self.max_simultaneous)
                
                if curr_count < 2:
                    self.current_step_idx = 1   # Bước 2: Lắp ốc vị trí 1 - 2
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 4:
                    self.current_step_idx = 2   # Bước 3: Lắp ốc vị trí 3 - 4
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 6:
                    self.current_step_idx = 3   # Bước 4: Lắp ốc vị trí 5 - 6
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 8:
                    self.current_step_idx = 4   # Bước 5: Lắp ốc vị trí 7 - 8
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                else:
                    self.current_step_idx = 5   # Bước 6: Hoàn tất & Cất chi tiết
                    self.has_completed_screws = True
                    if self.entered_cat_zone:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."
                    else:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Đóng nẹp & Đưa sang khay trái"
                
        else:
            # --- TRƯỜNG HỢP VẮNG BÓNG CHI TIẾT TRÊN TAY (ABSENT) ---
            if self.part_absent_start == 0.0:
                self.part_absent_start = now
            self.part_present_streak = 0
            self.last_screws_on_part = []
            
            # TRƯỜNG HỢP A: ĐÃ VÀO VÙNG CẤT THÀNH PHẨM (vung_cat) VÀ BUÔNG TAY THẢ VÀO KHAY -> PASS!
            if self.state == "ASSEMBLING" and self.entered_cat_zone:
                if self.cat_release_start == 0.0:
                    self.cat_release_start = now
                if now - self.cat_release_start >= 0.35:
                    self.total_good += 1
                    self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                    self.state = "COMPLETED"
                    self.sop_status = "completed"
                    self.is_failed = False
                    self.current_step_idx = 5
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: PASS (Đã buông tay cất vào khay trái)"
                    self.last_result_banner = (f"CHU KY #{self.cycle_count}: PASS (DU 8 OC)", True)
                    self.banner_until = now + 1.5
                    self.last_completed_time = now
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                    logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} PASS -> Absent after vung_cat.")

            # TRƯỜNG HỢP B: ĐÃ VÀO VÙNG CẤT (vung_cat) NHƯNG THIẾU ỐC VÀ BUÔNG TAY -> NG (HẾT CHU KỲ)!
            elif self.state == "ASSEMBLING" and self.entered_cat_incomplete:
                if self.cat_release_start == 0.0:
                    self.cat_release_start = now
                if now - self.cat_release_start >= 0.35:
                    curr_count = max(sum(self.slots), self.max_simultaneous)
                    self.total_ng += 1
                    self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                    self.state = "VIOLATION"
                    self.sop_status = "violation"
                    self.is_failed = True
                    self.violation_type = f"Thiếu ốc ({curr_count}/{self.target_screws}) đã cất khay trái"
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: NG - Thiếu ốc ({curr_count}/{self.target_screws})"
                    self.last_result_banner = (f"CHU KY #{self.cycle_count}: THIEU OC ({curr_count}/{self.target_screws})", False)
                    self.banner_until = now + 2.5
                    self.last_completed_time = now
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                    logger.warning(f"ProductEngine [laprap]: Cycle #{self.cycle_count} VIOLATION -> Absent after vung_cat (incomplete).")
            
            # TRƯỜNG HỢP C: ĐÃ ĐỦ 8 ỐC NHƯNG ĐANG XOAY/ĐÓNG NẸP Ở GIỮA BÀN -> TUYỆT ĐỐI KHÔNG CHỐT PASS, KHÔNG BÁO LỖI!
            elif self.state == "ASSEMBLING" and self.has_completed_screws:
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Đóng nẹp & Đưa sang khay trái"
            
            # TRƯỜNG HỢP C: 0 ỐC: Vắng bóng 1.5s -> Reset IDLE (không tính lỗi NG)
            elif self.state == "ASSEMBLING" and max(sum(self.slots), self.max_simultaneous) == 0:
                if now - self.last_seen_part_time >= 1.5:
                    self.state = "IDLE"
                    self.sop_status = "idle"
                    self.is_failed = False
                    self.violation_type = None
                    self.current_step_idx = 0
                    self.status_msg = "Sẵn sàng (Chờ phôi mới từ khay phải)"
                    self.banner_until = 0.0
                    self.last_result_banner = None
                    self.slots = [False] * self.target_screws
                    self.slot_hits = [0] * self.target_screws
                    self.max_simultaneous = 0
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                    logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} reset to IDLE (0 screws).")
                    
            # TRƯỜNG HỢP D: 1-7 ỐC ĐANG LẮP MÀ TẠM DỪNG (NGOẢNH NÓI CHUYỆN, ĐẶT XUỐNG BÀN, LẤY ỐC):
            # TUYỆT ĐỐI KHÔNG BÁO LỖI (KHÔNG TÍNH NG), GIỮ NGUYÊN CHU KỲ VÀ SLOTS ĐỂ CÔNG NHÂN QUAY LẠI LẮP TIẾP!
            elif self.state == "ASSEMBLING" and (1 <= max(sum(self.slots), self.max_simultaneous) < self.target_screws):
                curr_count = max(sum(self.slots), self.max_simultaneous)
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang tạm dừng ({curr_count}/{self.target_screws} ốc)"
                    
        # Kiểm tra quá thời gian tối đa chu kỳ (Timeout)
        if self.state == "ASSEMBLING" and (now - self.cycle_start_time > self.max_cycle_time):
            final_screw_count = max(sum(self.slots), self.max_simultaneous)
            self.last_cycle_duration = round(now - self.cycle_start_time, 1)
            
            if final_screw_count == 0:
                self.state = "IDLE"
                self.sop_status = "idle"
                self.is_failed = False
                self.violation_type = None
                self.current_step_idx = 0
                self.status_msg = "Sẵn sàng (Chờ phôi mới từ khay phải)"
                self.banner_until = 0.0
                self.last_result_banner = None
                self.slots = [False] * self.target_screws
                self.slot_hits = [0] * self.target_screws
                self.max_simultaneous = 0
                self.entered_cat_zone = False
                self.entered_cat_incomplete = False
                self.cat_release_start = 0.0
                logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} timeout with 0 screws -> reset to IDLE (NO NG).")
            elif final_screw_count >= self.target_screws or self.has_completed_screws:
                if self.entered_cat_zone:
                    self.total_good += 1
                    self.state = "COMPLETED"
                    self.sop_status = "completed"
                    self.is_failed = False
                    self.current_step_idx = 5
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: PASS ({final_screw_count}/{self.target_screws} ốc)"
                    self.banner_until = now + 1.8
                    self.last_completed_time = now
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                else:
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Chờ cất vào khay trái"
            else:
                # Chỉ chốt quá thời gian nếu công nhân đã thực sự bỏ đi khỏi trạm (vắng mặt liên tục > 20s)
                if now - self.last_seen_part_time >= 20.0:
                    self.total_ng += 1
                    self.state = "VIOLATION"
                    self.sop_status = "violation"
                    self.is_failed = True
                    self.violation_type = f"Quá thời gian ({final_screw_count}/{self.target_screws} ốc)"
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Quá thời gian ({final_screw_count}/{self.target_screws} ốc)"
                    self.last_result_banner = (f"CHU KY #{self.cycle_count}: QUA GIO ({final_screw_count}/{self.target_screws} OC)", False)
                    self.banner_until = now + 2.5
                    self.last_completed_time = now
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                    logger.warning(f"ProductEngine [laprap]: Cycle #{self.cycle_count} TIMEOUT VIOLATION (absent > 20s).")
                else:
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang tiếp tục lắp ({final_screw_count}/{self.target_screws} ốc)"
                    
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        now = self.last_update_time
        screw_count = max(sum(self.slots), self.max_simultaneous)
        
        # Danh sách 6 bước chuẩn SOP đồng bộ với laprap.yaml
        step_names = [
            "Lấy phôi chi tiết (Khay phải)",
            "Lắp ốc vị trí 1 - 2",
            "Lắp ốc vị trí 3 - 4",
            "Lắp ốc vị trí 5 - 6",
            "Lắp ốc vị trí 7 - 8",
            "Hoàn tất & Cất chi tiết (Khay trái)"
        ]
        
        # Tự động quay về IDLE sau khi hết thời gian lưu thông báo kết quả
        if now >= self.banner_until and self.state in ["COMPLETED", "VIOLATION"]:
            self.state = "IDLE"
            self.sop_status = "idle"
            self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
            self.current_step_idx = 0
            self.last_result_banner = None
            self.slots = [False] * self.target_screws
            self.slot_hits = [0] * self.target_screws
            self.max_simultaneous = 0
            self.entered_cat_zone = False
            self.entered_cat_incomplete = False
            self.cat_release_start = 0.0

        cycle_elapsed = (now - self.cycle_start_time) if self.state == "ASSEMBLING" else (
            self.last_cycle_duration if self.state in ["COMPLETED", "VIOLATION"] else 0.0
        )
            
        status_to_report = self.sop_status
        
        # Tính toán step_states và nhãn hiển thị đồng bộ
        if self.state == "IDLE":
            step_idx = 0
            step_states = [False] * 6
            expected_step = "Lấy phôi chi tiết (Khay phải)"
            detected_label = "Chờ phôi khay phải"
            cycle_time_left = self.max_cycle_time
            progress_pct = 0.0
        elif self.state == "ASSEMBLING":
            step_idx = self.current_step_idx
            step_states = [i < step_idx for i in range(6)]
            if step_idx < 5:
                expected_step = step_names[step_idx]
                if now - self.last_seen_part_time >= 2.0 and screw_count > 0:
                    detected_label = f"Tạm dừng (đã lắp {screw_count}/{self.target_screws} ốc)"
                else:
                    detected_label = f"Đã lắp {screw_count}/{self.target_screws} ốc"
            else:
                expected_step = "Hoàn tất & Cất chi tiết (Khay trái)"
                if self.entered_cat_zone:
                    detected_label = "Chờ buông 2 tay cất khay trái"
                else:
                    detected_label = f"Đủ {self.target_screws} ốc. Đưa sang khay trái"
            cycle_time_left = max(0.0, self.max_cycle_time - cycle_elapsed)
            progress_pct = min(100.0, (screw_count / float(self.target_screws)) * 100.0)
        elif self.state == "COMPLETED":
            step_idx = 5
            step_states = [True] * 6
            expected_step = "Hoàn tất chu kỳ"
            detected_label = f"Hoàn thành đủ {self.target_screws}/{self.target_screws} ốc"
            cycle_time_left = max(0.0, self.max_cycle_time - (self.last_cycle_duration or cycle_elapsed))
            progress_pct = 100.0
        else:  # VIOLATION
            step_idx = self.current_step_idx
            step_states = [i < step_idx for i in range(6)]
            expected_step = "Lắp đủ 8 ốc"
            detected_label = f"Thiếu ốc ({screw_count}/{self.target_screws})"
            cycle_time_left = 0.0
            progress_pct = min(100.0, (screw_count / float(self.target_screws)) * 100.0)
            
        return {
            "sop_status": status_to_report,
            "status_msg": self.status_msg,
            "expected_step": expected_step,
            "detected_label": detected_label,
            "step_index": step_idx,
            "step_states": step_states,
            "progress_percent": progress_pct,
            "is_failed": self.is_failed,
            "failed_step_idx": -1 if not self.is_failed else step_idx,
            "cycle_count": self.cycle_count,
            "cycle_time_left": cycle_time_left,
            "max_cycle_time": self.max_cycle_time,
            "cycle_elapsed": cycle_elapsed,
            "duration": round(cycle_elapsed, 1),
            "step_list": step_names,
            "violation_type": self.violation_type,
            "slots": list(self.slots),
            "screws_detected": screw_count,
            "target_screws": self.target_screws,
            "total_good": self.total_good,
            "total_ng": self.total_ng,
        }

    def reset(self) -> None:
        self.state = "IDLE"
        self.sop_status = "idle"
        self.slots = [False] * self.target_screws
        self.slot_hits = [0] * self.target_screws
        self.max_simultaneous = 0
        self.part_present_streak = 0
        self.cycle_start_time = 0.0
        self.last_cycle_duration = 0.0
        self.current_step_idx = 0
        self.is_failed = False
        self.violation_type = None
        self.last_result_banner = None
        self.banner_until = 0.0
        self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
        self.last_part_hand_box = None
        self.last_screws_on_part = []
        self.part_absent_start = 0.0
        self.last_absent_duration = 999.0
        self.last_completed_time = 0.0
        self.in_vung_lay = False
        self.in_vung_cat = False
        self.entered_cat_zone = False
        self.entered_cat_incomplete = False
        self.cat_release_start = 0.0
        self.pos_history = []

    def draw_hud(self, frame: np.ndarray) -> np.ndarray:
        now = self.last_update_time
        h, w = frame.shape[:2]
        
        # 1. Vẽ 2 VÙNG ROI: VÙNG CẤT (TRÁI) VÀ VÙNG LẤY (PHẢI)
        overlay = frame.copy()
        
        # 1.1 Vùng cất thành phẩm (Khay bên trái)
        cat_pts_norm = self.zones.get("vung_cat", [])
        if cat_pts_norm:
            cat_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in cat_pts_norm], dtype=np.int32)
            cat_active = self.in_vung_cat or self.entered_cat_zone
            cat_color = (255, 190, 40) if cat_active else (210, 140, 25)
            
            # Fill bán trong suốt
            cv2.fillPoly(overlay, [cat_pts], cat_color)
            cv2.polylines(frame, [cat_pts], True, cat_color, 2, cv2.LINE_AA)
            
            # Text Badge
            min_x = int(np.min(cat_pts[:, 0]))
            min_y = int(np.min(cat_pts[:, 1]))
            badge_lbl = "[VUNG CAT THANH PHAM]"
            (tw, th), _ = cv2.getTextSize(badge_lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            cv2.rectangle(frame, (min_x + 8, min_y + 8), (min_x + 14 + tw, min_y + 14 + th + 6), (20, 24, 30), -1)
            cv2.rectangle(frame, (min_x + 8, min_y + 8), (min_x + 14 + tw, min_y + 14 + th + 6), cat_color, 1)
            cv2.putText(frame, badge_lbl, (min_x + 11, min_y + 12 + th),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, cat_color, 1, cv2.LINE_AA)

        # 1.2 Vùng lấy phôi (Khay bên phải)
        lay_pts_norm = self.zones.get("vung_lay", [])
        if lay_pts_norm:
            lay_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in lay_pts_norm], dtype=np.int32)
            lay_active = self.in_vung_lay
            lay_color = (40, 240, 90) if lay_active else (30, 190, 70)
            
            # Fill bán trong suốt
            cv2.fillPoly(overlay, [lay_pts], lay_color)
            cv2.polylines(frame, [lay_pts], True, lay_color, 2, cv2.LINE_AA)
            
            # Text Badge
            min_x = int(np.min(lay_pts[:, 0]))
            min_y = int(np.min(lay_pts[:, 1]))
            badge_lbl = "[VUNG LAY PHOI]"
            (tw, th), _ = cv2.getTextSize(badge_lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            cv2.rectangle(frame, (min_x + 8, min_y + 8), (min_x + 14 + tw, min_y + 14 + th + 6), (20, 24, 30), -1)
            cv2.rectangle(frame, (min_x + 8, min_y + 8), (min_x + 14 + tw, min_y + 14 + th + 6), lay_color, 1)
            cv2.putText(frame, badge_lbl, (min_x + 11, min_y + 12 + th),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, lay_color, 1, cv2.LINE_AA)
                        
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        
        # 2. Vẽ Bbox part_hand thanh mảnh
        if self.last_part_hand_box is not None:
            px1, py1, px2, py2 = [int(v) for v in self.last_part_hand_box]
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 140, 255), 2)
            lbl = "SAN PHAM (Tren tay)"
            (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (px1, max(0, py1 - 20)), (px1 + tw + 6, py1), (0, 140, 255), -1)
            cv2.putText(frame, lbl, (px1 + 3, max(14, py1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                        
        # 3. Vẽ các ốc phát hiện trên thân chi tiết
        for s_box, s_conf, slot_idx in self.last_screws_on_part:
            sx1, sy1, sx2, sy2 = [int(v) for v in s_box]
            cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), (0, 230, 255), 2)
            cv2.putText(frame, f"#{slot_idx+1}", (sx1, max(14, sy1 - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1, cv2.LINE_AA)
                        
        # 4. HUD Dashboard Bar trên góc trên (y=15 đến y=72)
        overlay_bar = frame.copy()
        cv2.rectangle(overlay_bar, (20, 12), (750, 72), (20, 24, 30), -1)
        cv2.addWeighted(overlay_bar, 0.8, frame, 0.2, 0, frame)
        cv2.rectangle(frame, (20, 12), (750, 72), (65, 75, 90), 1)
        
        # Dòng 1: Tiêu đề máy + Trạng thái chu kỳ
        if self.state == "ASSEMBLING":
            if self.entered_cat_zone:
                state_color = (255, 200, 50)
                state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: CHO BUONG 2 TAY CAT KHAY TRAI"
            elif self.has_completed_screws:
                state_color = (16, 220, 160)
                state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: DU 8 OC - DUA SANG KHAY TRAI"
            elif now - self.last_seen_part_time >= 2.0 and max(sum(self.slots), self.max_simultaneous) > 0:
                state_color = (255, 180, 50)
                curr_count = max(sum(self.slots), self.max_simultaneous)
                state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: DANG TAM DUNG ({curr_count}/{self.target_screws} OC)"
            else:
                state_color = (0, 220, 255)
                state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: DANG LAP RAP"
        elif self.state == "COMPLETED" or (now < self.banner_until and self.last_result_banner and self.last_result_banner[1]):
            state_color = (16, 200, 100)
            state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: PASS (DU 8 OC)"
        elif self.state == "VIOLATION" or (now < self.banner_until and self.last_result_banner and not self.last_result_banner[1]):
            state_color = (60, 60, 240)
            state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: VI PHAM ({self.violation_type or 'THIEU OC'})"
        else:
            state_color = (160, 165, 175)
            state_str = "MAY IN-HOT-LAPRAP | CHO PHOI KHAY PHAI"
            
        cv2.putText(frame, state_str, (32, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.48, state_color, 1, cv2.LINE_AA)
        cv2.putText(frame, f"PASS: {self.total_good}  |  NG: {self.total_ng}", (565, 33),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (16, 200, 100), 1, cv2.LINE_AA)
                    
        # Dòng 2: Dải 8 ô ốc trực quan [1] [2] ... [8]
        screw_count = max(sum(self.slots), self.max_simultaneous)
        if self.state == "IDLE":
            screw_count = 0
        bar_x = 32
        bar_y = 44
        box_w = 26
        box_h = 20
        spacing = 6
        
        for i in range(self.target_screws):
            bx = bar_x + i * (box_w + spacing)
            by = bar_y
            if self.slots[i]:
                cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (16, 185, 129), -1)
                cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (50, 230, 160), 1)
                cv2.putText(frame, str(i + 1), (bx + 8, by + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            else:
                cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (40, 45, 55), -1)
                cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), (80, 90, 105), 1)
                cv2.putText(frame, str(i + 1), (bx + 8, by + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 155, 165), 1, cv2.LINE_AA)
                            
        # Nhãn tiến độ bên cạnh dải số
        progress_text = f"TIEN DO: {screw_count}/{self.target_screws} OC"
        cv2.putText(frame, progress_text, (bar_x + self.target_screws * (box_w + spacing) + 15, bar_y + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1, cv2.LINE_AA)
                    
        return frame
