import os
import re
import sys

# Thiết lập stdout UTF-8
sys.stdout.reconfigure(encoding='utf-8')

log_path = "data/logs/TFF4040_debug.txt"

if not os.path.exists(log_path):
    print("Log file not found!")
    exit(1)

violations = []
resets = []
completed_cycles = 0
step_completed_counts = {}

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if "VIOLATION:" in line:
            violations.append(line)
        elif "ENGINE RESET" in line:
            resets.append(line)
        elif "CYCLE STARTED" in line:
            pass
        elif "STEP COMPLETED:" in line:
            match = re.search(r"STEP COMPLETED: (\d+)/9\s*-\s*(.+)", line)
            if match:
                step_num = int(match.group(1))
                step_name = match.group(2)
                step_completed_counts[step_num] = step_completed_counts.get(step_num, 0) + 1
                if step_num == 9:
                    completed_cycles += 1
            else:
                # Thử pattern khác e.g. không có /9
                match = re.search(r"STEP COMPLETED: (\d+)\s*-\s*(.+)", line)
                if match:
                    step_num = int(match.group(1))
                    step_completed_counts[step_num] = step_completed_counts.get(step_num, 0) + 1
                    if step_num == 9:
                        completed_cycles += 1

print(f"Total cycles completed: {completed_cycles}")
print(f"Total VIOLATION events: {len(violations)}")
print(f"Total ENGINE RESET events: {len(resets)}")

print("\n--- Violation details ---")
violation_types = {}
for v in violations:
    match = re.search(r"VIOLATION:\s*(.+)", v)
    if match:
        v_desc = match.group(1)
        if "Timeout" in v_desc:
            key = "Timeout"
            step_match = re.search(r"step (\d+)\s*\((.+)\)", v_desc)
            if step_match:
                key = f"Timeout at step {step_match.group(1)} ({step_match.group(2)})"
            else:
                step_match = re.search(r"step (\d+)", v_desc)
                if step_match:
                    key = f"Timeout at step {step_match.group(1)}"
        elif "Premature Restart" in v_desc:
            key = "Premature Restart"
            step_match = re.search(r"step (\d+)", v_desc)
            if step_match:
                key = f"Premature Restart at step {step_match.group(1)}"
        else:
            key = v_desc
        violation_types[key] = violation_types.get(key, 0) + 1

# Write to file to be safe and also print
out_lines = []
out_lines.append(f"Total cycles completed: {completed_cycles}")
out_lines.append(f"Total VIOLATION events: {len(violations)}")
out_lines.append(f"Total ENGINE RESET events: {len(resets)}")
out_lines.append("\n--- Violation details ---")
for k, v in sorted(violation_types.items(), key=lambda item: item[1], reverse=True):
    out_lines.append(f"- {k}: {v} times")

with open("scratch/log_analysis.txt", "w", encoding="utf-8") as out_f:
    out_f.write("\n".join(out_lines))

print("Analysis written to scratch/log_analysis.txt successfully.")
