#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT"
DIST="$ROOT/dist"
WORK="$ROOT/build/appimage"
PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import tkinter" >/dev/null 2>&1; then
    echo "Tkinter is required to build the GUI (install python3-tk)." >&2
    exit 1
fi

rm -rf "$WORK"
mkdir -p "$WORK/AppDir/usr/bin" \
         "$WORK/AppDir/usr/share/applications" \
         "$WORK/AppDir/usr/share/icons/hicolor/256x256/apps" \
         "$DIST"

"$PYTHON" -m PyInstaller \
    --noconfirm --clean \
    --distpath "$WORK/pyinstaller-dist" \
    --workpath "$WORK/pyinstaller-work" \
    "$ROOT/packaging/fs25_vycompat.spec"

BIN="$WORK/pyinstaller-dist/FS25-Vehicle-Year-Compatibility-Tool"
if [[ ! -x "$BIN" ]]; then
    echo "PyInstaller did not produce the expected binary." >&2
    exit 1
fi

install -m 755 "$BIN" "$WORK/AppDir/usr/bin/fs25-vycompat"
install -m 644 "$APP/Icons/MAINicon.png" \
    "$WORK/AppDir/usr/share/icons/hicolor/256x256/apps/fs25-vycompat.png"
install -m 644 "$ROOT/packaging/fs25-vycompat.desktop" \
    "$WORK/AppDir/usr/share/applications/fs25-vycompat.desktop"
install -m 755 "$ROOT/packaging/AppRun" "$WORK/AppDir/AppRun"

# appimagetool also looks for the desktop file and icon at the AppDir root.
install -m 644 "$ROOT/packaging/fs25-vycompat.desktop" \
    "$WORK/AppDir/fs25-vycompat.desktop"
install -m 644 "$APP/Icons/MAINicon.png" \
    "$WORK/AppDir/fs25-vycompat.png"

TOOL="$WORK/appimagetool-x86_64.AppImage"
if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGETOOL=(appimagetool)
else
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL"
    APPIMAGETOOL=("$TOOL" --appimage-extract-and-run)
fi

VERSION="$("$PYTHON" -c \
    'import sys; sys.path.insert(0, sys.argv[1]); import vycompat; print(vycompat.__version__)' \
    "$APP")"
OUT="$DIST/FS25-Vehicle-Year-Compatibility-Tool-$VERSION-x86_64.AppImage"
rm -f "$OUT"

ARCH=x86_64 "${APPIMAGETOOL[@]}" "$WORK/AppDir" "$OUT"
chmod +x "$OUT"
echo "Built $OUT"
