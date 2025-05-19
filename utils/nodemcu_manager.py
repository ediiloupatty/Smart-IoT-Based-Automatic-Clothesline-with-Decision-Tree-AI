"""
NodeMCU interface utilities for Smart Clothesline System Application
Handles communication with NodeMCU ESP8266 controller via HTTP polling
Supports both local and Render.com cloud endpoints
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

# Fungsi utilitas untuk memilih endpoint yang tepat
def get_api_endpoint(path=""):
    """
    Determines the appropriate API endpoint based on whether we're running locally or on Render
    
    Args:
        path (str): The API path to append to the base URL
    
    Returns:
        str: The complete API URL
    """
    # Cek apakah kita perlu menggunakan endpoint Render
    use_render = config.NODEMCU_CONFIG.get('use_render', False)
    
    # Jika use_render True atau tidak ada koneksi ke NodeMCU lokal (base_url adalah localhost), gunakan Render
    if use_render or not config.NODEMCU_CONFIG['base_url'] or config.NODEMCU_CONFIG['base_url'] == 'http://localhost/':
        # Gunakan endpoint Render
        render_url = config.NODEMCU_CONFIG.get('render_url', 'https://iot-clothesline-system.onrender.com')
        endpoint = f"{render_url}/api/{path}" if path else f"{render_url}/api/data"
        print(f"Using Render endpoint: {endpoint}")
        return endpoint
    else:
        # Gunakan endpoint lokal
        endpoint = f"{config.NODEMCU_CONFIG['base_url']}/api/{path}" if path else f"{config.NODEMCU_CONFIG['base_url']}/api/data"
        print(f"Using local endpoint: {endpoint}")
        return endpoint

def get_nodemcu_data(force_refresh=False):
    """
    Get sensor data from NodeMCU via API with improved error handling
    Supports both local NodeMCU and Render cloud endpoints
    
    Args:
        force_refresh (bool): If True, forces a new request instead of using cached data
    """
    global latest_polled_data
    
    # If we have cached data and not forcing refresh, return it
    if not force_refresh and latest_polled_data is not None:
        # Check if the cached data is recent (less than 2 polling intervals old)
        if 'timestamp' in latest_polled_data:
            try:
                data_time = datetime.strptime(latest_polled_data['timestamp'], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                data_age_seconds = (now - data_time).total_seconds()
                
                # If data is recent enough, use it
                if data_age_seconds < (config.Config.POLLING_INTERVAL * 2):
                    return latest_polled_data
            except:
                # If there's an error parsing the timestamp, just continue to fetch fresh data
                pass
    
    try:
        # Get the appropriate endpoint URL (either local or Render)
        endpoint_url = get_api_endpoint()
        
        start_time = time.time()
        
        # Implement retry logic
        max_retries = config.APP_CONFIG.get('max_retries', 3)
        retry_delay = config.APP_CONFIG.get('retry_delay', 2)
        
        for retry in range(max_retries):
            try:
                # Add proper error handling for timeouts and connection errors
                response = requests.get(
                    endpoint_url, 
                    timeout=config.NODEMCU_CONFIG['timeout']
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Ensure data has a timestamp
                    if 'timestamp' not in data:
                        data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Log data for debugging
                    print(f"Data received from endpoint: {json.dumps(data, indent=2)}")
                    print(f"Response time: {response_time:.2f}s")
                    
                    # Log successful polling to the database
                    config.log_polling_event(True, response_time)
                    
                    # Store the data in our global cache
                    with polling_lock:
                        latest_polled_data = data
                    
                    # Simpan data ke database dengan parameter yang benar
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
                    print(f"Error getting data from endpoint: HTTP {response.status_code}")
                    if retry < max_retries - 1:  # Don't sleep on the last retry
                        time.sleep(retry_delay)
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, socket.gaierror):
                if retry < max_retries - 1:  # Don't sleep on the last retry
                    print(f"Connection error on try {retry+1}/{max_retries}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print("All retries failed.")
        
        # If we've exhausted our retries, log the failure
        error_msg = f"Failed to get data after {max_retries} retries"
        config.log_polling_event(False, time.time() - start_time, error_msg)
        return None
                    
    except Exception as e:
        response_time = time.time() - start_time
        error_msg = f"Unexpected error communicating with endpoint: {e}"
        print(error_msg)
        config.log_polling_event(False, response_time, error_msg)
        return None

def send_command_to_nodemcu(action):
    """Send command to NodeMCU with detailed logging and improved error handling"""
    print(f"\n----- SENDING COMMAND: {action} -----")
    
    # Validate action parameter
    if action not in ["open", "close"]:
        error_msg = f"Invalid action parameter: {action}. Must be 'open' or 'close'"
        print(f"ERROR: {error_msg}")
        return {"success": False, "message": error_msg}
    
    try:
        # First get current status - force refresh to ensure we have current data
        print("Fetching current NodeMCU status...")
        current_data = get_nodemcu_data(force_refresh=True)
        print(f"Current NodeMCU data: {current_data}")
        
        if current_data is None:
            print("Warning: Unable to get current NodeMCU status, but will still try to send command")
        else:
            # Check if the Arduino is connected to the NodeMCU
            if not current_data.get("connected", False) and not config.NODEMCU_CONFIG.get('use_render', False):
                error_msg = "Arduino is not connected to NodeMCU. Cannot send command."
                print(f"ERROR: {error_msg}")
                return {"success": False, "message": error_msg}
                
            # Check current status to avoid unnecessary commands
            current_status = current_data.get("status", "").upper()
            if (action == "open" and current_status == "TERBUKA"):
                print("Clothesline is already open, no need to send command")
                return {"success": True, "message": "Clothesline is already open"}
            elif (action == "close" and current_status == "TERTUTUP"):
                print("Clothesline is already closed, no need to send command")
                return {"success": True, "message": "Clothesline is already closed"}
        
        # Get the appropriate control endpoint URL
        control_endpoint = get_api_endpoint("control")
        
        # Implement retry logic
        max_retries = config.APP_CONFIG.get('max_retries', 3)
        retry_delay = config.APP_CONFIG.get('retry_delay', 2)
        
        for retry in range(max_retries):
            try:
                # Construct the URL
                url = control_endpoint
                print(f"Request URL: {url}")
                print(f"Request params: {{'action': {action}}}")
                
                # Send the command
                response = requests.post(
                    url, 
                    params={'action': action},
                    timeout=config.NODEMCU_CONFIG['timeout']
                )
                
                # Log response details
                print(f"Response status code: {response.status_code}")
                print(f"Response headers: {response.headers}")
                
                try:
                    result = response.json()
                    print(f"Response JSON: {result}")
                except:
                    print(f"Response text (not JSON): {response.text}")
                    result = {"success": False, "message": f"Invalid response: {response.text}"}
                
                if response.status_code == 200:
                    print(f"Command sent successfully!")
                    
                    # Force refresh data after command to get the new state
                    time.sleep(1)  # Allow a moment for the state to change
                    get_nodemcu_data(force_refresh=True)
                    
                    return result
                else:
                    print(f"Error on try {retry+1}/{max_retries}: HTTP {response.status_code}")
                    if retry < max_retries - 1:  # Don't sleep on the last retry
                        time.sleep(retry_delay)
                        
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if retry < max_retries - 1:  # Don't sleep on the last retry
                    print(f"Connection error on try {retry+1}/{max_retries}: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    error_msg = f"All retries failed: {e}"
                    print(f"ERROR: {error_msg}")
                    return {"success": False, "message": error_msg}
        
        # If we get here, all retries failed
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
    """Check if NodeMCU is available and reachable with improved error handling"""
    try:
        # Get the appropriate status endpoint URL
        status_endpoint = get_api_endpoint("status")
        
        # If we're using Render, return a special status
        if config.NODEMCU_CONFIG.get('use_render', False):
            print("Using Render cloud mode - assuming NodeMCU connection is available")
            return {"status": "partial", "message": "Running in cloud mode via Render"}, 200
        
        # Implement retry logic
        max_retries = config.APP_CONFIG.get('max_retries', 3)
        retry_delay = config.APP_CONFIG.get('retry_delay', 2)
        
        for retry in range(max_retries):
            try:
                response = requests.get(
                    status_endpoint, 
                    timeout=config.NODEMCU_CONFIG['timeout']
                )
                
                if response.status_code == 200:
                    # Try to parse the response to check if Arduino is connected
                    try:
                        data = response.json()
                        arduino_connected = data.get("connected", False)
                        
                        if arduino_connected:
                            return {"status": "connected", "message": "NodeMCU is connected and Arduino is responding"}, 200
                        else:
                            return {"status": "partial", "message": "NodeMCU is connected but Arduino is not responding"}, 200
                    except:
                        # If can't parse JSON, just check if there's HTML response (status page)
                        if "<html" in response.text.lower():
                            return {"status": "connected", "message": "NodeMCU status page is accessible"}, 200
                        else:
                            return {"status": "error", "message": "NodeMCU response format is invalid"}, 500
                else:
                    if retry < max_retries - 1:  # Don't sleep on the last retry
                        print(f"Connection error on try {retry+1}/{max_retries}: HTTP {response.status_code}, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                    else:
                        return {"status": "error", "message": f"NodeMCU returned HTTP {response.status_code}"}, 500
                        
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if retry < max_retries - 1:  # Don't sleep on the last retry
                    print(f"Connection error on try {retry+1}/{max_retries}: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    return {"status": "error", "message": f"Cannot connect to NodeMCU: {str(e)}"}, 500
        
        # If we've exhausted our retries
        return {"status": "error", "message": f"Failed to connect after {max_retries} retries"}, 500
        
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}, 500

def check_auto_conditions():
    """Check sensor conditions and automatically control the clothesline"""
    print("\n----- AUTO MODE CHECK -----")
    try:
        # First check if auto mode is enabled
        if not config.AUTO_SETTINGS.get('enabled', False):
            print("Auto mode is disabled")
            return
            
        print("Auto mode is enabled, checking conditions...")
            
        # Try to get data from endpoint first (real-time)
        endpoint_data = get_nodemcu_data()
        
        if endpoint_data:
            print("Using real-time data from endpoint")
            ldr = endpoint_data.get('ldr', 0)
            rain = endpoint_data.get('rain', 0)
            status = endpoint_data.get('status', '').upper()
        else:
            # Fall back to database data if endpoint is not available
            print("Endpoint not available, using database data")
            row = get_latest_data()
            
            if not row:
                print("No data available in database, skipping auto check")
                return
                
            ldr = row.get('ldr', 0)
            rain = row.get('rain', 0)
            status = row.get('status', '').upper()
        
        print(f"Current values - LDR: {ldr}, Rain: {rain}, Status: {status}")
        
        # Don't send commands if the system is currently moving (in transition)
        if status not in ["TERTUTUP", "TERBUKA"]:
            print("Auto mode: System is currently moving, waiting for it to finish")
            return
            
        # Add hysteresis to prevent oscillation
        LIGHT_HYSTERESIS = 50  # Buffer for light threshold
        RAIN_HYSTERESIS = 50   # Buffer for rain threshold
        
        # Define conditions with hysteresis to prevent rapid switching
        light_threshold = config.AUTO_SETTINGS.get('lightThreshold', 500)
        rain_threshold = config.AUTO_SETTINGS.get('rainThreshold', 500)
        
        print(f"Thresholds - Light: {light_threshold}, Rain: {rain_threshold}")
        
        is_raining = rain > rain_threshold
        is_dark = ldr < (light_threshold - LIGHT_HYSTERESIS)
        is_bright = ldr > (light_threshold + LIGHT_HYSTERESIS)
        is_dry = rain < (rain_threshold - RAIN_HYSTERESIS)
        
        print(f"Conditions - Raining: {is_raining}, Dark: {is_dark}, Bright: {is_bright}, Dry: {is_dry}")
        
        # Get the timestamp to prevent rapid commands
        current_time = time.time()
        
        # Only proceed if it's been at least the cooldown period since the last command
        if hasattr(config, 'last_auto_command_time') and current_time - config.last_auto_command_time < config.APP_CONFIG.get('command_cooldown', 300):
            remaining = config.last_auto_command_time + config.APP_CONFIG.get('command_cooldown', 300) - current_time
            print(f"Cooldown period active, {remaining:.1f} seconds remaining")
            return
            
        # Check conditions and send commands with improved logic
        if (is_raining or is_dark) and status == "TERBUKA":
            # Rain detected or low light, close the clothes line
            print("Auto mode: Bad conditions detected - sending close command")
            result = send_command_to_nodemcu('close')
            if result.get('success', False):
                config.last_auto_command_time = current_time
                print(f"Auto close command sent at {datetime.now().strftime('%H:%M:%S')}")
            
        elif is_bright and is_dry and status == "TERTUTUP":
            # Good conditions (sunny, no rain), open the clothes line
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
    
    # Create and start a new polling thread
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
            # Record the current time
            start_time = time.time()
            
            # Get data from endpoint
            get_nodemcu_data(force_refresh=True)
            
            # Check auto conditions if enabled
            if config.AUTO_SETTINGS.get('enabled', False):
                check_auto_conditions()
            
            # Calculate how long to sleep
            elapsed = time.time() - start_time
            sleep_time = max(0.1, config.Config.POLLING_INTERVAL - elapsed)
            
            # Sleep for the remaining time
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error in polling worker: {e}")
            time.sleep(config.Config.POLLING_INTERVAL)  # Sleep on error to avoid fast loops

def sync_data_with_server():
    """
    Sync local data with cloud server (render.com)
    This function should be called periodically to ensure data on the server is up-to-date
    """
    try:
        # Get the latest data from endpoint
        data = get_nodemcu_data()
        
        if not data:
            print("No data available from endpoint to sync with server")
            return {"success": False, "message": "No data available from endpoint"}
        
        # If we're already using Render, no need to sync
        if config.NODEMCU_CONFIG.get('use_render', False):
            return {"success": True, "message": "Already using Render cloud endpoint, no sync needed"}
            
        # Here you would implement the code to send the data to your render.com server
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