import sys
import os
import time

# Reconfigure stdout for UTF-8 to prevent Windows terminal encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
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

def print_engine_state(step_name, res, engine):
    print(f"--- {step_name} ---")
    print(f"SOP Status: {res.get('sop_status')}")
    print(f"Expected Step Name: {res.get('expected_step')}")
    print(f"Step Index: {res.get('step_index')} (Engine idx: {engine.current_step_idx})")
    print(f"Hit Count: {res.get('hit_count')} (Engine hit_count: {engine.hit_count})")
    print(f"S1 Withdrawn: {engine.s1_withdrawn}")
    print(f"Waiting for Start: {engine.waiting_for_start}")
    print(f"-------------------\n")

def update_sustained(engine, hands, duration=0.35):
    # First update to enter the zone
    engine.update(hands)
    # Sleep to simulate dwell time
    time.sleep(duration)
    # Second update to register the trigger
    return engine.update(hands)

def run_test():
    print("=== STARTING TFF4040 ENGINE INTEGRATION TEST ===")
    
    sop_file = "projects/sop_monitoring/config/TFF4040.yaml"
    sop_config = ConfigLoader.load_yaml(sop_file)
    if not sop_config:
        print("Error: Could not load TFF4040.yaml config!")
        sys.exit(1)
        
    engine = TFF4040Engine(sop_config)
    
    mold_center = [0.43, 0.58]
    left_table_center = [0.41, 0.26]
    jig_center = [0.35, 0.16]
    middle_center = [0.29, 0.44]
    button_right_center = [0.22, 0.73]
    
    # Test case 1
    res = engine.update([])
    print_engine_state("Test 1 (Initial)", res, engine)
    assert res["sop_status"] == "idle"

    # Test case 2
    res = engine.update([get_hand_in_zone("left", mold_center)])
    print_engine_state("Test 2 (Transient)", res, engine)
    assert res["sop_status"] == "idle"

    # Test case 3
    time.sleep(0.35)
    res = engine.update([get_hand_in_zone("left", mold_center)])
    print_engine_state("Test 3 (Dwell Start)", res, engine)
    assert res["sop_status"] == "processing"

    # Test case 4
    time.sleep(0.35)
    res = engine.update([])
    print_engine_state("Test 4 (Withdraw S1)", res, engine)
    assert res["step_index"] == 1

    # Test case 5
    res = update_sustained(engine, [get_hand_in_zone("left", left_table_center)])
    print_engine_state("Test 5 (S2 left_table)", res, engine)
    assert res["step_index"] == 2

    # Step 3
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 3 - trigger 1", res, engine)
    
    time.sleep(0.35)
    res = engine.update([])
    print_engine_state("Step 3 - withdraw 1", res, engine)
    
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 3 - trigger 2", res, engine)
    
    time.sleep(0.35)
    res = engine.update([])
    print_engine_state("Step 3 - withdraw 2", res, engine)
    
    time.sleep(0.35)
    res = engine.update([])
    print_engine_state("Step 3 - finalize", res, engine)
    assert engine.current_step_idx == 3
    
    # Step 4
    res = update_sustained(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 4", res, engine)
    assert engine.current_step_idx == 4
    
    # Step 5
    res = engine.update([get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 5 - start stay", res, engine)
    time.sleep(2.05)
    res = engine.update([get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 5 - end stay", res, engine)
    assert engine.current_step_idx == 5
    
    # Step 6
    print("--- Step 6 (multi_trigger, required_count 4) ---")
    for i in range(3):
        res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
        print_engine_state(f"Step 6 - trigger {i+1}", res, engine)
        time.sleep(0.35)
        res = engine.update([])
        print_engine_state(f"Step 6 - withdraw {i+1}", res, engine)
    
    # 4th trigger: complete Step 6 but keep hand in mold
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 6 - trigger 4 (completed)", res, engine)
    assert engine.current_step_idx == 6 # now at Step 7
    
    # Now hand remains in mold for more than 1.0 second (e.g. 1.2 seconds)
    print("--- Simulating hand remaining in mold for 1.2s without withdrawal ---")
    time.sleep(1.2)
    res = engine.update([get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 7 - Hand still in mold after 1.2s", res, engine)
    assert engine.current_step_idx == 6 # Should still be at Step 7, NOT reset!
    
    # Now withdraw hand
    res = engine.update([])
    print_engine_state("Step 7 - Hand withdrawn", res, engine)
    assert engine.s1_withdrawn == True
    
    # Step 7: Press right button
    res = update_sustained(engine, [get_hand_in_zone("left", button_right_center)])
    print_engine_state("Step 7 - press button", res, engine)
    assert engine.current_step_idx == 7

    # Test Auto-reset when hand returns to mold during Step 7
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.35)
    print_engine_state("Test Auto-Reset when hand returns to mold during Step 7", res, engine)
    assert engine.current_step_idx == 0
    assert res["sop_status"] == "processing"

    # Test Violation Reset
    print("--- Test Violation Reset ---")
    engine.is_failed = True
    engine.violation_type = "skip_step"
    res = engine.update([]) # should return violation
    print_engine_state("Violation active", res, engine)
    assert res["sop_status"] == "violation"
    
    # Simulate returning hand to Step 1 (mold)
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.25)
    print_engine_state("Violation Reset when hand returns to mold", res, engine)
    assert engine.current_step_idx == 0
    assert engine.is_failed == False
    assert res["sop_status"] == "processing"

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
