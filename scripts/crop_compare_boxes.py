import cv2

def main():
    ref = cv2.imread("frame_4110.jpg")
    user = cv2.imread("user_image.jpg")
    
    if ref is None or user is None:
        print("Failed to load images.")
        return
        
    ref_360 = cv2.resize(ref, (640, 360))
    user_360 = cv2.resize(user, (640, 360))
    
    # Box 1 (Top-right of mold): [341.5, 229.7, 371.8, 256.4] in 640x360
    # Box 2 (Center of mold): [307.9, 253.3, 340.4, 282.1] in 640x360
    
    # Crop with padding for context
    pad = 15
    y1_1, y2_1, x1_1, x2_1 = int(229.7 - pad), int(256.4 + pad), int(341.5 - pad), int(371.8 + pad)
    y1_2, y2_2, x1_2, x2_2 = int(253.3 - pad), int(282.1 + pad), int(307.9 - pad), int(340.4 + pad)
    
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/ref_box1.jpg", ref_360[y1_1:y2_1, x1_1:x2_1])
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/user_box1.jpg", user_360[y1_1:y2_1, x1_1:x2_1])
    
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/ref_box2.jpg", ref_360[y1_2:y2_2, x1_2:x2_2])
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/user_box2.jpg", user_360[y1_2:y2_2, x1_2:x2_2])
    
    print("Cropped Box 1 and Box 2 from both frames successfully.")

if __name__ == "__main__":
    main()
