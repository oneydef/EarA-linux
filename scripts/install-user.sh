#!/usr/bin/env bash
# Install EarA for the current user (menu launcher + PATH).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
META="${XDG_DATA_HOME:-$HOME/.local/share}/metainfo"
ICON="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
SHOT="${XDG_DATA_HOME:-$HOME/.local/share}/eara/screenshots"

mkdir -p "$BIN" "$APP" "$META" "$ICON" "$SHOT"

cat > "$BIN/eara" <<EOF
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "$ROOT")
from eara.cli import main
raise SystemExit(main())
EOF
chmod 0755 "$BIN/eara"

install -m 0644 "$ROOT/packaging/eara.svg" "$ICON/eara.svg"
ASSET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/eara/packaging"
FONT_DIR="$ASSET_DIR/fonts"
USER_FONT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/eara"
mkdir -p "$ASSET_DIR" "$FONT_DIR" "$USER_FONT_DIR"
install -m 0644 "$ROOT/packaging/"*.svg "$ASSET_DIR/"
for font in "$ROOT/packaging/fonts/"*.ttf; do
  [ -f "$font" ] || continue
  install -m 0644 "$font" "$FONT_DIR/"
  install -m 0644 "$font" "$USER_FONT_DIR/"
done
fc-cache -f "$USER_FONT_DIR" 2>/dev/null || true

sed "s|^Exec=.*|Exec=$BIN/eara gui|" "$ROOT/packaging/eara.desktop" > "$APP/eara.desktop"
install -m 0644 "$ROOT/packaging/eara.metainfo.xml" "$META/eara.metainfo.xml"
install -m 0644 "$ROOT/packaging/screenshots/"*.png "$SHOT/"

update-desktop-database "$APP" 2>/dev/null || true
gtk-update-icon-cache -f "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo "Installed:"
echo "  $BIN/eara"
echo "  $APP/eara.desktop"
echo "  $META/eara.metainfo.xml"
echo "  $ICON/eara.svg"
echo "Open from the app menu as «Nothing X; Nothing Ears», or run: eara gui"
if ! command -v eara >/dev/null 2>&1; then
  echo "Note: add $BIN to PATH if 'eara' is not found in a new terminal."
fi
