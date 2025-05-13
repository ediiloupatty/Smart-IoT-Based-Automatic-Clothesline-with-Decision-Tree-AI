<?php
/**
 * Main PHP application for Machine Learning Automated Clothesline System
 */

// Require configuration file
require_once 'config.php';
require_once 'utils/database.php';
require_once 'utils/nodemcu_manager.php';

// Set headers for CORS
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With");
header("Content-Type: application/json");

// Get current URI
$request_uri = $_SERVER['REQUEST_URI'];
$parsed_url = parse_url($request_uri);
$path = $parsed_url['path'];

// Router handler
switch ($path) {
    case '/':
        require_once 'views/index.php';
        break;
        
    case '/realtime-monitoring':
        require_once 'views/realtime.php';
        break;
        
    case '/control':
        require_once 'views/control.php';
        break;
        
    case '/settings':
        require_once 'views/settings.php';
        break;
        
    case '/get_data':
        $data = get_latest_data();
        if ($data) {
            echo json_encode($data);
        } else {
            echo json_encode([]);
        }
        break;
        
    case '/check-data-count':
        $count = get_data_count();
        echo json_encode(['count' => $count]);
        break;
        
    case '/send_command':
        $input = json_decode(file_get_contents('php://input'), true);
        $command = $input['command'] ?? '';
        
        if (in_array($command, ["open", "close", "stop"])) {
            $result = send_command_to_nodemcu($command);
            echo json_encode([
                'status' => 'success', 
                'message' => $result['message'] ?? 'Command sent'
            ]);
        } else {
            http_response_code(400);
            echo json_encode(['status' => 'error', 'message' => 'Invalid command']);
        }
        break;
        
    case '/train-model':
        // Call Python script to train model
        try {
            // First check if we have enough data
            $count = get_data_count();
            echo "Training model with $count data records\n";
            
            // Execute Python script
            $output = [];
            $return_var = 0;
            exec("python3 models/train_model.py 2>&1", $output, $return_var);
            
            if ($return_var !== 0) {
                http_response_code(500);
                echo json_encode(['error' => implode("\n", $output)]);
                break;
            }
            
            // Parse the last line of output as JSON result
            $result_json = end($output);
            $result = json_decode($result_json, true);
            
            if (json_last_error() !== JSON_ERROR_NONE) {
                http_response_code(500);
                echo json_encode(['error' => 'Failed to parse model training result']);
                break;
            }
            
            echo json_encode(['accuracy' => $result['accuracy']]);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode(['error' => $e->getMessage()]);
        }
        break;
        
    case '/predict-weather':
        // Call Python script to predict weather
        try {
            global $MODEL_INFO;
            
            // Check if model is trained
            if (!$MODEL_INFO['trained']) {
                echo json_encode([
                    'error' => 'Model not trained yet',
                    'will_rain' => false,
                    'probability' => 0
                ]);
                break;
            }
            
            // Execute Python script
            $output = [];
            $return_var = 0;
            exec("python3 models/predict_weather.py 2>&1", $output, $return_var);
            
            if ($return_var !== 0) {
                http_response_code(500);
                echo json_encode([
                    'error' => implode("\n", $output),
                    'will_rain' => false,
                    'probability' => 0
                ]);
                break;
            }
            
            // Parse the last line of output as JSON result
            $result_json = end($output);
            $result = json_decode($result_json, true);
            
            if (json_last_error() !== JSON_ERROR_NONE) {
                http_response_code(500);
                echo json_encode([
                    'error' => 'Failed to parse prediction result',
                    'will_rain' => false,
                    'probability' => 0
                ]);
                break;
            }
            
            echo json_encode([
                'will_rain' => $result['will_rain'] ?? false,
                'probability' => $result['probability'] ?? 0
            ]);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode([
                'error' => $e->getMessage(),
                'will_rain' => false,
                'probability' => 0
            ]);
        }
        break;
        
    case '/get-config':
        global $NODEMCU_CONFIG;
        echo json_encode([
            'base_url' => $NODEMCU_CONFIG['base_url'],
            'timeout' => $NODEMCU_CONFIG['timeout']
        ]);
        break;
        
    case '/save-config':
        try {
            global $NODEMCU_CONFIG;
            
            $input = json_decode(file_get_contents('php://input'), true);
            echo "Saving config: " . json_encode($input) . "\n";
            
            // Update NodeMCU configuration
            $NODEMCU_CONFIG['base_url'] = $input['base_url'];
            $NODEMCU_CONFIG['timeout'] = (float)$input['timeout'];
            
            // Save settings to database
            save_setting('nodemcu_base_url', $input['base_url']);
            save_setting('nodemcu_timeout', (string)$input['timeout']);
            
            echo json_encode(['status' => 'success', 'message' => 'Configuration saved!']);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;
        
    case '/get-auto-settings':
        global $AUTO_SETTINGS;
        echo json_encode($AUTO_SETTINGS);
        break;
        
    case '/save-auto-settings':
        try {
            global $AUTO_SETTINGS;
            
            $input = json_decode(file_get_contents('php://input'), true);
            echo "Saving auto settings: " . json_encode($input) . "\n";
            
            // Update auto settings
            $AUTO_SETTINGS['enabled'] = $input['enabled'];
            $AUTO_SETTINGS['lightThreshold'] = (int)$input['lightThreshold'];
            $AUTO_SETTINGS['rainThreshold'] = (int)$input['rainThreshold'];
            
            // Save settings to database
            save_setting('auto_enabled', $input['enabled'] ? 'True' : 'False');
            save_setting('light_threshold', (string)$input['lightThreshold']);
            save_setting('rain_threshold', (string)$input['rainThreshold']);
            
            echo json_encode(['status' => 'success', 'message' => 'Auto settings saved!']);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;
        
    case '/get-model-info':
        global $MODEL_INFO;
        echo json_encode($MODEL_INFO);
        break;
        
    case '/check-nodemcu':
        echo json_encode(check_nodemcu_connection());
        break;
        
    case '/view-data':
        $rows = get_all_data_records();
        echo json_encode($rows);
        break;
        
    case '/api/nodemcu/data':
        try {
            if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
                // Handle CORS preflight requests
                http_response_code(200);
                exit;
            }
            
            if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
                http_response_code(405);
                echo json_encode(['status' => 'error', 'message' => 'Method not allowed']);
                break;
            }
            
            $content_type = isset($_SERVER['CONTENT_TYPE']) ? $_SERVER['CONTENT_TYPE'] : '';
            if (strpos($content_type, 'application/json') === false) {
                http_response_code(400);
                echo json_encode(['status' => 'error', 'message' => 'Content-Type must be application/json']);
                break;
            }
            
            $data = json_decode(file_get_contents('php://input'), true);
            if (!$data) {
                http_response_code(400);
                echo json_encode(['status' => 'error', 'message' => 'Request body is empty or not valid JSON']);
                break;
            }
            
            echo "Received data from NodeMCU: " . json_encode($data) . "\n";
            
            // Save data to database
            save_sensor_data(
                $data['ldr'] ?? 0,
                $data['rain'] ?? 0,
                $data['status'] ?? 'UNKNOWN',
                $data['rotation'] ?? 0
            );
            
            // WebSocket handling will be handled via a JavaScript library
            // We'll just return success here
            echo json_encode(['status' => 'success', 'message' => 'Data received successfully']);
        } catch (Exception $e) {
            http_response_code(500);
            echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
        }
        break;
        
    default:
        http_response_code(404);
        echo json_encode(['error' => 'Not Found']);
        break;
}

// Function to handle auto mode checking
function check_auto_mode() {
    // We'll call this function from a cron job or scheduled task
    check_auto_conditions();
}

// If this script is being run from command line, check auto mode
if (php_sapi_name() === 'cli') {
    check_auto_mode();
}