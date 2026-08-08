import cv2
import numpy as np
import onnxruntime as ort

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    image_path = "test_live_camera.jpg"
    conf_threshold = 0.15
    iou_threshold = 0.3
    
    print(f"Loading model: {model_path}")
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Failed to read image {image_path}")
        return
        
    h, w = frame.shape[:2]
    # Preprocess
    input_size = 640
    r = min(input_size / h, input_size / w)
    new_unproc = (int(round(w * r)), int(round(h * r)))
    dw, dh = input_size - new_unproc[0], input_size - new_unproc[1]
    dw, dh = dw / 2, dh / 2
    
    img = cv2.resize(frame, new_unproc, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
    
    blob = cv2.dnn.blobFromImage(img, scalefactor=1.0/255.0, swapRB=True)
    
    # Inference
    outputs = sess.run(None, {input_name: blob})
    output = np.squeeze(outputs[0])
    output = output.T # shape: (8400, 4 + num_classes)
    
    num_classes = output.shape[1] - 4
    class_mapping = {0: "hand", 1: "robot", 2: "sp"}
    class_colors = {0: (0, 255, 0), 1: (255, 0, 255), 2: (0, 165, 255)}  # Green for hand, Pink for robot, Orange for sp
    
    all_detections = []
    for class_idx in range(num_classes):
        confidences = output[:, 4 + class_idx]
        mask = confidences > conf_threshold
        if not np.any(mask):
            continue
            
        class_output = output[mask]
        class_confs = confidences[mask]
        
        # Coordinates
        x1 = (class_output[:, 0] - class_output[:, 2] / 2 - left) / r
        y1 = (class_output[:, 1] - class_output[:, 3] / 2 - top) / r
        bw = class_output[:, 2] / r
        bh = class_output[:, 3] / r
        
        boxes = np.stack([x1, y1, bw, bh], axis=1).astype(int).tolist()
        confs = class_confs.astype(float).tolist()
        
        indices = cv2.dnn.NMSBoxes(boxes, confs, conf_threshold, iou_threshold)
        if len(indices) > 0:
            for idx in indices.flatten():
                box = boxes[idx]
                all_detections.append({
                    "class_idx": class_idx,
                    "class": class_mapping.get(class_idx, f"cls{class_idx}"),
                    "confidence": confs[idx],
                    "bbox": [box[0], box[1], box[0] + box[2], box[1] + box[3]]
                })
                
    print(f"Detections: {all_detections}")
    
    # Draw boxes
    for det in all_detections:
        cls_idx = det["class_idx"]
        cls_name = det["class"]
        conf = det["confidence"]
        bbox = det["bbox"]
        color = class_colors.get(cls_idx, (255, 255, 255))
        
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
        label = f"{cls_name} {conf:.2f}"
        cv2.putText(frame, label, (bbox[0], bbox[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        
    cv2.imwrite("test_live_camera_annotated.jpg", frame)
    print("Saved annotated frame to test_live_camera_annotated.jpg")

if __name__ == "__main__":
    main()
