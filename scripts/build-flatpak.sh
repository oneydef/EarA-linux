#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/flatpak/io.github.oneydef.eara.yml"
BUILD_DIR="$ROOT/dist/flatpak-build"
REPO_DIR="$ROOT/dist/flatpak-repo"
LOCAL_MANIFEST="$ROOT/dist/flatpak-local.yml"
RUNTIME="${FLATPAK_RUNTIME:-org.gnome.Platform//49}"
SDK="${FLATPAK_SDK:-org.gnome.Sdk//49}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing $1. Install: sudo apt install flatpak flatpak-builder" >&2
    exit 1
  }
}

need flatpak
need flatpak-builder

flatpak --user remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak --user install -y flathub "$RUNTIME" "$SDK" 2>/dev/null || flatpak install -y flathub "$RUNTIME" "$SDK"

python3 - "$MANIFEST" "$LOCAL_MANIFEST" "$ROOT" <<'PY'
import sys
from pathlib import Path

src, dst, root = sys.argv[1:4]
text = Path(src).read_text()
block = f"""    sources:
      - type: dir
        path: {root}
"""
# Replace git source block in eara module only (last module).
marker = "  - name: eara\n"
idx = text.rfind(marker)
if idx < 0:
    raise SystemExit("eara module not found in manifest")
tail = text[idx:]
sources_idx = tail.find("    sources:")
if sources_idx < 0:
    raise SystemExit("sources block not found")
end = tail.find("\n\n", sources_idx)
if end < 0:
    end = len(tail)
new_tail = tail[:sources_idx] + block + tail[end:]
Path(dst).write_text(text[:idx] + new_tail)
print(f"Wrote {dst}")
PY

rm -rf "$BUILD_DIR" "$REPO_DIR"
flatpak-builder --user --install --force-clean --repo="$REPO_DIR" "$BUILD_DIR" "$LOCAL_MANIFEST"

echo ""
echo "Installed: io.github.oneydef.eara"
echo "Run:       flatpak run io.github.oneydef.eara"
