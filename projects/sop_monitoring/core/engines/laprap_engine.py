import time
import math
import logging
import os
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
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

        # Cấu hình chống ốc rời / ốc lăn & Visible-Empty Reset (Hướng 1)
        self.slot_confirm_sec = float(sop_config.get("slot_confirm_sec", 0.42))
        self.slot_confirm_frames = int(sop_config.get("slot_confirm_frames", 3))
        self.slot_grace_sec = float(sop_config.get("slot_grace_sec", 0.35))
        self.slot_clear_sec = float(sop_config.get("slot_clear_sec", 0.85))
        self.slot_clear_moving_sec = float(sop_config.get("slot_clear_moving_sec", 1.25))
        self.slot_clear_frames = int(sop_config.get("slot_clear_frames", 4))
        self.max_rel_drift = float(sop_config.get("max_rel_drift", 0.12))
        
        # State machine
        self.state = "IDLE"  # "IDLE", "ASSEMBLING", "COMPLETED", "VIOLATION"
        self.cycle_count = 0
        self.total_good = 0
        self.total_ng = 0
        
        # Dữ liệu chu kỳ hiện tại
        self._reset_slot_tracking()
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

    def _reset_slot_tracking(self) -> None:
        """Khởi tạo hoặc xóa toàn bộ trạng thái bám vết 8 vị trí ốc cho chu kỳ mới."""
        self.slots = [False] * self.target_screws
        self.slot_hits = [0] * self.target_screws
        self.slot_seen_since = [0.0] * self.target_screws
        self.slot_last_seen = [0.0] * self.target_screws
        self.slot_last_rel: List[Optional[Tuple[float, float]]] = [None] * self.target_screws
        self.slot_missing_since = [0.0] * self.target_screws
        self.slot_missing_frames = [0] * self.target_screws
        self.has_completed_screws = False
        self.max_simultaneous = 0
        self.loose_pile_detected = False

    def _get_slot_pixel_center(self, slot_idx: int, part_box: List[float]) -> Tuple[float, float]:
        """Ước lượng tọa độ tâm (sx, sy) của vị trí lỗ ốc slot_idx trên bounding box sản phẩm."""
        px1, py1, px2, py2 = part_box
        pw = max(1.0, float(px2 - px1))
        ph = max(1.0, float(py2 - py1))
        tier_centers_long = (0.16, 0.38, 0.58, 0.84)
        tier = min(3, max(0, slot_idx // 2))
        c_long = tier_centers_long[tier]
        c_lat = 0.72 if (slot_idx % 2 == 1) else 0.30
        if ph >= pw:
            return (px1 + c_lat * pw, py1 + c_long * ph)
        return (px1 + c_long * pw, py1 + c_lat * ph)

    def _is_slot_occluded_by_hand(self, slot_idx: int, part_box: List[float],
                                  hands_data: List[Dict]) -> bool:
        """Kiểm tra vùng của slot_idx có đang bị bàn tay công nhân che khuất hay không."""
        if not hands_data:
            return False
        px1, py1, px2, py2 = part_box
        pw = max(1.0, float(px2 - px1))
        ph = max(1.0, float(py2 - py1))
        sx, sy = self._get_slot_pixel_center(slot_idx, part_box)
        radius = max(24.0, 0.16 * min(pw, ph))
        rx1, ry1, rx2, ry2 = sx - radius, sy - radius, sx + radius, sy + radius

        for h in hands_data:
            hb = h.get("bbox")
            if not hb:
                continue
            if max(rx1, hb[0]) < min(rx2, hb[2]) and max(ry1, hb[1]) < min(ry2, hb[3]):
                return True
        return False

    def _assign_screws_to_slots(self, part_box: List[float], screws: List[tuple]) -> Tuple[
        List[tuple], Dict[int, Tuple[float, float]], bool, set, int, Tuple[int, int, int, float]
    ]:
        """
        Gom cụm và ánh xạ các ốc phát hiện trên sản phẩm vào 8 vị trí slot theo cấu trúc 3 cụm thực tế:
          - Cụm Đầu (Tầng 0 - 2 lỗ): rel_long <= 0.28
          - Cụm Giữa (Tầng 1 & 2 - 4 lỗ): 0.28 < rel_long <= 0.65
          - Cụm Đuôi (Tầng 3 - 2 lỗ): rel_long > 0.65
        Đồng thời lọc ốc trùng bbox, cụm ốc rời dồn đống (loose pile) và vùng tràn ốc.
        """
        px1, py1, px2, py2 = part_box
        pw = max(1.0, float(px2 - px1))
        ph = max(1.0, float(py2 - py1))

        # 1. Lọc ốc nằm trong phạm vi sản phẩm (margin 10px) và khử duplicate detection gần nhau (< 12px)
        raw_on_part = []
        for s_box, s_conf in screws:
            scx = (s_box[0] + s_box[2]) / 2.0
            scy = (s_box[1] + s_box[3]) / 2.0
            if (px1 - 10) <= scx <= (px2 + 10) and (py1 - 10) <= scy <= (py2 + 10):
                raw_on_part.append((s_box, s_conf, scx, scy))

        raw_on_part.sort(key=lambda item: item[1], reverse=True)
        dedup_on_part = []
        for item in raw_on_part:
            _, _, cx, cy = item
            if any(math.hypot(cx - k[2], cy - k[3]) < 12.0 for k in dedup_on_part):
                continue
            dedup_on_part.append(item)

        top_screws: List[tuple] = []
        mid_screws: List[tuple] = []
        bot_screws: List[tuple] = []
        all_rel_long: List[float] = []
        all_rel_lat: List[float] = []

        for s_box, s_conf, scx, scy in dedup_on_part:
            if ph >= pw:
                rel_long = (scy - py1) / ph
                rel_lat = (scx - px1) / pw
            else:
                rel_long = (scx - px1) / pw
                rel_lat = (scy - py1) / ph

            rel_long = min(0.999, max(0.0, rel_long))
            rel_lat = min(0.999, max(0.0, rel_lat))
            all_rel_long.append(rel_long)
            all_rel_lat.append(rel_lat)

            item = (s_box, s_conf, rel_lat, rel_long)
            if rel_long <= 0.28:
                top_screws.append(item)
            elif rel_long <= 0.65:
                mid_screws.append(item)
            else:
                bot_screws.append(item)

        visible_screws = len(dedup_on_part)
        span_long = (max(all_rel_long) - min(all_rel_long)) if all_rel_long else 0.0
        span_lat = (max(all_rel_lat) - min(all_rel_lat)) if all_rel_lat else 0.0

        # Kiểm tra cụm ốc rời dồn đống (Loose Pile) toàn thân trước khi lọc nhiễu vùng
        has_loose_pile = False
        if visible_screws >= 5 and span_long < 0.35:
            has_loose_pile = True
        elif visible_screws >= 4 and span_long < 0.12 and span_lat < 0.15:
            has_loose_pile = True

        blocked_tiers = set()
        if not has_loose_pile:
            if len(top_screws) >= 4:
                blocked_tiers.add(0)
                has_loose_pile = True
            elif len(top_screws) == 3:
                # Nếu có 1 nhiễu ngón tay trắng ở sát mép trên (< 0.09) hoặc conf < 0.55 khi thân trải dài -> giữ 2 con chuẩn
                valid_top = [x for x in top_screws if x[3] >= 0.09 and x[1] >= 0.52]
                if len(valid_top) == 2 and span_long >= 0.40:
                    top_screws = valid_top
                else:
                    blocked_tiers.add(0)

            if len(bot_screws) >= 4:
                blocked_tiers.add(3)
                has_loose_pile = True
            elif len(bot_screws) == 3:
                valid_bot = [x for x in bot_screws if x[3] <= 0.91 and x[1] >= 0.52]
                if len(valid_bot) == 2 and span_long >= 0.40:
                    bot_screws = valid_bot
                else:
                    blocked_tiers.add(3)

            if len(mid_screws) >= 6:
                blocked_tiers.update({1, 2})
                has_loose_pile = True
            elif len(mid_screws) == 5:
                # Lọc 1 nhiễu conf thấp (< 0.48) hoặc lệch rìa ngoài cụm giữa khi toàn thân trải dài
                valid_mid = sorted(
                    [x for x in mid_screws if x[1] >= 0.48 and 0.34 <= x[3] <= 0.55],
                    key=lambda x: x[1],
                    reverse=True,
                )
                if len(valid_mid) >= 4 and span_long >= 0.40:
                    mid_screws = valid_mid[:4]
                else:
                    blocked_tiers.update({1, 2})

        # Phân cụm giữa (4 lỗ) vào Tầng 1 và Tầng 2 một cách linh hoạt theo cấu trúc 2x2
        tier_screws: Dict[int, List[tuple]] = {0: top_screws, 1: [], 2: [], 3: bot_screws}
        mid_sorted = sorted(mid_screws, key=lambda x: x[3])
        if len(mid_sorted) == 4:
            tier_screws[1] = mid_sorted[:2]
            tier_screws[2] = mid_sorted[2:]
        elif len(mid_sorted) == 3:
            t1 = [x for x in mid_sorted if x[3] <= 0.46]
            t2 = [x for x in mid_sorted if x[3] > 0.46]
            if len(t1) > 2:
                t2.insert(0, t1.pop())
            elif len(t2) > 2:
                t1.append(t2.pop(0))
            tier_screws[1] = t1
            tier_screws[2] = t2
        elif len(mid_sorted) >= 5:
            tier_screws[1] = mid_sorted[:2]
            tier_screws[2] = mid_sorted[2:]
        else:
            for item in mid_sorted:
                if item[3] <= 0.46:
                    tier_screws[1].append(item)
                else:
                    tier_screws[2].append(item)

        current_frame_screws_on_part: List[tuple] = []
        observed_slot_coords: Dict[int, Tuple[float, float]] = {}

        for t in range(4):
            s_list = tier_screws[t]
            slot_base = t * 2

            if len(s_list) >= 2:
                s_list.sort(key=lambda item: item[2])
                first, second = s_list[0], s_list[1]
                current_frame_screws_on_part.append((first[0], first[1], slot_base))
                current_frame_screws_on_part.append((second[0], second[1], slot_base + 1))
                observed_slot_coords[slot_base] = (first[3], first[2])
                observed_slot_coords[slot_base + 1] = (second[3], second[2])
                for extra in s_list[2:]:
                    current_frame_screws_on_part.append((extra[0], extra[1], slot_base + 1))
            elif len(s_list) == 1:
                s0 = s_list[0]
                assigned = slot_base if s0[2] < 0.65 else (slot_base + 1)
                current_frame_screws_on_part.append((s0[0], s0[1], assigned))
                observed_slot_coords[assigned] = (s0[3], s0[2])

        cluster_info = (len(top_screws), len(mid_screws), len(bot_screws), span_long)
        return current_frame_screws_on_part, observed_slot_coords, has_loose_pile, blocked_tiers, visible_screws, cluster_info

    def _update_slot_states(self, now: float, part_box: List[float], hands_data: List[Dict],
                            observed_slot_coords: Dict[int, Tuple[float, float]],
                            has_loose_pile: bool, blocked_tiers: set,
                            visible_screws: int, is_moving: bool, w_frame: int,
                            cluster_info: Tuple[int, int, int, float]) -> None:
        """
        Cập nhật 8 slot theo 3 lớp bảo vệ (Hướng 1):
          1. Chặn cụm ốc rời (has_loose_pile / blocked_tiers).
          2. Neo giữ thời gian + chống trôi/lăn (dwell >= slot_confirm_sec & drift <= max_rel_drift).
          3. Visible-Empty Reset: Khi cụm đó hoặc toàn bộ lòng máng đang mở rõ và không bị tay che
             mà slot trống liên tiếp >= clear_sec -> Xóa slot.
        """
        pw = max(1.0, float(part_box[2] - part_box[0]))
        ph = max(1.0, float(part_box[3] - part_box[1]))
        can_see_interior = (visible_screws >= 1) and (min(pw, ph) >= max(55.0, 0.045 * float(w_frame)))
        n_top, n_mid, n_bot, span_long = cluster_info
        is_full_view = (visible_screws >= 3 and span_long >= 0.48)

        for idx in range(self.target_screws):
            tier = idx // 2
            if idx in observed_slot_coords:
                rel_long, rel_lat = observed_slot_coords[idx]
                self.slot_missing_since[idx] = 0.0
                self.slot_missing_frames[idx] = 0

                if not self.slots[idx]:
                    # Chặn xác nhận mới nếu đang phát hiện cụm ốc rời hoặc vùng bị tràn ốc
                    if has_loose_pile or (tier in blocked_tiers):
                        self.slot_hits[idx] = 0
                        self.slot_seen_since[idx] = 0.0
                        self.slot_last_rel[idx] = None
                        continue

                    prev_rel = self.slot_last_rel[idx]
                    if prev_rel is not None:
                        # Ốc rời chỉ có thể lăn dọc theo lòng máng -> kiểm tra độ trượt dọc rel_long
                        # (không dùng rel_lat vì khi nghiêng chéo phôi, bounding box X/Y làm rel_lat dao động lớn)
                        long_drift = abs(rel_long - prev_rel[0])
                        if long_drift > self.max_rel_drift:
                            # Ốc đang trượt/lăn dọc qua ô -> reset bộ đếm thời gian đứng yên
                            self.slot_seen_since[idx] = now
                            self.slot_hits[idx] = 1
                        else:
                            if self.slot_seen_since[idx] == 0.0:
                                self.slot_seen_since[idx] = now
                            self.slot_hits[idx] += 1
                    else:
                        self.slot_seen_since[idx] = now
                        self.slot_hits[idx] = 1

                    self.slot_last_seen[idx] = now
                    self.slot_last_rel[idx] = (rel_long, rel_lat)

                    if ((now - self.slot_seen_since[idx]) >= self.slot_confirm_sec
                            and self.slot_hits[idx] >= self.slot_confirm_frames):
                        self.slots[idx] = True
                else:
                    self.slot_last_seen[idx] = now
                    self.slot_last_rel[idx] = (rel_long, rel_lat)
            else:
                if not self.slots[idx]:
                    if self.slot_last_seen[idx] > 0.0 and (now - self.slot_last_seen[idx]) > self.slot_grace_sec:
                        self.slot_seen_since[idx] = 0.0
                        self.slot_hits[idx] = 0
                        self.slot_last_rel[idx] = None
                else:
                    # Chỉ xóa slot nếu chính cụm đó đang lộ rõ hoặc đang mở toàn bộ lòng máng (chống xóa oan khi nghiêng lắp đầu kia)
                    if idx in (0, 1):
                        view_ok = (n_top >= 1) or is_full_view
                    elif idx in (2, 3, 4, 5):
                        view_ok = (n_mid >= 1) or (n_top >= 1 and n_bot >= 1) or is_full_view
                    else:
                        view_ok = (n_bot >= 1) or is_full_view

                    occluded = self._is_slot_occluded_by_hand(idx, part_box, hands_data)
                    if can_see_interior and view_ok and not occluded:
                        if self.slot_missing_since[idx] == 0.0:
                            self.slot_missing_since[idx] = now
                        self.slot_missing_frames[idx] += 1
                        clear_sec = self.slot_clear_moving_sec if is_moving else self.slot_clear_sec
                        if ((now - self.slot_missing_since[idx]) >= clear_sec
                                and self.slot_missing_frames[idx] >= self.slot_clear_frames):
                            self.slots[idx] = False
                            self.slot_hits[idx] = 0
                            self.slot_seen_since[idx] = 0.0
                            self.slot_last_rel[idx] = None
                            self.slot_missing_since[idx] = 0.0
                            self.slot_missing_frames[idx] = 0
                            self.has_completed_screws = False
                            logger.info(f"ProductEngine [laprap]: Visible-Empty Reset cleared slot #{idx + 1}.")
                    else:
                        self.slot_missing_since[idx] = 0.0
                        self.slot_missing_frames[idx] = 0

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
               robot_data: List[Dict] = None, timestamp: Optional[float] = None) -> Dict[str, Any]:
        now = timestamp if timestamp is not None else time.time()
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

            (
                current_frame_screws_on_part,
                observed_slot_coords,
                has_loose_pile,
                blocked_tiers,
                visible_screws,
                cluster_info,
            ) = self._assign_screws_to_slots(part_hand_box, screws)

            self.loose_pile_detected = has_loose_pile
            has_all_screws = (self.has_completed_screws or sum(self.slots) >= self.target_screws)

            # Đánh dấu chi tiết vào VÙNG CẤT (vung_cat) bên trái
            # CHỈ kích hoạt khi chính bounding box của chi tiết (part_hand) nằm trong khay cất
            if self.state == "ASSEMBLING":
                if part_in_cat:
                    if has_all_screws:
                        self.entered_cat_zone = True
                    elif sum(self.slots) > 0 or self.loose_pile_detected or visible_screws > 0:
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
                        curr_count = sum(self.slots)
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
                        self._reset_slot_tracking()
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

            # Cập nhật trạng thái 8 slots theo Hướng 1 (Dwell >= 0.65s, chống ốc lăn/cụm ốc rời, Visible-Empty Reset)
            if self.state == "ASSEMBLING":
                self._update_slot_states(
                    now=now,
                    part_box=part_hand_box,
                    hands_data=hands_data,
                    observed_slot_coords=observed_slot_coords,
                    has_loose_pile=has_loose_pile,
                    blocked_tiers=blocked_tiers,
                    visible_screws=visible_screws,
                    is_moving=is_moving,
                    w_frame=w_frame,
                    cluster_info=cluster_info,
                )

            self.last_screws_on_part = current_frame_screws_on_part
            
            # Chỉ lưu thống kê tham khảo, KHÔNG dùng để đếm tiến độ hoặc chốt PASS
            n_sim = len(current_frame_screws_on_part)
            if not has_loose_pile and n_sim > self.max_simultaneous:
                self.max_simultaneous = n_sim
                
            if self.state == "ASSEMBLING":
                curr_count = sum(self.slots)
                self.has_completed_screws = (curr_count >= self.target_screws)
                
                if curr_count < 2:
                    self.current_step_idx = 1   # Bước 2: Lắp ốc vị trí 1 - 2
                elif curr_count < 4:
                    self.current_step_idx = 2   # Bước 3: Lắp ốc vị trí 3 - 4
                elif curr_count < 6:
                    self.current_step_idx = 3   # Bước 4: Lắp ốc vị trí 5 - 6
                elif curr_count < 8:
                    self.current_step_idx = 4   # Bước 5: Lắp ốc vị trí 7 - 8
                else:
                    self.current_step_idx = 5   # Bước 6: Hoàn tất & Cất chi tiết

                if curr_count >= self.target_screws:
                    if self.entered_cat_zone:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang cất khay trái - Chờ buông 2 tay..."
                    else:
                        self.status_msg = f"Chu kỳ #{self.cycle_count}: Đủ 8 ốc - Đóng nẹp & Đưa sang khay trái"
                elif has_loose_pile:
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Cảnh báo cụm ốc rời! ({curr_count}/{self.target_screws})"
                else:
                    self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang lắp ốc ({curr_count}/{self.target_screws})"
                
        else:
            # --- TRƯỜNG HỢP VẮNG BÓNG CHI TIẾT TRÊN TAY (ABSENT) ---
            if self.part_absent_start == 0.0:
                self.part_absent_start = now
            self.part_present_streak = 0
            self.last_screws_on_part = []
            self.loose_pile_detected = False
            
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
                    curr_count = sum(self.slots)
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
            elif self.state == "ASSEMBLING" and sum(self.slots) == 0:
                if now - self.last_seen_part_time >= 1.5:
                    self.state = "IDLE"
                    self.sop_status = "idle"
                    self.is_failed = False
                    self.violation_type = None
                    self.current_step_idx = 0
                    self.status_msg = "Sẵn sàng (Chờ phôi mới từ khay phải)"
                    self.banner_until = 0.0
                    self.last_result_banner = None
                    self._reset_slot_tracking()
                    self.entered_cat_zone = False
                    self.entered_cat_incomplete = False
                    self.cat_release_start = 0.0
                    logger.info(f"ProductEngine [laprap]: Cycle #{self.cycle_count} reset to IDLE (0 screws).")
                    
            # TRƯỜNG HỢP D: 1-7 ỐC ĐANG LẮP MÀ TẠM DỪNG (NGOẢNH NÓI CHUYỆN, ĐẶT XUỐNG BÀN, LẤY ỐC):
            # TUYỆT ĐỐI KHÔNG BÁO LỖI (KHÔNG TÍNH NG), GIỮ NGUYÊN CHU KỲ VÀ SLOTS ĐỂ CÔNG NHÂN QUAY LẠI LẮP TIẾP!
            elif self.state == "ASSEMBLING" and (1 <= sum(self.slots) < self.target_screws):
                curr_count = sum(self.slots)
                self.status_msg = f"Chu kỳ #{self.cycle_count}: Đang tạm dừng ({curr_count}/{self.target_screws} ốc)"
                    
        # Kiểm tra quá thời gian tối đa chu kỳ (Timeout)
        if self.state == "ASSEMBLING" and (now - self.cycle_start_time > self.max_cycle_time):
            final_screw_count = sum(self.slots)
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
                self._reset_slot_tracking()
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
        screw_count = sum(self.slots)
        
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
            self._reset_slot_tracking()
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
        self._reset_slot_tracking()
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
            elif self.loose_pile_detected:
                state_color = (0, 165, 255)
                state_str = f"MAY IN-HOT-LAPRAP | CHU KY #{self.cycle_count}: CANH BAO CUM OC ROI!"
            elif now - self.last_seen_part_time >= 2.0 and sum(self.slots) > 0:
                state_color = (255, 180, 50)
                curr_count = sum(self.slots)
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
        screw_count = sum(self.slots)
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
