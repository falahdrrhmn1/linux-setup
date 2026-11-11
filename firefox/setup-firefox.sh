#!/usr/bin/env bash
# Firefox di X11: aktifkan pinch-to-zoom touchpad (zoom visual, bukan level zoom).
#
# Firefox hanya menerima gestur pinch dari X11 bila dijalankan dengan
# MOZ_USE_XINPUT2=1 (bug 1980781 / 1438107). Skrip ini memastikan variabel itu
# ikut di SEMUA cara membuka Firefox (menu, ikon Desktop, tombol "Web Browser"
# di panel, link dari aplikasi lain, dan semua program setelah login ulang),
# lalu menyalakan pref APZ di setiap profil. Aman dijalankan berulang.
set -euo pipefail

VAR="MOZ_USE_XINPUT2=1"

# Cari desktop-id Firefox (ESR atau biasa).
ID=""
for cand in firefox-esr.desktop firefox.desktop; do
    if [ -f "/usr/share/applications/$cand" ]; then ID="$cand"; break; fi
done
if [ -z "$ID" ]; then
    echo "-- Firefox tidak ditemukan, lewati"
    exit 0
fi
BIN="$(command -v "${ID%.desktop}" || true)"
[ -n "$BIN" ] || BIN="${ID%.desktop}"
BIN="$(readlink -f "$BIN")"

patch_exec() {
    # Tambahkan "env MOZ_USE_XINPUT2=1" di depan setiap baris Exec=.
    local f="$1"
    if ! grep -q "env $VAR" "$f"; then
        sed -i "s|^Exec=|Exec=env $VAR |" "$f"
    fi
}

echo "-- Firefox: pinch-to-zoom ($ID)"

# 1. Menu aplikasi / link dari aplikasi lain: override launcher di level user.
mkdir -p "$HOME/.local/share/applications"
cp "/usr/share/applications/$ID" "$HOME/.local/share/applications/$ID"
patch_exec "$HOME/.local/share/applications/$ID"

# 2. Ikon di Desktop (salinan launcher yang punya Exec sendiri).
if [ -f "$HOME/Desktop/$ID" ]; then
    patch_exec "$HOME/Desktop/$ID"
fi

# 3. Tombol "Web Browser" di panel XFCE (exo-open --launch WebBrowser).
if command -v exo-open >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/share/xfce4/helpers" "$HOME/.config/xfce4"
    cat > "$HOME/.local/share/xfce4/helpers/firefox-xi2.desktop" <<EOF
[Desktop Entry]
NoDisplay=true
Version=1.0
Encoding=UTF-8
Type=X-XFCE-Helper
X-XFCE-Category=WebBrowser
X-XFCE-Binaries=$(basename "$BIN");
X-XFCE-Commands=env $VAR $BIN;
X-XFCE-CommandsWithParameter=env $VAR $BIN "%s";
Icon=${ID%.desktop}
Name=Firefox (XInput2)
EOF
    # Dialog "Preferred Applications" XFCE membuat helper sendiri dari launcher
    # dan menulis "X-XFCE-Commands=env" saja, sehingga tombol panel tidak
    # membuka apa-apa. Betulkan kalau ada.
    HELPER="$HOME/.local/share/xfce4/helpers/${ID}"
    if [ -f "$HELPER" ]; then
        sed -i "s|^X-XFCE-Commands=env\$|X-XFCE-Commands=env $VAR $BIN;|" "$HELPER"
    fi
    touch "$HOME/.config/xfce4/helpers.rc"
    if grep -q '^WebBrowser=' "$HOME/.config/xfce4/helpers.rc"; then
        current="$(sed -n 's/^WebBrowser=//p' "$HOME/.config/xfce4/helpers.rc")"
        # Kalau sudah firefox-esr/firefox hasil dialog, helper-nya sudah dibetulkan di atas.
        case "$current" in
            firefox-xi2|"${ID%.desktop}") ;;
            *) sed -i 's/^WebBrowser=.*/WebBrowser=firefox-xi2/' "$HOME/.config/xfce4/helpers.rc" ;;
        esac
    else
        echo "WebBrowser=firefox-xi2" >> "$HOME/.config/xfce4/helpers.rc"
    fi
fi

# 4. Browser default untuk link dari aplikasi lain (xdg-open).
if command -v xdg-settings >/dev/null 2>&1; then
    xdg-settings set default-web-browser "$ID" 2>/dev/null || true
fi

# 5. Semua program di sesi login berikutnya (termasuk Firefox dari terminal).
touch "$HOME/.xsessionrc"
if ! grep -q "export MOZ_USE_XINPUT2=1" "$HOME/.xsessionrc"; then
    {
        echo
        echo "# Firefox: pinch-to-zoom touchpad di X11 (XInput2)"
        echo "export MOZ_USE_XINPUT2=1"
    } >> "$HOME/.xsessionrc"
fi

# 6. Pref APZ di setiap profil Firefox.
add_pref() {
    local file="$1" name="$2"
    grep -q "\"$name\"" "$file" 2>/dev/null || \
        echo "user_pref(\"$name\", true);" >> "$file"
}
INI="$HOME/.mozilla/firefox/profiles.ini"
if [ -f "$INI" ]; then
    while IFS= read -r rel; do
        case "$rel" in /*) dir="$rel" ;; *) dir="$HOME/.mozilla/firefox/$rel" ;; esac
        [ -d "$dir" ] || continue
        add_pref "$dir/user.js" apz.allow_zooming
        add_pref "$dir/user.js" apz.gtk.touchpad_pinch.enabled
    done < <(sed -n 's/^Path=//p' "$INI")
fi

echo "   selesai. Tutup SEMUA jendela Firefox lalu buka lagi supaya berlaku."
