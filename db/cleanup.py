import os
import time
import logging
import threading
from db.db import db

logger = logging.getLogger(__name__)

class StorageCleanup:
    """
    Automatic cleanup of old violation clips when disk usage is high.
    Runs as a daemon thread.
    """
    def __init__(self, violations_dir: str, max_usage_percent: float = 85.0, 
                 check_interval_min: int = 10):
        self.violations_dir = violations_dir
        self.max_usage = max_usage_percent
        self.interval = check_interval_min * 60
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        logger.info(f"StorageCleanup: Started cleanup worker (checking every {self.interval/60} mins).")

    def _worker(self):
        while self.running:
            try:
                self._check_and_cleanup()
            except Exception as e:
                logger.error(f"StorageCleanup: Error in worker: {e}")
            time.sleep(self.interval)

    def _check_and_cleanup(self):
        """Checks disk usage and deletes oldest clips if necessary."""
        import psutil
        usage = psutil.disk_usage(self.violations_dir)
        percent = usage.percent
        
        if percent > self.max_usage:
            logger.warning(f"StorageCleanup: Disk usage high ({percent}%). Starting cleanup...")
            self._delete_oldest_clips()

    def _delete_oldest_clips(self):
        """Deletes oldest clips from DB and disk until usage is acceptable."""
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Lấy danh sách 10 clip cũ nhất
            cursor.execute("SELECT id, file_path FROM violation_clips ORDER BY created_at ASC LIMIT 10")
            clips = cursor.fetchall()
            
            for clip_id, file_path in clips:
                # Xóa file vật lý
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"StorageCleanup: Deleted file {file_path}")
                
                # Xóa bản ghi trong DB
                cursor.execute("DELETE FROM violation_clips WHERE id = ?", (clip_id,))
                conn.commit()
                
            logger.info(f"StorageCleanup: Cleaned up {len(clips)} old clips.")
        except Exception as e:
            logger.error(f"StorageCleanup error: {e}")
        finally:
            conn.close()

    def stop(self):
        self.running = False
