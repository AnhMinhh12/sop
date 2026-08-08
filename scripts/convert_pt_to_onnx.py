"""
Convert best.pt -> best.onnx - 1 cell doc lap
Khong phu thuoc cell nao. Paste 1 cell, Run.
"""

import os
import shutil
import subprocess
from pathlib import Path

# ==== DOI NEU KHAC ====
PT_WEIGHTS = "/content/drive/MyDrive/yolo_runs/tff4040_yolov8/exp/weights/best.pt"
OUT_DIR = "/content/drive/MyDrive/yolo_runs/tff4040_yolov8/exp/exports"
IMG_SIZE = 640
# ====================

# Buoc 1: Mount Drive (popup xin quyen se hien)
try:
    from google.colab import drive
    if not os.path.exists("/content/drive/MyDrive"):
        print("Mount Drive...")
        drive.mount('/content/drive', force_remount=False)
    else:
        print("Drive da duoc mount san.")
except ImportError:
    print("Khong chay tren Colab.")
except Exception as e:
    print(f"Loi mount: {e}")
    # Thu force_remount
    try:
        drive.mount('/content/drive', force_remount=True)
    except Exception as e2:
        print(f"Force remount cung loi: {e2}")

# Buoc 2: Cai ultralytics
print("\nCai ultralytics ...")
subprocess.run("pip install -q ultralytics>=8.2.0", shell=True, check=False)

# Buoc 3: Check file
print(f"\nFile can convert: {PT_WEIGHTS}")
if not os.path.exists(PT_WEIGHTS):
    print("KHONG TIM THAY. Dang tim best.pt tren toan Drive...")
    r = subprocess.run(
        "find /content/drive -name 'best.pt' -not -path '*/.Trash/*' 2>/dev/null",
        shell=True, capture_output=True, text=True
    )
    print("Ket qua find:")
    print(r.stdout or "(khong co)")
    print("\nKiem tra Drive da mount chua:")
    print(f"  /content/drive ton tai: {os.path.exists('/content/drive')}")
    print(f"  /content/drive/MyDrive ton tai: {os.path.exists('/content/drive/MyDrive')}")
    raise FileNotFoundError(f"Khong tim thay {PT_WEIGHTS}")

print(f"OK - {os.path.getsize(PT_WEIGHTS)/1e6:.2f} MB")

# Buoc 4: Export ONNX
print(f"\nLoading model...")
from ultralytics import YOLO
model = YOLO(PT_WEIGHTS)

print(f"Exporting ONNX (imgsz={IMG_SIZE}) ...")
model.export(format="onnx", imgsz=IMG_SIZE, simplify=True, opset=12, dynamic=False)

# Buoc 5: Copy ONNX ve Drive
# Ultralytics luu ONNX ngay cung cho voi best.pt (khong phai /content/runs/detect/exp/)
os.makedirs(OUT_DIR, exist_ok=True)

# Tim ONNX vua export - co the nam o nhieu cho
candidates = [
    Path(PT_WEIGHTS).parent / "best.onnx",     # cung folder voi best.pt
    Path("/content/runs/detect/exp/best.onnx"),
    Path("/content/runs/detect/exp1/best.onnx"),
]

found = False
for src in candidates:
    if src.exists():
        dst = Path(OUT_DIR) / src.name
        shutil.copy2(src, dst)
        found = True
        print(f"\nDA XONG: {dst}")
        print(f"Size   : {dst.stat().st_size / 1e6:.2f} MB")
        print(f"Source : {src}")

if not found:
    # Cuoi cung, find toan drive
    print("Khong thay o vi tri thuong, dang find...")
    r = subprocess.run(
        "find /content/drive -name 'best.onnx' -not -path '*/.Trash/*' 2>/dev/null",
        shell=True, capture_output=True, text=True
    )
    print("Find result:")
    print(r.stdout or "(khong co)")
    if r.stdout:
        first = Path(r.stdout.strip().split('\n')[0])
        dst = Path(OUT_DIR) / first.name
        shutil.copy2(first, dst)
        print(f"DA XONG: {dst}")

# Liet ke
print(f"\nONNX trong {OUT_DIR}:")
if os.path.isdir(OUT_DIR):
    for f in os.listdir(OUT_DIR):
        full = os.path.join(OUT_DIR, f)
        if os.path.isfile(full):
            print(f"  {f}  ({os.path.getsize(full)/1e6:.2f} MB)")

print(f"\nTai ve tai: {OUT_DIR}/best.onnx")
print("Hoac them cell: from google.colab import files; files.download('duong_dan_ben_tren')")