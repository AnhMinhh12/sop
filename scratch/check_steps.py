import cv2

video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
cap = cv2.VideoCapture(video_path)
fps = 20

# Let's save frames at 0s, 10s, 20s, 25s, 28s, 30s, 32s, 34s, 36s, 38s, 40s
for sec in [0, 10, 20, 25, 28, 30, 32, 34, 36, 38, 40]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"scratch/video_samples/step_{sec:02d}s.jpg", frame)

cap.release()
print("Saved step frames.")

