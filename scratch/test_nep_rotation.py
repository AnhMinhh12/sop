import sys, os, time
sys.path.insert(0, ".")
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine

def test_nep_rotation_and_inspection():
    sop_config = {
        "station_id": "machine_08",
        "station_name": "Máy IN-HOT-LAPRAP",
        "target_screws": 8,
        "missing_dwell_sec": 4.5,
        "max_cycle_time_sec": 35.0,
        "zones": {
            "vung_cat": [[0.02, 0.11], [0.36, 0.11], [0.36, 0.94], [0.02, 0.94]],
            "vung_lay": [[0.60, 0.18], [0.97, 0.18], [0.97, 0.94], [0.60, 0.94]]
        },
        "config": {"w": 1280, "h": 720, "max_cycle_time_sec": 35.0}
    }
    
    engine = ProductEngine(sop_config)
    
    # 1. Start Cycle 1 from vung_lay
    part_lay = [800, 250, 920, 500]
    hand_lay = [{"bbox": [780, 240, 900, 480], "label": "right"}]
    prod_lay = [{"class": "part_hand", "bbox": part_lay, "confidence": 0.9}]
    for _ in range(5):
        engine.update(hand_lay, prod_lay)
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 1
    
    # 2. Assemble 8 screws in center
    part_center = [520, 180, 640, 580]
    hand_center = [{"bbox": [480, 200, 560, 400], "label": "left"}]
    s_t0 = [([540, 220, 555, 235], 0.8), ([600, 220, 615, 235], 0.8)]
    s_t1 = [([540, 310, 555, 325], 0.8), ([600, 310, 615, 325], 0.8)]
    s_t2 = [([540, 410, 555, 425], 0.8), ([600, 410, 615, 425], 0.8)]
    s_t3 = [([540, 510, 555, 525], 0.8), ([600, 510, 615, 525], 0.8)]
    all_8_screws = [{"class": "screw", "bbox": b, "confidence": c} for b, c in (s_t0 + s_t1 + s_t2 + s_t3)]
    prod_8 = [{"class": "part_hand", "bbox": part_center, "confidence": 0.95}] + all_8_screws
    for _ in range(5):
        engine.update(hand_center, prod_8)
    assert engine.has_completed_screws == True
    assert sum(engine.slots) == 8
    print(">>> Step 1: 8 screws completed.")
    
    # 3. Worker snaps black nẹp on in center table
    # Case A: Part lost for 1.5s while grabbing nẹp and fitting
    print("\n--- TEST: PART LOST FOR 1.5s IN CENTER (FITTING NEP) ---")
    t0 = time.time()
    while time.time() - t0 < 1.5:
        st = engine.update([], [])
        time.sleep(0.1)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    assert engine.cycle_count == 1, f"Expected Cycle 1, got {engine.cycle_count}"
    assert engine.total_good == 0, f"Expected 0 good, got {engine.total_good}"
    print(">>> VERIFIED: Part lost in center did NOT trigger PASS or close cycle!")
    
    # Case B: Part reappears in center (worker inspects, 0 screws visible due to black nẹp)
    prod_nep = [{"class": "part_hand", "bbox": [530, 190, 650, 590], "confidence": 0.9}] # 0 screws visible
    for _ in range(5):
        st = engine.update(hand_center, prod_nep)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    assert engine.cycle_count == 1, f"Expected Cycle 1, got {engine.cycle_count}"
    assert engine.total_good == 0, f"Expected 0 good, got {engine.total_good}"
    print(">>> VERIFIED: Part reappearance with nẹp in center did NOT create duplicate cycle!")
    
    # Case C: Worker rotates part to inspect back side (lost again for 2.0s)
    print("\n--- TEST: PART ROTATED / LOST AGAIN FOR 2.0s (INSPECTION) ---")
    t0 = time.time()
    while time.time() - t0 < 2.0:
        st = engine.update([], [])
        time.sleep(0.1)
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 1
    assert engine.total_good == 0
    print(">>> VERIFIED: Second loss in center still did NOT trigger PASS!")
    
    # 4. Worker brings part to vung_cat (left zone)
    print("\n--- TEST: MOVE TO VUNG_CAT AND RELEASE HANDS ---")
    part_cat = [150, 200, 280, 500]
    hand_cat_2hands = [
        {"bbox": [130, 220, 220, 380], "label": "left"},
        {"bbox": [210, 220, 300, 380], "label": "right"}
    ]
    prod_cat = [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}]
    # Holding with 2 hands
    for _ in range(5):
        st = engine.update(hand_cat_2hands, prod_cat)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING"
    assert engine.total_good == 0
    
    # Release hands in vung_cat
    for _ in range(8):
        st = engine.update([], [])
        time.sleep(0.06)
    assert engine.state == "COMPLETED"
    assert engine.total_good == 1, f"Expected 1 good, got {engine.total_good}"
    print(">>> VERIFIED: Only completed PASS once after releasing hands in vung_cat!")
    
    # 5. Worker takes new part from vung_lay -> Start Cycle 2
    time.sleep(1.6) # Banner expires
    for _ in range(4):
        st = engine.update(hand_lay, prod_lay)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 2
    assert engine.total_good == 1
    print(">>> VERIFIED: Cycle 2 started, total PASS is exactly 1 (no double count)!")
    
    print("\n========================================================")
    print(">>> PERFECT: ROTATION / NEP / DOUBLE-COUNT FULLY FIXED! <<<")
    print("========================================================")

if __name__ == "__main__":
    test_nep_rotation_and_inspection()

