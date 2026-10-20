# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file, windowed build for the GUI-only application."""

from pathlib import Path

app_dir = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(app_dir / "vycompat_gui.py")],
    pathex=[str(app_dir)],
    binaries=[],
    datas=[(str(app_dir / "Icons"), "Icons")],
    hiddenimports=[
        "vycompat",
        "vycompat_addon",
        "vycompat_gui",
        "vycompat_history",
        "vycompat_icons",
        "vycompat_theme",
        "vycompat_tutorial",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FS25-Vehicle-Year-Compatibility-Tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_dir / "Icons" / "appicon.ico"),
)
