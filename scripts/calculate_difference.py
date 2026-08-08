import cv2
import numpy as np

def main():
    empty = cv2.imread("compare_empty.jpg")
    user = cv2.imread("compare_user.jpg")
    ref = cv2.imread("compare_ref.jpg")
    
    if empty is None or user is None or ref is None:
        print("Failed to load images.")
        return
        
    # Convert to grayscale
    empty_gray = cv2.cvtColor(empty, cv2.COLOR_BGR2GRAY)
    user_gray = cv2.cvtColor(user, cv2.COLOR_BGR2GRAY)
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    
    # Calculate absolute difference between empty and user, and empty and ref
    diff_empty_user = cv2.absdiff(empty_gray, user_gray)
    diff_empty_ref = cv2.absdiff(empty_gray, ref_gray)
    
    print(f"Mean pixel difference (Empty vs User): {np.mean(diff_empty_user):.2f}")
    print(f"Mean pixel difference (Empty vs Ref):  {np.mean(diff_empty_ref):.2f}")
    print(f"Mean pixel difference (User vs Ref):   {np.mean(cv2.absdiff(user_gray, ref_gray)):.2f}")
    
    # Let's save the diff images so we can verify them
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/diff_user.jpg", diff_empty_user)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/diff_ref.jpg", diff_empty_ref)
    print("Diff images saved.")

if __name__ == "__main__":
    main()
