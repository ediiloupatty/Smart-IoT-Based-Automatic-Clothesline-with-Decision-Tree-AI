# Smart Clothesline Automation Using IoT & Decision Tree Classifier

An Internet of Things (IoT)-based smart clothesline system with AI Machine Learning (Decision Tree Classifier) for weather prediction and fully automated clothesline control.

## Features

* **Weather Monitoring** – Automatically detects rainy or sunny conditions.
* **Automatic Clothesline Movement** – Extends/retracts clothesline based on weather predictions.
* **Remote Control** – Operate the clothesline via web or mobile devices.
* **AI Weather Prediction** – Uses Decision Tree Classifier to analyze sensor data.
* **Notifications** – Alerts users in case of extreme weather changes.
* **Web Interface** – HTML/CSS-based dashboard for monitoring and control.

## Technologies Used

* **Python** – Backend & sensor integration.
* **C++** – NodeMCU (microcontroller) programming.
* **HTML/CSS** – Web dashboard UI.
* **IoT Devices** – Light sensor, rain sensor, clothesline motor actuator.
* **Machine Learning** – Decision Tree Classifier for weather prediction.

## Installation

```bash
# Clone repository
git clone https://github.com/ediiloupatty/iot-clothesline-system.git
cd iot-clothesline-system

# Install Python dependencies
pip install -r requirements.txt

# Upload C++ code to NodeMCU
# (use Arduino IDE or compatible platform)

# Run backend application
python app.py
```

Open your browser and go to:

```
http://localhost:5000
```

## How It Works

1. Sensors read light and rain conditions.
2. Data is sent to the Python backend.
3. The Decision Tree Classifier predicts the weather.
4. The motor automatically moves the clothesline in/out.
5. Users can monitor and control the clothesline via the web dashboard.

## Contributing

Contributions are welcome! Fork the repository, make changes, and submit a pull request.

## License

© Group 3 – Free to use for learning and development purposes.
