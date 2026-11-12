# linux-setup

Kumpulan setelan Linux (Debian 13 + XFCE/X11) supaya laptop langsung nyaman dipakai:
gestur touchpad, kontrol brightness/volume, pindah jendela, pencarian aplikasi ala
Windows, dan tombol volume.

Diuji di Lenovo IdeaPad 82HS, Debian 13 (trixie), XFCE 4.20, touchpad multitouch
5 jari (MSFT0001:00 04F3:3140).

## Fitur

| Fitur | Cara pakai |
|---|---|
| Brightness | Tahan `Ctrl`+`Shift`, geser 2 jari di **sisi kiri** (atas naik, bawah turun) |
| Volume | Tahan `Ctrl`+`Shift`, geser 2 jari di **sisi kanan** |
| Pindah jendela | 5 jari, geser ke arah mana saja |
| Ukuran jendela | `Alt`+`Atas` / `Alt`+`Bawah` |
| Lebar jendela | `Alt`+`Kanan` / `Alt`+`Kiri` |
| Tampilkan desktop | 3 jari ke bawah: minimize semua jendela di workspace ini saja (workspace lain tidak ikut); ulangi = pulihkan |
| App switcher | 3 jari ke atas: switcher tetap terbuka; geser 3 jari kanan/kiri = pilih, `Enter`/`Space` = buka, `Esc` atau klik = tutup (otomatis tutup setelah 5 menit). Jendela yang diminimize ikut tampil di daftar |
| Pindah aplikasi | 3 jari ke kiri = berikutnya, ke kanan = sebelumnya (terus geser = lanjut ke aplikasi berikutnya) |
| Pindah workspace | 4 jari ke kiri = berikutnya, ke kanan = sebelumnya |
| Zoom (pinch) | 2 jari melebar/merapat. Di Firefox = zoom visual (level zoom tidak berubah); di aplikasi lain = `Ctrl`+scroll |
| Screenshot | `Ctrl`+`Shift`+`S` atau `PrtSc`: drag area, lepas, langsung masuk clipboard (tanpa tombol OK) |
| Riwayat clipboard | `Super`+`V` (teks dan gambar) |
| Back / Forward browser | Flick 2 jari cepat ke kanan = Back, ke kiri = Forward (hanya di jendela browser). Dimatikan selama halaman sedang di-zoom, supaya geser/panning tidak salah terbaca |
| Cari aplikasi | Tap tombol **Super/Windows**, ketik nama, `Enter` |
| Tombol volume | `F2`/`F3`/`Mute` langsung mengatur volume (Fn lock dimatikan) |
| Copy/paste terminal | **Shift+drag** untuk menyeleksi, `Ctrl`+`Shift`+`C` copy, `Ctrl`+`Shift`+`V` paste |

## Copy/paste di terminal

- Aplikasi TUI seperti opencode menangkap mouse. Tahan **Shift** saat drag untuk
  menyeleksi teks.
- Copy: `Ctrl`+`Shift`+`C` (bukan `Ctrl`+`C`). Paste: `Ctrl`+`Shift`+`V` atau klik tengah.
- `xfce4-clipman` otomatis jalan supaya clipboard tersimpan walau terminal ditutup.
- Terminal baru: seleksi langsung otomatis copy (`MiscCopyOnSelect=TRUE`).

## Syarat

- Sesi **X11** (XFCE). Wayland belum didukung.
- Touchpad multitouch minimal 5 jari untuk pindah jendela.
- Debian/Ubuntu dengan `apt`. Paket yang dipasang otomatis bila belum ada:
  `python3-evdev`, `python3-xlib`, `python3-gi`, `xdotool`, `xinput`,
  `pulseaudio-utils`, `acl`, `libinput-tools`, `wmctrl`, `x11-utils`, `xcape`.

## Instalasi

```bash
git clone https://github.com/falahdrrhmn1/linux-setup.git
cd linux-setup
./install.sh
```

Setelah selesai, semua fitur langsung aktif dan otomatis jalan setiap login/restart.

## Yang dipasang

- **TouchTamer**: program di `~/.local/share/touchtamer`, autostart
  `~/.config/autostart/touchtamer.desktop`, entri menu, dan perintah `touchtamer`.
- **Gestur 3/4 jari**: `/usr/local/bin/touchpad-gestures.py` + service systemd
  `touchpad-gestures` (enabled).
- **Izin touchpad**: `/etc/udev/rules.d/99-touchtamer.rules`.
- **Super search**: `~/.local/bin/super-search` + autostart, memakai `xcape` dan
  shortcut `XF86Search`.
- **Touchpad**: `/etc/X11/xorg.conf.d/40-libinput-touchpad.conf`
  (tap-to-click, klik kanan 2 jari, natural scrolling).
- **Firefox**: `MOZ_USE_XINPUT2=1` di semua cara membuka Firefox (menu, ikon Desktop,
  tombol "Web Browser" di panel, link dari aplikasi lain, dan `~/.xsessionrc` untuk
  semua program setelah login ulang) + pref `apz.allow_zooming` dan
  `apz.gtk.touchpad_pinch.enabled` di setiap profil. Tanpa variabel itu Firefox di X11
  tidak menerima pinch.
- **Fn lock**: service `fnlock` (enabled) supaya `F2`/`F3` tetap tombol volume.
- **XFCE**: zoom desktop dimatikan, hotkey volume, natural scrolling, kecepatan scroll
  touchpad (`ScrollPixelDistance`), dan `vblank_mode=glx` di xfwm4 (scroll lebih responsif).

## Pengaturan

- TouchTamer: `~/.config/touchtamer/TouchTamer.ini`. Setelah diubah, jalankan ulang:
  ```bash
  pkill -f touchtamer.py
  touchtamer
  ```
- Gestur 3/4 jari, pinch, dan flick Back/Forward: `touchpad/src/touchpad-gestures.py`
  (ambang `START_PX`, `H_STEP_PX`, `COOLDOWN`, `COMMIT_DELAY`, `FIVE_HOLD`, `PINCH_STEP`,
  `NAV_DIST`, `NAV_TIME`, `ZOOM_LOCK`, `NAV_FINGER_RIGHT_IS_BACK`). Setelah diubah:
  ```bash
  sudo install -m 755 touchpad/src/touchpad-gestures.py /usr/local/bin/touchpad-gestures.py
  sudo systemctl restart touchpad-gestures
  ```
- Kecepatan scroll touchpad: `Option "ScrollPixelDistance"` di
  `/etc/X11/xorg.conf.d/40-libinput-touchpad.conf` (lebih besar = lebih lambat);
  coba langsung: `xinput set-prop <id> "libinput Scrolling Pixel Distance" 36`.
- Log:
  ```bash
  tail -f ~/.cache/touchtamer/TouchTamer.log     # set debug=1 dulu
  cat ~/.cache/touchtamer/touchtamer.err
  journalctl -u touchpad-gestures -f
  ```

## Menghapus

```bash
./uninstall.sh
```

Setelan XFCE (zoom, hotkey volume, xorg touchpad) sengaja dibiarkan.

## Troubleshooting

| Masalah | Cek |
|---|---|
| Gestur tidak jalan | Pastikan sesi X11: `echo $XDG_SESSION_TYPE` |
| 3/4/5 jari diam | `systemctl status touchpad-gestures`, lalu `libinput debug-events` |
| Brightness tidak berubah | Hanya layar bawaan; cek `/sys/class/backlight/` |
| Volume tidak berubah | `pactl get-sink-volume @DEFAULT_SINK@` |
| Layar ikut nge-zoom | `xfconf-query -c xfwm4 -p /general/zoom_desktop -s false` |
| Super tidak membuka pencarian | `pgrep -x xcape`; cek `xfconf-query -c xfce4-keyboard-shortcuts -p /commands/custom/XF86Search` |
| Pinch Firefox tidak zoom | Cek proses punya variabelnya: `tr '\0' '\n' < /proc/$(pgrep -x firefox-esr \| head -1)/environ \| grep XINPUT2`. Tutup **semua** jendela Firefox lalu buka lagi. Jalankan `./firefox/setup-firefox.sh` ulang bila perlu |
| Flick Back/Forward tidak jalan | `journalctl -u touchpad-gestures -f`, lalu flick: log menjelaskan alasannya (`too-slow`, `not-straight`, `page is zoomed`). Pastikan jendela aktif browser |
| TouchTamer diam setelah error | Baca `~/.cache/touchtamer/touchtamer.err` |

## Struktur repo

```
linux-setup/
├── install.sh                 # pasang semua
├── uninstall.sh               # lepas semua
├── touchpad/                  # TouchTamer + gestur 3/4 jari
│   ├── install.sh
│   ├── uninstall.sh
│   ├── bin/TouchTamer.ini
│   └── src/
│       ├── gesture.py
│       ├── touchtamer.py
│       └── touchpad-gestures.py
├── super-search/              # tap Super -> cari aplikasi
│   ├── install.sh
│   ├── super-search
│   └── super-search.desktop.in
├── xfce/
│   ├── 40-libinput-touchpad.conf
│   └── setup-xfce.sh
├── firefox/                   # pinch-to-zoom Firefox di X11 (XInput2 + pref APZ)
│   ├── setup-firefox.sh
│   └── uninstall.sh
└── system/
    └── fnlock.service
```

Lisensi MIT.
