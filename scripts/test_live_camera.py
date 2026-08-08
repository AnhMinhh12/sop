import cv2
import numpy as np
import onnxruntime as ort
import time

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    rtsp_url = "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102"
    conf_threshold = 0.15
    iou_threshold = 0.3
    
    print(f"Loading model: {model_path}")
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    
    print(f"Connecting to RTSP stream: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print("Failed to open RTSP stream.")
        return
        
    print("Successfully connected. Processing 30 frames...")
    
    class_mapping = {0: "hand", 1: "robot", 2: "sp"}
    
    for i in range(30):
        ret, frame = cap.read()
        if not ret:
            print(f"Frame {i}: Failed to read frame.")
            time.sleep(0.1)
            continue
            
        h, w = frame.shape[:2]
        # Preprocess
        input_size = 640  # Model TFF4040.onnx input size is 640
        # Resize with letterbox (keep aspect ratio)
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
                        "class": class_mapping.get(class_idx, f"cls{class_idx}"),
                        "confidence": confs[idx],
                        "bbox": [box[0], box[1], box[0] + box[2], box[1] + box[3]]
                    })
                    
        print(f"Frame {i}: Detections: {all_detections}")
        
    cap.release()

if __name__ == "__main__":
    main()
