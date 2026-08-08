import cv2

def main():
    rtsp_url = "rtsp://admin:Htmp%402019@10.0.7.47:554/Streaming/Channels/102"
    print(f"Connecting to RTSP stream: {rtsp_url}")
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print("Failed to open RTSP stream.")
        return
        
    ret, frame = cap.read()
    if ret:
        cv2.imwrite("test_live_camera.jpg", frame)
        print("Saved raw frame to test_live_camera.jpg")
    else:
        print("Failed to read frame.")
    cap.release()

if __name__ == "__main__":
    main()
