import cv2

def main():
    img = cv2.imread("user_image.jpg")
    if img is not None:
        h, w = img.shape[:2]
        # Crop the mold region
        x1, x2 = int(0.38 * w), int(0.68 * w)
        y1, y2 = int(0.50 * h), int(0.99 * h)
        crop_user = img[y1:y2, x1:x2]
        cv2.imwrite("C:/Users/it07/.gemini/antigravity/brain/5a5697aa-1654-44de-b677-695a539abc47/artifacts/crop_user_mold.jpg", crop_user)
        print("Saved crop_user_mold.jpg")
    else:
        print("Failed to read user_image.jpg")

if __name__ == "__main__":
    main()
