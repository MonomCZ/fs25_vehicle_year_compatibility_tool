# Changelog

All notable changes to the FS25 Vehicle Year Compatibility Tool are documented
here. The project uses a `MAJOR.MINOR.PATCH` version.

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
