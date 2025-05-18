"""
Fixed Flask app for Machine Learning Automated Clothesline System
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
import os
from flask_cors import CORS

# Import configuration and utilities
import config
from utils.database import get_latest_data, get_data_count, get_all_data_records, get_recent_sensor_data
from models.weather_predictor import WeatherPredictor, start_auto_training
from utils.nodemcu_manager import get_nodemcu_data, send_command_to_nodemcu, check_auto_conditions


# Create Flask application
app = Flask(__name__)
app.config.from_object(config.Config)

# Initialize CORS with the configuration to allow all methods and headers from any origin
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], 
                            "allow_headers": ["Content-Type", "Authorization"]}})

print(f"Current working directory: {os.getcwd()}")
print(f"Absolute path to app: {os.path.abspath(__file__)}")


# Validasi dan perbaiki base_url NodeMCU jika perlu
if 'base_url' in config.NODEMCU_CONFIG:
    if config.NODEMCU_CONFIG['base_url'] and not config.NODEMCU_CONFIG['base_url'].startswith(('http://', 'https://')):
        # Tambahkan skema HTTP jika tidak ada
        config.NODEMCU_CONFIG['base_url'] = 'http://' + config.NODEMCU_CONFIG['base_url']
        print(f"URL NodeMCU diperbaiki: {config.NODEMCU_CONFIG['base_url']}")

# Initialize weather predictor model
try:
    weather_predictor = WeatherPredictor()
    print("Weather predictor initialized successfully")
except Exception as e:
    print(f"Error initializing weather predictor: {e}")
    import traceback
    print(traceback.format_exc())
    weather_predictor = WeatherPredictor()
    config.MODEL_INFO['trained'] = False

# =============================================
# BACKGROUND THREADS
# =============================================
def nodemcu_reader():
    """Background thread to read data from NodeMCU and save to database"""
    from utils.database import save_sensor_data
    
    print("Starting NodeMCU reader thread")
    
    while config.threads_running:
        try:
            # Get data from NodeMCU
            data = get_nodemcu_data()
            
            # If data was retrieved successfully
            if data and isinstance(data, dict):
                print(f"Data from NodeMCU: {data}")
                
                # Save data to database - PERBAIKAN DISINI
                # Memastikan semua parameter yang diperlukan disediakan
                save_sensor_data(
                    data.get('ldr', 0),
                    data.get('rain', 0),
                    data.get('status', 'UNKNOWN'),
                    data.get('rotation', 0)
                )
            else:
                print("No data received from NodeMCU or data format invalid")
                
            # Check auto mode and send commands if needed
            if config.AUTO_SETTINGS['enabled']:
                check_auto_conditions()
        except Exception as e:
            print(f"NodeMCU reader error: {str(e)}")
        
        # Sleep for the configured interval
        time.sleep(config.APP_CONFIG['polling_interval'])
    
    print("NodeMCU reader thread stopped")

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

# Tambahan route yang khusus menangani API yang mungkin diakses dari domain lain
@app.route('/api/data', methods=['GET', 'OPTIONS'])
def api_data():
    """
    Endpoint untuk mendapatkan data terbaru sensor dari database
    Ini adalah endpoint yang sama dengan /get_data tetapi dengan path yang lebih RESTful
    """
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    data = get_latest_data()
    if data:
        print(f"Data API dari database: {data}")
        return jsonify(data)
    return jsonify({})

@app.route('/get_data')
def get_data():
    """Endpoint lama untuk mendapatkan data terbaru"""
    data = get_latest_data()
    if data:
        print(f"Data dari database: {data}")
        return jsonify(data)
    return jsonify({})

@app.route('/check-data-count')
def check_data_count():
    count = get_data_count()
    return jsonify({'count': count})

@app.route('/send_command', methods=['POST', 'OPTIONS'])
def send_command():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    try:
        command = request.json.get('command')
        if command in ["open", "close", "stop"]:
            result = send_command_to_nodemcu(command)
            return jsonify({'status': 'success', 'message': result.get('message', 'Command sent')})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid command'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/train-model', methods=['POST', 'OPTIONS'])
def handle_train():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    try:
        count = get_data_count()
        print(f"Training model with {count} data records")
        
        min_required = weather_predictor.window_size + 10
        if count < min_required:
            return jsonify({'error': f'Insufficient data. At least {min_required} data points required, currently have {count}'}), 400
            
        try:
            result = weather_predictor.train()
            return jsonify({'accuracy': result['accuracy']})
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error during model training: {str(e)}\n{error_details}")
            return jsonify({'error': f'Training error: {str(e)}'}), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in train_model: {str(e)}\n{error_details}")
        return jsonify({'error': str(e)}), 500

@app.route('/predict-weather', methods=['GET', 'OPTIONS'])
def predict_weather():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    try:
        if not config.MODEL_INFO.get('trained', False):
            return jsonify({
                'error': 'Model not trained yet',
                'will_rain': False,
                'probability': 0
            })
        
        window_size = weather_predictor.window_size
        recent_data = get_recent_sensor_data(window_size-1)
        
        if len(recent_data) < window_size-1:
            return jsonify({
                'error': f'Not enough recent data for prediction. Need {window_size-1} records.',
                'will_rain': False,
                'probability': 0
            })
        
        print(f"Using data for prediction: {recent_data}")
        
        try:
            prediction, probability = weather_predictor.predict_next_hour(recent_data)
            print(f"Prediction result: {prediction}, probability: {probability}")
            
            will_rain = bool(prediction == 1)
            
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
@app.route('/get-config', methods=['GET', 'OPTIONS'])
def get_config():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    return jsonify({
        'base_url': config.NODEMCU_CONFIG['base_url'],
        'timeout': config.NODEMCU_CONFIG['timeout']
    })

@app.route('/save-config', methods=['POST', 'OPTIONS'])
def save_config():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    try:
        conf = request.json
        print(f"Saving config: {conf}")
        
        # Validasi dan perbaiki base_url jika perlu
        base_url = conf['base_url']
        if base_url and not base_url.startswith(('http://', 'https://')):
            base_url = 'http://' + base_url
            print(f"URL diperbaiki: {base_url}")
        
        config.NODEMCU_CONFIG['base_url'] = base_url
        config.NODEMCU_CONFIG['timeout'] = float(conf['timeout'])
        
        config.save_setting('nodemcu_base_url', base_url)
        config.save_setting('nodemcu_timeout', str(conf['timeout']))
        
        return jsonify({'status': 'success', 'message': 'Konfigurasi tersimpan!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get-auto-settings', methods=['GET', 'OPTIONS'])
def get_auto_settings():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    return jsonify(config.AUTO_SETTINGS)

@app.route('/save-auto-settings', methods=['POST', 'OPTIONS'])
def save_auto_settings():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    try:
        settings = request.json
        print(f"Saving auto settings: {settings}")
        
        config.AUTO_SETTINGS['enabled'] = settings['enabled']
        config.AUTO_SETTINGS['lightThreshold'] = int(settings['lightThreshold'])
        config.AUTO_SETTINGS['rainThreshold'] = int(settings['rainThreshold'])
        
        config.save_setting('auto_enabled', str(settings['enabled']))
        config.save_setting('light_threshold', str(settings['lightThreshold']))
        config.save_setting('rain_threshold', str(settings['rainThreshold']))
        
        return jsonify({'status': 'success', 'message': 'Pengaturan otomatis tersimpan!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get-model-info', methods=['GET', 'OPTIONS'])
def get_model_info():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    return jsonify(config.MODEL_INFO)

@app.route('/check-nodemcu', methods=['GET', 'OPTIONS'])
def check_nodemcu():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    # Validasi URL sebelum mencoba menghubungi NodeMCU
    if config.NODEMCU_CONFIG['base_url']:
        if not config.NODEMCU_CONFIG['base_url'].startswith(('http://', 'https://')):
            config.NODEMCU_CONFIG['base_url'] = 'https://' + config.NODEMCU_CONFIG['base_url']
            config.save_setting('nodemcu_base_url', config.NODEMCU_CONFIG['base_url'])
            
    # Jika deployment di Render, sesuaikan handling fallback
    if 'onrender.com' in request.host:
        # Gunakan penanganan khusus untuk deployment Render
        print("Terdeteksi deployment di Render - menggunakan mode fallback")
        return jsonify({
            "status": "partial", 
            "message": "Menggunakan data fallback untuk deployment di Render"
        }), 200
            
    from utils.nodemcu_manager import check_nodemcu_connection
    result, status_code = check_nodemcu_connection()
    return jsonify(result), status_code

@app.route('/check-model-status', methods=['GET', 'OPTIONS'])
def check_model_status():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    # Rute baru untuk memeriksa status model yang dibutuhkan oleh frontend
    try:
        return jsonify({
            'model_trained_flag': config.MODEL_INFO.get('trained', False),
            'model_loaded_in_memory': hasattr(weather_predictor, 'model') and weather_predictor.model is not None,
            'enough_data': get_data_count() >= (weather_predictor.window_size + 10)
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'model_trained_flag': False,
            'model_loaded_in_memory': False,
            'enough_data': False
        })

@app.route('/force-train-model', methods=['GET', 'OPTIONS'])
def force_train_model():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    # Rute baru untuk memaksa pelatihan model yang dibutuhkan oleh frontend
    try:
        result = weather_predictor.train()
        return jsonify({
            'status': 'success',
            'accuracy': result.get('accuracy', 0)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/view-data', methods=['GET', 'OPTIONS'])
def view_data():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
        
    rows = get_all_data_records()
    return jsonify(rows)

@app.route('/api/nodemcu/data', methods=['POST', 'OPTIONS', 'GET'])
def receive_nodemcu_data():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response
    
    if request.method == 'GET':
        # Mengembalikan data terbaru jika metode GET digunakan
        data = get_latest_data()
        if data:
            return jsonify(data)
        return jsonify({})
        
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Request body is empty or not valid JSON'}), 400
        
        print(f"Received data from NodeMCU: {data}")
        
        from utils.database import save_sensor_data

        save_sensor_data(
            data.get('ldr', 0),
            data.get('rain', 0),
            data.get('status', 'UNKNOWN'),
            data.get('rotation', 0)
        )

        return jsonify({'status': 'success', 'message': 'Data received successfully'})
    except Exception as e:
        print(f"Error receiving data from NodeMCU: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Tambahkan fallback route untuk menangani OPTIONS request pada semua route
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return app.make_default_options_response()

# Tambahkan error handler global
@app.errorhandler(Exception)
def handle_error(e):
    print(f"Global error handler caught: {str(e)}")
    import traceback
    print(traceback.format_exc())
    return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================
# MAIN EXECUTION
# =============================================
if __name__ == '__main__':
    config.threads_running = True
    
    # Start background threads
    nodemcu_thread = threading.Thread(target=nodemcu_reader)
    nodemcu_thread.daemon = True
    nodemcu_thread.start()
    
    try:
        auto_train_thread = start_auto_training(weather_predictor)
    except Exception as e:
        print(f"Error starting auto-train thread: {e}")
    
    try:
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=False,
            use_reloader=False
        )
    finally:
        config.threads_running = False
        print("Shutting down application and threads...")