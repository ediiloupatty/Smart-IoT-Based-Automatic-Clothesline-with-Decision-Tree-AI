"""
NodeMCU interface utilities for PY-PY Application
Handles communication with NodeMCU ESP8266 controller
"""

import requests
import time
import sys
import os
import socket

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
            return response.json()
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
    try:
        # First get current status
        print("Fetching current NodeMCU status...")
        current_data = get_nodemcu_data()
        print(f"Current NodeMCU data: {current_data}")
        
        # Always send the command regardless of current status
        print(f"Sending {action} command to NodeMCU...")
        
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
        response = requests.get(
            f"{config.NODEMCU_CONFIG['base_url']}/api/status", 
            timeout=config.NODEMCU_CONFIG['timeout']
        )
        if response.status_code == 200:
            return {"status": "connected", "message": "NodeMCU is connected"}
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
    try:
        # Get latest sensor data
        row = get_latest_data()
        
        if not row:
            return
            
        ldr = row['ldr']
        rain = row['rain']
        status = row['status']
        
        # Don't send commands if the system is currently moving (in transition)
        if status not in ["TERTUTUP", "TERBUKA"]:
            print("Auto mode: System is currently moving, waiting for it to finish")
            return
            
        # Add hysteresis to prevent oscillation
        LIGHT_HYSTERESIS = 50  # Buffer for light threshold
        RAIN_HYSTERESIS = 50   # Buffer for rain threshold
        
        # Define conditions with hysteresis to prevent rapid switching
        is_raining = rain > (config.AUTO_SETTINGS['rainThreshold'])
        is_dark = ldr < (config.AUTO_SETTINGS['lightThreshold'] - LIGHT_HYSTERESIS)
        is_bright = ldr > (config.AUTO_SETTINGS['lightThreshold'] + LIGHT_HYSTERESIS)
        is_dry = rain < (config.AUTO_SETTINGS['rainThreshold'] - RAIN_HYSTERESIS)
        
        # Get the timestamp to prevent rapid commands
        current_time = time.time()
        
        # Only proceed if it's been at least the cooldown period since the last command
        if current_time - config.last_auto_command_time < config.APP_CONFIG['command_cooldown']:
            return
            
        # Check conditions and send commands with improved logic
        if (is_raining or is_dark) and status == "TERBUKA":
            # Rain detected or low light, close the clothes line
            send_command_to_nodemcu('close')
            config.last_auto_command_time = current_time
            print("Auto mode: Bad conditions detected - sending close command")
            
        elif is_bright and is_dry and status == "TERTUTUP":
            # Good conditions (sunny, no rain), open the clothes line
            send_command_to_nodemcu('open')
            config.last_auto_command_time = current_time
            print("Auto mode: Good conditions - sending open command")
            
    except Exception as e:
        print(f"Error in auto mode: {e}")