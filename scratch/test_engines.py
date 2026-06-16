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

def get_product_in_zone(centroid):
    w, h = 640, 480
    cx_pix = int(centroid[0] * w)
    cy_pix = int(centroid[1] * h)
    return {
        "class": "product",
        "centroid": centroid,
        "bbox": [cx_pix - 20, cy_pix - 20, cx_pix + 20, cy_pix + 20],
        "confidence": 0.8
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

def engine_update(engine, hands):
    products = [get_product_in_zone(h["centroid"]) for h in hands]
    return engine.update(hands, products)

def update_sustained(engine, hands, duration=0.35):
    products = [get_product_in_zone(h["centroid"]) for h in hands]
    engine.update(hands, products)
    time.sleep(duration)
    return engine.update(hands, products)

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
    button_right_center = [0.20, 0.79]
    
    # Test case 1
    res = engine_update(engine, [])
    print_engine_state("Test 1 (Initial)", res, engine)
    assert res["sop_status"] == "idle"

    # Test case 2
    res = engine_update(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Test 2 (Transient)", res, engine)
    assert res["sop_status"] == "idle"

    # Test case 3
    time.sleep(0.35)
    res = engine_update(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Test 3 (Dwell Start)", res, engine)
    assert res["sop_status"] == "processing"

    # Test case 4
    time.sleep(0.35)
    res = engine_update(engine, [])
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
    res = engine_update(engine, [])
    print_engine_state("Step 3 - withdraw 1", res, engine)
    
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 3 - trigger 2", res, engine)
    
    time.sleep(0.35)
    res = engine_update(engine, [])
    print_engine_state("Step 3 - withdraw 2", res, engine)
    
    time.sleep(0.35)
    res = engine_update(engine, [])
    print_engine_state("Step 3 - finalize", res, engine)
    assert engine.current_step_idx == 3
    
    # Step 4
    res = update_sustained(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 4", res, engine)
    assert engine.current_step_idx == 4
    
    # Step 5
    res = engine_update(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 5 - start stay", res, engine)
    time.sleep(2.05)
    res = engine_update(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    print_engine_state("Step 5 - end stay", res, engine)
    assert engine.current_step_idx == 5
    
    # Step 6
    print("--- Step 6 (multi_trigger, required_count 4) ---")
    for i in range(3):
        res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
        print_engine_state(f"Step 6 - trigger {i+1}", res, engine)
        time.sleep(0.35)
        res = engine_update(engine, [])
        print_engine_state(f"Step 6 - withdraw {i+1}", res, engine)
    
    # 4th trigger: complete Step 6 but keep hand in mold
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 6 - trigger 4 (completed)", res, engine)
    assert engine.current_step_idx == 6 # now at Step 7
    
    # Now hand remains in mold for more than 1.0 second (e.g. 1.2 seconds)
    print("--- Simulating hand remaining in mold for 1.2s without withdrawal ---")
    time.sleep(1.2)
    res = engine_update(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Step 7 - Hand still in mold after 1.2s", res, engine)
    assert engine.current_step_idx == 6 # Should still be at Step 7, NOT reset!
    
    # Now withdraw hand
    res = engine_update(engine, [])
    print_engine_state("Step 7 - Hand withdrawn", res, engine)
    assert engine.s1_withdrawn == True
    
    # Step 7: Press right button (no require_product)
    res = update_sustained(engine, [get_hand_in_zone("left", button_right_center)])
    print_engine_state("Step 7 - press button", res, engine)
    assert engine.current_step_idx == 7

    # Simulate hand empty for 2.6 seconds (machine is pressing, operator waiting/withdrawing)
    res = update_sustained(engine, [], duration=2.6)
    print_engine_state("Step 8 - Waiting after button press", res, engine)

    # Test that returning to mold when current_step_idx >= 6 triggers skip_step violation
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.35)
    print_engine_state("Violation triggered when returning to mold during Step 8", res, engine)
    assert engine.current_step_idx == 7
    assert res["sop_status"] == "violation"
    assert res["violation_type"] == "skip_step"

    # Subsequent frame resets engine to Step 1 (index 0)
    res = engine_update(engine, [get_hand_in_zone("left", mold_center)])
    print_engine_state("Engine reset to Step 1 on subsequent frame", res, engine)
    assert engine.current_step_idx == 0
    assert res["sop_status"] == "processing"
    assert engine.is_failed == False

    # Test Violation Reset
    print("--- Test Violation Reset ---")
    engine.is_failed = True
    engine.violation_type = "skip_step"
    res = engine_update(engine, []) # should return violation
    print_engine_state("Violation active", res, engine)
    assert res["sop_status"] == "violation"
    
    # Simulate returning hand to Step 1 (mold)
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.25)
    print_engine_state("Violation Reset when hand returns to mold", res, engine)
    assert engine.current_step_idx == 0
    assert engine.is_failed == False
    assert res["sop_status"] == "processing"

    print("ALL TESTS PASSED SUCCESSFULLY!")

def run_test_step7_relaxation():
    print("=== STARTING TFF4040 STEP 7 RELAXATION TEST ===")
    sop_file = "projects/sop_monitoring/config/TFF4040.yaml"
    sop_config = ConfigLoader.load_yaml(sop_file)
    engine = TFF4040Engine(sop_config)
    
    # Initialize engine last_update_time
    engine_update(engine, [])
    
    mold_center = [0.43, 0.58]
    left_table_center = [0.41, 0.26]
    middle_center = [0.29, 0.44]
    
    # Step 1: 1 hit + withdraw
    update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    time.sleep(0.35)
    engine_update(engine, [])
    assert engine.current_step_idx == 1
    
    # Step 2: 1 hit (dwell)
    update_sustained(engine, [get_hand_in_zone("left", left_table_center)])
    assert engine.current_step_idx == 2
    
    # Step 3: 1 hit + withdraw
    update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    time.sleep(0.35)
    engine_update(engine, [])
    assert engine.current_step_idx == 3
    
    # Step 4: 1 hit (dwell)
    update_sustained(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)])
    assert engine.current_step_idx == 4
    
    # Step 5: stay 2.1s
    update_sustained(engine, [get_hand_in_zone("left", middle_center), get_hand_in_zone("right", middle_center)], duration=2.1)
    assert engine.current_step_idx == 5
    
    # Step 6: 4 hits
    for i in range(3):
        update_sustained(engine, [get_hand_in_zone("left", mold_center)])
        time.sleep(0.35)
        engine_update(engine, [])
    update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    assert engine.current_step_idx == 6 # now at Step 7 (button press)
    
    # Withdraw hand
    time.sleep(0.35)
    engine_update(engine, [])
    
    # Instead of pressing button, go directly to Step 8 zone (left_table)
    print("--- Simulating hand going directly to left_table (Step 8 zone) while at Step 7 ---")
    res = update_sustained(engine, [get_hand_in_zone("left", left_table_center)], duration=0.25)
    print_engine_state("Step 7 auto-completed via Step 8 detection", res, engine)
    
    assert engine.current_step_idx == 7
    assert res["sop_status"] == "processing"
    print("STEP 7 RELAXATION TEST PASSED!")

def run_test_mid_cycle_restart():
    print("=== STARTING TFF4040 MID-CYCLE RESTART TEST ===")
    sop_file = "projects/sop_monitoring/config/TFF4040.yaml"
    sop_config = ConfigLoader.load_yaml(sop_file)
    engine = TFF4040Engine(sop_config)
    
    # Initialize engine last_update_time
    engine_update(engine, [])
    
    mold_center = [0.43, 0.58]
    left_table_center = [0.41, 0.26]
    middle_center = [0.29, 0.44]
    
    # Step 1: 1 hit + withdraw
    update_sustained(engine, [get_hand_in_zone("left", mold_center)])
    time.sleep(0.35)
    engine_update(engine, [])
    assert engine.current_step_idx == 1
    
    # Step 2: 1 hit (dwell)
    update_sustained(engine, [get_hand_in_zone("left", left_table_center)])
    assert engine.current_step_idx == 2
    
    # Now at Step 3 (Lấy 2 Slider từ khuôn).
    # Since Step 3 requires 'mold', putting the hand in the mold should NOT cause a violation.
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.25)
    assert engine.current_step_idx == 2
    assert res["sop_status"] == "processing"
    
    # Complete Step 3 (withdraw to complete)
    time.sleep(0.35)
    engine_update(engine, [])
    assert engine.current_step_idx == 3 # Now at Step 4
    
    # Withdraw hand
    time.sleep(0.35)
    engine_update(engine, [])
    
    # Wait for grace period (>2.5s) to expire so return-to-mold restart can trigger
    time.sleep(2.6)
    
    # At Step 4, if they return to mold (Step 1) and stay there, it should trigger a skip_step violation!
    print("--- Simulating return to mold at Step 4 (abandoning cycle) ---")
    res = update_sustained(engine, [get_hand_in_zone("left", mold_center)], duration=0.35)
    print_engine_state("Violation triggered when returning to mold during Step 4", res, engine)
    assert engine.current_step_idx == 3
    assert res["sop_status"] == "violation"
    assert res["violation_type"] == "skip_step"
    
    # Subsequent frame resets engine to Step 1
    res = engine_update(engine, [get_hand_in_zone("left", mold_center)])
    assert engine.current_step_idx == 0
    assert res["sop_status"] == "processing"
    print("MID-CYCLE RESTART TEST PASSED!")

if __name__ == "__main__":
    run_test()
    run_test_step7_relaxation()
    run_test_mid_cycle_restart()
