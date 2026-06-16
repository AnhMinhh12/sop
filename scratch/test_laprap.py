import sys
import os
import time

# Reconfigure stdout for UTF-8 to prevent Windows terminal encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine as LaprapEngine
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

def engine_update(engine, hands, require_prod_indices=None):
    # Determine if products should be present
    products = []
    if require_prod_indices and engine.current_step_idx in require_prod_indices:
        products = [get_product_in_zone(h["centroid"]) for h in hands]
    else:
        # Check if the step YAML requires product
        if engine.current_step_idx < len(engine.sop_steps):
            step = engine.sop_steps[engine.current_step_idx]
            if step.get("require_product", False):
                products = [get_product_in_zone(h["centroid"]) for h in hands]
    return engine.update(hands, products)

def update_sustained(engine, hands, require_prod_indices=None, duration=0.4):
    res = engine_update(engine, hands, require_prod_indices)
    time.sleep(duration)
    return engine_update(engine, hands, require_prod_indices)

def run_test():
    print("=== STARTING LAPRAP ENGINE INTEGRATION TEST ===")
    
    sop_file = "projects/sop_monitoring/config/laprap.yaml"
    sop_config = ConfigLoader.load_yaml(sop_file)
    if not sop_config:
        print("Error: Could not load laprap.yaml config!")
        sys.exit(1)
        
    engine = LaprapEngine(sop_config)
    
    # Centers of the zones computed from laprap.yaml coordinates
    hop_giua_center = [0.466, 0.732]
    thung_tren_center = [0.234, 0.689]
    thung_phai_center = [0.430, 0.482]
    
    # Test case 1: Initial state
    res = engine_update(engine, [])
    print_engine_state("Test 1 (Initial)", res, engine)
    
    # Test case 2: Hand enters hop_giua (Step 1)
    res = engine_update(engine, [get_hand_in_zone("left", hop_giua_center)])
    print_engine_state("Test 2 (Step 1 - Entry)", res, engine)
    
    # Test case 3: Dwell inside hop_giua to trigger Cycle Start
    time.sleep(0.4)
    res = engine_update(engine, [get_hand_in_zone("left", hop_giua_center)])
    print_engine_state("Test 3 (Cycle Started)", res, engine)
    assert res["sop_status"] == "processing"
    
    # Test case 3b: Keep hand inside hop_giua to complete Step 1 (dwell time >= 0.2s)
    time.sleep(0.3)
    res = engine_update(engine, [get_hand_in_zone("left", hop_giua_center)])
    print_engine_state("Test 3b (Step 1 Completed)", res, engine)
    assert res["step_index"] == 1
    
    # Test case 4: Hand withdrawn from hop_giua
    res = engine_update(engine, [])
    print_engine_state("Test 4 (Step 1 - Withdrawn)", res, engine)
    assert res["step_index"] == 1
    
    # Test case 5: Step 2 - Lấy SP2 từ thùng trên
    res = update_sustained(engine, [get_hand_in_zone("left", thung_tren_center)])
    print_engine_state("Test 5 (Step 2 - Triggered thung_tren)", res, engine)
    assert res["step_index"] == 2
    
    # Withdraw hand
    res = engine_update(engine, [])
    print_engine_state("Test 6 (Step 2 - Withdrawn)", res, engine)
    
    # Test case 6: Step 3 - Lắp SP2 vào hộp giữa
    res = update_sustained(engine, [get_hand_in_zone("left", hop_giua_center)])
    print_engine_state("Test 7 (Step 3 - Triggered hop_giua)", res, engine)
    assert res["step_index"] == 3
    
    # Withdraw hand
    res = engine_update(engine, [])
    print_engine_state("Test 8 (Step 3 - Withdrawn)", res, engine)
    
    # Test case 7: Step 4 - Đưa thành phẩm vào thùng phải (Yêu cầu có product: require_product=True)
    # We pass products to this step to satisfy require_product=True
    res = update_sustained(engine, [get_hand_in_zone("left", thung_phai_center)])
    print_engine_state("Test 9 (Step 4 - Completed)", res, engine)
    assert res["sop_status"] == "completed" or engine.current_step_idx == 4
    
    # Test case 8: Cycle restart
    time.sleep(1.6) # Wait for engine to auto-reset after completion
    res = engine_update(engine, [])
    print_engine_state("Test 10 (Post-Completion Auto-Reset)", res, engine)
    assert engine.current_step_idx == 0
    
    # Test case 9: Test violation (timeout)
    print("--- Simulating Cycle Timeout ---")
    res = update_sustained(engine, [get_hand_in_zone("left", hop_giua_center)])
    engine.cycle_start_time = time.time() - 40.0 # Force timeout (> 38s)
    res = engine_update(engine, [get_hand_in_zone("left", hop_giua_center)])
    print_engine_state("Test 11 (Cycle Timeout)", res, engine)
    assert res["sop_status"] == "violation"
    
    print("=== LAPRAP ENGINE TEST COMPLETED ===")

if __name__ == "__main__":
    run_test()
