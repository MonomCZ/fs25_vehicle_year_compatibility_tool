#!/usr/bin/env python3
"""Local snapshots and undo for the compatibility-addon source.

The GUI keeps a timestamped copy of the addon source before every confirmed
export.  Snapshots live in
``FS25_VehicleYears_CompatibilityTool/.vycompat_history`` and
are deliberately excluded from the addon ZIP (``build_addon_zip`` only packs
top-level files).  Restoring a snapshot:
  - snapshots the current source first, so the undo itself can be undone,
  - restores the top-level source files,
  - rebuilds the addon ZIP,
  - installs it only when the caller explicitly passes ``install_dir``.

Nothing here touches the game mods folder unless the caller asks for it.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import vycompat as vy

HISTORY_DIR_NAME = ".vycompat_history"


def history_path(source_dir, history_dir=None):
    """Return the snapshot directory for an addon source folder."""
    if history_dir is not None:
        return Path(history_dir)
    return Path(source_dir) / HISTORY_DIR_NAME


def _addon_version(source_dir):
    moddesc = Path(source_dir) / vy.ADDON_MODDESC_NAME
    try:
        text = moddesc.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "unknown"
    match = re.search(r"<version>([^<]+)</version>", text)
    return match.group(1).strip() if match else "unknown"


def _require_source(source_dir):
    source = Path(source_dir)
    if not (source / vy.ADDON_LUA_NAME).is_file():
        raise FileNotFoundError(
            f"addon Lua not found: {source / vy.ADDON_LUA_NAME}"
        )
    if not (source / vy.ADDON_MODDESC_NAME).is_file():
        raise FileNotFoundError(
            f"addon modDesc not found: {source / vy.ADDON_MODDESC_NAME}"
        )
    return source


def snapshot_addon(source_dir, reason="addon export", history_dir=None):
    """Copy the current addon source into a timestamped history archive.

    Returns metadata for the snapshot.  Raises when the source is missing or
    cannot be archived.  The caller should abort the edit when this raises.
    """
    source = _require_source(source_dir)
    history = history_path(source, history_dir)
    history.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    stamp = now.strftime("%Y%m%d_%H%M%S_%f")
    archive = history / f"{stamp}.zip"
    vy.build_addon_zip(source, archive)
    version = _addon_version(source)
    created = now.isoformat(timespec="seconds")
    manifest = {
        "created": created,
        "version": version,
        "reason": str(reason),
        "archive": archive.name,
    }
    manifest_path = history / f"{stamp}.json"
    temp = manifest_path.with_name(manifest_path.name + ".tmp")
    temp.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(manifest_path)
    return {
        "path": str(archive),
        "manifest": str(manifest_path),
        "created": created,
        "version": version,
        "reason": str(reason),
    }


def list_addon_snapshots(source_dir, history_dir=None):
    """Return snapshots newest first; malformed manifests are ignored."""
    history = history_path(source_dir, history_dir)
    if not history.is_dir():
        return []
    snapshots = []
    for manifest_path in history.glob("*.json"):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        archive_name = data.get("archive") or f"{manifest_path.stem}.zip"
        if Path(str(archive_name)).name != str(archive_name):
            continue
        archive = history / archive_name
        if not archive.is_file():
            continue
        snapshots.append(
            {
                "path": str(archive),
                "manifest": str(manifest_path),
                "created": str(data.get("created") or manifest_path.stem),
                "version": str(data.get("version") or "unknown"),
                "reason": str(data.get("reason") or "addon export"),
            }
        )
    snapshots.sort(
        key=lambda item: (item["created"], Path(item["path"]).name),
        reverse=True,
    )
    return snapshots


def _checked_infos(archive):
    """Validate that an archive only contains top-level regular files."""
    infos = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            if info.is_dir():
                continue
            if (
                not name
                or name in (".", "..")
                or name.startswith(".")
                or "/" in name
                or "\\" in name
            ):
                raise ValueError(f"unsafe path in addon snapshot: {name!r}")
            infos.append(info)
    if not infos:
        raise ValueError("addon snapshot is empty")
    return infos


def restore_addon_snapshot(source_dir, snapshot_path, zip_path=None,
                           install_dir=None, history_dir=None):
    """Restore one snapshot, snapshot the current state, and rebuild the ZIP.

    ``install_dir`` is opt-in.  When omitted the rebuilt ZIP stays next to the
    addon source and the game mods folder is not touched.
    """
    source = _require_source(source_dir)
    snapshot = Path(snapshot_path)
    if not snapshot.is_file():
        raise FileNotFoundError(f"addon snapshot not found: {snapshot}")
    _checked_infos(snapshot)

    history = history_path(source, history_dir)
    previous = snapshot_addon(
        source,
        reason=f"Before restoring {snapshot.name}",
        history_dir=history,
    )

    history.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restore_", dir=history) as temp_dir:
        temp = Path(temp_dir)
        with zipfile.ZipFile(snapshot) as zf:
            zf.extractall(temp)
        restored_names = set()
        for file in sorted(temp.iterdir()):
            if not file.is_file() or file.name.startswith("."):
                continue
            shutil.copy2(file, source / file.name)
            restored_names.add(file.name)
        if not restored_names:
            raise ValueError("addon snapshot has no restorable files")
        # Remove top-level files that were not part of the snapshot.  Hidden
        # files and the history directory itself are left alone.
        for item in source.iterdir():
            if (
                item.is_file()
                and not item.name.startswith(".")
                and item.name not in restored_names
                and not item.name.endswith(".tmp")
            ):
                item.unlink()

    zip_target = (
        Path(zip_path) if zip_path else source.parent / vy.ADDON_ZIP_NAME
    )
    vy.build_addon_zip(source, zip_target)
    installed = None
    if install_dir is not None:
        install_dir = Path(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)
        installed_path = install_dir / vy.ADDON_ZIP_NAME
        shutil.copy2(zip_target, installed_path)
        installed = str(installed_path)
    return {
        "restored": str(snapshot),
        "previous_snapshot": previous["path"],
        "version": _addon_version(source),
        "zip": str(zip_target),
        "installed": installed,
    }
