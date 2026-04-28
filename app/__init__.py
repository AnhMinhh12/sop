import os
import logging
from flask import Flask
from flask_socketio import SocketIO
from typing import Dict, Any

# Initialize Flask & SocketIO
app = Flask(__name__, 
            template_folder='templates', 
            static_folder='static')
app.config['SECRET_KEY'] = 'sop_monitoring_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global storage for processors
processors: Dict[str, Any] = {}

# Import all routes from the central routes.py
from app import routes

def emit_step_update(camera_id, status_data, hands_detected):
    socketio.emit('step_update', {
        'camera_id': camera_id,
        'current_step': status_data.get('expected_step', 'Ready'),
        'detected_step': status_data.get('detected_label', 'Idle'),
        'status_msg': status_data.get('status_msg', ''),
        'hit_count': status_data.get('hit_count', 0),
        'step_index': status_data.get('step_index', 0),
        'step_list': status_data.get('step_list', []), # Danh sách các bước
        'confidence': status_data.get('confidence', 0),
        'sop_status': status_data.get('sop_status', 'idle'),
        'progress_percent': status_data.get('progress_percent', 0),
        'hands_detected': hands_detected
    })

def emit_violation(camera_id, violation_data):
    import time
    socketio.emit('violation', {
        'camera_id': camera_id,
        'violation_type': violation_data.get('violation_type'),
        'timestamp': time.strftime('%H:%M:%S')
    })
