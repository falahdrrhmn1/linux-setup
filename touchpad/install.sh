#!/usr/bin/env bash
# Pasang TouchTamer untuk Linux pada user yang sedang menjalankan skrip ini.
set -euo pipefail

APP="TouchTamer"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/touchtamer"
CONFIG_DIR="$HOME/.config/touchtamer"
CONFIG_FILE="$CONFIG_DIR/TouchTamer.ini"
AUTOSTART_DIR="$HOME/.config/autostart"
APPLICATIONS_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
CACHE_DIR="$HOME/.cache/touchtamer"
UDEV_RULE="/etc/udev/rules.d/99-touchtamer.rules"
USER_NAME="$(id -un)"

echo "== TouchTamer: memasang untuk user $USER_NAME =="

# ---------------------------------------------------------------- dependencies
missing=()
for cmd in python3 xdotool xinput pactl busctl xprop wmctrl libinput; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
command -v setfacl >/dev/null 2>&1 || missing+=("acl")

packages=()
case " ${missing[*]} " in
    *" xdotool "*) packages+=("xdotool") ;;
esac
case " ${missing[*]} " in
    *" xinput "*) packages+=("xinput") ;;
esac
case " ${missing[*]} " in
    *" pactl "*) packages+=("pulseaudio-utils") ;;
esac
case " ${missing[*]} " in
    *" acl "*) packages+=("acl") ;;
esac
case " ${missing[*]} " in
    *" xprop "*) packages+=("x11-utils") ;;
esac
case " ${missing[*]} " in
    *" wmctrl "*) packages+=("wmctrl") ;;
esac
case " ${missing[*]} " in
    *" libinput "*) packages+=("libinput-tools") ;;
esac

if ! python3 -c 'import evdev, Xlib, gi' >/dev/null 2>&1; then
    packages+=("python3-evdev" "python3-xlib" "python3-gi")
fi

if [ ${#packages[@]} -gt 0 ]; then
    echo "-- memasang paket: ${packages[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${packages[@]}"
fi

# ---------------------------------------------------------------- program files
echo "-- menyalin program ke $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/src" "$CONFIG_DIR" "$AUTOSTART_DIR" "$APPLICATIONS_DIR" "$BIN_DIR"
cp "$SRC_DIR/src/gesture.py" "$INSTALL_DIR/src/gesture.py"
cp "$SRC_DIR/src/touchtamer.py" "$INSTALL_DIR/src/touchtamer.py"
chmod +x "$INSTALL_DIR/src/touchtamer.py"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "-- membuat pengaturan awal di $CONFIG_FILE"
    cp "$SRC_DIR/bin/TouchTamer.ini" "$CONFIG_FILE"
fi

# ---------------------------------------------------------------- udev permission
TP_NAME="$(awk -F'"' 'tolower($0) ~ /touchpad/ {print $2; exit}' /proc/bus/input/devices || true)"
if [ -z "$TP_NAME" ]; then
    TP_NAME="*Touchpad*"
fi
echo "-- touchpad terdeteksi: $TP_NAME"

TMP_RULE="$(mktemp)"
cat > "$TMP_RULE" <<EOF
# TouchTamer: izinkan user yang dipasang membaca touchpad (multitouch)
ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="$TP_NAME", RUN+="/usr/bin/setfacl -m u:$USER_NAME:rw /dev/%k", TAG+="uaccess"
EOF
sudo cp "$TMP_RULE" "$UDEV_RULE"
rm -f "$TMP_RULE"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input
sleep 1

# ---------------------------------------------------------------- 3/4-finger service
echo "-- memasang service gesture 3/4 jari"
sudo install -m 755 "$SRC_DIR/src/touchpad-gestures.py" /usr/local/bin/touchpad-gestures.py

UNIT_TMP="$(mktemp)"
cat > "$UNIT_TMP" <<EOF
[Unit]
Description=Multi-finger touchpad gestures (3/4 fingers, XFCE/X11)
After=graphical.target
StartLimitIntervalSec=0

[Service]
User=$USER_NAME
SupplementaryGroups=input
Environment=DISPLAY=:0
Environment=XAUTHORITY=$HOME/.Xauthority
ExecStart=/usr/bin/python3 /usr/local/bin/touchpad-gestures.py
Restart=always
RestartSec=2

[Install]
WantedBy=graphical.target
EOF
sudo cp "$UNIT_TMP" /etc/systemd/system/touchpad-gestures.service
rm -f "$UNIT_TMP"
sudo systemctl daemon-reload
sudo systemctl enable touchpad-gestures.service >/dev/null 2>&1 || true
sudo systemctl restart touchpad-gestures.service

# ---------------------------------------------------------------- launchers
EXEC_LINE="/usr/bin/python3 $INSTALL_DIR/src/touchtamer.py"

cat > "$AUTOSTART_DIR/touchtamer.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TouchTamer
Comment=Touchpad gestures for brightness, volume and windows
Exec=$EXEC_LINE
Icon=input-touchpad
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

cat > "$APPLICATIONS_DIR/touchtamer.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TouchTamer
Comment=Touchpad gestures for brightness, volume and windows
Exec=$EXEC_LINE
Icon=input-touchpad
Terminal=false
Categories=Utility;
StartupNotify=false
EOF

cat > "$BIN_DIR/touchtamer" <<EOF
#!/bin/sh
exec /usr/bin/python3 "$INSTALL_DIR/src/touchtamer.py" "\$@"
EOF
chmod +x "$BIN_DIR/touchtamer"

# ---------------------------------------------------------------- start now
pkill -f "$INSTALL_DIR/src/touchtamer.py" 2>/dev/null || true
sleep 1
mkdir -p "$CACHE_DIR"
echo "-- menjalankan TouchTamer sekarang"
setsid /usr/bin/python3 "$INSTALL_DIR/src/touchtamer.py" \
    >>"$CACHE_DIR/touchtamer.err" 2>&1 &

echo
echo "== Selesai =="
echo "TouchTamer akan otomatis jalan setiap kamu login."
echo "Mulai manual: menu aplikasi -> TouchTamer, atau perintah: touchtamer"
echo "Pengaturan: $CONFIG_FILE (jalankan ulang setelah mengubah)"
echo "Hapus: jalankan ./uninstall.sh"
