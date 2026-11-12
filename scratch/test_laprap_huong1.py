import os
import sys

sys.path.insert(0, os.path.abspath("."))
from projects.sop_monitoring.core.engines.laprap_engine import ProductEngine


def make_config():
    return {
        "station_id": "machine_08",
        "station_name": "Máy IN-HOT-LAPRAP",
        "target_screws": 8,
        "missing_dwell_sec": 15.0,
        "max_cycle_time_sec": 60.0,
        "zones": {
            "vung_cat": [[0.02, 0.11], [0.30, 0.11], [0.30, 0.94], [0.02, 0.94]],
            "vung_lay": [[0.65, 0.18], [0.97, 0.18], [0.97, 0.94], [0.65, 0.94]],
        },
        "config": {"w": 1280, "h": 720, "max_cycle_time_sec": 60.0},
    }


def start_cycle(engine: ProductEngine, t: float) -> float:
    part_lay = [880, 240, 1020, 500]
    hand_lay = [{"bbox": [850, 230, 960, 420], "label": "right"}]
    prod_lay = [{"class": "part_hand", "bbox": part_lay, "confidence": 0.92}]
    for _ in range(4):
        t += 0.1
        engine.update(hand_lay, prod_lay, timestamp=t)
    assert engine.state == "ASSEMBLING", f"Expected ASSEMBLING, got {engine.state}"
    return t


def run_tests():
    # Tọa độ chuẩn các slot trên part_center [520, 180, 660, 580] (w=140, h=400)
    part_center = [520, 180, 660, 580]
    hand_side = [{"bbox": [450, 250, 515, 420], "label": "left"}]  # Tay cầm mép trái, không che các lỗ
    slot_boxes = [
        [545, 220, 560, 235],  # 0: Tier 0 Left
        [620, 220, 635, 235],  # 1: Tier 0 Right
        [545, 315, 560, 330],  # 2: Tier 1 Left (lỗ #3)
        [620, 315, 635, 330],  # 3: Tier 1 Right (lỗ #4)
        [545, 405, 560, 420],  # 4: Tier 2 Left
        [620, 405, 635, 420],  # 5: Tier 2 Right
        [545, 505, 560, 520],  # 6: Tier 3 Left
        [620, 505, 635, 520],  # 7: Tier 3 Right
    ]

    # ---------------------------------------------------------
    # TEST 1: Bốc 1 nắm 8 ốc thả dồn cục vào lòng sản phẩm -> BỊ CHẶN & BÁO NG KHI CẤT
    # ---------------------------------------------------------
    print("=== TEST 1: Thả 1 nắm 8 ốc dồn cục -> KHÔNG ĐƯỢC TÍNH ĐỦ ===")
    engine = ProductEngine(make_config())
    t = 100.0
    t = start_cycle(engine, t)

    # 8 con ốc rơi dồn ở khoảng giữa-dưới (rel_long từ 0.45 đến 0.65 -> span < 0.35)
    loose_pile = []
    for i in range(8):
        sx = 540 + (i % 4) * 20
        sy = 370 + (i // 4) * 20
        loose_pile.append({"class": "screw", "bbox": [sx, sy, sx + 12, sy + 14], "confidence": 0.75})

    for _ in range(15):  # 1.5 giây
        t += 0.1
        engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}] + loose_pile, timestamp=t)

    assert engine.loose_pile_detected is True, "Phải phát hiện cụm ốc rời!"
    assert sum(engine.slots) == 0, f"Không được bật slot nào từ cụm ốc rời, got {sum(engine.slots)}"
    assert engine.has_completed_screws is False

    # Đưa vào khay trái cất -> Phải báo NG!
    part_cat = [120, 200, 260, 580]
    hand_cat = [{"bbox": [100, 250, 200, 400], "label": "left"}]
    loose_cat = [{"class": "screw", "bbox": [150 + (i % 4) * 18, 380 + (i // 4) * 18, 162 + (i % 4) * 18, 394 + (i // 4) * 18], "confidence": 0.75} for i in range(8)]
    t += 0.1
    engine.update(hand_cat, [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}] + loose_cat, timestamp=t)
    for _ in range(5):
        t += 0.1
        engine.update([], [], timestamp=t)
    assert engine.state == "VIOLATION", f"Thả nắm ốc cất khay phải báo VIOLATION, got {engine.state}"
    assert engine.total_ng == 1
    print("=> TEST 1 PASSED!")

    # ---------------------------------------------------------
    # TEST 2: Ốc lăn qua các tầng khi nghiêng sản phẩm -> KHÔNG ĐƯỢC TÍCH LŨY ẢO
    # ---------------------------------------------------------
    print("\n=== TEST 2: Ốc lăn qua 4 tầng (0.2s/tầng) -> KHÔNG ĐƯỢC BẬT SLOT ===")
    engine = ProductEngine(make_config())
    t = 200.0
    t = start_cycle(engine, t)

    # 1 con ốc lăn lần lượt qua tất cả 8 vị trí, mỗi vị trí 2 frames (0.2s < 0.65s)
    for b in slot_boxes:
        for _ in range(2):
            t += 0.1
            engine.update(
                hand_side,
                [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}, {"class": "screw", "bbox": b, "confidence": 0.8}],
                timestamp=t,
            )
        # Khoảng trống giữa các lần lăn > 0.25s
        for _ in range(3):
            t += 0.1
            engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}], timestamp=t)

    assert sum(engine.slots) == 0, f"Ốc lăn lướt qua không được bật slot, got {engine.slots}"
    print("=> TEST 2 PASSED!")

    # ---------------------------------------------------------
    # TEST 3: Ốc lăn dừng im ở lỗ #3 (>= 0.8s), sau đó bị nhặt đi lắp vào lỗ #4 -> Lỗ #3 PHẢI BỊ XÓA!
    # ---------------------------------------------------------
    print("\n=== TEST 3: Ốc kẹt ở lỗ #3 rồi bị nhặt sang lỗ #4 -> Lỗ #3 tự xóa (chỉ còn 1/8) ===")
    engine = ProductEngine(make_config())
    t = 300.0
    t = start_cycle(engine, t)

    # Bước 3A: Con ốc rời đứng im ở lỗ #3 (slot index 2) suốt 0.9s -> máy lỡ ghi nhận lỗ #3
    for _ in range(9):
        t += 0.1
        engine.update(
            hand_side,
            [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}, {"class": "screw", "bbox": slot_boxes[2], "confidence": 0.8}],
            timestamp=t,
        )
    assert engine.slots[2] is True
    assert sum(engine.slots) == 1

    # Bước 3B: Công nhân nhặt con ốc ở lỗ #3 lắp sang lỗ #4 (slot index 3) và giữ trong 1.0s
    # Lúc này lòng máng đang mở rõ (có 1 ốc ở lỗ #4), lỗ #3 trống trơn và không bị tay che!
    for _ in range(10):
        t += 0.1
        engine.update(
            hand_side,
            [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}, {"class": "screw", "bbox": slot_boxes[3], "confidence": 0.8}],
            timestamp=t,
        )

    print(f"Sau khi nhặt từ lỗ #3 sang #4: slots = {engine.slots}, sum = {sum(engine.slots)}")
    assert engine.slots[2] is False, "LỖI: Lỗ #3 đã bị nhặt đi phải tự động reset về False!"
    assert engine.slots[3] is True, "Lỗ #4 đã lắp phải là True!"
    assert sum(engine.slots) == 1, f"Tổng số ốc chỉ được là 1, nhưng lại là {sum(engine.slots)}"
    print("=> TEST 3 PASSED!")

    # ---------------------------------------------------------
    # TEST 4: Lắp thiếu 1 con (7/8), có 1 ốc rời lăn qua lỗ #8 -> VẪN CHỈ 7/8 -> Cất báo NG!
    # ---------------------------------------------------------
    print("\n=== TEST 4: Lắp 7 ốc thật + 1 ốc lăn qua lỗ #8 -> Vẫn báo NG (7/8) ===")
    engine = ProductEngine(make_config())
    t = 400.0
    t = start_cycle(engine, t)

    screws_7 = [{"class": "screw", "bbox": b, "confidence": 0.8} for b in slot_boxes[:7]]
    for _ in range(10):
        t += 0.1
        engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}] + screws_7, timestamp=t)
    assert sum(engine.slots) == 7

    # Có con ốc lăn lướt qua lỗ #8 trong 0.2s rồi biến mất
    for _ in range(2):
        t += 0.1
        engine.update(
            hand_side,
            [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}] + screws_7 + [{"class": "screw", "bbox": slot_boxes[7], "confidence": 0.8}],
            timestamp=t,
        )
    for _ in range(5):
        t += 0.1
        engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}] + screws_7, timestamp=t)

    assert sum(engine.slots) == 7, f"Lắp thiếu 1 không được báo đủ 8! Got {sum(engine.slots)}"

    # Cất vào khay trái -> NG
    t += 0.1
    engine.update(hand_cat, [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}], timestamp=t)
    for _ in range(5):
        t += 0.1
        engine.update([], [], timestamp=t)
    assert engine.state == "VIOLATION"
    assert engine.total_ng == 1
    print("=> TEST 4 PASSED!")

    # ---------------------------------------------------------
    # TEST 5: Lắp đủ 8 ốc thật, xoay úp lưng / đóng nẹp đen che kín -> GIỮ NGUYÊN 8/8 -> PASS!
    # ---------------------------------------------------------
    print("\n=== TEST 5: Lắp đủ 8 ốc -> Đóng nẹp che kín (0 ốc lộ) -> Không bị xóa oan -> PASS ===")
    engine = ProductEngine(make_config())
    t = 500.0
    t = start_cycle(engine, t)

    screws_8 = [{"class": "screw", "bbox": b, "confidence": 0.82} for b in slot_boxes]
    for _ in range(10):
        t += 0.1
        engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.95}] + screws_8, timestamp=t)
    assert sum(engine.slots) == 8
    assert engine.has_completed_screws is True

    # Đóng nẹp đen che hết 8 ốc trong 2.0s (visible_screws = 0)
    for _ in range(20):
        t += 0.1
        engine.update(hand_side, [{"class": "part_hand", "bbox": part_center, "confidence": 0.9}], timestamp=t)
    assert sum(engine.slots) == 8, "Khi đóng nẹp che kín (0 ốc visible) KHÔNG được xóa slots!"
    assert engine.has_completed_screws is True

    # Cất vào khay trái & buông tay -> PASS
    t += 0.1
    engine.update(hand_cat, [{"class": "part_hand", "bbox": part_cat, "confidence": 0.9}], timestamp=t)
    for _ in range(5):
        t += 0.1
        engine.update([], [], timestamp=t)
    assert engine.state == "COMPLETED"
    assert engine.total_good == 1
    print("=> TEST 5 PASSED!")

    print("\n=================================================")
    print(" TAT CA 5 BAI TEST HUONG 1 DEU PASS 100%!")
    print("=================================================")


if __name__ == "__main__":
    run_tests()

