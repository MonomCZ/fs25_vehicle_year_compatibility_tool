#!/usr/bin/env python3
"""FS25 Vehicle Year Compatibility Tool.

Detect Farming Simulator 25 vehicle/implement mods that have no production-year
support and help maintain the compatibility-addon tables.

Year support for a store item can come from three sources; all are checked:

  1. the mod's own ``<storeData><year>...</year>``
  2. the Vehicle Years compatibility addon (source Lua or installed ZIP)
       MOD_VEHICLE_YEARS  key: customEnvironment .. "/" .. xml file (no .xml)
       MOD_YEARS          key: customEnvironment
       BASE_GAME_YEARS    key: base_data_vehicles_brand_model_model
  3. the FS25 Vehicle Years database (one XML per vehicle inside the installed
     FS25_Vehicle_Years.zip, keyed by the data file name)

The scanner is read-only: it never writes to the game mods folder, mod ZIPs or
the compatibility addon.  Only files explicitly passed via --json /
--years-info / --copy-unsupported are written.  The GUI's addon editor
additionally keeps local undo snapshots in
``FS25_VehicleYears_CompatibilityTool/.vycompat_history`` and writes the addon
source/ZIP only after the user reviews and confirms the change.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import vycompat_addon as addon_template

__version__ = "1.3.0"
APP_NAME = "FS25 Vehicle Year Compatibility Tool"
TOOL = "vycompat"

# FS25 SDK modDesc templates use descVersion 90; FS22 mods use 55-71 and are
# not scanned unless --include-non-fs25 is given.
FS25_MIN_DESC_VERSION = 90

VY_MOD_NAME = "FS25_Vehicle_Years"
ADDON_MOD_NAME = "FS25_VehicleYears_CompatibilityTool"
ADDON_TITLE = addon_template.ADDON_TITLE
ADDON_ICON_NAME = addon_template.ADDON_ICON_NAME
ADDON_LUA_NAME = "vehicle_years_addon.lua"
ADDON_MODDESC_NAME = "modDesc.xml"
ADDON_ZIP_NAME = ADDON_MOD_NAME + ".zip"

MIN_YEAR = 1900
MAX_YEAR = 2030

COMPATDATA_ID = "3152698207"
DOCS_REL = "pfx/drive_c/users/steamuser/Documents/My Games/FarmingSimulator2025"
GAME_DIR_NAME = "Farming Simulator 25"

HOME = Path.home()
STEAM_ROOTS = [
    HOME / ".steam" / "steam" / "steamapps",
    HOME / ".local" / "share" / "Steam" / "steamapps",
    HOME / ".steam" / "root" / "steamapps",
]

REPO_DIR = Path(__file__).resolve().parent
WORKDIR = REPO_DIR.parent


def _writable_parent(path):
    """Return True when a directory can probably be created at ``path``."""
    path = Path(path)
    probe = path if path.is_dir() else path.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe.is_dir() and os.access(probe, os.W_OK)


def default_source_addon_dir():
    """Locate the editable compatibility-addon source used by the GUI editor.

    The source can live next to the app, in the current working directory, or
    in the user's Documents folder.  A packaged install can point at another
    checkout with the ``VYCOMPAT_ADDON_DIR`` environment variable.
    """
    override = os.environ.get("VYCOMPAT_ADDON_DIR")
    if override:
        return Path(override).expanduser()
    cwd = Path.cwd()
    documents = HOME / "Documents" / ADDON_MOD_NAME
    candidates = [
        WORKDIR / ADDON_MOD_NAME,
        cwd / ADDON_MOD_NAME,
        cwd.parent / ADDON_MOD_NAME,
        documents,
    ]
    for candidate in candidates:
        if (candidate / ADDON_LUA_NAME).is_file():
            return candidate

    # A source checkout keeps the editable addon beside the app folder.  An
    # installed wheel has no pyproject.toml there, so use Documents instead of
    # writing into the Python library directory.
    preferred = []
    if (REPO_DIR / "pyproject.toml").is_file():
        preferred.append(WORKDIR / ADDON_MOD_NAME)
    preferred.extend([documents, cwd / ADDON_MOD_NAME])
    for candidate in preferred:
        if _writable_parent(candidate):
            return candidate
    return documents


SOURCE_ADDON_DIR = default_source_addon_dir()
SOURCE_ADDON_LUA = SOURCE_ADDON_DIR / ADDON_LUA_NAME


def set_source_addon_dir(source_dir):
    """Point the editor at a newly created or selected source folder."""
    global SOURCE_ADDON_DIR, SOURCE_ADDON_LUA
    SOURCE_ADDON_DIR = Path(source_dir)
    SOURCE_ADDON_LUA = SOURCE_ADDON_DIR / ADDON_LUA_NAME
    return SOURCE_ADDON_DIR

EMPTY_TABLES = {"MOD_VEHICLE_YEARS": {}, "MOD_YEARS": {}, "BASE_GAME_YEARS": {}}

# FS25 maps/productions register pallets as <vehicle> store items; they are not
# vehicles/implements and must not show up as needing years.
NON_VEHICLE_CATEGORIES = {"pallets"}

YEAR_TAG_RE = re.compile(r"<year>\s*(\d{1,4})\s*</year>")
LUA_ENTRY_RE = re.compile(r'\["([^"]+)"\]\s*=\s*(\d+)')
LUA_TABLE_NAMES = ("MOD_VEHICLE_YEARS", "MOD_YEARS", "BASE_GAME_YEARS")


# ---------------------------------------------------------------------------
# default paths
# ---------------------------------------------------------------------------

def default_game_dir():
    for root in STEAM_ROOTS:
        candidate = root / "common" / GAME_DIR_NAME
        if candidate.is_dir():
            return candidate
    return None


def default_mods_dir():
    for root in STEAM_ROOTS:
        candidate = root / "compatdata" / COMPATDATA_ID / DOCS_REL / "mods"
        if candidate.is_dir():
            return candidate
    return None


# ---------------------------------------------------------------------------
# key normalization (must mirror vehicle_years_addon.lua / pack_mod.py)
# ---------------------------------------------------------------------------

def clean_rel(name):
    """Normalize a mod relative path: backslashes, leading './'."""
    if not name:
        return ""
    name = str(name).strip().replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name


def norm_rel(name):
    """Key form of an item XML path: clean_rel() without the .xml suffix."""
    name = clean_rel(name)
    if name.lower().endswith(".xml"):
        name = name[:-4]
    return name


def mod_vy_key(env, raw_xml):
    """Vehicle Years data file key for a mod vehicle."""
    flat = norm_rel(raw_xml).replace("/", "_")
    return f"{env}_{flat}" if env else flat


def base_key(raw_xml):
    """Vehicle Years / addon key for a base game path ($data/... or data/...)."""
    name = norm_rel(raw_xml)
    if name.startswith("$data"):
        name = "base_data" + name[5:]
    elif name.startswith("data"):
        name = "base_" + name
    return name.replace("/", "_")


# ---------------------------------------------------------------------------
# data source: Vehicle Years database
# ---------------------------------------------------------------------------

def load_vy_zip(path):
    """Read data/*.xml entries from the installed Vehicle Years ZIP."""
    keys = {}
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            low = name.lower()
            if not low.startswith("data/") or not low.endswith(".xml"):
                continue
            if "__macosx" in low:
                continue
            key = name[len("data/"):-len(".xml")]
            year = None
            try:
                text = zf.read(name).decode("utf-8", "ignore")
                match = YEAR_TAG_RE.search(text)
                if match:
                    year = int(match.group(1))
                elif text.strip().isdigit():
                    year = int(text.strip())
            except (KeyError, OSError):
                pass
            keys[key] = year
    return keys


def load_vy_dir(path):
    """Read a directory of per vehicle year XML files (extracted database)."""
    keys = {}
    for xml_file in sorted(Path(path).glob("*.xml")):
        year = None
        try:
            text = xml_file.read_text(encoding="utf-8", errors="ignore")
            match = YEAR_TAG_RE.search(text)
            if match:
                year = int(match.group(1))
            elif text.strip().isdigit():
                year = int(text.strip())
        except OSError:
            pass
        keys[xml_file.stem] = year
    return keys


# ---------------------------------------------------------------------------
# data source: addon Lua tables
# ---------------------------------------------------------------------------

def parse_lua_tables(text):
    """Extract the three addon lookup tables from vehicle_years_addon.lua."""
    tables = {}
    for name in LUA_TABLE_NAMES:
        match = re.search(r"local\s+%s\s*=\s*\{" % re.escape(name), text)
        if not match:
            tables[name] = {}
            continue
        block = text[match.end():]
        end = re.search(r"^\}", block, re.M)
        if end:
            block = block[:end.start()]
        entries = {}
        for line in block.splitlines():
            line = line.split("--", 1)[0]
            entry = LUA_ENTRY_RE.search(line)
            if entry:
                entries[entry.group(1)] = int(entry.group(2))
        tables[name] = entries
    return tables


def load_addon_zip(path):
    """Load the tables and version from an installed addon ZIP."""
    tables = dict(EMPTY_TABLES)
    version = None
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        lua_name = next(
            (n for n in names if n.lower().endswith(ADDON_LUA_NAME.lower())),
            None,
        )
        if lua_name is None:
            # Be tolerant of a custom addon that uses another Lua file name.
            lua_name = next(
                (
                    n for n in names
                    if n.lower().endswith(".lua")
                    and not n.lower().endswith(("/moddesc.xml", "\\moddesc.xml"))
                    and b"MOD_VEHICLE_YEARS" in zf.read(n)
                ),
                None,
            )
        if lua_name:
            tables = parse_lua_tables(zf.read(lua_name).decode("utf-8", "ignore"))
        moddesc = next(
            (n for n in names if n.lower().endswith("moddesc.xml")),
            None,
        )
        if moddesc:
            match = re.search(
                r"<version>\s*([^<\s]+)\s*</version>",
                zf.read(moddesc).decode("utf-8", "ignore"),
            )
            if match:
                version = match.group(1)
    return tables, version


def load_addon_source(lua_path):
    """Load the tables and version from the addon source folder."""
    tables = parse_lua_tables(Path(lua_path).read_text(encoding="utf-8", errors="ignore"))
    version = None
    moddesc = Path(lua_path).parent / "modDesc.xml"
    if moddesc.is_file():
        match = re.search(
            r"<version>\s*([^<\s]+)\s*</version>",
            moddesc.read_text(encoding="utf-8", errors="ignore"),
        )
        if match:
            version = match.group(1)
    return tables, version


def addon_info(tables, version, path, kind):
    counts = {name: len(tables.get(name, {})) for name in LUA_TABLE_NAMES}
    return {
        "path": str(path) if path else None,
        "kind": kind,
        "version": version,
        "counts": counts,
        "total": sum(counts.values()),
    }


def _as_dirs(value):
    """Accept one path or an iterable of paths and return unique folders."""
    if value is None:
        return []
    if isinstance(value, (str, os.PathLike, Path)):
        values = [value]
    else:
        values = value
    result = []
    for item in values:
        if item is None:
            continue
        path = Path(item)
        if path not in result:
            result.append(path)
    return result


def installed_addon_path(directory):
    """Return an installed addon path and kind from one mods folder."""
    if directory is None:
        return None, None
    directory = Path(directory)
    zip_path = directory / ADDON_ZIP_NAME
    if zip_path.is_file():
        return zip_path, "installed-zip"
    folder = directory / ADDON_MOD_NAME
    lua_path = folder / ADDON_LUA_NAME
    if lua_path.is_file():
        return lua_path, "installed-folder"
    return None, None


def addon_setup_state(discovery_dirs):
    """Describe the installed/source state used by the GUI setup prompt."""
    installed = None
    installed_kind = None
    for directory in _as_dirs(discovery_dirs):
        installed, installed_kind = installed_addon_path(directory)
        if installed is not None:
            break
    source = SOURCE_ADDON_LUA if SOURCE_ADDON_LUA.is_file() else None
    return {
        "installed": installed,
        "installed_kind": installed_kind,
        "source": source,
        "needs_setup": installed is None,
        "needs_install": installed is None and source is not None,
    }


def resolve_addon(value, discovery_dir):
    """Resolve --addon into (tables, info)."""
    value = (value or "installed").strip()
    candidates = []
    if value == "installed":
        for directory in _as_dirs(discovery_dir):
            installed, _kind = installed_addon_path(directory)
            if installed is not None:
                candidates.append(installed)
        candidates.append(SOURCE_ADDON_LUA)
    elif value == "source":
        candidates.append(SOURCE_ADDON_LUA)
    else:
        candidate = Path(value).expanduser()
        if candidate.is_dir():
            candidate = candidate / ADDON_LUA_NAME
        candidates.append(candidate)

    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            if candidate.suffix.lower() == ".zip":
                tables, version = load_addon_zip(candidate)
                kind = "installed-zip"
            else:
                tables, version = load_addon_source(candidate)
                kind = (
                    "installed-folder"
                    if candidate.parent.name == ADDON_MOD_NAME
                    and candidate.parent.parent in _as_dirs(discovery_dir)
                    else "source-lua"
                )
        except (zipfile.BadZipFile, OSError) as exc:
            print(f"{TOOL}: warning: cannot read addon {candidate}: {exc}", file=sys.stderr)
            continue
        return tables, addon_info(tables, version, candidate, kind)

    return dict(EMPTY_TABLES), addon_info(dict(EMPTY_TABLES), None, None, "missing")


def resolve_vy(args, discovery_dir):
    """Resolve --vy-zip / --vy-dir / default into (keys, info)."""
    if args.vy_zip:
        path = Path(args.vy_zip).expanduser()
        return load_vy_zip(path), {"kind": "zip", "path": str(path)}
    if args.vy_dir:
        path = Path(args.vy_dir).expanduser()
        return load_vy_dir(path), {"kind": "dir", "path": str(path)}
    for directory in _as_dirs(discovery_dir):
        for name in (f"{VY_MOD_NAME}.zip", f"{VY_MOD_NAME}_update.zip"):
            candidate = Path(directory) / name
            if candidate.is_file():
                return load_vy_zip(candidate), {"kind": "zip", "path": str(candidate)}
    return {}, {"kind": "missing", "path": None}


# ---------------------------------------------------------------------------
# addon editing: add years, rebuild the ZIP, install it
# ---------------------------------------------------------------------------

def validate_year(value):
    """Accept a year as int or string, return int, raise ValueError otherwise."""
    text = str(value).strip()
    if not text or not text.isdigit():
        raise ValueError(f"'{value}' is not a year")
    year = int(text)
    if not (MIN_YEAR <= year <= MAX_YEAR):
        raise ValueError(f"'{value}' is not a year (allowed: {MIN_YEAR}-{MAX_YEAR})")
    return year


def bump_version(version):
    """1.0.4.0 -> 1.0.5.0 (content bump); falls back to the last component."""
    parts = str(version).split(".")
    index = len(parts) - 2 if len(parts) >= 4 else len(parts) - 1
    if index >= 0 and parts[index].isdigit():
        parts[index] = str(int(parts[index]) + 1)
        return ".".join(parts)
    return str(version) + ".1"


def _lua_upsert(text, table_name, key, year):
    """Insert or update one entry inside a `local TABLE = { ... }` block."""
    match = re.search(r"local\s+%s\s*=\s*\{" % re.escape(table_name), text)
    if match is None:
        raise ValueError(f"table {table_name} not found in the addon Lua file")
    block_start = match.end()
    closing = re.search(r"^\s*\}", text[block_start:], re.M)
    if closing is None:
        raise ValueError(f"could not find the end of {table_name}")
    close_pos = block_start + closing.start()
    block = text[block_start:close_pos]

    pattern = re.compile(r'(\["%s"\]\s*=\s*)(\d+)' % re.escape(key))
    existing = pattern.search(block)
    if existing is not None:
        old_year = int(existing.group(2))
        if old_year == year:
            return text, "unchanged", old_year
        new_block = block[: existing.start(2)] + str(year) + block[existing.end(2):]
        return (
            text[:block_start] + new_block + text[close_pos:],
            "updated",
            old_year,
        )

    indent_match = re.search(r"^(\s+)\[", block, re.M)
    indent = indent_match.group(1) if indent_match else "    "
    insertion = f'{indent}["{key}"] = {year},\n'
    return text[:close_pos] + insertion + text[close_pos:], "added", None


def update_addon_lua(text, mod_years=None, vehicle_years=None):
    """Add or update year entries in the addon Lua tables.

    mod_years     -> MOD_YEARS        {customEnvironment: year}
    vehicle_years -> MOD_VEHICLE_YEARS {customEnvironment/xml: year}

    Returns (new_text, entries) where each entry reports
    table/key/year/action, plus old_year for updated entries.  Action is
    'added', 'updated' or 'unchanged'.
    """
    entries = []
    for table_name, mapping in (
        ("MOD_YEARS", mod_years or {}),
        ("MOD_VEHICLE_YEARS", vehicle_years or {}),
    ):
        for key, year in mapping.items():
            text, action, old_year = _lua_upsert(
                text, table_name, str(key), int(year)
            )
            entries.append(
                {
                    "table": table_name,
                    "key": str(key),
                    "year": int(year),
                    "old_year": old_year,
                    "action": action,
                }
            )
    return text, entries


def _insert_section_lines(text, header, lines):
    """Append lines at the end of a description list that starts with `header`."""
    start = text.find(header)
    if start == -1:
        return text, False
    start += len(header)
    end = text.find("\n\n", start)
    if end == -1:
        return text, False
    addition = "".join("\n" + line for line in lines)
    return text[:end] + addition + text[end:], True


def update_addon_description(text, mod_lines=None, per_vehicle=None):
    """Append human readable lines to the addon modDesc description.

    mod_lines: ["- FS25_X (Title) - 1965"]
    per_vehicle: [("- FS25_X (Title)", ["  - Vehicle A - 1965", ...])]
    """
    updated = False
    if mod_lines:
        text, ok = _insert_section_lines(text, "Supported mods:\n", list(mod_lines))
        updated = updated or ok
    if per_vehicle:
        block = []
        for header, sublines in per_vehicle:
            block.append(header)
            block.extend(sublines)
        text, ok = _insert_section_lines(
            text, "Supported mods with per-vehicle years:\n", block
        )
        updated = updated or ok
    return text, updated


def update_addon_moddesc_version(text, version):
    return re.sub(r"<version>[^<]*</version>", f"<version>{version}</version>", text, count=1)


def update_addon_moddesc_icon(text, icon_name=ADDON_ICON_NAME):
    """Point modDesc at the icon filename, inserting it when necessary."""
    element = f"<iconFilename>{icon_name}</iconFilename>"
    if re.search(r"<iconFilename>[^<]*</iconFilename>", text):
        return re.sub(
            r"<iconFilename>[^<]*</iconFilename>", element, text, count=1
        )
    version = re.search(r"<version>[^<]*</version>", text)
    if version:
        pos = version.end()
        return text[:pos] + "\n    " + element + text[pos:]
    end = re.search(r"<modDesc\b[^>]*>", text)
    if end:
        pos = end.end()
        return text[:pos] + "\n    " + element + text[pos:]
    return text


def _atomic_write(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _atomic_write_bytes(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def build_addon_zip(source_dir, out_zip):
    """Zip the addon source folder into out_zip.

    Hidden folders (including ``.vycompat_history``), ``__pycache__`` and
    ``*.tmp`` files are excluded.  Nested resource files are kept so a user
    addon with an icon or other assets rebuilds without losing them.
    """
    source_dir = Path(source_dir)
    files = []
    for file in sorted(source_dir.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(source_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if "__pycache__" in relative.parts or file.name.endswith(".tmp"):
            continue
        files.append((file, relative.as_posix()))
    if not files:
        raise FileNotFoundError(f"no addon files found in {source_dir}")
    with zipfile.ZipFile(Path(out_zip), "w", zipfile.ZIP_DEFLATED) as zf:
        for file, archive_name in files:
            zf.write(file, archive_name)
    return Path(out_zip)


def _empty_or_missing_source(source):
    source = Path(source)
    return not source.exists() or (
        source.is_dir() and not any(source.iterdir())
    )


def _replace_empty_source(temp_source, source):
    source = Path(source)
    if source.exists():
        source.rmdir()
    Path(temp_source).replace(source)


def extract_addon_zip(zip_path, source_dir):
    """Extract an installed compatibility-addon ZIP into a new source folder.

    This is offered when the addon is installed but no editable source exists.
    It never overwrites an existing source and rejects path-traversal entries.
    """
    zip_path = Path(zip_path)
    source = Path(source_dir)
    if not _empty_or_missing_source(source):
        raise FileExistsError(f"addon source already exists: {source}")

    with zipfile.ZipFile(zip_path) as zf:
        members = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            parts = [part for part in name.split("/") if part not in ("", ".")]
            if name.startswith("/") or any(part == ".." for part in parts):
                raise ValueError(f"unsafe addon ZIP entry: {info.filename}")
            if not parts:
                continue
            members.append((info, "/".join(parts)))
        names = {name.lower() for _info, name in members}
        if ADDON_MODDESC_NAME.lower() not in names:
            raise ValueError("installed addon has no modDesc.xml")
        if ADDON_LUA_NAME.lower() not in names:
            raise ValueError(
                "installed addon has no editable vehicle_years_addon.lua"
            )

    source.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".vycompat_extract_", dir=str(source.parent)
    ) as temp_dir:
        temp_source = Path(temp_dir) / ADDON_MOD_NAME
        temp_source.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            for info, relative in members:
                target = temp_source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
        _replace_empty_source(temp_source, source)

    return {
        "source": str(source),
        "lua": str(source / ADDON_LUA_NAME),
        "description": str(source / ADDON_MODDESC_NAME),
        "extracted_from": str(zip_path),
    }


def copy_addon_source(source_dir, destination):
    """Copy an unpacked installed addon into a new editable source folder."""
    source = _require_addon_source(source_dir)
    destination = Path(destination)
    if not _empty_or_missing_source(destination):
        raise FileExistsError(f"addon source already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".vycompat_copy_", dir=str(destination.parent)
    ) as temp_dir:
        temp_source = Path(temp_dir) / ADDON_MOD_NAME
        shutil.copytree(
            source,
            temp_source,
            ignore=shutil.ignore_patterns(
                ".vycompat_history", "__pycache__", "*.tmp"
            ),
        )
        _replace_empty_source(temp_source, destination)

    return {
        "source": str(destination),
        "lua": str(destination / ADDON_LUA_NAME),
        "description": str(destination / ADDON_MODDESC_NAME),
        "copied_from": str(source),
    }


def _require_addon_source(source_dir):
    source = Path(source_dir)
    lua_path = source / ADDON_LUA_NAME
    desc_path = source / ADDON_MODDESC_NAME
    if not lua_path.is_file():
        raise FileNotFoundError(f"addon Lua not found: {lua_path}")
    if not desc_path.is_file():
        raise FileNotFoundError(f"addon modDesc not found: {desc_path}")
    return source


def install_addon_source(source_dir, install_dir, zip_path=None):
    """Rebuild an existing addon source and install it.

    An already installed target is never replaced; the caller must remove or
    update it through the reviewed export flow.
    """
    source = _require_addon_source(source_dir)
    install_dir = Path(install_dir)
    install_target = install_dir / ADDON_ZIP_NAME
    if install_target.exists():
        raise FileExistsError(f"addon already installed: {install_target}")

    zip_target = Path(zip_path) if zip_path else source.parent / ADDON_ZIP_NAME
    install_dir.mkdir(parents=True, exist_ok=True)
    zip_target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".vycompat_build_", dir=str(source.parent)
    ) as temp_dir:
        built = Path(temp_dir) / ADDON_ZIP_NAME
        build_addon_zip(source, built)
        shutil.copy2(built, zip_target)
        if install_target != zip_target:
            shutil.copy2(built, install_target)
    return {
        "source": str(source),
        "zip": str(zip_target),
        "installed": str(install_target),
    }


def set_addon_icon(source_dir, icon_data, install_dir=None, zip_path=None):
    """Replace the addon icon, rebuild its ZIP and optionally install it.

    The caller is responsible for taking a history snapshot first.  Years,
    ``modDesc.xml`` and the addon version are deliberately left unchanged.
    """
    source = _require_addon_source(source_dir)
    data = bytes(icon_data)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("addon icon must be a PNG image")

    icon_path = source / ADDON_ICON_NAME
    _atomic_write_bytes(icon_path, data)

    desc_path = source / ADDON_MODDESC_NAME
    desc_text = desc_path.read_text(encoding="utf-8")
    desc_with_icon = update_addon_moddesc_icon(desc_text)
    if desc_with_icon != desc_text:
        _atomic_write(desc_path, desc_with_icon)

    zip_target = Path(zip_path) if zip_path else source.parent / ADDON_ZIP_NAME
    zip_target.parent.mkdir(parents=True, exist_ok=True)
    build_addon_zip(source, zip_target)

    installed = None
    if install_dir:
        install_dir = Path(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)
        target = install_dir / ADDON_ZIP_NAME
        if target.resolve() != zip_target.resolve():
            shutil.copy2(zip_target, target)
        installed = target

    return {
        "source": str(source),
        "icon": str(icon_path),
        "zip": str(zip_target),
        "installed": str(installed) if installed else None,
    }


def scaffold_addon(source_dir=None, install_dir=None, zip_path=None):
    """Create a valid, empty compatibility addon after explicit confirmation.

    The source folder and both ZIP targets are checked before anything is
    written.  Existing files are never replaced.
    """
    source = Path(source_dir) if source_dir else SOURCE_ADDON_DIR
    zip_target = Path(zip_path) if zip_path else source.parent / ADDON_ZIP_NAME
    install_target = Path(install_dir) / ADDON_ZIP_NAME if install_dir else None

    if source.exists() and (not source.is_dir() or any(source.iterdir())):
        raise FileExistsError(f"addon source already exists: {source}")
    if zip_target.exists():
        raise FileExistsError(f"addon ZIP already exists: {zip_target}")
    if install_target is not None and install_target.exists():
        raise FileExistsError(f"addon already installed: {install_target}")

    source.parent.mkdir(parents=True, exist_ok=True)
    zip_target.parent.mkdir(parents=True, exist_ok=True)
    if install_target is not None:
        install_target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".vycompat_setup_", dir=str(source.parent)
    ) as temp_dir:
        temp_source = Path(temp_dir) / ADDON_MOD_NAME
        temp_source.mkdir()
        _atomic_write(temp_source / ADDON_LUA_NAME, addon_template.BLANK_LUA)
        _atomic_write(
            temp_source / ADDON_MODDESC_NAME, addon_template.BLANK_MODDESC
        )
        (temp_source / ADDON_ICON_NAME).write_bytes(
            addon_template.default_icon_png()
        )
        built = Path(temp_dir) / ADDON_ZIP_NAME
        build_addon_zip(temp_source, built)

        if source.exists():
            source.rmdir()
        temp_source.replace(source)
        shutil.copy2(built, zip_target)
        if install_target is not None:
            shutil.copy2(built, install_target)

    return {
        "title": ADDON_TITLE,
        "source": str(source),
        "lua": str(source / ADDON_LUA_NAME),
        "description": str(source / ADDON_MODDESC_NAME),
        "icon": str(source / ADDON_ICON_NAME),
        "zip": str(zip_target),
        "installed": str(install_target) if install_target else None,
        "version": "1.0.0.0",
    }


def plan_addon_years(source_dir, mod_years=None, vehicle_years=None,
                     description_mods=None, description_vehicles=None,
                     bump=True):
    """Build an addon edit without writing anything.

    Returns a plan dict with the edited Lua/modDesc text, entry actions
    (``added``/``updated``/``unchanged``), old/new version and whether the
    description would be extended.  The GUI uses this for its review dialog;
    ``export_addon_years`` applies the same plan.
    """
    source_dir = Path(source_dir)
    lua_path = source_dir / ADDON_LUA_NAME
    desc_path = source_dir / ADDON_MODDESC_NAME
    if not lua_path.is_file():
        raise FileNotFoundError(f"addon Lua not found: {lua_path}")
    if not desc_path.is_file():
        raise FileNotFoundError(f"addon modDesc not found: {desc_path}")

    lua_text = lua_path.read_text(encoding="utf-8", errors="ignore")
    new_lua, entries = update_addon_lua(lua_text, mod_years, vehicle_years)
    changed = any(entry["action"] != "unchanged" for entry in entries)

    desc_text = desc_path.read_text(encoding="utf-8", errors="ignore")
    version_match = re.search(r"<version>([^<]+)</version>", desc_text)
    old_version = version_match.group(1).strip() if version_match else "1.0.0.0"
    plan = {
        "changed": changed,
        "entries": entries,
        "version": old_version,
        "new_version": old_version,
        "description_updated": False,
        "lua": new_lua,
        "description": desc_text,
    }
    if not changed:
        return plan

    # sanity check: the edited Lua must still parse and contain every entry
    tables = parse_lua_tables(new_lua)
    for entry in entries:
        if tables[entry["table"]].get(entry["key"]) != entry["year"]:
            raise ValueError(
                f'internal check failed for {entry["table"]}["{entry["key"]}"]'
            )

    new_version = bump_version(old_version) if bump else old_version
    desc_text = update_addon_moddesc_version(desc_text, new_version)
    desc_text, description_updated = update_addon_description(
        desc_text, description_mods, description_vehicles
    )
    plan.update(
        new_version=new_version,
        description_updated=description_updated,
        description=desc_text,
    )
    return plan


def export_addon_years(source_dir, mod_years=None, vehicle_years=None,
                       description_mods=None, description_vehicles=None,
                       install_dir=None, zip_path=None, bump=True):
    """Apply years to the addon source, bump its version, rebuild and install.

    Returns a report dict; raises on failure.  Call ``plan_addon_years`` first
    when the change should be reviewed before it is written.
    """
    source_dir = Path(source_dir)
    lua_path = source_dir / ADDON_LUA_NAME
    desc_path = source_dir / ADDON_MODDESC_NAME
    plan = plan_addon_years(
        source_dir, mod_years, vehicle_years,
        description_mods, description_vehicles, bump,
    )
    report = {
        "changed": plan["changed"],
        "entries": plan["entries"],
        "version": None,
        "zip": None,
        "installed": None,
        "description_updated": False,
    }
    if not plan["changed"]:
        return report

    _atomic_write(lua_path, plan["lua"])
    _atomic_write(desc_path, plan["description"])

    zip_target = Path(zip_path) if zip_path else source_dir.parent / ADDON_ZIP_NAME
    build_addon_zip(source_dir, zip_target)
    report["version"] = plan["new_version"]
    report["zip"] = str(zip_target)
    report["description_updated"] = plan["description_updated"]

    if install_dir:
        install_dir = Path(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)
        installed = install_dir / ADDON_ZIP_NAME
        shutil.copy2(zip_target, installed)
        report["installed"] = str(installed)
    return report


# ---------------------------------------------------------------------------
# file access: read mods as ZIP or unpacked folder, without extracting
# ---------------------------------------------------------------------------

def find_moddesc(names):
    candidates = [n for n in names if n.lower().endswith("moddesc.xml") and "__macosx" not in n.lower()]
    if not candidates:
        return None
    candidates.sort(key=lambda n: (n.count("/"), len(n)))
    return candidates[0]


class ZipSource:
    kind = "zip"

    def __init__(self, path):
        self.path = Path(path)
        self.zf = zipfile.ZipFile(self.path)
        self.names = self.zf.namelist()
        self.lower = {n.lower(): n for n in self.names}
        self.moddesc = find_moddesc(self.names)

    def read(self, rel):
        rel = clean_rel(rel).lstrip("/")
        name = rel if rel in self.names else self.lower.get(rel.lower())
        if name is None:
            return None
        try:
            return self.zf.read(name)
        except (KeyError, OSError):
            return None

    def close(self):
        self.zf.close()


class DirSource:
    kind = "dir"

    def __init__(self, path):
        self.path = Path(path)
        self._index = None
        self._lower = None
        self._moddesc = None

    @property
    def moddesc(self):
        if self._index is None:
            self._build()
        return self._moddesc

    def _build(self):
        index = {}
        for dirpath, _dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                full = Path(dirpath) / filename
                rel = full.relative_to(self.path).as_posix()
                index[rel] = full
        self._index = index
        self._lower = {k.lower(): k for k in index}
        self._moddesc = find_moddesc(self._index)

    def read(self, rel):
        if self._index is None:
            self._build()
        rel = clean_rel(rel).lstrip("/")
        full = self._index.get(rel)
        if full is None:
            key = self._lower.get(rel.lower())
            if key is not None:
                full = self._index[key]
        if full is None:
            return None
        try:
            return full.read_bytes()
        except OSError:
            return None

    def close(self):
        pass


def open_source(path):
    path = Path(path)
    if path.is_dir():
        return DirSource(path)
    return ZipSource(path)


# ---------------------------------------------------------------------------
# item inspection
# ---------------------------------------------------------------------------

def text_of(elem):
    """English text of an l10n style element (<name><en>..</en></name>)."""
    if elem is None:
        return ""
    child = elem.find("en")
    if child is not None and child.text:
        return child.text.strip()
    if elem.text:
        return elem.text.strip()
    for sub in elem:
        if sub.text and sub.text.strip():
            return sub.text.strip()
    return ""


def is_base_ref(name):
    """True for a store item path pointing at base game data ($data/...)."""
    name = clean_rel(name)
    return name.startswith("$data") or name.startswith("data/")


def is_non_vehicle_category(category):
    """Pallets (maps, productions) are registered as vehicles but are not vehicles."""
    tokens = category.replace(",", " ").split()
    return any(token in NON_VEHICLE_CATEGORIES for token in tokens)


def inspect_item(raw_bytes):
    """-> (root tag, info dict). tag is 'vehicle', 'handTool', another tag or 'invalid'."""
    try:
        root = ET.fromstring(raw_bytes.lstrip(b"\xef\xbb\xbf"))
    except ET.ParseError:
        return "invalid", {}
    tag = root.tag.split("}")[-1]
    info = {"root": tag, "brand": "", "name": "", "category": "", "own_year": None,
            "show_in_store": True}
    store_data = root.find("storeData")
    if store_data is not None:
        info["brand"] = (store_data.findtext("brand") or "").strip().upper()
        info["name"] = text_of(store_data.find("name"))
        info["category"] = (store_data.findtext("category") or "").strip()
        info["show_in_store"] = (store_data.findtext("showInStore") or "").strip().lower() != "false"
        year_text = (store_data.findtext("year") or "").strip()
        if year_text.isdigit():
            info["own_year"] = int(year_text)
    return tag, info


def resolve_support(env, item_xml, own_year, addon, vy):
    """Find which source gives this store item a year."""
    rel = norm_rel(item_xml)
    if own_year is not None:
        return {"source": "own", "year": own_year, "key": None}

    if rel.startswith("$data") or rel.startswith("data/"):
        key = base_key(rel)
        if key in addon.get("BASE_GAME_YEARS", {}):
            return {"source": "addon-base", "year": addon["BASE_GAME_YEARS"][key], "key": key}
        if key in vy:
            return {"source": "vy", "year": vy[key], "key": key}
        return {"source": "none", "year": None, "key": key}

    if env:
        vehicle_key = f"{env}/{rel}"
        if vehicle_key in addon.get("MOD_VEHICLE_YEARS", {}):
            return {
                "source": "addon-vehicle",
                "year": addon["MOD_VEHICLE_YEARS"][vehicle_key],
                "key": vehicle_key,
            }
        if env in addon.get("MOD_YEARS", {}):
            return {"source": "addon-mod", "year": addon["MOD_YEARS"][env], "key": env}

    for candidate in (mod_vy_key(env, rel), rel.replace("/", "_")):
        if candidate in vy:
            return {"source": "vy", "year": vy[candidate], "key": candidate}

    return {"source": "none", "year": None, "key": mod_vy_key(env, rel)}


# ---------------------------------------------------------------------------
# mod scanning
# ---------------------------------------------------------------------------

def scan_mod(path, addon, vy, include_non_fs25=False):
    path = Path(path)
    result = {
        "file": path.name,
        "path": str(path),
        "kind": "dir" if path.is_dir() else "zip",
        "custom_environment": path.stem,
        "title": "",
        "version": "",
        "desc_version": None,
        "status": "error",
        "error": None,
        "vehicles": [],
        "missing": [],
        "non_vehicle_items": 0,
    }

    try:
        source = open_source(path)
    except (zipfile.BadZipFile, OSError) as exc:
        result["error"] = f"cannot open: {exc}"
        return result

    try:
        if source.moddesc is None:
            result["error"] = "no modDesc.xml in mod"
            return result
        raw = source.read(source.moddesc)
        try:
            root = ET.fromstring(raw.lstrip(b"\xef\xbb\xbf"))
        except ET.ParseError as exc:
            result["error"] = f"modDesc.xml parse error: {exc}"
            return result

        desc_version = root.get("descVersion") or "0"
        result["desc_version"] = int(desc_version) if desc_version.isdigit() else 0
        env = (root.findtext("customEnvironment") or "").strip()
        result["custom_environment"] = env or path.stem
        result["title"] = text_of(root.find("title"))
        result["version"] = (root.findtext("version") or "").strip()

        if (
            result["desc_version"]
            and result["desc_version"] < FS25_MIN_DESC_VERSION
            and not include_non_fs25
        ):
            result["status"] = "skipped"
            return result

        env_name = result["custom_environment"]
        base_dir = posixpath.dirname(source.moddesc)

        for elem in root.iter("storeItem"):
            xml_file = (elem.get("xmlFilename") or "").strip()
            if not xml_file:
                continue
            root_node = (elem.get("rootNode") or "").strip()
            if root_node and root_node not in ("vehicle", "handTool"):
                result["non_vehicle_items"] += 1
                continue

            raw_item = source.read(xml_file)
            if raw_item is None and base_dir:
                raw_item = source.read(posixpath.join(base_dir, xml_file))
            if raw_item is None:
                if is_base_ref(xml_file):
                    # base game reference (map foliage/train/pallets), not the mod's own
                    result["non_vehicle_items"] += 1
                else:
                    result["missing"].append(xml_file)
                continue

            tag, info = inspect_item(raw_item)
            if tag not in ("vehicle", "handTool"):
                result["non_vehicle_items"] += 1
                continue
            if not info["show_in_store"]:
                result["non_vehicle_items"] += 1
                continue
            if is_non_vehicle_category(info["category"]):
                result["non_vehicle_items"] += 1
                continue

            support = resolve_support(env_name, xml_file, info["own_year"], addon, vy)
            result["vehicles"].append(
                {
                    "xml": clean_rel(xml_file),
                    "name": info["name"],
                    "brand": info["brand"],
                    "category": info["category"],
                    "own_year": info["own_year"],
                    "source": support["source"],
                    "year": support["year"],
                    "addon_vehicle_key": f"{env_name}/{norm_rel(xml_file)}",
                    "addon_mod_key": env_name,
                    "vy_key": mod_vy_key(env_name, xml_file),
                }
            )

        vehicles = result["vehicles"]
        if not vehicles:
            result["status"] = "error" if result["missing"] else "no-vehicles"
            if result["missing"]:
                result["error"] = "store item XML files missing from mod"
            return result

        supported = sum(1 for v in vehicles if v["source"] != "none")
        if supported == len(vehicles):
            result["status"] = "supported"
        elif supported == 0:
            result["status"] = "unsupported"
        else:
            result["status"] = "partial"
        return result
    finally:
        source.close()


def scan_mods_dir(directory, addon, vy, include_non_fs25=False):
    directory = Path(directory)
    results = []
    if not directory.is_dir():
        return results
    entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
    for entry in entries:
        if entry.is_dir():
            if not (entry / "modDesc.xml").is_file():
                continue
            results.append(scan_mod(entry, addon, vy, include_non_fs25))
        elif entry.suffix.lower() == ".zip":
            results.append(scan_mod(entry, addon, vy, include_non_fs25))
    return results


# ---------------------------------------------------------------------------
# base game scanning
# ---------------------------------------------------------------------------

def scan_base_game(game_dir, addon, vy):
    data_dir = Path(game_dir) / "data"
    items = []
    for sub in ("vehicles", "handtools"):
        base = data_dir / sub
        if not base.is_dir():
            continue
        for xml_file in sorted(base.rglob("*.xml")):
            if xml_file.name.startswith("."):
                continue
            try:
                raw = xml_file.read_bytes()
            except OSError:
                continue
            tag, info = inspect_item(raw)
            if tag not in ("vehicle", "handTool"):
                continue
            if not info["show_in_store"]:
                continue
            if not info["category"]:
                continue
            if is_non_vehicle_category(info["category"]):
                continue
            raw_xml = f"$data/{xml_file.relative_to(data_dir).as_posix()}"
            key = base_key(raw_xml)
            if info["own_year"] is not None:
                source, year = "own", info["own_year"]
            elif key in addon.get("BASE_GAME_YEARS", {}):
                source, year = "addon-base", addon["BASE_GAME_YEARS"][key]
            elif key in vy:
                source, year = "vy", vy[key]
            else:
                source, year = "none", None
            items.append(
                {
                    "raw_xml": raw_xml,
                    "key": key,
                    "brand": info["brand"],
                    "name": info["name"],
                    "category": info["category"],
                    "source": source,
                    "year": year,
                }
            )
    return items


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def mod_needs_support(mod):
    return mod["status"] in ("unsupported", "partial")


def missing_vehicles(mod):
    return [v for v in mod["vehicles"] if v["source"] == "none"]


def vehicle_label(vehicle):
    label = vehicle["name"] or vehicle["xml"]
    if label.startswith("$l10n_"):
        label = label[len("$l10n_"):]
    if vehicle["category"]:
        label += f" ({vehicle['category']})"
    return label


def counts_of(mods):
    summary = {
        "scanned": len(mods),
        "vehicle_mods": 0,
        "supported": 0,
        "partial": 0,
        "unsupported": 0,
        "no_vehicles": 0,
        "skipped": 0,
        "errors": 0,
        "vehicles_total": 0,
        "vehicles_missing": 0,
        "missing_partial": 0,
        "missing_unsupported": 0,
    }
    for mod in mods:
        status = mod["status"]
        if status == "skipped":
            summary["skipped"] += 1
        elif status == "error":
            summary["errors"] += 1
        elif status == "no-vehicles":
            summary["no_vehicles"] += 1
        else:
            summary["vehicle_mods"] += 1
            summary[status] += 1
            missing = len(missing_vehicles(mod))
            summary["vehicles_total"] += len(mod["vehicles"])
            summary["vehicles_missing"] += missing
            if status == "partial":
                summary["missing_partial"] += missing
            elif status == "unsupported":
                summary["missing_unsupported"] += missing
    return summary


def format_console(mods, base_items, src, verbose):
    summary = counts_of(mods)
    lines = []
    lines.append(f"{APP_NAME} {__version__}")
    lines.append("FS25 vehicle year support check")
    lines.append("=" * 60)
    if src["mods_dirs"]:
        for directory in src["mods_dirs"]:
            lines.append(f"mods folder : {directory}")
    vy = src["vy"]
    if vy["kind"] == "missing":
        lines.append("VY database : not found (addon tables only)")
    else:
        lines.append(f"VY database : {vy['path']} ({src['vy_count']} keys)")
    addon = src["addon"]
    if addon["path"] is None:
        lines.append("addon       : not found")
    else:
        version = f" v{addon['version']}" if addon["version"] else ""
        counts = addon["counts"]
        lines.append(
            f"addon       : {addon['path']} [{addon['kind']}{version}] "
            f"({counts['MOD_YEARS']} mod + {counts['MOD_VEHICLE_YEARS']} per-vehicle "
            f"+ {counts['BASE_GAME_YEARS']} base entries)"
        )
    lines.append("")

    needs = [m for m in mods if mod_needs_support(m)]
    if needs:
        lines.append(f"NEEDS YEAR SUPPORT ({len(needs)} mod(s), "
                     f"{sum(len(missing_vehicles(m)) for m in needs)} vehicle(s))")
        lines.append("-" * 60)
        for mod in needs:
            missing = missing_vehicles(mod)
            total = len(mod["vehicles"])
            title = f" - {mod['title']}" if mod["title"] else ""
            lines.append(
                f"{mod['file']}{title} [{mod['custom_environment']}] "
                f"({len(missing)}/{total} vehicle(s) missing)"
            )
            if total > 1 and total == len(missing):
                lines.append(
                    f'    use MOD_YEARS["{mod["custom_environment"]}"] if all vehicles '
                    f"share one year, or per vehicle:"
                )
            for vehicle in missing:
                lines.append(
                    f'    MOD_VEHICLE_YEARS["{vehicle["addon_vehicle_key"]}"] = ?   '
                    f"{vehicle_label(vehicle)}"
                )
            for xml_file in mod["missing"]:
                lines.append(f"    missing file in mod: {xml_file}")
        lines.append("")

    if verbose:
        lines.append("ALL VEHICLE MODS")
        lines.append("-" * 60)
        for mod in mods:
            if mod["status"] in ("skipped", "error", "no-vehicles"):
                continue
            title = f" - {mod['title']}" if mod["title"] else ""
            lines.append(f"{mod['file']}{title} [{mod['status']}]")
            for vehicle in mod["vehicles"]:
                year = f" {vehicle['year']}" if vehicle["year"] is not None else ""
                lines.append(
                    f"    [{vehicle['source']}{year}] {vehicle_label(vehicle)}"
                )
        lines.append("")

    if base_items is not None:
        missing = [b for b in base_items if b["source"] == "none"]
        lines.append("BASE GAME")
        lines.append("-" * 60)
        lines.append(
            f"{len(base_items)} vehicle(s) checked, {len(missing)} without a year"
        )
        for item in missing:
            lines.append(
                f"    {item['raw_xml']} | {item['brand']} | {item['name']} | {item['category']}"
            )
        lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 60)
    lines.append(f"  mods scanned             : {summary['scanned']}")
    lines.append(f"  FS25 vehicle/implement   : {summary['vehicle_mods']}")
    lines.append(f"      fully supported      : {summary['supported']}")
    lines.append(
        f"      partially supported  : {summary['partial']}"
        f"   ({summary['missing_partial']} vehicle(s) missing)"
    )
    lines.append(
        f"      not supported        : {summary['unsupported']}"
        f"   ({summary['missing_unsupported']} vehicle(s) missing)"
    )
    lines.append(f"  non-vehicle mods         : {summary['no_vehicles']}")
    lines.append(f"  skipped (FS22 or older)  : {summary['skipped']}")
    if summary["errors"]:
        lines.append(f"  unreadable / other       : {summary['errors']}")
    if base_items is not None:
        base_missing = sum(1 for b in base_items if b["source"] == "none")
        lines.append(
            f"  base game missing years  : {base_missing} of {len(base_items)}"
        )
    lines.append("")

    remaining = summary["vehicles_missing"]
    if base_items is not None:
        remaining += sum(1 for b in base_items if b["source"] == "none")
    if remaining:
        lines.append(f"{remaining} vehicle(s) still need years "
                     f"(- use --lua-suggest for addon entries)")
    else:
        lines.append("all scanned vehicles have year support")
    return "\n".join(lines)


def format_json(mods, base_items, src):
    addon = src["addon"]
    payload = {
        "tool": TOOL,
        "name": APP_NAME,
        "version": __version__,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "sources": {
            "mods_dirs": [str(d) for d in src["mods_dirs"]],
            "game_dir": str(src["game_dir"]) if src["game_dir"] else None,
            "vy": dict(src["vy"], count=src["vy_count"]),
            "addon": addon,
        },
        "summary": counts_of(mods),
        "mods": mods,
        "base_game": None,
    }
    if base_items is not None:
        missing = [b for b in base_items if b["source"] == "none"]
        payload["base_game"] = {
            "checked": len(base_items),
            "missing": len(missing),
            "items": base_items,
        }
    return json.dumps(payload, indent=2)


def format_years_info(mods):
    lines = []
    for mod in mods:
        if not mod_needs_support(mod):
            continue
        missing = missing_vehicles(mod)
        if not missing:
            continue
        label = mod["file"]
        if len(missing) == 1:
            lines.append(f"{label} - {vehicle_label(missing[0])} -")
        else:
            lines.append(f"{label} - per vehicle:")
            for vehicle in missing:
                lines.append(f"  {vehicle_label(vehicle)} -")
    return "\n".join(lines)


def format_lua_suggest(mods):
    lines = [
        "-- Add these to vehicle_years_addon.lua and fill in the years.",
        '-- MOD_YEARS        : ["customEnvironment"] = year            (whole mod, one year)',
        '-- MOD_VEHICLE_YEARS: ["customEnvironment/xml file"] = year   (single vehicle)',
        "",
    ]
    for mod in mods:
        if not mod_needs_support(mod):
            continue
        missing = missing_vehicles(mod)
        if not missing:
            continue
        title = f" ({mod['title']})" if mod["title"] else ""
        lines.append(f"-- {mod['file']}{title} - {len(missing)} of {len(mod['vehicles'])} missing")
        if len(missing) == len(mod["vehicles"]):
            lines.append("    -- if every vehicle shares one year:")
            lines.append(f'    ["{mod["custom_environment"]}"] = ?,')
        for vehicle in missing:
            lines.append(
                f'    ["{vehicle["addon_vehicle_key"]}"] = ?,'
                f"  -- {vehicle_label(vehicle)}"
            )
        lines.append("")
    return "\n".join(lines)


def normalize_addon_key(key):
    """Normalize an addon key (backslashes, leading ./, trailing .xml)."""
    key = str(key).strip()
    if "/" not in key:
        return key
    env, _, relative = key.partition("/")
    relative = relative.replace("\\", "/").strip()
    while relative.startswith("./"):
        relative = relative[2:]
    if relative.endswith(".xml"):
        relative = relative[:-4]
    return env.strip() + "/" + relative


TEMPLATE_HEADER = [
    "# FS25 Vehicle Year Compatibility Tool - mods that still need a year",
    '# Replace ? with a year (1900-2030), then press "Paste years..." in the tool.',
    "# KEY = year   -   KEY without / = whole mod, KEY with / = single vehicle",
    "# Fill the lines you need - whole-mod and per-vehicle lines can be mixed.",
]


def missing_template(mods):
    """Build the copyable KEY = ? list for every vehicle that needs a year.

    Each mod gets a whole-mod line plus one line per vehicle that is still
    missing a year. Returns (text, count) with count = number of lines to fill.
    """
    groups = []
    count = 0
    for mod in sorted(mods, key=lambda item: item["file"].lower()):
        missing = missing_vehicles(mod)
        if not missing:
            continue
        env = mod["custom_environment"]
        if not env:
            continue
        title = mod["title"] or mod["file"]
        lines = [f"# {title} ({mod['file']})"]
        lines.append(f"{env} = ?    # whole mod")
        count += 1
        for vehicle in missing:
            lines.append(
                f"{vehicle['addon_vehicle_key']} = ?"
                f"    # single vehicle - {vehicle_label(vehicle)}"
            )
            count += 1
        groups.append("\n".join(lines))
    if not groups:
        return "", 0
    return "\n".join(TEMPLATE_HEADER) + "\n\n" + "\n\n".join(groups) + "\n", count


CHATGPT_ITEM_MARKER = "ITEMS TO VERIFY:"
CHATGPT_ITEM_PLACEHOLDER = "PASTE THE VYCOMPAT ITEM LIST HERE"

# The verification prompt used with ChatGPT. Kept verbatim; chatgpt_template
# only replaces the item placeholder with the pending KEY = ? lines.
CHATGPT_VERIFICATION_PROMPT = """Find the real-world production year of each FS25 mod vehicle, implement, trailer, tool, or other individual item listed below. Search the web and use reliable sources.

Rules:
- Change only `year`, `certainty`, and `guess`.
- Keep all other fields exactly unchanged.
- `certainty` must be `sure`, `unsure`, or `unknown`.
- Use `sure` only when the production year is verified by reliable sources.
- Use `unsure` when the most likely production year is known but not fully verified.
- Use `unknown` when the production year cannot be determined reliably.
- If the year is known, set `guess` to `none`.
- If the year is `unknown` but the brand or model is identifiable, provide your best estimated production year in `guess`, even if the model number appears invalid or fictional. Use available model numbering, manufacturer history, and related models to make a reasonable estimate.
- If the item is generic or its brand and model cannot be identified, set `guess` to `none`.
- `guess` must contain only a four-digit year or `none`. Never include explanations in `guess`.
- A guess is speculative and must not be presented as a verified fact.
- Distinguish the real-world production year from the mod release year.
- For vehicles and equipment manufactured over multiple years, use the earliest verified production year of the exact model where possible.
- Do not invent sources or claim verification without evidence.
- Preserve the exact order and all original IDs and fields.
- Do not add or remove entries.
- Do not include whole-mod entries; process only the individual items listed below.

Return exactly one line per item, in this exact format, with no blank lines, no parentheses, braces, bullets, numbering, introductory text, explanations, or Markdown fences:

MOD_KEY/ITEM_KEY = YEAR | CERTAINTY | GUESS

- YEAR must be a four-digit production year or `unknown`.
- CERTAINTY must be `sure`, `unsure`, or `unknown`.
- GUESS must be a four-digit year or `none`.
- Copy each MOD_KEY/ITEM_KEY exactly as given. Do not change characters, reorder items, or split an entry across lines.
- Do not add or remove entries.

ITEMS TO VERIFY:

PASTE THE VYCOMPAT ITEM LIST HERE
"""


def chatgpt_items(mods):
    """One "MOD_KEY/ITEM_KEY = ?" line per item still missing a year.

    Every line refers to a single vehicle, implement, trailer, tool or other
    store item - whole-mod entries are never emitted.
    """
    lines = []
    for mod in sorted(mods, key=lambda item: item["file"].lower()):
        for vehicle in missing_vehicles(mod):
            key = vehicle.get("addon_vehicle_key") or ""
            if not key or "/" not in key:
                continue
            lines.append(f"{key} = ?")
    return lines


def chatgpt_template(mods):
    """Build the ChatGPT verification prompt with the pending items appended.

    Returns (text, count) where count is the number of items to fill in. The
    prompt is reused verbatim from CHATGPT_VERIFICATION_PROMPT and its item
    placeholder is replaced by the per-item KEY = ? list. No whole-mod
    entries and no already-supported items are included. Returns ("", 0)
    when there is nothing missing.
    """
    lines = chatgpt_items(mods)
    if not lines:
        return "", 0
    text = CHATGPT_VERIFICATION_PROMPT.replace(
        CHATGPT_ITEM_PLACEHOLDER, "\n".join(lines)
    )
    return text, len(lines)


def strip_verification_prompt(text):
    """Drop the ChatGPT verification prompt, keeping only the item lines.

    Accepts the text produced by chatgpt_template (prompt followed by the
    KEY = ? list) so the filled-in answer can be pasted back into vycompat.
    Text without the prompt marker is returned unchanged.
    """
    index = text.find(CHATGPT_ITEM_MARKER)
    if index == -1:
        return text
    first_line = CHATGPT_VERIFICATION_PROMPT.splitlines()[0]
    if first_line not in text[:index]:
        return text
    lines = text[index + len(CHATGPT_ITEM_MARKER):].splitlines()
    lines = [
        line for line in lines if line.strip() != CHATGPT_ITEM_PLACEHOLDER
    ]
    return "\n".join(lines).strip()


YEAR_LINE = re.compile(r"^(.+?)\s*=\s*(.*)$")
LABELLED_YEAR_RE = re.compile(r"\byear\s*[:=]\s*(\d{4}|unknown)\b", re.I)


def parse_years_text(text):
    """Parse KEY = YEAR lines as produced by missing_template.

    The ChatGPT verification output from chatgpt_template is accepted too:
    a leading prompt block is stripped automatically. An optional
    "| certainty | guess" suffix after the year is ignored, as is a
    single-line labelled form like "(year: 1983, certainty: sure, guess:
    none)". Comment lines (#) and blank lines are ignored. A value of ?,
    ??, unknown (case-insensitive) or nothing marks the line as still
    pending - unknown years are never written to the addon. Returns a dict
    with mod_years, vehicle_years, pending (keys) and errors (messages).
    """
    text = strip_verification_prompt(text)
    mod_years = {}
    vehicle_years = {}
    pending = []
    errors = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = YEAR_LINE.match(line)
        if match is None:
            candidate = normalize_addon_key(line)
            if re.fullmatch(r"[^\s=]+/[^\s=]+", candidate):
                # An item key with no value - treat it as still pending.
                pending.append(candidate)
                continue
            if re.match(r"^[({]?\s*year\s*[:=]", line, re.I):
                # Orphan value line from a wrapped answer; nothing to apply.
                continue
            errors.append(f"line {number}: expected KEY = year -> {line}")
            continue
        key = normalize_addon_key(match.group(1))
        if not key or key.startswith("/") or key.endswith("/"):
            errors.append(f"line {number}: missing key -> {line}")
            continue
        value = match.group(2).strip()
        labelled = LABELLED_YEAR_RE.search(value)
        if labelled is not None:
            token = labelled.group(1)
        else:
            first = value.split("|", 1)[0].strip()
            token = first.split()[0] if first.split() else ""
            token = token.strip("(){}[],;")
        if token.lower() in ("", "?", "??", "unknown"):
            pending.append(key)
            continue
        try:
            year = validate_year(token)
        except ValueError:
            errors.append(f"line {number}: '{token}' is not a year (1900-2030)")
            continue
        if "/" in key:
            vehicle_years[key] = year
        else:
            mod_years[key] = year
    return {
        "mod_years": mod_years,
        "vehicle_years": vehicle_years,
        "pending": pending,
        "errors": errors,
    }


def description_entries(mod_years, vehicle_years, mods):
    """Build modDesc description lines for the given year entries.

    Returns (description_mods, description_vehicles) for export_addon_years.
    """
    mods_by_env = {}
    for mod in mods or []:
        env = mod.get("custom_environment")
        if env:
            mods_by_env.setdefault(env, mod)

    description_mods = []
    for env, year in mod_years.items():
        mod = mods_by_env.get(env)
        title = (mod and mod.get("title")) or env
        description_mods.append(f"- {env} ({title}) - {year}")

    grouped = {}
    for key, year in vehicle_years.items():
        env, _, relative = key.partition("/")
        grouped.setdefault(env, []).append((key, relative, year))

    description_vehicles = []
    for env, items in grouped.items():
        mod = mods_by_env.get(env)
        header = f"- {env} ({(mod and mod.get('title')) or env})"
        names = {}
        if mod:
            for vehicle in mod["vehicles"]:
                names[vehicle["addon_vehicle_key"]] = vehicle["name"] or vehicle["xml"]
        subs = [
            f"  - {names.get(key) or relative} - {year}"
            for key, relative, year in items
        ]
        description_vehicles.append((header, subs))
    return description_mods or None, description_vehicles or None


def copy_unsupported(mods, target_dir):
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for mod in mods:
        if not mod_needs_support(mod):
            continue
        if mod["kind"] != "zip":
            copied.append((mod["file"], "skipped (unpacked folder)"))
            continue
        source = Path(mod["path"])
        destination = target / source.name
        if destination.exists():
            copied.append((source.name, "already there"))
            continue
        shutil.copy2(source, destination)
        copied.append((source.name, "copied"))
    return copied


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog=TOOL,
        description="Detect FS25 vehicle/implement mods without year support "
                    "(Vehicle Years database + compatibility-addon tables).",
    )
    parser.add_argument(
        "--dir", action="append", default=[], metavar="FOLDER",
        help="mod folder to scan (repeatable; default: the game mods folder)",
    )
    parser.add_argument("--mods-dir", metavar="FOLDER",
                        help="game mods folder used to find the installed VY and "
                             "compatibility-addon ZIPs")
    parser.add_argument("--base-game", action="store_true",
                        help="also scan the FS25 base game vehicles")
    parser.add_argument("--base-game-only", action="store_true",
                        help="scan only the FS25 base game vehicles")
    parser.add_argument("--include-non-fs25", action="store_true",
                        help="also scan mods built for FS22 or older")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="list every vehicle mod and the support source per vehicle")
    parser.add_argument("--json", metavar="FILE", help="write a JSON report")
    parser.add_argument("--years-info", metavar="FILE",
                        help="append missing vehicles to a years_info.txt style file")
    parser.add_argument("--lua-suggest", action="store_true",
                        help="print ready-to-paste addon Lua lines with '?' years")
    parser.add_argument("--copy-unsupported", metavar="DIR",
                        help="copy mods that need support into DIR")
    parser.add_argument("--no-fail", action="store_true",
                        help="exit 0 even when vehicles without years were found")
    parser.add_argument("--game-dir", metavar="DIR",
                        help="FS25 install directory (for --base-game)")
    parser.add_argument("--vy-zip", metavar="FILE",
                        help="FS25_Vehicle_Years.zip to read the database from")
    parser.add_argument("--vy-dir", metavar="DIR",
                        help="extracted Vehicle Years data/ directory")
    parser.add_argument("--addon", default="installed", metavar="SOURCE",
                        help="'installed' (default), 'source', or a path to "
                             "FS25_VehicleYears_CompatibilityTool.zip / "
                             "vehicle_years_addon.lua")
    parser.add_argument("--gui", action="store_true",
                        help="open the graphical interface (Tkinter)")
    parser.add_argument("--version", action="version", version=f"{TOOL} {__version__}")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    stderr = lambda message: print(f"{TOOL}: {message}", file=sys.stderr)

    if args.gui:
        try:
            import vycompat_gui
        except ImportError as exc:
            stderr(f"GUI not available: {exc}")
            stderr("Tkinter ships with Python; on Debian/Ubuntu install python3-tk.")
            return 2
        return vycompat_gui.main()

    discovery_dir = Path(args.mods_dir).expanduser() if args.mods_dir else default_mods_dir()

    game_dir = None
    if args.game_dir:
        game_dir = Path(args.game_dir).expanduser()
    elif args.base_game or args.base_game_only:
        game_dir = default_game_dir()

    if args.base_game_only:
        mods_dirs = []
    elif args.dir:
        mods_dirs = [Path(d).expanduser() for d in args.dir]
    else:
        mods_dirs = [discovery_dir] if discovery_dir else []

    if not mods_dirs and not args.base_game and not args.base_game_only:
        stderr("no mods folder found; pass --dir FOLDER")
        return 2

    addon, addon_meta = resolve_addon(args.addon, discovery_dir)
    vy, vy_meta = resolve_vy(args, discovery_dir)

    mods = []
    for directory in mods_dirs:
        if not directory.is_dir():
            stderr(f"not a folder: {directory}")
            return 2
        mods.extend(scan_mods_dir(directory, addon, vy, args.include_non_fs25))

    base_items = None
    if args.base_game or args.base_game_only:
        if game_dir is None or not (game_dir / "data").is_dir():
            stderr("FS25 install not found; pass --game-dir DIR")
            return 2
        base_items = scan_base_game(game_dir, addon, vy)

    src = {
        "mods_dirs": mods_dirs,
        "game_dir": game_dir,
        "vy": vy_meta,
        "vy_count": len(vy),
        "addon": addon_meta,
    }

    print(format_console(mods, base_items, src, args.verbose))

    if args.json:
        Path(args.json).write_text(format_json(mods, base_items, src) + "\n", encoding="utf-8")
        print(f"json report written to {args.json}")

    if args.years_info:
        body = format_years_info(mods)
        if body:
            target = Path(args.years_info)
            section = f"\n--- {TOOL} scan {date.today().isoformat()} ---\n{body}\n"
            with target.open("a", encoding="utf-8") as handle:
                handle.write(section)
            print(f"years_info section appended to {args.years_info}")
        else:
            print("years_info: nothing to append (all scanned vehicles are supported)")

    if args.lua_suggest:
        print()
        print(format_lua_suggest(mods))

    if args.copy_unsupported:
        copied = copy_unsupported(mods, args.copy_unsupported)
        for name, action in copied:
            print(f"copy-unsupported: {name}: {action}")

    missing = sum(len(missing_vehicles(mod)) for mod in mods)
    if base_items is not None:
        missing += sum(1 for b in base_items if b["source"] == "none")
    if missing and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
