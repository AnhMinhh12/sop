import cv2
import numpy as np
import onnxruntime as ort

def run_inference(sess, img_bgr, mode):
    h0, w0 = img_bgr.shape[:2]
    if mode == "stretch":
        img = cv2.resize(img_bgr, (640, 640))
        img = img.astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)[None]  # NCHW
    else: # letterbox
        # Scale ratio (new / old)
        r = min(640 / h0, 640 / w0)
        new_unpad = (int(round(w0 * r)), int(round(h0 * r)))
        dw, dh = 640 - new_unpad[0], 640 - new_unpad[1]
        dw /= 2
        dh /= 2
        resized = cv2.resize(img_bgr, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
        img = padded.astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)[None]  # NCHW
        
    outputs = sess.run(None, {sess.get_inputs()[0].name: img})
    pred = np.squeeze(outputs[0]).T # (8400, 7)
    return pred

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    image_path = "C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/.tempmediaStorage/media_5a5697aa-1654-44de-b677-695a539abc47_1785835569853.jpg"
    
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    img = cv2.imread(image_path)
    if img is None:
        print("Could not read image.")
        return
        
    for mode in ["stretch", "letterbox"]:
        print(f"\n================ Mode: {mode.upper()} ================")
        pred = run_inference(sess, img, mode)
        hand_scores = pred[:, 4]
        robot_scores = pred[:, 5]
        sp_scores = pred[:, 6]
        
        print(f"Max Hand Score:  {np.max(hand_scores):.6f}")
        print(f"Max Robot Score: {np.max(robot_scores):.6f}")
        print(f"Max SP Score:    {np.max(sp_scores):.6f}")
        
        # Check if there are any detections above 0.05
        class_names = ["hand", "robot", "sp"]
        for cls_idx, name in enumerate(class_names):
            scores = pred[:, 4 + cls_idx]
            top_idx = np.argmax(scores)
            max_s = scores[top_idx]
            if max_s > 0.05:
                print(f"  Detected {name} with conf {max_s:.4f} at anchor {top_idx}")
            else:
                print(f"  No {name} detected above 0.05 (best was {max_s:.4f})")

if __name__ == "__main__":
    main()
