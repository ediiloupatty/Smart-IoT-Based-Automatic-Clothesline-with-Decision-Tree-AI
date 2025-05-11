"""
Main Flask application for Machine Learning Automated Clothesline System
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
import os

# Import configuration and utilities
import config
from utils.database import get_latest_data, get_data_count, get_all_data_records, get_recent_sensor_data
from utils.nodemcu_manager import get_nodemcu_data, send_command_to_nodemcu, check_auto_conditions
from models.weather_predictor import WeatherPredictor, start_auto_training
from flask_socketio import SocketIO, emit

# Create Flask application
app = Flask(__name__)
print(f"Current working directory: {os.getcwd()}")
print(f"Absolute path to app: {os.path.abspath(__file__)}")

socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize weather predictor model
weather_predictor = WeatherPredictor()

# =============================================
# BACKGROUND THREADS
# =============================================
def nodemcu_reader():
    """Background thread to read data from NodeMCU and save to database"""
    from utils.database import save_sensor_data
    
    while config.threads_running:
        try:
            # Get data from NodeMCU
            data = get_nodemcu_data()
            
            # If data was retrieved successfully
            if data:
                print(f"Data from NodeMCU: {data}")
                
                # Save data to database
                save_sensor_data(
                    data.get('ldr', 0),
                    data.get('rain', 0),
                    data.get('status', ''),
                    data.get('rotation', 0)
                )
                
                # Check auto mode and send commands if needed
                if config.AUTO_SETTINGS['enabled']:
                    check_auto_conditions()
        except Exception as e:
            print(f"NodeMCU reader error: {str(e)}")
        
        time.sleep(config.APP_CONFIG['polling_interval'])

# =============================================
# FLASK ROUTES
# =============================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/realtime-monitoring')
def realtime_monitoring():
    return render_template('realtime.html')

@app.route('/control')
def control():
    return render_template('control.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/get_data')
def get_data():
    data = get_latest_data()
    if data:
        print(f"Data from database: {data}")
        return jsonify(data)
    return jsonify({})  # Return empty JSON if no data found

@app.route('/check-data-count')
def check_data_count():
    count = get_data_count()
    return jsonify({'count': count})

@app.route('/send_command', methods=['POST'])
def send_command():
    try:
        command = request.json.get('command')
        if command in ["open", "close", "stop"]:
            result = send_command_to_nodemcu(command)
            return jsonify({'status': 'success', 'message': result.get('message', 'Command sent')})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid command'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/train-model', methods=['POST'])
def handle_train():
    try:
        # First check if we have enough data
        count = get_data_count()
        print(f"Training model with {count} data records")
        
        min_required = weather_predictor.window_size + 10
        if count < min_required:
            return jsonify({'error': f'Data tidak cukup. Dibutuhkan minimal {min_required} data, saat ini hanya ada {count}'}), 400
            
        # Continue with training
        result = weather_predictor.train()
        
        return jsonify({
            'accuracy': result['accuracy']
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in train_model: {str(e)}\n{error_details}")
        return jsonify({'error': str(e)}), 500

@app.route('/predict-weather')
def predict_weather():
    try:
        # Check if model is trained
        if not config.MODEL_INFO['trained']:
            return jsonify({
                'error': 'Model not trained yet',
                'will_rain': False,
                'probability': 0
            })
        
        # Get the recent data from database - we need window_size-1 records
        window_size = weather_predictor.window_size
        recent_data = get_recent_sensor_data(window_size-1)
        
        # Check if we have enough data
        if len(recent_data) < window_size-1:
            return jsonify({
                'error': f'Not enough recent data for prediction. Need {window_size-1} records.',
                'will_rain': False,
                'probability': 0
            })
        
        # Log the data we're using for prediction
        print(f"Using data for prediction: {recent_data}")
        
        try:
            # Get prediction
            prediction, probability = weather_predictor.predict_next_hour(recent_data)
            print(f"Prediction result: {prediction}, probability: {probability}")
            
            # Convert prediction to boolean based on threshold
            will_rain = bool(prediction == 1)  # If prediction is 1, it will rain
            
            return jsonify({
                'will_rain': will_rain,
                'probability': float(probability)
            })
        except Exception as e:
            print(f"Error during prediction: {e}")
            import traceback
            print(traceback.format_exc())
            return jsonify({
                'error': f'Prediction error: {str(e)}',
                'will_rain': False,
                'probability': 0
            })
    except Exception as e:
        print(f"General error in predict_weather: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'will_rain': False, 
            'probability': 0
        })

# =============================================
# ROUTES FOR SETTINGS PAGE
# =============================================
@app.route('/get-config')
def get_config():
    """Get current system configuration"""
    return jsonify({
        'base_url': config.NODEMCU_CONFIG['base_url'],
        'timeout': config.NODEMCU_CONFIG['timeout']
    })

@app.route('/save-config', methods=['POST'])
def save_config():
    try:
        # Get configuration from request
        conf = request.json
        print(f"Saving config: {conf}")
        
        # Update NodeMCU configuration
        config.NODEMCU_CONFIG['base_url'] = conf['base_url']
        config.NODEMCU_CONFIG['timeout'] = float(conf['timeout'])
        
        # Save settings to database
        config.save_setting('nodemcu_base_url', conf['base_url'])
        config.save_setting('nodemcu_timeout', str(conf['timeout']))
        
        return jsonify({'status': 'success', 'message': 'Configuration saved!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get-auto-settings')
def get_auto_settings():
    """Get auto mode settings"""
    return jsonify(config.AUTO_SETTINGS)

@app.route('/save-auto-settings', methods=['POST'])
def save_auto_settings():
    try:
        # Get settings from request
        settings = request.json
        print(f"Saving auto settings: {settings}")
        
        # Update auto settings
        config.AUTO_SETTINGS['enabled'] = settings['enabled']
        config.AUTO_SETTINGS['lightThreshold'] = int(settings['lightThreshold'])
        config.AUTO_SETTINGS['rainThreshold'] = int(settings['rainThreshold'])
        
        # Save settings to database
        config.save_setting('auto_enabled', str(settings['enabled']))
        config.save_setting('light_threshold', str(settings['lightThreshold']))
        config.save_setting('rain_threshold', str(settings['rainThreshold']))
        
        return jsonify({'status': 'success', 'message': 'Auto settings saved!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get-model-info')
def get_model_info():
    """Get model information"""
    return jsonify(config.MODEL_INFO)

@app.route('/check-nodemcu')
def check_nodemcu():
    """Check if NodeMCU is available"""
    from utils.nodemcu_manager import check_nodemcu_connection
    return check_nodemcu_connection()

@app.route('/view-data')
def view_data():
    """Get all sensor data records"""
    rows = get_all_data_records()
    return jsonify(rows)

# =============================================
# MAIN EXECUTION
# =============================================
if __name__ == '__main__':
    # Start background threads
    nodemcu_thread = threading.Thread(target=nodemcu_reader)
    nodemcu_thread.daemon = True
    nodemcu_thread.start()
    
    # Start the automatic model training thread
    auto_train_thread = start_auto_training(weather_predictor)
    
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    finally:
        # Ensure threads are properly signaled to stop when app exits
        config.threads_running = False
        print("Shutting down application and threads...")