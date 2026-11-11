import sys
import os
sys.path.append(os.path.abspath("."))

from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.core.engines.loader import EngineLoader

sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
engine = EngineLoader.create_engine("laprap", sop_config)

print("--- SUB-TEST 1: 2 tay chưa có gì, trạng thái sẵn sàng ---")
st0 = engine.get_status()
print("State:", engine.state, "| StepIdx:", st0["step_index"], "| States:", st0["step_states"], "| Msg:", st0["status_msg"])
assert engine.state == "IDLE"
assert st0["step_states"] == [False, False, False, False]
assert engine.hands_were_empty == True

print("\n--- SUB-TEST 2: 1 tay cho vào vùng lấy (khay phải) ---")
# Hand enters vung_lay (x: 900..1050 on 1280 is 0.70 .. 0.82)
hand_in_lay = [{"bbox": [900, 200, 1050, 400], "label": "right"}]
st1 = engine.update(hands_data=hand_in_lay, products_data=[])
print("State:", engine.state, "| StepIdx:", st1["step_index"], "| EnteredLay:", engine.entered_lay_zone, "| Msg:", st1["status_msg"])
assert engine.entered_lay_zone == True
assert "Đang lấy phôi" in st1["status_msg"]

print("\n--- SUB-TEST 3: Có sản phẩm trên tay -> Tính hoàn thành Bước 1 ngay lập tức ---")
# Product now on hand
part_in_hand = [{"class": "part_hand", "bbox": [910, 210, 1060, 410], "confidence": 0.88}]
st2 = engine.update(hands_data=hand_in_lay, products_data=part_in_hand)
print("State:", engine.state, "| StepIdx:", st2["step_index"], "| States:", st2["step_states"], "| Msg:", st2["status_msg"])
assert engine.state == "ASSEMBLING"
assert st2["step_index"] == 1  # Đang ở Bước 2 (Lắp ốc)
assert st2["step_states"][0] == True  # Bước 1 ĐÃ HOÀN THÀNH ✓
assert st2["cycle_count"] == 1
print("PASS: Bước 1 đã hoàn thành ngay khi có sản phẩm trên tay!")

print("\n--- SUB-TEST 4: Test chuyển tiếp chu kỳ sau khi cất phôi cũ ---")
# Simulate finishing cycle 1
engine.has_verified_8_screws = True
engine.state = "COMPLETED"
engine.get_status()
engine.banner_until = 0.0 # expire banner
# Empty hands
engine.update(hands_data=[], products_data=[])
st3 = engine.get_status()
print("After reset: State =", engine.state, "| hands_were_empty =", engine.hands_were_empty)
assert engine.hands_were_empty == True
assert engine.state == "IDLE"

# Fast pick: hand enters vung_lay and grabs part
st4 = engine.update(hands_data=hand_in_lay, products_data=part_in_hand)
print("Cycle 2 started: State =", engine.state, "| StepIdx =", st4["step_index"], "| States =", st4["step_states"])
assert engine.state == "ASSEMBLING"
assert st4["step_index"] == 1
assert st4["step_states"][0] == True
assert st4["cycle_count"] == 2
print("PASS: Chu kỳ 2 bắt đầu mượt mà, bước 1 tích xanh ngay lập tức!")

print("\nALL STEP 1 SIMPLIFICATION TESTS PASSED 100%!")

