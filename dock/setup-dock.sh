#!/usr/bin/env bash
# Dock bawah ala macOS: Plank dengan ikon membesar saat di-hover (zoom 160%).
# Menggantikan panel bawah XFCE (panel-2 disembunyikan, setelannya tidak dihapus).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
L="$HOME/.local/share/dock-launchers"
D="$HOME/.config/plank/dock1/launchers"
S="net.launchpad.plank.dock.settings:/net/launchpad/plank/docks/dock1/"

echo "-- paket plank"
sudo apt-get install -y plank

echo "-- isi dock"
mkdir -p "$L" "$D"
items="'desktop.dockitem'"
printf '[PlankDockItemPreferences]\nLauncher=docklet://desktop\n' > "$D/desktop.dockitem"
for nm in firefox tilix terminal filemanager webbrowser appfinder nemo; do
    sed "s#@HOME@#$HOME#g" "$DIR/launchers/$nm.desktop" > "$L/$nm.desktop"
    printf '[PlankDockItemPreferences]\nLauncher=file://%s\n' "$L/$nm.desktop" > "$D/$nm.dockitem"
    items="$items, '$nm.dockitem'"
done

echo "-- setelan (zoom saat hover, sembunyi otomatis bila tertutup jendela)"
gsettings set $S dock-items "[$items]"
gsettings set $S position 'bottom'
gsettings set $S alignment 'center'
gsettings set $S icon-size 40
gsettings set $S zoom-enabled true
gsettings set $S zoom-percent 160
gsettings set $S hide-mode 'intelligent'
gsettings set $S show-dock-item false
gsettings set $S pinned-only true
gsettings set $S theme 'Transparent'

echo "-- sembunyikan panel bawah XFCE"
xfconf-query -c xfce4-panel -p /panels -t int -s 1 --force-array
xfce4-panel -r || true

echo "-- autostart"
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/plank.desktop" <<A
[Desktop Entry]
Type=Application
Name=Plank (dock ala macOS)
Exec=sh -c "sleep 3; plank"
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
A
pgrep -x plank >/dev/null || (setsid plank >/dev/null 2>&1 < /dev/null &)
echo "Dock aktif. Atur: klik kanan dock sambil tahan Ctrl -> Preferences."
