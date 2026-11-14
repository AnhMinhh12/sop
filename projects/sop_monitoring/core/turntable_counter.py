import time
import logging
import cv2
import numpy as np
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class TurntableCounter:
    """
    Module chung chuyên xử lý phát hiện và đếm sản lượng mâm xoay 180 độ (MOG2 + FSM).
    Hỗ trợ 2 chế độ đếm:
    1. Đếm theo lượt xoay cơ bản (spins_per_product: 1 hoặc 2)
    2. Đếm kết hợp xác thực sản phẩm nhô lên ở khung nhỏ (require_product_popup=True, dùng cho Máy 4 - TK_1A00-V0022).
       -> Sau khi mâm xoay dừng, theo dõi khung nhỏ (product_popup) xem sản phẩm nhựa đen có nhô lên không.
       -> Khi phát hiện sản phẩm nhô lên trong khung nhỏ thì mới chính thức chốt +1 sản phẩm!
    """

    def __init__(
        self,
        station_id: str = "04",
        product_id: str = "TK_1A00-V0022",
        products_per_cycle: int = 1,
        spins_per_product: int = 1,
        require_product_popup: bool = True,
        debounce_sec: float = 3.5,
        wait_spin_timeout_sec: float = 10.0,
        wait_popup_timeout_sec: float = 8.0,
        min_spin_duration: float = 0.7,
        max_spin_duration: float = 4.5,
        max_allowed_spin_sec: float = 5.5,
        min_spin_frames: int = 6,
        motion_threshold_base: int = 1500,
        peak_motion_base: int = 4000,
        auto_spin_trigger_base: int = 5000,
        popup_motion_threshold_base: int = 600
    ):
        self.station_id = station_id
        self.product_id = product_id
        self.products_per_cycle = products_per_cycle
        self.spins_per_product = spins_per_product
        self.require_product_popup = require_product_popup
        self.debounce_sec = debounce_sec
        self.wait_spin_timeout_sec = wait_spin_timeout_sec
        self.wait_popup_timeout_sec = wait_popup_timeout_sec
        self.min_spin_duration = min_spin_duration
        self.max_spin_duration = max_spin_duration
        self.max_allowed_spin_sec = max_allowed_spin_sec
        self.min_spin_frames = min_spin_frames
        self.motion_threshold_base = motion_threshold_base
        self.peak_motion_base = peak_motion_base
        self.auto_spin_trigger_base = auto_spin_trigger_base
        self.popup_motion_threshold_base = popup_motion_threshold_base

        # MOG2 Subtractor cho mâm xoay và cho khung nhỏ
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=20, varThreshold=50, detectShadows=False)
        self.fgbg_popup = cv2.createBackgroundSubtractorMOG2(history=25, varThreshold=45, detectShadows=False)

        # FSM State:
        # IDLE -> TRIGGERED_WAIT_SPIN -> SPINNING -> WAIT_PRODUCT_POPUP -> COOLDOWN_LOCK -> ERROR_SPIN_ANOMALY
        self.state = 'IDLE'
        self.trigger_time = 0.0
        self.spin_start_time = 0.0
        self.spin_finish_time = 0.0
        self.spin_frames = 0
        self.spin_gap_frames = 0
        self.peak_motion = 0
        self.last_count_time = 0.0
        self.last_motion_score = 0
        self.last_popup_score = 0
        self.is_moving = False
        self.is_turntable_moving = False
        self.is_popup_detected = False

        # Thống kê sản lượng và lượt xoay
        self.current_date = time.strftime('%Y-%m-%d')
        self.total_products = 0
        self.cycle_rotations = 0
        self.spins_in_current_product = 0

        # Sự kiện đếm sản phẩm vừa hoàn thành
        self.pending_product_event: Optional[Dict[str, Any]] = None

        # Cờ vi phạm an toàn
        self.safety_violation: Optional[str] = None

    def trigger_button_pressed(self, curr_time: float) -> None:
        """Kích hoạt từ nút bấm bên ngoài."""
        if (curr_time - self.last_count_time) > self.debounce_sec:
            if self.state in ['IDLE', 'COOLDOWN_LOCK']:
                self.state = 'TRIGGERED_WAIT_SPIN'
                self.trigger_time = curr_time
                self.spin_frames = 0
                self.spin_gap_frames = 0
                self.peak_motion = 0

    def update(
        self,
        frame: np.ndarray,
        curr_time: float,
        turntable_poly_normalized: List[List[float]],
        popup_poly_normalized: Optional[List[List[float]]] = None,
        is_button_triggered: bool = False,
        is_hand_in_mold: bool = False
    ) -> Dict[str, Any]:
        """
        Cập nhật chuyển động mâm xoay và theo dõi khung nhỏ sản phẩm nhô lên từng frame.
        """
        if frame is None or not turntable_poly_normalized:
            return self.get_status()

        # Reset chỉ số ngày mới nếu qua 0h
        today = time.strftime('%Y-%m-%d')
        if hasattr(self, 'current_date') and today != self.current_date:
            self.current_date = today
            self.total_products = 0
            self.cycle_rotations = 0
            self.spins_in_current_product = 0

        h, w = frame.shape[:2]
        scale_factor = (w * h) / (640 * 360)

        # 1. Đo chuyển động mâm xoay lớn (mold)
        poly_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in turntable_poly_normalized], np.int32)
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [poly_pts], 255)
        roi = cv2.bitwise_and(frame, frame, mask=mask)
        fgmask = self.fgbg.apply(roi)
        motion_score = cv2.countNonZero(fgmask)
        self.last_motion_score = motion_score

        motion_threshold = int(self.motion_threshold_base * scale_factor)
        self.is_moving = motion_score > motion_threshold
        self.is_turntable_moving = self.is_moving

        # 2. Đo chuyển động ở khung nhỏ (popup_poly) nếu có
        popup_motion_score = 0
        if popup_poly_normalized:
            pop_pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in popup_poly_normalized], np.int32)
            mask_pop = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_pop, [pop_pts], 255)
            roi_pop = cv2.bitwise_and(frame, frame, mask=mask_pop)
            fg_pop = self.fgbg_popup.apply(roi_pop)
            popup_motion_score = cv2.countNonZero(fg_pop)
            self.last_popup_score = popup_motion_score

        popup_threshold = int(self.popup_motion_threshold_base * scale_factor)
        self.is_popup_detected = popup_motion_score > popup_threshold

        # 3. Cảnh báo an toàn: Đưa tay vào khuôn khi mâm đang quay thực sự (sau khi đã ấn nút kích hoạt)
        if self.is_moving and self.state == 'SPINNING' and is_hand_in_mold and self.trigger_time > 0:
            self.safety_violation = "hand_in_spinning_turntable"
            logger.warning(f"[{self.product_id}] CANH BAO NGUY HIEM: Tay cong nhan nam trong khuon khi mam dang quay!")
        else:
            self.safety_violation = None

        # 4. Máy trạng thái hữu hạn (FSM)
        if (curr_time - self.last_count_time) > self.debounce_sec:
            if self.state == 'COOLDOWN_LOCK':
                self.state = 'IDLE'

            if self.state == 'IDLE':
                # Chỉ kích hoạt chờ xoay khi có tín hiệu bấm nút khởi động (bước 3),
                # hoặc khi mâm xoay quay cực lớn (chuyển động toàn bộ mâm > 10.000 pixel) VÀ tay công nhân KHÔNG ở trong khuôn!
                if is_button_triggered:
                    self.state = 'TRIGGERED_WAIT_SPIN'
                    self.trigger_time = curr_time
                    self.spin_frames = 0
                    self.spin_gap_frames = 0
                    self.peak_motion = 0
                elif not is_hand_in_mold and motion_score > int(10000 * scale_factor):
                    self.state = 'SPINNING'
                    self.spin_start_time = curr_time
                    self.spin_frames = 1
                    self.spin_gap_frames = 0
                    self.peak_motion = motion_score

            elif self.state == 'TRIGGERED_WAIT_SPIN':
                # Khi đang chờ xoay sau khi ấn nút: mâm xoay chuyển động (và tay đã rút khỏi khuôn)
                if self.is_moving and not is_hand_in_mold:
                    self.state = 'SPINNING'
                    self.spin_start_time = curr_time
                    self.spin_frames = 1
                    self.spin_gap_frames = 0
                    self.peak_motion = motion_score
                elif (curr_time - self.trigger_time) > self.wait_spin_timeout_sec:
                    self.state = 'IDLE'
                    self.spin_frames = 0

            elif self.state == 'SPINNING':
                spin_elapsed = curr_time - self.spin_start_time
                if self.is_moving:
                    self.spin_frames += 1
                    self.spin_gap_frames = 0
                    self.peak_motion = max(self.peak_motion, motion_score)

                    if spin_elapsed > self.max_allowed_spin_sec:
                        self.state = 'ERROR_SPIN_ANOMALY'
                        logger.warning(f"[{self.product_id}] Mam xoay lien tuc bat thuong ({spin_elapsed:.1f}s) -> Khoa dem.")
                else:
                    self.spin_gap_frames += 1
                    if self.spin_gap_frames > 6:
                        actual_spin_dur = spin_elapsed - 0.2
                        min_peak_thresh = int(self.peak_motion_base * scale_factor)

                        # Xác nhận mâm xoay hoàn thành lượt xoay 180°
                        if (self.spin_frames >= self.min_spin_frames and 
                            (self.min_spin_duration <= actual_spin_dur <= self.max_spin_duration) and 
                            (self.peak_motion >= min_peak_thresh)):
                            
                            self.cycle_rotations += 1
                            self.spin_finish_time = curr_time

                            # Nếu yêu cầu sản phẩm nhô lên ở khung nhỏ (TK_1A00-V0022)
                            if self.require_product_popup and popup_poly_normalized:
                                self.state = 'WAIT_PRODUCT_POPUP'
                                logger.info(
                                    f"[{self.product_id}] Mam xoay 180 dung thanh cong. Dang cho san pham nho len o khung nho..."
                                )
                            else:
                                # Không yêu cầu kiểm tra popup -> Đếm trực tiếp
                                self._confirm_product_completed(curr_time, actual_spin_dur)
                        else:
                            self.state = 'IDLE'
                            self.spin_frames = 0
                            self.spin_gap_frames = 0

            elif self.state == 'WAIT_PRODUCT_POPUP':
                # Chờ sản phẩm nhô lên ở khung nhỏ trong vòng wait_popup_timeout_sec
                popup_elapsed = curr_time - self.spin_finish_time
                
                # CHỐNG NHẦM: Nếu tay công nhân đang ở trong khuôn (is_hand_in_mold == True),
                # đó là tay thao tác chứ TUYỆT ĐỐI KHÔNG PHẢI là sản phẩm tự nhô lên từ khuôn!
                if not is_hand_in_mold and self.is_popup_detected:
                    logger.info(
                        f"[{self.product_id}][PRODUCT POP-UP DETECTED] Phat hien san pham nhua den nho len trong khung nho (score={popup_motion_score})!"
                    )
                    self._confirm_product_completed(curr_time, popup_elapsed)
                elif popup_elapsed > self.wait_popup_timeout_sec:
                    # Hết thời gian chờ mà không thấy sản phẩm nhô lên (ví dụ: lượt xoay đưa khuôn trống ra hoặc xoay nhầm)
                    logger.info(f"[{self.product_id}] Khong co san pham nho len sau {popup_elapsed:.1f}s -> Bo qua, khong dem.")
                    self.state = 'IDLE'

            elif self.state == 'ERROR_SPIN_ANOMALY':
                if not self.is_moving:
                    self.state = 'IDLE'
                    self.spin_frames = 0
                    self.spin_gap_frames = 0
                    self.last_count_time = curr_time
        else:
            self.state = 'COOLDOWN_LOCK'

        return self.get_status()

    def _confirm_product_completed(self, curr_time: float, dur: float):
        """Xác nhận hoàn tất chu kỳ sản phẩm và cộng +1 SP."""
        self.spins_in_current_product += 1
        self.last_count_time = curr_time
        self.state = 'COOLDOWN_LOCK'
        self.spin_frames = 0
        self.spin_gap_frames = 0

        # CHỈ ĐẾM +1 SP KHI KHUÔN MÂM NHỎ QUAY RA:
        # Chu kỳ đảo chiều 180° gồm 2 lượt:
        # - Lượt 1: KHUÔN MÂM NHỎ QUAY RA -> ĐẾM +1 SP!
        # - Lượt 2: MÂM TO QUAY -> KHÔNG TÍNH SP!
        if self.spins_in_current_product == 1:
            self.total_products += self.products_per_cycle

            self.pending_product_event = {
                "added_products": self.products_per_cycle,
                "rotations": self.cycle_rotations,
                "total_products": self.total_products,
                "duration": round(dur, 2)
            }
            logger.info(
                f"[{self.product_id}][KHUON MAM NHO QUAY RA] Xac nhan +{self.products_per_cycle} SP! | Tong san luong: {self.total_products} SP (Tong luot xoay: {self.cycle_rotations})"
            )
        else:
            # Lượt 2 (Mâm to quay) -> reset nhịp về 0 cho chu kỳ tiếp theo, không đếm
            self.spins_in_current_product = 0
            logger.info(
                f"[{self.product_id}][MAM TO QUAY] Mam to quay -> KHONG TINH SP. Tong luot xoay: {self.cycle_rotations}."
            )

    def pop_pending_product_event(self) -> Optional[Dict[str, Any]]:
        ev = self.pending_product_event
        self.pending_product_event = None
        return ev

    def get_status(self) -> Dict[str, Any]:
        return {
            "turntable_state": self.state,
            "is_turntable_moving": self.is_moving,
            "motion_score": self.last_motion_score,
            "popup_score": getattr(self, "last_popup_score", 0),
            "is_popup_detected": getattr(self, "is_popup_detected", False),
            "total_products": self.total_products,
            "cycle_rotations": self.cycle_rotations,
            "spins_in_current_product": getattr(self, "spins_in_current_product", 0),
            "spins_per_product": self.spins_per_product,
            "safety_violation": self.safety_violation
        }
