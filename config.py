"""
Configuration file for PY-PY Application
Contains all configuration parameters and settings
"""

import os
import sqlite3
import time
import platform
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file if exists
load_dotenv()

# Flask and CORS configuration
class Config:
    CORS_ALLOWED_ORIGINS = "*"
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    # SocketIO configs
    SOCKETIO_PING_TIMEOUT = 25
    SOCKETIO_PING_INTERVAL = 5
    SOCKETIO_ASYNC_MODE = "gevent"

# Check if we're running on a production environment (Render)
IS_PRODUCTION = os.environ.get('RENDER', False)

# Database configuration
if IS_PRODUCTION:
    # In production, use a directory that persists
    DATABASE = os.environ.get('DATABASE_URL', 'sqlite:///data/sensor_data.db').replace('sqlite:///', '')
else:
    DATABASE = 'data/sensor_data.db'

# Make sure the data directory exists
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

# NodeMCU Configuration
NODEMCU_CONFIG = {
    'base_url': os.environ.get('NODEMCU_BASE_URL', 'https://iot-clothesline-system.onrender.com/'),  # URL NodeMCU
    'timeout': float(os.environ.get('NODEMCU_TIMEOUT', '5'))  # Timeout dalam detik
}

# Auto mode settings
AUTO_SETTINGS = {
    'enabled': os.environ.get('AUTO_ENABLED', 'False').lower() == 'true',
    'lightThreshold': int(os.environ.get('LIGHT_THRESHOLD', '500')),
    'rainThreshold': int(os.environ.get('RAIN_THRESHOLD', '500'))
}

# Model information
MODEL_INFO = {
    'trained': False,
    'lastTraining': None,
    'accuracy': None
}

# Additional configuration
APP_CONFIG = {
    'polling_interval': int(os.environ.get('POLLING_INTERVAL', '3')),  # Seconds between NodeMCU reads
    'training_interval': int(os.environ.get('TRAINING_INTERVAL', '1800')),  # 30 minutes between auto-training
    'command_cooldown': int(os.environ.get('COMMAND_COOLDOWN', '60'))  # Seconds between auto commands
}

# Thread control variables
threads_running = True
last_auto_command_time = 0

# Database functions
def init_db():
    """Initialize database tables if they don't exist"""
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            ldr INTEGER,
            rain INTEGER,
            status TEXT,
            rotation INTEGER
        )
    ''')
    
    # Create settings table if it doesn't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            key TEXT UNIQUE,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_setting(key, value):
    """Save a setting to the database"""
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def load_setting(key, default=None):
    """Load a setting from the database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def load_all_settings():
    """Load all settings from the database"""
    global NODEMCU_CONFIG, AUTO_SETTINGS, MODEL_INFO
    
    # Load NodeMCU config
    base_url = load_setting('nodemcu_base_url', NODEMCU_CONFIG['base_url'])
    timeout = float(load_setting('nodemcu_timeout', NODEMCU_CONFIG['timeout']))
    
    NODEMCU_CONFIG['base_url'] = base_url
    NODEMCU_CONFIG['timeout'] = timeout
    
    # Load auto settings
    AUTO_SETTINGS['enabled'] = load_setting('auto_enabled', 'False') == 'True'
    AUTO_SETTINGS['lightThreshold'] = int(load_setting('light_threshold', AUTO_SETTINGS['lightThreshold']))
    AUTO_SETTINGS['rainThreshold'] = int(load_setting('rain_threshold', AUTO_SETTINGS['rainThreshold']))
    
    # Load model info
    MODEL_INFO['trained'] = load_setting('model_trained', 'False') == 'True'
    MODEL_INFO['lastTraining'] = load_setting('model_last_training')
    accuracy = load_setting('model_accuracy')
    MODEL_INFO['accuracy'] = float(accuracy) if accuracy else None

# Print system info
print(f"System: {platform.system()} {platform.release()}")
print(f"Python: {platform.python_version()}")
print(f"Database path: {os.path.abspath(DATABASE)}")
print(f"Production mode: {IS_PRODUCTION}")

# Initialize the database and load settings when this module is imported
init_db()
load_all_settings()