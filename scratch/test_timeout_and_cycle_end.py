import sys, os, time
sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.core.engines.loader import EngineLoader

sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
engine = EngineLoader.create_engine("laprap", sop_config)

print("=== TEST 1: REPRODUCE USER SCREENSHOT (TIMEOUT WITH 8 SCREWS VERIFIED) ===")
# Start cycle #4
hand_lay = [{"bbox": [900, 200, 1050, 400], "label": "right"}]
part_lay = [{"class": "part_hand", "bbox": [910, 210, 1060, 410], "confidence": 0.88}]
engine.update(hands_data=hand_lay, products_data=part_lay)
engine.cycle_count = 4 # match user's screenshot
assert engine.state == "ASSEMBLING"

# Set 8 screws verified
engine.has_verified_8_screws = True
engine.current_step_idx = 3
st_before = engine.get_status()
print("Before timeout:", st_before["status_msg"], "| StepIdx:", st_before["step_index"])
assert st_before["step_index"] == 3

# Fast-forward time to simulate cycle timeout (now - cycle_start_time > 60s, countdown hits 0.0s)
engine.cycle_start_time = time.time() - 65.0 # exceeded 60s!

# Next frame comes in
st_timeout = engine.update(hands_data=[], products_data=[])
print("On timeout frame:")
print(" - State:", engine.state)
print(" - SOP status:", st_timeout["sop_status"])
print(" - Step index:", st_timeout["step_index"])
print(" - Total Good:", st_timeout["total_good"])
print(" - Msg:", st_timeout["status_msg"])
assert st_timeout["sop_status"] == "completed"
assert st_timeout["total_good"] == 1
assert engine.state == "COMPLETED"
print("PASS: Hết giờ chu kỳ đã tự động chốt PASS thành công (Total Good = 1)!")

# Wait for 1.3s banner to expire
time.sleep(1.3)
st_idle = engine.get_status()
print("\nAfter banner expires:")
print(" - State:", engine.state)
print(" - SOP status:", st_idle["sop_status"])
print(" - Step index:", st_idle["step_index"])
print(" - Msg:", st_idle["status_msg"])
assert engine.state == "IDLE"
assert st_idle["step_index"] == 0
assert "Sẵn sàng" in st_idle["status_msg"]
print("PASS: Tự động chuyển về IDLE để chờ nhận Bước 1 (Lấy phôi) cho chu kỳ mới!")

print("\n=== TEST 2: WORKER REACHES TO VUNG_LAY WHILE AT STEP 4 ===")
# Start cycle #5
engine.update(hands_data=hand_lay, products_data=part_lay)
assert engine.cycle_count == 5
assert engine.state == "ASSEMBLING"
engine.has_verified_8_screws = True
engine.current_step_idx = 3

# Worker moves hand into vung_lay to pick next part
st_reach = engine.update(hands_data=hand_lay, products_data=[])
print("When worker reaches to vung_lay:")
print(" - Total Good:", engine.total_good)
print(" - State:", engine.state)
print(" - StepIdx:", st_reach["step_index"])
print(" - Msg:", st_reach["status_msg"])
assert engine.total_good == 2 # cycle 5 also counted as good!
assert engine.state == "IDLE"
assert engine.entered_lay_zone == True
assert "Đang lấy phôi" in st_reach["status_msg"]

# Worker picks new part
st_new_part = engine.update(hands_data=hand_lay, products_data=part_lay)
print("\nWhen worker picks new part:")
print(" - Cycle count:", engine.cycle_count)
print(" - State:", engine.state)
print(" - StepIdx:", st_new_part["step_index"])
print(" - StepStates:", st_new_part["step_states"])
assert engine.cycle_count == 6
assert engine.state == "ASSEMBLING"
assert st_new_part["step_index"] == 1 # Step 2 active
assert st_new_part["step_states"][0] == True # Step 1 completed!
print("PASS: Chu kỳ mới #6 lập tức bắt đầu, bước 1 tích xanh ngay lập tức!")

print("\nALL TIMEOUT AND CYCLE END TESTS PASSED 100%!")

