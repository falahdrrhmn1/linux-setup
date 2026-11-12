#!/usr/bin/env bash
# Judul jendela di grid alt+tab + ganti nama jendela dengan Alt+F2.
#
# Memasang xfwm4 hasil patch ke /usr/local/bin/xfwm4, jadi paket xfwm4 dari
# apt tetap utuh. Patch menampilkan nama tiap jendela di bawah thumbnail dan
# memprioritaskan _NET_WM_VISIBLE_NAME, sehingga nama buatan sendiri tidak
# ditimpa saat aplikasi memperbarui judulnya sendiri.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="${XDG_CACHE_HOME:-$HOME/.cache}/linux-setup/xfwm4-build"
PATCH="$DIR/xfwm4-4.20-window-titles.patch"

echo "-- dependensi"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    build-essential pkg-config gettext \
    libglib2.0-dev libgtk-3-dev libpango1.0-dev libgdk-pixbuf-2.0-dev \
    libxfce4util-dev libxfce4ui-2-dev libxfconf-0-dev libwnck-3-dev \
    libepoxy-dev libx11-dev libxcomposite-dev libxdamage-dev \
    libxrender-dev libxrandr-dev libxi-dev libxfixes-dev libxext-dev \
    libxres-dev libxpresent-dev libxcursor-dev libdrm-dev \
    libstartup-notification0-dev \
    x11-utils xdotool wmctrl zenity

echo "-- mengambil source xfwm4 4.20"
rm -rf "$BUILD"
mkdir -p "$BUILD"
cd "$BUILD"
src=""
if apt-get source xfwm4 >/dev/null 2>&1; then
    src="$(find . -maxdepth 1 -type d -name 'xfwm4-*' | head -1)"
fi
if [ -z "$src" ] || [ ! -f "$src/src/tabwin.c" ]; then
    echo "   (deb-src tidak tersedia, pakai tarball rilis 4.20.0)"
    curl -fsSL \
        "https://archive.xfce.org/src/xfce/xfwm4/4.20/xfwm4-4.20.0.tar.bz2" \
        -o xfwm4.tar.bz2
    tar xf xfwm4.tar.bz2
    src="xfwm4-4.20.0"
fi
cd "$src"

echo "-- menerapkan patch"
if ! patch -p1 --forward --dry-run < "$PATCH" >/dev/null 2>&1; then
    echo "!! patch tidak cocok dengan source xfwm4 yang didapat." >&2
    echo "   Repo ini diuji pada xfwm4 4.20.0 (Debian 13)." >&2
    exit 1
fi
patch -p1 --forward < "$PATCH"

echo "-- build xfwm4 (beberapa menit)"
./configure --prefix=/usr/local >/dev/null
make -j"$(nproc)" >/dev/null

echo "-- memasang ke /usr/local"
sudo install -Dm755 src/xfwm4 /usr/local/bin/xfwm4
sudo install -Dm644 defaults/defaults /usr/local/share/xfwm4/defaults

echo "-- script rename + shortcut Alt+F2"
install -Dm755 "$DIR/rename-window" "$HOME/.local/bin/rename-window"

set_str() {
    local prop="$1" value="$2"
    if xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" >/dev/null 2>&1; then
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -s "$value"
    else
        xfconf-query -c xfce4-keyboard-shortcuts -p "$prop" -n -t string -s "$value"
    fi
}

set_xfwm4() {
    local prop="$1" type="$2" value="$3"
    if xfconf-query -c xfwm4 -p "$prop" >/dev/null 2>&1; then
        xfconf-query -c xfwm4 -p "$prop" -s "$value"
    else
        xfconf-query -c xfwm4 -p "$prop" -n -t "$type" -s "$value"
    fi
}

if xfconf-query -c xfwm4 -l >/dev/null 2>&1; then
    set_str '/commands/custom/<Alt>F2' "$HOME/.local/bin/rename-window"
    xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/F2' -r \
        2>/dev/null || true
    xfconf-query -c xfce4-keyboard-shortcuts -p '/commands/custom/<F2>' -r \
        2>/dev/null || true
    set_xfwm4 /general/cycle_tabwin_mode int 0
    set_xfwm4 /general/cycle_preview bool true
else
    echo "   (sesi XFCE tidak aktif; shortcut & alt+tab diatur saat login)"
fi

echo "-- fungsi 'nama' di ~/.bashrc"
if ! grep -qF '# >>> linux-setup: nama jendela terminal >>>' \
        "$HOME/.bashrc" 2>/dev/null; then
    cat >> "$HOME/.bashrc" <<'EOF'

# >>> linux-setup: nama jendela terminal >>>
# nama TESIS   -> judul jendela ini "TESIS"
# nama         -> kembali ke judul otomatis
_judul_terminal() {
    printf '\033]0;%s\007' "${WINNAME:-$USER@$HOSTNAME: ${PWD/#$HOME/~}}"
}
nama() {
    if [ $# -gt 0 ]; then WINNAME="$*"; else unset WINNAME; fi
    _judul_terminal
}
PROMPT_COMMAND="_judul_terminal${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
# <<< linux-setup: nama jendela terminal <<<
EOF
fi

# Judul bawaan Debian ditulis PS1 setelah PROMPT_COMMAND, jadi dimatikan.
while IFS=: read -r n _; do
    sed -i "${n}s/^/# linux-setup: /" "$HOME/.bashrc"
done < <(grep -nF 'PS1="\[\e]0;' "$HOME/.bashrc" 2>/dev/null || true)

case "$(command -v xfwm4)" in
    /usr/local/bin/xfwm4) ;;
    *) echo "!! $(command -v xfwm4) muncul lebih dulu di PATH; pastikan" \
            "/usr/local/bin ada di depan PATH saat login." >&2 ;;
esac

if [ -n "${DISPLAY:-}" ]; then
    echo "-- menjalankan ulang xfwm4"
    setsid xfwm4 --replace >/dev/null 2>&1 < /dev/null &
    sleep 2
fi

echo "-- selesai. Alt+F2 = ganti nama jendela (kosongkan = nama asli)."
