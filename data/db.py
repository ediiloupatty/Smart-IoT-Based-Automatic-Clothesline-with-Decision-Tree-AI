import sqlite3

nama_database = "sensor_data.db"

conn = sqlite3.connect(nama_database)
cursor = conn.cursor()

print(f"Nama Database: {nama_database}")
print("Struktur Tabel:")

try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tabels = cursor.fetchall()

    if not tabels:
        print("  (Tidak ada tabel dalam database)")
    else:
        for tabel in tabels:
            nama_tabel = tabel[0]
            print(f"\nTabel: {nama_tabel}")
            cursor.execute(f"PRAGMA table_info({nama_tabel});")
            koloms = cursor.fetchall()
            print(" Kolom:")
            print("  ID | Nama Kolom | Tipe | NotNull | Default | PK")
            for kolom in koloms:
                # kolom = (cid, name, type, notnull, dflt_value, pk)
                print(f"  {kolom[0]}  | {kolom[1]} | {kolom[2]} |   {kolom[3]}    | {kolom[4]} |  {kolom[5]}")

except sqlite3.Error as e:
    print("Terjadi kesalahan:", e)

conn.close()
