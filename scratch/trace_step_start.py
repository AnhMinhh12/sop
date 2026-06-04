import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from projects.sop_monitoring.core.engines.TFF4040_engine import ProductEngine as TFF4040Engine
from shared.services.config_loader import ConfigLoader

def get_hand_in_zone(label, centroid):
    w, h = 640, 480
    cx_pix = int(centroid[0] * w)
    cy_pix = int(centroid[1] * h)
    return {
        "label": label,
        "centroid": centroid,
        "bbox": [cx_pix - 20, cy_pix - 20, cx_pix + 20, cy_pix + 20],
        "confidence": 0.9
    }

sop_file = "projects/sop_monitoring/config/TFF4040.yaml"
sop_config = ConfigLoader.load_yaml(sop_file)
engine = TFF4040Engine(sop_config)

mold_center = [0.43, 0.58]
left_table_center = [0.41, 0.26]

# Test 1
t1 = time.time()
print(f"t1 = {t1}")
res = engine.update([])
print(f"Test 1: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")

# Test 2
time.sleep(0.1)
t2 = time.time()
print(f"t2 = {t2}")
res = engine.update([get_hand_in_zone("left", mold_center)])
print(f"Test 2: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")

# Test 3
time.sleep(0.35)
t3 = time.time()
print(f"t3 = {t3}")
res = engine.update([get_hand_in_zone("left", mold_center)])
print(f"Test 3: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")

# Test 4
time.sleep(0.35)
t4 = time.time()
print(f"t4 = {t4}")
res = engine.update([])
print(f"Test 4: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")

# Test 5 - first update
time.sleep(0.35)
t5_1 = time.time()
print(f"t5_1 = {t5_1}")
res = engine.update([get_hand_in_zone("left", left_table_center)])
print(f"Test 5.1: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")

# Test 5 - second update
time.sleep(0.25)
t5_2 = time.time()
print(f"t5_2 = {t5_2}")
res = engine.update([get_hand_in_zone("left", left_table_center)])
print(f"Test 5.2: idx={engine.current_step_idx}, step_start_time={engine.step_start_time}, last_update_time={engine.last_update_time}")
