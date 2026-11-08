#!/usr/bin/env bash
# Setelan XFCE yang dipakai bersama TouchTamer dan gestur 3/4 jari.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

set_str() {
    local prop="$1" value="$2"
    if xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" >/dev/null 2>&1; then
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -s "$value"
    else
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -n -t string -s "$value"
    fi
}

set_bool() {
    local prop="$1" value="$2"
    if xfconf-query -c xfwm4 -p "$prop" >/dev/null 2>&1; then
        xfconf-query -c xfwm4 -p "$prop" -s "$value"
    else
        xfconf-query -c xfwm4 -p "$prop" -n -t bool -s "$value"
    fi
}

echo "-- mematikan zoom desktop XFCE"
set_bool /general/zoom_desktop false
set_bool /general/zoom_pointer false

echo "-- memasang hotkey volume"
set_str /commands/custom/XF86AudioRaiseVolume "pactl set-sink-volume @DEFAULT_SINK@ +5%"
set_str /commands/custom/XF86AudioLowerVolume "pactl set-sink-volume @DEFAULT_SINK@ -5%"
set_str /commands/custom/XF86AudioMute "pactl set-sink-mute @DEFAULT_SINK@ toggle"
set_str /commands/custom/XF86AudioMicMute "pactl set-source-mute @DEFAULT_SOURCE@ toggle"

echo "-- touchpad: tap-to-click + natural scrolling"
if [ ! -f /etc/X11/xorg.conf.d/40-libinput-touchpad.conf ]; then
    sudo cp "$DIR/40-libinput-touchpad.conf" \
        /etc/X11/xorg.conf.d/40-libinput-touchpad.conf
fi

if command -v xinput >/dev/null 2>&1; then
    tp_id="$(xinput list --short 2>/dev/null | awk '
        /Touchpad/ {
            for (i = 1; i <= NF; i++)
                if ($i ~ /^id=/) { gsub("id=", "", $i); print $i; exit }
        }')"
    if [ -n "$tp_id" ]; then
        xinput set-prop "$tp_id" "libinput Tapping Enabled" 1 2>/dev/null || true
        xinput set-prop "$tp_id" \
            "libinput Natural Scrolling Enabled" 1 2>/dev/null || true
    fi
fi

echo "-- fn lock: F2/F3 langsung menjadi tombol volume"
if [ -f "$DIR/../system/fnlock.service" ]; then
    sudo cp "$DIR/../system/fnlock.service" /etc/systemd/system/fnlock.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now fnlock.service
fi
