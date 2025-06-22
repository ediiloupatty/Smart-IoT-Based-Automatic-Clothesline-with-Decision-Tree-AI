# IoT Clothesline System

Sistem jemuran pintar berbasis Internet of Things (IoT) yang dapat memonitor dan mengontrol jemuran pakaian secara otomatis menggunakan sensor dan perangkat IoT.

## Fitur

- **Monitoring Cuaca**: Mendeteksi kondisi cuaca (hujan/cerah) secara otomatis.
- **Otomatisasi Jemuran**: Menggerakkan jemuran masuk/keluar sesuai kondisi cuaca.
- **Kontrol Jarak Jauh**: Kontrol jemuran melalui aplikasi web atau perangkat mobile.
- **Notifikasi**: Memberikan peringatan ke pengguna jika terjadi perubahan cuaca ekstrem.
- **Antarmuka Web**: Tersedia dashboard berbasis HTML/CSS untuk monitoring dan kontrol.

## Teknologi yang Digunakan

- **Python**: Backend & integrasi sensor.
- **C++**: Pemrograman mikrokontroler/embedded system.
- **HTML/CSS**: Tampilan dashboard web.
- **IoT Devices**: Sensor cuaca, aktuator motor, dsb.

## Instalasi

1. **Clone repository:**
   ```bash
   git clone https://github.com/ediiloupatty/iot-clothesline-system.git
   cd iot-clothesline-system
   ```

2. **Install dependencies Python:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Upload kode C++ ke mikrokontroler**  
   (pastikan menggunakan Arduino IDE atau sejenis)

4. **Jalankan aplikasi backend:**
   ```bash
   python app.py
   ```

5. **Akses dashboard web:**  
   Buka browser dan akses `http://localhost:5000`

## Cara Kerja

1. Sensor cuaca membaca kondisi lingkungan.
2. Data sensor dikirim ke backend (Python).
3. Jika terdeteksi hujan, motor secara otomatis menarik jemuran ke dalam.
4. Pengguna dapat memantau dan mengontrol jemuran melalui dashboard web.

## Kontribusi

Kontribusi sangat terbuka! Silakan fork repo ini, lakukan perubahan, dan buat pull request.

## Lisensi

Kelompok 3
