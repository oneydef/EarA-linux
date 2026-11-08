#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/flatpak/io.github.oneydef.eara.yml"
BUILD_DIR="$ROOT/dist/flatpak-build"
REPO_DIR="$ROOT/dist/flatpak-repo"
LOCAL_MANIFEST="$ROOT/dist/flatpak-local.yml"
SOURCE_DIR="$ROOT/dist/flatpak-source"
INSTALL=1
OFFLINE=0
for arg in "$@"; do
  case "$arg" in
    --no-install) INSTALL=0 ;;
    --offline) OFFLINE=1 ;;
    *) echo "Usage: $0 [--no-install] [--offline]" >&2; exit 2 ;;
  esac
done
RUNTIME_VERSION="$(sed -n 's/^runtime-version: "\([^"]*\)"/\1/p' "$MANIFEST")"
test -n "$RUNTIME_VERSION"
RUNTIME="org.gnome.Platform//$RUNTIME_VERSION"
SDK="org.gnome.Sdk//$RUNTIME_VERSION"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing $1. Install: sudo apt install flatpak flatpak-builder" >&2
    exit 1
  }
}

need flatpak
need flatpak-builder

if (( ! OFFLINE )); then
  flatpak --user remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
  flatpak --user install -y flathub "$RUNTIME" "$SDK"
fi
mkdir -p "$ROOT/dist"

python3 - "$MANIFEST" "$LOCAL_MANIFEST" "$ROOT" "$SOURCE_DIR" <<'PY'
import json
import shutil
import sys
from pathlib import Path

src, dst, root, source = sys.argv[1:5]
snapshot = Path(source)
if snapshot.exists():
    shutil.rmtree(snapshot)
snapshot.mkdir()
# Only package inputs: never recursively copy dist, git state or other projects.
for name in ('eara', 'packaging', 'flatpak'):
    shutil.copytree(Path(root) / name, snapshot / name,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'root'))
for name in ('LICENSE', 'meson.build'):
    shutil.copy2(Path(root) / name, snapshot / name)
text = Path(src).read_text()
block = f"""    sources:
      - type: dir
        path: {json.dumps(source)}
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

options=(--user --force-clean --state-dir="$ROOT/.flatpak-builder" --repo="$REPO_DIR")
if (( INSTALL )); then options+=(--install); fi
if (( OFFLINE )); then options+=(--disable-download); fi
flatpak-builder "${options[@]}" "$BUILD_DIR" "$LOCAL_MANIFEST"

echo ""
if (( INSTALL )); then
  echo "Installed: io.github.oneydef.eara"
  echo "Run:       flatpak run io.github.oneydef.eara"
else
  echo "Built without installation: $BUILD_DIR"
fi
