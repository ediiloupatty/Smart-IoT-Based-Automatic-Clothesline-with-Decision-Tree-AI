"""
NodeMCU interface utilities for PY-PY Application
Handles communication with NodeMCU ESP8266 controller
"""

import requests
import time
import sys
import os
import socket
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.database import get_latest_data

def get_nodemcu_data():
    """Get sensor data from NodeMCU via API with improved error handling"""
    try:
        # Check if base URL is actually available
        if not config.NODEMCU_CONFIG['base_url'] or config.NODEMCU_CONFIG['base_url'] == 'http://localhost/':
            print("NodeMCU URL not configured or set to localhost.")
            return None
        
        # Add proper error handling for timeouts and connection errors
        response = requests.get(
            f"{config.NODEMCU_CONFIG['base_url']}/api/data", 
            timeout=config.NODEMCU_CONFIG['timeout']
        )
        if response.status_code == 200:
            data = response.json()
            # Log data for debugging
            print(f"Data received from NodeMCU: {json.dumps(data, indent=2)}")
            
            # Ensure data formatting matches what the NodeMCU sends
            # Based on the NodeMCU code, we expect these fields
            expected_fields = ["ldr", "rain", "status", "weather", "rotation", "connected", "device_id", "timestamp"]
            
            # Check if all expected fields are present
            if not all(field in data for field in expected_fields):
                print(f"Warning: Some expected fields missing from NodeMCU data. Received: {list(data.keys())}")
            
            return data
        else:
            print(f"Error getting data from NodeMCU: HTTP {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("Connection timed out while connecting to NodeMCU")
        return None
    except (requests.exceptions.ConnectionError, socket.gaierror):
        print(f"Cannot connect to NodeMCU at {config.NODEMCU_CONFIG['base_url']}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Connection error with NodeMCU: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error communicating with NodeMCU: {e}")
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
        # First get current status
        print("Fetching current NodeMCU status...")
        current_data = get_nodemcu_data()
        print(f"Current NodeMCU data: {current_data}")
        
        if current_data is None:
            print("Warning: Unable to get current NodeMCU status, but will still try to send command")
        else:
            # Check if the Arduino is connected to the NodeMCU
            if not current_data.get("connected", False):
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
        
        # Construct the URL
        url = f"{config.NODEMCU_CONFIG['base_url']}/api/control"
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

            # Update the database with the command sent
            # You may need to import additional functions or modify your database utility
            # to handle this functionality
            try:
                # Example of how you might log the command to your database
                # log_command_to_database(action, result.get("success", False))
                pass
            except Exception as db_error:
                print(f"Warning: Could not log command to database: {db_error}")
                
            return result
        else:
            error_msg = f"Error sending command to NodeMCU: HTTP {response.status_code}"
            print(f"ERROR: {error_msg}")
            return {"success": False, "message": error_msg}
            
    except requests.exceptions.Timeout:
        error_msg = "Connection timed out while connecting to NodeMCU"
        print(f"ERROR: {error_msg}")
        return {"success": False, "message": error_msg}
    except (requests.exceptions.ConnectionError, socket.gaierror):
        error_msg = f"Cannot connect to NodeMCU at {config.NODEMCU_CONFIG['base_url']}"
        print(f"ERROR: {error_msg}")
        return {"success": False, "message": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error with NodeMCU: {e}"
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
        # First check if the URL is properly configured
        if not config.NODEMCU_CONFIG['base_url'] or config.NODEMCU_CONFIG['base_url'] == 'http://localhost/':
            return {"status": "error", "message": "NodeMCU URL not configured or set to localhost"}, 500
            
        response = requests.get(
            f"{config.NODEMCU_CONFIG['base_url']}/api/status", 
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
            return {"status": "error", "message": f"NodeMCU returned HTTP {response.status_code}"}, 500
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Connection timed out while connecting to NodeMCU"}, 500
    except (requests.exceptions.ConnectionError, socket.gaierror):
        return {"status": "error", "message": f"Cannot connect to NodeMCU at {config.NODEMCU_CONFIG['base_url']}"}, 500
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Cannot connect to NodeMCU: {str(e)}"}, 500
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
            
        # Try to get data from NodeMCU first (real-time)
        nodemcu_data = get_nodemcu_data()
        
        if nodemcu_data and nodemcu_data.get('connected', False):
            print("Using real-time data from NodeMCU")
            ldr = nodemcu_data.get('ldr', 0)
            rain = nodemcu_data.get('rain', 0)
            status = nodemcu_data.get('status', '').upper()
        else:
            # Fall back to database data if NodeMCU is not available
            print("NodeMCU not available, using database data")
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

def sync_data_with_server():
    """
    Sync local data with cloud server (render.com)
    This function should be called periodically to ensure data on the server is up-to-date
    """
    try:
        # Get the latest data from NodeMCU
        data = get_nodemcu_data()
        
        if not data:
            print("No data available from NodeMCU to sync with server")
            return {"success": False, "message": "No data available from NodeMCU"}
            
        # Here you would implement the code to send the data to your render.com server
        # Example:
        # server_url = "https://iot-clothesline-system.onrender.com/api/data/update"
        # response = requests.post(server_url, json=data, timeout=10)
        # return {"success": response.status_code == 200, "message": "Data synced with server"}
        
        # For now, just return success
        return {"success": True, "message": "Data sync functionality not implemented yet"}
        
    except Exception as e:
        print(f"Error syncing data with server: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}