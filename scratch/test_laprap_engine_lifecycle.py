import sys
import os
import time
import numpy as np

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine

def test_lifecycle():
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = ProductEngine(sop_config)
    
    print("=== TEST 1: Initial State ===")
    status = engine.get_status()
    assert status["sop_status"] == "idle"
    assert status["cycle_count"] == 0
    assert status["step_states"] == [False, False, False, False]
    print("PASS: Initial state is IDLE.")

    print("\n=== TEST 2: Pick fresh part from vung_lay ===")
    # Part in vung_lay (x: 0.70 to 0.90), worker hand holding it
    part_box = [900, 200, 1100, 400] # x in 900..1100 on 1280 (0.70 .. 0.86)
    hand_box = [880, 180, 1000, 350]
    
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_box, "label": "right"}],
            products_data=[{"class": "part_hand", "bbox": part_box, "confidence": 0.85}]
        )
    
    status = engine.get_status()
    assert status["sop_status"] == "processing"
    assert status["cycle_count"] == 1
    assert status["step_index"] == 1 # Step 2: Lắp ráp 8 ốc
    assert status["step_states"] == [True, False, False, False]
    assert status["has_verified_8_screws"] == False
    print("PASS: Cycle started, Step 1 checked, waiting at Step 2.")

    print("\n=== TEST 3: Free Assembly (swaying, 2 screws, 4 screws) ===")
    # Worker brings part to center (x: 500..700), screws detected jittering
    part_box_center = [500, 250, 750, 450]
    hand_box_center = [480, 240, 600, 400]
    
    # 2 screws detected
    s1 = [520, 280, 540, 300]
    s2 = [580, 280, 600, 300]
    for _ in range(5):
        engine.update(
            hands_data=[{"bbox": hand_box_center, "label": "left"}],
            products_data=[
                {"class": "part_hand", "bbox": part_box_center, "confidence": 0.90},
                {"class": "screw", "bbox": s1, "confidence": 0.55},
                {"class": "screw", "bbox": s2, "confidence": 0.60}
            ]
        )
    status = engine.get_status()
    assert status["sop_status"] == "processing"
    assert status["step_index"] == 1
    assert status["has_verified_8_screws"] == False
    assert status["step_states"] == [True, False, False, False]
    print(f"PASS: During assembly with 2 screws, no false jumps. StepStates: {status['step_states']}.")

    print("\n=== TEST 4: Inspection Gesture (Worker holds part facing camera with 8 screws) ===")
    # 8 screws simultaneously detected on part_hand
    screws_8 = [
        [520 + (i % 2) * 80, 270 + (i // 2) * 40, 540 + (i % 2) * 80, 290 + (i // 2) * 40]
        for i in range(8)
    ]
    prods_8 = [{"class": "part_hand", "bbox": part_box_center, "confidence": 0.92}]
    for sb in screws_8:
        prods_8.append({"class": "screw", "bbox": sb, "confidence": 0.50})
        
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_box_center, "label": "left"}],
            products_data=prods_8
        )
    status = engine.get_status()
    assert status["has_verified_8_screws"] == True
    assert status["step_index"] == 3 # Moved to Step 4: Đóng nẹp & Cất
    assert status["step_states"] == [True, True, True, False]
    print(f"PASS: 8 screws verified! Step 1..3 checked, waiting for Step 4. StepStates: {status['step_states']}.")

    print("\n=== TEST 5: Worker puts cover strip on (screws covered) and stores into vung_cat ===")
    # Screws covered (0 screws seen now), part moves to vung_cat (x: 100..250)
    part_cat = [100, 300, 300, 500]
    hand_cat = [90, 280, 200, 450]
    
    # In vung_cat, holding
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_cat, "label": "left"}],
            products_data=[{"class": "part_hand", "bbox": part_cat, "confidence": 0.88}]
        )
    status = engine.get_status()
    assert status["sop_status"] == "processing"
    assert status["has_verified_8_screws"] == True
    assert "buông tay" in status["status_msg"].lower()
    
    # Release hands (part left in vung_cat or absent)
    engine.update(hands_data=[], products_data=[])
    time.sleep(0.4)
    status = engine.update(hands_data=[], products_data=[])
    assert status["sop_status"] == "completed"
    assert status["total_good"] == 1
    assert status["step_states"] == [True, True, True, True]
    print(f"PASS: Cycle #1 PASS! total_good = {status['total_good']}, StepStates: {status['step_states']}.")

    print("\n=== TEST 6: Draw HUD Test ===")
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    hud_frame = engine.draw_hud(dummy_frame)
    assert hud_frame.shape == (720, 1280, 3)
    print("PASS: draw_hud executed successfully.")

    print("\n=== TEST 7: NEGATIVE CASE (Missing inspection / Missing screws stored into vung_cat) ===")
    engine.reset()
    # Cycle 2 starts
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_box, "label": "right"}],
            products_data=[{"class": "part_hand", "bbox": part_box, "confidence": 0.85}]
        )
    # Worker assembles only 3 screws
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_box_center, "label": "left"}],
            products_data=[
                {"class": "part_hand", "bbox": part_box_center, "confidence": 0.90},
                {"class": "screw", "bbox": s1, "confidence": 0.55}
            ]
        )
    # Directly stores into vung_cat without inspection gesture
    for _ in range(3):
        engine.update(
            hands_data=[{"bbox": hand_cat, "label": "left"}],
            products_data=[{"class": "part_hand", "bbox": part_cat, "confidence": 0.88}]
        )
    engine.update(hands_data=[], products_data=[])
    time.sleep(0.4)
    status = engine.update(hands_data=[], products_data=[])
    assert status["sop_status"] == "violation"
    assert status["total_ng"] == 1
    assert status["is_failed"] == True
    print(f"PASS: Negative case correctly flagged VIOLATION! total_ng = {status['total_ng']}, msg: {status['status_msg']}.")

    print("\nALL LIFECYCLE TESTS PASSED 100%!")

if __name__ == "__main__":
    test_lifecycle()
