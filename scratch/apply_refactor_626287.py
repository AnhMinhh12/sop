import os

file_path = r"c:\Users\it07\Downloads\AI_Monitoring_Hub\projects\sop_monitoring\core\engines\626287_engine.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

multi_idx = -1
is_in_zone_idx = -1
for i, line in enumerate(lines):
    if 'elif logic == "multi_trigger":' in line:
        multi_idx = i
    if 'def _is_in_zone(' in line:
        is_in_zone_idx = i
        break

if multi_idx != -1 and is_in_zone_idx != -1:
    print(f"Found logic block: multi_trigger at line {multi_idx}, _is_in_zone at line {is_in_zone_idx}")
    
    # We will replace lines from multi_idx to is_in_zone_idx (exclusive, except the return False at the end)
    # Let's see: the last line before _is_in_zone is "        return False\n" or similar.
    # Let's inspect them:
    block_lines = lines[multi_idx:is_in_zone_idx]
    print("First line:", block_lines[0])
    print("Last line:", block_lines[-1])
    
    replacement_code = """        elif logic == "multi_trigger":
            target = step.get("required_zone")
            count_needed = step.get("required_count", 1)
            mode = step.get("active_hand", "any")
            any_in = False
            
            if target not in self._zone_last_seen:
                self._zone_last_seen[target] = {"left": 0.0, "right": 0.0}
            if target not in self._hand_entry_time:
                self._hand_entry_time[target] = {"left": 0.0, "right": 0.0}
                
            for side in ["left", "right"]:
                is_in = self._is_in_zone(side, target, centroid_only=centroid_only)
                if is_in:
                    if mode == "any" or mode == side:
                        any_in = True
                    if update_status:
                        self._zone_last_seen[target][side] = now
                        if self._hand_entry_time[target][side] == 0.0:
                            self._hand_entry_time[target][side] = now
                else:
                    if update_status:
                        self._hand_entry_time[target][side] = 0.0
                        
                is_in_debounced = is_in
                if not is_in and update_status:
                    last_seen = self._zone_last_seen[target].get(side, 0.0)
                    if last_seen > 0 and (now - last_seen < 0.3):
                        is_in_debounced = True
                        
                # Tay phải ở trong vùng liên tục ít nhất 0.2 giây mới tính là trigger hợp lệ
                is_in_sustained = is_in_debounced
                if is_in_debounced and update_status:
                    entry = self._hand_entry_time[target].get(side, 0.0)
                    if entry > 0.0 and (now - entry >= 0.2):
                        is_in_sustained = True
                    else:
                        is_in_sustained = False
                        
                if side not in self.last_trigger_states:
                    was_already_in = (
                        self.current_step_idx > 0 and
                        self.hand_states[side]["zone"] == target and
                        self.hand_states[side]["entry_time"] < self.step_start_time
                    )
                    self.last_trigger_states[side] = was_already_in
                    
                if update_status:
                    if is_in_sustained and not self.last_trigger_states.get(side, False):
                        self.hit_count += 1
                        self.log_debug(f"Multi-trigger hit counted for {side} hand in {target}. Hit count: {self.hit_count}/{count_needed}", self.product_id)
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

            if "dual_left_in_l" not in self.last_trigger_states:
                self.last_trigger_states["dual_left_in_l"] = False
                self.last_trigger_states["dual_right_in_r"] = False
                self.last_trigger_states["dual_right_in_l"] = False
                self.last_trigger_states["dual_left_in_r"] = False

            # Đảm bảo có entry timer cho 2 vùng của dual_task
            for z in [l_zone, r_zone]:
                if z not in self._zone_entry_time:
                    self._zone_entry_time[z] = {"left": 0.0, "right": 0.0}

            for side in ["left", "right"]:
                for z in [l_zone, r_zone]:
                    if self._is_in_zone(side, z, centroid_only=centroid_only):
                        if self._zone_entry_time[z][side] == 0.0:
                            self._zone_entry_time[z][side] = now
                    else:
                        self._zone_entry_time[z][side] = 0.0

            # Chỉ ghi nhận kích hoạt khi tay giữ trong vùng ít nhất 0.2s
            if self._zone_entry_time[l_zone]["left"] > 0 and (now - self._zone_entry_time[l_zone]["left"] >= 0.2):
                self.last_trigger_states["dual_left_in_l"] = True
            if self._zone_entry_time[r_zone]["right"] > 0 and (now - self._zone_entry_time[r_zone]["right"] >= 0.2):
                self.last_trigger_states["dual_right_in_r"] = True
            if self._zone_entry_time[l_zone]["right"] > 0 and (now - self._zone_entry_time[l_zone]["right"] >= 0.2):
                self.last_trigger_states["dual_right_in_l"] = True
            if self._zone_entry_time[r_zone]["left"] > 0 and (now - self._zone_entry_time[r_zone]["left"] >= 0.2):
                self.last_trigger_states["dual_left_in_r"] = True

            normal_match = self.last_trigger_states["dual_left_in_l"] and self.last_trigger_states["dual_right_in_r"]
            swapped_match = self.last_trigger_states["dual_right_in_l"] and self.last_trigger_states["dual_left_in_r"]
            return normal_match or swapped_match
        return False
"""
    
    # We replace from multi_idx to is_in_zone_idx (exclusive)
    # Let's convert replacement_code to lines
    new_lines = lines[:multi_idx] + [line + "\n" for line in replacement_code.splitlines()] + lines[is_in_zone_idx:]
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Replaced successfully!")
else:
    print("Could not find line indices!")
