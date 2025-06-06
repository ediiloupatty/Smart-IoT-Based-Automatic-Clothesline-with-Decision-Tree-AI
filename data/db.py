"""
Weather Prediction Decision Tree Classifier - Testing Version
Program sederhana untuk testing Machine Learning Model
"""

import sqlite3
import numpy as np
import pandas as pd
import joblib
import os
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

class WeatherPredictor:
    def __init__(self, db_path='sensor_data.db'):
        """
        Initialize Weather Predictor
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.feature_columns = ['ldr', 'rain', 'rotation']
        self.target_column = 'status'
        
        # Create models directory if not exists
        os.makedirs('models', exist_ok=True)
        
    def connect_db(self):
        """Connect to SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None
    
    def load_data(self):
        """Load data from sensor_data table"""
        conn = self.connect_db()
        if conn is None:
            return None
            
        try:
            query = """
            SELECT id, timestamp, ldr, rain, status, rotation 
            FROM sensor_data 
            WHERE ldr IS NOT NULL 
            AND rain IS NOT NULL 
            AND status IS NOT NULL 
            AND rotation IS NOT NULL
            ORDER BY timestamp DESC
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            print(f"Data loaded: {len(df)} records")
            print(f"Columns: {df.columns.tolist()}")
            print(f"Data shape: {df.shape}")
            
            return df
            
        except Exception as e:
            print(f"Error loading data: {e}")
            conn.close()
            return None
    
    def preprocess_data(self, df):
        """
        Preprocess data for training
        Args:
            df: DataFrame with sensor data
        Returns:
            X: Features array
            y: Target array
        """
        try:
            # Check if required columns exist
            missing_cols = [col for col in self.feature_columns + [self.target_column] if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing columns: {missing_cols}")
            
            # Prepare features (X) and target (y)
            X = df[self.feature_columns].copy()
            y = df[self.target_column].copy()
            
            # Handle missing values
            X = X.fillna(X.mean())
            y = y.fillna('UNKNOWN')  # Replace NaN with 'UNKNOWN'
            
            # Clean up target column - remove empty strings and rare classes
            print("Original target distribution:")
            print(y.value_counts())
            
            # Replace empty strings with 'UNKNOWN'
            y = y.replace('', 'UNKNOWN')
            
            # Keep only classes with at least 2 samples for stratified split
            class_counts = y.value_counts()
            valid_classes = class_counts[class_counts >= 2].index.tolist()
            
            print(f"\nClasses with >= 2 samples: {len(valid_classes)}")
            print(f"Valid classes: {valid_classes}")
            
            # Filter data to keep only valid classes
            mask = y.isin(valid_classes)
            X_filtered = X[mask]
            y_filtered = y[mask]
            
            print(f"\nData after filtering:")
            print(f"Original samples: {len(y)}")
            print(f"Filtered samples: {len(y_filtered)}")
            print("Filtered target distribution:")
            print(y_filtered.value_counts())
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X_filtered)
            
            # Encode target labels
            y_encoded = self.label_encoder.fit_transform(y_filtered)
            
            print(f"\nFinal shapes:")
            print(f"Features shape: {X_scaled.shape}")
            print(f"Target shape: {y_encoded.shape}")
            print(f"Target classes: {self.label_encoder.classes_}")
            
            return X_scaled, y_encoded
            
        except Exception as e:
            print(f"Error in preprocessing: {e}")
            return None, None
    
    def train_model(self, test_size=0.2, random_state=42):
        """
        Train Decision Tree model
        Args:
            test_size: Proportion of test data
            random_state: Random seed for reproducibility
        Returns:
            Dictionary with training results
        """
        print("Starting model training...")
        
        # Load data
        df = self.load_data()
        if df is None or df.empty:
            raise ValueError("No data available for training")
        
        # Preprocess data
        X, y = self.preprocess_data(df)
        if X is None or y is None:
            raise ValueError("Data preprocessing failed")
        
        # Check if we have enough data
        if len(X) < 10:
            raise ValueError(f"Insufficient data for training. Need at least 10 records, got {len(X)}")
        
        # Check class distribution for stratified split
        unique_classes, class_counts = np.unique(y, return_counts=True)
        min_class_count = min(class_counts)
        
        print(f"\nClass distribution check:")
        for cls, count in zip(unique_classes, class_counts):
            class_name = self.label_encoder.inverse_transform([cls])[0]
            print(f"  {class_name}: {count} samples")
        
        # Use stratified split only if all classes have at least 2 samples
        use_stratify = min_class_count >= 2
        
        if use_stratify:
            print("Using stratified split...")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y
            )
        else:
            print("Using random split (some classes have < 2 samples)...")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state
            )
        
        # Create Decision Tree model
        self.model = DecisionTreeClassifier(
            max_depth=8,              # Increased depth for complex data
            min_samples_split=10,     # Increased to prevent overfitting
            min_samples_leaf=5,       # Increased to prevent overfitting
            random_state=random_state,
            class_weight='balanced'   # Handle imbalanced classes
        )
        
        # Train model
        print(f"Training on {len(X_train)} samples...")
        self.model.fit(X_train, y_train)
        
        # Make predictions
        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)
        
        # Calculate accuracy
        train_accuracy = accuracy_score(y_train, y_pred_train)
        test_accuracy = accuracy_score(y_test, y_pred_test)
        
        # Print results
        print(f"\n=== Training Results ===")
        print(f"Training Accuracy: {train_accuracy:.4f}")
        print(f"Testing Accuracy: {test_accuracy:.4f}")
        
        # Get class names for report
        class_names = [self.label_encoder.inverse_transform([i])[0] for i in range(len(self.label_encoder.classes_))]
        
        print(f"\n=== Classification Report ===")
        print(classification_report(y_test, y_pred_test, target_names=class_names, zero_division=0))
        
        print(f"\n=== Confusion Matrix ===")
        cm = confusion_matrix(y_test, y_pred_test)
        print("Predicted ->")
        print("Actual |")
        print(cm)
        
        # Save model
        self.save_model()
        
        results = {
            'train_accuracy': train_accuracy,
            'test_accuracy': test_accuracy,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'classes': self.label_encoder.classes_.tolist(),
            'class_distribution': dict(zip(class_names, class_counts.tolist())),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return results
    
    def predict(self, ldr, rain, rotation):
        """
        Make prediction for new data
        Args:
            ldr: LDR sensor value
            rain: Rain sensor value  
            rotation: Rotation value
        Returns:
            Prediction and probability
        """
        if self.model is None:
            try:
                self.load_model()
            except:
                raise ValueError("Model not trained. Please train first.")
        
        # Prepare input data
        input_data = np.array([[ldr, rain, rotation]])
        
        # Scale input
        input_scaled = self.scaler.transform(input_data)
        
        # Make prediction
        prediction = self.model.predict(input_scaled)[0]
        probabilities = self.model.predict_proba(input_scaled)[0]
        
        # Decode prediction
        predicted_status = self.label_encoder.inverse_transform([prediction])[0]
        max_probability = max(probabilities)
        
        return {
            'predicted_status': predicted_status,
            'confidence': max_probability,
            'all_probabilities': dict(zip(self.label_encoder.classes_, probabilities))
        }
    
    def save_model(self):
        """Save trained model and preprocessors"""
        try:
            if self.model is None:
                raise ValueError("No model to save")
            
            # Save model
            model_path = os.path.join('models', 'weather_decision_tree.joblib')
            joblib.dump(self.model, model_path)
            
            # Save scaler
            scaler_path = os.path.join('models', 'scaler.joblib')
            joblib.dump(self.scaler, scaler_path)
            
            # Save label encoder
            encoder_path = os.path.join('models', 'label_encoder.joblib')
            joblib.dump(self.label_encoder, encoder_path)
            
            print(f"Model saved successfully!")
            print(f"- Model: {model_path}")
            print(f"- Scaler: {scaler_path}")
            print(f"- Encoder: {encoder_path}")
            
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def load_model(self):
        """Load trained model and preprocessors"""
        try:
            # Load model
            model_path = os.path.join('models', 'weather_decision_tree.joblib')
            self.model = joblib.load(model_path)
            
            # Load scaler
            scaler_path = os.path.join('models', 'scaler.joblib')
            self.scaler = joblib.load(scaler_path)
            
            # Load label encoder
            encoder_path = os.path.join('models', 'label_encoder.joblib')
            self.label_encoder = joblib.load(encoder_path)
            
            print("Model loaded successfully!")
            
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    def get_data_info(self):
        """Get information about available data"""
        df = self.load_data()
        if df is None or df.empty:
            return "No data available"
        
        info = {
            'total_records': len(df),
            'date_range': f"{df['timestamp'].min()} to {df['timestamp'].max()}",
            'status_distribution': df['status'].value_counts().to_dict(),
            'feature_stats': df[self.feature_columns].describe().to_dict()
        }
        
        return info

def main():
    """Main testing function"""
    print("=== Weather Prediction Decision Tree Testing ===\n")
    
    # Initialize predictor
    predictor = WeatherPredictor('sensor_data.db')
    
    try:
        # Show data info
        print("1. Data Information:")
        data_info = predictor.get_data_info()
        print(data_info)
        print("\n" + "="*50 + "\n")
        
        # Train model
        print("2. Training Model:")
        results = predictor.train_model()
        print(f"\nTraining completed at: {results['timestamp']}")
        print("\n" + "="*50 + "\n")
        
        # Test predictions
        print("3. Testing Predictions:")
        
        # Example predictions
        test_cases = [
            (100, 500, 45),   # Example 1
            (800, 200, 90),   # Example 2
            (300, 750, 180),  # Example 3
        ]
        
        for i, (ldr, rain, rotation) in enumerate(test_cases, 1):
            try:
                result = predictor.predict(ldr, rain, rotation)
                print(f"Test Case {i}:")
                print(f"  Input: LDR={ldr}, Rain={rain}, Rotation={rotation}")
                print(f"  Prediction: {result['predicted_status']}")
                print(f"  Confidence: {result['confidence']:.4f}")
                print(f"  All probabilities: {result['all_probabilities']}")
                print()
            except Exception as e:
                print(f"Test Case {i} failed: {e}")
        
        print("="*50)
        print("Testing completed successfully!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()