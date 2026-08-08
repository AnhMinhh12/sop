"""Debug: dò tìm best.pt trên Drive"""
import os
import subprocess

def sh(cmd):
    print(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=False, text=True)

# 1) Mount Drive (nếu chưa mount)
try:
    from google.colab import drive
    if not os.path.exists("/content/drive/MyDrive"):
        drive.mount('/content/drive')
except ImportError:
    print("Không chạy trên Colab")

# 2) Liệt kê cấu trúc yolo_runs
print("\n=== ls /content/drive/MyDrive/ ===")
sh("ls -la /content/drive/MyDrive/")

print("\n=== ls yolo_runs ===")
sh("ls -la /content/drive/MyDrive/yolo_runs/ 2>/dev/null || echo '(không có yolo_runs)'")

print("\n=== ls yolo_runs/tff4040_yolov8 ===")
sh("ls -la /content/drive/MyDrive/yolo_runs/tff4040_yolov8/ 2>/dev/null || echo '(không có)'")

# 3) Tìm mọi file best.pt trên toàn Drive
print("\n=== find best.pt (toàn Drive, không tính Trash) ===")
r = subprocess.run(
    ["find", "/content/drive", "-name", "best.pt", "-not", "-path", "*/.Trash/*"],
    capture_output=True, text=True
)
print(r.stdout or "(không có)")

# 4) Tìm mọi folder yolo_runs
print("\n=== find yolo_runs ===")
r = subprocess.run(
    ["find", "/content/drive", "-name", "yolo_runs", "-type", "d",
     "-not", "-path", "*/.Trash/*"],
    capture_output=True, text=True
)
print(r.stdout or "(không có)")

# 5) Tìm mọi file .pt
print("\n=== find *.pt ===")
r = subprocess.run(
    ["find", "/content/drive/MyDrive", "-maxdepth", "6", "-name", "*.pt",
     "-not", "-path", "*/.Trash/*"],
    capture_output=True, text=True
)
print(r.stdout or "(không có)")