import cv2
import threading
import time
import logging
import os
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class RTSPStream:
    """
    Manages an RTSP connection from an IP camera.
    Includes auto-reconnect logic and FPS capping.
    """
    def __init__(self, camera_id: str, rtsp_url: str, fps_cap: int = 15):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.fps_cap = fps_cap
        self.frame_delay = 1.0 / fps_cap
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[cv2.Mat] = None
        self.running = False
        self.status = "disconnected" # disconnected | connected | error
        self.retry_count = 0
        self.width = 0
        self.height = 0
        
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the camera reading thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        logger.info(f"RTSPStream [{self.camera_id}]: Started stream thread.")

    def _update_loop(self):
        """Main loop to read frames and handle reconnections."""
        print(f"RTSPStream [{self.camera_id}]: Thread loop started.", flush=True)
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self._connect()
                if self.cap is None or not self.cap.isOpened():
                    # Reconnect failed, wait 5 seconds
                    time.sleep(5)
                    continue

            start_time = time.time()
            ret, frame = self.cap.read()
            
            if ret:
                with self.lock:
                    self.frame = frame
                self.status = "connected"
                # Chỉ log mỗi 300 frame (20s) để tránh làm đầy file log
                if getattr(self, '_frame_count', 0) % 300 == 0:
                    print(f"RTSPStream [{self.camera_id}]: Frame received successfully.", flush=True)
                    logger.debug(f"RTSPStream [{self.camera_id}]: Reading frames active...")
                self._frame_count = getattr(self, '_frame_count', 0) + 1
            else:
                # Nếu là file video quay sẵn thì tự động lặp lại (Loop)
                if not self.rtsp_url.startswith(("rtsp://", "http://", "https://")):
                    logger.debug(f"RTSPStream [{self.camera_id}]: Video file ended. Looping...")
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                print(f"RTSPStream [{self.camera_id}]: Lost connection.", flush=True)
                logger.warning(f"RTSPStream [{self.camera_id}]: Stream signal lost.")
                self.status = "error"
                self.cap.release()
                time.sleep(2) # Short wait before reconnecting

            # FPS Control: Đảm bảo không quá giới hạn fps_cap để tiết kiệm CPU
            elapsed = time.time() - start_time
            sleep_time = max(0, self.frame_delay - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _connect(self):
        """Attempts to open the RTSP or Video stream."""
        try:
            print(f"RTSPStream [{self.camera_id}]: Connecting to {self.rtsp_url}...", flush=True)
            logger.info(f"RTSPStream [{self.camera_id}]: Attempting to connect to {self.rtsp_url}")
            
            # Đóng cũ nếu tồn tại
            if self.cap is not None:
                self.cap.release()
            
            # Sử dụng CAP_FFMPEG để ổn định hơn cho cả RTSP và File trên Windows
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print(f"RTSPStream [{self.camera_id}]: CONNECTED SUCCESSFULLY.", flush=True)
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(f"RTSPStream [{self.camera_id}]: Connected. Res: {self.width}x{self.height}")
                self.status = "connected"
                self.retry_count = 0
            else:
                print(f"RTSPStream [{self.camera_id}]: FAILED TO OPEN STREAM.", flush=True)
                logger.warning(f"RTSPStream [{self.camera_id}]: Could not open stream.")
                self.status = "error"
                self.retry_count += 1
                
        except Exception as e:
            print(f"RTSPStream [{self.camera_id}]: CONNECTION ERROR: {e}", flush=True)
            logger.error(f"RTSPStream [{self.camera_id}]: Connection error: {e}")
            self.status = "error"
            self.retry_count += 1

    def get_frame(self) -> Optional[cv2.Mat]:
        """Returns the latest captured frame."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        """Stops the stream thread and releases resources."""
        self.running = False
        if self.thread:
            self.thread.join()
        if self.cap:
            self.cap.release()
        logger.info(f"RTSPStream [{self.camera_id}]: Stream stopped.")
