#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-$(PYTHONPATH="$ROOT" python3 -c 'from eara import __version__; print(__version__)')}"
DIST="$ROOT/dist"
STAGE="$DIST/pkgroot"
rm -rf "$DIST"
mkdir -p "$STAGE/usr/bin" "$STAGE/usr/share/eara" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/metainfo" "$STAGE/usr/share/eara/screenshots" \
         "$STAGE/usr/share/doc/eara" "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/DEBIAN"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cp -a "$ROOT/eara" "$STAGE/usr/share/eara/"
cp -a "$ROOT/packaging" "$STAGE/usr/share/eara/"
install -m 0755 "$ROOT/packaging/eara" "$STAGE/usr/bin/eara"
# launcher uses installed package path
cat > "$STAGE/usr/bin/eara" <<'EOF'
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "/usr/share/eara")
from eara.cli import main
raise SystemExit(main())
EOF
chmod 0755 "$STAGE/usr/bin/eara"
install -m 0644 "$ROOT/packaging/eara.desktop" "$STAGE/usr/share/applications/eara.desktop"
install -m 0644 "$ROOT/packaging/eara.metainfo.xml" "$STAGE/usr/share/metainfo/eara.metainfo.xml"
install -m 0644 "$ROOT/packaging/screenshots/"*.png "$STAGE/usr/share/eara/screenshots/"
install -m 0644 "$ROOT/packaging/eara.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/eara.svg"
cp "$ROOT/README.md" "$ROOT/LINEUP.md" "$ROOT/LICENSE" "$ROOT/NOTICE" "$STAGE/usr/share/doc/eara/" 2>/dev/null || true

cat > "$STAGE/DEBIAN/control" <<EOF
Package: eara
Version: ${VERSION}
Section: sound
Priority: optional
Architecture: all
Maintainer: oneydef <oneydefwork@gmail.com>
Depends: python3 (>= 3.10), python3-gi, python3-dbus, gir1.2-gtk-4.0, gir1.2-adw-1, bluez, pulseaudio-utils | pipewire-bin
Description: Unofficial Linux companion for compatible True Wireless earbuds
 Controls ANC, EQ, gestures, battery and Bluetooth audio for compatible
 earbuds over a community RFCOMM protocol. Independent of the hardware vendor.
EOF

DEB="$DIST/eara_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"
echo "built $DEB"

# source tarball
tar -C "$ROOT" --exclude dist --exclude .git --exclude '*.pyc' \
    -czf "$DIST/eara-${VERSION}.tar.gz" eara packaging tests docs README.md LINEUP.md LICENSE NOTICE TRADEMARKS.md pyproject.toml nfpm.yaml
echo "built $DIST/eara-${VERSION}.tar.gz"

# thin AppImage (uses host python3 + GTK)
APPDIR="$DIST/EarA.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/eara" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications"
cp -a "$ROOT/eara" "$APPDIR/usr/share/eara/"
cp "$ROOT/packaging/eara.desktop" "$APPDIR/eara.desktop"
cp "$ROOT/packaging/eara.svg" "$APPDIR/eara.svg"
sed -i 's/^Icon=.*/Icon=eara/' "$APPDIR/eara.desktop"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$HERE/usr/share/eara${PYTHONPATH:+:$PYTHONPATH}"
if [ "${1:-}" = "" ]; then
  exec python3 -m eara gui
fi
exec python3 -m eara "$@"
EOF
chmod 0755 "$APPDIR/AppRun"
ln -sf eara.desktop "$APPDIR/usr/share/applications/eara.desktop"

if command -v appimagetool >/dev/null 2>&1; then
          ARCH=x86_64 appimagetool --no-appstream "$APPDIR" "$DIST/EarA-${VERSION}-x86_64.AppImage"
  echo "built AppImage"
else
  tar -C "$DIST" -czf "$DIST/EarA-${VERSION}-AppDir.tar.gz" EarA.AppDir
  echo "appimagetool missing; shipped AppDir tarball"
fi
