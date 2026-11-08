# TouchTamer untuk Linux

Gestur touchpad untuk Linux (X11/XFCE): atur brightness dan volume dengan menggeser
dua jari, pindahkan jendela dengan lima jari, dan ubah ukuran/lebar jendela dengan
`Alt`+panah.

Ini adalah versi Linux dari [TouchTamer untuk Windows](https://github.com/falahdrrhmn1/TouchTamer).

| Yang ingin dilakukan | Caranya |
|---|---|
| Mengatur **brightness** | Tahan `Ctrl`+`Shift`, geser naik/turun dengan **2 jari** di **sisi kiri** touchpad |
| Mengatur **volume** | Tahan `Ctrl`+`Shift`, geser naik/turun dengan **2 jari** di **sisi kanan** touchpad |
| **Memindahkan jendela** | Arahkan kursor ke jendela, lalu geser dengan **5 jari** |
| **Menampilkan desktop** | Geser **3 jari ke bawah** |
| **App switcher** | Geser **3 jari ke atas** (tahan untuk melihat, lepas untuk memilih) |
| **Pindah aplikasi** | Geser **3 jari ke kiri** (berikutnya) atau **ke kanan** (sebelumnya) |
| **Pindah workspace** | Geser **4 jari ke kiri** (berikutnya) atau **ke kanan** (sebelumnya) |
| Mengubah **ukuran jendela** | `Alt`+`Atas` dan `Alt`+`Bawah` |
| Mengubah **lebar jendela** | `Alt`+`Kanan` dan `Alt`+`Kiri` |

## Syarat

- Linux dengan sesi **X11** (XFCE, Xfce). Wayland belum didukung.
- Touchpad yang mendukung **multi-touch** (minimal 2 jari; 5 jari untuk memindah jendela).
- Paket: `python3-evdev`, `python3-xlib`, `python3-gi`, `xdotool`, `xinput`,
  `pulseaudio-utils` (atau PipeWire dengan `pactl`), `acl`, `libinput-tools`,
  `wmctrl`, `x11-utils`.

Installer akan memasang paket yang belum ada.

## Memasang

```bash
cd TouchTamer-linux
./install.sh
```

Installer akan:

- Memasang paket yang dibutuhkan.
- Menyalin program ke `~/.local/share/touchtamer`.
- Membuat pengaturan awal di `~/.config/touchtamer/TouchTamer.ini` (tidak menimpa
  pengaturan lama).
- Membuat aturan udev `/etc/udev/rules.d/99-touchtamer.rules` supaya user bisa
  membaca touchpad.
- Menambahkan autostart (`~/.config/autostart/touchtamer.desktop`) dan entri menu
  aplikasi.
- Menjalankan TouchTamer sekarang.

Setelah itu TouchTamer otomatis berjalan setiap login, tanpa perlu setting ulang.

Menjalankan manual: menu aplikasi → **TouchTamer**, atau perintah `touchtamer`.

## Memakai

### Brightness dan volume

1. Tahan `Ctrl`+`Shift` (bukan `Ctrl`+`Alt`) dan terus tahan selama menggeser.
2. Tempelkan 2 jari:
   - **Sisi kiri** untuk brightness.
   - **Sisi kanan** untuk volume.
3. Geser **ke atas untuk menambah** atau **ke bawah untuk mengurangi**.

Sisi ditentukan saat geseran dimulai. Selama gestur, scroll touchpad dimatikan
sementara supaya halaman di belakang tidak ikut bergulir/zoom.

### Memindahkan jendela

1. Arahkan kursor ke jendela yang ingin dipindah.
2. Tempelkan **5 jari**, lalu geser ke arah mana saja.
3. Angkat jari untuk selesai.

Jendela fullscreen dan panel desktop diabaikan. Untuk memindah jauh, angkat jari,
tempelkan lagi, dan lanjutkan.

### Gestur 3 dan 4 jari

| Gestur | Efek |
|---|---|
| 3 jari ke bawah | Tampilkan/sembunyikan desktop |
| 3 jari ke atas | Buka app switcher dan **tahan**; geser ke kanan (berikutnya) / kiri (sebelumnya) untuk memilih, lepas untuk pindah. Setelah lepas masih terbuka ±0,6 detik, tempel lagi untuk lanjut memilih |
| 3 jari ke kiri / kanan | Pindah ke aplikasi berikutnya / sebelumnya |
| 4 jari ke bawah | Tampilkan/sembunyikan desktop |
| 4 jari ke atas | Buka app switcher |
| 4 jari ke kiri / kanan | Pindah ke workspace berikutnya / sebelumnya |

Gestur 3/4 jari dijalankan oleh service `touchpad-gestures` yang dipasang installer
dan otomatis aktif saat login. Lima jari khusus untuk memindahkan jendela.

### Ukuran dan lebar jendela

| Tombol | Efek |
|---|---|
| `Alt`+`Atas` | Memperbesar (95% → 90% → 75% → 40% → maximize, lalu kembali ke 40%) |
| `Alt`+`Bawah` | Memperkecil (berhenti di 40%) |
| `Alt`+`Kanan` | Melebarkan 40 piksel |
| `Alt`+`Kiri` | Menyempitkan 40 piksel (minimal 300 piksel) |

`Alt`+`Kiri`/`Kanan` mengambil alih Back/Forward di browser selama TouchTamer
berjalan. Matikan dengan `width_hotkeys=0`.

## Mengubah pengaturan

Edit `~/.config/touchtamer/TouchTamer.ini`, lalu jalankan ulang TouchTamer.

| Pengaturan | Bawaan | Fungsi |
|---|---|---|
| `level_gesture` | `1` | Gestur brightness/volume. `0` mematikan |
| `gesture_mod` | `ctrl+shift` | Tombol yang ditahan: `ctrl`, `alt`, `shift`, atau gabungan |
| `full_height_pct` | `60` | Perubahan persen untuk geseran setinggi touchpad |
| `move_gesture` | `1` | Pindah jendela dengan 5 jari |
| `move_speed_pct` | `150` | Kecepatan jendela. Makin besar makin cepat |
| `size_hotkeys` | `1` | `Alt`+`Atas`/`Bawah` |
| `width_hotkeys` | `1` | `Alt`+`Kanan`/`Kiri` |
| `suppress_scroll` | `1` | Matikan scroll saat gestur berjalan |
| `hide_after_ms` | `850` | Lama panel terlihat (ms) |
| `alpha` | `245` | Kepekatan panel (40–255) |
| `debug` | `0` | `1` menulis log ke `~/.cache/touchtamer/TouchTamer.log` |

## Menghentikan / menjalankan ulang

```bash
pkill -f touchtamer.py      # berhenti
touchtamer                  # jalan lagi
```

## Menghapus

```bash
cd TouchTamer-linux
./uninstall.sh
```

Pengaturan di `~/.config/touchtamer` sengaja disimpan.

## Kalau ada masalah

| Masalah | Coba ini |
|---|---|
| Gestur tidak jalan | Pastikan sesi X11, dan TouchTamer berjalan: `pgrep -af touchtamer.py` |
| Volume tidak berubah | Cek `pactl get-sink-volume @DEFAULT_SINK@`; pastikan tidak mute |
| Brightness tidak berubah | Hanya layar bawaan laptop. Cek `/sys/class/backlight/` |
| Lima jari tidak bereaksi | Touchpad harus membaca 5 jari; tempelkan kelima jari dulu sebelum menggeser |
| `Alt`+panah tidak jalan | Pastikan `size_hotkeys`/`width_hotkeys` = 1 dan tidak ada aplikasi lain yang memegang tombol itu |
| Panel tidak muncul | Pastikan sesi punya compositor (XFCE: Settings → Window Manager Tweaks → Compositor) |
| Ingin log | Set `debug=1`, jalankan ulang, baca `~/.cache/touchtamer/TouchTamer.log` |

## Lisensi

MIT, sama seperti versi Windows.
