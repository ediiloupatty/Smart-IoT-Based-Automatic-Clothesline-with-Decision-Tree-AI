"""
Weather prediction model using Decision Tree
"""

import os
import sys
import threading
import time
import numpy as np
import joblib
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import MinMaxScaler

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.database import get_all_sensor_data, get_data_count, get_recent_sensor_data

class WeatherPredictor:
    def __init__(self):
        """Initialize the weather predictor model"""
        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        self.window_size = 3  # Reduce from 6 to 3
        self.threshold = 0.65
        
        # Try to load model if it exists
        try:
            self.load_model()
            config.MODEL_INFO['trained'] = True
        except (FileNotFoundError, EOFError):
            print("Model file not found or empty. Will need training.")
            config.MODEL_INFO['trained'] = False
        except KeyError as e:
            print(f"Incompatible model format: {e}. Model needs retraining.")
            config.MODEL_INFO['trained'] = False
            self.build_model()  # Initialize a new model
        except Exception as e:
            print(f"Unexpected error loading model: {e}")
            config.MODEL_INFO['trained'] = False

    def load_model(self, filename='models/weather_model.joblib'):
        """Load a trained model from disk"""
        try:
            print(f"Loading model from {os.path.abspath(filename)}")
            self.model = joblib.load(filename)
            self.scaler = joblib.load('models/scaler.save')
            print("Model loaded successfully")
        except (FileNotFoundError, EOFError) as e:
            print(f"Model file not found or empty: {e}")
            raise
        except KeyError as e:
            print(f"Incompatible model format: {e}. Needs retraining.")
            # Reset to untrained state
            config.MODEL_INFO['trained'] = False
            self.build_model()  # Initialize a new model
            raise ValueError("Model needs retraining due to compatibility issues")
        except Exception as e:
            print(f"Unexpected error loading model: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    def create_dataset(self, scaled_data, y):
        """Create time-series dataset from scaled sensor data"""
        try:
            if len(scaled_data) <= self.window_size:
                raise ValueError(f"Data length ({len(scaled_data)}) must be greater than window size ({self.window_size})")
                
            X, y_processed = [], []
            for i in range(len(scaled_data) - self.window_size):
                # Flatten window to 1D array
                window = scaled_data[i:(i+self.window_size-1), :].flatten()
                target = y[i+self.window_size-1]
                X.append(window)
                y_processed.append(target)
                
            if not X or not y_processed:
                raise ValueError("Failed to create dataset - empty X or y")
                
            return np.array(X), np.array(y_processed)
        except Exception as e:
            print(f"Error in create_dataset: {e}")
            raise

    def load_training_data(self):
        """Load and prepare training data from database"""
        data = get_all_sensor_data()
        
        print(f"Found {len(data)} records for training")
        
        if len(data) < self.window_size + 10:
            raise ValueError(f"Insufficient data for training. Need at least {self.window_size + 10} records, but only have {len(data)}")
        
        # Convert string data to integers
        converted_data = []
        for row in data:
            try:
                ldr = int(row[0])
                rain = int(row[1])
                converted_data.append([ldr, rain])
            except (ValueError, TypeError) as e:
                print(f"Error converting data: {e}, row: {row}")
                continue
        
        if not converted_data:
            raise ValueError("No valid data after conversion")
                
        return np.array(converted_data)

    def preprocess_data(self, data):
        """Preprocess data for training the model"""
        try:
            # Use all columns as features
            X = data[:, :]
            # Use rain as target
            y = data[:, 1]
            
            # Scale features
            scaled_X = self.scaler.fit_transform(X)
            
            # Convert target to categories (0 = no rain, 1 = rain)
            y = np.where(y < self.threshold, 1, 0).astype(int)
            
            # Create dataset
            X_processed, y_processed = self.create_dataset(scaled_X, y)
            
            return X_processed, y_processed
        except Exception as e:
            print(f"Error in preprocess_data: {e}")
            raise

    def build_model(self):
        """Build a Decision Tree model with parameters to avoid overfitting"""
        self.model = DecisionTreeClassifier(
            max_depth=3,              # Limit tree depth to prevent overfitting
            min_samples_split=5,      # Require more samples to split a node
            min_samples_leaf=3,       # Require more samples in leaf nodes
            class_weight='balanced'   # Balance the classes for better predictions
        )
        print("Built model with parameters to prevent overfitting")

    def train(self, epochs=20, batch_size=32):
        """Train the weather prediction model"""
        try:
            # Check if we have enough data
            data_count = get_data_count()
            print(f"Data count: {data_count}")
            
            if data_count < self.window_size + 10:
                raise ValueError(f"Not enough data. Need at least {self.window_size + 10} records, but only have {data_count}")
            
            # Get training data
            data = self.load_training_data()
            print(f"Data shape: {data.shape}")
            
            # Preprocess data
            try:
                X, y = self.preprocess_data(data)
                print(f"X shape: {X.shape}, y shape: {y.shape}")
                print(f"Sample y values: {np.unique(y, return_counts=True)}")
            except Exception as e:
                print(f"Error in preprocessing: {e}")
                raise
            
            # Check if we have enough data to split
            if len(X) < 2:
                raise ValueError("Not enough data for training/testing split")
                    
            split = max(1, int(0.8 * len(X)))
            
            # Build and train model
            self.build_model()
            self.model.fit(X[:split], y[:split])
            
            # Save model after training
            self.save_model()
            
            # Calculate accuracy
            if len(X) > split:  # Make sure we have test data
                accuracy = self.model.score(X[split:], y[split:])
            else:
                accuracy = self.model.score(X[:split], y[:split])  # Use training data if necessary
            
            # Update model info
            config.MODEL_INFO['trained'] = True
            config.MODEL_INFO['lastTraining'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            config.MODEL_INFO['accuracy'] = accuracy
            
            # Save model info to database
            config.save_setting('model_trained', 'True')
            config.save_setting('model_last_training', config.MODEL_INFO['lastTraining'])
            config.save_setting('model_accuracy', str(accuracy))
            
            print(f"Model trained with accuracy: {accuracy}")
            return {"accuracy": accuracy}
        except Exception as e:
            print(f"Error during training: {e}")
            raise

    def predict_next_hour(self, recent_data):
        """
        Predict weather for the next hour using recent sensor data.
        Returns prediction (0=sunny, 1=rain) and confidence level.
        """
        if not self.model:
            try:
                self.load_model()
            except (FileNotFoundError, EOFError, ValueError):
                # If model can't be loaded, build a new one
                self.build_model()
                raise ValueError("Model not trained or incompatible. Please train first.")
            except Exception as e:
                print(f"Unexpected error loading model: {e}")
                self.build_model()  # Create empty model
                raise ValueError("Model error. Please train first.")
        
        # Convert data to numpy array
        data_array = np.array(recent_data)
        print(f"Input data shape for prediction: {data_array.shape}")
        
        try:
            # Scale the input data
            scaled = self.scaler.transform(data_array)
            
            # Reshape to match the expected input shape (flatten window)
            flattened = scaled.flatten()
            print(f"Flattened data shape: {flattened.shape}")
            
            # Make prediction
            prediction = self.model.predict([flattened])[0]
            
            # Get probability of the prediction
            probabilities = self.model.predict_proba([flattened])[0]
            print(f"Raw prediction: {prediction}, probabilities: {probabilities}")
            
            # Get the probability for the predicted class
            if len(probabilities) > 1:
                rain_probability = probabilities[1]  # Probability for class 1 (rain)
            else:
                rain_probability = probabilities[0]
                
            # Adjust probability to be more realistic
            adjusted_probability = 0.60 + (rain_probability * 0.35)
            
            print(f"Original probability: {rain_probability}, adjusted: {adjusted_probability}")
            return prediction, float(adjusted_probability)
        except Exception as e:
            print(f"Error in model prediction: {e}")
            import traceback
            print(traceback.format_exc())
            raise

    def save_model(self, filename='models/weather_model.joblib'):
        """Save the trained model to disk"""
        try:
            dir_path = os.path.dirname(filename)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            print(f"Saving model to {os.path.abspath(filename)}")
            # Use protocol=4 which is compatible with Python 3.4+ 
            # and works consistently across environments
            joblib.dump(self.model, filename, protocol=4)
            joblib.dump(self.scaler, os.path.join(dir_path, 'scaler.save'), protocol=4)
            print("Model saved successfully")
        except Exception as e:
            print(f"Error saving model: {e}")
            raise


def auto_train_model_thread():
    """Thread function to periodically train the model automatically"""
    global weather_predictor
    while config.threads_running:
        try:
            print("Automatic training started")
            # Check if we have enough data
            count = get_data_count()
            
            if count >= (weather_predictor.window_size + 10):
                # Train model
                result = weather_predictor.train()
                print(f"Auto-training complete. Accuracy: {result['accuracy']}")
            else:
                print(f"Not enough data for training. Need {weather_predictor.window_size + 10}, have {count}")
        except Exception as e:
            print(f"Error in auto training: {e}")
        
        # Wait before next training
        time.sleep(config.APP_CONFIG['training_interval'])

def start_auto_training(predictor):
    """Start the automatic model training thread"""
    global weather_predictor
    weather_predictor = predictor
    auto_train_thread = threading.Thread(target=auto_train_model_thread)
    auto_train_thread.daemon = True
    auto_train_thread.start()
    return auto_train_thread