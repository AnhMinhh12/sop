import sys, os, time
sys.path.insert(0, ".")
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine

def test_pause_talking_scenario():
    sop_config = {
        "station_id": "machine_08",
        "station_name": "Máy IN-HOT-LAPRAP",
        "target_screws": 8,
        "missing_dwell_sec": 15.0,
        "max_cycle_time_sec": 50.0,
        "zones": {
            "vung_cat": [[0.02, 0.11], [0.36, 0.11], [0.36, 0.94], [0.02, 0.94]],
            "vung_lay": [[0.60, 0.18], [0.97, 0.18], [0.97, 0.94], [0.60, 0.94]]
        },
        "config": {"w": 1280, "h": 720, "max_cycle_time_sec": 50.0}
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
    print(">>> Step 1: Cycle 1 started.")
    
    # 2. Worker installs 6 screws (nearly done: 6/8)
    part_center = [520, 180, 640, 580]
    hand_center = [{"bbox": [480, 200, 560, 400], "label": "left"}]
    s_t0 = [([540, 220, 555, 235], 0.8), ([600, 220, 615, 235], 0.8)]
    s_t1 = [([540, 310, 555, 325], 0.8), ([600, 310, 615, 325], 0.8)]
    s_t2 = [([540, 410, 555, 425], 0.8), ([600, 410, 615, 425], 0.8)]
    screws_6 = [{"class": "screw", "bbox": b, "confidence": c} for b, c in (s_t0 + s_t1 + s_t2)]
    prod_6 = [{"class": "part_hand", "bbox": part_center, "confidence": 0.95}] + screws_6
    for _ in range(5):
        engine.update(hand_center, prod_6)
    assert sum(engine.slots) == 6
    print(">>> Step 2: 6/8 screws assembled.")
    
    # 3. WORKER TURNS AROUND TO TALK ("ngoảnh ra ngoài nói chuyện") FOR 6 SECONDS
    # Hands release part, part not actively tracked
    print("\n--- TEST: WORKER PAUSES TO TALK FOR 6.0 SECONDS ---")
    t0 = time.time()
    while time.time() - t0 < 6.0:
        st = engine.update([], [])
        time.sleep(0.2)
        
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    assert engine.cycle_count == 1, f"Expected Cycle 1, got {engine.cycle_count}"
    assert engine.total_ng == 0, f"Expected 0 NG (no error while talking), got {engine.total_ng}"
    assert sum(engine.slots) == 6, f"Expected slots preserved at 6, got {sum(engine.slots)}"
    print(">>> VERIFIED: Worker pausing to talk for 6.0s did NOT trigger VIOLATION and did NOT reset slots!")
    
    # 4. WORKER TURNS BACK TO RESUME WORK ("ngoảnh lại tiếp tục")
    # Picks up the part with hands, adds screw 7 and 8
    print("\n--- TEST: WORKER TURNS BACK, FINISHES REMAINING SCREWS ---")
    s_t3 = [([540, 510, 555, 525], 0.8), ([600, 510, 615, 525], 0.8)]
    screws_8 = screws_6 + [{"class": "screw", "bbox": b, "confidence": c} for b, c in s_t3]
    prod_8 = [{"class": "part_hand", "bbox": part_center, "confidence": 0.95}] + screws_8
    for _ in range(5):
        st = engine.update(hand_center, prod_8)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 1, f"Expected still Cycle 1, got {engine.cycle_count}"
    assert sum(engine.slots) == 8
    assert engine.has_completed_screws == True
    print(">>> VERIFIED: Same cycle smoothly resumed, 8/8 screws completed!")
    
    # 5. Worker carries part to vung_cat (left zone) and releases hands
    print("\n--- TEST: CARRY TO VUNG_CAT AND RELEASE HANDS ---")
    part_cat = [150, 200, 280, 500]
    hand_cat_2hands = [
        {"bbox": [130, 220, 220, 380], "label": "left"},
        {"bbox": [210, 220, 300, 380], "label": "right"}
    ]
    prod_cat = [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}]
    # Holding
    for _ in range(5):
        st = engine.update(hand_cat_2hands, prod_cat)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING"
    assert engine.total_good == 0
    
    # Hands release in vung_cat
    for _ in range(8):
        st = engine.update([], [])
        time.sleep(0.06)
    assert engine.state == "COMPLETED"
    assert engine.total_good == 1, f"Expected 1 PASS, got {engine.total_good}"
    assert engine.total_ng == 0, f"Expected 0 NG, got {engine.total_ng}"
    print(">>> VERIFIED: Cycle cleanly finished as PASS with 0 NG!")
    
    print("\n========================================================")
    print(">>> ALL CHECKS PASSED: TALKING / PAUSE ISSUE SOLVED! <<<")
    print("========================================================")

if __name__ == "__main__":
    test_pause_talking_scenario()

