import cv2
import os

video_path = r"D:\Apps\SOP_HTMP\random.mp4"
print(f"Checking file: {video_path}")
print(f"Exists: {os.path.exists(video_path)}")
if os.path.exists(video_path):
    print(f"Size: {os.path.getsize(video_path)} bytes")

cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
if cap.isOpened():
    print("Successfully opened with CAP_FFMPEG")
    ret, frame = cap.read()
    print(f"Read frame: {ret}")
    cap.release()
else:
    print("Failed to open with CAP_FFMPEG")
    
cap = cv2.VideoCapture(video_path)
if cap.isOpened():
    print("Successfully opened with default backend")
    ret, frame = cap.read()
    print(f"Read frame: {ret}")
    cap.release()
else:
    print("Failed to open with default backend")
