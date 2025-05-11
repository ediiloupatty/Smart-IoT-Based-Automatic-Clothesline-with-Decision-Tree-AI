"""
Main application file for IoT Clothesline System
"""

import os
import sys
import time
from flask import Flask, jsonify, request, render_template, send_from_directory
from datetime import datetime

# Print system info for debugging
print(f"System: {sys.platform}")
print(f"Python: {sys.version.split()[0]}")

# Add absolute paths to help with imports
current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Database path: {os.path.join(current_dir, 'data', 'sensor_data.db')}")

# Set production mode
production = os.environ.get('PRODUCTION', 'true').lower() == 'true'
print(f"Production mode: {production}")

# Show current working directory
print(f"Current working directory: {os.getcwd()}")
print(f"Absolute path to app: {os.path.abspath(__file__)}")

# Create necessary directories
data_dir = os.path.join(current_dir, 'data')
models_dir = os.path.join(current_dir, 'models')

for directory in [data_dir, models_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

# Import project modules
import config
from models.weather_predictor import WeatherPredictor, start_auto_training
from utils.database import save_sensor_data, get_recent_sensor_data, get_predictions, save_prediction

# Initialize Flask app
app = Flask(__name__)

# Initialize weather predictor with robust error handling
try:
    weather_predictor = WeatherPredictor()
except ValueError as e:
    print(f"Warning: {e}")
    weather_predictor = WeatherPredictor()
    # Ensure the model attribute is initialized even if loading failed
    if weather_predictor.model is None:
        weather_predictor.build_model()
    config.MODEL_INFO['trained'] = False
except Exception as e:
    print(f"Critical error initializing weather predictor: {e}")
    import traceback
    print(traceback.format_exc())
    # Create minimal predictor
    weather_predictor = WeatherPredictor()
    weather_predictor.build_model()
    config.MODEL_INFO['trained'] = False

# Start background processes
if production:
    # Start auto-training thread
    config.threads_running = True
    auto_train_thread = start_auto_training(weather_predictor)

# Routes
@app.route('/')
def index():
    """Render the main dashboard"""
    return render_template('index.html')

@app.route('/realtime')
def realtime():
    """Render the realtime monitoring page"""
    return render_template('realtime.html')

@app.route('/control')
def control():
    """Render the control panel"""
    return render_template('control.html')

@app.route('/settings')
def settings():
    """Render the settings page"""
    return render_template('settings.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/sensor-data', methods=['POST'])
def receive_sensor_data():
    """API endpoint to receive sensor data from devices"""
    try:
        data = request.get_json()
        
        if not data or 'ldr' not in data or 'rain' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Invalid data. LDR and rain values required.'
            }), 400
        
        ldr = data['ldr']
        rain = data['rain']
        
        # Save to database
        save_sensor_data(ldr, rain)
        
        # If model is trained, make prediction
        prediction_result = None
        if config.MODEL_INFO['trained']:
            try:
                recent_data = get_recent_sensor_data(window_size=weather_predictor.window_size-1)
                if len(recent_data) >= weather_predictor.window_size-1:
                    prediction, confidence = weather_predictor.predict_next_hour(recent_data)
                    save_prediction(prediction, confidence)
                    prediction_result = {
                        'prediction': int(prediction),
                        'confidence': float(confidence),
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
            except Exception as e:
                print(f"Error making prediction: {e}")
        
        return jsonify({
            'status': 'success',
            'message': 'Data received successfully',
            'prediction': prediction_result
        })
    except Exception as e:
        print(f"Error processing sensor data: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/recent-data', methods=['GET'])
def get_recent_data():
    """API endpoint to get recent sensor data"""
    try:
        count = request.args.get('count', 10, type=int)
        data = get_recent_sensor_data(count)
        predictions = get_predictions(count)
        
        return jsonify({
            'status': 'success',
            'data': [{'ldr': row[0], 'rain': row[1], 'timestamp': row[2]} for row in data],
            'predictions': [{'prediction': p[0], 'confidence': p[1], 'timestamp': p[2]} for p in predictions]
        })
    except Exception as e:
        print(f"Error getting recent data: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/force-train', methods=['POST'])
def force_train():
    """Force model training regardless of previous state"""
    try:
        result = weather_predictor.train()
        return jsonify({
            "status": "success",
            "message": "Model trained successfully",
            "data": result
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/train', methods=['POST'])
def train_model():
    """API endpoint to train the model"""
    try:
        result = weather_predictor.train()
        return jsonify({
            'status': 'success',
            'message': 'Model trained successfully',
            'accuracy': result['accuracy']
        })
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        print(f"Error training model: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/model-info', methods=['GET'])
def get_model_info():
    """API endpoint to get model information"""
    return jsonify({
        'status': 'success',
        'data': config.MODEL_INFO
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=not production)