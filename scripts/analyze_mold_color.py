import cv2
import numpy as np

def main():
    img_ref = cv2.imread("frame_4110.jpg")
    img_user = cv2.imread("user_image.jpg")
    
    if img_ref is None or img_user is None:
        print("Failed to read one of the images.")
        return
        
    print(f"Ref Image shape: {img_ref.shape}")
    print(f"User Image shape: {img_user.shape}")
    
    # Crop regions for top and bottom cavities (in 640x360 coordinates)
    # Ref image is 1280x720, User image is 640x360
    # Let's resize both to 640x360 for consistent coordinate analysis
    ref_360 = cv2.resize(img_ref, (640, 360))
    user_360 = cv2.resize(img_user, (640, 360))
    
    # We will crop around the top cavity (approx [310:350, 310:350] in 640x360 coordinates)
    # and bottom cavity (approx [250:290, 290:330])
    # Let's save these small patches to verify they capture the cavities
    
    # Top cavity center area
    top_y1, top_y2 = 240, 275
    top_x1, top_x2 = 310, 345
    
    # Bottom cavity center area
    bot_y1, bot_y2 = 205, 235
    bot_x1, bot_x2 = 280, 310
    
    patch_ref_top = ref_360[top_y1:top_y2, top_x1:top_x2]
    patch_user_top = user_360[top_y1:top_y2, top_x1:top_x2]
    
    patch_ref_bot = ref_360[bot_y1:bot_y2, bot_x1:bot_x2]
    patch_user_bot = user_360[bot_y1:bot_y2, bot_x1:bot_x2]
    
    # Print mean colors (BGR)
    print("\n--- TOP CAVITY ANALYSIS ---")
    print(f"Ref Top Cavity Mean BGR:  {np.mean(patch_ref_top, axis=(0,1))}")
    print(f"User Top Cavity Mean BGR: {np.mean(patch_user_top, axis=(0,1))}")
    
    print("\n--- BOTTOM CAVITY ANALYSIS ---")
    print(f"Ref Bot Cavity Mean BGR:  {np.mean(patch_ref_bot, axis=(0,1))}")
    print(f"User Bot Cavity Mean BGR: {np.mean(patch_user_bot, axis=(0,1))}")
    
    # Save the patches for verification
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/patch_ref_top.jpg", patch_ref_top)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/patch_user_top.jpg", patch_user_top)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/patch_ref_bot.jpg", patch_ref_bot)
    cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/patch_user_bot.jpg", patch_user_bot)

if __name__ == "__main__":
    main()
