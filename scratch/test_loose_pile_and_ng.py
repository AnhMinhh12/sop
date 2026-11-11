import time
import os
import sys

sys.path.append(os.path.abspath("."))
from shared.services.config_loader import ConfigLoader
from projects.sop_monitoring.core.engines.loader import EngineLoader

def test_loose_pile_and_ng():
    sop_config = ConfigLoader.load_yaml("projects/sop_monitoring/config/laprap.yaml")
    w = 1280
    h = 720
    
    # -------------------------------------------------------------
    # TEST 1: Thả 1 nắm ốc (loose pile) -> KHÔNG ĐƯỢC tính đã kiểm tra!
    # -------------------------------------------------------------
    print("=== TEST 1: Thả 1 nắm ốc (loose pile) ===")
    engine = EngineLoader.create_engine("laprap", sop_config)
    
    # Bắt đầu lấy phôi từ khay phải
    hands = [{"class": "hand", "bbox": [1000, 300, 1150, 450], "confidence": 0.85}]
    engine.update(hands_data=hands, products_data=[])
    
    # Phôi đã trên tay tại giữa bàn
    part = [{"class": "part_hand", "bbox": [400, 200, 600, 600], "confidence": 0.85}]
    hands = [{"class": "hand", "bbox": [450, 250, 550, 350], "confidence": 0.85}]
    engine.update(hands_data=hands, products_data=part)
    assert engine.state == "ASSEMBLING", f"State must be ASSEMBLING, got {engine.state}"
    assert engine.has_verified_8_screws == False
    
    # Thả 8 con ốc chụm lại 1 chỗ (cụm bán kính 40px quanh (480, 350))
    loose_screws = []
    import random
    for i in range(8):
        sx = 480 + (i % 3) * 15
        sy = 350 + (i // 3) * 15
        loose_screws.append({"class": "screw", "bbox": [sx, sy, sx + 12, sy + 14], "confidence": 0.70})
        
    prods = part + loose_screws
    for _ in range(5):
        engine.update(hands_data=hands, products_data=prods)
        
    print(f"Sau khi đổ 8 ốc chụm lại: has_verified_8_screws = {engine.has_verified_8_screws}")
    assert engine.has_verified_8_screws == False, "LỖI! Nắm ốc chụm lại không được phép kích hoạt check đủ 8 ốc!"
    print("=> TEST 1 PASSED: Cầm nắm ốc thả vào không bị tính hoàn thành sớm!")

    # -------------------------------------------------------------
    # TEST 2: Cất thành phẩm khi chưa giơ check / thiếu ốc -> BẮT BUỘC BÁO NG!
    # -------------------------------------------------------------
    print("\n=== TEST 2: Cất phôi chưa check vào khay cất -> BÁO LỖI NG ===")
    # Đưa chi tiết vào vùng cất bên trái (x < 0.35)
    part_in_cat = [{"class": "part_hand", "bbox": [100, 200, 300, 600], "confidence": 0.85}]
    hands_cat = [{"class": "hand", "bbox": [150, 250, 250, 350], "confidence": 0.85}]
    engine.update(hands_data=hands_cat, products_data=part_in_cat)
    
    # Buông tay trong khay cất trong 0.4s
    engine.update(hands_data=[], products_data=[])
    time.sleep(0.35)
    engine.update(hands_data=[], products_data=[])
    
    print(f"Kết quả sau khi cất: State={engine.state}, Good={engine.total_good}, NG={engine.total_ng}")
    assert engine.state == "VIOLATION", f"Phải báo VIOLATION khi thiếu/chưa check, nhưng lại ra {engine.state}"
    assert engine.total_ng == 1, "Phải ghi nhận NG = 1!"
    print("=> TEST 2 PASSED: Đã bắt chính xác lỗi thiếu ốc / chưa giơ check!")

    # -------------------------------------------------------------
    # TEST 3: Giơ kiểm tra đạt chuẩn (8 ốc trải dọc thân) -> CHỐT PASS!
    # -------------------------------------------------------------
    print("\n=== TEST 3: Giơ kiểm tra 8 ốc trải dọc thân chi tiết -> PASS ===")
    # Chờ banner NG biến mất để sẵn sàng chu kỳ mới
    time.sleep(2.0)
    engine.get_status() # Trigger auto-return to IDLE
    assert engine.state == "IDLE", f"Phải tự động về IDLE, got {engine.state}"
    
    # Chu kỳ mới: Lấy phôi
    engine.update(hands_data=[{"class": "hand", "bbox": [1000, 300, 1150, 450], "confidence": 0.85}], products_data=[])
    part = [{"class": "part_hand", "bbox": [200, 100, 500, 550], "confidence": 0.85}]
    hands = [
        {"class": "hand", "bbox": [150, 150, 250, 250], "confidence": 0.85},
        {"class": "hand", "bbox": [420, 350, 520, 450], "confidence": 0.85}
    ]
    engine.update(hands_data=hands, products_data=part)
    assert engine.state == "ASSEMBLING"
    
    # 8 ốc trải dọc thân: 2 ở đầu (y=150), 4 ở giữa (y=300), 2 ở đuôi (y=450)
    # Khoảng cách tối đa = 450 - 150 = 300px >= 140px!
    installed_screws = [
        {"class": "screw", "bbox": [250, 150, 262, 164], "confidence": 0.65},
        {"class": "screw", "bbox": [270, 155, 282, 169], "confidence": 0.28}, # conf thấp 0.28 vẫn nhận!
        {"class": "screw", "bbox": [320, 290, 332, 304], "confidence": 0.60},
        {"class": "screw", "bbox": [340, 295, 352, 309], "confidence": 0.55},
        {"class": "screw", "bbox": [320, 310, 332, 324], "confidence": 0.50},
        {"class": "screw", "bbox": [340, 315, 352, 329], "confidence": 0.45},
        {"class": "screw", "bbox": [400, 440, 412, 454], "confidence": 0.58},
        {"class": "screw", "bbox": [420, 445, 432, 459], "confidence": 0.25}, # conf thấp 0.25 vẫn nhận!
    ]
    engine.update(hands_data=hands, products_data=part + installed_screws)
    print(f"Sau khi giơ check: has_verified_8_screws = {engine.has_verified_8_screws}")
    assert engine.has_verified_8_screws == True, "Phải xác nhận đủ 8 ốc khi giơ kiểm tra trải dài!"
    assert engine.current_step_idx == 3, "Phải nhảy sang Bước 4 (Đóng nẹp & Cất khay)"
    
    # Cất vào khay trái
    engine.update(hands_data=[{"class": "hand", "bbox": [100, 250, 200, 350], "confidence": 0.85}], 
                  products_data=[{"class": "part_hand", "bbox": [80, 200, 250, 550], "confidence": 0.85}])
    engine.update(hands_data=[], products_data=[])
    time.sleep(0.35)
    engine.update(hands_data=[], products_data=[])
    
    print(f"Kết quả sau khi cất 8 ốc: State={engine.state}, Good={engine.total_good}, NG={engine.total_ng}")
    assert engine.state == "COMPLETED"
    assert engine.total_good == 1
    print("=> TEST 3 PASSED: Đủ 8 ốc giơ check và cất -> PASS!")
    
    print("\n==========================================")
    print(" TẤT CẢ CÁC BÀI TEST ĐÃ VƯỢT QUA 100%!")
    print("==========================================")

if __name__ == "__main__":
    test_loose_pile_and_ng()
