#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
#include <SoftwareSerial.h>

// Konfigurasi WiFi
const char *ssid = "No Internet Connection";
const char *password = "Loupatty143";

// Pin untuk komunikasi serial dengan Arduino
const int RX_PIN = D2; // D2 pada NodeMCU (menerima dari Arduino TX)
const int TX_PIN = D1; // D1 pada NodeMCU (mengirim ke Arduino RX)

// Inisialisasi server web pada port 80
ESP8266WebServer server(80);

// Software Serial untuk komunikasi dengan Arduino
SoftwareSerial arduinoSerial(RX_PIN, TX_PIN); // RX, TX

// Buffer untuk data serial
String serialBuffer = "";
bool isDataComplete = false;

// Variable untuk menyimpan data sensor dari Arduino
DynamicJsonDocument sensorData(512);

// Timeout dan waktu terakhir komunikasi
unsigned long lastArduinoResponse = 0;
const unsigned long ARDUINO_TIMEOUT = 5000; // 5 detik timeout

void setup()
{
    // Inisialisasi Serial untuk debugging
    Serial.begin(115200);
    Serial.println("\nBooting Jemuran Otomatis - NodeMCU API Bridge");

    // Inisialisasi serial untuk komunikasi dengan Arduino
    arduinoSerial.begin(9600);

    // Set default values
    sensorData["ldr"] = 0;
    sensorData["rain"] = 0;
    sensorData["status"] = "MENDETEKSI...";
    sensorData["weather"] = "MENDETEKSI...";
    sensorData["rotation"] = 0;
    sensorData["connected"] = false;

    // Menghubungkan ke WiFi
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    Serial.print("Menghubungkan ke WiFi");
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println("");
    Serial.println("WiFi terhubung");
    Serial.print("Alamat IP: ");
    Serial.println(WiFi.localIP());

    // Mendefinisikan endpoint server
    server.on("/", handleRoot);
    server.on("/api/status", HTTP_GET, handleGetStatus);
    server.on("/api/control", HTTP_POST, handleControl);
    server.on("/api/data", HTTP_GET, handleData);
    server.onNotFound(handleNotFound);

    // Memulai server
    server.begin();
    Serial.println("Server HTTP dimulai");

    // Minta status awal dari Arduino
    delay(2000);              // Tunggu Arduino siap
    arduinoSerial.print("S"); // Kode untuk request status
}

void loop()
{
    // Handle HTTP requests
    server.handleClient();

    // Baca data dari Arduino jika tersedia
    while (arduinoSerial.available())
    {
        char c = arduinoSerial.read();
        serialBuffer += c;

        // Cek untuk end of line (data lengkap)
        if (c == '\n')
        {
            isDataComplete = true;
            break;
        }
    }

    // Parse data jika sudah complete
    if (isDataComplete)
    {
        parseArduinoData(serialBuffer);
        serialBuffer = "";
        isDataComplete = false;
        lastArduinoResponse = millis();
        sensorData["connected"] = true;
    }

    // Check Arduino connection status
    if (millis() - lastArduinoResponse > ARDUINO_TIMEOUT)
    {
        sensorData["connected"] = false;
    }

    // Request update dari Arduino setiap 3 detik
    static unsigned long lastRequest = 0;
    if (millis() - lastRequest > 3000)
    {
        arduinoSerial.print("S"); // Kode untuk request status
        lastRequest = millis();
    }

    // Delay kecil untuk stabilitas
    delay(10);
}

// Parse data dari Arduino
void parseArduinoData(String data)
{
    // Cek apakah data valid JSON
    if (data.indexOf("{") == 0 && data.lastIndexOf("}") > 0)
    {
        // Potong string agar hanya berisi JSON
        data = data.substring(0, data.lastIndexOf("}") + 1);

        DynamicJsonDocument doc(512);
        DeserializationError error = deserializeJson(doc, data);

        if (!error)
        {
            // Copy semua field ke sensorData
            sensorData["ldr"] = doc["ldr"];
            sensorData["rain"] = doc["rain"];
            sensorData["status"] = doc["status"].as<String>();
            sensorData["weather"] = doc["weather"].as<String>();
            sensorData["rotation"] = doc["rotation"];

            // Debug output
            Serial.println("Data dari Arduino berhasil diproses");
            serializeJson(sensorData, Serial);
            Serial.println();
        }
        else
        {
            Serial.print("deserializeJson() failed: ");
            Serial.println(error.c_str());
            Serial.println("Data yang diterima: " + data);
        }
    }
    else
    {
        Serial.println("Data bukan JSON yang valid: " + data);
    }
}

// Handle halaman utama
void handleRoot()
{
    String html = "<!DOCTYPE html>";
    html += "<html lang='id'>";
    html += "<head>";
    html += "<meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<meta http-equiv='refresh' content='0;url=/api/status'>";
    html += "<title>Redirecting to API Status</title>";
    html += "</head>";
    html += "<body>";
    html += "<p>Redirecting to API status...</p>";
    html += "</body>";
    html += "</html>";

    server.send(200, "text/html", html);
}

// Handle GET status
void handleGetStatus()
{
    String html = "<!DOCTYPE html>";
    html += "<html lang='id'>";
    html += "<head>";
    html += "<meta charset='UTF-8'>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
    html += "<title>Jemuran Otomatis API Status</title>";
    html += "<style>";
    html += "body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }";
    html += ".container { max-width: 800px; margin: 0 auto; background-color: #f8f9fa; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }";
    html += "h1 { color: #343a40; }";
    html += "pre { background-color: #e9ecef; padding: 15px; border-radius: 5px; overflow-x: auto; }";
    html += "code { font-family: monospace; }";
    html += ".endpoint { background-color: #fff; margin: 20px 0; padding: 15px; border-left: 5px solid #007bff; border-radius: 3px; }";
    html += ".method { display: inline-block; padding: 5px 10px; border-radius: 3px; font-weight: bold; margin-right: 10px; }";
    html += ".get { background-color: #28a745; color: white; }";
    html += ".post { background-color: #007bff; color: white; }";
    html += "</style>";
    html += "</head>";
    html += "<body>";
    html += "<div class='container'>";
    html += "<h1>Jemuran Otomatis API</h1>";
    html += "<p>IP Address: " + WiFi.localIP().toString() + "</p>";
    html += "<p>Status Arduino: " + String(sensorData["connected"].as<bool>() ? "Terhubung" : "Tidak Terhubung") + "</p>";

    html += "<h2>Endpoints:</h2>";

    html += "<div class='endpoint'>";
    html += "<span class='method get'>GET</span> <code>/api/data</code>";
    html += "<p>Mendapatkan data sensor dalam format JSON</p>";
    html += "</div>";

    html += "<div class='endpoint'>";
    html += "<span class='method post'>POST</span> <code>/api/control</code>";
    html += "<p>Mengirim perintah kontrol ke jemuran</p>";
    html += "<p>Parameters:</p>";
    html += "<ul>";
    html += "<li><code>action</code>: <code>open</code> atau <code>close</code></li>";
    html += "</ul>";
    html += "</div>";

    html += "<h2>Data Sensor Saat Ini:</h2>";
    String jsonOutput;
    serializeJsonPretty(sensorData, jsonOutput);
    html += "<pre><code>" + jsonOutput + "</code></pre>";

    html += "</div>";
    html += "</body>";
    html += "</html>";

    server.send(200, "text/html", html);
}

// Handle API data request
void handleData()
{
    String jsonOutput;
    serializeJson(sensorData, jsonOutput);

    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "GET");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(200, "application/json", jsonOutput);
}

// Handle control commands
void handleControl()
{
    String action = server.arg("action");
    bool success = false;
    String message = "";

    if (action == "open")
    {
        arduinoSerial.print("O"); // Command untuk buka
        message = "Perintah untuk membuka jemuran dikirim";
        success = true;
    }
    else if (action == "close")
    {
        arduinoSerial.print("C"); // Command untuk tutup
        message = "Perintah untuk menutup jemuran dikirim";
        success = true;
    }
    else
    {
        message = "Action tidak valid. Gunakan 'open' atau 'close'";
    }

    DynamicJsonDocument responseDoc(256);
    responseDoc["success"] = success;
    responseDoc["message"] = message;

    String jsonOutput;
    serializeJson(responseDoc, jsonOutput);

    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "POST");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.send(200, "application/json", jsonOutput);
}

// Handle 404 Not Found
void handleNotFound()
{
    DynamicJsonDocument responseDoc(256);
    responseDoc["success"] = false;
    responseDoc["message"] = "Endpoint tidak ditemukan";

    String jsonOutput;
    serializeJson(responseDoc, jsonOutput);

    server.send(404, "application/json", jsonOutput);
}