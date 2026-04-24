import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ViolationDetector:
    """
    High-level analyzer for SOP violations.
    Includes cooldown to prevent alert spam and violation count tracking.
    """
    def __init__(self, camera_id: str, cooldown_sec: float = 10.0):
        self.camera_id = camera_id
        self.cooldown_sec = cooldown_sec
        self.last_violation_time: float = 0
        self.last_violation_type: Optional[str] = None
        self.violation_count: int = 0

    def analyze(self, sm_status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyzes the output from SOPStateMachine.
        Returns a violation event dict if a serious violation is detected.
        Includes cooldown to avoid logging the same violation type repeatedly.
        """
        status = sm_status.get("sop_status")
        violation_type = sm_status.get("violation_type")

        if violation_type:
            current_time = time.time()

            # Cooldown: không trigger cùng loại vi phạm trong khoảng thời gian ngắn
            if (violation_type == self.last_violation_type and
                    current_time - self.last_violation_time < self.cooldown_sec):
                return None

            logger.warning(f"ViolationDetector [{self.camera_id}]: "
                           f"{violation_type} detected (total: {self.violation_count + 1})")
            self.last_violation_type = violation_type
            self.last_violation_time = current_time
            self.violation_count += 1

            return {
                "camera_id": self.camera_id,
                "violation_type": violation_type,
                "expected_step": sm_status.get("expected_step"),
                "detected_step": sm_status.get("detected_label"),
                "confidence": sm_status.get("confidence", 0.0),
                "timestamp": current_time,
                "total_violations": self.violation_count,
            }
        else:
            # Reset khi trở lại trạng thái bình thường
            if status in ["correct", "idle", "completed"]:
                self.last_violation_type = None

        return None
