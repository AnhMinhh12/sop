import os

# --- TFF4040 ---
file_4040 = r"c:\Users\it07\Downloads\AI_Monitoring_Hub\projects\sop_monitoring\core\engines\TFF4040_engine.py"
with open(file_4040, "r", encoding="utf-8") as f:
    lines_4040 = f.readlines()

start_4040 = -1
end_4040 = -1
for i, line in enumerate(lines_4040):
    if "def _check_step_logic(" in line:
        start_4040 = i
    if "def _is_in_zone(" in line and start_4040 != -1:
        end_4040 = i
        break

code_4040 = """    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False, shrink_factor: float = 0.0) -> bool:
        logic = step.get("logic")
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            
            if target not in self._zone_triggered:
                self._zone_triggered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                if is_in:
                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                    if entry > 0.0 and (now - entry >= 0.2):
                        if update_status:
                            self._zone_triggered[target][side] = True
                            
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                return any(self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor) for side in ["left", "right"])
                
            if mode == "both":
                return self._zone_triggered[target]["left"] and self._zone_triggered[target]["right"]
            elif mode == "any":
                return self._zone_triggered[target]["left"] or self._zone_triggered[target]["right"]
            else:
                return self._zone_triggered[target].get(mode, False)
                
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            if target not in self._stay_timer: self._stay_timer[target] = {"left": 0, "right": 0}
            for side in ["left", "right"]:
                if self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor):
                    if self._stay_timer[target][side] == 0 and update_status: self._stay_timer[target][side] = now  
                elif update_status: self._stay_timer[target][side] = 0 
            if mode == "any": return any(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            elif mode == "both": return all(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            return self._stay_timer[target][mode] > 0 and (now - self._stay_timer[target][mode]) >= min_dur
            
        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("required_count", 1)
            mode = step.get("active_hand", "any")
            any_in = False
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hit_registered:
                self._hit_registered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                is_in_debounced = is_in
                if not is_in and update_status:
                    last_seen = self._zone_last_seen[target].get(side, 0.0)
                    if last_seen > 0 and (now - last_seen < 0.3):
                        is_in_debounced = True
                        
                if update_status:
                    if is_in:
                        self._zone_last_seen[target][side] = now
                        
                if side not in self.last_trigger_states:
                    was_already_in = (
                        self.current_step_idx > 0 and
                        self.hand_states[side]["zone"] == target and
                        self.hand_states[side]["entry_time"] < self.step_start_time
                    )
                    self.last_trigger_states[side] = was_already_in
                    
                if update_status:
                    if is_in_debounced:
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if not self._hit_registered.get(target, {}).get(side, False):
                                self.hit_count += 1
                                if target not in self._hit_registered:
                                    self._hit_registered[target] = {"left": False, "right": False}
                                self._hit_registered[target][side] = True
                                self.log_debug(f"Multi-trigger hit counted for {side} hand in {target}. Hit count: {self.hit_count}/{count_needed}", self.product_id)
                    else:
                        if target in self._hit_registered:
                            self._hit_registered[target][side] = False
                    self.last_trigger_states[side] = is_in_debounced
                    
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only, shrink_factor=shrink_factor)
                return any_in
                
            # Cho phép hoàn thành chu kỳ bằng 1 trigger + rút tay cho bước đầu tiên (đặc trưng của TFF4040)
            if self.current_step_idx == 0:
                if self.hit_count >= count_needed:
                    return True
                s1_any_in = False
                for side in ["left", "right"]:
                    if self.last_trigger_states.get(side, False):
                        s1_any_in = True
                if self.hit_count >= 1 and not s1_any_in:
                    return True
                return False
                
            return self.hit_count >= count_needed
            
        elif logic == "dual_task":
            l_zone, r_zone = step.get("left_zone"), step.get("right_zone")
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                        self._is_in_zone("right", r_zone, centroid_only=centroid_only, shrink_factor=shrink_factor)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only, shrink_factor=shrink_factor) and \
                        self._is_in_zone("left", r_zone, centroid_only=centroid_only, shrink_factor=shrink_factor)
                return cond1 or cond2

            # Chỉ ghi nhận kích hoạt khi tay giữ trong vùng ít nhất 0.2s
            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    if self._is_in_zone(side, z, centroid_only=centroid_only, shrink_factor=shrink_factor):
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if side == "left" and z == l_zone:
                                self.last_trigger_states["dual_left_in_l"] = True
                            if side == "right" and z == r_zone:
                                self.last_trigger_states["dual_right_in_r"] = True
                            if side == "right" and z == l_zone:
                                self.last_trigger_states["dual_right_in_l"] = True
                            if side == "left" and z == r_zone:
                                self.last_trigger_states["dual_left_in_r"] = True

            normal_match = self.last_trigger_states.get("dual_left_in_l", False) and self.last_trigger_states.get("dual_right_in_r", False)
            swapped_match = self.last_trigger_states.get("dual_right_in_l", False) and self.last_trigger_states.get("dual_left_in_r", False)
            return normal_match or swapped_match
        return False
"""

if start_4040 != -1 and end_4040 != -1:
    new_lines = lines_4040[:start_4040] + [line + "\n" for line in code_4040.splitlines()] + lines_4040[end_4040:]
    with open(file_4040, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("TFF4040_engine refactored successfully!")
else:
    print("Could not find start/end for TFF4040_engine!")


# --- 626287 ---
file_626287 = r"c:\Users\it07\Downloads\AI_Monitoring_Hub\projects\sop_monitoring\core\engines\626287_engine.py"
with open(file_626287, "r", encoding="utf-8") as f:
    lines_626287 = f.readlines()

start_626287 = -1
end_626287 = -1
for i, line in enumerate(lines_626287):
    if "def _check_step_logic(" in line:
        start_626287 = i
    if "def _is_in_zone(" in line and start_626287 != -1:
        end_626287 = i
        break

code_626287 = """    def _check_step_logic(self, step: Dict, now: float, update_status: bool = True, centroid_only: bool = False) -> bool:
        logic = step.get("logic")
        if logic == "zone_trigger":
            target = step.get("required_zone")
            mode = step.get("active_hand", "any")
            
            if target not in self._zone_triggered:
                self._zone_triggered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                if is_in:
                    entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                    if entry > 0.0 and (now - entry >= 0.2):
                        if update_status:
                            self._zone_triggered[target][side] = True
                            
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only)
                return any(self._is_in_zone(side, target, centroid_only=centroid_only) for side in ["left", "right"])
                
            if mode == "both":
                return self._zone_triggered[target]["left"] and self._zone_triggered[target]["right"]
            elif mode == "any":
                return self._zone_triggered[target]["left"] or self._zone_triggered[target]["right"]
            else:
                return self._zone_triggered[target].get(mode, False)
                
        elif logic == "stay_in_zone":
            target = step.get("required_zone")
            min_dur = step.get("min_duration_sec", 0.5)
            mode = step.get("active_hand", "both")
            if target not in self._stay_timer: self._stay_timer[target] = {"left": 0, "right": 0}
            for side in ["left", "right"]:
                if self._is_in_zone(side, target, centroid_only=centroid_only):
                    if self._stay_timer[target][side] == 0 and update_status: self._stay_timer[target][side] = now  
                elif update_status: self._stay_timer[target][side] = 0 
            if mode == "any": return any(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            elif mode == "both": return all(self._stay_timer[target][s] > 0 and (now - self._stay_timer[target][s]) >= min_dur for s in ["left", "right"])
            return self._stay_timer[target][mode] > 0 and (now - self._stay_timer[target][mode]) >= min_dur
            
        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("required_count", 1)
            mode = step.get("active_hand", "any")
            any_in = False
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hit_registered:
                self._hit_registered[target] = {"left": False, "right": False}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                is_in_debounced = is_in
                if not is_in and update_status:
                    last_seen = self._zone_last_seen[target].get(side, 0.0)
                    if last_seen > 0 and (now - last_seen < 0.3):
                        is_in_debounced = True
                        
                if update_status:
                    if is_in:
                        self._zone_last_seen[target][side] = now
                        
                if side not in self.last_trigger_states:
                    was_already_in = (
                        self.current_step_idx > 0 and
                        self.hand_states[side]["zone"] == target and
                        self.hand_states[side]["entry_time"] < self.step_start_time
                    )
                    self.last_trigger_states[side] = was_already_in
                    
                if update_status:
                    if is_in_debounced:
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == target else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if not self._hit_registered.get(target, {}).get(side, False):
                                self.hit_count += 1
                                if target not in self._hit_registered:
                                    self._hit_registered[target] = {"left": False, "right": False}
                                self._hit_registered[target][side] = True
                                self.log_debug(f"Multi-trigger hit counted for {side} hand in {target}. Hit count: {self.hit_count}/{count_needed}", self.product_id)
                    else:
                        if target in self._hit_registered:
                            self._hit_registered[target][side] = False
                    self.last_trigger_states[side] = is_in_debounced
                    
            if not update_status:
                if mode == "both":
                    return self._is_in_zone("left", target, centroid_only=centroid_only) and \
                           self._is_in_zone("right", target, centroid_only=centroid_only)
                return any_in
                
            return self.hit_count >= count_needed
            
        elif logic == "dual_task":
            l_zone, r_zone = step.get("left_zone"), step.get("right_zone")
            if not update_status:
                cond1 = self._is_in_zone("left", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("right", r_zone, centroid_only=centroid_only)
                cond2 = self._is_in_zone("right", l_zone, centroid_only=centroid_only) and \
                        self._is_in_zone("left", r_zone, centroid_only=centroid_only)
                return cond1 or cond2

            # Chỉ ghi nhận kích hoạt khi tay giữ trong vùng ít nhất 0.2s
            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    if self._is_in_zone(side, z, centroid_only=centroid_only):
                        entry = self.hand_states[side]["entry_time"] if self.hand_states[side]["zone"] == z else now
                        if entry > 0.0 and (now - entry >= 0.2):
                            if side == "left" and z == l_zone:
                                self.last_trigger_states["dual_left_in_l"] = True
                            if side == "right" and z == r_zone:
                                self.last_trigger_states["dual_right_in_r"] = True
                            if side == "right" and z == l_zone:
                                self.last_trigger_states["dual_right_in_l"] = True
                            if side == "left" and z == r_zone:
                                self.last_trigger_states["dual_left_in_r"] = True

            normal_match = self.last_trigger_states.get("dual_left_in_l", False) and self.last_trigger_states.get("dual_right_in_r", False)
            swapped_match = self.last_trigger_states.get("dual_right_in_l", False) and self.last_trigger_states.get("dual_left_in_r", False)
            return normal_match or swapped_match
        return False
"""

if start_626287 != -1 and end_626287 != -1:
    new_lines = lines_626287[:start_626287] + [line + "\n" for line in code_626287.splitlines()] + lines_626287[end_626287:]
    with open(file_626287, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("626287_engine refactored successfully!")
else:
    print("Could not find start/end for 626287_engine!")
