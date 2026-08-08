import cv2

def main():
    video_path = "data/recordings/30_20260730_081531_10min.mp4"
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Failed to open video.")
        return
        
    target_frame = 4110
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/sp_reference_frame.jpg", frame)
        print(f"Saved frame #{target_frame} to sp_reference_frame.jpg")
    else:
        print("Failed to extract frame.")
    cap.release()

if __name__ == "__main__":
    main()
