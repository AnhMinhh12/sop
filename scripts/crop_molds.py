import cv2

def main():
    # 1. Crop mold from reference frame (1280x720)
    ref_img = cv2.imread("sp_reference_frame.jpg")
    if ref_img is not None:
        h, w = ref_img.shape[:2]
        # mold polygon bounds: x: [0.383, 0.672], y: [0.522, 0.989]
        x1, x2 = int(0.38 * w), int(0.68 * w)
        y1, y2 = int(0.50 * h), int(0.99 * h)
        crop_ref = ref_img[y1:y2, x1:x2]
        cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_ref_mold.jpg", crop_ref)
        print("Saved crop_ref_mold.jpg")
        
    # 2. Crop mold from live frame 101 (2560x1440)
    live_img = cv2.imread("test_live_camera_101.jpg")
    if live_img is not None:
        h, w = live_img.shape[:2]
        x1, x2 = int(0.38 * w), int(0.68 * w)
        y1, y2 = int(0.50 * h), int(0.99 * h)
        crop_live = live_img[y1:y2, x1:x2]
        cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_live_mold.jpg", crop_live)
        print("Saved crop_live_mold.jpg")

if __name__ == "__main__":
    main()
