import sys, os, time
sys.path.insert(0, ".")
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine

def run_suite():
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
    
    # 1. GLOVE STATIC ON TABLE (Center: X=550..620, Y=250..470)
    glove_box = [550, 250, 620, 470]
    glove_hand = [{"bbox": [540, 260, 610, 460], "label": "left"}]
    prod_glove = [{"class": "part_hand", "bbox": glove_box, "confidence": 0.9}]
    
    print("\n--- TEST 1: STATIC GLOVE LYING ON TABLE (WORKER ON BREAK) ---")
    for _ in range(30):
        st = engine.update(glove_hand, prod_glove)
        time.sleep(0.02)
    assert engine.state == "IDLE", f"Expected IDLE, got {engine.state}"
    assert engine.cycle_count == 0, f"Expected 0 cycles, got {engine.cycle_count}"
    assert engine.total_ng == 0, f"Expected 0 NG, got {engine.total_ng}"
    print(">>> TEST 1 PASSED: Static glove on table did NOT trigger cycle or NG!")
    
    # 2. WORKER REACHES TO VUNG LAY (X=800..950, Y=250..450)
    part_lay_box = [800, 250, 920, 500]
    hand_lay = [{"bbox": [780, 240, 900, 480], "label": "right"}]
    prod_lay = [{"class": "part_hand", "bbox": part_lay_box, "confidence": 0.92}]
    
    print("\n--- TEST 2: WORKER PICKS BLANK PART FROM VUNG_LAY ---")
    for _ in range(5):
        st = engine.update(hand_lay, prod_lay)
        time.sleep(0.02)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    assert engine.cycle_count == 1, f"Expected cycle 1, got {engine.cycle_count}"
    assert sum(engine.slots) == 0
    print(">>> TEST 2 PASSED: Picking part from vung_lay cleanly started Cycle 1!")
    
    # 3. WORKER ASSEMBLES SCREWS IN CENTER
    part_center = [520, 180, 640, 580]
    hand_center = [{"bbox": [480, 200, 560, 400], "label": "left"}]
    s_t0 = [([540, 220, 555, 235], 0.8), ([600, 220, 615, 235], 0.8)]
    s_t1 = [([540, 310, 555, 325], 0.8), ([600, 310, 615, 325], 0.8)]
    s_t2 = [([540, 410, 555, 425], 0.8), ([600, 410, 615, 425], 0.8)]
    s_t3 = [([540, 510, 555, 525], 0.8), ([600, 510, 615, 525], 0.8)]
    all_8_screws = [{"class": "screw", "bbox": b, "confidence": c} for b, c in (s_t0 + s_t1 + s_t2 + s_t3)]
    
    print("\n--- TEST 3: ASSEMBLE 8 SCREWS ---")
    prod_8 = [{"class": "part_hand", "bbox": part_center, "confidence": 0.95}] + all_8_screws
    for _ in range(5):
        st = engine.update(hand_center, prod_8)
        time.sleep(0.02)
    assert sum(engine.slots) == 8
    assert engine.has_completed_screws == True
    print(">>> TEST 3 PASSED: All 8 screws assembled and verified!")
    
    # 4. WORKER MOVES FINISHED PART INTO VUNG_CAT (X=150..300, Y=200..450)
    part_cat_box = [150, 200, 280, 500]
    hand_cat = [{"bbox": [140, 190, 250, 420], "label": "left"}]
    prod_cat = [{"class": "part_hand", "bbox": part_cat_box, "confidence": 0.9}]
    
    print("\n--- TEST 4: DROP IN VUNG_CAT AND RELEASE HANDS -> PASS ---")
    st = engine.update(hand_cat, prod_cat)
    assert engine.state == "ASSEMBLING", "Must still be ASSEMBLING while hands hold part in vung_cat"
    # Now hands release the part
    for _ in range(8):
        st = engine.update([], [])
        time.sleep(0.06)
    assert engine.state == "COMPLETED", f"Expected COMPLETED, got {engine.state}"
    assert engine.total_good == 1, f"Expected 1 good, got {engine.total_good}"
    assert engine.total_ng == 0
    print(">>> TEST 4 PASSED: Released hands in vung_cat confirmed PASS!")
    
    # 5. WORKER PICKS PART 2 FROM VUNG_LAY
    print("\n--- TEST 5: START CYCLE 2 FROM VUNG_LAY ---")
    for _ in range(4):
        st = engine.update(hand_lay, prod_lay)
        time.sleep(0.02)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    assert engine.cycle_count == 2, f"Expected cycle 2, got {engine.cycle_count}"
    assert sum(engine.slots) == 0
    print(">>> TEST 5 PASSED: Cycle 2 started!")
    
    print("\n==============================================")
    print(">>> ALL 5 TESTS PASSED WITH 100% SUCCESS! <<<")
    print("==============================================")

if __name__ == "__main__":
    run_suite()

