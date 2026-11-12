#!/bin/sh
# Riwayat clipboard (Clipman) muncul di dekat kursor mouse, bukan di ikon tray.
eval "$(xdotool getmouselocation --shell | sed -n "s/^X=/MX=/p;s/^Y=/MY=/p")"
SW=$(xdotool getdisplaygeometry | cut -d' ' -f1)
SH=$(xdotool getdisplaygeometry | cut -d' ' -f2)
xfce4-popup-clipman &
i=0
while [ $i -lt 40 ]; do
    i=$((i + 1))
    sleep 0.025
    for id in $(xdotool search --onlyvisible --class xfce4-clipman 2>/dev/null); do
        eval "$(xdotool getwindowgeometry --shell "$id" 2>/dev/null)"
        [ "${WIDTH:-0}" -gt 80 ] && [ "${HEIGHT:-0}" -gt 40 ] || continue
        nx=$MX; ny=$MY
        [ $((nx + WIDTH)) -gt "$SW" ] && nx=$((SW - WIDTH))
        [ $((ny + HEIGHT)) -gt "$SH" ] && ny=$((SH - HEIGHT))
        [ "$nx" -lt 0 ] && nx=0
        [ "$ny" -lt 0 ] && ny=0
        xdotool windowmove "$id" "$nx" "$ny"
        exit 0
    done
done
