import cv2
import os
import sys
import time

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.hand_detector import HandDetector
from projects.sop_monitoring.core.engines.base_engine import BaseEngine
import numpy as np

class InspectionGestureEngine(BaseEngine):
    """
    Engine trạm Máy IN-HOT-LAPRAP theo quy trình 'Giơ chi tiết kiểm tra 8 ốc' (Inspection Gesture).
    4 bước SOP:
      1. Lấy phôi chi tiết (Khay phải)
      2. Lắp ráp 8 ốc vào thân chi tiết (Thao tác tự do)
      3. Giơ kiểm tra đủ 8 ốc trước camera (Khoảnh khắc vàng 0.5s)
      4. Đóng nẹp & Cất thành phẩm (Khay trái)
    """
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
        
        self.has_verified_8_screws = False
        self.inspect_streak = 0
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
        self.last_part_hand_box = None
        self.last_screws_on_part = []

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

        # Lọc các ốc nằm trên chi tiết
        current_frame_screws_on_part = []
        if part_hand_box is not None and has_hand_holding:
            self.part_present_streak += 1
            self.last_seen_part_time = now
            self.part_absent_start = 0.0
            
            px1, py1, px2, py2 = part_hand_box
            for s_box, s_conf in screws:
                scx = (s_box[0] + s_box[2]) / 2
                scy = (s_box[1] + s_box[3]) / 2
                if (px1 - 25) <= scx <= (px2 + 25) and (py1 - 25) <= scy <= (py2 + 25):
                    current_frame_screws_on_part.append((s_box, s_conf))

            n_screws = len(current_frame_screws_on_part)
            if n_screws > self.max_simultaneous:
                self.max_simultaneous = n_screws

            # 1. BẮT ĐẦU CHU KỲ TỪ IDLE / COMPLETED / VIOLATION
            if self.state in ["IDLE", "COMPLETED", "VIOLATION"] and self.part_present_streak >= 3:
                if self.in_vung_cat or part_in_cat:
                    self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
                else:
                    is_fresh_part = (n_screws <= 2)
                    is_from_lay = (self.in_vung_lay or (now - self.last_seen_lay_time < 3.0))
                    if is_fresh_part and (is_from_lay or is_moving):
                        self.state = "ASSEMBLING"
                        self.sop_status = "processing"
                        self.cycle_count += 1
                        self.cycle_start_time = now
                        self.last_cycle_duration = 0.0
                        self.has_verified_8_screws = False
                        self.inspect_streak = 0
                        self.max_simultaneous = 0
                        self.is_failed = False
                        self.violation_type = None
                        self.banner_until = 0.0
                        self.last_result_banner = None
                        self.entered_cat_zone = False
                        self.cat_release_start = 0.0
                        self.current_step_idx = 1  # Đã lấy phôi (Bước 1 OK), đang ở Bước 2: Lắp ráp 8 ốc
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ráp 8 ốc..."
                    else:
                        if not is_fresh_part:
                            self.status_msg = f"Chờ cất chi tiết cũ ({n_screws} ốc) vào khay trái"
                        else:
                            self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"

            # 2. XỬ LÝ TRONG LÚC LẮP RÁP (ASSEMBLING)
            if self.state == "ASSEMBLING":
                # Kiểm tra tư thế giơ kiểm tra (Inspection Gesture):
                # Khi giơ chi tiết ngửa lên trước camera và thấy >= 7 hoặc 8 ốc cùng lúc
                is_inspect_frame = (n_screws >= (self.target_screws - 1) and not part_in_lay and not part_in_cat)
                if is_inspect_frame:
                    self.inspect_streak += 1
                    if self.inspect_streak >= 2:  # Xác nhận ổn định >= 2-3 frame
                        self.has_verified_8_screws = True
                        self.current_step_idx = 3  # Tích hoàn thành Bước 3 (Giơ kiểm tra 8 ốc), chuyển sang Bước 4 (Đóng nẹp & Cất)
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: ✅ ĐÃ CHECK ĐỦ 8 ỐC (OK) - Đóng nẹp & Cất khay trái"
                else:
                    self.inspect_streak = 0
                    if not self.has_verified_8_screws:
                        self.current_step_idx = 1
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ráp 8 ốc (Chờ giơ kiểm tra)..."

                # Đánh dấu chi tiết vào VÙNG CẤT (vung_cat) bên trái
                if part_in_cat:
                    self.entered_cat_zone = True
                else:
                    self.entered_cat_zone = False
                    self.cat_release_start = 0.0

                # Chốt chu kỳ khi vào VÙNG CẤT và buông tay
                if self.entered_cat_zone:
                    hands_released = (not has_hand_holding) or (not hand_in_cat)
                    if hands_released:
                        if self.cat_release_start == 0.0:
                            self.cat_release_start = now
                        if now - self.cat_release_start >= 0.35:
                            self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                            self.entered_cat_zone = False
                            self.cat_release_start = 0.0
                            self.last_completed_time = now

                            if self.has_verified_8_screws:
                                # PASS: Đã giơ check đủ 8 ốc và cất vào khay trái
                                self.total_good += 1
                                self.state = "COMPLETED"
                                self.sop_status = "completed"
                                self.is_failed = False
                                self.current_step_idx = 3  # Bước 4 hoàn thành
                                self.status_msg = f"Chu kỳ #{self.cycle_count}: PASS (Đã kiểm tra đủ 8 ốc & cất khay)"
                                self.last_result_banner = (f"CHU KY #{self.cycle_count}: PASS (DU 8 OC)", True)
                                self.banner_until = now + 1.8
                            else:
                                # NG: Chưa giơ kiểm tra hoặc thiếu ốc mà đã cất vào khay trái
                                self.total_ng += 1
                                self.state = "VIOLATION"
                                self.sop_status = "violation"
                                self.is_failed = True
                                self.violation_type = f"Thiếu ốc hoặc chưa giơ kiểm tra đủ 8 ốc (Thấy {self.max_simultaneous}/8)"
                                self.status_msg = f"Chu kỳ #{self.cycle_count}: NG - Chưa kiểm tra đủ 8 ốc đã cất khay!"
                                self.last_result_banner = (f"CHU KY #{self.cycle_count}: THIEU OC / CHUA CHECK", False)
                                self.banner_until = now + 2.5
                    else:
                        self.cat_release_start = 0.0
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông tay..."

        else:
            # Chi tiết vắng mặt
            if self.part_absent_start == 0.0:
                self.part_absent_start = now
            self.part_present_streak = 0
            
            # Nếu chi tiết vừa ở trong khay cất và tay buông ra
            if self.state == "ASSEMBLING" and self.entered_cat_zone:
                if self.cat_release_start == 0.0:
                    self.cat_release_start = now
                if now - self.cat_release_start >= 0.35:
                    self.last_cycle_duration = round(now - self.cycle_start_time, 1)
                    self.entered_cat_zone = False
                    self.cat_release_start = 0.0
                    self.last_completed_time = now

                    if self.has_verified_8_screws:
                        self.total_good += 1
                        self.state = "COMPLETED"
                        self.sop_status = "completed"
                        self.is_failed = False
                        self.current_step_idx = 3
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: PASS (Đã kiểm tra đủ 8 ốc & cất khay)"
                        self.last_result_banner = (f"CHU KY #{self.cycle_count}: PASS (DU 8 OC)", True)
                        self.banner_until = now + 1.8
                    else:
                        self.total_ng += 1
                        self.state = "VIOLATION"
                        self.sop_status = "violation"
                        self.is_failed = True
                        self.violation_type = f"Thiếu ốc hoặc chưa giơ kiểm tra đủ 8 ốc (Thấy {self.max_simultaneous}/8)"
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: NG - Chưa kiểm tra đủ 8 ốc đã cất khay!"
                        self.last_result_banner = (f"CHU KY #{self.cycle_count}: THIEU OC / CHUA CHECK", False)
                        self.banner_until = now + 2.5

            elif self.state == "ASSEMBLING" and self.has_verified_8_screws:
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đã kiểm tra đủ 8 ốc - Đóng nẹp & Cất khay trái"
            elif self.state == "ASSEMBLING" and self.max_simultaneous == 0:
                if now - self.last_seen_part_time >= 2.0:
                    self.state = "IDLE"
                    self.sop_status = "idle"
                    self.current_step_idx = 0
                    self.status_msg = "Sẵn sàng (Chờ phôi mới từ khay phải)"

        self.last_part_hand_box = part_hand_box if has_hand_holding else None
        self.last_screws_on_part = current_frame_screws_on_part
        return self.get_status()

    def reset(self) -> None:
        self.state = "IDLE"
        self.sop_status = "idle"
        self.has_verified_8_screws = False
        self.inspect_streak = 0
        self.max_simultaneous = 0
        self.current_step_idx = 0
        self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"

    def get_status(self):
        now = self.last_update_time
        if now >= self.banner_until and self.state in ["COMPLETED", "VIOLATION"]:
            self.state = "IDLE"
            self.sop_status = "idle"
            self.status_msg = "Sẵn sàng (Chờ lấy phôi từ khay phải)"
            self.current_step_idx = 0
            self.has_verified_8_screws = False
            self.inspect_streak = 0
            self.max_simultaneous = 0
            self.last_result_banner = None
            self.entered_cat_zone = False
            self.cat_release_start = 0.0

        step_names = [
            "Lấy phôi chi tiết (Khay phải)",
            "Lắp ráp 8 ốc vào thân chi tiết",
            "Giơ kiểm tra đủ 8 ốc trước camera",
            "Đóng nẹp & Cất thành phẩm (Khay trái)"
        ]

        if self.state == "IDLE":
            step_idx = 0
            step_states = [False, False, False, False]
            expected_step = step_names[0]
            progress_pct = 0.0
        elif self.state == "ASSEMBLING":
            if self.has_verified_8_screws:
                step_idx = 3  # Đang ở bước 4 (Đóng nẹp & Cất)
                step_states = [True, True, True, False]
                expected_step = step_names[3]
                progress_pct = 85.0
            else:
                step_idx = 1  # Đang ở bước 2 (Lắp ốc)
                step_states = [True, False, False, False]
                expected_step = step_names[1]
                progress_pct = 40.0
        elif self.state == "COMPLETED":
            step_idx = 3
            step_states = [True, True, True, True]
            expected_step = "Hoàn tất chu kỳ"
            progress_pct = 100.0
        else: # VIOLATION
            step_idx = self.current_step_idx
            step_states = [i < step_idx for i in range(4)]
            expected_step = "Kiểm tra ốc không đạt"
            progress_pct = 40.0

        return {
            "sop_status": self.sop_status,
            "status_msg": self.status_msg,
            "expected_step": expected_step,
            "step_index": step_idx,
            "step_states": step_states,
            "progress_percent": progress_pct,
            "is_failed": self.is_failed,
            "cycle_count": self.cycle_count,
            "total_good": self.total_good,
            "total_ng": self.total_ng,
            "has_verified_8_screws": self.has_verified_8_screws,
            "state": self.state
        }

def test_video_benchmark():
    video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 20
    
    detector = HandDetector("machine_08", confidence_threshold=0.25, model_path="shared/models/yolo/laprap_8_oc.onnx")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = InspectionGestureEngine(sop_config)

    print("Running Inspection Gesture Engine on video (first 90s)...", flush=True)
    frame_idx = 0
    last_step = -1
    last_state = ""
    
    while frame_idx < 90 * fps:
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
        
        if engine.current_step_idx != last_step or engine.state != last_state or frame_idx % 60 == 0:
            print(f"[{sec:5.1f}s | F{frame_idx:04d}] State: {engine.state:11s} | StepIdx: {engine.current_step_idx} | Verified8: {engine.has_verified_8_screws} | Msg: {engine.status_msg}", flush=True)
            last_step = engine.current_step_idx
            last_state = engine.state

    cap.release()
    print(f"\nFinal Result: GOOD = {engine.total_good}, NG = {engine.total_ng}, Cycles = {engine.cycle_count}", flush=True)

if __name__ == "__main__":
    test_video_benchmark()
