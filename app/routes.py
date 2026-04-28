import cv2
import time
import psutil
from flask import render_template, Response, jsonify, request
from app import app, processors
from services.config_loader import ConfigLoader
from services.disk_monitor import DiskMonitor
from db.queries import EventQueries

@app.route('/')
def index():
    """Trang chủ dashboard."""
    return render_template('index.html')

def gen_frames(camera_id: str):
    """Máy phát luồng MJPEG cho trình duyệt."""
    while True:
        if camera_id in processors:
            frame = processors[camera_id].get_latest_frame()
            if frame is not None:
                try:
                    # Trả lại độ nét gốc cho người dùng
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                except Exception:
                    pass
        # Nghỉ lâu hơn một chút (~15 FPS) để CPU nhẹ gánh
        time.sleep(0.07)

@app.route('/video_feed/<camera_id>')
def video_feed(camera_id):
    """Endpoint cho livestream."""
    return Response(gen_frames(camera_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/cameras')
def get_cameras():
    config = ConfigLoader.load_config()
    return jsonify(config.get("cameras", []))

@app.route('/api/events')
def get_events():
    limit = request.args.get('limit', 50, type=int)
    events = EventQueries.get_recent_events(limit=limit)
    return jsonify(events)

@app.route('/api/system/health')
def get_health():
    stats = DiskMonitor.get_system_stats()
    return jsonify(stats)

@app.route('/clip/<int:event_id>')
def get_clip_by_id(event_id):
    """Lấy đường dẫn clip từ DB và serve file."""
    conn = db.get_connection()
    conn.row_factory = Database.dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT clip_path FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        if event and event['clip_path'] and os.path.exists(event['clip_path']):
            filename = os.path.basename(event['clip_path'])
            return send_from_directory(os.path.abspath("data/violations"), filename)
        return "Clip not found", 404
    finally:
        conn.close()

@app.route('/data/violations/<path:filename>')
def serve_violation_file(filename):
    """Serve trực tiếp file từ thư mục violations."""
    return send_from_directory(os.path.abspath("data/violations"), filename)

import os
from flask import send_from_directory
from db.db import db, Database
