import cv2
import os
import sys

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector

def main():
    model_path = "shared/models/yolo/max.onnx"
    video_path = "shared/tools/data/raw/07_08.mp4"
    
    print(f"Loading model: {model_path}")
    detector = HandDetector("test_cam", confidence_threshold=0.15, model_path=model_path)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video: {video_path}")
        return
        
    print("Opened video. Reading frames...")
    frame_idx = 0
    max_confs = {"hand": 0.0, "robot": 0.0, "sp": 0.0}
    saved_sp = False
    saved_robot = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        detections = detector.detect(frame)
        
        hands = [d for d in detections if d.get("class") == "hand"]
        products = [d for d in detections if d.get("class") == "sp"]
        robots = [d for d in detections if d.get("class") == "robot"]
        
        for d in detections:
            cls = d["class"]
            max_confs[cls] = max(max_confs[cls], d["confidence"])
            
        if (products and not saved_sp) or (robots and not saved_robot):
            display_frame = frame.copy()
            
            # Draw hands
            for h in hands:
                bbox = h["bbox"]
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 230, 20), 2)
                cv2.putText(display_frame, f"Hand {h['confidence']:.2f}", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 230, 20), 1, cv2.LINE_AA)
            
            # Draw products
            for p in products:
                bbox = p["bbox"]
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 0, 0), 2)
                cv2.putText(display_frame, f"Product {p['confidence']:.2f}", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)
            
            # Draw robots
            for r in robots:
                bbox = r["bbox"]
                cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 100, 180), 2)
                cv2.putText(display_frame, f"Robot {r['confidence']:.2f}", (int(bbox[0]), int(bbox[1] - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 180), 1, cv2.LINE_AA)
            
            if products and not saved_sp:
                cv2.imwrite("test_sp_detected_08.jpg", display_frame)
                print(f"Frame {frame_idx}: Saved test_sp_detected_08.jpg. Detections: {detections}")
                saved_sp = True
                
            if robots and not saved_robot:
                cv2.imwrite("test_robot_detected_08.jpg", display_frame)
                print(f"Frame {frame_idx}: Saved test_robot_detected_08.jpg. Detections: {detections}")
                saved_robot = True
                
        frame_idx += 1
        if frame_idx % 200 == 0:
            print(f"Processed {frame_idx} frames... Max confs so far: {max_confs}")
            
        if frame_idx > 2000 or (saved_sp and saved_robot):
            break
            
    print(f"Final max confidences detected: {max_confs}")
    cap.release()

if __name__ == "__main__":
    main()
