import cv2
import os

video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 25
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"FPS: {fps}, Total frames: {total_frames}, Duration: {total_frames/fps:.1f}s")

out_dir = "scratch/video_samples"
os.makedirs(out_dir, exist_ok=True)

for sec in [5, 15, 30, 45, 60, 80, 100]:
    frame_no = int(sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"{out_dir}/sample_{sec}s.jpg", frame)
        print(f"Saved {sec}s")

cap.release()

