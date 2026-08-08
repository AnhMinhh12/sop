from ultralytics import YOLO
import cv2

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    # Load YOLO model
    model = YOLO(model_path, task="detect")
    
    # Test on frame 4110
    print("\n--- ULTRALYTICS INFERENCE ON FRAME 4110 ---")
    res_ref = model.predict("frame_4110.jpg", conf=0.01, verbose=False)
    for r in res_ref:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            print(f"  Class: {r.names[cls]} ({cls}) | Conf: {conf:.4f} | Bbox: {xyxy}")
            
    # Test on user image
    print("\n--- ULTRALYTICS INFERENCE ON USER IMAGE ---")
    res_user = model.predict("user_image.jpg", conf=0.01, verbose=False)
    for r in res_user:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            print(f"  Class: {r.names[cls]} ({cls}) | Conf: {conf:.4f} | Bbox: {xyxy}")

if __name__ == "__main__":
    main()
