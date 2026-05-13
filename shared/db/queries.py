import logging
import time
import os
from typing import List, Dict, Any, Optional
from shared.db.db import db

logger = logging.getLogger(__name__)


class EventQueries:
    """
    Handles all database operations related to SOP events and violations.
    Uses MySQL (pymysql) with connection pool.
    """

    @staticmethod
    def _log_to_file(message: str):
        """Helper to log DB operations to a debug file. Clears after 24 hours."""
        log_dir = "data/logs"
        if not os.path.exists(log_dir): os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "db_debug.txt")
        
        # Tự động xóa nếu file cũ hơn 1 ngày (86400 giây)
        mode = 'a'
        if os.path.exists(log_path):
            mtime = os.path.getmtime(log_path)
            if time.time() - mtime > 86400:
                mode = 'w' # Ghi đè (xóa cũ)
        
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(log_path, mode, encoding='utf-8') as f:
                f.write(f"[{ts}] {message}\n")
        except:
            pass # Tránh làm crash app chính nếu lỗi file log

    @staticmethod
    def log_event(camera_id: str, violation_type: str,
                  step_detected: Optional[str] = None,
                  expected_step: Optional[str] = None,
                  sop_status: str = "violation",
                  confidence: float = 0.0,
                  clip_path: str = "") -> Optional[int]:
        """
        Ghi nhận một sự kiện vi phạm vào sop_events.
        Trả về event_id nếu thành công, None nếu lỗi.
        """
        conn = db.get_connection()
        if conn is None:
            logger.error("DB: Connection lost. Skipping event log.")
            return None
            
        cursor = conn.cursor()
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Tìm camera_id (INT) và definition_id (Mã hàng hiện tại) từ station_id
            cursor.execute(
                "SELECT id, definition_id FROM sop_cameras WHERE station_id = %s",
                (camera_id,)
            )
            cam_row = cursor.fetchone()
            cam_db_id = cam_row["id"] if cam_row else None
            def_db_id = cam_row["definition_id"] if cam_row else None

            if cam_db_id is None:
                logger.warning(
                    f"DB: Camera '{camera_id}' not found in sop_cameras. "
                    f"Logging event without FK."
                )

            cursor.execute("""
                INSERT INTO sop_events (
                    camera_id, definition_id, timestamp, violation_type,
                    step_detected, expected_step, sop_status,
                    confidence, clip_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cam_db_id, def_db_id, timestamp, violation_type,
                step_detected or "N/A", expected_step,
                sop_status, confidence, clip_path
            ))
            
            event_id = cursor.lastrowid

            # --- MỚI: Nếu có clip_path, ghi thêm vào bảng sop_clips để quản lý ---
            if clip_path and os.path.exists(clip_path):
                file_size = os.path.getsize(clip_path) / (1024 * 1024) # MB
                cursor.execute("""
                    INSERT INTO sop_clips (event_id, camera_id, file_path, file_size_mb, duration_sec)
                    VALUES (%s, %s, %s, %s, %s)
                """, (event_id, cam_db_id, clip_path, file_size, 10)) # 10s theo cấu hình mới
            
            conn.commit()
            logger.info(
                f"DB: Logged violation '{violation_type}' for camera "
                f"{camera_id} (event_id={event_id}, clip_saved={bool(clip_path)})"
            )
            EventQueries._log_to_file(f"LOG_EVENT: Cam:{camera_id} (DBID:{cam_db_id}), Type:{violation_type}, Status:{sop_status}, ID:{event_id}")
            return event_id

        except Exception as e:
            EventQueries._log_to_file(f"LOG_EVENT_ERROR: {e}")
            logger.error(f"DB Error logging event: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Truy vấn danh sách các vi phạm gần đây nhất từ sop_events.
        """
        conn = db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM sop_events ORDER BY timestamp DESC LIMIT %s",
                (limit,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting recent events: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_violation_counts() -> Dict[str, int]:
        """Thống kê tổng số vi phạm theo loại (tất cả thời gian)."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT violation_type, COUNT(*) as cnt "
                "FROM sop_events WHERE sop_status = 'violation' "
                "GROUP BY violation_type"
            )
            rows = cursor.fetchall()
            return {row["violation_type"]: row["cnt"] for row in rows}
        except Exception as e:
            logger.error(f"DB Error getting violation counts: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_daily_summary(target_date: str, camera_id: Optional[str] = None) -> Dict[str, Any]:
        """Lấy tổng lỗi và tỷ lệ tuân thủ của một ngày cụ thể."""
        # Bảo vệ: Nếu JS gửi chuỗi "undefined", coi như là None
        if camera_id == "undefined" or not camera_id:
            camera_id = None
            
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clause = "WHERE DATE(e.timestamp) = %s"
            params = [target_date]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)

            # Đếm lỗi
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {where_clause} AND e.sop_status = 'violation'
            """, tuple(params))
            violations = cursor.fetchone()["cnt"]

            # Đếm số chu kỳ hoàn thành
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {where_clause} AND e.sop_status = 'completed'
            """, tuple(params))
            completions = cursor.fetchone()["cnt"]

            total_cycles = violations + completions
            compliance = 100.0 if total_cycles == 0 else (completions / total_cycles) * 100.0

            res = {
                "total_violations": violations,
                "total_completions": completions,
                "compliance_rate": round(compliance, 1)
            }
            EventQueries._log_to_file(f"GET_SUMMARY: Date:{target_date}, Cam:{camera_id} -> {res}")
            return res
        except Exception as e:
            EventQueries._log_to_file(f"GET_SUMMARY_ERROR: {e}")
            logger.error(f"DB Error getting daily summary: {e}")
            return {"total_violations": 0, "total_completions": 0, "compliance_rate": 100.0}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_daily_distribution(target_date: str, camera_id: Optional[str] = None) -> Dict[str, int]:
        """Phân bổ loại vi phạm trong một ngày cụ thể."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
            
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clause = "WHERE DATE(e.timestamp) = %s AND e.sop_status = 'violation'"
            params = [target_date]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)

            cursor.execute(f"""
                SELECT e.violation_type, COUNT(*) as cnt 
                FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {where_clause}
                GROUP BY e.violation_type
            """, tuple(params))
            rows = cursor.fetchall()
            return {row["violation_type"]: row["cnt"] for row in rows}
        except Exception as e:
            logger.error(f"DB Error getting daily distribution: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_weekly_trend(target_date: str, camera_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy xu hướng vi phạm 7 ngày (Thứ 2 -> Chủ Nhật) của tuần chứa target_date."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
            
        import datetime
        try:
            dt = datetime.datetime.strptime(target_date, '%Y-%m-%d')
            start_of_week = dt - datetime.timedelta(days=dt.weekday())
            end_of_week = start_of_week + datetime.timedelta(days=6)
            
            conn = db.get_connection()
            cursor = conn.cursor()
            
            where_clause = "WHERE DATE(e.timestamp) >= %s AND DATE(e.timestamp) <= %s AND e.sop_status = 'violation'"
            params = [start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)

            # Lấy dữ liệu gộp theo ngày
            cursor.execute(f"""
                SELECT DATE(e.timestamp) as date, COUNT(*) as cnt 
                FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {where_clause}
                GROUP BY DATE(e.timestamp)
            """, tuple(params))
            
            db_data = {str(row["date"]): row["cnt"] for row in cursor.fetchall()}
            
            # Build đủ 7 ngày kể cả ngày không có dữ liệu
            trend = []
            days_vn = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for i in range(7):
                current_day = start_of_week + datetime.timedelta(days=i)
                date_str = current_day.strftime('%Y-%m-%d')
                trend.append({
                    "day": days_vn[i],
                    "date": date_str,
                    "count": db_data.get(date_str, 0)
                })
            return trend
        except Exception as e:
            logger.error(f"DB Error getting weekly trend: {e}")
            return []
        finally:
            if 'cursor' in locals(): cursor.close()
            if 'conn' in locals(): conn.close()

    @staticmethod
    def get_events_by_camera(camera_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Truy vấn vi phạm theo camera station_id.
        """
        conn = db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT e.* FROM sop_events e
                JOIN sop_cameras c ON e.camera_id = c.id
                WHERE c.station_id = %s
                ORDER BY e.timestamp DESC
                LIMIT %s
            """, (camera_id, limit))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting events for camera {camera_id}: {e}")
            return []
        finally:
            cursor.close()
            conn.close()


class CameraQueries:
    """
    Handles database operations for sop_cameras.
    """

    @staticmethod
    def upsert_camera(station_id: str, name: str, rtsp_url: str,
                      definition_id: Optional[int] = None) -> Optional[int]:
        """
        Thêm hoặc cập nhật camera. Trả về camera id.
        """
        conn = db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT id FROM sop_cameras WHERE station_id = %s",
                (station_id,)
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE sop_cameras
                    SET name = %s, rtsp_url = %s, definition_id = %s, status = 'active'
                    WHERE station_id = %s
                """, (name, rtsp_url, definition_id, station_id))
                conn.commit()
                return existing["id"]
            else:
                cursor.execute("""
                    INSERT INTO sop_cameras (station_id, name, rtsp_url, definition_id)
                    VALUES (%s, %s, %s, %s)
                """, (station_id, name, rtsp_url, definition_id))
                conn.commit()
                cam_id = cursor.lastrowid
                logger.info(f"DB: Registered camera '{station_id}' (id={cam_id})")
                return cam_id

        except Exception as e:
            logger.error(f"DB Error upserting camera {station_id}: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_cameras() -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả camera SOP."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT c.*, d.name as definition_name
                FROM sop_cameras c
                LEFT JOIN sop_definitions d ON c.definition_id = d.id
                ORDER BY c.station_id
            """)
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting cameras: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_status(station_id: str, status: str) -> None:
        """Cập nhật trạng thái camera."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sop_cameras SET status = %s WHERE station_id = %s",
                (status, station_id)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"DB Error updating camera status: {e}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_camera_definition(station_id: str, definition_id: int) -> None:
        """Cập nhật liên kết giữa camera và định nghĩa SOP mới."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sop_cameras SET definition_id = %s WHERE station_id = %s",
                (definition_id, station_id)
            )
            conn.commit()
            logger.info(f"DB: Updated camera '{station_id}' with definition_id={definition_id}")
        except Exception as e:
            logger.error(f"DB Error updating camera definition: {e}")
        finally:
            cursor.close()
            conn.close()


class DefinitionQueries:
    """
    Handles database operations for sop_definitions and sop_steps.
    """

    @staticmethod
    def upsert_definition(name: str, description: str = "",
                          total_steps: int = 0) -> Optional[int]:
        """Thêm hoặc lấy definition. Trả về definition_id."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM sop_definitions WHERE name = %s", (name,)
            )
            existing = cursor.fetchone()
            if existing:
                return existing["id"]

            cursor.execute("""
                INSERT INTO sop_definitions (name, description, total_steps)
                VALUES (%s, %s, %s)
            """, (name, description, total_steps))
            conn.commit()
            def_id = cursor.lastrowid
            logger.info(f"DB: Created SOP definition '{name}' (id={def_id})")
            return def_id
        except Exception as e:
            logger.error(f"DB Error upserting definition: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def sync_steps(definition_id: int, steps: List[Dict[str, Any]]) -> None:
        """
        Đồng bộ danh sách bước từ YAML vào DB.
        Xóa bước cũ, thêm bước mới.
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM sop_steps WHERE definition_id = %s",
                (definition_id,)
            )
            for step in steps:
                cursor.execute("""
                    INSERT INTO sop_steps
                    (definition_id, step_order, step_name, step_label, max_duration_ms, is_mandatory)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    definition_id,
                    step.get("step_order", 0),
                    step.get("step_name", ""),
                    step.get("step_label", step.get("step_name", "")),
                    step.get("max_duration_ms"),
                    1 if step.get("is_mandatory", True) else 0,
                ))

            # Cập nhật total_steps
            cursor.execute(
                "UPDATE sop_definitions SET total_steps = %s WHERE id = %s",
                (len(steps), definition_id)
            )
            conn.commit()
            logger.info(
                f"DB: Synced {len(steps)} steps for definition_id={definition_id}"
            )
        except Exception as e:
            logger.error(f"DB Error syncing steps: {e}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_steps(definition_id: int) -> List[Dict[str, Any]]:
        """Lấy danh sách bước theo definition."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM sop_steps WHERE definition_id = %s "
                "ORDER BY step_order",
                (definition_id,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting steps: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
