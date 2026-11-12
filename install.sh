#!/usr/bin/env bash
# Pasang semua fitur linux-setup untuk user yang sedang login.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== linux-setup: memasang semua fitur =="
echo

bash "$DIR/touchpad/install.sh"
echo
bash "$DIR/super-search/install.sh"
echo
bash "$DIR/xfce/setup-xfce.sh"
echo
bash "$DIR/window-titles/setup-window-titles.sh"
echo
bash "$DIR/firefox/setup-firefox.sh"
echo
echo "== Selesai =="
echo "TouchTamer, gestur touchpad, Super search, setelan XFCE, nama jendela, dan pinch-zoom Firefox sudah aktif."
echo "Semua akan otomatis jalan setiap login/restart."
