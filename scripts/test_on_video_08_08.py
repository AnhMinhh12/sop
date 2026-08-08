import cv2
import os
import sys

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector

def main():
    model_path = "shared/models/yolo/TFF4040_final.onnx"
    video_path = "data/recordings/08_08_20260808_113003_3min.mp4"
    
    if not os.path.exists(model_path):
        print(f"Model path does not exist: {model_path}")
        return
        
    if not os.path.exists(video_path):
        print(f"Video path does not exist: {video_path}")
        return

    print(f"Loading model: {model_path}")
    detector = HandDetector("test_cam", confidence_threshold=0.35, model_path=model_path)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return
        
    print("Opened video. Reading frames...")
    frame_idx = 0
    
    # Let's save a sequence of frames when a hand is near the right button
    # The right button coordinates are roughly in the normalized region:
    # x: 0.23 to 0.30, y: 0.70 to 0.80
    
    saved_frames = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        detections = detector.detect(frame)
        hands = [d for d in detections if d.get("class") == "hand"]
        
        # Check if any hand has a centroid near the right button (x: 0.20-0.35, y: 0.65-0.85)
        near_button = False
        huge_box = False
        
        for h in hands:
            cx, cy = h["centroid"]
            bbox = h["bbox"]
            w = bbox[2] - bbox[0]
            h_box = bbox[3] - bbox[1]
            
            # If the box is extremely large (e.g. width or height > 300 pixels in a 640x480 frame)
            if w > 200 or h_box > 200:
                huge_box = True
                
            if 0.20 <= cx <= 0.35 and 0.60 <= cy <= 0.85:
                near_button = True
                
        if (near_button or huge_box) and saved_frames < 20:
            display_frame = frame.copy()
            for d in detections:
                bbox = d["bbox"]
                cls = d["class"]
                conf = d["confidence"]
                
                color = (0, 230, 20) if cls == "hand" else ((255, 0, 0) if cls == "sp" else (255, 100, 180))
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
                cv2.putText(display_frame, f"{cls} {conf:.2f} w={int(bbox[2]-bbox[0])}", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
            
            # Save frame to disk
            fn = f"frame_btn_{frame_idx}_huge_{huge_box}.jpg"
            cv2.imwrite(fn, display_frame)
            print(f"Saved {fn} with detections: {detections}")
            saved_frames += 1
            
        frame_idx += 1
        if frame_idx % 200 == 0:
            print(f"Processed {frame_idx} frames...")
            
    cap.release()
    print("Done testing.")

if __name__ == "__main__":
    main()
