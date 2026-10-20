# AGENTS.md — FS25 Vehicle Year Compatibility Tool

This folder contains the **FS25 Vehicle Year Compatibility Tool**, the standalone
CLI and Tkinter GUI that scans FS25 mods for vehicles/implements without a
production year. It also contains the reviewed compatibility-addon editor,
blank-addon setup flow and local undo/history support. The short command name
is `vycompat`.

The surrounding repository is the FS25 Vehicle Years project. The repository
root [`AGENTS.md`](../AGENTS.md) keeps the safety rules; the older full
repository guide is archived at
[`archive/AGENTS_2026-10-20.md`](../archive/AGENTS_2026-10-20.md). Read this file
for work inside `fs25_vehicle_year_compatibility_tool/`.

## Quick start

```bash
cd fs25_vehicle_year_compatibility_tool

python3 vycompat.py                          # game mods folder
python3 vycompat.py --dir ../newmods         # any folder of mods
python3 vycompat.py --base-game              # also base game vehicles
python3 vycompat.py --dir ../newmods --addon source
python3 vycompat_gui.py                      # GUI; or: python3 vycompat.py --gui

python3 -m unittest discover -s tests -v
```

The app is Python 3.9+ and **standard library only**. The GUI additionally needs
Tkinter (`python3-tk` on Debian/Ubuntu). No package installation is required
for normal use; `pip install -e .` only provides the `vycompat` / `vycompat-gui`
console scripts.

## Safety and boundaries

- **The game's `mods` folder is READ-ONLY for agents.** Reading, listing and
  unzipping is allowed. Do not write, move, edit or delete anything there
  without explicit permission for that exact change. Tell the user to install a
  rebuilt compatibility-addon ZIP unless they ask you to do it. The app itself
  may create/install the blank addon or export years only after the user
  confirms it.
- **Back up the app at the start of every turn** from the repository root:

  ```bash
  mkdir -p backups
  zip -qr "backups/fs25_compat_pre_<task>_$(date +%Y%m%d_%H%M%S).zip" \
    fs25_vehicle_year_compatibility_tool AGENTS.md \
    -x 'fs25_vehicle_year_compatibility_tool/__pycache__/*' \
       'fs25_vehicle_year_compatibility_tool/tests/__pycache__/*'
  ```

  Never overwrite an existing backup. Add other changed files to the archive
  when needed.
- **Do not touch `~/Documents/FS25VehicleYearsModSupportApp`.** That separate
  desktop application is out of scope.
- **Never write before confirmation in the app.** The year editor must use the
  read-only plan/review path first. Snapshot the addon source before an export
  or restore. CLI output files are opt-in only.
- **Do not overwrite a vehicle's year at runtime.** The addon only fills gaps:
  a mod's own `<year>` and the Vehicle Years database take precedence.
- **Do not install test output anywhere.** Tests must use temporary directories
  and mocked install targets, never the real game mods folder.

## Module map

| File | Responsibility |
|---|---|
| `vycompat.py` | Scanner core, source/ZIP readers, year detection, resolution, CLI, prompt/parser helpers, addon setup/planning/export. |
| `vycompat_gui.py` | Tkinter application: library, filters, search, details, background scan, setup prompt, year dialogs, review dialog, history dialog, icon dialog and actions. |
| `vycompat_addon.py` | Neutral `modDesc.xml` and Lua templates for the blank **Vehicle Years Compatibility Tool** addon. |
| `vycompat_history.py` | Timestamped addon source snapshots, history listing, restore-and-rebuild. |
| `vycompat_icons.py` | Bundled main/ALT icon lookup, icon-state detection and the 10% easter-egg gate. |
| `vycompat_theme.py` | FS25-inspired palette, fonts, ttk styles, cards, dialog helpers. Styling only. |
| `vycompat_tutorial.py` | Six-step non-modal in-app tutorial (`F1` / **HELP**). |
| `Icons/` | `MAINicon.png` (app/default mod icon), `ALTicon.png` (easter egg), `appicon.ico` (Windows) and provenance notes. |
| `packaging/` | GUI-only PyInstaller spec, AppImage `AppRun`/desktop assets and local build script. |
| `.github/workflows/build-desktop.yml` | Builds the windowed Windows EXE and x86_64 Linux AppImage in CI. |
| `docs/UI_SPEC.md` | Visual/UX specification used by the theme and UI. |
| `CHANGELOG.md` | Release history and version notes. |
| `MANIFEST.in` | Extra files included in the source archive. |
| `tests/test_vycompat.py` | Scanner, normalization, prompt/parser, CLI and default-path tests. |
| `tests/test_export.py` | Blank-addon scaffold, setup detection, editing, planning, versioning, export/ZIP/install and icon-swap tests. |
| `tests/test_history.py` | Snapshot, manifest, list and restore/undo tests. |
| `tests/test_icons.py` | Bundled icon assets, icon-state detection and easter-egg gating tests. |
| `tests/test_vycompat_gui.py` | GUI data helpers, search, dialogs, easter-egg button and app-flow tests. |
| `tests/test_theme.py` | Theme and helper tests. |
| `tests/test_tutorial.py` | Tutorial content, window and responsiveness tests. |

`pyproject.toml` registers the seven packaged modules in `py-modules`; add any
new top-level module there. `Icons` is also registered as a package so its PNG,
ICO and README assets are installed with the wheel.

The desktop packages are GUI-only. Do not add the CLI entry point to the
PyInstaller spec or the AppImage launcher.

## Scan and detection model

A store item is supported when one of these is found:

1. the mod's own `<storeData><year>YEAR</year>`,
2. the addon source/installed ZIP:
   - `MOD_VEHICLE_YEARS[customEnvironment .. "/" .. rawXMLFilename without .xml]`
   - `MOD_YEARS[customEnvironment]`
   - `BASE_GAME_YEARS[base_data_vehicles_brand_model_model]`
3. the Vehicle Years database `FS25_Vehicle_Years.zip` / extracted data files.

Resolution order is mod year, addon per-vehicle, addon whole-mod, addon base
game, then the Vehicle Years database. The addon and database are read directly
from ZIPs or source paths without extracting the scanned mods.

Useful normalizers in `vycompat.py`:

- `clean_rel()` strips `./`, normalizes separators and removes a `.xml` suffix.
- `norm_rel()` also strips leading `$data/` or `data/`.
- `mod_vy_key()` builds `environment_path_without_xml`.
- `base_key()` builds `base_data_vehicles_brand_model_model`.

Scanner rules:

- FS25 mods use `descVersion >= 90`. FS22/older mods are skipped unless
  `--include-non-fs25` is passed.
- Pallets (`pallets` category), `showInStore=false` items and store items
  without vehicle/handTool data are not vehicles and are ignored/counted
  separately.
- Mod-defined vehicle types are valid; do not treat them as bad categories.
  `<category>` can contain several space-separated categories.
- Years are integers `1900`–`2030`.

## Addon setup, editing and history

The generic addon identity is **Vehicle Years Compatibility Tool**:

- installed ZIP: `FS25_VehicleYears_CompatibilityTool.zip`
- unpacked mod folder: `FS25_VehicleYears_CompatibilityTool/`
- editable source: `FS25_VehicleYears_CompatibilityTool/vehicle_years_addon.lua`

The source is looked up next to the app, in the current folder and in
`~/Documents/`. A packaged install can point at another folder with
`VYCOMPAT_ADDON_DIR`. The app detects both ZIP and unpacked-folder installs.

### Missing addon setup

`VycompatApp` checks the detected game mods folder shortly after startup and
`start_scan()` checks the selected folder plus the game mods folder before
scanning. When no addon is installed it opens `AddonSetupDialog`:

- **CREATE BLANK MOD** calls `scaffold_addon()` to write a neutral
  `vycompat_addon.BLANK_MODDESC` / `BLANK_LUA` source, build the ZIP and install
  it. It refuses any existing source folder, ZIP or install target.
- **INSTALL EXISTING** calls `install_addon_source()` when source exists but the
  installed ZIP is missing. It reuses existing years.
- **EXTRACT SOURCE** calls `extract_addon_zip()` or `copy_addon_source()` when
  the addon is installed but no editable source exists. It preserves existing
  years and never overwrites a source folder.
- **NOT NOW** writes nothing and scans read-only. The prompt is remembered for
  that folder until **ADDON SETUP...** is used.

`ensure_addon_source()` runs before Add years, Paste years and Addon History.
It creates the blank source if nothing exists, or offers extraction when only
an installed ZIP/folder exists.

The blank scaffold has empty `MOD_VEHICLE_YEARS`, `MOD_YEARS` and
`BASE_GAME_YEARS` tables, the full runtime wrapper and a generated original
256x256 `icon.png`. It contains no community-specific mod list, author data or
pre-filled years.

### Add years / Paste years

The GUI exposes one reviewed write path:

1. **Plan** — `vycompat.plan_addon_years()` computes edited Lua/modDesc text and
   entry actions (`added`, `updated`, `unchanged`) without touching disk.
2. **Review** — `ChangesDialog` shows every entry, old/new version, source and
   ZIP paths, install target and skipped paste lines. Cancel writes nothing.
3. **Snapshot** — `vycompat_history.snapshot_addon()` archives the current
   source in `FS25_VehicleYears_CompatibilityTool/.vycompat_history/`.
4. **Write** — `vycompat.export_addon_years()` updates
   `vehicle_years_addon.lua` and `modDesc.xml`, bumps `<version>`, appends
   description lines, rebuilds the ZIP and optionally copies it to the game
   mods folder.
5. **Rescan** — the GUI rescans so the mod shows its new support immediately.

One year for the whole mod goes to `MOD_YEARS`; per-vehicle years go to
`MOD_VEHICLE_YEARS`. Paste output without `/` is treated as a whole-mod key;
keys with `/` are per-vehicle. `?` and `unknown` lines are skipped.

`plan_addon_years()` is the single source of truth for the preview. If you
change the Lua/description/version behavior, update both the plan and export
paths and add tests. Existing addon years are only replaced after the user sees
the amber **changed** row and confirms.

### Snapshots and undo

`vycompat_history.py` owns the `.vycompat_history/` folder:

- `snapshot_addon(source_dir, reason)` builds a timestamped ZIP plus a JSON
  manifest.
- `list_addon_snapshots(source_dir)` returns valid snapshots newest first;
  malformed manifests are ignored.
- `restore_addon_snapshot(source_dir, snapshot_path, install_dir=None)` first
  snapshots the current state, restores the top-level source files, rebuilds the
  ZIP, and installs only when `install_dir` is explicitly supplied.

The history dialog is **ADDON HISTORY...** in the sidebar. Restore install is
off by default. Snapshots are not packaged in the addon ZIP; `build_addon_zip()`
packs top-level files and ignores hidden files/directories and `.tmp` files.

### Runtime addon behavior

The addon is loaded after Vehicle Years and wraps the lazy `year` /
`handtool_year` spec getters. It also hooks `StoreManager.addItem` and keeps an
`onFinishedLoading` backup pass. It never overwrites an existing
`storeItem.specs.year`; per-vehicle keys win over whole-mod keys.

## GUI map

The app starts in **simple** mode: vehicle mods by title, problems first,
support shown as *mod itself / Vehicle Years / addon*. **Advanced** reveals ZIP
names, environments, descVersions, keys, hidden non-vehicle/FS22 mods and export
buttons.

Key UI pieces:

- **Library filters**: All mods, Needs years, Supported, Hidden (Advanced).
- **SEARCH** / `Ctrl+F`: filters by title, ZIP, vehicle, brand, category and
  addon key; multiple words are ANDed. `Esc` or **CLEAR** clears it.
- **F5**: rescan. **F1 / HELP**: tutorial.
- **ADDON SETUP...**: create a blank mod, install an existing source, or explain
  the missing addon. The same prompt runs before a scan when needed.
- **Add years...**: reviewed compatibility-addon editor.
- **Copy years...**: ChatGPT prompt plus one `KEY = ?` line per unresolved
  item. **Paste years...** parses the answer, previews and applies it.
- **ADDON HISTORY...**: restore a snapshot and rebuild the ZIP.
- **Advanced exports**: JSON, append to `years_info.txt`, copy Lua suggestions,
  copy unsupported ZIPs.

The scan runs in a background thread; use `notify()` for short confirmations and
`show_error()` for failures. Year dialogs validate inline. Keep additions
consistent with the charcoal/green theme and the existing card/dense-table
layout.

### Responsive UI rules

- Do not tie the tutorial to fixed screen positions or fixed window sizes, and
  do not use screenshot-based layout tests.
- Prefer normal `Toplevel` dialogs with reflowing labels, scrollable bodies and
  footer buttons that stay visible when Hyprland tiles or resizes the window.
- Avoid modal grabs for the tutorial; it must stay available while the user
  works in the main window.
- New dialogs should have horizontal/vertical scrolling where tables can
  overflow and should remain usable at narrow widths.

## Tests

Run from `fs25_vehicle_year_compatibility_tool/`:

```bash
python3 -m unittest discover -s tests -v
```

The suite currently has **172 tests**. It creates synthetic mod ZIPs and
blank/addon sources in temporary folders and does not need the game installed.
GUI/theme/tutorial tests skip when no display is available. Keep icon tests on
the checked-in assets and keep the game mods folder untouched; patch
`vycompat.default_mods_dir()`/`vycompat.SOURCE_ADDON_LUA` for flows that would
otherwise touch real game data.

When changing behavior:

- Add or update focused tests in the matching test module.
- Keep tests away from the real game `mods` folder; patch
  `vycompat.SOURCE_ADDON_LUA` / `vycompat.default_mods_dir()` or pass temp paths.
- Keep the test count in this file and `README.md` in sync.
- Run the full suite before reporting completion.

Useful checks:

```bash
python3 -m py_compile vycompat.py vycompat_gui.py vycompat_history.py
python3 vycompat.py --dir ../newmods --addon source --no-fail
python3 -c "import vycompat_addon; print(vycompat_addon.BLANK_LUA)" > /tmp/vycompat_blank.lua
lua -e "assert(loadfile('/tmp/vycompat_blank.lua'))"
```

## Conventions

- Keep the scanner and GUI **stdlib-only**; do not add third-party runtime
  dependencies.
- Prefer small pure helpers in `vycompat.py` or at the top of `vycompat_gui.py` so
  they can be tested without a display.
- Preserve existing public helpers and return shapes unless all callers and
  tests are updated.
- Use `Path`, UTF-8 with `errors="ignore"` where existing code does, and atomic
  writes for source files.
- Keep ZIP and path handling safe: no traversal, no extraction of scanned mods,
  and hidden history folders excluded from packaging.
- Update `README.md` and `docs/UI_SPEC.md` when user-facing behavior changes.
- Keep `__version__` in `vycompat.py`, `version` in `pyproject.toml` and the
  top entry in `CHANGELOG.md` in sync.
- Never silently install, delete or overwrite user files.

## Common tasks

| Task | Command / action |
|---|---|
| Scan the game mods folder | `python3 vycompat.py` |
| Scan downloaded mods | `python3 vycompat.py --dir ../newmods` |
| Use local addon source instead of installed ZIP | add `--addon source` |
| Create or install the compatibility addon | GUI **ADDON SETUP...** or scan prompt |
| Check base game vehicles | add `--base-game` |
| Show missing addon entries | add `--lua-suggest` |
| Read-only JSON report | `python3 vycompat.py --json /tmp/report.json` |
| Open GUI | `python3 vycompat_gui.py` |
| Run tests | `python3 -m unittest discover -s tests -v` |
| Add a module | add it to `py-modules` in `pyproject.toml` |
| Rebuild addon after a GUI export | done by **Write & rebuild**; install is opt-in |

## Gotchas

- The installed addon ZIP can be older than the source. Use `--addon source`
  when checking local edits.
- The setup prompt only appears when no installed ZIP/folder or editable source
  exists. Declining it records that scan folder for the session; use
  **ADDON SETUP...** to open it again.
- `scaffold_addon()` is the only blank-addon writer. It never overwrites an
  existing source folder, build ZIP or installed ZIP.
- `plan_addon_years()` is pure; `export_addon_years()` recomputes the plan and
  performs the writes. Do not write from the preview path.
- `.vycompat_history/` is intentionally excluded from the addon ZIP. Do not
  include it when packaging manually.
- Addon description updates append lines; they do not deduplicate existing
  entries. Keep new description lines unique.
- `FS25` mods with descVersion below 90 are skipped; pass
  `--include-non-fs25` only when investigating old mods.
- Maps, productions, pallets and hidden store items are not vehicles. Do not
  flag them as missing years.
- Some mods register custom vehicle types; validate store categories with the
  full token list rather than assuming only vanilla categories.
- Do not rely on `g_storeManager:getItems()` being complete during
  `onFinishedLoading`; Vehicle Years and the addon use lazy spec getters for a
  reason.
- The game must be restarted or the save reloaded after installing a rebuilt
  addon.

## Related docs

- Root safety rules: [`../AGENTS.md`](../AGENTS.md)
- Archived repository-wide guide: [`../archive/AGENTS_2026-10-20.md`](../archive/AGENTS_2026-10-20.md)
- User guide and CLI options: [`README.md`](README.md)
- UI specification: [`docs/UI_SPEC.md`](docs/UI_SPEC.md)
- Release history: [`CHANGELOG.md`](CHANGELOG.md)
- Blank addon templates: [`vycompat_addon.py`](vycompat_addon.py)
