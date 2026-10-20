# Changelog

All notable changes to the FS25 Vehicle Year Compatibility Tool are documented
here. The project uses a `MAJOR.MINOR.PATCH` version.

## 1.3.0 — 2026-10-20

- Added `Icons/MAINicon.png` as the application/window icon, the Windows
  `appicon.ico` source and the default icon for newly created blank addons.
- Added the optional `Icons/ALTicon.png` easter egg: a colourful **AMAZING
  ICON** sidebar button appears on roughly 10% of GUI launches. It can be
  forced with `VYCOMPAT_EASTER_EGG=1` / `--easter-egg` or suppressed with `0` /
  `--no-easter-egg`.
- The icon dialog previews the current and alternate icons, saves an addon
  snapshot, writes `icon.png`, updates `modDesc.xml`'s `<iconFilename>`,
  rebuilds the ZIP and offers an opt-in install into the game mods folder.
  Restoring the main icon follows the same reviewed path.
- Added native Windows discovery for
  `Documents/My Games/FarmingSimulator2025/mods`, OneDrive Documents and Steam
  game folders, while keeping the Linux/Proton paths.
- Added a GUI-only PyInstaller build, AppImage launcher assets and a GitHub
  Actions workflow that builds a windowed Windows EXE on `windows-latest` and
  an x86_64 AppImage on `ubuntu-22.04`.
- Documented the ALT icon's third-party licensing status.
- Test suite expanded to 172 tests.

## 1.2.0 — 2026-10-20

- Added **ADDON SETUP...**, a startup prompt and a pre-scan prompt when the
  mods folder has no compatibility addon.
- Added a reviewed **CREATE BLANK MOD** flow that creates a neutral
  **Vehicle Years Compatibility Tool** scaffold with empty year tables and a
  generated original icon, installs its ZIP, and never overwrites existing
  files.
- The tool now manages the generic `FS25_VehicleYears_CompatibilityTool`
  addon identity and detects both ZIP and unpacked-folder installs.
- Removed the old community-specific addon paths, descriptions and fixtures
  from the app, documentation and tests.
- Add years, Paste years and Addon History now offer setup when the editable
  source is missing instead of only reporting an error. If only an installed
  ZIP or unpacked folder exists, the app offers to extract/copy it into an
  editable source while preserving existing years.
- Addon ZIP builds now keep nested resource files while still excluding hidden
  history folders, `__pycache__` and temp files.
- Added `vycompat_addon.py` with neutral blank-mod templates.
- Supported rows now say **compatibility tool** instead of **addon** in the
  GUI and documentation; the compact Advanced column uses `tool`.

## 1.1.0 — 2026-10-20

- Renamed the application to **FS25 Vehicle Year Compatibility Tool**.
- Renamed the project folder to `fs25_vehicle_year_compatibility_tool/`.
- Renamed the Python modules and console commands to `vycompat` /
  `vycompat-gui`.
- Moved the visual specification to `docs/UI_SPEC.md`.
- Added release metadata, a project layout and a release checklist.
- Renamed the local addon snapshot folder to `.vycompat_history/`.

## 1.0.0

- Initial standalone scanner, Tkinter GUI, addon review/export flow and local
  snapshot/undo support.
