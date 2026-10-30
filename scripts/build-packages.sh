#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-$(PYTHONPATH="$ROOT" python3 -c 'from eara import __version__; print(__version__)')}"
DIST="$ROOT/dist"
STAGE="$DIST/pkgroot"

clean_python_cache() {
  local target="$1"
  find "$target" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  find "$target" -depth -type d -name __pycache__ -empty -delete
}

rm -rf "$DIST"
mkdir -p "$STAGE/usr/bin" "$STAGE/usr/share/eara" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/metainfo" "$STAGE/usr/share/eara/screenshots" \
         "$STAGE/usr/share/doc/eara" "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/DEBIAN"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
cp -a "$ROOT/eara" "$STAGE/usr/share/eara/"
cp -a "$ROOT/packaging" "$STAGE/usr/share/eara/"
clean_python_cache "$STAGE/usr/share/eara/eara"
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
install -m 0644 "$ROOT/packaging/eara.png" "$STAGE/usr/share/icons/hicolor/256x256/apps/eara.png"
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
tar -C "$ROOT" --exclude dist --exclude .git --exclude '*/__pycache__' --exclude '*.py[co]' \
    -czf "$DIST/eara-${VERSION}.tar.gz" eara packaging tests docs README.md LINEUP.md LICENSE NOTICE TRADEMARKS.md pyproject.toml nfpm.yaml
echo "built $DIST/eara-${VERSION}.tar.gz"

# Portable AppImage. Bundle the Python runtime, PyGObject/DBus modules,
# GTK4/Libadwaita typelibs and their shared-library dependencies so the image
# does not depend on the host having the desktop development stack installed.
APPDIR="$DIST/EarA.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/eara" "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib/python3/dist-packages" \
         "$APPDIR/usr/lib/x86_64-linux-gnu" \
         "$APPDIR/usr/share/applications" "$APPDIR/usr/share/metainfo" \
         "$APPDIR/usr/share/glib-2.0" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/eara" "$APPDIR/usr/share/eara/"
clean_python_cache "$APPDIR/usr/share/eara/eara"
cp "$ROOT/packaging/eara.desktop" "$APPDIR/eara.desktop"
cp "$ROOT/packaging/eara.svg" "$APPDIR/eara.svg"
cp "$ROOT/packaging/eara.png" "$APPDIR/eara.png"
cp "$ROOT/packaging/eara.png" "$APPDIR/.DirIcon"
cp "$ROOT/packaging/eara.desktop" "$APPDIR/usr/share/applications/eara.desktop"
cp "$ROOT/packaging/eara.metainfo.xml" "$APPDIR/usr/share/metainfo/io.github.oneydef.eara.appdata.xml"
cp "$ROOT/packaging/eara.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/eara.svg"
cp "$ROOT/packaging/eara.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/eara.png"
sed -i 's/^Icon=.*/Icon=eara/' "$APPDIR/eara.desktop"

PYTHON_STDLIB="$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')"
GI_PACKAGE="$(python3 -c 'import gi, pathlib; print(pathlib.Path(gi.__file__).parent)')"
DBUS_PACKAGE="$(python3 -c 'import dbus, pathlib; print(pathlib.Path(dbus.__file__).parent)')"
DIST_PACKAGES="$(dirname "$GI_PACKAGE")"

cp -L "$(command -v python3)" "$APPDIR/usr/bin/python3"
cp -a "$PYTHON_STDLIB" "$APPDIR/usr/lib/"
cp -a "$GI_PACKAGE" "$DBUS_PACKAGE" "$APPDIR/usr/lib/python3/dist-packages/"
find "$DIST_PACKAGES" -maxdepth 1 -name '_dbus*.so' -exec cp -a {} "$APPDIR/usr/lib/python3/dist-packages/" \;
cp -a /usr/lib/x86_64-linux-gnu/girepository-1.0 "$APPDIR/usr/lib/x86_64-linux-gnu/"
cp -a /usr/share/glib-2.0/schemas "$APPDIR/usr/share/glib-2.0/"
cat > "$APPDIR/usr/bin/eara" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/../../AppRun" "$@"
EOF
chmod 0755 "$APPDIR/usr/bin/eara"

LINUXDEPLOY_BIN="${LINUXDEPLOY:-$(command -v linuxdeploy || true)}"
if [ -z "$LINUXDEPLOY_BIN" ]; then
  echo "linuxdeploy is required to build the portable AppImage" >&2
  exit 1
fi

GTK_LIB="$(ldconfig -p | awk '$1 == "libgtk-4.so.1" && !found { found=$NF } END { print found }')"
ADW_LIB="$(ldconfig -p | awk '$1 == "libadwaita-1.so.0" && !found { found=$NF } END { print found }')"
GI_LIB="$(ldconfig -p | awk '$1 == "libgirepository-1.0.so.1" && !found { found=$NF } END { print found }')"
cp -L "$GTK_LIB" "$ADW_LIB" "$GI_LIB" "$APPDIR/usr/lib/x86_64-linux-gnu/"

APPIMAGE_EXTRACT_AND_RUN=1 "$LINUXDEPLOY_BIN" \
  --appdir "$APPDIR" \
  --deploy-deps-only "$APPDIR"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="${APPDIR:-$(dirname "$(readlink -f "$0")")}"
if [ "$(basename "$HERE")" = "bin" ] && [ "$(basename "$(dirname "$HERE")")" = "usr" ]; then
  HERE="$(dirname "$(dirname "$HERE")")"
fi
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONHOME="$HERE/usr"
export PYTHONPATH="$HERE/usr/share/eara:$HERE/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
export GI_TYPELIB_PATH="$HERE/usr/lib/x86_64-linux-gnu/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export XDG_DATA_DIRS="$HERE/usr/share${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
if [ "${1:-}" = "" ]; then
  exec "$HERE/usr/bin/python3" -m eara gui
fi
exec "$HERE/usr/bin/python3" -m eara "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

if command -v appimagetool >/dev/null 2>&1; then
  ARCH=x86_64 appimagetool "$APPDIR" "$DIST/EarA-${VERSION}-x86_64.AppImage"
  echo "built AppImage"
else
  tar -C "$DIST" -czf "$DIST/EarA-${VERSION}-AppDir.tar.gz" EarA.AppDir
  echo "appimagetool missing; shipped AppDir tarball"
fi
