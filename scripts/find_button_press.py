import cv2
import os
import sys
import numpy as np

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projects.sop_monitoring.hand_detector import HandDetector
from shared.services.config_loader import ConfigLoader

def main():
    model_path = "shared/models/yolo/TFF4040_final.onnx"
    video_path = "data/recordings/08_08_20260808_113003_3min.mp4"
    
    detector = HandDetector("test_cam", confidence_threshold=0.15, model_path=model_path)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Failed to open video")
        return
        
    # Get button_right polygon from YAML
    sop_def = ConfigLoader.load_yaml("projects/sop_monitoring/config/TFF4040.yaml")
    poly_pts = np.array(sop_def["zones"]["button_right"], np.float32)
    
    frame_idx = 0
    w, h = 640, 480
    
    print("Scanning video for hands near button_right...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_resized = cv2.resize(frame, (w, h))
        detections = detector.detect(frame_resized)
        
        for det in detections:
            if det["class"] == "hand":
                bbox = det["bbox"]
                centroid = det["centroid"]
                # Check polygon overlap
                # We can check centroid or any corners
                test_points = [centroid, [bbox[0]/w, bbox[1]/h], [bbox[2]/w, bbox[1]/h], 
                               [bbox[0]/w, bbox[3]/h], [bbox[2]/w, bbox[3]/h]]
                
                is_in = any(cv2.pointPolygonTest(poly_pts, (pt[0], pt[1]), False) >= 0 for pt in test_points)
                if is_in:
                    box_w = bbox[2] - bbox[0]
                    box_h = bbox[3] - bbox[1]
                    print(f"Frame {frame_idx}: Hand in button_right zone! Conf: {det['confidence']:.2f}, Size: {box_w}x{box_h}")
                    
                    # Save frame
                    display_frame = frame_resized.copy()
                    cv2.rectangle(display_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 255, 0), 2)
                    # Draw button zone
                    pts_pixels = (poly_pts * np.array([w, h])).astype(int)
                    cv2.polylines(display_frame, [pts_pixels], True, (0, 0, 255), 2)
                    cv2.imwrite(f"btn_detect_{frame_idx}.jpg", display_frame)
                    
        frame_idx += 1
        
    cap.release()
    print("Done scanning.")

if __name__ == "__main__":
    main()
