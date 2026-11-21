#!/usr/bin/env bash
# Compiz: jendela jelly (wobbly) saat digeser + animasi Magic Lamp saat minimize,
# dengan tombol bulat macOS (WhiteSur). Menggantikan xfwm4 saat login.
# Kalau Compiz crash/dihapus, xfwm4 otomatis dipakai lagi.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "-- paket compiz"
sudo apt-get install -y --no-install-recommends \
    compiz-core compiz-gnome compiz-plugins compiz-plugins-main \
    compiz-plugins-extra compizconfig-settings-manager python3-compizconfig git

echo "-- tema tombol WhiteSur (format metacity untuk dekorator compiz)"
T="$HOME/.themes/WhiteSur-Dark/metacity-1"
if [ ! -f "$T/metacity-theme-1.xml" ]; then
    SRC="$(mktemp -d)"
    git clone -q --depth 1 --filter=blob:none --sparse \
        https://github.com/vinceliuice/WhiteSur-gtk-theme "$SRC"
    git -C "$SRC" sparse-checkout set src/main/metacity-1 src/assets/metacity-1
    mkdir -p "$T/titlebuttons"
    cp "$SRC"/src/assets/metacity-1/titlebuttons-Dark/* "$T/titlebuttons/"
    cp "$SRC/src/main/metacity-1/metacity-theme-Dark.xml" "$T/metacity-theme-1.xml"
    cp "$SRC/src/main/metacity-1/metacity-theme-Dark.xml" "$T/metacity-theme-2.xml"
    rm -rf -- "$SRC"
fi

echo "-- setelan compiz"
CFG="$HOME/.config/compiz/compizconfig"
mkdir -p "$CFG"
[ -f "$CFG/Default.ini" ] && cp "$CFG/Default.ini" "$CFG/Default.ini.bak"
cp "$DIR/Default.ini" "$CFG/Default.ini"
printf '[general]\nprofile = \nintegration = true\n' > "$CFG/config"

echo "-- skrip + autostart"
mkdir -p "$HOME/.local/bin" "$HOME/.config/autostart"
install -m 755 "$DIR/bin/compiz-coba" "$DIR/bin/balik-xfwm4" "$HOME/.local/bin/"
cat > "$HOME/.config/autostart/compiz.desktop" <<D
[Desktop Entry]
Type=Application
Name=Compiz (wobbly + magic lamp)
Comment=Ganti xfwm4 dengan Compiz saat login; hapus file ini untuk kembali ke xfwm4
Exec=sh -c "sleep 2; $HOME/.local/bin/compiz-coba"
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
D

echo "-- jalankan sekarang"
"$HOME/.local/bin/compiz-coba"
echo "Compiz aktif. Kembali ke xfwm4 sementara: balik-xfwm4 | permanen: compiz/uninstall.sh"
