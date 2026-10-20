<p align="center">
  <img src="Icons/MAINicon.png" width="128" alt="FS25 Vehicle Year Compatibility Tool icon">
</p>

<h1 align="center">FS25 Vehicle Year Compatibility Tool</h1>

<p align="center">
  <strong>Find every Farming Simulator 25 vehicle that still needs a year &mdash; and add it safely.</strong>
</p>

<p align="center">
  <a href="https://github.com/MonomCZ/fs25_vehicle_year_compatibility_tool/releases/latest">
    <img src="https://img.shields.io/github/v/release/MonomCZ/fs25_vehicle_year_compatibility_tool?style=for-the-badge&label=download" alt="Download the latest release">
  </a>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-2f8f5b?style=for-the-badge" alt="Windows and Linux">
</p>

A friendly desktop app for **Farming Simulator 25** modders and players. It scans
your mods, shows exactly which vehicles, implements, trailers and tools still
need a production year, and helps you fill the gaps without hand-editing Lua.

It understands the three normal places a year can come from:

- the mod's own year tag,
- the **Vehicle Years Compatibility Tool** addon,
- the **FS25 Vehicle Years** database.

Everything stays local. No accounts, no cloud, no telemetry.

## At a glance

| Feature | Details |
|---|---|
| **Finds** | vehicles and implements that still need a year |
| **Adds** | one year for a whole mod, or one year per vehicle |
| **Writes** | only after you review and confirm |
| **Runs on** | Windows x64, Linux x86_64, or Python 3.9+ |
| **Works with** | ZIP mods and unpacked mod folders |

## Download and run

Get the latest version from the
[**Releases page**](https://github.com/MonomCZ/fs25_vehicle_year_compatibility_tool/releases/latest).
The packaged builds are **GUI-only** and need no Python installation.

### Windows

1. Download `FS25-Vehicle-Year-Compatibility-Tool.exe`.
2. Run it. There is no installer.
3. Windows may show a SmartScreen warning because the build is not code-signed.
   Only run files downloaded from this repository's Releases page.

### Linux

1. Download `FS25-Vehicle-Year-Compatibility-Tool-1.3.0-x86_64.AppImage`.
2. Make it executable, then run it:

   ```bash
   chmod +x FS25-Vehicle-Year-Compatibility-Tool-1.3.0-x86_64.AppImage
   ./FS25-Vehicle-Year-Compatibility-Tool-1.3.0-x86_64.AppImage
   ```

If your distribution does not have FUSE, install `libfuse2` (Ubuntu/Debian) or
run the AppImage with `--appimage-extract-and-run`.

## Your first scan

1. Open the app. It tries to find
   `Documents/My Games/FarmingSimulator2025/mods` automatically.
2. If needed, choose your FS25 `mods` folder.
3. Press **Scan**.

Scanning is read-only. Your mods, ZIPs and compatibility tool are not changed
until you explicitly confirm an edit.

## Reading the results

The list is colour-coded and puts mods that need attention first.

| Status | What it means |
|---|---|
| **Needs years** | One or more vehicles still have no year from any source. |
| **Supported &mdash; mod itself** | The mod already contains its own year data. |
| **Supported &mdash; Vehicle Years** | The FS25 Vehicle Years database covers it. |
| **Supported &mdash; compatibility tool** | The compatibility tool fills the gap. |

Click a mod to see its vehicles, the years it already has, and what still
needs one. FS22 and older mods are skipped by default.

> **Tip:** Press **F1** or the **HELP** button for the built-in six-step guide.

## Adding years

1. Select a mod marked **Needs years**.
2. Click **Add years...**.
3. Enter one year for the whole mod, or one year per vehicle.
4. Review every change in the confirmation window.
5. Click **Write & rebuild**.

Before anything is written, the app saves an undo snapshot. It then updates the
compatibility tool, bumps its version, rebuilds the ZIP and — by default —
installs it into your game mods folder. Untick the install box if you only want
to build the ZIP.

Restart FS25 (or reload the save) to see the new years in game.

> **No silent overwrites:** the mod's own year and the Vehicle Years database
> always win. The compatibility tool only fills gaps. If an existing tool value
> would change, the review marks it and asks first.

## Bulk years with ChatGPT

Doing a lot at once? Use **Copy years...**:

1. The app copies a ready-made verification prompt plus a `KEY = ?` line for
   every item that still needs a year.
2. Paste it into ChatGPT and let it fill in the years.
3. Paste the answer back with **Paste years...**.
4. Review the changes, then click **Write & rebuild**.

Unknown or `?` answers are skipped, and you can mix whole-mod answers with
per-vehicle answers.

## Compatibility tool and undo

If no compatibility tool is installed, the app offers to set one up:

- **CREATE BLANK MOD** — creates a clean, empty compatibility tool and installs
  it.
- **INSTALL EXISTING** — rebuilds and installs an existing editable source.
- **EXTRACT SOURCE** — copies an installed addon into an editable source folder
  while keeping its existing years.
- **NOT NOW** — continues the read-only scan without changing anything.

You can reopen this with **ADDON SETUP...** in the sidebar. The blank
compatibility tool requires the `FS25_Vehicle_Years` mod and does nothing until
you add years.

Every confirmed change creates a timestamped snapshot. Open **ADDON HISTORY...**
to restore an earlier version. The current state is snapshotted first, so even a
restore can be undone.

## The secret icon

The compatibility tool normally uses the clean main icon. On average, **one in
ten launches** adds a very colourful **AMAZING ICON** button to the sidebar.

Click it to preview the alternate icon. You can switch the in-game compatibility
tool to the ALT icon or restore the main one. The app saves a snapshot, rebuilds
the ZIP and asks before installing anything. Years and the compatibility tool
version are not changed.

Want to see it now? Force it on:

```bash
# Linux AppImage
VYCOMPAT_EASTER_EGG=1 ./FS25-Vehicle-Year-Compatibility-Tool-1.3.0-x86_64.AppImage

# From source
VYCOMPAT_EASTER_EGG=1 python3 vycompat_gui.py
```

Disable it with `VYCOMPAT_EASTER_EGG=0` in the same place, or use the
`--easter-egg` / `--no-easter-egg` flags instead.

The ALT image is a bit of fun and contains third-party imagery, so it is not
covered by the project's MIT licence. See
[`Icons/README.md`](Icons/README.md) for details.

## Safety

- Scanning never modifies your mods.
- Nothing is overwritten without a review and confirmation.
- Compatibility tool changes and icon changes save a snapshot first.
- Installing into the game mods folder is always shown in the confirmation
  window.
- The app works offline and has no telemetry.
- Only download packaged builds from this repository's Releases page.

## Good to know

- **Search** (or `Ctrl+F`) filters by mod title, ZIP name, vehicle, brand,
  category or addon key.
- **Advanced** shows technical details such as ZIP names, environments,
  descVersion, exact Lua keys and extra export buttons.
- **Include base game vehicles** checks the game's own vehicles too.
- Years must be between 1900 and 2030.
- Restart FS25 after installing a rebuilt compatibility tool.

## Run from source

For development or if you prefer not to use a packaged build:

```bash
git clone https://github.com/MonomCZ/fs25_vehicle_year_compatibility_tool.git
cd fs25_vehicle_year_compatibility_tool
python3 vycompat_gui.py
```

Requires Python 3.9+ with Tkinter. On Debian/Ubuntu:

```bash
sudo apt install python3-tk
```

A command-line scanner is also included:

```bash
python3 vycompat.py --help
```

## License

The app and its main icon are MIT-licensed. `Icons/ALTicon.png` contains
third-party meme/logo imagery and is **not** covered by the MIT licence; do not
redistribute it separately or use it commercially without checking the original
rights.

This is an unofficial community tool and is not affiliated with GIANTS
Software. Farming Simulator 25 is a trademark of GIANTS Software.
