import os
import sys
import yaml
import time

# Add root directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from projects.sop_monitoring.core.engines.TFF4040_engine import ProductEngine

def run_tests():
    # 1. Load config
    config_path = "projects/sop_monitoring/config/TFF4040.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        sop_config = yaml.safe_load(f)
    
    print("SOP Config loaded successfully.")
    
    # A point inside 'mold' zone: (0.43, 0.57)
    inside_mold = [0.43, 0.57]
    outside_mold = [0.1, 0.1]
    
    # ----------------------------------------------------
    # TEST 1: Two-handed operation (both hands enter mold)
    # ----------------------------------------------------
    print("\n=== TEST 1: TWO-HANDED OPERATION ===")
    engine = ProductEngine(sop_config)
    print(f"Engine initialized: current_step_idx = {engine.current_step_idx}, waiting_for_start = {engine.waiting_for_start}")
    
    # Frame 1: No hands -> Initializes engine timestamps
    res = engine.update([])
    print(f"Frame 1 (No hands): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, status = {res.get('status')}")
    
    # Frame 2: Both hands enter mold -> Cycle starts, waiting_for_start becomes False
    hands_both = [
        {"label": "Left", "centroid": inside_mold, "bbox": [inside_mold[0]*640-10, inside_mold[1]*480-10, inside_mold[0]*640+10, inside_mold[1]*480+10]},
        {"label": "Right", "centroid": inside_mold, "bbox": [inside_mold[0]*640-10, inside_mold[1]*480-10, inside_mold[0]*640+10, inside_mold[1]*480+10]}
    ]
    res = engine.update(hands_both)
    print(f"Frame 2 (Both hands entered): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, hit_count = {engine.hit_count}")
    
    # Frame 3: Both hands still in mold after 0.9s (dwell time OK) -> Step 1 completes
    time.sleep(0.9)
    res = engine.update(hands_both)
    print(f"Frame 3 (Both hands held in mold > 0.8s): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, hit_count = {engine.hit_count}")
    
    if engine.current_step_idx == 1:
        print("=> TEST 1 SUCCESS: Both hands completed step 1!")
    else:
        print("=> TEST 1 FAILED!")

    # ----------------------------------------------------
    # TEST 2: One-handed operation (1 hand enters mold and withdraws)
    # ----------------------------------------------------
    print("\n=== TEST 2: ONE-HANDED OPERATION (1 touch + withdrawal) ===")
    engine = ProductEngine(sop_config)
    print(f"Engine initialized: current_step_idx = {engine.current_step_idx}, waiting_for_start = {engine.waiting_for_start}")
    
    # Frame 1: No hands -> Initializes engine timestamps
    res = engine.update([])
    print(f"Frame 1 (No hands): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, status = {res.get('status')}")
    
    # Frame 2: 1 hand enters mold -> Cycle starts, hit_count = 1
    hand_one = [
        {"label": "Right", "centroid": inside_mold, "bbox": [inside_mold[0]*640-10, inside_mold[1]*480-10, inside_mold[0]*640+10, inside_mold[1]*480+10]}
    ]
    res = engine.update(hand_one)
    print(f"Frame 2 (1 hand in mold): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, hit_count = {engine.hit_count}")
    
    # Frame 3: Hand still in mold after 0.9s -> hit_count remains 1
    time.sleep(0.9)
    res = engine.update(hand_one)
    print(f"Frame 3 (1 hand still in mold > 0.8s): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, hit_count = {engine.hit_count}")
    
    # Frame 4: Hand withdrawn -> Step 1 completes (since hit_count >= 1 and hands withdrawn)
    res = engine.update([])
    print(f"Frame 4 (Hand withdrawn): step = {engine.current_step_idx}, waiting = {engine.waiting_for_start}, hit_count = {engine.hit_count}")
    
    if engine.current_step_idx == 1:
        print("=> TEST 2 SUCCESS: 1 hand touch + withdrawal completed step 1!")
    else:
        print("=> TEST 2 FAILED!")

    # ----------------------------------------------------
    # TEST 3: Return to Step 1 during Step 4 (Starts new cycle immediately)
    # ----------------------------------------------------
    print("\n=== TEST 3: RETURN TO STEP 1 (Return to mold during Step 4) ===")
    engine = ProductEngine(sop_config)
    
    # Initialize engine
    engine.update([])
    
    # Manually transition the engine state to Step 4 (index 3)
    engine.current_step_idx = 3
    engine.waiting_for_start = False
    engine.s1_withdrawn = True
    engine.last_completed_zone = 'mold'
    engine.last_completed_time = time.time() - 2.0  # Clear 1.0s grace period
    
    # Hand enters mold (Step 1 zone) during Step 4
    res = engine.update(hand_one)
    print(f"Frame B (Entered mold during Step 4): step = {engine.current_step_idx}, sop_status = {res.get('sop_status')}, failed = {engine.is_failed}")
    
    # Since returning to Step 1 starts a new cycle immediately without reporting a violation,
    # the status should be 'processing' and engine.current_step_idx should be 0.
    if res.get('sop_status') == 'processing' and engine.current_step_idx == 0 and not engine.is_failed:
        print("=> TEST 3 SUCCESS: Returning to Step 1 immediately starts a new cycle (reset to step 0) without violation!")
    else:
        print("=> TEST 3 FAILED!")

    # ----------------------------------------------------
    # TEST 4: Entering Unrelated Zone during Step 6 (Ignored)
    # ----------------------------------------------------
    print("\n=== TEST 4: ENTERING UNRELATED ZONE (Return to Step 2/left_table during Step 6) ===")
    engine = ProductEngine(sop_config)
    
    # Initialize engine
    engine.update([])
    
    # Manually transition the engine state to Step 6 (index 5)
    # Step 6 uses 'mold'. If we enter 'left_table' (Step 2 zone), it should be ignored since it's unrelated to the current or next step.
    engine.current_step_idx = 5
    engine.waiting_for_start = False
    engine.s1_withdrawn = True
    engine.last_completed_zone = 'middle_table'
    engine.last_completed_time = time.time() - 2.0  # Clear 1.0s grace period
    
    # Define hand inside 'left_table' zone
    inside_left_table = [0.41, 0.26]
    hand_left_table = [
        {"label": "Right", "centroid": inside_left_table, "bbox": [inside_left_table[0]*640-10, inside_left_table[1]*480-10, inside_left_table[0]*640+10, inside_left_table[1]*480+10]}
    ]
    
    # Update engine with hand in left_table
    res = engine.update(hand_left_table)
    print(f"Frame (Entered left_table during Step 6): step = {engine.current_step_idx}, sop_status = {res.get('sop_status')}, failed = {engine.is_failed}")
    
    # Verify we ignore other zones during Step 6 (no violation, remains at Step 6)
    if res.get('sop_status') == 'processing' and engine.current_step_idx == 5 and not engine.is_failed:
        print("=> TEST 4 SUCCESS: Entering unrelated zone (left_table) during Step 6 is correctly ignored!")
    else:
        print("=> TEST 4 FAILED!")

if __name__ == "__main__":
    run_tests()
