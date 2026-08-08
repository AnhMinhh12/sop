import cv2
import numpy as np

def main():
    b1_ref = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/ref_box1.jpg")
    b1_usr = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/user_box1.jpg")
    b2_ref = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/ref_box2.jpg")
    b2_usr = cv2.imread("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/user_box2.jpg")
    
    if any(x is None for x in [b1_ref, b1_usr, b2_ref, b2_usr]):
        print("Error loading box images.")
        return
        
    # Resize all to 120x120 for grid
    sz = 120
    b1_ref_r = cv2.resize(b1_ref, (sz, sz))
    b1_usr_r = cv2.resize(b1_usr, (sz, sz))
    b2_ref_r = cv2.resize(b2_ref, (sz, sz))
    b2_usr_r = cv2.resize(b2_usr, (sz, sz))
    
    # Create grid: Row 1 = Box 1 (Ref vs User), Row 2 = Box 2 (Ref vs User)
    row1 = np.hstack([b1_ref_r, b1_usr_r])
    row2 = np.hstack([b2_ref_r, b2_usr_r])
    grid = np.vstack([row1, row2])
    
    # Add labels (draw text)
    # White background for text
    canvas = np.zeros((grid.shape[0] + 40, grid.shape[1], 3), dtype=np.uint8)
    canvas[40:] = grid
    
    cv2.putText(canvas, "B1 Ref | B1 User", (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    cv2.putText(canvas, "B2 Ref | B2 User", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/box_comparison.jpg", canvas)
    print("Saved box_comparison.jpg")

if __name__ == "__main__":
    main()
