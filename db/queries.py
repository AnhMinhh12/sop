import logging
import time
from typing import List, Dict, Any, Optional
from db.db import db, Database

logger = logging.getLogger(__name__)

class EventQueries:
    """
    Handles all database operations related to SOP events and violations.
    """
    @staticmethod
    def log_event(camera_id: str, violation_type: str, 
                  step_detected: Optional[str] = None, 
                  expected_step: Optional[str] = None, 
                  sop_status: str = "violation", 
                  confidence: float = 0.0,
                  clip_path: str = ""):
        """
        Ghi nhận một sự kiện vi phạm vào database.
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            cursor.execute("""
                INSERT INTO events (
                    camera_id, timestamp, violation_type, 
                    step_detected, expected_step, sop_status, 
                    confidence, clip_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (camera_id, timestamp, violation_type, step_detected, expected_step, sop_status, confidence, clip_path))
            
            conn.commit()
            logger.info(f"DB: Logged violation '{violation_type}' for camera {camera_id}")
        except Exception as e:
            logger.error(f"DB Error logging event: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Truy vấn danh sách các vi phạm gần đây nhất.
        """
        conn = db.get_connection()
        # Sử dụng Class method thay vì instance attribute để tránh AttributeError
        conn.row_factory = Database.dict_factory
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting recent events: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_violation_counts() -> Dict[str, int]:
        """
        Thống kê tổng số vi phạm theo loại.
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT violation_type, COUNT(*) FROM events GROUP BY violation_type")
            return dict(cursor.fetchall())
        except Exception as e:
            logger.error(f"DB Error getting violation counts: {e}")
            return {}
        finally:
            conn.close()
