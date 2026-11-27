#!/bin/sh
# OpenKey for Linux - uninstaller. Your settings in ~/.config/openkey are kept.
set -e
LIBDIR="${OPENKEY_LIBDIR:-$HOME/.local/share/openkey}"
if command -v gsettings >/dev/null; then
    CUR="$(gsettings get org.gnome.desktop.input-sources sources)"
    case "$CUR" in
        *"'openkey'"*)
            NEW="$(echo "$CUR" | sed -e "s/, ('ibus', 'openkey')//" -e "s/('ibus', 'openkey'), //" -e "s/('ibus', 'openkey')//")"
            gsettings set org.gnome.desktop.input-sources sources "$NEW" ;;
    esac
fi
sudo rm -f /usr/share/ibus/component/openkey.xml
rm -rf "$LIBDIR"
ibus write-cache 2>/dev/null || true
ibus restart 2>/dev/null || true
echo "Đã gỡ OpenKey. (Cấu hình còn giữ ở ~/.config/openkey)"
