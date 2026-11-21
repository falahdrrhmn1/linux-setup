#!/usr/bin/env bash
# Kembali ke xfwm4 dan hapus autostart Compiz. Paket compiz tidak dihapus
# (hapus manual dengan apt bila mau). TouchTamer otomatis kembali ke mode biasa.
set -euo pipefail
rm -f "$HOME/.config/autostart/compiz.desktop"
"$HOME/.local/bin/balik-xfwm4" 2>/dev/null || (xfwm4 --replace >/dev/null 2>&1 &)
echo "xfwm4 aktif lagi. Hapus paket: sudo apt remove compiz-core compiz-gnome compiz-plugins compiz-plugins-main compiz-plugins-extra compizconfig-settings-manager"
