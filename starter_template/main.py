import os
from app import app, socketio

if __name__ == '__main__':
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 5002))
    
    print(f"=== Project Starter Template is running at http://{host}:{port} ===")
    socketio.run(app, host=host, port=port, debug=True)
