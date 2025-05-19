import sqlite3

# Ganti dengan nama file database SQLite Anda
nama_database = 'sensor_data.db'

# Koneksi ke database
conn = sqlite3.connect(nama_database)
cursor = conn.cursor()

# Ambil semua nama tabel dalam database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tabels = cursor.fetchall()

print("📋 Daftar Tabel:")
for tabel in tabels:
    nama_tabel = tabel[0]
    print(f"\n📌 Struktur Tabel: {nama_tabel}")

    # Tampilkan struktur tabel (tanpa data)
    cursor.execute(f"PRAGMA table_info({nama_tabel});")
    kolom = cursor.fetchall()

    # Cetak kolom tabel
    print("Kolom | Tipe Data | Not Null | Primary Key")
    print("-------------------------------------------")
    for k in kolom:
        print(f"{k[1]} | {k[2]} | {k[3]} | {k[5]}")

# Tutup koneksi
conn.close()
