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
| Tampilkan desktop | 3 jari ke bawah |
| App switcher | 3 jari ke atas (ditahan), geser kanan = berikutnya, kiri = sebelumnya, lepas = pilih |
| Pindah aplikasi | 3 jari ke kiri = berikutnya, ke kanan = sebelumnya |
| Pindah workspace | 4 jari ke kiri = berikutnya, ke kanan = sebelumnya |
| Cari aplikasi | Tap tombol **Super/Windows**, ketik nama, `Enter` |
| Tombol volume | `F2`/`F3`/`Mute` langsung mengatur volume (Fn lock dimatikan) |

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
- **Fn lock**: service `fnlock` (enabled) supaya `F2`/`F3` tetap tombol volume.
- **XFCE**: zoom desktop dimatikan, hotkey volume, natural scrolling.

## Pengaturan

- TouchTamer: `~/.config/touchtamer/TouchTamer.ini`. Setelah diubah, jalankan ulang:
  ```bash
  pkill -f touchtamer.py
  touchtamer
  ```
- Gestur 3/4 jari: `touchpad/src/touchpad-gestures.py` (ambang `START_PX`,
  `H_STEP_PX`, `COOLDOWN`, `COMMIT_DELAY`). Setelah diubah:
  ```bash
  sudo install -m 755 touchpad/src/touchpad-gestures.py /usr/local/bin/touchpad-gestures.py
  sudo systemctl restart touchpad-gestures
  ```
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
└── system/
    └── fnlock.service
```

Lisensi MIT.
