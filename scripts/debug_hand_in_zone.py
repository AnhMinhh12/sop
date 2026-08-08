import cv2
import numpy as np

def main():
    # button_right polygon coordinates from TFF4040.yaml
    button_right = [[0.289, 0.764], [0.269, 0.714], [0.237, 0.742], [0.258, 0.797]]
    
    # Hand detected at Frame 2078-2081: Box=[158, 282, 193, 356]
    bbox = [158, 282, 193, 356]
    w, h = 640, 480
    
    centroid = [(bbox[0] + bbox[2]) / 2.0 / w, (bbox[1] + bbox[3]) / 2.0 / h]
    
    test_points = [
        centroid,
        [bbox[0]/w, bbox[1]/h],
        [bbox[2]/w, bbox[1]/h],
        [bbox[0]/w, bbox[3]/h],
        [bbox[2]/w, bbox[3]/h]
    ]
    
    poly = np.array(button_right, np.float32)
    
    print(f"Centroid: {centroid}")
    print(f"Points to test:")
    for pt in test_points:
        res = cv2.pointPolygonTest(poly, (pt[0], pt[1]), False)
        print(f"  Point {pt}: {res}")

if __name__ == "__main__":
    main()
