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

echo "-- xfwm4: vblank glx (scroll lebih responsif)"
if xfconf-query -c xfwm4 -p /general/vblank_mode >/dev/null 2>&1; then
    xfconf-query -c xfwm4 -p /general/vblank_mode -s glx
else
    xfconf-query -c xfwm4 -p /general/vblank_mode -n -t string -s glx
fi

echo "-- memasang hotkey volume"
set_str /commands/custom/XF86AudioRaiseVolume "pactl set-sink-volume @DEFAULT_SINK@ +5%"
set_str /commands/custom/XF86AudioLowerVolume "pactl set-sink-volume @DEFAULT_SINK@ -5%"
set_str /commands/custom/XF86AudioMute "pactl set-sink-mute @DEFAULT_SINK@ toggle"
set_str /commands/custom/XF86AudioMicMute "pactl set-source-mute @DEFAULT_SOURCE@ toggle"

echo "-- touchpad: tap-to-click + natural scrolling"
if ! cmp -s "$DIR/40-libinput-touchpad.conf" \
        /etc/X11/xorg.conf.d/40-libinput-touchpad.conf 2>/dev/null; then
    sudo mkdir -p /etc/X11/xorg.conf.d
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
        xinput set-prop "$tp_id" \
            "libinput Scrolling Pixel Distance" 36 2>/dev/null || true
    fi
fi

echo "-- terminal: copy-on-select + clipboard manager"
if ! command -v xfce4-clipman >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y xfce4-clipman xclip
fi

rc="$HOME/.config/xfce4/terminal/terminalrc"
mkdir -p "$(dirname "$rc")"
touch "$rc"
if grep -q '^MiscCopyOnSelect=' "$rc"; then
    sed -i 's/^MiscCopyOnSelect=.*/MiscCopyOnSelect=TRUE/' "$rc"
elif grep -q '^\[Configuration\]' "$rc"; then
    sed -i '/^\[Configuration\]/a MiscCopyOnSelect=TRUE' "$rc"
else
    printf '[Configuration]\nMiscCopyOnSelect=TRUE\n' >> "$rc"
fi

if [ -f "$DIR/clipman.desktop" ]; then
    mkdir -p "$HOME/.config/autostart"
    cp "$DIR/clipman.desktop" "$HOME/.config/autostart/clipman.desktop"
fi
if command -v xfce4-clipman >/dev/null 2>&1; then
    if ! pgrep -x xfce4-clipman >/dev/null 2>&1; then
        setsid xfce4-clipman </dev/null >/dev/null 2>&1 &
    fi
fi

echo "-- fn lock: F2/F3 langsung menjadi tombol volume"
if [ -f "$DIR/../system/fnlock.service" ]; then
    sudo cp "$DIR/../system/fnlock.service" /etc/systemd/system/fnlock.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now fnlock.service
fi
