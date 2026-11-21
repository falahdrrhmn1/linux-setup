#!/usr/bin/env bash
# Hapus dock Plank dan tampilkan lagi panel bawah XFCE.
set -euo pipefail
rm -f "$HOME/.config/autostart/plank.desktop"
pkill -x plank || true
xfconf-query -c xfce4-panel -p /panels -t int -s 1 -t int -s 2 --force-array
xfce4-panel -r || true
echo "Panel bawah XFCE aktif lagi. Hapus paket: sudo apt remove plank"
