#!/usr/bin/env python3
"""Bundled app icons and the optional alternate mod-icon easter egg.

The master images live in ``Icons/`` next to this module.  The same folder is
installed as package data for wheel/source installs and copied beside the
frozen modules by the PyInstaller builds.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

ICON_DIR_NAME = "Icons"
MAIN_ICON_NAME = "MAINicon.png"
ALT_ICON_NAME = "ALTicon.png"
EASTER_EGG_ENV = "VYCOMPAT_EASTER_EGG"
EASTER_EGG_CHANCE = 0.10

_TRUTHY = {"1", "true", "yes", "on", "force", "always"}
_FALSY = {"0", "false", "no", "off", "never"}


def icon_dir():
    """Folder containing the bundled icon masters."""
    return Path(__file__).resolve().parent / ICON_DIR_NAME


def icon_path(name):
    return icon_dir() / name


def icon_bytes(name):
    path = icon_path(name)
    if not path.is_file():
        return None
    return path.read_bytes()


def main_icon_bytes():
    return icon_bytes(MAIN_ICON_NAME)


def alt_icon_bytes():
    return icon_bytes(ALT_ICON_NAME)


def alt_icon_available():
    return icon_path(ALT_ICON_NAME).is_file()


def icon_state(path):
    """Return ``main``, ``alt``, ``custom`` or ``missing`` for an icon file."""
    path = Path(path)
    if not path.is_file():
        return "missing"
    data = path.read_bytes()
    main = main_icon_bytes()
    alt = alt_icon_bytes()
    if main is not None and data == main:
        return "main"
    if alt is not None and data == alt:
        return "alt"
    return "custom"


def _env_force():
    value = os.environ.get(EASTER_EGG_ENV, "").strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    return None


def should_show_easter_egg(force=None, roll=None):
    """Decide the one-per-launch 10% sidebar easter egg.

    ``force`` (True/False) overrides the environment and random roll.  A
    ``roll`` of 0.0-1.0 can be supplied by tests; it is not used when forced.
    """
    if not alt_icon_available():
        return False
    if force is None:
        force = _env_force()
    if force is not None:
        return bool(force)
    if roll is None:
        roll = random.random()
    return roll < EASTER_EGG_CHANCE
