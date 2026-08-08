from ultralytics import YOLO
import cv2

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    model = YOLO(model_path, task="detect")
    
    # 1. Visualize frame 4110 (threshold 0.15)
    img_ref = cv2.imread("frame_4110.jpg")
    res_ref = model.predict(img_ref, conf=0.15, verbose=False)
    annotated_ref = res_ref[0].plot()
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/detected_ref.jpg", annotated_ref)
    print("Saved detected_ref.jpg")
    
    # 2. Visualize user image with very low threshold (0.001) to see any weak detections
    img_user = cv2.imread("user_image.jpg")
    res_user = model.predict(img_user, conf=0.001, verbose=False)
    annotated_user = res_user[0].plot()
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/detected_user_low_conf.jpg", annotated_user)
    print("Saved detected_user_low_conf.jpg")

if __name__ == "__main__":
    main()
