import os
import logging
import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Database:
    """
    MySQL database connection pool and schema initialization.
    Uses DBUtils.PooledDB for thread-safe connection reuse.
    All SOP tables use 'sop_' prefix to avoid conflicts with legacy tables.
    """

    def __init__(self):
        try:
            self.pool = PooledDB(
                creator=pymysql,
                mincached=1,       # Giảm xuống 1 để khởi động nhanh hơn
                maxcached=5,
                maxconnections=10,
                blocking=True,
                host=os.getenv("DB_HOST", "10.0.10.13"),
                port=int(os.getenv("DB_PORT", 3306)),
                user=os.getenv("DB_USER", "minhha"),
                password=os.getenv("DB_PASSWORD", "Htmp1234"),
                database=os.getenv("DB_NAME", "ai_system"),
                charset="utf8mb4",
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10, # Tăng timeout lên 10s cho mạng chậm
            )
            logger.info(
                f"Database: Connected to MySQL "
                f"{os.getenv('DB_HOST', '10.0.10.13')}:{os.getenv('DB_PORT', 3306)} "
                f"successfully."
            )
            self._init_tables()
        except Exception as e:
            logger.error(f"!!! DATABASE ERROR: Could not connect to MySQL at {os.getenv('DB_HOST')}. Error: {e}")
            logger.warning("System will continue but database logging will be DISABLED. Please check your network/VPN.")
            self.pool = None

    def get_connection(self):
        """Get a connection from the pool. Caller MUST close() it to return to pool."""
        if self.pool is None:
            return None
        return self.pool.connection()

    def _init_tables(self):
        """Create all sop_* tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 1. sop_definitions — Template quy trình SOP
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_definitions (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    name            VARCHAR(255) NOT NULL UNIQUE,
                    description     TEXT DEFAULT NULL,
                    total_steps     INT NOT NULL DEFAULT 0,
                    version         VARCHAR(20) DEFAULT '1.0',
                    is_active       TINYINT(1) DEFAULT 1,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 2. sop_steps — Các bước thuộc 1 definition
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_steps (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    definition_id   INT NOT NULL,
                    step_order      INT NOT NULL,
                    step_name       VARCHAR(255) NOT NULL,
                    step_label      VARCHAR(100) NOT NULL,
                    max_duration_ms INT DEFAULT NULL,
                    is_mandatory    TINYINT(1) DEFAULT 1,
                    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE,
                    UNIQUE(definition_id, step_order)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 3. sop_cameras — Camera gắn với 1 definition
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_cameras (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    station_id      VARCHAR(50) NOT NULL UNIQUE,
                    name            VARCHAR(255) NOT NULL,
                    rtsp_url        TEXT NOT NULL,
                    definition_id   INT DEFAULT NULL,
                    status          VARCHAR(20) DEFAULT 'active',
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 4. sop_sessions — Phiên làm việc
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_sessions (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    camera_id       INT NOT NULL,
                    definition_id   INT NOT NULL,
                    start_time      DATETIME NOT NULL,
                    end_time        DATETIME DEFAULT NULL,
                    total_steps     INT DEFAULT 0,
                    correct_steps   INT DEFAULT 0,
                    compliance_rate FLOAT DEFAULT NULL,
                    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
                    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 5. sop_events — Sự kiện vi phạm
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_events (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id      INT DEFAULT NULL,
                    camera_id       INT NOT NULL,
                    definition_id   INT DEFAULT NULL,
                    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
                    step_detected   VARCHAR(255) NOT NULL,
                    confidence      FLOAT DEFAULT NULL,
                    sop_status      VARCHAR(50) NOT NULL,
                    violation_type  VARCHAR(100) DEFAULT NULL,
                    expected_step   VARCHAR(255) DEFAULT NULL,
                    clip_path       TEXT DEFAULT NULL,
                    FOREIGN KEY (session_id) REFERENCES sop_sessions(id) ON DELETE SET NULL,
                    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE,
                    FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # MỚI: Migration tự động thêm cột definition_id nếu bảng đã tồn tại từ bản cũ
            try:
                cursor.execute("SHOW COLUMNS FROM sop_events LIKE 'definition_id'")
                if not cursor.fetchone():
                    logger.info("Database: Migrating sop_events - adding definition_id column...")
                    cursor.execute("ALTER TABLE sop_events ADD COLUMN definition_id INT DEFAULT NULL AFTER camera_id")
                    cursor.execute("ALTER TABLE sop_events ADD CONSTRAINT fk_event_definition FOREIGN KEY (definition_id) REFERENCES sop_definitions(id) ON DELETE SET NULL")
            except Exception as e:
                logger.warning(f"Database: Migration notice (sop_events): {e}")

            # 6. sop_clips — Clip video vi phạm
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_clips (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    event_id        BIGINT DEFAULT NULL,
                    camera_id       INT NOT NULL,
                    file_path       TEXT NOT NULL,
                    file_size_mb    FLOAT DEFAULT NULL,
                    duration_sec    INT DEFAULT NULL,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES sop_events(id) ON DELETE SET NULL,
                    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 7. sop_health — Monitor hệ thống
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_health (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    camera_id       INT NOT NULL,
                    fps             FLOAT DEFAULT NULL,
                    latency_ms      FLOAT DEFAULT NULL,
                    cpu_usage       FLOAT DEFAULT NULL,
                    ram_used_mb     INT DEFAULT NULL,
                    disk_free_gb    FLOAT DEFAULT NULL,
                    checked_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (camera_id) REFERENCES sop_cameras(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # --- Indexes ---
            index_statements = [
                "CREATE INDEX idx_sop_events_camera_time ON sop_events(camera_id, timestamp)",
                "CREATE INDEX idx_sop_events_session ON sop_events(session_id)",
                "CREATE INDEX idx_sop_sessions_camera ON sop_sessions(camera_id)",
                "CREATE INDEX idx_sop_sessions_def ON sop_sessions(definition_id)",
                "CREATE INDEX idx_sop_health_time ON sop_health(checked_at)",
                "CREATE INDEX idx_sop_health_camera ON sop_health(camera_id)",
                "CREATE INDEX idx_sop_clips_created ON sop_clips(created_at)",
                "CREATE INDEX idx_sop_steps_def ON sop_steps(definition_id)",
            ]
            for stmt in index_statements:
                try:
                    cursor.execute(stmt)
                except pymysql.err.OperationalError as e:
                    # Index đã tồn tại — bỏ qua (error code 1061)
                    if e.args[0] != 1061:
                        raise

            logger.info("Database: All 7 sop_* tables initialized successfully.")

        except Exception as e:
            logger.error(f"Database: Error initializing tables: {e}")
            raise
        finally:
            cursor.close()
            conn.close()


# Singleton instance — khởi tạo khi import
db = Database()
