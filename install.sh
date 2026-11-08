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
echo "== Selesai =="
echo "TouchTamer, gestur 3/4 jari, Super search, dan setelan XFCE sudah aktif."
echo "Semua akan otomatis jalan setiap login/restart."
