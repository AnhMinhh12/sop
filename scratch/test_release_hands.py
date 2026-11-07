import sys, os, time
sys.path.insert(0, ".")
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine

def test_release_hands_in_cat_zone():
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
    
    # 1. Pick part from vung_lay
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
    print(">>> Phase 1: 8 screws assembled.")
    
    # 3. Bring product to vung_cat, but STILL HOLDING with 2 hands!
    part_cat = [150, 200, 280, 500] # In vung_cat
    hand_cat_2hands = [
        {"bbox": [130, 220, 220, 380], "label": "left"},
        {"bbox": [210, 220, 300, 380], "label": "right"}
    ]
    prod_cat = [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}]
    
    print("\n--- TEST: STILL HOLDING PRODUCT IN VUNG_CAT (DO NOT FINISH YET) ---")
    for _ in range(8):
        st = engine.update(hand_cat_2hands, prod_cat)
        time.sleep(0.05)
    
    # MUST STILL BE ASSEMBLING (NOT COMPLETED!)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING while holding, got {engine.state}"
    assert engine.total_good == 0, f"Expected 0 total_good while holding, got {engine.total_good}"
    assert engine.entered_cat_zone == True
    print(">>> VERIFIED: Cycle is NOT closed while worker is still holding the part with 2 hands in vung_cat!")
    
    # 4. Worker releases product ("rời khỏi 2 tay ở vùng trái")
    print("\n--- TEST: RELEASE FROM BOTH HANDS IN VUNG_CAT -> COMPLETED PASS ---")
    # Hands let go: no hands holding the part (or hands withdrew from vung_cat)
    for _ in range(8):
        st = engine.update([], []) # Hands let go and pulled back
        time.sleep(0.06)
        
    assert engine.state == "COMPLETED", f"Expected COMPLETED after releasing hands, got {engine.state}"
    assert engine.total_good == 1, f"Expected 1 total_good, got {engine.total_good}"
    print(">>> VERIFIED: Cycle cleanly COMPLETED as PASS only AFTER hands released the product in vung_cat!")
    
    # 5. Worker takes new part from vung_lay -> Start Cycle 2
    time.sleep(1.6) # Banner expires
    for _ in range(4):
        st = engine.update(hand_lay, prod_lay)
        time.sleep(0.05)
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 2
    assert sum(engine.slots) == 0
    print(">>> VERIFIED: Cycle 2 started from vung_lay seamlessly!")
    
    print("\n========================================================")
    print(">>> ALL TESTS FOR USER'S EXACT REQUIREMENT PASSED 100%! <<<")
    print("========================================================")

if __name__ == "__main__":
    test_release_hands_in_cat_zone()

