import os
import logging
import time
import threading
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from typing import Dict, Any

# Initialize Flask & SocketIO
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app, resources={r"/static/*": {"origins": "*"}, r"/api/*": {"origins": "*"}})
app.config['SECRET_KEY'] = os.getenv("APP_SECRET_KEY", "sop_monitoring_secret_default")
app.config['HUB_URL'] = os.getenv("HUB_URL", "")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global storage for processors (local AI mode)
processors: Dict[str, Any] = {}

# Global storage for external frames (aggregator mode)
# Structure: {camera_id: {"frame": bytes, "timestamp": float}}
external_frames: Dict[str, Dict[str, Any]] = {}
_frame_cache_ttl = 10  # seconds before marking edge as offline


def _init_frame_cache_cleanup():
    """Background thread to clean up stale external frames."""
    def cleanup_loop():
        while True:
            time.sleep(5)  # Check every 5 seconds
            current_time = time.time()
            stale_cameras = []

            for cam_id, data in external_frames.items():
                if current_time - data.get("timestamp", 0) > _frame_cache_ttl:
                    stale_cameras.append(cam_id)

            for cam_id in stale_cameras:
                if cam_id in external_frames:
                    del external_frames[cam_id]
                    logging.warning(f"External frame cache expired for camera: {cam_id}")

    t = threading.Thread(target=cleanup_loop, daemon=True)
    t.start()


# Start frame cache cleanup
_init_frame_cache_cleanup()

# Import all routes from the central routes.py
from app import routes

def emit_step_update(camera_id, status_data, hands_detected):
    socketio.emit('step_update', {
        'camera_id': camera_id,
        'cycle_count': status_data.get('cycle_count', 0),
        'current_step': status_data.get('expected_step', 'Ready'),
        'detected_step': status_data.get('detected_label', 'Idle'),
        'status_msg': status_data.get('status_msg', ''),
        'hit_count': status_data.get('hit_count', 0),
        'step_index': status_data.get('step_index', 0),
        'step_list': status_data.get('step_list', []), # Danh sách các bước
        'confidence': status_data.get('confidence', 0),
        'sop_status': status_data.get('sop_status', 'idle'),
        'progress_percent': status_data.get('progress_percent', 0),
        'hands_detected': hands_detected,
        'cycle_time_left': status_data.get('cycle_time_left', 38.0)
    })

def emit_violation(camera_id, violation_data):
    import time
    socketio.emit('violation', {
        'camera_id': camera_id,
        'violation_type': violation_data.get('violation_type'),
        'expected_step': violation_data.get('expected_step', 'N/A'),
        'detected_step': violation_data.get('detected_label', 'N/A'), # Sẽ đồng bộ key sang detected_step
        'timestamp': time.strftime('%H:%M:%S')
    })

def emit_camera_status(camera_id: str, status: str):
    """
    Emits camera status updates (connected, error, disconnected).
    """
    socketio.emit('camera_status', {
        'camera_id': camera_id,
        'status': status
    })
