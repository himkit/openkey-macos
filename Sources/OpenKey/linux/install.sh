#!/bin/sh
# OpenKey for Linux - installer (IBus input method)
#   ./install.sh            install for the current user (asks sudo once for the IBus component file)
#   ./install.sh --add-source   also add OpenKey to GNOME input sources
set -e
cd "$(dirname "$0")"
VERSION="$(python3 -I src/openkey_ibus.py --version)"
LIBDIR="${OPENKEY_LIBDIR:-$HOME/.local/share/openkey}"
COMPONENT_DIR=/usr/share/ibus/component

if [ ! -f build/libopenkey.so ]; then
    echo ">> building libopenkey.so"
    make
fi
python3 -I -c 'import gi; gi.require_version("IBus", "1.0"); from gi.repository import IBus' 2>/dev/null || {
    echo "!! thiếu thư viện IBus cho Python. Cài: sudo apt install python3-gi gir1.2-ibus-1.0"; exit 1; }

echo ">> installing files to $LIBDIR"
mkdir -p "$LIBDIR"
install -m 755 build/libopenkey.so "$LIBDIR/libopenkey.so"
install -m 644 src/openkey_core.py "$LIBDIR/openkey_core.py"
install -m 755 src/openkey_ibus.py "$LIBDIR/openkey_ibus.py"
install -m 644 data/openkey.svg "$LIBDIR/openkey.svg"

TMP_XML="$(mktemp)"
sed -e "s|@LIBDIR@|$LIBDIR|g" -e "s|@VERSION@|$VERSION|g" data/openkey.xml.in > "$TMP_XML"
echo ">> installing IBus component to $COMPONENT_DIR/openkey.xml (needs sudo)"
sudo install -m 644 "$TMP_XML" "$COMPONENT_DIR/openkey.xml"
rm -f "$TMP_XML"

echo ">> restarting IBus"
ibus write-cache 2>/dev/null || true
ibus restart 2>/dev/null || true

if [ "$1" = "--add-source" ] && command -v gsettings >/dev/null; then
    CUR="$(gsettings get org.gnome.desktop.input-sources sources)"
    case "$CUR" in
        *"'openkey'"*) ;;
        "@a(ss) []"|"[]") gsettings set org.gnome.desktop.input-sources sources "[('xkb', 'us'), ('ibus', 'openkey')]" ;;
        *) gsettings set org.gnome.desktop.input-sources sources "$(echo "$CUR" | sed "s/]\$/, ('ibus', 'openkey')]/")" ;;
    esac
    echo ">> added OpenKey to GNOME input sources"
fi

cat <<MSG

Đã cài OpenKey $VERSION.
- GNOME: Settings > Keyboard > Input Sources > + > Vietnamese > OpenKey
  (hoặc chạy lại: ./install.sh --add-source)
- Đổi bộ gõ: Super+Space. Chuyển Việt/Anh trong OpenKey: Ctrl+Shift.
- Cấu hình: biểu tượng "V" trên thanh trên cùng, hoặc ~/.config/openkey/config.json
MSG
