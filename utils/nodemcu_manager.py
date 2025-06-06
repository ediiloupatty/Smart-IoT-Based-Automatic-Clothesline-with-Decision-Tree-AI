"""
NodeMCU interface utilities for Smart Clothesline System Application
Handles communication with NodeMCU ESP8266 controller via HTTP polling
Supports both local and Render.com cloud endpoints - FIXED FOR RENDER DEPLOYMENT
"""

import requests
import time
import sys
import os
import socket
import json
import threading
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.database import get_latest_data, save_sensor_data

# Global variable to store the latest data from polling
latest_polled_data = None
polling_thread = None
polling_lock = threading.Lock()

def is_render_environment():
    """Check if we're running in Render environment"""
    return ('RENDER' in os.environ or 
            'onrender.com' in os.environ.get('RENDER_EXTERNAL_URL', '') or
            'onrender.com' in os.environ.get('SERVER_NAME', ''))

def get_api_endpoint(path=""):
    """
    Determines the appropriate API endpoint based on environment
    FOR RENDER: Always use the actual NodeMCU IP, not Render URL
    """
    # If we're in Render environment, we need to connect to the actual NodeMCU device
    if is_render_environment():
        # In Render, we should connect to the actual NodeMCU IP address
        # NOT the Render URL itself!
        nodemcu_ip = config.NODEMCU_CONFIG.get('base_url', '')
        
        # If no NodeMCU IP configured, return None to indicate no connection
        if not nodemcu_ip or 'onrender.com' in nodemcu_ip:
            print("WARNING: No valid NodeMCU IP configured for Render deployment")
            return None
            
        endpoint = f"{nodemcu_ip}/api/{path}" if path else f"{nodemcu_ip}/api/data"
        print(f"Using NodeMCU endpoint from Render: {endpoint}")
        return endpoint
    else:
        # Local development - use configured endpoint
        endpoint = f"{config.NODEMCU_CONFIG['base_url']}/api/{path}" if path else f"{config.NODEMCU_CONFIG['base_url']}/api/data"
        print(f"Using local endpoint: {endpoint}")
        return endpoint

def get_nodemcu_data(force_refresh=False):
    """
    Get sensor data from NodeMCU via API with improved error handling
    """
    global latest_polled_data
    
    # If we have cached data and not forcing refresh, return it
    if not force_refresh and latest_polled_data is not None:
        if 'timestamp' in latest_polled_data:
            try:
                data_time = datetime.strptime(latest_polled_data['timestamp'], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                data_age_seconds = (now - data_time).total_seconds()
                
                if data_age_seconds < (config.Config.POLLING_INTERVAL * 2):
                    return latest_polled_data
            except:
                pass
    
    try:
        endpoint_url = get_api_endpoint()
        
        # If no endpoint available (Render without NodeMCU IP), return database data
        if endpoint_url is None:
            print("No NodeMCU endpoint available, using database data")
            return get_latest_data()
        
        start_time = time.time()
        max_retries = config.APP_CONFIG.get('max_retries', 3)
        retry_delay = config.APP_CONFIG.get('retry_delay', 2)
        
        for retry in range(max_retries):
            try:
                response = requests.get(
                    endpoint_url, 
                    timeout=config.NODEMCU_CONFIG['timeout']
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'timestamp' not in data:
                        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f"Data received from NodeMCU: {json.dumps(data, indent=2)}")
                    print(f"Response time: {response_time:.2f}s")
                    
                    config.log_polling_event(True, response_time)
                    
                    with polling_lock:
                        latest_polled_data = data
                    
                    try:
                        save_sensor_data(
                            data.get('ldr', 0),
                            data.get('rain', 0),
                            data.get('status', 'UNKNOWN'),
                            data.get('rotation', 0)
                        )
                    except Exception as db_error:
                        print(f"Error saving sensor data to database: {db_error}")
                    
                    return data
                else:
                    print(f"Error getting data from NodeMCU: HTTP {response.status_code}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, socket.gaierror):
                if retry < max_retries - 1:
                    print(f"Connection error on try {retry+1}/{max_retries}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print("All retries failed.")
        
        error_msg = f"Failed to get data after {max_retries} retries"
        config.log_polling_event(False, time.time() - start_time, error_msg)
        return None
                    
    except Exception as e:
        response_time = time.time() - start_time
        error_msg = f"Unexpected error communicating with NodeMCU: {e}"
        print(error_msg)
        config.log_polling_event(False, response_time, error_msg)
        return None

def send_command_to_nodemcu(action):
    """Send command to NodeMCU - FIXED FOR RENDER DEPLOYMENT"""
    print(f"\n----- SENDING COMMAND: {action} -----")
    
    # Validate action parameter
    if action not in ["open", "close"]:
        error_msg = f"Invalid action parameter: {action}. Must be 'open' or 'close'"
        print(f"ERROR: {error_msg}")
        return {"success": False, "message": error_msg}
    
    try:
        # Special handling for Render environment
        if is_render_environment():
            print("Detected Render environment - checking NodeMCU configuration")
            
            # Check if we have a valid NodeMCU IP configured
            nodemcu_ip = config.NODEMCU_CONFIG.get('base_url', '')
            if not nodemcu_ip or 'onrender.com' in nodemcu_ip:
                error_msg = "NodeMCU IP address not configured for Render deployment"
                print(f"ERROR: {error_msg}")
                return {"success": False, "message": error_msg}
        
        # Get current status first (with reduced timeout for Render)
        print("Fetching current NodeMCU status...")
        current_data = get_nodemcu_data(force_refresh=True)
        print(f"Current NodeMCU data: {current_data}")
        
        if current_data is None:
            print("Warning: Unable to get current NodeMCU status, but will still try to send command")
        else:
            # Check current status to avoid unnecessary commands
            current_status = current_data.get("status", "").upper()
            if (action == "open" and current_status == "TERBUKA"):
                print("Clothesline is already open, no need to send command")
                return {"success": True, "message": "Clothesline is already open"}
            elif (action == "close" and current_status == "TERTUTUP"):
                print("Clothesline is already closed, no need to send command")
                return {"success": True, "message": "Clothesline is already closed"}
        
        # Get the control endpoint
        control_endpoint = get_api_endpoint("control")
        
        if control_endpoint is None:
            error_msg = "No NodeMCU control endpoint available"
            print(f"ERROR: {error_msg}")
            return {"success": False, "message": error_msg}
        
        # Reduced retries and timeout for Render to prevent worker timeout
        max_retries = 2 if is_render_environment() else config.APP_CONFIG.get('max_retries', 3)
        retry_delay = 1 if is_render_environment() else config.APP_CONFIG.get('retry_delay', 2)
        timeout = 5 if is_render_environment() else config.NODEMCU_CONFIG['timeout']
        
        for retry in range(max_retries):
            try:
                print(f"Sending command to: {control_endpoint}")
                print(f"Action: {action}, Timeout: {timeout}s")
                
                response = requests.post(
                    control_endpoint, 
                    params={'action': action},
                    timeout=timeout
                )
                
                print(f"Response status code: {response.status_code}")
                
                try:
                    result = response.json()
                    print(f"Response JSON: {result}")
                except:
                    print(f"Response text (not JSON): {response.text}")
                    result = {"success": True, "message": f"Command sent (status {response.status_code})"}
                
                if response.status_code == 200:
                    print(f"Command sent successfully!")
                    
                    # Don't wait too long in Render environment
                    if not is_render_environment():
                        time.sleep(1)
                        get_nodemcu_data(force_refresh=True)
                    
                    return result
                else:
                    print(f"Error on try {retry+1}/{max_retries}: HTTP {response.status_code}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                        
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if retry < max_retries - 1:
                    print(f"Connection error on try {retry+1}/{max_retries}: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    error_msg = f"All retries failed: {e}"
                    print(f"ERROR: {error_msg}")
                    return {"success": False, "message": error_msg}
        
        error_msg = f"Command failed after {max_retries} attempts"
        print(f"ERROR: {error_msg}")
        return {"success": False, "message": error_msg}
            
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"ERROR: {error_msg}")
        import traceback
        print(traceback.format_exc())
        return {"success": False, "message": error_msg}
    finally:
        print("----- COMMAND PROCESSING COMPLETE -----\n")

def check_nodemcu_connection():
    """Check if NodeMCU is available and reachable"""
    try:
        # Special handling for Render
        if is_render_environment():
            nodemcu_ip = config.NODEMCU_CONFIG.get('base_url', '')
            if not nodemcu_ip or 'onrender.com' in nodemcu_ip:
                return {"status": "partial", "message": "NodeMCU IP not configured for Render deployment"}, 200
            
            print(f"Checking NodeMCU connection in Render environment: {nodemcu_ip}")
        
        status_endpoint = get_api_endpoint("status")
        
        if status_endpoint is None:
            return {"status": "error", "message": "No NodeMCU endpoint configured"}, 500
        
        max_retries = 2 if is_render_environment() else config.APP_CONFIG.get('max_retries', 3)
        retry_delay = 1 if is_render_environment() else config.APP_CONFIG.get('retry_delay', 2)
        timeout = 5 if is_render_environment() else config.NODEMCU_CONFIG['timeout']
        
        for retry in range(max_retries):
            try:
                response = requests.get(status_endpoint, timeout=timeout)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        arduino_connected = data.get("connected", False)
                        
                        if arduino_connected:
                            return {"status": "connected", "message": "NodeMCU is connected and Arduino is responding"}, 200
                        else:
                            return {"status": "partial", "message": "NodeMCU is connected but Arduino is not responding"}, 200
                    except:
                        if "<html" in response.text.lower():
                            return {"status": "connected", "message": "NodeMCU status page is accessible"}, 200
                        else:
                            return {"status": "error", "message": "NodeMCU response format is invalid"}, 500
                else:
                    if retry < max_retries - 1:
                        print(f"Connection error on try {retry+1}/{max_retries}: HTTP {response.status_code}, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                    else:
                        return {"status": "error", "message": f"NodeMCU returned HTTP {response.status_code}"}, 500
                        
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if retry < max_retries - 1:
                    print(f"Connection error on try {retry+1}/{max_retries}: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    return {"status": "error", "message": f"Cannot connect to NodeMCU: {str(e)}"}, 500
        
        return {"status": "error", "message": f"Failed to connect after {max_retries} retries"}, 500
        
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}, 500

def check_auto_conditions():
    """Check sensor conditions and automatically control the clothesline"""
    print("\n----- AUTO MODE CHECK -----")
    try:
        if not config.AUTO_SETTINGS.get('enabled', False):
            print("Auto mode is disabled")
            return
            
        print("Auto mode is enabled, checking conditions...")
            
        endpoint_data = get_nodemcu_data()
        
        if endpoint_data:
            print("Using real-time data from endpoint")
            ldr = endpoint_data.get('ldr', 0)
            rain = endpoint_data.get('rain', 0)
            status = endpoint_data.get('status', '').upper()
        else:
            print("Endpoint not available, using database data")
            row = get_latest_data()
            
            if not row:
                print("No data available in database, skipping auto check")
                return
                
            ldr = row.get('ldr', 0)
            rain = row.get('rain', 0)
            status = row.get('status', '').upper()
        
        print(f"Current values - LDR: {ldr}, Rain: {rain}, Status: {status}")
        
        if status not in ["TERTUTUP", "TERBUKA"]:
            print("Auto mode: System is currently moving, waiting for it to finish")
            return
            
        LIGHT_HYSTERESIS = 50
        RAIN_HYSTERESIS = 50
        
        light_threshold = config.AUTO_SETTINGS.get('lightThreshold', 500)
        rain_threshold = config.AUTO_SETTINGS.get('rainThreshold', 500)
        
        print(f"Thresholds - Light: {light_threshold}, Rain: {rain_threshold}")
        
        is_raining = rain > rain_threshold
        is_dark = ldr < (light_threshold - LIGHT_HYSTERESIS)
        is_bright = ldr > (light_threshold + LIGHT_HYSTERESIS)
        is_dry = rain < (rain_threshold - RAIN_HYSTERESIS)
        
        print(f"Conditions - Raining: {is_raining}, Dark: {is_dark}, Bright: {is_bright}, Dry: {is_dry}")
        
        current_time = time.time()
        
        if hasattr(config, 'last_auto_command_time') and current_time - config.last_auto_command_time < config.APP_CONFIG.get('command_cooldown', 300):
            remaining = config.last_auto_command_time + config.APP_CONFIG.get('command_cooldown', 300) - current_time
            print(f"Cooldown period active, {remaining:.1f} seconds remaining")
            return
            
        if (is_raining or is_dark) and status == "TERBUKA":
            print("Auto mode: Bad conditions detected - sending close command")
            result = send_command_to_nodemcu('close')
            if result.get('success', False):
                config.last_auto_command_time = current_time
                print(f"Auto close command sent at {datetime.now().strftime('%H:%M:%S')}")
            
        elif is_bright and is_dry and status == "TERTUTUP":
            print("Auto mode: Good conditions - sending open command")
            result = send_command_to_nodemcu('open')
            if result.get('success', False):
                config.last_auto_command_time = current_time
                print(f"Auto open command sent at {datetime.now().strftime('%H:%M:%S')}")
        else:
            print("Auto mode: No action needed based on current conditions")
            
    except Exception as e:
        print(f"Error in auto mode: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        print("----- AUTO MODE CHECK COMPLETE -----\n")

def start_polling():
    """Start a background thread for HTTP polling"""
    global polling_thread
    
    if polling_thread is not None and polling_thread.is_alive():
        print("Polling thread already running")
        return
    
    polling_thread = threading.Thread(target=polling_worker, daemon=True)
    polling_thread.start()
    print(f"HTTP polling thread started (interval: {config.Config.POLLING_INTERVAL}s)")

def stop_polling():
    """Stop the background polling thread"""
    config.threads_running = False
    
    if polling_thread is not None:
        print("Waiting for polling thread to stop...")
        polling_thread.join(timeout=5)
        print("Polling thread stopped")

def polling_worker():
    """Worker function for the polling thread"""
    print("Polling worker started")
    
    while config.threads_running:
        try:
            start_time = time.time()
            
            get_nodemcu_data(force_refresh=True)
            
            if config.AUTO_SETTINGS.get('enabled', False):
                check_auto_conditions()
            
            elapsed = time.time() - start_time
            sleep_time = max(0.1, config.Config.POLLING_INTERVAL - elapsed)
            
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error in polling worker: {e}")
            time.sleep(config.Config.POLLING_INTERVAL)

def sync_data_with_server():
    """Sync local data with cloud server"""
    try:
        data = get_nodemcu_data()
        
        if not data:
            print("No data available from endpoint to sync with server")
            return {"success": False, "message": "No data available from endpoint"}
        
        if is_render_environment():
            return {"success": True, "message": "Already in Render environment, no sync needed"}
            
        render_url = config.NODEMCU_CONFIG.get('render_url', 'https://iot-clothesline-system.onrender.com')
        server_url = f"{render_url}/api/data/update"
        
        try:
            response = requests.post(server_url, json=data, timeout=10)
            return {
                "success": response.status_code == 200, 
                "message": f"Data synced with server (status {response.status_code})"
            }
        except Exception as e:
            return {"success": False, "message": f"Error syncing with Render: {str(e)}"}
        
    except Exception as e:
        print(f"Error syncing data with server: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}

# Start polling automatically when this module is imported
if config.Config.POLLING_ENABLED:
    print("Automatic HTTP polling is enabled. Starting polling thread...")
    start_polling()