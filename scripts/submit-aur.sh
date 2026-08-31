#!/usr/bin/env bash
# Publish eara to AUR (requires AUR account + SSH key in https://aur.archlinux.org).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(PYTHONPATH="$ROOT" python3 -c 'from eara import __version__; print(__version__)')"
TMP="$(mktemp -d)"
TARBALL="eara-${VERSION}.tar.gz"
SHA256="$(curl -fsSL "https://github.com/oneydef/EarA-linux/releases/download/v${VERSION}/${TARBALL}" | sha256sum | awk '{print $1}')"

git clone --depth 1 "ssh://aur@aur.archlinux.org/eara.git" "$TMP/aur" 2>/dev/null || {
  echo "Create empty package first at https://aur.archlinux.org/packages/eara"
  git clone "ssh://aur@aur.archlinux.org/eara.git" "$TMP/aur" || exit 1
}

cp "$ROOT/packaging/arch/PKGBUILD" "$TMP/aur/"
sed -i "s/^pkgver=.*/pkgver=${VERSION}/" "$TMP/aur/PKGBUILD"
sed -i "s/^sha256sums=.*/sha256sums=('${SHA256}')/" "$TMP/aur/PKGBUILD"
(cd "$TMP/aur" && makepkg --printsrcinfo > .SRCINFO)

echo "Review $TMP/aur then:"
echo "  cd $TMP/aur && git add PKGBUILD .SRCINFO && git commit -m 'release ${VERSION}' && git push"
