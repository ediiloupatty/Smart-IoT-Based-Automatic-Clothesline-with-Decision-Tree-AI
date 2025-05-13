<?php
/**
 * Configuration file for Smart Clothesline System Application
 * Contains all configuration parameters and settings
 */

// Load environment variables from .env file if exists
if (file_exists(__DIR__ . '/.env')) {
    $envLines = file(__DIR__ . '/.env', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($envLines as $line) {
        if (strpos(trim($line), '#') === 0) {
            continue;
        }
        list($name, $value) = explode('=', $line, 2);
        $_ENV[trim($name)] = trim($value);
        putenv(sprintf('%s=%s', trim($name), trim($value)));
    }
}

// CORS configuration
define('CORS_ALLOWED_ORIGINS', '*');
define('SECRET_KEY', getenv('SECRET_KEY') ?: 'dev-secret-key');

// Check if we're running on a production environment (Render)
define('IS_PRODUCTION', getenv('RENDER') ?: false);

// Database configuration
if (IS_PRODUCTION) {
    // In production, use a directory that persists
    define('DATABASE', getenv('DATABASE_URL') ?: __DIR__ . '/data/sensor_data.db');
} else {
    define('DATABASE', __DIR__ . '/data/sensor_data.db');
}

// Make sure the data directory exists
if (!file_exists(dirname(DATABASE))) {
    mkdir(dirname(DATABASE), 0777, true);
}

// NodeMCU Configuration
$NODEMCU_CONFIG = [
    'base_url' => getenv('NODEMCU_BASE_URL') ?: 'http://192.168.8.137/',
    'timeout' => (float)(getenv('NODEMCU_TIMEOUT') ?: '10')
];

// Auto mode settings
$AUTO_SETTINGS = [
    'enabled' => getenv('AUTO_ENABLED') === 'true',
    'lightThreshold' => (int)(getenv('LIGHT_THRESHOLD') ?: '500'),
    'rainThreshold' => (int)(getenv('RAIN_THRESHOLD') ?: '500')
];

// Model information
$MODEL_INFO = [
    'trained' => false,
    'lastTraining' => null,
    'accuracy' => null
];

// Additional configuration
$APP_CONFIG = [
    'polling_interval' => (int)(getenv('POLLING_INTERVAL') ?: '10'),
    'training_interval' => (int)(getenv('TRAINING_INTERVAL') ?: '3600'),
    'command_cooldown' => (int)(getenv('COMMAND_COOLDOWN') ?: '60')
];

// Thread control variables (used in Python ML integration)
$threads_running = true;
$last_auto_command_time = 0;

// Database functions
function init_db() {
    try {
        $db = new SQLite3(DATABASE);
        $db->exec('
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                ldr INTEGER,
                rain INTEGER,
                status TEXT,
                rotation INTEGER
            )
        ');
        
        // Create settings table if it doesn't exist
        $db->exec('
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                key TEXT UNIQUE,
                value TEXT
            )
        ');
        
        $db->close();
        echo "Database initialized successfully\n";
        return true;
    } catch (Exception $e) {
        echo "Error initializing database: " . $e->getMessage() . "\n";
        return false;
    }
}

function save_setting($key, $value) {
    try {
        $db = new SQLite3(DATABASE);
        $stmt = $db->prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (:key, :value)');
        $stmt->bindValue(':key', $key, SQLITE3_TEXT);
        $stmt->bindValue(':value', (string)$value, SQLITE3_TEXT);
        $stmt->execute();
        $db->close();
        echo "Setting saved: $key=$value\n";
        return true;
    } catch (Exception $e) {
        echo "Error saving setting: " . $e->getMessage() . "\n";
        return false;
    }
}

function load_setting($key, $default = null) {
    try {
        $db = new SQLite3(DATABASE);
        $stmt = $db->prepare('SELECT value FROM settings WHERE key = :key');
        $stmt->bindValue(':key', $key, SQLITE3_TEXT);
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        $db->close();
        
        if ($row) {
            echo "Setting loaded: $key=" . $row['value'] . "\n";
            return $row['value'];
        }
        return $default;
    } catch (Exception $e) {
        echo "Error loading setting: " . $e->getMessage() . "\n";
        return $default;
    }
}

function load_all_settings() {
    global $NODEMCU_CONFIG, $AUTO_SETTINGS, $MODEL_INFO;
    
    try {
        // Load NodeMCU config
        $base_url = load_setting('nodemcu_base_url', $NODEMCU_CONFIG['base_url']);
        $timeout = (float)load_setting('nodemcu_timeout', $NODEMCU_CONFIG['timeout']);
        
        $NODEMCU_CONFIG['base_url'] = $base_url;
        $NODEMCU_CONFIG['timeout'] = $timeout;
        
        // Load auto settings
        $AUTO_SETTINGS['enabled'] = load_setting('auto_enabled', 'False') === 'True';
        $AUTO_SETTINGS['lightThreshold'] = (int)load_setting('light_threshold', $AUTO_SETTINGS['lightThreshold']);
        $AUTO_SETTINGS['rainThreshold'] = (int)load_setting('rain_threshold', $AUTO_SETTINGS['rainThreshold']);
        
        // Load model info
        $MODEL_INFO['trained'] = load_setting('model_trained', 'False') === 'True';
        $MODEL_INFO['lastTraining'] = load_setting('model_last_training');
        $accuracy = load_setting('model_accuracy');
        $MODEL_INFO['accuracy'] = $accuracy ? (float)$accuracy : null;
        
        echo "All settings loaded successfully\n";
    } catch (Exception $e) {
        echo "Error loading settings: " . $e->getMessage() . "\n";
    }
}

// Print system info
echo "System: " . php_uname() . "\n";
echo "PHP: " . phpversion() . "\n";
echo "Database path: " . realpath(DATABASE) . "\n";
echo "Production mode: " . (IS_PRODUCTION ? 'true' : 'false') . "\n";

// Initialize the database and load settings
init_db();
load_all_settings();