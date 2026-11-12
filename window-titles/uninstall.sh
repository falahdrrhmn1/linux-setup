#!/usr/bin/env bash
# Lepas xfwm4 hasil patch dan fungsi rename jendela.
# Paket xfwm4 dari apt tidak pernah diubah, jadi cukup login ulang.
set -euo pipefail

echo "-- melepas xfwm4 hasil patch"
sudo rm -f /usr/local/bin/xfwm4
sudo rm -rf /usr/local/share/xfwm4
rm -f "$HOME/.local/bin/rename-window"

if command -v xfconf-query >/dev/null 2>&1; then
    xfconf-query -c xfce4-keyboard-shortcuts \
        -p '/commands/custom/<Alt>F2' -r 2>/dev/null || true
fi

if grep -qF '# >>> linux-setup: nama jendela terminal >>>' \
        "$HOME/.bashrc" 2>/dev/null; then
    sed -i '/# >>> linux-setup: nama jendela terminal >>>/,/# <<< linux-setup: nama jendela terminal <<</d' \
        "$HOME/.bashrc"
fi

echo "-- selesai. Login ulang untuk kembali memakai xfwm4 dari apt."
