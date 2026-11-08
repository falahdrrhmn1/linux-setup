#!/usr/bin/env bash
# Lepas TouchTamer dari user yang sedang menjalankan skrip ini.
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/touchtamer"
CONFIG_DIR="$HOME/.config/touchtamer"
AUTOSTART_DIR="$HOME/.config/autostart"
APPLICATIONS_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
UDEV_RULE="/etc/udev/rules.d/99-touchtamer.rules"

echo "== TouchTamer: melepas =="

pkill -f "$INSTALL_DIR/src/touchtamer.py" 2>/dev/null || true
sleep 1

if [ -f /etc/systemd/system/touchpad-gestures.service ]; then
    sudo systemctl disable --now touchpad-gestures.service >/dev/null 2>&1 || true
    sudo rm -f /etc/systemd/system/touchpad-gestures.service
    sudo rm -f /usr/local/bin/touchpad-gestures.py
    sudo systemctl daemon-reload
fi

rm -rf "$INSTALL_DIR"
rm -f "$AUTOSTART_DIR/touchtamer.desktop"
rm -f "$APPLICATIONS_DIR/touchtamer.desktop"
rm -f "$BIN_DIR/touchtamer"

if [ -f "$UDEV_RULE" ]; then
    sudo rm -f "$UDEV_RULE"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=input || true
fi

echo "== Selesai =="
echo "Program dan autostart sudah dihapus."
echo "Pengaturanmu tetap disimpan di: $CONFIG_DIR"
echo "Kalau ingin menghapusnya juga: rm -rf $CONFIG_DIR"
