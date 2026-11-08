#!/usr/bin/env bash
# Tap Super to open the application search (like the Windows Start menu).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v xcape >/dev/null 2>&1; then
    echo "-- memasang xcape"
    sudo apt-get update -qq
    sudo apt-get install -y xcape
fi

mkdir -p "$HOME/.local/bin" "$HOME/.config/autostart"
install -m 755 "$DIR/super-search" "$HOME/.local/bin/super-search"
sed "s|@HOME@|$HOME|g" "$DIR/super-search.desktop.in" \
    > "$HOME/.config/autostart/super-search.desktop"
chmod 644 "$HOME/.config/autostart/super-search.desktop"

# XF86Search has no physical key, so binding it does not steal a normal key.
if command -v xfconf-query >/dev/null 2>&1; then
    prop=/commands/custom/XF86Search
    if xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" >/dev/null 2>&1; then
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -s "xfce4-appfinder -c"
    else
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -n -t string \
            -s "xfce4-appfinder -c"
    fi
fi

pkill -x xcape 2>/dev/null || true
setsid "$HOME/.local/bin/super-search" >/dev/null 2>&1 &

if command -v xfce4-appfinder >/dev/null 2>&1; then
    echo "-- Super search siap (tap tombol Super untuk mencari aplikasi)"
else
    echo "-- peringatan: xfce4-appfinder tidak ditemukan"
fi
