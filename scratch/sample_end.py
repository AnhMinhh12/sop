import cv2
import os

video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 20

out_dir = "scratch/cycle_end_sample"
os.makedirs(out_dir, exist_ok=True)

for sec in [68, 70, 72, 74, 76, 78, 80, 82, 85]:
    frame_no = int(sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"{out_dir}/sec_{sec}.jpg", frame)
        print(f"Saved sec_{sec}.jpg")

cap.release()

