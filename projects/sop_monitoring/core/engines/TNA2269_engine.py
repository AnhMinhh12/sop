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
    Engine logic cho mã sản phẩm TNA2269.
    Quy trình 2 bước:
    - Bước 1: Lấy sản phẩm ra khỏi khuôn (1 tay bất kỳ, SP xuất hiện ở bàn giữa, khuôn không còn SP).
    - Bước 2: Lấy terminal từ bàn trái đưa vào khuôn (1 tay bất kỳ).
    * Tín hiệu Bước 1 làm điểm khởi đầu và kết thúc 1 chu kỳ.
    """

    def __init__(self, sop_config: Dict[str, Any]):
        self.station_id = sop_config.get("station_id")
        self.zones = sop_config.get("zones", {})
        self.sop_steps = sop_config.get("steps", [])
        if not self.sop_steps:
            raise ValueError("ProductEngine [TNA2269]: Steps list is empty! Check TNA2269.yaml.")

        self.config = sop_config.get("config", {"w": 640, "h": 480})
        self.product_id = "TNA2269"

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
        self.cycle_start_time = 0.0
        self.start_zone_entry_time = 0.0
        self.s1_withdrawn = True
        self.step1_stage = 0
        self.product_was_in_mold = False

        # Trạng thái các bước
        self.step1_done = False
        self.step2_done = False

        # Quản lý dwell time & debouncing theo từng vùng
        self._zone_dwell_start = {}
        self._hand_touch_history = {}
        self.last_completed_zone = None
        self.last_completed_time = 0.0

        logger.info(f"ProductEngine [TNA2269]: Initialized successfully for station {self.station_id}")
        self.log_debug("--- NEW ENGINE INITIALIZED (TNA2269) ---", self.product_id)

    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
               robot_data: List[Dict] = None) -> Dict[str, Any]:
        now = time.time()
        self.last_hands = hands_data
        self.last_products = products_data if products_data is not None else []
        self.last_update_time = now

        # Active zones cho tay trái và tay phải
        active_zones = {"left": None, "right": None}
        for side in ["left", "right"]:
            for z_name in self.zones.keys():
                if self._is_in_zone(side, z_name):
                    active_zones[side] = z_name
                    break

        # Kiểm tra trạng thái rút tay khỏi Bước 1
        is_in_s1_zone = any(self._is_in_zone(side, "middle_table") or self._is_in_zone(side, "mold")
                            for side in ["left", "right"])
        if not is_in_s1_zone:
            self.s1_withdrawn = True

        # Xử lý delay kết thúc chu kỳ (sau khi hoàn thành đủ cả 2 bước): Hiển thị thông báo trong 3.5 giây
        if self._completed_at > 0:
            if now - self._completed_at < 3.5:
                return self._get_status_result(active_zones, "completed")
            else:
                self._completed_at = 0.0
                self.reset(now=now)

        # Xử lý trạng thái lỗi vi phạm
        if self.is_failed:
            # Nếu tay quay lại vùng Bước 2 (Khuôn/Lấy SP ra), tự động reset và bắt đầu chu kỳ mới
            hand_in_mold = any(self._is_in_zone(side, "mold") for side in ["left", "right"])
            if hand_in_mold:
                self.log_debug("Tự động reset khi tay quay lại vùng Bước 2 (Khuôn) sau vi phạm.", self.product_id)
                self.reset(now=now)
            else:
                return self._get_status_result(active_zones, "violation", violation_type=self.violation_type)

        max_cycle_time = self.config.get("max_cycle_time_sec", 45.0)

        # ----------------------------------------------------
        # FSM BƯỚC 2: LẤY SẢN PHẨM RA KHỎI KHUÔN (Khởi đầu & Kết thúc chu kỳ)
        # Khuôn rỗng (0) -> Có SP (1) -> Tay vào (2) -> LẤY SP RA (HOÀN THÀNH B2)
        # ----------------------------------------------------
        hand_in_mold = any(self._is_in_zone(side, "mold") for side in ["left", "right"])
        prod_in_mold = self._is_product_in_zone("mold")

        if self.step1_stage == 0:
            if prod_in_mold:
                self.step1_stage = 1
        elif self.step1_stage == 1:
            if hand_in_mold:
                self.step1_stage = 2
        elif self.step1_stage == 2:
            if not prod_in_mold:
                if self.start_zone_entry_time == 0.0:
                    self.start_zone_entry_time = now
                elif now - self.start_zone_entry_time >= 0.2:
                    # BƯỚC 2 HOÀN THÀNH CHÍNH THỨC!
                    self.step1_stage = 0

                    violation_res = None
                    # Nếu chu kỳ cũ chưa làm Bước 1 (Lấy terminal bàn trái vào khuôn) mà đã lấy SP ra -> Báo lỗi bỏ bước!
                    if not self.waiting_for_start and not self.step1_done:
                        missing_name = "Lấy terminal bàn trái vào khuôn"
                        self.log_debug(f"VIOLATION: Bỏ qua bước '{missing_name}' ở chu kỳ cũ! Đã sang chu kỳ mới.", self.product_id)
                        self.is_failed = True
                        self.violation_type = "skipped_step"
                        self.failed_step_idx = 1
                        violation_res = self._get_status_result(active_zones, "violation", violation_type="skipped_step")
                        violation_res["expected_step"] = f"Chưa hoàn thành: {missing_name}"

                    # BẮT ĐẦU CHU KỲ MỚI TỪ BƯỚC 2 (Lấy sản phẩm ra khỏi khuôn)
                    curr_cycle = self.cycle_count + 1
                    self.reset(now=now)
                    self.cycle_count = curr_cycle
                    self.waiting_for_start = False
                    self.cycle_start_time = now
                    self.step_start_time = now
                    self.step2_done = True
                    self.current_step_idx = 2
                    self.start_zone_entry_time = 0.0

                    self.log_debug(f"CYCLE {self.cycle_count} STARTED: Step 2 completed (Lấy SP ra khỏi khuôn).", self.product_id)

                    if violation_res:
                        return violation_res
                    else:
                        return self._get_status_result(active_zones, "processing")
            else:
                self.start_zone_entry_time = 0.0

        if self.waiting_for_start:
            self.status_msg = "Sẵn sàng (Chờ lấy sản phẩm ra khỏi khuôn)"
            return self._get_status_result(active_zones, "idle")

        # Kiểm tra timeout chu kỳ khi đang trong chu kỳ
        if now - self.cycle_start_time > max_cycle_time:
            self.is_failed = True
            self.violation_type = "timeout"
            self.failed_step_idx = self.current_step_idx
            self.log_debug(f"VIOLATION: Cycle Timeout (> {max_cycle_time}s)", self.product_id)
            return self._get_status_result(active_zones, "violation", violation_type="timeout")

        # ----------------------------------------------------
        # BƯỚC 1: LẤY TERMINAL BÀN TRÁI VÀO KHUÔN
        # ----------------------------------------------------
        if not self.step1_done:
            for side in ["left", "right"]:
                if self._is_in_zone(side, "left_table"):
                    self._hand_touch_history[f"step1_{side}"] = now

                touch_time = self._hand_touch_history.get(f"step1_{side}", 0.0)
                if touch_time > 0 and (now - touch_time <= 5.0):
                    if self._is_in_zone(side, "mold"):
                        dwell_key = f"step1_dwell_{side}"
                        if dwell_key not in self._zone_dwell_start or self._zone_dwell_start[dwell_key] == 0.0:
                            self._zone_dwell_start[dwell_key] = now
                        elif now - self._zone_dwell_start[dwell_key] >= 0.2:
                            self.step1_done = True
                            self.step_start_time = now
                            self.current_step_idx = 1
                            self.log_debug(f"STEP 1 COMPLETED (Lấy terminal bàn trái vào khuôn).", self.product_id)
                            break
                    else:
                        self._zone_dwell_start[f"step1_{side}"] = 0.0

        # Kiểm tra hoàn thành cả 2 bước
        if self.step1_done and self.step2_done:
            if self._completed_at == 0.0:
                self._completed_at = now
                self.log_debug(f"Chu kỳ {self.cycle_count} HOÀN THÀNH THÀNH CÔNG (Xong đủ 2 bước)!", self.product_id)
            self.status_msg = "🎉 HOÀN THÀNH CHU KỲ THÀNH CÔNG!"
            return self._get_status_result(active_zones, "completed")
        elif self.step2_done:
            self.status_msg = "Đã lấy SP ra khỏi khuôn. Đang chờ: Lấy terminal bàn trái vào khuôn"
        else:
            self.status_msg = "Đang thực hiện: B1 (Lấy terminal bàn trái vào khuôn)"

        return self._get_status_result(active_zones, "processing")

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
        self.step1_done = False
        self.step2_done = False
        self._zone_dwell_start = {}
        self._hand_touch_history = {}
        self.s1_withdrawn = True
        self.step1_stage = 0
        self.product_was_in_mold = False
        self.status_msg = "Sẵn sàng"
        self.log_debug("ENGINE RESET (TNA2269)", self.product_id)

    def get_status(self) -> Dict[str, Any]:
        return self._get_status_result({"left": None, "right": None}, "idle")

    # --- Internal Helpers ---
    def _get_status_result(self, active_zones: Dict, status: str, violation_type: str = None) -> Dict:
        step_list = [s["step_name"] for s in self.sop_steps]
        
        # Calculate current step name & overall progress (2 steps total)
        completed_count = (1 if self.step1_done else 0) + (1 if self.step2_done else 0)
        progress_pct = (completed_count / 2.0) * 100.0

        if completed_count == 2:
            cur_step_name = "CHỜ TÍN HIỆU BƯỚC 2 ĐỂ KẾT THÚC CHU KỲ"
        elif self.step2_done:
            cur_step_name = "B1 (Lấy terminal bàn trái vào khuôn)"
        else:
            cur_step_name = self.sop_steps[1]["step_name"] if len(self.sop_steps) > 1 else "Lấy sản phẩm ra khỏi khuôn"

        detected_parts = []
        for side, zone in active_zones.items():
            if zone:
                detected_parts.append(f"{side[0].upper()}:{zone}")
        detected_label = ", ".join(detected_parts) if detected_parts else "Idle"

        max_cycle_time = self.config.get("max_cycle_time_sec", 45.0)
        if self.waiting_for_start:
            cycle_time_left = max_cycle_time
        elif self.is_failed:
            cycle_time_left = 0.0
        else:
            cycle_time_left = max(0.0, max_cycle_time - (self.last_update_time - self.cycle_start_time))

        res = {
            "sop_status": status,
            "status_msg": self.status_msg,
            "expected_step": cur_step_name,
            "detected_label": detected_label,
            "step_index": self.current_step_idx,
            "step_states": [self.step1_done, self.step2_done],
            "progress_percent": progress_pct,
            "is_failed": self.is_failed,
            "failed_step_idx": self.failed_step_idx,
            "cycle_count": self.cycle_count,
            "hands_info": active_zones,
            "step_list": step_list,
            "cycle_time_left": cycle_time_left,
            "max_cycle_time": max_cycle_time
        }

        if self.is_failed:
            if violation_type and not self.violation_type:
                self.violation_type = violation_type
            if not self.violation_notified:
                self.violation_notified = True
                status = "violation"
            else:
                status = "failed_silent"

            msg = "VI PHẠM - CHỜ QUAY LẠI BƯỚC 1"
            if self.violation_type == "timeout":
                msg = "VI PHẠM - QUÁ THỜI GIAN CHỜ CHU KỲ"

            elapsed = (self.last_update_time - self.cycle_start_time) if self.cycle_start_time > 0 else max_cycle_time
            dur_val = round(elapsed, 1)

            res.update({
                "detected_label": msg,
                "sop_status": status,
                "violation_type": self.violation_type or "unknown",
                "step_index": 0,
                "progress_percent": 0,
                "cycle_time_left": 0.0,
                "duration": dur_val
            })

        return res

    def _is_product_in_zone(self, zone_name: str) -> bool:
        if not hasattr(self, 'last_products') or not self.last_products:
            return False

        zone_pts = self.zones.get(zone_name)
        if not zone_pts:
            return False

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
                [bbox[0] / w, bbox[1] / h],
                [bbox[2] / w, bbox[1] / h],
                [bbox[0] / w, bbox[3] / h],
                [bbox[2] / w, bbox[3] / h]
            ]
            if any(cv2.pointPolygonTest(poly, (pt[0], pt[1]), False) >= 0 for pt in points):
                return True
        return False

    def _is_in_zone(self, side: str, zone_name: str, centroid_only: bool = False) -> bool:
        zone_pts = self.zones.get(zone_name)
        if not zone_pts:
            return False

        w, h = self.config.get("w", 640), self.config.get("h", 480)
        for hand in self.last_hands:
            if hand["label"].lower() != side:
                continue
            if self._check_bbox_polygon_intersection(hand["bbox"], zone_pts, hand["centroid"], w, h, centroid_only):
                return True
        return False
