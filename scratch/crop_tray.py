import cv2

img = cv2.imread("scratch/live_worker_action/act_00_f000_IDLE_0.jpg")
# Crop transparent tray (bottom right: x: 380 to 600, y: 150 to 360)
tray_crop = img[150:360, 370:620]
cv2.imwrite("scratch/tray_crop.jpg", tray_crop)
print("Saved scratch/tray_crop.jpg")

