# Simulasi Perempatan Lalu Lintas SUMO (Indonesia Style)

Proyek ini adalah simulasi lalu lintas perempatan 4 arah menggunakan **SUMO (Simulation of Urban MObility)**. Simulasi ini dikonfigurasi khusus mengikuti standar jalanan di Indonesia dengan sistem lajur kiri dan fitur *slip road*.

## Fitur Utama

- **Lajur Kiri (LHT)**: Mengikuti aturan mengemudi di Indonesia.
- **Slip Road (Belok Kiri Jalan Terus)**: 4 tikungan fisik yang melengkung di setiap sudut perempatan yang memungkinkan kendaraan belok kiri tanpa melewati lampu merah.
- **Lampu Lalu Lintas Dinamis**: Lampu merah hanya mengontrol kendaraan yang berjalan lurus dan belok kanan.
- **Variasi Kendaraan**: Simulasi mencakup campuran kendaraan seperti mobil, motor, bus, dan truk dengan volume lalu lintas yang berubah sesuai waktu (jam sibuk/normal).
- **Struktur Jalan Konsisten**: Lebar jalan utama (3 lajur) yang terbagi menjadi 2 lajur persimpangan dan 1 lajur slip road secara proporsional.

## Struktur File

- `nodes.nod.xml`: Definisi titik koordinat perempatan dan tikungan.
- `edges.edg.xml`: Definisi ruas jalan, jumlah lajur, dan bentuk tikungan (*shape*).
- `connections.con.xml`: Aturan koneksi antar lajur (lurus, kiri, kanan).
- `generate.py`: Script Python utama untuk membangun jaringan (`netconvert`) dan menghasilkan rute kendaraan secara acak namun realistis.
- `config.sumocfg`: File konfigurasi utama untuk menjalankan simulasi di SUMO.

## Cara Menjalankan

### Prasyarat
Pastikan Anda sudah menginstall **SUMO** dan mengatur `SUMO_HOME` di environment variables sistem Anda.

### Eksekusi
Jalankan script generator untuk membangun jaringan dan membuka GUI:

```powershell
python generate.py
```

Setelah **sumo-gui** terbuka:
1. Atur kecepatan simulasi menggunakan slider (opsional).
2. Tekan tombol **Play (>)** untuk memulai simulasi.

## Visualisasi Tikungan
Tikungan slip road didesain dengan atribut `shape` melengkung untuk memberikan visualisasi yang realistis sesuai dengan sketsa geometris perempatan modern.
