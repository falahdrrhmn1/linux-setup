#!/usr/bin/env bash
# Lepas semua fitur linux-setup dari user yang sedang login.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== linux-setup: melepas =="

pkill -x xcape 2>/dev/null || true
rm -f "$HOME/.config/autostart/super-search.desktop"
rm -f "$HOME/.local/bin/super-search"

if command -v xfconf-query >/dev/null 2>&1; then
    xfconf-query -c xfce4-keyboard-shortcuts \
        -p /commands/custom/XF86Search -r 2>/dev/null || true
fi

if [ -f /etc/systemd/system/fnlock.service ]; then
    sudo systemctl disable --now fnlock.service >/dev/null 2>&1 || true
    sudo rm -f /etc/systemd/system/fnlock.service
    sudo systemctl daemon-reload
fi

bash "$DIR/touchpad/uninstall.sh"

echo "== Selesai =="
echo "Pengaturan XFCE (zoom, hotkey volume, xorg touchpad) dibiarkan."
