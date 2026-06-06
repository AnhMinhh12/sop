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

def run_countdown_test():
    print("=== STARTING COUNTDOWN & CYCLE TIMEOUT TEST ===")
    
    sop_file = "projects/sop_monitoring/config/TFF4040.yaml"
    sop_config = ConfigLoader.load_yaml(sop_file)
    if not sop_config:
        print("Error: Could not load TFF4040.yaml config!")
        sys.exit(1)
        
    engine = TFF4040Engine(sop_config)
    
    mold_center = [0.43, 0.58]
    
    # 1. Initially waiting for start
    res = engine.update([])
    print(f"Initial: waiting_for_start={engine.waiting_for_start}, cycle_time_left={res.get('cycle_time_left')}")
    assert engine.waiting_for_start == True
    assert res.get("cycle_time_left") == 38.0
    
    # 2. Trigger step 1 to start cycle
    engine.update([get_hand_in_zone("left", mold_center)])
    time.sleep(0.35)
    res = engine.update([get_hand_in_zone("left", mold_center)])
    print(f"Cycle started: waiting_for_start={engine.waiting_for_start}, cycle_time_left={res.get('cycle_time_left')}")
    assert engine.waiting_for_start == False
    assert res.get("cycle_time_left") == 38.0
    
    # Sleep 0.2s and update again to see countdown decrement
    time.sleep(0.2)
    res = engine.update([get_hand_in_zone("left", mold_center)])
    print(f"After 0.2s: cycle_time_left={res.get('cycle_time_left')}")
    assert res.get("cycle_time_left") < 38.0 and res.get("cycle_time_left") > 35.0
    
    # 3. Simulate elapsed time within cycle limit
    fake_now = engine.cycle_start_time + 20.0
    # Override engine last update time to fake time
    engine.last_update_time = fake_now
    res = engine._get_status_result({"left": "mold", "right": None}, "processing")
    print(f"Faked 20s elapsed: cycle_time_left={res.get('cycle_time_left')}")
    assert abs(res.get("cycle_time_left") - 18.0) < 0.1
    
    # 4. Simulate cycle timeout (> 38s)
    # We call update with a hand in mold, but elapsed cycle time is 39s
    # To simulate time, we can manually manipulate the time inside the engine update or simulate it by sleeping/mocking.
    # In TFF4040_engine.py, time is read via time.time() or we can check the logic.
    # Let's verify by overriding time.time in the test context or faking the elapsed time.
    # Let's temporarily mock time.time or sleep to check.
    # Since we don't want to sleep 38 seconds in a test, let's mock time.time!
    original_time = time.time
    try:
        start_t = original_time()
        # Mock time to advance 40 seconds on next check
        time.time = lambda: start_t + 40.0
        
        # Run update
        res = engine.update([get_hand_in_zone("left", mold_center)])
        print(f"Faked 40s update: sop_status={res.get('sop_status')}, violation_type={res.get('violation_type')}, cycle_time_left={res.get('cycle_time_left')}")
        assert res.get("sop_status") == "violation"
        assert res.get("violation_type") == "timeout"
        assert res.get("cycle_time_left") == 0.0
    finally:
        time.time = original_time
        
    print("COUNTDOWN & CYCLE TIMEOUT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_countdown_test()
