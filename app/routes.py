import cv2
import os
import time
import json
import psutil
import logging
from flask import render_template, Response, jsonify, request, send_from_directory

logger = logging.getLogger(__name__)
from app import app, processors, emit_step_update
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
    last_emitted_at = 0.0

    while True:
        # Nếu là camera ngoại vi tự push frame lên Hub (Aggregator mode)
        from app import external_frames
        if camera_id in external_frames:
            data = external_frames.get(camera_id, {})
            frame_bytes = data.get("frame") if isinstance(data, dict) else data
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.06)  # Giới hạn khoảng 15 FPS
            continue

        # Local AI mode - đọc từ FrameProcessor
        # Khóa nhẹ để tránh race condition khi đọc _loop_count và frame từ thread xử lý
        if camera_id in processors:
            proc = processors[camera_id]
            try:
                # Đọc loop_count + frame "trong cùng 1 nhịp" với lock nhẹ của processor
                frame = None
                with proc.frame_lock:
                    loop_count = proc._loop_count
                    if loop_count != last_loop_count:
                        frame = proc.current_processed_frame  # đã là bản copy an toàn vì được set tham chiếu
                        last_loop_count = loop_count

                if frame is not None:
                    # JPEG quality 75 (mượt hơn 60 nhưng vẫn nhẹ) + nâng FPS gửi
                    ok, buffer = cv2.imencode(
                        '.jpg', frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                    )
                    if ok:
                        cached_bytes = buffer.tobytes()
            except AttributeError:
                # Fallback nếu processor chưa được thêm frame_lock (backward compat)
                loop_count = proc._loop_count
                if loop_count != last_loop_count:
                    frame = proc.get_latest_frame()
                    if frame is not None:
                        try:
                            ok, buffer = cv2.imencode(
                                '.jpg', frame,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                            )
                            if ok:
                                cached_bytes = buffer.tobytes()
                                last_loop_count = loop_count
                        except Exception:
                            pass

            if cached_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + cached_bytes + b'\r\n')
                last_emitted_at = time.time()
        else:
            # Không có processor → in placeholder đen để báo cho client biết
            # (Tránh trình duyệt treo khi không có dữ liệu)
            pass

        # ~15 FPS nhưng nhanh hơn trước đây để giảm delay cảm nhận được
        time.sleep(0.06)


@app.route('/video_feed/<camera_id>')
def video_feed(camera_id):
    """Endpoint cho livestream."""
    return Response(
        gen_frames(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Accel-Buffering': 'no',  # tắt buffering nếu chạy sau nginx
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/station/<camera_id>/push_frame', methods=['POST'])
def push_frame(camera_id):
    """
    API endpoint để các Edge server đẩy frame đã vẽ và trạng thái FSM lên Hub.
    Yêu cầu X-API-Key header để xác thực.
    """
    import time
    from app import external_frames

    # 1. Validate API Key
    api_key = request.headers.get('X-API-Key')
    expected_key = os.getenv("HUB_API_KEY", "change-me-in-production")
    if api_key != expected_key:
        logger.warning(f"Unauthorized push_frame attempt from camera {camera_id}")
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # 2. Validate camera_id exists in config
    config = ConfigLoader.load_config()
    cameras = {c["id"] for c in config.get("cameras", [])}
    if camera_id not in cameras:
        logger.warning(f"Push frame from unregistered camera: {camera_id}")
        return jsonify({"success": False, "error": "Camera not registered"}), 403

    # 3. Validate image data
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image file provided"}), 400

    file = request.files['image']
    img_bytes = file.read()

    # 4. Lưu vào cache với timestamp
    external_frames[camera_id] = {
        "frame": img_bytes,
        "timestamp": time.time()
    }

    # 5. Nhận trạng thái FSM và phát qua WebSocket
    status_json = request.form.get('status')
    hands_json = request.form.get('hands')

    if status_json:
        try:
            status_data = json.loads(status_json)
            hands_data = json.loads(hands_json) if hands_json else []
            emit_step_update(camera_id, status_data, hands_data)
        except Exception as e:
            logger.error(f"Error parsing external FSM status: {e}")

    return jsonify({"success": True})


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
    page = request.args.get('page', 1, type=int)
    camera_id = request.args.get('camera_id', None)
    product_id = request.args.get('product_id', None)
    date = request.args.get('date', None)
    hour = request.args.get('hour', None)
    
    days_param = request.args.get('days', 15)
    days = int(days_param) if (days_param and str(days_param).isdigit()) else 15
    if date:
        days = None # Nếu người dùng chọn ngày cụ thể, bỏ qua lọc 15 ngày mặc định

    res = EventQueries.get_filtered_events(
        camera_id=camera_id,
        product_id=product_id,
        date=date,
        hour=hour,
        days=days,
        page=page,
        limit=limit
    )

    # Chuyển datetime và BIGINT thành string để tránh lỗi precision ở Frontend JS
    events = res.get("events", [])
    for ev in events:
        if ev.get("id"):
            ev["id"] = str(ev["id"])
        if ev.get("camera_id"):
            ev["camera_id"] = str(ev["camera_id"])
        if ev.get("station_id"):
            ev["station_id"] = str(ev["station_id"])
        if ev.get("timestamp"):
            ev["timestamp"] = str(ev["timestamp"])

    if request.args.get('format') == 'list':
        return jsonify(events)

    return jsonify(res)


@app.route('/api/station/<camera_id>/products')
def get_station_products(camera_id):
    try:
        config = ConfigLoader.load_config()
        products_cfg = config.get("products", [])

        # Direct machine mapping as fallback
        static_machine_map = {
            "machine_06": ["TNA2269"],
            "machine_07": ["TFF4040", "626287"],
            "machine_08": ["laprap"]
        }

        # If camera_id is "all", empty, or undefined -> return all products
        if not camera_id or camera_id in ["all", "undefined", "null"]:
            return jsonify([{"id": p.get("id"), "name": p.get("name")} for p in products_cfg])

        camera = next((c for c in config.get("cameras", []) if c.get("id") == camera_id), None)
        allowed_ids = None

        if camera and "allowed_products" in camera:
            allowed_ids = set(camera.get("allowed_products", []))
        elif camera_id in static_machine_map:
            allowed_ids = set(static_machine_map[camera_id])

        if allowed_ids:
            res = [p for p in products_cfg if p.get("id") in allowed_ids]
            return jsonify([{"id": p.get("id"), "name": p.get("name")} for p in res])

        # Fallback to all products if machine is unknown
        return jsonify([{"id": p.get("id"), "name": p.get("name")} for p in products_cfg])
    except Exception as e:
        logger.error(f"Error in get_station_products: {e}")
        return jsonify([])


@app.route('/api/stats/summary')
def get_stat_summary():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    start_hour = request.args.get('start_hour', type=int)
    end_hour = request.args.get('end_hour', type=int)
    summary = EventQueries.get_daily_summary(target_date, camera_id=camera_id, product_id=product_id, start_hour=start_hour, end_hour=end_hour)
    return jsonify(summary)


@app.route('/api/stats/trend')
def get_stat_trend():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    start_hour = request.args.get('start_hour', type=int)
    end_hour = request.args.get('end_hour', type=int)
    trend = EventQueries.get_weekly_trend(target_date, camera_id=camera_id, product_id=product_id, start_hour=start_hour, end_hour=end_hour)
    return jsonify(trend)


@app.route('/api/stats/distribution')
def get_stat_distribution():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    start_hour = request.args.get('start_hour', type=int)
    end_hour = request.args.get('end_hour', type=int)
    dist = EventQueries.get_daily_distribution(target_date, camera_id=camera_id, product_id=product_id, start_hour=start_hour, end_hour=end_hour)
    return jsonify(dist)


@app.route('/api/stats/hourly')
def get_stat_hourly():
    target_date = request.args.get('date', time.strftime('%Y-%m-%d'))
    camera_id = request.args.get('camera_id')
    product_id = request.args.get('product_id')
    start_hour = request.args.get('start_hour', type=int)
    end_hour = request.args.get('end_hour', type=int)
    hourly = EventQueries.get_hourly_stats(target_date, camera_id=camera_id, product_id=product_id, start_hour=start_hour, end_hour=end_hour)
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
