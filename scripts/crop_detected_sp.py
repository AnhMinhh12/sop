import cv2
import numpy as np

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    shape = img.shape[:2]
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img

def main():
    img_ref = cv2.imread("frame_4110.jpg")
    img_user = cv2.imread("user_image.jpg")
    
    if img_ref is None or img_user is None:
        print("Failed to read one of the images.")
        return
        
    padded_ref = letterbox(img_ref)
    padded_user = letterbox(img_user)
    
    # Bbox of sp detected in frame 4110 (Letterbox mode):
    # cx = 356.5, cy = 383.3, w = 31.0, h = 25.3
    cx, cy, w, h = 356.5, 383.3, 31.0, 25.3
    
    x1 = int(cx - w/2)
    y1 = int(cy - h/2)
    x2 = int(cx + w/2)
    y2 = int(cy + h/2)
    
    # Let's crop a slightly wider area (e.g. padding of 20 pixels) to see the context
    pad = 40
    crop_y1 = max(0, y1 - pad)
    crop_y2 = min(640, y2 + pad)
    crop_x1 = max(0, x1 - pad)
    crop_x2 = min(640, x2 + pad)
    
    crop_ref = padded_ref[crop_y1:crop_y2, crop_x1:crop_x2]
    crop_user = padded_user[crop_y1:crop_y2, crop_x1:crop_x2]
    
    # Save crops to artifacts
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/detected_sp_ref.jpg", crop_ref)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/detected_sp_user.jpg", crop_user)
    print("Saved crop_ref and crop_user patches.")

if __name__ == "__main__":
    main()
