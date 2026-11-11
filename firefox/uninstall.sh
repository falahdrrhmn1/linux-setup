#!/usr/bin/env bash
# Lepas penyesuaian Firefox dari linux-setup (untuk user yang sedang login).
set -euo pipefail

echo "-- Firefox: melepas penyesuaian pinch-to-zoom"

for id in firefox-esr.desktop firefox.desktop; do
    rm -f "$HOME/.local/share/applications/$id"
    if [ -f "$HOME/Desktop/$id" ]; then
        sed -i 's|^Exec=env MOZ_USE_XINPUT2=1 |Exec=|' "$HOME/Desktop/$id"
    fi
done

rm -f "$HOME/.local/share/xfce4/helpers/firefox-xi2.desktop"
if [ -f "$HOME/.config/xfce4/helpers.rc" ]; then
    sed -i '/^WebBrowser=firefox-xi2$/d' "$HOME/.config/xfce4/helpers.rc"
fi

if [ -f "$HOME/.xsessionrc" ]; then
    sed -i '/# Firefox: pinch-to-zoom touchpad di X11/d;/export MOZ_USE_XINPUT2=1/d' \
        "$HOME/.xsessionrc"
fi

INI="$HOME/.mozilla/firefox/profiles.ini"
if [ -f "$INI" ]; then
    while IFS= read -r rel; do
        case "$rel" in /*) dir="$rel" ;; *) dir="$HOME/.mozilla/firefox/$rel" ;; esac
        [ -f "$dir/user.js" ] || continue
        sed -i '/apz.allow_zooming/d;/apz.gtk.touchpad_pinch.enabled/d' "$dir/user.js"
    done < <(sed -n 's/^Path=//p' "$INI")
fi

echo "   selesai."
