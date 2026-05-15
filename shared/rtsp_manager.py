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
    Compliance: Max 10 retries, emits camera_status.
    """
    def __init__(self, camera_id: str, rtsp_url: str, fps_cap: int = 15,
                 target_width: int = 640, target_height: int = 480):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.fps_cap = fps_cap
        self.frame_delay = 1.0 / fps_cap
        self.target_width = target_width
        self.target_height = target_height
        
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[cv2.Mat] = None
        self.running = False
        self.status = "disconnected" # disconnected | connected | error
        self.retry_count = 0
        self.max_retries = 10 # Tuân thủ quy tắc: tối đa 10 lần
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
        from app import emit_camera_status # Lazy import to avoid circular dependency
        
        is_rtsp = self.rtsp_url.startswith(("rtsp://", "http://", "https://"))
        
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                if self.retry_count >= self.max_retries:
                    if self.status != "error":
                        self.status = "error"
                        emit_camera_status(self.camera_id, "error")
                        logger.error(f"RTSPStream [{self.camera_id}]: Max retries reached. Stopping attempts.")
                    time.sleep(10) # Chờ lâu hơn trước khi thử lại sau khi đã fail 10 lần
                    self.retry_count = 0 # Reset để thử lại sau khi chờ
                    continue

                self._connect()
                if self.cap is None or not self.cap.isOpened():
                    emit_camera_status(self.camera_id, "error")
                    time.sleep(5)
                    continue
                else:
                    emit_camera_status(self.camera_id, "connected")

            # Flush buffer: Xóa sạch bộ đệm để lấy khung hình mới nhất (Real-time)
            if is_rtsp:
                # Flush buffer nhanh: grab 2-3 frames thay vì loop vô hạn có thể gây nghẽn
                for _ in range(2):
                    self.cap.grab()
            
            start_time = time.time()
            ret, frame = self.cap.read()
            
            if ret:
                # RESIZE NGAY TẠI ĐÂY
                if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                    frame = cv2.resize(frame, (self.target_width, self.target_height), 
                                       interpolation=cv2.INTER_LINEAR)
                
                with self.lock:
                    self.frame = frame
                
                if self.status != "connected":
                    self.status = "connected"
                    emit_camera_status(self.camera_id, "connected")
            else:
                if not is_rtsp:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                logger.warning(f"RTSPStream [{self.camera_id}]: Stream signal lost.")
                self.status = "error"
                emit_camera_status(self.camera_id, "error")
                self.cap.release()
                time.sleep(2)

            # FPS Control
            elapsed = time.time() - start_time
            sleep_time = self.frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _connect(self):
        """Attempts to open the RTSP or Video stream."""
        try:
            print(f"RTSPStream [{self.camera_id}]: Connecting to {self.rtsp_url}...", flush=True)
            logger.info(f"RTSPStream [{self.camera_id}]: Attempt {self.retry_count + 1}/{self.max_retries}")
            
            if self.cap is not None:
                self.cap.release()
            
            # Ép TCP và cấu hình timeout ngắn hơn nếu có thể qua env (OpenCV 4.x)
            if self.rtsp_url.startswith("rtsp://"):
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000" # 5 seconds
            
            self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print(f"RTSPStream [{self.camera_id}]: CONNECTED SUCCESSFULLY.", flush=True)
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.status = "connected"
                self.retry_count = 0
            else:
                print(f"RTSPStream [{self.camera_id}]: FAILED TO OPEN (Check URL/Network).", flush=True)
                self.status = "error"
                self.retry_count += 1
                
        except Exception as e:
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
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        logger.info(f"RTSPStream [{self.camera_id}]: Stream stopped.")
