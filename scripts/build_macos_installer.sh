#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Ce build doit être exécuté sur macOS."
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI_ROOT="$REPO_ROOT/local_ui"
VENV_ROOT="$REPO_ROOT/.venv-build-macos"
VENV_PYTHON="$VENV_ROOT/bin/python"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ARCHITECTURE="$(uname -m)"
SPEC_PATH="$REPO_ROOT/packaging/macos/EndurawTestingTool.spec"
BUILD_ROOT="$REPO_ROOT/build/macos"
APP_PATH="$REPO_ROOT/dist/Enduraw Testing Tool V2.app"
ARTIFACTS_ROOT="$REPO_ROOT/artifacts"
APP_VERSION="$(PYTHONPATH="$REPO_ROOT/src" "$PYTHON_BIN" -c 'from config import APP_VERSION; print(APP_VERSION)')"
DMG_PATH="$ARTIFACTS_ROOT/EndurawTestingTool-macOS-${ARCHITECTURE}-${APP_VERSION}.dmg"

cd "$REPO_ROOT"

echo "[1/7] Build React"
npm --prefix "$UI_ROOT" ci
npm --prefix "$UI_ROOT" run build
test -f "$UI_ROOT/dist/index.html"

echo "[2/7] Environnement Python de build"
if [[ ! -x "$VENV_PYTHON" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_ROOT"
fi
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$REPO_ROOT/requirements.txt"
"$VENV_PYTHON" -c 'import tkinter; assert tkinter.TkVersion >= 8.5'

echo "[3/7] Icône macOS"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/EndurawTestingTool.iconset"
"$VENV_PYTHON" - <<'PY'
from pathlib import Path
from PIL import Image

image = Image.open("icon.ico")
image.seek(getattr(image, "n_frames", 1) - 1)
image.convert("RGBA").save(Path("build/macos/icon-source.png"))
PY
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$BUILD_ROOT/icon-source.png" \
        --out "$BUILD_ROOT/EndurawTestingTool.iconset/icon_${size}x${size}.png" >/dev/null
    double_size=$((size * 2))
    sips -z "$double_size" "$double_size" "$BUILD_ROOT/icon-source.png" \
        --out "$BUILD_ROOT/EndurawTestingTool.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$BUILD_ROOT/EndurawTestingTool.iconset" \
    -o "$BUILD_ROOT/EndurawTestingTool.icns"

echo "[4/7] Bundle PyInstaller"
rm -rf "$REPO_ROOT/build/macos/pyinstaller" "$APP_PATH" "$REPO_ROOT/dist/EndurawTestingTool"
"$VENV_PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --workpath "$REPO_ROOT/build/macos/pyinstaller" \
    --distpath "$REPO_ROOT/dist" \
    "$SPEC_PATH"
test -x "$APP_PATH/Contents/MacOS/EndurawTestingTool"

echo "[5/7] Vérification du bundle et smoke test isolé"
ARCHIVE_CONTENTS="$BUILD_ROOT/archive-contents.txt"
"$VENV_ROOT/bin/pyi-archive_viewer" -b -r \
    "$APP_PATH/Contents/MacOS/EndurawTestingTool" > "$ARCHIVE_CONTENTS"
"$VENV_PYTHON" - "$REPO_ROOT/src" "$ARCHIVE_CONTENTS" <<'PY'
from pathlib import Path
import sys

source_root = Path(sys.argv[1])
archive = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
missing = []
for path in source_root.rglob("*.py"):
    if path.name == "__init__.py":
        continue
    module = ".".join(path.relative_to(source_root).with_suffix("").parts)
    if module not in archive:
        missing.append(module)
if missing:
    raise SystemExit(f"Modules projet absents du bundle: {', '.join(missing)}")
print("Archive vérifiée : tous les modules Python de src sont embarqués.")
PY
codesign --force --deep --sign - "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH"
SMOKE_ROOT="$(mktemp -d)"
trap 'rm -rf "$SMOKE_ROOT"' EXIT
ENDURAW_DATA_DIR="$SMOKE_ROOT/data" ENDURAW_STARTUP_SMOKE_TEST=1 \
    "$APP_PATH/Contents/MacOS/EndurawTestingTool"
test -f "$SMOKE_ROOT/data/data_schema.json"
test ! -e "$SMOKE_ROOT/data/migration.lock"

echo "[6/7] Image disque glisser-déposer"
STAGING_ROOT="$BUILD_ROOT/dmg"
rm -rf "$STAGING_ROOT"
mkdir -p "$STAGING_ROOT" "$ARTIFACTS_ROOT"
ditto "$APP_PATH" "$STAGING_ROOT/Enduraw Testing Tool V2.app"
ln -s /Applications "$STAGING_ROOT/Applications"
cp "$REPO_ROOT/packaging/macos/LISEZ-MOI.txt" "$STAGING_ROOT/LISEZ-MOI.txt"
rm -f "$DMG_PATH"
hdiutil create \
    -volname "Enduraw Testing Tool" \
    -srcfolder "$STAGING_ROOT" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo "[7/7] Vérification de l'image disque"
MOUNT_ROOT="$(mktemp -d)"
hdiutil attach -nobrowse -readonly -mountpoint "$MOUNT_ROOT" "$DMG_PATH" >/dev/null
test -d "$MOUNT_ROOT/Enduraw Testing Tool V2.app"
test -L "$MOUNT_ROOT/Applications"
codesign --verify --deep --strict "$MOUNT_ROOT/Enduraw Testing Tool V2.app"
hdiutil detach "$MOUNT_ROOT" >/dev/null
rmdir "$MOUNT_ROOT"
shasum -a 256 "$DMG_PATH"

echo "Installateur macOS : $DMG_PATH"
