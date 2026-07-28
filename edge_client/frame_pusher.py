"""
FramePusher: Gửi frame đã annotate và status lên Hub qua HTTP POST.
Designed for low-bandwidth: chỉ gửi 1-2 FPS thay vì mỗi frame.
"""
import requests
import logging
import time
import json
from typing import Dict, Any, Optional

logger = logging.getLogger("FramePusher")


class FramePusher:
    def __init__(self, hub_url: str, api_key: str, camera_id: str):
        self.hub_url = hub_url.rstrip('/')
        self.api_key = api_key
        self.camera_id = camera_id
        self.push_endpoint = f"{self.hub_url}/api/station/{camera_id}/push_frame"
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': self.api_key})
        self.last_push_time = 0
        self.push_interval = 1.0  # seconds between pushes (adjust for bandwidth)
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5

    def push(self, frame_bytes: bytes, status: Dict[str, Any], hands: list = None) -> bool:
        """
        Gửi frame + status lên Hub.

        Args:
            frame_bytes: JPEG encoded frame
            status: FSM status dict từ Engine
            hands: Optional hands data

        Returns:
            True if successful, False otherwise
        """
        try:
            files = {'image': ('frame.jpg', frame_bytes, 'image/jpeg')}
            data = {
                'status': json.dumps(status),
                'hands': json.dumps(hands or [])
            }

            response = self.session.post(
                self.push_endpoint,
                files=files,
                data=data,
                timeout=5
            )

            if response.status_code == 200:
                self.consecutive_errors = 0
                self.last_push_time = time.time()
                return True
            else:
                logger.warning(f"Push failed: HTTP {response.status_code} - {response.text[:100]}")
                self.consecutive_errors += 1
                return False

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error pushing to Hub: {e}")
            self.consecutive_errors += 1
            return False
        except requests.exceptions.Timeout as e:
            logger.warning(f"Push timeout: {e}")
            self.consecutive_errors += 1
            return False
        except Exception as e:
            logger.error(f"Unexpected error in push: {e}")
            self.consecutive_errors += 1
            return False

    def is_healthy(self) -> bool:
        """Kiểm tra xem edge có kết nối được Hub không."""
        return self.consecutive_errors < self.max_consecutive_errors

    def get_last_push_age(self) -> float:
        """Trả về số giây kể từ lần push cuối."""
        return time.time() - self.last_push_time

    def set_push_interval(self, interval: float):
        """Điều chỉnh interval giữa các lần push (seconds)."""
        self.push_interval = max(0.1, min(interval, 10.0))
