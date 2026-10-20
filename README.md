# FS25 Vehicle Year Compatibility Tool

A standalone CLI and Tkinter GUI that scans Farming Simulator 25 mods, reports
**which vehicles/implements still have no year support**, and can create and
maintain a compatible **Vehicle Years Compatibility Tool** addon after a
reviewed preview.

It understands all three ways a store item can get a year:

1. the mod's own `<storeData><year>` tag,
2. the compatibility addon Lua tables
   (`MOD_VEHICLE_YEARS`, `MOD_YEARS`, `BASE_GAME_YEARS`),
3. the **FS25 Vehicle Years** database (one XML per vehicle inside
   `FS25_Vehicle_Years.zip`).

Everything is read directly from the mod ZIPs and the installed mod files —
nothing is extracted, nothing is written unless you ask for an output file or
confirm an addon setup/export.

## Quick start

```bash
python3 vycompat.py                  # scan the game mods folder
python3 vycompat.py --dir ../newmods # scan any folder of mods
python3 vycompat.py --base-game      # also check base game vehicles
```

No dependencies, Python 3.9+.

To install the console commands from this folder:

```bash
python3 -m pip install .
vycompat --version
vycompat-gui
```

Running the scripts directly from the checkout needs no installation.

The editor keeps its source in `FS25_VehicleYears_CompatibilityTool/` next to
the app, in the current folder, or in your Documents folder. Set
`VYCOMPAT_ADDON_DIR` to use a different folder containing
`vehicle_years_addon.lua`; CLI scans work anywhere.

### Missing compatibility addon

When a game mods folder is known, the GUI checks at startup and again
immediately before scanning. If no compatibility addon is present, it offers to
create one. It never writes automatically:

- **CREATE BLANK MOD** creates a valid empty **Vehicle Years Compatibility
  Tool** with the runtime hooks and empty year tables, then installs the ZIP
  into the mods folder.
- **INSTALL EXISTING** rebuilds and installs the editable source if it already
  exists but the ZIP is missing.
- **EXTRACT SOURCE** appears when the addon is installed but no editable source
  exists. It copies the installed ZIP or unpacked folder into the source folder
  so **Add years...**, **Paste years...** and **ADDON HISTORY...** can work with
  the existing years.
- **NOT NOW** continues the read-only scan without writing anything.

You can reopen the same prompt with **ADDON SETUP...** in the sidebar. The
blank mod requires the `FS25_Vehicle_Years` mod and does nothing until you add
years with **Add years...** or **Paste years...**.

This project is not tied to any particular community addon: the scanner reads
the standard compatibility tables from an installed ZIP or source folder, and
the setup flow creates a neutral scaffold with no pre-filled community data.

## GUI

```bash
python3 vycompat_gui.py    # or: python3 vycompat.py --gui
```

Tkinter front end (ships with Python, no extra dependencies). It uses an
original FS25-inspired charcoal/green theme (`vycompat_theme.py`) - game-menu
header, condensed headings, dense tables, dark cards and no game artwork.

**Simple (default):** pick a folder, press Scan. The list shows only vehicle
mods by their friendly title - problem mods first, colour-coded - and supported
mods say *how* they are covered:

- `Supported — mod itself`
- `Supported — Vehicle Years`
- `Supported — compatibility tool`

The details pane then just lists the vehicles with their years and what still
needs a year (with the full explanation, e.g. *added by the compatibility
tool*). The left rail filters the library by **All mods**, **Needs years**,
**Supported** and, in Advanced, **Hidden**; the counts follow the scan.
**Search** (or Ctrl+F) narrows either view by mod title, ZIP name, vehicle,
brand, category or addon key; several words are matched together.

**Tutorial:** press **F1** or the header **HELP** button for a six-step
in-app guide. It covers folder selection and scanning, reading statuses and
filters and search, Advanced exports, Add years including the change review and
history, and the Copy/Paste years workflow. The guide is a normal non-modal
window: its layout is not tied to a fixed size or screen position, it does not
grab input, and it wraps its text and scrolls its body, so it works as a tiled
or resized window under Hyprland and other tiling window managers. Use the
left/right arrows to change steps and Esc to close it. It stays available while
you follow along in the main window.

**Advanced** (checkbox) adds the technical view: ZIP file names instead of
titles, environment, descVersion, non-vehicle store-item counts, the exact
`MOD_YEARS` / `MOD_VEHICLE_YEARS` keys to paste, FS22/older and non-vehicle
mods, and the export buttons (save JSON, append to `years_info.txt`, copy Lua
suggestions, copy unsupported mods). Its compact status column uses short
forms (`Supported - VY`, `Supported - tool`, `Needs years 1/2`) so the extra
columns fit.
"Include base game vehicles" is always available.

**Adding years:** select a mod whose status says *Needs years*, then press
**Add years...**. Type one year for the whole mod (stored in `MOD_YEARS`) or
one year per vehicle (stored in `MOD_VEHICLE_YEARS`), then **Save & export**:

1. a review lists every added, changed and already-present entry, the version
   bump, the source/ZIP paths and whether the ZIP will be installed; nothing
   has been written yet,
2. **Write & rebuild** first stores an undo snapshot in
   `FS25_VehicleYears_CompatibilityTool/.vycompat_history/`,
3. the entries are written into
   `FS25_VehicleYears_CompatibilityTool/vehicle_years_addon.lua`,
4. the addon `<version>` is bumped and the modDesc description is extended,
5. `FS25_VehicleYears_CompatibilityTool.zip` is rebuilt,
6. by default it is installed straight into the game mods folder (untick the
   box to only build it), and
7. the folder is rescanned, so the mod shows as supported right away.

If only the installed ZIP exists, **Add years...** offers **EXTRACT SOURCE**
first and preserves the years already in it.

The game must be restarted (or the save reloaded) to pick up the new
compatibility addon. Years must be 1900-2030. An existing year is never
overwritten - the mod's own `<year>` and the Vehicle Years database still win,
the compatibility addon only fills gaps. If a year already exists in the addon
table, the review marks it amber as a change and asks before replacing it.

**Undo / history:** every confirmed addon export (and every restore) saves a
timestamped snapshot of the compatibility-addon source. **ADDON HISTORY...**
lists them; select one
and press **Restore & rebuild** to put the source files back and rebuild the
ZIP. The current state is snapshotted first, so a restore can itself be undone.
Installing the restored ZIP is an opt-in checkbox (off by default); the game
mods folder is never changed by a restore unless you tick it.

**Bulk via text:** **Copy years...** copies the ChatGPT verification prompt
followed by one `KEY = ?` line for every individual item that still needs a year
(vehicles, implements, trailers, tools - whole-mod entries are never included):

```
Find the real-world production year of each FS25 mod vehicle, implement, ...
...
ITEMS TO VERIFY:

FS25_ExampleTractor/ExampleTractor = ?
FS25_ExamplePack/ImplementA = ?
```

Paste that into ChatGPT, let it fill in the years, then paste its answer back
with **Paste years...** (the prompt block is skipped automatically). The prompt
now demands one line per item in the exact form
`MOD_KEY/ITEM_KEY = YEAR | CERTAINTY | GUESS` (no blank lines, no wrapping).
`unknown` (like `?`) means no year is written and the line is reported as
skipped; single-line `(year: 1983, certainty: sure, guess: none)` values are
accepted too. **Apply years** opens the same change review; after **Write &
rebuild** it snapshots the addon, writes every filled entry in one go (same
rebuild/install as above) and reports how many lines were skipped. Lines
without `/` become `MOD_YEARS` entries, lines with `/` become
`MOD_VEHICLE_YEARS` entries, and mixing both is still fine (per-vehicle wins at
runtime).

The scan runs in a background thread, so the window stays responsive.
Copy/scan confirmations appear as in-app toasts above the status bar; errors
use a themed modal dialog. Both year dialogs validate entries inline, and the
Add years dialog scrolls long vehicle lists. On Debian/Ubuntu install
`python3-tk` if Tkinter is missing.

Example output:

```
FS25 Vehicle Year Compatibility Tool 1.2.0
FS25 vehicle year support check
============================================================
mods folder : .../FarmingSimulator2025/mods
VY database : .../mods/FS25_Vehicle_Years.zip (5800 keys)
addon       : .../mods/FS25_VehicleYears_CompatibilityTool.zip [installed-zip v1.0.0.0] (3 mod + 2 per-vehicle + 1 base entries)

NEEDS YEAR SUPPORT (1 mod(s), 2 vehicle(s))
------------------------------------------------------------
FS25_ExampleTractor.zip - Example Tractor [FS25_ExampleTractor] (1/2 vehicle(s) missing)
    MOD_VEHICLE_YEARS["FS25_ExampleTractor/ExampleTractor"] = ?   Example Tractor (tractors)

SUMMARY
------------------------------------------------------------
  mods scanned             : 45
  FS25 vehicle/implement   : 12
      fully supported      : 10
      partially supported  : 1   (1 vehicle(s) missing)
      not supported        : 1
  non-vehicle mods         : 30
  skipped (FS22 or older)  : 2

1 vehicle(s) still need years (- use --lua-suggest for addon entries)
```

## Options

| Option | Meaning |
|---|---|
| `--dir FOLDER` | Folder to scan (repeatable). Default: the game mods folder. Zips and unpacked mod folders are both handled. |
| `--base-game` | Also scan the FS25 base game vehicles (`<game>/data/vehicles`, `handtools`). |
| `--base-game-only` | Scan only base game vehicles. |
| `--include-non-fs25` | Do not skip mods built for FS22 or older (descVersion < 90). |
| `--verbose`, `-v` | List every vehicle mod with the year source for each vehicle. |
| `--json FILE` | Write a machine-readable JSON report. |
| `--years-info FILE` | Append the missing vehicles to a `years_info.txt` style file (years left blank for you to fill in). |
| `--lua-suggest` | Print ready-to-paste addon Lua lines with `?` years, choosing `MOD_YEARS` vs `MOD_VEHICLE_YEARS` per mod. |
| `--copy-unsupported DIR` | Copy the mods that need support into DIR (opt-in, never automatic). |
| `--no-fail` | Exit 0 even when vehicles without years were found. |
| `--mods-dir FOLDER` | Game mods folder used to locate the installed Vehicle Years and compatibility-addon ZIPs. |
| `--game-dir DIR` | FS25 install folder (for `--base-game`). |
| `--vy-zip FILE` | Read the year database from a specific `FS25_Vehicle_Years.zip`. |
| `--vy-dir DIR` | Read the year database from an extracted `data/` folder instead. |
| `--addon SOURCE` | `installed` (default, the ZIP or unpacked folder in the mods folder), `source` (the editable `FS25_VehicleYears_CompatibilityTool/vehicle_years_addon.lua`), or an explicit path to either. |
| `--gui` | Open the graphical interface instead of the console report. |

Exit codes: `0` everything supported, `1` some vehicles still need years,
`2` a path or source could not be found.

## How support is detected

| Source | Key checked |
|---|---|
| Mod's own year | `<storeData><year>` inside the item XML |
| Addon per-vehicle | `customEnvironment .. "/" .. xml file` (no `.xml`) in `MOD_VEHICLE_YEARS` |
| Addon whole mod | `customEnvironment` in `MOD_YEARS` |
| Addon base game | `base_data_vehicles_brand_model_model` in `BASE_GAME_YEARS` |
| Vehicle Years DB | mods: `customEnvironment_raw_path`; base game: `base_data_vehicles_...` — the `data/*.xml` file names inside `FS25_Vehicle_Years.zip` |

The keys are computed exactly like `vehicle_years_addon.lua` does at runtime
(backslashes normalized, leading `./` stripped, `.xml` suffix removed,
`$data/...` and `data/...` both map to `base_data_...`).

## Notes

- Read-only by default: scanning never modifies the game mods folder, mod ZIPs
  or the compatibility addon. The only writes are the confirmed addon setup,
  the reviewed GUI addon editor (source Lua + modDesc, snapshot, rebuilt ZIP,
  optional install into the mods folder), the **ADDON HISTORY...** restore, and
  the opt-in CLI output flags (`--json`, `--years-info`, `--copy-unsupported`).
- Mods with a descVersion below 90 (FS22 and older) are skipped and counted
  separately, with `--include-non-fs25` to override.
- Mods without vehicle/handTool store items (maps, placeables, scripts) are
  counted as *non-vehicle* and ignored.
- Store items hidden from the shop (`<showInStore>false</showInStore>`, e.g.
  base game trains) and pallet store items used by maps/productions are ignored.
- Keys are compared case-sensitively, matching the game's lookup.

## Project layout

```text
fs25_vehicle_year_compatibility_tool/
├── AGENTS.md                  Agent guidance for this app
├── CHANGELOG.md               Release history
├── LICENSE                    MIT licence
├── MANIFEST.in                Source archive contents
├── README.md                  This guide
├── pyproject.toml             Package metadata and console scripts
├── docs/
│   └── UI_SPEC.md             Visual/UX specification
├── tests/                     Standard-library unittest suite
├── vycompat.py                Scanner core, planning/export and CLI
├── vycompat_gui.py            Tkinter application and dialogs
├── vycompat_addon.py          Neutral blank-addon modDesc/Lua templates
├── vycompat_history.py        Addon snapshots, history and undo
├── vycompat_theme.py          Palette, styles and dialog helpers
└── vycompat_tutorial.py       Responsive in-app guide (F1 / Help)
```

## Release

1. Keep `__version__` in `vycompat.py` and `version` in `pyproject.toml` in
   sync (currently `1.2.0`).
2. Update `CHANGELOG.md` and the test count in `README.md` and `AGENTS.md` when
   it changes.
3. Run the complete suite:

   ```bash
   python3 -m unittest discover -s tests -v
   ```

4. Build the wheel and source archive (the `build` package is optional; the app
   itself has no runtime dependencies):

   ```bash
   python3 -m build
   # or, with only pip/setuptools available:
   python3 -m pip wheel . --no-deps -w dist
   ```

   Artifacts are written to `dist/`, which is git-ignored. Do not install a
   rebuilt game addon from the release process; hand the ZIP to the user.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests build synthetic mod ZIPs and addon sources in a temp folder and need no
game installation. There are 154 tests (CLI, blank-addon scaffold, source
extraction, planning/export, local snapshot/undo, ChatGPT prompt/template/parser,
GUI data helpers, setup flow, search and dialogs, the FS25-inspired theme, and
the responsive in-app tutorial); the GUI, theme and tutorial window tests skip
themselves when no display is available.

Files:

- `vycompat.py` - scanner, detection, prompt/parser, addon setup, planning/export
- `vycompat_addon.py` - neutral blank compatibility-addon templates
- `vycompat_gui.py` - themed Tkinter application, filters, search, dialogs and actions
- `vycompat_history.py` - local addon snapshots, history listing and undo
- `vycompat_theme.py` - palette, ttk styles, cards, fonts and dialog helpers
- `vycompat_tutorial.py` - non-modal responsive in-app guide (F1 / Help)
- `docs/UI_SPEC.md` - visual/UX specification used by the theme

## License

MIT
