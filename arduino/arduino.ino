#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>

// Pin Configuration
#define LDR_PIN A0  // Sensor cahaya
#define RAIN_PIN A1 // Sensor hujan
#define SERVO_PIN 9 // Pin servo

// Threshold Values - disesuaikan dengan pembacaan sensor Anda
const int LDR_THRESHOLD = 50;   // Nilai dibawah 50 berarti terang (0-5 saat terang)
const int RAIN_THRESHOLD = 500; // Nilai dibawah 400 berarti hujan

// Servo rotation time (in milliseconds)
const unsigned long ROTATION_TIME = 3000; // 3 detik (diubah dari 5000)

// LCD Object
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo myservo;

// State Variables
int currentPosition = -1; // -1: undefined, 0: closed, 1: open
unsigned long rotationStartTime = 0;
bool isRotating = false;
String weatherStatus = "Mendeteksi...";
400 String clotheslineStatus = "Mendeteksi...";
bool statusChanged = false; // Flag untuk menandakan perubahan status
bool manualControl = false; // Flag untuk menandakan kontrol manual

// Variables for smoothing the LDR value
const int NUM_SAMPLES = 10; // Jumlah sampel untuk smoothing
int ldrValues[NUM_SAMPLES]; // Array untuk menyimpan nilai LDR
int ldrIndex = 0;           // Index untuk array LDR
int smoothedLdrValue = 0;   // Nilai LDR yang sudah dihaluskan

// Variabel untuk komunikasi serial
unsigned long lastSerialSend = 0;
const unsigned long SERIAL_INTERVAL = 1000; // Kirim data setiap 1 detik

void setup()
{
    // Inisialisasi Serial dengan baud rate 9600
    Serial.begin(9600);

    // Initialize LCD
    lcd.init();
    lcd.backlight();
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Jemuran Otomatis");
    lcd.setCursor(0, 1);
    lcd.print("Initializing...");

    // Initialize Servo
    myservo.attach(SERVO_PIN);
    myservo.write(90); // Start in neutral position

    delay(2000);

    // Set initial position
    currentPosition = 1; // Anggap awalnya terbuka
    clotheslineStatus = "TERBUKA";

    // Initialize LDR values
    for (int i = 0; i < NUM_SAMPLES; i++)
    {
        ldrValues[i] = analogRead(LDR_PIN); // Set initial value to LDR sensor reading
    }
}

void loop()
{
    // Check for incoming serial commands
    checkSerialCommands();

    // Read sensors
    int rainValue = analogRead(RAIN_PIN);

    // Smooth the LDR reading by averaging the previous readings
    int ldrValue = analogRead(LDR_PIN);
    ldrValues[ldrIndex] = ldrValue;          // Update the current index with the latest value
    ldrIndex = (ldrIndex + 1) % NUM_SAMPLES; // Update index, wrap around if needed

    smoothedLdrValue = 0;
    for (int i = 0; i < NUM_SAMPLES; i++)
    {
        smoothedLdrValue += ldrValues[i]; // Sum all LDR values
    }
    smoothedLdrValue /= NUM_SAMPLES; // Average the LDR values to reduce sensitivity

    // Interpret sensor readings correctly berdasarkan karakteristik sensor
    bool isDark = smoothedLdrValue > LDR_THRESHOLD; // Nilai LDR rendah (0-5) = terang
    bool isRaining = rainValue < RAIN_THRESHOLD;    // Nilai Rain rendah (<400) = hujan

    // Update weather status
    if (isRaining)
    {
        weatherStatus = "HUJAN";
    }
    else
    {
        weatherStatus = "CERAH";
    }

    // Jika tidak sedang dikendalikan manual, jalankan otomatis
    if (!manualControl)
    {
        // Periksa perubahan kondisi
        bool shouldBeClosed = isRaining || isDark;

        // Decision logic for clothesline - servo hanya bergerak ketika status berubah
        if (isRotating)
        {
            // Cek apakah waktu rotasi sudah selesai
            if (millis() - rotationStartTime >= ROTATION_TIME)
            {
                isRotating = false;
                myservo.detach(); // Lepaskan servo untuk mencegah bergetar

                // Update status setelah selesai
                if (currentPosition == 0)
                {
                    clotheslineStatus = "TERTUTUP";
                }
                else
                {
                    clotheslineStatus = "TERBUKA";
                }
            }
        }
        else
        {
            // Cek jika perlu mengubah posisi dan HANYA jika ada perubahan status
            if (shouldBeClosed && currentPosition != 0)
            {
                // Perlu ditutup
                startClosingClothesline();
                statusChanged = true;
            }
            else if (!shouldBeClosed && currentPosition != 1)
            {
                // Perlu dibuka
                startOpeningClothesline();
                statusChanged = true;
            }
        }
    }
    else
    {
        // Cek apakah waktu rotasi sudah selesai saat di kontrol manual
        if (isRotating && (millis() - rotationStartTime >= ROTATION_TIME))
        {
            isRotating = false;
            myservo.detach(); // Lepaskan servo untuk mencegah bergetar

            // Update status setelah selesai
            if (currentPosition == 0)
            {
                clotheslineStatus = "TERTUTUP";
            }
            else
            {
                clotheslineStatus = "TERBUKA";
            }

            // Reset flag manual control setelah rotasi selesai
            manualControl = false;
        }
    }

    // Update display
    updateDisplay(smoothedLdrValue, rainValue, isDark, isRaining);

    // Send data to Serial for monitoring - kirim secara berkala
    unsigned long currentMillis = millis();
    if (currentMillis - lastSerialSend >= SERIAL_INTERVAL || statusChanged)
    {
        sendSerialData(smoothedLdrValue, rainValue, isDark, isRaining);
        lastSerialSend = currentMillis;

        // Reset flag status berubah
        if (statusChanged)
        {
            statusChanged = false;
        }
    }

    delay(100); // Small delay for stability
}

void checkSerialCommands()
{
    if (Serial.available() > 0)
    {
        char cmd = Serial.read();

        // Clear buffer
        while (Serial.available() > 0)
        {
            Serial.read();
        }

        // Tangani perintah
        if (cmd == 'O')
        {
            // Perintah buka jemuran dari NodeMCU
            manualControl = true; // Tandai sebagai kontrol manual
            startOpeningClothesline();
        }
        else if (cmd == 'C')
        {
            // Perintah tutup jemuran dari NodeMCU
            manualControl = true; // Tandai sebagai kontrol manual
            startClosingClothesline();
        }
        else if (cmd == 'S')
        {
            // Perintah untuk mendapatkan status terkini
            sendSerialData(smoothedLdrValue, analogRead(RAIN_PIN),
                           smoothedLdrValue > LDR_THRESHOLD,
                           analogRead(RAIN_PIN) < RAIN_THRESHOLD);
        }
    }
}

void startOpeningClothesline()
{
    myservo.attach(SERVO_PIN); // Pasang kembali servo
    myservo.write(0);          // Gerakan ke posisi terbuka (sekarang ke kiri)
    isRotating = true;
    rotationStartTime = millis();
    currentPosition = 1; // Tandai sebagai terbuka
    clotheslineStatus = "MEMBUKA...";

    // Pemberitahuan status berubah
    statusChanged = true;
}

void startClosingClothesline()
{
    myservo.attach(SERVO_PIN); // Pasang kembali servo
    myservo.write(180);        // Gerakan ke posisi tertutup (sekarang ke kanan)
    isRotating = true;
    rotationStartTime = millis();
    currentPosition = 0; // Tandai sebagai tertutup
    clotheslineStatus = "MENUTUP...";

    // Pemberitahuan status berubah
    statusChanged = true;
}

void updateDisplay(int ldr, int rain, bool dark, bool raining)
{
    lcd.clear();

    // First row: Sensor readings
    lcd.setCursor(0, 0);
    lcd.print("L:");
    lcd.print(ldr);
    lcd.print(" R:");
    lcd.print(rain);

    // Second row: Status information
    lcd.setCursor(0, 1);
    if (isRotating)
    {
        // Menghitung waktu tersisa dengan aman (mencegah nilai yang sangat besar)
        unsigned long elapsedTime = millis() - rotationStartTime;
        unsigned long remainingSecs;

        if (elapsedTime >= ROTATION_TIME)
        {
            remainingSecs = 0;
        }
        else
        {
            remainingSecs = (ROTATION_TIME - elapsedTime) / 1000;
        }

        lcd.print(weatherStatus);
        lcd.print(" ");
        lcd.print(remainingSecs);
        lcd.print("s");
    }
    else
    {
        lcd.print(weatherStatus);
        lcd.print(" ");
        lcd.print(clotheslineStatus.substring(0, 8));
    }
}

void sendSerialData(int ldr, int rain, bool dark, bool raining)
{
    // Format data untuk NodeMCU dengan JSON sederhana
    Serial.print("{\"ldr\":");
    Serial.print(ldr);
    Serial.print(",\"rain\":");
    Serial.print(rain);
    Serial.print(",\"status\":\"");
    Serial.print(clotheslineStatus);
    Serial.print("\"");

    // Tambahkan info cuaca
    Serial.print(",\"weather\":\"");
    Serial.print(weatherStatus);
    Serial.print("\"");

    // Tampilkan waktu rotasi jika sedang berputar
    if (isRotating)
    {
        // Menghitung waktu tersisa dengan aman
        unsigned long elapsedTime = millis() - rotationStartTime;
        unsigned long remainingTime;

        if (elapsedTime >= ROTATION_TIME)
        {
            remainingTime = 0;
        }
        else
        {
            remainingTime = (ROTATION_TIME - elapsedTime) / 1000;
        }

        Serial.print(",\"rotation\":");
        Serial.print(remainingTime);
    }
    else
    {
        Serial.print(",\"rotation\":0");
    }

    Serial.println("}"); // Akhiri JSON dan line
}