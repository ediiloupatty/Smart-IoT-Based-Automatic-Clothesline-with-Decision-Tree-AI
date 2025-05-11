"""
Configuration file for Smart Clothesline System Application
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
    # SocketIO configs - adjusted for better websocket compatibility
    SOCKETIO_PING_TIMEOUT = 30  # Increased from 25
    SOCKETIO_PING_INTERVAL = 10  # Increased from 5
    SOCKETIO_ASYNC_MODE = "gevent"  # Keep using gevent

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

# NodeMCU Configuration - Fixed to not use render URL as default
# This should be the actual IP or domain of your NodeMCU, not the web app itself
NODEMCU_CONFIG = {
    'base_url': os.environ.get('NODEMCU_BASE_URL', 'http://192.168.8.137/'),  # Default should be a local IP, not the render URL
    'timeout': float(os.environ.get('NODEMCU_TIMEOUT', '10'))  # Increased timeout for network reliability
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

# Additional configuration - adjusted for better behavior on hosted environments
APP_CONFIG = {
    'polling_interval': int(os.environ.get('POLLING_INTERVAL', '10')),  # Increased from 3 to reduce server load
    'training_interval': int(os.environ.get('TRAINING_INTERVAL', '3600')),  # Increased to 1 hour between auto-training
    'command_cooldown': int(os.environ.get('COMMAND_COOLDOWN', '60'))  # Seconds between auto commands
}

# Thread control variables
threads_running = True
last_auto_command_time = 0

# Database functions
def init_db():
    """Initialize database tables if they don't exist"""
    try:
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
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

def save_setting(key, value):
    """Save a setting to the database"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
        ''', (key, str(value)))
        conn.commit()
        conn.close()
        print(f"Setting saved: {key}={value}")
        return True
    except Exception as e:
        print(f"Error saving setting: {str(e)}")
        return False

def load_setting(key, default=None):
    """Load a setting from the database"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            print(f"Setting loaded: {key}={row[0]}")
            return row[0]
        return default
    except Exception as e:
        print(f"Error loading setting: {str(e)}")
        return default

def load_all_settings():
    """Load all settings from the database"""
    global NODEMCU_CONFIG, AUTO_SETTINGS, MODEL_INFO
    
    try:
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
        
        print("All settings loaded successfully")
    except Exception as e:
        print(f"Error loading settings: {str(e)}")

# Print system info
print(f"System: {platform.system()} {platform.release()}")
print(f"Python: {platform.python_version()}")
print(f"Database path: {os.path.abspath(DATABASE)}")
print(f"Production mode: {IS_PRODUCTION}")

# Initialize the database and load settings when this module is imported
init_db()
load_all_settings()