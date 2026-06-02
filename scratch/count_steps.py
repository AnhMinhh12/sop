import os
import re

log_path = "data/logs/TFF4040_debug.txt"

step_counts = {}
with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "STEP COMPLETED:" in line:
            # count the exact line
            line = line.strip()
            match = re.search(r"STEP COMPLETED:\s*(\d+)/?(\d+)?", line)
            if match:
                step_num = match.group(1)
                step_counts[step_num] = step_counts.get(step_num, 0) + 1

for k, v in sorted(step_counts.items(), key=lambda x: int(x[0])):
    print(f"Step {k}: {v} times")
