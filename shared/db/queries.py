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
                  clip_path: str = "",
                  duration: Optional[float] = None) -> Optional[int]:
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
                    confidence, clip_path, duration
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cam_db_id, def_db_id, timestamp, violation_type,
                step_detected or "N/A", expected_step,
                sop_status, confidence, clip_path, duration
            ))
            
            event_id = cursor.lastrowid

            # --- MỚI: Nếu có clip_path, ghi thêm vào bảng sop_clips để quản lý ---
            if clip_path and os.path.exists(clip_path):
                file_size = os.path.getsize(clip_path) / (1024 * 1024) # MB
                cursor.execute("""
                    INSERT INTO sop_clips (event_id, camera_id, file_path, file_size_mb, duration_sec)
                    VALUES (%s, %s, %s, %s, %s)
                """, (event_id, cam_db_id, clip_path, file_size, int(duration) if duration else 10))
            
            conn.commit()
            logger.info(
                f"DB: Logged violation '{violation_type}' for camera "
                f"{camera_id} (event_id={event_id}, clip_saved={bool(clip_path)})"
            )
            EventQueries._log_to_file(f"LOG_EVENT: Cam:{camera_id} (DBID:{cam_db_id}), Type:{violation_type}, Status:{sop_status}, Duration:{duration}, ID:{event_id}")
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
            cursor.execute("""
                SELECT e.*, c.station_id 
                FROM sop_events e
                LEFT JOIN sop_cameras c ON e.camera_id = c.id
                WHERE e.sop_status = 'violation'
                ORDER BY e.timestamp DESC 
                LIMIT %s
            """, (limit,))
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
            counts = {}
            for row in rows:
                vtype = row["violation_type"]
                if vtype == "premature_restart":
                    vtype = "skip_step"
                counts[vtype] = counts.get(vtype, 0) + row["cnt"]
            return counts
        except Exception as e:
            logger.error(f"DB Error getting violation counts: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_daily_summary(target_date: str, camera_id: Optional[str] = None, product_id: Optional[str] = None, start_hour: Optional[int] = None, end_hour: Optional[int] = None) -> Dict[str, Any]:
        """Lấy tổng lỗi và tỷ lệ tuân thủ của một ngày cụ thể."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
        if product_id == "undefined" or not product_id:
            product_id = None
            
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clause = "WHERE DATE(e.timestamp) = %s"
            params = [target_date]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)
            if product_id:
                if product_id == "TFF4040":
                    where_clause += " AND (d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s)"
                    params.extend(["%TFF4040%", "%Reformed%", "%TEST MODEL%", "%Sản phẩm A%"])
                elif product_id == "626287":
                    where_clause += " AND (d.name LIKE %s)"
                    params.append("%626287%")
                else:
                    where_clause += " AND (d.name LIKE %s OR d.name = %s)"
                    params.extend([f"%{product_id}%", product_id])

            if start_hour is not None:
                where_clause += " AND HOUR(e.timestamp) >= %s"
                params.append(start_hour)
            if end_hour is not None:
                where_clause += " AND HOUR(e.timestamp) <= %s"
                params.append(end_hour)

            # Đếm lỗi
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {"LEFT JOIN sop_definitions d ON e.definition_id = d.id" if product_id else ""}
                {where_clause} AND e.sop_status = 'violation'
            """, tuple(params))
            violations = cursor.fetchone()["cnt"]

            # Đếm số chu kỳ hoàn thành
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {"LEFT JOIN sop_definitions d ON e.definition_id = d.id" if product_id else ""}
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
            EventQueries._log_to_file(f"GET_SUMMARY: Date:{target_date}, Cam:{camera_id}, Prod:{product_id}, Hours:{start_hour}-{end_hour} -> {res}")
            return res
        except Exception as e:
            EventQueries._log_to_file(f"GET_SUMMARY_ERROR: {e}")
            logger.error(f"DB Error getting daily summary: {e}")
            return {"total_violations": 0, "total_completions": 0, "compliance_rate": 100.0}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_daily_distribution(target_date: str, camera_id: Optional[str] = None, product_id: Optional[str] = None, start_hour: Optional[int] = None, end_hour: Optional[int] = None) -> Dict[str, int]:
        """Phân bổ loại vi phạm trong một ngày cụ thể."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
        if product_id == "undefined" or not product_id:
            product_id = None
            
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clause = "WHERE DATE(e.timestamp) = %s AND e.sop_status = 'violation'"
            params = [target_date]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)
            if product_id:
                if product_id == "TFF4040":
                    where_clause += " AND (d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s)"
                    params.extend(["%TFF4040%", "%Reformed%", "%TEST MODEL%", "%Sản phẩm A%"])
                elif product_id == "626287":
                    where_clause += " AND (d.name LIKE %s)"
                    params.append("%626287%")
                else:
                    where_clause += " AND (d.name LIKE %s OR d.name = %s)"
                    params.extend([f"%{product_id}%", product_id])

            if start_hour is not None:
                where_clause += " AND HOUR(e.timestamp) >= %s"
                params.append(start_hour)
            if end_hour is not None:
                where_clause += " AND HOUR(e.timestamp) <= %s"
                params.append(end_hour)

            cursor.execute(f"""
                SELECT e.violation_type, COUNT(*) as cnt 
                FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {"LEFT JOIN sop_definitions d ON e.definition_id = d.id" if product_id else ""}
                {where_clause}
                GROUP BY e.violation_type
            """, tuple(params))
            rows = cursor.fetchall()
            dist = {}
            for row in rows:
                vtype = row["violation_type"]
                if vtype == "premature_restart":
                    vtype = "skip_step"
                dist[vtype] = dist.get(vtype, 0) + row["cnt"]
            return dist
        except Exception as e:
            logger.error(f"DB Error getting daily distribution: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_weekly_trend(target_date: str, camera_id: Optional[str] = None, product_id: Optional[str] = None, start_hour: Optional[int] = None, end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lấy xu hướng vi phạm 7 ngày (Thứ 2 -> Chủ Nhật) của tuần chứa target_date."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
        if product_id == "undefined" or not product_id:
            product_id = None
            
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
            if product_id:
                if product_id == "TFF4040":
                    where_clause += " AND (d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s)"
                    params.extend(["%TFF4040%", "%Reformed%", "%TEST MODEL%", "%Sản phẩm A%"])
                elif product_id == "626287":
                    where_clause += " AND (d.name LIKE %s)"
                    params.append("%626287%")
                else:
                    where_clause += " AND (d.name LIKE %s OR d.name = %s)"
                    params.extend([f"%{product_id}%", product_id])

            if start_hour is not None:
                where_clause += " AND HOUR(e.timestamp) >= %s"
                params.append(start_hour)
            if end_hour is not None:
                where_clause += " AND HOUR(e.timestamp) <= %s"
                params.append(end_hour)

            # Lấy dữ liệu gộp theo ngày
            cursor.execute(f"""
                SELECT DATE(e.timestamp) as date, COUNT(*) as cnt 
                FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {"LEFT JOIN sop_definitions d ON e.definition_id = d.id" if product_id else ""}
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
    def get_hourly_stats(target_date: str, camera_id: Optional[str] = None, product_id: Optional[str] = None, start_hour: Optional[int] = None, end_hour: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lấy số liệu vi phạm và hoàn thành theo từng giờ trong ngày target_date."""
        if camera_id == "undefined" or not camera_id:
            camera_id = None
        if product_id == "undefined" or not product_id:
            product_id = None
            
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clause = "WHERE DATE(e.timestamp) = %s"
            params = [target_date]
            
            if camera_id:
                where_clause += " AND c.station_id = %s"
                params.append(camera_id)
            if product_id:
                if product_id == "TFF4040":
                    where_clause += " AND (d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s)"
                    params.extend(["%TFF4040%", "%Reformed%", "%TEST MODEL%", "%Sản phẩm A%"])
                elif product_id == "626287":
                    where_clause += " AND (d.name LIKE %s)"
                    params.append("%626287%")
                else:
                    where_clause += " AND (d.name LIKE %s OR d.name = %s)"
                    params.extend([f"%{product_id}%", product_id])

            if start_hour is not None:
                where_clause += " AND HOUR(e.timestamp) >= %s"
                params.append(start_hour)
            if end_hour is not None:
                where_clause += " AND HOUR(e.timestamp) <= %s"
                params.append(end_hour)

            cursor.execute(f"""
                SELECT HOUR(e.timestamp) as hr,
                       SUM(CASE WHEN e.sop_status = 'violation' THEN 1 ELSE 0 END) as violations,
                       SUM(CASE WHEN e.sop_status = 'completed' THEN 1 ELSE 0 END) as completions
                FROM sop_events e
                {"JOIN sop_cameras c ON e.camera_id = c.id" if camera_id else ""}
                {"LEFT JOIN sop_definitions d ON e.definition_id = d.id" if product_id else ""}
                {where_clause}
                GROUP BY HOUR(e.timestamp)
                ORDER BY hr
            """, tuple(params))
            
            db_data = {row["hr"]: {"violations": int(row["violations"]), "completions": int(row["completions"])} for row in cursor.fetchall()}
            
            hourly = []
            start_h = start_hour if start_hour is not None else 0
            end_h = end_hour if end_hour is not None else 23
            for h in range(start_h, end_h + 1):
                data = db_data.get(h, {"violations": 0, "completions": 0})
                hourly.append({
                    "hour": f"{h:02d}:00",
                    "violations": data["violations"],
                    "completions": data["completions"]
                })
            return hourly
        except Exception as e:
            logger.error(f"DB Error getting hourly stats: {e}")
            start_h = start_hour if start_hour is not None else 0
            end_h = end_hour if end_hour is not None else 23
            return [{"hour": f"{h:02d}:00", "violations": 0, "completions": 0} for h in range(start_h, end_h + 1)]
        finally:
            if 'cursor' in locals() and cursor: cursor.close()
            if 'conn' in locals() and conn: conn.close()

    @staticmethod
    def get_events_by_camera(camera_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Truy vấn vi phạm theo camera station_id.
        """
        conn = db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT e.*, c.station_id FROM sop_events e
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

    @staticmethod
    def get_filtered_events(camera_id: Optional[str] = None,
                            product_id: Optional[str] = None,
                            date: Optional[str] = None,
                            hour: Optional[int] = None,
                            days: Optional[int] = 15,
                            page: int = 1,
                            limit: int = 50) -> Dict[str, Any]:
        """
        Truy vấn danh sách vi phạm được lọc theo camera, mã sản phẩm, ngày, giờ và phân trang (mặc định 15 ngày).
        """
        import math
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            where_clauses = ["e.sop_status = 'violation'"]
            params = []
            
            if camera_id:
                where_clauses.append("c.station_id = %s")
                params.append(camera_id)
            if product_id:
                if product_id == "TFF4040":
                    where_clauses.append("(d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s OR d.name LIKE %s)")
                    params.extend(["%TFF4040%", "%Reformed%", "%TEST MODEL%", "%Sản phẩm A%"])
                elif product_id == "626287":
                    where_clauses.append("(d.name LIKE %s)")
                    params.append("%626287%")
                else:
                    where_clauses.append("(d.name LIKE %s OR d.name = %s)")
                    params.extend([f"%{product_id}%", product_id])
            if date:
                where_clauses.append("DATE(e.timestamp) = %s")
                params.append(date)
            elif days:
                where_clauses.append("e.timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)")
                params.append(int(days))

            if hour is not None and hour != "":
                where_clauses.append("HOUR(e.timestamp) = %s")
                params.append(int(hour))

            where_str = " WHERE " + " AND ".join(where_clauses)

            # 1. Đếm tổng số bản ghi
            count_query = f"""
                SELECT COUNT(*) as total
                FROM sop_events e
                LEFT JOIN sop_cameras c ON e.camera_id = c.id
                LEFT JOIN sop_definitions d ON e.definition_id = d.id
                {where_str}
            """
            cursor.execute(count_query, tuple(params))
            count_row = cursor.fetchone()
            total_count = count_row["total"] if count_row else 0

            # 2. Truy vấn dữ liệu theo trang
            offset = max(0, (page - 1) * limit)
            query = f"""
                SELECT e.*, c.station_id, d.name as definition_name, cl.duration_sec as clip_duration
                FROM sop_events e
                LEFT JOIN sop_cameras c ON e.camera_id = c.id
                LEFT JOIN sop_definitions d ON e.definition_id = d.id
                LEFT JOIN sop_clips cl ON cl.event_id = e.id
                {where_str}
                ORDER BY e.timestamp DESC LIMIT %s OFFSET %s
            """
            data_params = list(params) + [limit, offset]
            cursor.execute(query, tuple(data_params))
            events = cursor.fetchall()

            total_pages = math.ceil(total_count / limit) if limit > 0 else 1

            return {
                "events": events,
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": max(1, total_pages)
            }
        except Exception as e:
            logger.error(f"DB Error getting filtered events: {e}")
            return {"events": [], "total": 0, "page": 1, "limit": limit, "total_pages": 1}
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

    @staticmethod
    def get_products_by_camera(station_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các mã sản phẩm (definitions) liên kết hoặc từng chạy trên camera."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT d.id, d.name 
                FROM sop_definitions d
                JOIN sop_cameras c ON c.definition_id = d.id OR d.id IN (
                    SELECT DISTINCT e.definition_id 
                    FROM sop_events e 
                    WHERE e.camera_id = c.id
                )
                WHERE c.station_id = %s
                ORDER BY d.name
            """, (station_id,))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting products for camera {station_id}: {e}")
            return []
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

    @staticmethod
    def get_all_definitions() -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả định nghĩa SOP (mã hàng)."""
        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name FROM sop_definitions ORDER BY name")
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"DB Error getting all definitions: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
