import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class Database:
    """
    Handles SQLite database connection and table initialization.
    Uses WAL (Write-Ahead Logging) mode for better concurrency.
    """
    def __init__(self, db_path: str = "data/sop_monitoring.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        # Kích hoạt chế độ WAL
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @staticmethod
    def dict_factory(cursor, row):
        """Helper to convert sqlite row to dict."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _init_db(self):
        """
        Initializes the database schema if it doesn't exist.
        """
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path))

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 1. Cameras table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id  TEXT NOT NULL UNIQUE,
                    name        TEXT NOT NULL,
                    rtsp_url    TEXT NOT NULL,
                    status      TEXT DEFAULT 'active',
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. SOP Steps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sop_steps (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id      TEXT NOT NULL,
                    step_order      INTEGER NOT NULL,
                    step_name       TEXT NOT NULL,
                    step_label      TEXT NOT NULL,
                    max_duration_ms INTEGER,
                    is_mandatory    INTEGER DEFAULT 1
                )
            """)

            # 3. Sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id       INTEGER REFERENCES cameras(id),
                    start_time      DATETIME NOT NULL,
                    end_time        DATETIME,
                    total_steps     INTEGER DEFAULT 0,
                    correct_steps   INTEGER DEFAULT 0,
                    compliance_rate REAL
                )
            """)

            # 4. Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      INTEGER REFERENCES sessions(id),
                    camera_id       INTEGER REFERENCES cameras(id),
                    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
                    step_detected   TEXT NOT NULL,
                    confidence      REAL,
                    sop_status      TEXT NOT NULL,
                    violation_type  TEXT,
                    expected_step   TEXT,
                    clip_path       TEXT
                )
            """)

            # 5. Violation Clips
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS violation_clips (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id        INTEGER REFERENCES events(id),
                    camera_id       INTEGER REFERENCES cameras(id),
                    file_path       TEXT NOT NULL,
                    file_size_mb    REAL,
                    duration_sec    INTEGER,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 6. System Health
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_health (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id   INTEGER REFERENCES cameras(id),
                    fps         REAL,
                    latency_ms  REAL,
                    cpu_usage   REAL,
                    ram_used_mb INTEGER,
                    disk_free_gb REAL,
                    checked_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_camera_time ON events(camera_id, timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_time ON system_health(checked_at)")

            conn.commit()
            logger.info("Database initialized successfully with WAL mode.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()

# Singleton instance
db = Database()
