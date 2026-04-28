import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SOPGraph:
    def __init__(self, sop_config: dict):
        self.config = sop_config
        self.steps = sop_config.get("sop_steps", {})
        self.step_ids = list(self.steps.keys())
        self.current_step_id = "S1"
        self.completed = False
        self.step_progress = set() 
        self.session_start_time = time.time()
        self.last_step_complete_time = time.time()

    def advance(self) -> dict:
        if self.completed: return {"success": False}
        current_idx = self.step_ids.index(self.current_step_id)
        logger.info(f"SOPGraph: Step {self.current_step_id} COMPLETED.")
        self.step_progress = set() 
        self.last_step_complete_time = time.time()
        if current_idx < len(self.step_ids) - 1:
            self.current_step_id = self.step_ids[current_idx + 1]
            return {"success": True, "completed": False}
        else:
            self.completed = True
            return {"success": True, "completed": True}

    def reset(self):
        self.current_step_id = "S1"
        self.completed = False
        self.session_start_time = time.time()

    def get_state(self) -> dict:
        step_data = self.steps.get(self.current_step_id, {})
        total = len(self.step_ids)
        current_idx = self.step_ids.index(self.current_step_id) if not self.completed else total
        return {
            "current_node": self.current_step_id if not self.completed else "DONE",
            "expected_step": step_data.get("name", self.current_step_id) if not self.completed else "DONE",
            "desc": step_data.get("desc", "Finish"),
            "progress_percent": (current_idx / total) * 100,
            "completed": self.completed,
            "sop_status": "completed" if self.completed else "in_progress"
        }
