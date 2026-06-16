import cv2
import os
import time
import psutil
import logging
from flask import render_template, Response, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)
from app import app, processors
from shared.services.config_loader import ConfigLoader
from shared.services.disk_monitor import DiskMonitor
from shared.db.db import db
from shared.db.queries import EventQueries, CameraQueries, DefinitionQueries

#xin chao
@app.route('/')
def index():
    """Trang chủ AI Monitoring Hub (Tổng hợp các dự án)."""
    return render_template('portal.html')


@app.route('/sop')
def sop_dashboard():
    """Trang lưới camera cho dự án SOP Monitoring."""
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
    last_loop_count = -1
    cached_bytes = None
    
    while True:
        if camera_id in processors:
            proc = processors[camera_id]
            loop_count = proc._loop_count
            if loop_count != last_loop_count:
                frame = proc.get_latest_frame()
                if frame is not None:
                    try:
                        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        cached_bytes = buffer.tobytes()
                        last_loop_count = loop_count
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


@app.route('/api/shared/templates/<path:template_name>')
def get_shared_template(template_name):
    """API cho phép các server con lấy nội dung file giao diện chuẩn."""
    # Chỉ cho phép lấy các template an toàn
    allowed_templates = ['base.html', 'partials/sidebar.html', 'partials/header.html', 'partials/modals.html']
    
    if template_name not in allowed_templates:
        return jsonify({"error": "Template not found or not allowed"}), 404
        
    try:
        # Sử dụng đường dẫn tuyệt đối để tránh lỗi Errno 2 khi chạy từ thư mục khác
        template_path = os.path.join(app.root_path, app.template_folder, template_name)
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype='text/html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/shared/manifest')
def get_ui_manifest():
    """API trả về thông tin phiên bản giao diện hiện tại."""
    try:
        manifest_path = os.path.join(app.root_path, app.static_folder, 'ui_manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                import json
                return jsonify(json.load(f))
        return jsonify({"error": "Manifest not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/cameras')
def get_cameras():
    config = ConfigLoader.load_config()
    return jsonify(config.get("cameras", []))


@app.route('/api/events')
def get_events():
    limit = request.args.get('limit', 50, type=int)
    camera_id = request.args.get('camera_id', None)
    product_id = request.args.get('product_id', None)
    date = request.args.get('date', None)

    events = EventQueries.get_filtered_events(camera_id=camera_id, product_id=product_id, date=date, limit=limit)

    # Chuyển datetime và BIGINT thành string để tránh lỗi precision ở Frontend JS
    for ev in events:
        if ev.get("id"):
            ev["id"] = str(ev["id"])
        if ev.get("camera_id"):
            ev["camera_id"] = str(ev["camera_id"])
        if ev.get("station_id"):
            ev["station_id"] = str(ev["station_id"])
        if ev.get("timestamp"):
            ev["timestamp"] = str(ev["timestamp"])

    return jsonify(events)


@app.route('/api/station/<camera_id>/products')
def get_station_products(camera_id):
    def map_raw_to_clean_product(raw_name: str) -> str:
        if not raw_name:
            return None
        raw_name_lower = raw_name.lower()
        if "626287" in raw_name_lower:
            return "626287"
        if any(k in raw_name_lower for k in ["tff4040", "reformed", "test model", "sản phẩm a"]):
            return "TFF4040"
        if "laprap" in raw_name_lower:
            return "laprap"
        return None

    try:
        products = []
        if camera_id and camera_id not in ["all", "undefined", "null"]:
            products = CameraQueries.get_products_by_camera(camera_id)
        
        # If camera_id is "all" or the query returned no records, load all definitions from DB
        if not products:
            conn = db.get_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT id, name FROM sop_definitions ORDER BY name")
                    products = cursor.fetchall()
                    cursor.close()
                except Exception as db_err:
                    logger.warning(f"Failed to query all products from DB: {db_err}")
                finally:
                    conn.close()
            
        config = ConfigLoader.load_config()
        products_cfg = config.get("products", [])

        # If we got products from DB, map them to clean IDs
        clean_ids = set()
        if camera_id == "machine_07":
            clean_ids = {"TFF4040", "626287"}
        elif camera_id == "machine_08":
            clean_ids = {"laprap"}
        else:
            for p in products:
                name = p.get("name", "")
                clean_id = map_raw_to_clean_product(name)
                if clean_id:
                    clean_ids.add(clean_id)

        # Build response list matching config.yaml definitions
        res = []
        for p in products_cfg:
            p_id = p.get("id")
            if p_id in clean_ids:
                res.append({"id": p_id, "name": p.get("name")})

        # Fallback to all config products if no match found
        if not res:
            res = [{"id": p.get("id"), "name": p.get("name")} for p in products_cfg]

        return jsonify(res)
    except Exception as e:
        logger.error(f"Error in get_station_products: {e}")
        return jsonify([])


@app.route('/api/stats/summary')
def get_stat_summary():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    summary = EventQueries.get_daily_summary(target_date, camera_id=camera_id, product_id=product_id)
    return jsonify(summary)


@app.route('/api/stats/trend')
def get_stat_trend():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    trend = EventQueries.get_weekly_trend(target_date, camera_id=camera_id, product_id=product_id)
    return jsonify(trend)


@app.route('/api/stats/distribution')
def get_stat_distribution():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    dist = EventQueries.get_daily_distribution(target_date, camera_id=camera_id, product_id=product_id)
    return jsonify(dist)


@app.route('/api/stats/hourly')
def get_stat_hourly():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    hourly = EventQueries.get_hourly_stats(target_date, camera_id=camera_id, product_id=product_id)
    return jsonify(hourly)


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
        
        # Thử nhiều cách để tìm file clip
        if event and event['clip_path']:
            clip_path = event['clip_path']
            filename = os.path.basename(clip_path)
            
            # Tính toán project root tuyệt đối dựa trên vị trí file routes.py hiện tại
            app_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(app_dir)
            violations_dir = os.path.join(project_root, "data", "violations")
            
            # 1. Thử path tuyệt đối từ DB
            target_path = ""
            if os.path.exists(clip_path):
                target_path = os.path.abspath(clip_path)
            else:
                # 2. Thử tìm trong thư mục violations mặc định của project root
                full_path = os.path.join(violations_dir, filename)
                if os.path.exists(full_path):
                    target_path = os.path.abspath(full_path)
                else:
                    # 3. Thử tìm trong CWD hiện tại
                    cwd_path = os.path.abspath(os.path.join("data", "violations", filename))
                    if os.path.exists(cwd_path):
                        target_path = cwd_path

            if target_path:
                # Dùng send_file với conditional=True để hỗ trợ Range Requests (tua video)
                from flask import send_file
                return send_file(
                    target_path, 
                    mimetype='video/mp4',
                    as_attachment=False,
                    conditional=True
                )
                
        logger.warning(f"Clip not found for event_id={event_id}")
        return "Clip not found", 404
    finally:
        cursor.close()
        conn.close()


@app.route('/data/violations/<path:filename>')
def serve_violation_file(filename):
    """Serve trực tiếp file từ thư mục violations."""
    return send_from_directory(os.path.abspath("data/violations"), filename)
@app.route('/api/products')
def get_products():
    """Lấy danh sách mã sản phẩm từ config."""
    config = ConfigLoader.load_config()
    return jsonify(config.get("products", []))


@app.route('/api/station/<camera_id>/switch_product', methods=['POST'])
def switch_product(camera_id):
    """Chuyển đổi mã sản phẩm cho 1 trạm cụ thể."""
    data = request.json
    product_id = data.get('product_id')
    
    if camera_id not in processors:
        return jsonify({"success": False, "error": "Camera not found"}), 404
        
    config = ConfigLoader.load_config()
    # Tìm thông tin sản phẩm trong config
    product = next((p for p in config.get("products", []) if p['id'] == product_id), None)
    
    if not product:
        return jsonify({"success": False, "error": "Product not found in config"}), 400
        
    # Load SOP definition cho mã hàng này
    # Giả sử sop_file trong config là đường dẫn tương đối từ project root
    sop_def = ConfigLoader.load_yaml(product['sop_file'])
    if not sop_def:
        return jsonify({"success": False, "error": "Failed to load SOP definition"}), 500
        
    # 1. Chuyển đổi Engine thực tế (Real-time logic)
    success = processors[camera_id].switch_engine(product_id, sop_def)
    
    if success:
        # 2. Cập nhật Database để Dashboard (History/Stats) biết về mã hàng mới
        # Upsert định nghĩa và sync các bước
        def_name = f"{product['name']} (Auto)"
        def_id = DefinitionQueries.upsert_definition(def_name, total_steps=len(sop_def.get("steps", [])))
        if def_id:
            DefinitionQueries.sync_steps(def_id, sop_def.get("steps", []))
            # Cập nhật liên kết camera - định nghĩa mới
            CameraQueries.update_camera_definition(camera_id, def_id)
            
        return jsonify({"success": True, "message": f"Switched to {product['name']}"})
    else:
        return jsonify({"success": False, "error": "Engine failed to switch"}), 500


@app.route('/api/station/<camera_id>/sop')
def get_station_sop(camera_id):
    """Lấy danh sách các bước SOP hiện tại của trạm."""
    # 1. Ưu tiên lấy SOP đang chạy từ FrameProcessor nếu có (đã switch product)
    if camera_id in processors and getattr(processors[camera_id], 'sop_config', None):
        steps = processors[camera_id].sop_config.get("steps", [])
        return jsonify(steps)

    config = ConfigLoader.load_config()
    camera = next((c for c in config.get("cameras", []) if c['id'] == camera_id), None)
    
    if not camera:
        return jsonify({"error": "Camera not found"}), 404
        
    sop_file = camera.get('sop_file')
    if not sop_file:
        return jsonify([])
        
    try:
        # Load trực tiếp từ file YAML để đảm bảo luôn có dữ liệu nạp cho Checklist
        sop_def = ConfigLoader.load_yaml(sop_file)
        steps = sop_def.get("steps", [])
        return jsonify(steps)
    except Exception as e:
        logger.error(f"Failed to load SOP file {sop_file}: {e}")
        return jsonify([])
