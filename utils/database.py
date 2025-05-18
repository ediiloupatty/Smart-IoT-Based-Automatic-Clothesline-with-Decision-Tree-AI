"""
Database utility functions for PY-PY Application
"""

import sqlite3
from datetime import datetime
import sys
import os
import time

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def save_sensor_data(ldr, rain, status, rotation):
    """Save sensor data to database with retry mechanism"""
    max_retries = 5
    retry_delay = 0.1  # 100ms initial delay
    
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(config.DATABASE, timeout=10)  # Tambah timeout
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            conn.execute(
                'INSERT INTO sensor_data (timestamp, ldr, rain, status, rotation) VALUES (?, ?, ?, ?, ?)',
                (timestamp, int(ldr), int(rain), status, int(rotation))
            )
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                print(f"Error saving sensor data: {e}")
                return False
        except Exception as e:
            print(f"Error saving sensor data: {e}")
            return False
        finally:
            if conn:
                conn.close()
    return False

def get_latest_data():
    """Get the latest sensor data from database"""
    conn = None
    try:
        conn = sqlite3.connect(config.DATABASE, timeout=10)
        cursor = conn.execute('SELECT timestamp, ldr, rain, status, rotation FROM sensor_data ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        
        if row:
            return {
                'timestamp': row[0],
                'ldr': row[1],
                'rain': row[2],
                'status': row[3],
                'rotation': row[4]
            }
        return None
    except Exception as e:
        print(f"Error fetching latest data: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_data_count():
    """Get the count of sensor data records"""
    try:
        conn = sqlite3.connect(config.DATABASE)
        cursor = conn.execute('SELECT COUNT(*) FROM sensor_data')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Error getting data count: {e}")
        return 0

def get_recent_sensor_data(limit):
    """Get recent sensor data for predictions"""
    try:
        conn = sqlite3.connect(config.DATABASE)
        cursor = conn.execute(f'SELECT ldr, rain FROM sensor_data ORDER BY timestamp DESC LIMIT {limit}')
        recent_data = cursor.fetchall()
        conn.close()
        return list(reversed(recent_data))  # Return in oldest-first order
    except Exception as e:
        print(f"Error getting recent data: {e}")
        return []

def get_all_sensor_data():
    """Get all sensor data for training"""
    try:
        conn = sqlite3.connect(config.DATABASE)
        cursor = conn.execute('SELECT ldr, rain FROM sensor_data ORDER BY timestamp')
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        print(f"Error fetching all sensor data: {e}")
        return []

def get_all_data_records():
    """Get all data records for display"""
    try:
        conn = sqlite3.connect(config.DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sensor_data ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching all records: {e}")
        return []