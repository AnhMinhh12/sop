import cv2
import numpy as np
import onnxruntime as ort

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    shape = img.shape[:2] # [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    # Compute padding
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1] # wh padding

    dw /= 2 # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad: # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color) # add border
    return img, r, (left, top)

def main():
    model_path = "shared/models/yolo/TFF4040.onnx"
    image_path = "C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/.tempmediaStorage/media_5a5697aa-1654-44de-b677-695a539abc47_1785835569853.jpg"
    
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    img = cv2.imread(image_path)
    if img is None:
        print("Could not read image.")
        return
        
    print(f"Original image shape: {img.shape}")
    padded, ratio, (left, top) = letterbox(img)
    print(f"Padded shape: {padded.shape}")
    
    blob = cv2.dnn.blobFromImage(padded, scalefactor=1.0/255.0, swapRB=True)
    
    outputs = sess.run(None, {sess.get_inputs()[0].name: blob})
    output = np.squeeze(outputs[0]).T # (8400, 7)
    
    hand_scores = output[:, 4]
    robot_scores = output[:, 5]
    sp_scores = output[:, 6]
    
    print("\n--- RAW MAXIMUM SCORES OVER ALL 8400 BOXES ---")
    print(f"Max Hand Score:  {np.max(hand_scores):.6f}")
    print(f"Max Robot Score: {np.max(robot_scores):.6f}")
    print(f"Max SP Score:    {np.max(sp_scores):.6f}")
    
    print("\nTop 5 SP scores and boxes:")
    top_sp_indices = np.argsort(sp_scores)[-5:][::-1]
    for idx in top_sp_indices:
        cx, cy, bw, bh = output[idx, :4]
        # Denormalize box
        x1 = (cx - bw/2 - left) / ratio
        y1 = (cy - bh/2 - top) / ratio
        x2 = (cx + bw/2 - left) / ratio
        y2 = (cy + bh/2 - top) / ratio
        print(f"  Score: {sp_scores[idx]:.6f} | Box: [{int(x1)}, {int(y1)}, {int(x2)}, {int(y2)}]")

if __name__ == "__main__":
    main()
