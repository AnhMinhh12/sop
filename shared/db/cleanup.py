import os
import time
import logging
import threading
from shared.db.db import db

logger = logging.getLogger(__name__)


class StorageCleanup:
    """
    Automatic cleanup of old violation clips when disk usage is high.
    Runs as a daemon thread. Uses MySQL sop_clips table.
    """

    def __init__(self, violations_dir: str, max_usage_percent: float = 85.0, 
                 check_interval_min: int = 10, retention_days: int = 15):
        self.violations_dir = violations_dir
        self.max_usage = max_usage_percent
        self.retention_days = retention_days
        self.interval = check_interval_min * 60
        self.running = False

    def start(self) -> None:
        """Start the cleanup daemon thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        logger.info(
            f"StorageCleanup: Started cleanup worker "
            f"(Interval: {self.interval / 60:.0f} mins, Retention: {self.retention_days} days)."
        )

    def _worker(self) -> None:
        """Background worker loop."""
        while self.running:
            try:
                # 1. Xóa theo thời gian (Hết hạn 15 ngày)
                self._cleanup_by_time()

                # 2. Xóa theo dung lượng ổ cứng (nếu vượt ngưỡng max_usage)
                self._check_and_cleanup()

                # 3. Dọn dẹp spatial_debug.txt nếu phình to
                self._cleanup_debug_logs()

            except Exception as e:
                logger.error(f"StorageCleanup: Unexpected error in worker: {e}")

            time.sleep(self.interval)

    def _cleanup_debug_logs(self):
        """Xóa file log spatial_debug.txt nếu nó quá 50MB để tránh đầy ổ cứng."""
        debug_file = "data/logs/spatial_debug.txt"
        if os.path.exists(debug_file):
            try:
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(f"--- Cleared by StorageCleanup at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                logger.info("StorageCleanup: Cleared spatial_debug.txt")
            except Exception as e:
                logger.error(f"StorageCleanup: Could not clear {debug_file}: {e}")

    def _cleanup_by_time(self):
        """Deletes clips older than the retention period."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            # MySQL syntax to find records older than N days
            cursor.execute(f"""
                SELECT id, event_id, file_path FROM sop_clips 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (self.retention_days,))
            
            clips = cursor.fetchall()
            if not clips:
                return

            logger.info(f"StorageCleanup: Found {len(clips)} clips older than {self.retention_days} days. Deleting...")
            
            for clip in clips:
                clip_id = clip["id"]
                file_path = clip["file_path"]
                ev_id = clip.get("event_id")

                # Xóa file vật lý
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Could not delete file {file_path}: {e}")

                # Xóa bản ghi trong DB và reset clip_path trong sop_events
                cursor.execute("DELETE FROM sop_clips WHERE id = %s", (clip_id,))
                if ev_id:
                    cursor.execute("UPDATE sop_events SET clip_path = NULL WHERE id = %s", (ev_id,))
            
            conn.commit()
            logger.info(f"StorageCleanup: Cleaned up {len(clips)} expired clips.")
        except Exception as e:
            logger.error(f"StorageCleanup (time-based) error: {e}")
        finally:
            cursor.close()
            conn.close()

    def _check_and_cleanup(self) -> None:
        """Checks disk usage and deletes oldest clips if necessary."""
        import psutil
        usage = psutil.disk_usage(self.violations_dir)
        percent = usage.percent

        if percent > self.max_usage:
            logger.warning(
                f"StorageCleanup: Disk usage high ({percent}%). "
                f"Starting cleanup..."
            )
            self._delete_oldest_clips()

    def _delete_oldest_clips(self) -> None:
        """Deletes oldest clips from DB (sop_clips) and disk."""
        conn = db.get_connection()
        cursor = conn.cursor()

        try:
            # Lấy danh sách 10 clip cũ nhất
            cursor.execute(
                "SELECT id, file_path FROM sop_clips "
                "ORDER BY created_at ASC LIMIT 10"
            )
            clips = cursor.fetchall()

            for clip in clips:
                clip_id = clip["id"]
                file_path = clip["file_path"]

                # Xóa file vật lý
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"StorageCleanup: Deleted file {file_path}")

                # Xóa bản ghi trong DB
                cursor.execute(
                    "DELETE FROM sop_clips WHERE id = %s", (clip_id,)
                )

            conn.commit()
            logger.info(
                f"StorageCleanup: Cleaned up {len(clips)} old clips."
            )
        except Exception as e:
            logger.error(f"StorageCleanup error: {e}")
        finally:
            cursor.close()
            conn.close()

    def stop(self) -> None:
        """Stop the cleanup daemon."""
        self.running = False
