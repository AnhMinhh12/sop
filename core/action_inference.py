import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ActionInference:
    def __init__(self, sop_config: dict, sop_graph):
        self.config = sop_config
        self.graph = sop_graph
        self.steps_def = self.graph.steps
        self.timers = {}
        self.counters = {}
        self.accumulated_events = set()
        self.ghost_hands = {"left": {"locked_zone": None, "lock_time": 0}, 
                            "right": {"locked_zone": None, "lock_time": 0}}
        self._last_detected_label = "Idle"
        self._last_zones = {"left": None, "right": None}

    def process_features(self, features: Dict) -> dict:
        now = time.time()
        current_step_id = self.graph.current_step_id
        if self.graph.completed:
            state = self.graph.get_state()
            state["detected_label"] = "Finished"
            return state

        step_def = self.steps_def.get(current_step_id, {})
        conditions = step_def.get("conditions", [])
        active_zones = step_def.get("active_zones", [])
        mode = step_def.get("mode", "all") 
        
        if active_zones:
            for side in ["left", "right"]:
                z = features["hands"][side].get("zone")
                if z and z not in active_zones:
                    features["hands"][side]["zone"] = None

        current_actions = []
        for side in ["left", "right"]:
            z = features["hands"][side].get("zone")
            if z: current_actions.append(f"{side.upper()} @ {z}")
            if z != self._last_zones[side]:
                if z: logger.info(f"--- [ZONE ENTRY] Hand {side.upper()} entered {z}")
                elif self._last_zones[side]: logger.info(f"--- [ZONE EXIT] Hand {side.upper()} left {self._last_zones[side]}")
                self._last_zones[side] = z
        self._last_detected_label = ", ".join(current_actions) if current_actions else "Idle"

        conditions_met_this_frame = []
        for idx, cond in enumerate(conditions):
            met = self._check_condition(cond, features, now)
            if met:
                conditions_met_this_frame.append(idx)
                
        step_completed = False
        if mode == "independent":
            for idx in conditions_met_this_frame:
                self.accumulated_events.add(idx)
            if len(self.accumulated_events) >= len(conditions):
                step_completed = True
        else:
            if len(conditions_met_this_frame) >= len(conditions):
                step_completed = True

        if step_completed:
            logger.info(f"!!! [SOP ADVANCE] Step {current_step_id} -> {step_def.get('next')}")
            self.graph.advance()
            self.accumulated_events = set()
            self.timers = {} 
            self.counters = {}
        
        state = self.graph.get_state()
        state["detected_label"] = self._last_detected_label
        return state

    def _check_condition(self, cond: Dict, features: Dict, now: float) -> bool:
        c_type = cond.get("type")
        if c_type == "pick_accumulation":
            target = cond.get("target_count", 1)
            zone_from = cond.get("zone_from")
            zone_to = cond.get("zone_to")
            if isinstance(zone_from, str): zone_from = [zone_from]
            if "pick_count" not in self.counters: self.counters["pick_count"] = 0
            if "last_zone" not in self.counters: self.counters["last_zone"] = {}
            for side in ["left", "right"]:
                if side not in self.counters["last_zone"]: self.counters["last_zone"][side] = None
                z = features["hands"][side].get("zone")
                if z in zone_from:
                    self.counters["last_zone"][side] = "from"
                elif z == zone_to and self.counters["last_zone"][side] == "from":
                    self.counters["pick_count"] += 1
                    self.counters["last_zone"][side] = "to"
                    logger.info(f"*** [+] ITEM PICKED ({side.upper()}): {self.counters['pick_count']}/{target}")
            return self.counters["pick_count"] >= target
        elif c_type == "both_hands_in_zone":
            zone = cond.get("zone")
            tolerance = cond.get("loss_tolerance", 0.5)
            duration = cond.get("min_duration", 3.0)
            in_zone = features.get("both_hands_zone") == zone
            return self._timer_with_tolerance(f"both_{zone}", in_zone, now, duration, tolerance)
        elif c_type == "jig_occlusion_logic":
            zone = cond.get("zone")
            side_l = features["hands"]["left"]
            side_r = features["hands"]["right"]
            if side_l["zone"] == zone:
                self.ghost_hands["left"]["locked_zone"] = zone
                self.ghost_hands["left"]["lock_time"] = now
            elif side_l["occluded"] and self.ghost_hands["left"]["locked_zone"] == zone:
                side_l["zone"] = zone
            both_active = (side_l["zone"] == zone) and (side_r["zone"] == zone)
            return self._timer_with_tolerance("jig_check", both_active, now, cond.get("min_duration", 2.0), 0.5)
        elif c_type == "hand_in_zone":
            h_side = cond.get("hand")
            zone = cond.get("zone")
            in_zone = features["hands"].get(h_side, {}).get("zone") == zone
            return self._timer_with_tolerance(f"{h_side}_{zone}", in_zone, now, cond.get("min_duration", 0.3), 0.1)
        return False

    def _timer_with_tolerance(self, key: str, is_active: bool, now: float, duration: float, tolerance: float) -> bool:
        t_key = f"timer_{key}"
        l_key = f"last_active_{key}"
        if is_active:
            if t_key not in self.timers:
                self.timers[t_key] = now
                logger.info(f">>> [TIMER START] {key}")
            self.timers[l_key] = now
            elapsed = now - self.timers[t_key]
            return elapsed >= duration
        else:
            last_active = self.timers.get(l_key, 0)
            if now - last_active > tolerance:
                if t_key in self.timers: 
                    logger.info(f"xxx [TIMER RESET] {key}")
                    del self.timers[t_key]
            return False
