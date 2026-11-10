import time
import sys
import os

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.core.engines.loader import EngineLoader

def run_test():
    print(">>> Loading laprap config and engine...")
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    engine = EngineLoader.create_engine("laprap", sop_config)
    
    # 1. Start cycle from vung_lay (Right tray)
    for i in range(5):
        engine.update(
            hands_data=[{"bbox": [900, 300, 1050, 500]}],
            products_data=[{"bbox": [920, 320, 1020, 480], "confidence": 0.85, "class": "part_hand"}]
        )
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    print(f">>> Cycle #{engine.cycle_count} started cleanly.")

    # 2. Worker puts 2 screws in the center
    for i in range(5):
        engine.update(
            hands_data=[{"bbox": [500, 300, 680, 500]}],
            products_data=[
                {"bbox": [520, 320, 660, 480], "confidence": 0.85, "class": "part_hand"},
                {"bbox": [540, 340, 560, 360], "confidence": 0.8, "class": "screw"},
                {"bbox": [620, 340, 640, 360], "confidence": 0.8, "class": "screw"}
            ]
        )
    screw_cnt = sum(engine.slots)
    assert screw_cnt == 2, f"Expected 2 screws, got {screw_cnt}"
    print(f">>> 2 screws installed (Slots: {engine.slots})")

    # 3. ROTATION TEST: Worker rotates product in center table, screws hidden, hand wanders to right
    print("\n--- TEST: ROTATING PRODUCT ON TABLE ---")
    for step in range(15):
        # Product rotated: tilted / only 1 screw or 0 screws visible, hand at x=800 (vung_lay)
        engine.update(
            hands_data=[{"bbox": [750, 300, 850, 500]}], # Hand near right
            products_data=[{"bbox": [500, 320, 650, 480], "confidence": 0.80, "class": "part_hand"}] # 0 screws visible
        )
        assert engine.state == "ASSEMBLING", f"Failed! State became {engine.state} during rotation!"
        assert engine.total_ng == 0, f"Failed! NG triggered during rotation: {engine.total_ng}"
        assert engine.is_failed == False, "Failed! is_failed became True!"
        assert sum(engine.slots) == 2, f"Failed! Slots lost during rotation: {engine.slots}"
    print(">>> VERIFIED: Rotating product in center table NEVER triggers error! Slots strictly preserved.")

    # 4. Install remaining 6 screws -> 8/8 screws
    for t, (y1, y2) in enumerate([(380, 400), (420, 440), (450, 470)], start=1):
        for _ in range(5):
            engine.update(
                hands_data=[{"bbox": [500, 300, 680, 500]}],
                products_data=[
                    {"bbox": [520, 320, 660, 480], "confidence": 0.85, "class": "part_hand"},
                    {"bbox": [540, y1, 560, y2], "confidence": 0.8, "class": "screw"},
                    {"bbox": [620, y1, 640, y2], "confidence": 0.8, "class": "screw"}
                ]
            )
    assert sum(engine.slots) == 8, f"Expected 8 screws, got {sum(engine.slots)}"
    assert engine.has_completed_screws == True
    print(f">>> 8 screws completed (Slots: {engine.slots})")

    # 5. Worker attaches nẹp and rotates to check -> product absent or hidden for 2.0s
    print("\n--- TEST: FITTING NEP AND CHECKING (TEMPORARY ABSENCE) ---")
    for _ in range(20):
        engine.update(hands_data=[], products_data=[])
        assert engine.state == "ASSEMBLING"
        assert engine.total_ng == 0
        assert engine.total_good == 0 # Should not pass yet until in vung_cat
    print(">>> VERIFIED: Fitting nẹp and checking does NOT trigger NG or false PASS.")

    # 6. Worker carries product to vung_cat (Left crate: x = 50 to 250, < 0.30)
    print("\n--- TEST: CARRY TO VUNG_CAT AND RELEASE HANDS ---")
    for _ in range(5):
        engine.update(
            hands_data=[{"bbox": [80, 200, 260, 400]}],
            products_data=[{"bbox": [100, 220, 240, 380], "confidence": 0.85, "class": "part_hand"}]
        )
        assert engine.state == "ASSEMBLING"
        assert engine.entered_cat_zone == True

    # Worker releases hands in vung_cat (hands withdraw)
    for _ in range(10):
        time.sleep(0.05)
        engine.update(hands_data=[], products_data=[])
    
    assert engine.state == "COMPLETED", f"Expected COMPLETED, got {engine.state}"
    assert engine.total_good == 1, f"Expected 1 good, got {engine.total_good}"
    assert engine.total_ng == 0, f"Expected 0 NG, got {engine.total_ng}"
    print(f">>> VERIFIED: PASS 8/8 triggered cleanly upon releasing hands in vung_cat!")

    # 7. INCOMPLETE TEST: Worker starts Cycle #2, only puts 4 screws, genuinely puts in vung_cat and releases
    print("\n--- TEST: INCOMPLETE PART (4/8 SCREWS) STORED IN VUNG_CAT ---")
    # Wait for banner to reset to IDLE
    time.sleep(1.6)
    engine.update(hands_data=[], products_data=[])
    assert engine.state == "IDLE", f"Expected IDLE, got {engine.state}"

    # Start cycle 2
    for _ in range(4):
        engine.update(
            hands_data=[{"bbox": [900, 300, 1050, 500]}],
            products_data=[{"bbox": [920, 320, 1020, 480], "confidence": 0.85, "class": "part_hand"}]
        )
    assert engine.state == "ASSEMBLING"
    assert engine.cycle_count == 2

    # Put only 4 screws
    for _ in range(5):
        engine.update(
            hands_data=[{"bbox": [500, 300, 680, 500]}],
            products_data=[
                {"bbox": [520, 320, 660, 480], "confidence": 0.85, "class": "part_hand"},
                {"bbox": [540, 340, 560, 360], "confidence": 0.8, "class": "screw"},
                {"bbox": [620, 340, 640, 360], "confidence": 0.8, "class": "screw"},
                {"bbox": [540, 380, 560, 400], "confidence": 0.8, "class": "screw"},
                {"bbox": [620, 380, 640, 400], "confidence": 0.8, "class": "screw"}
            ]
        )
    assert sum(engine.slots) == 4

    # Worker rotates on table -> verify STILL NO NG
    for _ in range(10):
        engine.update(
            hands_data=[{"bbox": [500, 300, 680, 500]}],
            products_data=[{"bbox": [520, 320, 660, 480], "confidence": 0.85, "class": "part_hand"}]
        )
        assert engine.state == "ASSEMBLING"
        assert engine.total_ng == 0
    print(">>> VERIFIED: 4/8 screws rotating on table NEVER triggers NG.")

    # Worker now genuinely places incomplete part into vung_cat and releases hands
    for _ in range(5):
        engine.update(
            hands_data=[{"bbox": [80, 200, 260, 400]}],
            products_data=[{"bbox": [100, 220, 240, 380], "confidence": 0.85, "class": "part_hand"}]
        )
        assert engine.entered_cat_incomplete == True

    for _ in range(10):
        time.sleep(0.05)
        engine.update(hands_data=[], products_data=[])

    assert engine.state == "VIOLATION", f"Expected VIOLATION, got {engine.state}"
    assert engine.total_ng == 1, f"Expected 1 NG, got {engine.total_ng}"
    assert "Thiếu ốc (4/8)" in engine.violation_type
    print(f">>> VERIFIED: Only triggers NG at cycle end when incomplete part is stored in vung_cat!")

    print("\n==================================================================")
    print(">>> ALL TESTS PASSED 100%! ZERO FLICKERING ERRORS DURING ASSEMBLY! <<<")
    print("==================================================================")

if __name__ == "__main__":
    run_test()
