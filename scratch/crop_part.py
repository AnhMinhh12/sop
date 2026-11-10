import cv2
import numpy as np

img = cv2.imread("scratch/live_worker_action/act_00_f000_IDLE_0.jpg")
# Let's crop the workpiece area
# In act_00, part_hand bbox was around [310, 80, 480, 260]
h, w = img.shape[:2]
part_crop = img[50:300, 280:520]
cv2.imwrite("scratch/cropped_part.jpg", part_crop)
print("Saved scratch/cropped_part.jpg", part_crop.shape)

