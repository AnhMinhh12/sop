import cv2
import numpy as np

def main():
    img_empty = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_live_mold.jpg")
    img_user = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_user_mold.jpg")
    img_ref = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_ref_mold.jpg")
    
    if img_empty is None or img_user is None or img_ref is None:
        print("Failed to load one of the cropped mold images.")
        return
        
    print(f"Empty mold crop shape: {img_empty.shape}")
    print(f"User mold crop shape: {img_user.shape}")
    print(f"Ref mold crop shape:  {img_ref.shape}")
    
    # Let's resize all to 300x300 for direct comparison
    empty_res = cv2.resize(img_empty, (300, 300))
    user_res = cv2.resize(img_user, (300, 300))
    ref_res = cv2.resize(img_ref, (300, 300))
    
    # Save the resized crops so we can inspect them easily
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/compare_empty.jpg", empty_res)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/compare_user.jpg", user_res)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/compare_ref.jpg", ref_res)
    print("Resized mold comparison images saved.")

if __name__ == "__main__":
    main()
