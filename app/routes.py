import cv2
import os
import time
import psutil
from flask import render_template, Response, jsonify, request, send_from_directory
from app import app, processors
from services.config_loader import ConfigLoader
from services.disk_monitor import DiskMonitor
from db.db import db
from db.queries import EventQueries

#xin chao
@app.route('/')
def index():
    """Trang chủ dashboard SOP (Tổng hợp)."""
    return render_template('index.html')


@app.route('/station/<camera_id>')
def station(camera_id):
    """Trang chi tiết từng trạm camera."""
    return render_template('station.html', camera_id=camera_id)


@app.route('/history')
def history():
    """Trang lịch sử vi phạm."""
    return render_template('history.html')


@app.route('/stats')
def stats():
    """Trang thống kê quy trình."""
    return render_template('stats.html')


def gen_frames(camera_id: str):
    """Máy phát luồng MJPEG cho trình duyệt — Tối ưu CPU."""
    last_frame_id = None
    cached_bytes = None
    
    while True:
        if camera_id in processors:
            frame = processors[camera_id].get_latest_frame()
            if frame is not None:
                # Chỉ encode lại khi frame thực sự thay đổi (tránh encode lại cùng 1 frame)
                frame_id = id(frame)
                if frame_id != last_frame_id:
                    try:
                        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        cached_bytes = buffer.tobytes()
                        last_frame_id = frame_id
                    except Exception:
                        pass
                
                if cached_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + cached_bytes + b'\r\n')
        # Giảm xuống ~10 FPS — Mắt người không phân biệt 10 vs 15 FPS trên dashboard
        time.sleep(0.1)


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
    camera_id = request.args.get('camera_id', None)

    if camera_id:
        events = EventQueries.get_events_by_camera(camera_id, limit=limit)
    else:
        events = EventQueries.get_recent_events(limit=limit)

    # Chuyển datetime thành string để JSON serialize được
    for ev in events:
        if ev.get("timestamp"):
            ev["timestamp"] = str(ev["timestamp"])

    return jsonify(events)


@app.route('/api/stats/summary')
def get_stat_summary():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    summary = EventQueries.get_daily_summary(target_date, camera_id=camera_id)
    return jsonify(summary)


@app.route('/api/stats/trend')
def get_stat_trend():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    trend = EventQueries.get_weekly_trend(target_date, camera_id=camera_id)
    return jsonify(trend)


@app.route('/api/stats/distribution')
def get_stat_distribution():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    dist = EventQueries.get_daily_distribution(target_date, camera_id=camera_id)
    return jsonify(dist)


@app.route('/api/stats/violations')
def get_violation_stats():
    """Thống kê vi phạm theo loại (Tổng tất cả)."""
    counts = EventQueries.get_violation_counts()
    return jsonify(counts)


@app.route('/api/system/health')
def get_health():
    stats = DiskMonitor.get_system_stats()
    return jsonify(stats)


@app.route('/clip/<int:event_id>')
def get_clip_by_id(event_id):
    """Lấy đường dẫn clip từ sop_events và serve file."""
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT clip_path FROM sop_events WHERE id = %s", (event_id,)
        )
        event = cursor.fetchone()
        if event and event['clip_path'] and os.path.exists(event['clip_path']):
            filename = os.path.basename(event['clip_path'])
            return send_from_directory(os.path.abspath("data/violations"), filename)
        return "Clip not found", 404
    finally:
        cursor.close()
        conn.close()


@app.route('/data/violations/<path:filename>')
def serve_violation_file(filename):
    """Serve trực tiếp file từ thư mục violations."""
    return send_from_directory(os.path.abspath("data/violations"), filename)
