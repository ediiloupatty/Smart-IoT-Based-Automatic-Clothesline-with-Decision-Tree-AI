<?php
/**
 * Database utilities for Smart Clothesline System Application
 * Handles database operations for sensor data
 */

function save_sensor_data($ldr, $rain, $status, $rotation) {
    try {
        $db = new SQLite3(DATABASE);
        $timestamp = date('Y-m-d H:i:s');
        
        $stmt = $db->prepare('
            INSERT INTO sensor_data (timestamp, ldr, rain, status, rotation)
            VALUES (:timestamp, :ldr, :rain, :status, :rotation)
        ');
        
        $stmt->bindValue(':timestamp', $timestamp, SQLITE3_TEXT);
        $stmt->bindValue(':ldr', $ldr, SQLITE3_INTEGER);
        $stmt->bindValue(':rain', $rain, SQLITE3_INTEGER);
        $stmt->bindValue(':status', $status, SQLITE3_TEXT);
        $stmt->bindValue(':rotation', $rotation, SQLITE3_INTEGER);
        
        $result = $stmt->execute();
        $db->close();
        
        echo "Saved sensor data: LDR=$ldr, Rain=$rain, Status=$status, Rotation=$rotation\n";
        return true;
    } catch (Exception $e) {
        echo "Error saving sensor data: " . $e->getMessage() . "\n";
        return false;
    }
}

function get_latest_data() {
    try {
        $db = new SQLite3(DATABASE);
        $result = $db->query('
            SELECT * FROM sensor_data 
            ORDER BY id DESC 
            LIMIT 1
        ');
        
        $row = $result->fetchArray(SQLITE3_ASSOC);
        $db->close();
        
        return $row ?: null;
    } catch (Exception $e) {
        echo "Error getting latest data: " . $e->getMessage() . "\n";
        return null;
    }
}

function get_data_count() {
    try {
        $db = new SQLite3(DATABASE);
        $result = $db->query('SELECT COUNT(*) as count FROM sensor_data');
        $row = $result->fetchArray(SQLITE3_ASSOC);
        $db->close();
        
        return $row['count'] ?? 0;
    } catch (Exception $e) {
        echo "Error getting data count: " . $e->getMessage() . "\n";
        return 0;
    }
}

function get_all_data_records($limit = 100) {
    try {
        $db = new SQLite3(DATABASE);
        $result = $db->query("
            SELECT * FROM sensor_data 
            ORDER BY id DESC 
            LIMIT $limit
        ");
        
        $rows = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $rows[] = $row;
        }
        
        $db->close();
        return $rows;
    } catch (Exception $e) {
        echo "Error getting all data records: " . $e->getMessage() . "\n";
        return [];
    }
}

function get_recent_sensor_data($count) {
    try {
        $db = new SQLite3(DATABASE);
        $result = $db->query("
            SELECT * FROM sensor_data 
            ORDER BY id DESC 
            LIMIT $count
        ");
        
        $rows = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $rows[] = $row;
        }
        
        $db->close();
        return array_reverse($rows); // Return in chronological order
    } catch (Exception $e) {
        echo "Error getting recent sensor data: " . $e->getMessage() . "\n";
        return [];
    }
}