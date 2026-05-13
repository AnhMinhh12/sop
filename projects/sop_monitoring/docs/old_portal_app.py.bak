from flask import Flask, render_template
import os

app = Flask(__name__, 
            template_folder='app/templates', 
            static_folder='app/static')

@app.route('/')
def portal():
    """Trang quản lý trung tâm (Hub) chạy trên cổng 4000."""
    return render_template('portal.html')

if __name__ == '__main__':
    port = 4000
    print(f"====================================================")
    print(f"  AI MONITORING HUB IS READY AT: http://0.0.0.0:{port}")
    print(f"====================================================")
    app.run(host='0.0.0.0', port=port, debug=False)
