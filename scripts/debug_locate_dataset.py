"""Debug script — paste vào 1 cell Colab để dò tìm dataset."""
import os, subprocess

# 1) Kiểm tra Drive có mount chưa + tìm folder yolov8
print("=== /content/drive ===")
subprocess.run(["ls", "-la", "/content/drive"], check=False)

print("\n=== MyDrive ===")
subprocess.run(["ls", "-la", "/content/drive/MyDrive"], check=False)

# 2) Tìm mọi file data.yaml trong toàn Drive
print("\n=== Tìm data.yaml trong toàn Drive ===")
result = subprocess.run(
    ["find", "/content/drive", "-name", "data.yaml", "-not", "-path", "*/.Trash/*"],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout or "(không tìm thấy)")
print("STDERR:", result.stderr[:500] if result.stderr else "")

# 3) Tìm folder tff4040
print("\n=== Tìm folder tff4040 ===")
result = subprocess.run(
    ["find", "/content/drive", "-iname", "tff4040*", "-not", "-path", "*/.Trash/*"],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout or "(không tìm thấy)")

# 4) Tìm mọi file .yaml ở top-level MyDrive
print("\n=== Tất cả .yaml ở MyDrive (top 2 level) ===")
result = subprocess.run(
    ["find", "/content/drive/MyDrive", "-maxdepth", "3", "-name", "*.yaml"],
    capture_output=True, text=True
)
print("STDOUT:", result.stdout or "(không có)")