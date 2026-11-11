import cv2

video_path = "data/recordings/laprap_20261103_131237_10min.mp4"
cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS) or 20

# Search around 50s-52s
for sec in [50.0, 50.5, 51.0, 51.5]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(f"scratch/original_{sec:.1f}s.jpg", frame)

cap.release()
print("Extracted original frames around 51s.")

