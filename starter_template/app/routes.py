from flask import render_template, jsonify, request
from app import app

@app.route('/')
def index():
    """Trang chủ của dự án mới."""
    # Trang này sẽ kế thừa từ base.html đã được sync từ Hub
    return render_template('index.html')

@app.route('/api/status')
def status():
    """API mẫu để Hub có thể lấy trạng thái."""
    return jsonify({
        "status": "online",
        "project": "New Project Template",
        "message": "Project is running and connected to Hub."
    })
