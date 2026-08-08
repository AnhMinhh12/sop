import cv2
import numpy as np
import onnxruntime as ort

def run_inference(sess, img_bgr, preprocess_mode):
    input_name = sess.get_inputs()[0].name
    h, w = img_bgr.shape[:2]
    
    if preprocess_mode == "stretch":
        # Direct resize to 640x640
        img = cv2.resize(img_bgr, (640, 640))
        blob = cv2.dnn.blobFromImage(img, scalefactor=1.0/255.0, swapRB=True)
        r = w / 640
        pad_left, pad_top = 0.0, 0.0
    else: # letterbox
        # Resize keeping aspect ratio, pad to 640x640
        r_scale = min(640 / h, 640 / w)
        new_unproc = (int(round(w * r_scale)), int(round(h * r_scale)))
        dw, dh = 640 - new_unproc[0], 640 - new_unproc[1]
        dw, dh = dw / 2, dh / 2
        img = cv2.resize(img_bgr, new_unproc, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        blob = cv2.dnn.blobFromImage(img, scalefactor=1.0/255.0, swapRB=True)
        r = 1.0 / r_scale
        pad_left, pad_top = left, top
        
    outputs = sess.run(None, {input_name: blob})
    output = np.squeeze(outputs[0]).T # (8400, 7)
    
    num_classes = output.shape[1] - 4
    if num_classes == 2:
        class_mapping = {0: "hand", 1: "sp"}
    else:
        class_mapping = {0: "hand", 1: "robot", 2: "sp"}
    conf_threshold = 0.01
    iou_threshold = 0.3
    
    detections = []
    for class_idx in range(num_classes):
        confidences = output[:, 4 + class_idx]
        mask = confidences > conf_threshold
        if not np.any(mask):
            continue
            
        class_output = output[mask]
        class_confs = confidences[mask]
        
        if preprocess_mode == "stretch":
            x1 = (class_output[:, 0] - class_output[:, 2] / 2) * (w / 640)
            y1 = (class_output[:, 1] - class_output[:, 3] / 2) * (h / 640)
            bw = class_output[:, 2] * (w / 640)
            bh = class_output[:, 3] * (h / 640)
        else:
            x1 = (class_output[:, 0] - class_output[:, 2] / 2 - pad_left) / r_scale
            y1 = (class_output[:, 1] - class_output[:, 3] / 2 - pad_top) / r_scale
            bw = class_output[:, 2] / r_scale
            bh = class_output[:, 3] / r_scale
            
        boxes = np.stack([x1, y1, bw, bh], axis=1).astype(int).tolist()
        confs = class_confs.astype(float).tolist()
        
        indices = cv2.dnn.NMSBoxes(boxes, confs, conf_threshold, iou_threshold)
        if len(indices) > 0:
            for idx in indices.flatten():
                box = boxes[idx]
                detections.append({
                    "class": class_mapping.get(class_idx, f"cls{class_idx}"),
                    "confidence": confs[idx],
                    "bbox": [box[0], box[1], box[0] + box[2], box[1] + box[3]]
                })
    return detections

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    image_path = "test_live_camera.jpg"
    
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    img = cv2.imread(image_path)
    if img is None:
        print("Could not read image.")
        return
        
    print("--- PREPROCESSING COMPARISON ---")
    
    print("\n[Mode: STRETCH]")
    dets_stretch = run_inference(sess, img, "stretch")
    for d in dets_stretch:
        print(f"  {d['class']}: conf={d['confidence']:.4f}, bbox={d['bbox']}")
        
    print("\n[Mode: LETTERBOX]")
    dets_letterbox = run_inference(sess, img, "letterbox")
    for d in dets_letterbox:
        print(f"  {d['class']}: conf={d['confidence']:.4f}, bbox={d['bbox']}")

if __name__ == "__main__":
    main()
