import cv2
import os
import sys
import time

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.base_engine import BaseEngine
import numpy as np

class ImprovedProductEngine(BaseEngine):
    def __init__(self, sop_config):
        self.station_id = sop_config.get("station_id", "machine_08")
        self.station_name = sop_config.get("station_name", "Máy IN-HOT-LAPRAP")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        self.config = sop_config.get("config", {"w": 1280, "h": 720})
        self.target_screws = int(sop_config.get("target_screws", 8))
        self.max_cycle_time = float(sop_config.get("max_cycle_time_sec", 60.0))
        
        self.state = "IDLE"
        self.cycle_count = 0
        self.total_good = 0
        self.total_ng = 0
        
        self.slots = [False] * self.target_screws
        self.slot_hits = [0] * self.target_screws  # Cần thấy >= 3 frame mới xác nhận slot
        self.has_completed_screws = False
        self.max_simultaneous = 0
        self.cycle_start_time = 0.0
        self.last_cycle_duration = 0.0
        self.last_seen_part_time = 0.0
        self.part_present_streak = 0
        self.last_update_time = time.time()
        
        self.in_vung_lay = False
        self.in_vung_cat = False
        self.last_seen_lay_time = 0.0
        self.last_seen_cat_time = 0.0
        self.entered_cat_zone = False
        self.entered_cat_incomplete = False
        self.cat_release_start = 0.0
        
        self.pos_history = []
        self.is_part_moving = False
        self.current_step_idx = 0
        self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
        self.sop_status = "idle"
        self.is_failed = False
        self.violation_type = None
        self.banner_until = 0.0
        self.last_result_banner = None
        self.last_completed_time = 0.0
        self.part_absent_start = 0.0

    def _is_point_in_zone(self, point: tuple, zone_name: str) -> bool:
        pts = self.zones.get(zone_name)
        if not pts:
            return False
        poly = np.array(pts, np.float32)
        return cv2.pointPolygonTest(poly, (float(point[0]), float(point[1])), False) >= 0

    def _is_box_in_zone(self, box, zone_name: str, w: int, h: int) -> bool:
        if not box:
            return False
        cx = ((box[0] + box[2]) / 2.0) / float(w)
        cy = ((box[1] + box[3]) / 2.0) / float(h)
        return self._is_point_in_zone((cx, cy), zone_name)

    def _is_hand_in_zone(self, hands_data, zone_name: str, w: int, h: int) -> bool:
        for h_data in hands_data:
            hb = h_data.get("bbox")
            if hb and self._is_box_in_zone(hb, zone_name, w, h):
                return True
        return False

    def update(self, hands_data, products_data=None, robot_data=None):
        now = time.time()
        self.last_update_time = now
        products_data = products_data or []
        hands_data = hands_data or []
        
        w_frame = self.config.get("w", 1280)
        h_frame = self.config.get("h", 720)
        
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
                # Lọc ốc tin cậy conf >= 0.35 để tránh nhiễu phản xạ / lỗ trống / bao ngón tay
                if conf >= 0.35:
                    screws.append((b, conf))
                    
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

        is_moving = False
        if part_hand_box is not None and has_hand_holding:
            pcx = (part_hand_box[0] + part_hand_box[2]) / 2.0
            pcy = (part_hand_box[1] + part_hand_box[3]) / 2.0
            self.pos_history.append((now, pcx, pcy))
            self.pos_history = [p for p in self.pos_history if now - p[0] <= 1.2]
            if len(self.pos_history) >= 4:
                xs = [p[1] for p in self.pos_history]
                ys = [p[2] for p in self.pos_history]
                is_moving = (max(max(xs) - min(xs), max(ys) - min(ys)) >= 18.0)
        else:
            self.pos_history = []
        self.is_part_moving = is_moving

        current_frame_screws_on_part = []
        
        if part_hand_box is not None and has_hand_holding:
            self.part_present_streak += 1
            self.last_seen_part_time = now
            self.part_absent_start = 0.0
            
            px1, py1, px2, py2 = part_hand_box
            pw = max(1, px2 - px1)
            ph = max(1, py2 - py1)
            
            tier_screws = {0: [], 1: [], 2: [], 3: []}
            for s_box, s_conf in screws:
                scx = (s_box[0] + s_box[2]) / 2
                scy = (s_box[1] + s_box[3]) / 2
                if (px1 - 15) <= scx <= (px2 + 15) and (py1 - 15) <= scy <= (py2 + 15):
                    if ph >= pw:
                        rel_long = (scy - py1) / ph
                        rel_lat = (scx - px1) / pw
                    else:
                        rel_long = (scx - px1) / pw
                        rel_lat = (scy - py1) / ph
                    
                    rel_long = min(0.999, max(0.0, rel_long))
                    
                    # 4 tầng hình học dọc của chi tiết
                    if rel_long <= 0.28:
                        t = 0
                    elif rel_long <= 0.45:
                        t = 1
                    elif rel_long <= 0.65:
                        t = 2
                    else:
                        t = 3
                        
                    tier_screws[t].append((s_box, s_conf, rel_lat))

            visible_screws = sum(len(tier_screws[t]) for t in range(4))
            has_all_screws = (self.has_completed_screws or sum(self.slots) >= self.target_screws or visible_screws >= self.target_screws)

            # Phân bổ slot cho từng tầng
            for t in range(4):
                s_list = tier_screws[t]
                slot_base = t * 2
                
                if len(s_list) >= 2:
                    s_list.sort(key=lambda item: item[2])
                    current_frame_screws_on_part.append((s_list[0][0], s_list[0][1], slot_base))
                    current_frame_screws_on_part.append((s_list[1][0], s_list[1][1], slot_base + 1))
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

            n_sim = len(current_frame_screws_on_part)
            if n_sim > self.max_simultaneous:
                self.max_simultaneous = n_sim
                
            # Đánh dấu chi tiết vào VÙNG CẤT (vung_cat) bên trái
            if self.state == "ASSEMBLING":
                if part_in_cat:
                    if has_all_screws:
                        self.entered_cat_zone = True
                    elif max(sum(self.slots), self.max_simultaneous) > 0:
                        self.entered_cat_incomplete = True
                else:
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0

            # TRƯỜNG HỢP 1A: Chi tiết ĐỦ 8 ỐC vào VÙNG CẤT -> Chờ buông tay mới chốt PASS
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
                else:
                    self.cat_release_start = 0.0
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."

            # TRƯỜNG HỢP 1B: Chi tiết THIẾU ỐC vào VÙNG CẤT và buông tay -> VI PHẠM (NG)
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
                else:
                    self.cat_release_start = 0.0
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."

            # TRƯỜNG HỢP 2: Bắt đầu chu kỳ mới từ IDLE / COMPLETED / VIOLATION
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
                    else:
                        if not is_fresh_part:
                            self.status_msg = f"Chờ cất chi tiết cũ ({visible_screws} ốc) vào khay trái"
                        else:
                            self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"

            if self.state == "ASSEMBLING":
                curr_count = max(sum(self.slots), self.max_simultaneous)
                if curr_count < 2:
                    self.current_step_idx = 1
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 4:
                    self.current_step_idx = 2
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 6:
                    self.current_step_idx = 3
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                elif curr_count < 8:
                    self.current_step_idx = 4
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                else:
                    self.current_step_idx = 5
                    self.has_completed_screws = True
                    if self.entered_cat_zone:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."
                    else:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Đóng nẹp & Đưa sang khay trái"

        else:
            # Chi tiết vắng mặt
            if self.part_absent_start == 0.0:
                self.part_absent_start = now
            self.part_present_streak = 0
            
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

            elif self.state == "ASSEMBLING" and self.has_completed_screws:
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Đóng nẹp & Đưa sang khay trái"
            elif self.state == "ASSEMBLING" and max(sum(self.slots), self.max_simultaneous) == 0:
                if now - self.last_seen_part_time >= 2.0:
                    self.state = "IDLE"
                    self.sop_status = "idle"
                    self.current_step_idx = 0
                    self.status_msg = "Sẵn sàng (Chờ phôi mới từ khay phải)"
                    self.slots = [False] * self.target_screws
                    self.slot_hits = [0] * self.target_screws
                    self.max_simultaneous = 0
            elif self.state == "ASSEMBLING":
                curr_count = max(sum(self.slots), self.max_simultaneous)
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang tạm dừng ({curr_count}/{self.target_screws} ốc)"

        return self.get_status()

    def reset(self) -> None:
        self.state = "IDLE"
        self.sop_status = "idle"
        self.slots = [False] * self.target_screws
        self.slot_hits = [0] * self.target_screws
        self.max_simultaneous = 0
        self.current_step_idx = 0

    def get_status(self):
        now = self.last_update_time
        screw_count = max(sum(self.slots), self.max_simultaneous)
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

        if self.state == "IDLE":
            step_idx = 0
            step_states = [False] * 6
        elif self.state == "ASSEMBLING":
            step_idx = self.current_step_idx
            step_states = [i < step_idx for i in range(6)]
        elif self.state == "COMPLETED":
            step_idx = 5
            step_states = [True] * 6
        else:
            step_idx = self.current_step_idx
            step_states = [i < step_idx for i in range(6)]

        return {
            "sop_status": self.sop_status,
            "step_index": step_idx,
            "step_states": step_states,
            "screw_count": screw_count,
            "state": self.state
        }


def run_benchmark():
    video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    
    detector = HandDetector("machine_08", confidence_threshold=0.22, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = ImprovedProductEngine(sop_config)

    print("Testing Improved Engine on first 85s of video...", flush=True)
    frame_idx = 0
    last_slots_sum = -1
    last_state = ""
    
    while frame_idx < 85 * fps:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % 2 != 0:
            continue
            
        dets = detector.detect(frame)
        hands = [d for d in dets if d.get("class") == "hand"]
        prods = [d for d in dets if d.get("class") in ["part_hand", "part_tray", "screw"]]
        
        status = engine.update(hands_data=hands, products_data=prods)
        sec = frame_idx / fps
        slots_sum = sum(engine.slots)
        
        if slots_sum != last_slots_sum or engine.state != last_state or frame_idx % 50 == 0:
            print(f"[{sec:5.1f}s | F{frame_idx:04d}] State: {engine.state:11s} | Step: {engine.current_step_idx} | Slots: {engine.slots} ({slots_sum}/8) | Msg: {engine.status_msg}", flush=True)
            last_slots_sum = slots_sum
            last_state = engine.state

    cap.release()
    print(f"\nFinal Result: Total GOOD = {engine.total_good}, Total NG = {engine.total_ng}, Total Cycles = {engine.cycle_count}", flush=True)

if __name__ == "__main__":
    run_benchmark()
