import os
import logging
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask
app = Flask(__name__, 
            template_folder='templates', 
            static_folder='static')

# CORS setup for cross-port resource sharing
CORS(app, resources={r"/static/*": {"origins": "*"}, r"/api/*": {"origins": "*"}})

app.config['SECRET_KEY'] = os.getenv("APP_SECRET_KEY", "default_secret")
app.config['HUB_URL'] = os.getenv("HUB_URL", "")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Import routes
from app import routes
