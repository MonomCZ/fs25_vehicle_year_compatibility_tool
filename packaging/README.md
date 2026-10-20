# Desktop packaging

These files build **GUI-only** desktop artifacts. The command-line interface is
not included in either package.

- `fs25_vycompat.spec` - one-file, windowed PyInstaller build. It bundles the
  `Icons/` folder and uses `appicon.ico` for the Windows executable.
- `build_appimage.sh` - builds the Linux AppImage with appimagetool.
- `AppRun` and `fs25-vycompat.desktop` - AppImage launcher metadata.

From the repository root:

```bash
python3 -m pip install pyinstaller
python3 packaging/build_appimage.sh
```

The AppImage is written to `dist/`. The Windows executable is built by the
GitHub Actions workflow, because PyInstaller must run on Windows for a native
`.exe`. Both jobs start from a `v*` tag or a manual workflow dispatch.
