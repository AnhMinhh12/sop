"""
Dataclass definitions for SOP database tables.
Provides type-safe representations of each sop_* table row.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SOPDefinition:
    """Represents a row in sop_definitions — template quy trình SOP."""
    id: int = 0
    name: str = ""
    description: Optional[str] = None
    total_steps: int = 0
    version: str = "1.0"
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class SOPStep:
    """Represents a row in sop_steps — 1 bước trong quy trình."""
    id: int = 0
    definition_id: int = 0
    step_order: int = 0
    step_name: str = ""
    step_label: str = ""
    max_duration_ms: Optional[int] = None
    is_mandatory: bool = True


@dataclass
class SOPCamera:
    """Represents a row in sop_cameras."""
    id: int = 0
    station_id: str = ""
    name: str = ""
    rtsp_url: str = ""
    definition_id: Optional[int] = None
    status: str = "active"
    created_at: Optional[datetime] = None


@dataclass
class SOPSession:
    """Represents a row in sop_sessions — 1 phiên làm việc."""
    id: int = 0
    camera_id: int = 0
    definition_id: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_steps: int = 0
    correct_steps: int = 0
    compliance_rate: Optional[float] = None


@dataclass
class SOPEvent:
    """Represents a row in sop_events — sự kiện vi phạm."""
    id: int = 0
    session_id: Optional[int] = None
    camera_id: int = 0
    timestamp: Optional[datetime] = None
    step_detected: str = ""
    confidence: Optional[float] = None
    sop_status: str = ""
    violation_type: Optional[str] = None
    expected_step: Optional[str] = None
    clip_path: Optional[str] = None


@dataclass
class SOPClip:
    """Represents a row in sop_clips — clip video vi phạm."""
    id: int = 0
    event_id: Optional[int] = None
    camera_id: int = 0
    file_path: str = ""
    file_size_mb: Optional[float] = None
    duration_sec: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class SOPHealth:
    """Represents a row in sop_health — system monitoring."""
    id: int = 0
    camera_id: int = 0
    fps: Optional[float] = None
    latency_ms: Optional[float] = None
    cpu_usage: Optional[float] = None
    ram_used_mb: Optional[int] = None
    disk_free_gb: Optional[float] = None
    checked_at: Optional[datetime] = None
