#!/usr/bin/env python3
"""Tests for bundled icons and the alternate-icon easter egg."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vycompat_icons as icons  # noqa: E402


class BundledIconTest(unittest.TestCase):
    def test_main_and_alt_are_valid_pngs(self):
        for name in (icons.MAIN_ICON_NAME, icons.ALT_ICON_NAME):
            data = icons.icon_bytes(name)
            self.assertIsNotNone(data, name)
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), name)

    def test_windows_icon_is_a_valid_ico(self):
        path = icons.icon_path("appicon.ico")
        self.assertTrue(path.is_file())
        self.assertTrue(path.read_bytes().startswith(b"\x00\x00\x01\x00"))

    def test_icon_state_recognises_main_alt_and_custom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "icon.png"
            path.write_bytes(icons.main_icon_bytes())
            self.assertEqual(icons.icon_state(path), "main")
            path.write_bytes(icons.alt_icon_bytes())
            self.assertEqual(icons.icon_state(path), "alt")
            path.write_bytes(b"\x89PNG\r\n\x1a\ncustom")
            self.assertEqual(icons.icon_state(path), "custom")
            path.unlink()
            self.assertEqual(icons.icon_state(path), "missing")


class EasterEggTest(unittest.TestCase):
    def test_force_overrides_the_roll(self):
        self.assertTrue(icons.should_show_easter_egg(force=True, roll=1.0))
        self.assertFalse(icons.should_show_easter_egg(force=False, roll=0.0))

    def test_roll_threshold_is_ten_percent(self):
        env = {icons.EASTER_EGG_ENV: ""}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop(icons.EASTER_EGG_ENV, None)
            self.assertTrue(icons.should_show_easter_egg(force=None, roll=0.0))
            self.assertTrue(icons.should_show_easter_egg(force=None, roll=0.099))
            self.assertFalse(icons.should_show_easter_egg(force=None, roll=0.10))
            self.assertFalse(icons.should_show_easter_egg(force=None, roll=1.0))

    def test_environment_can_force_or_disable(self):
        with mock.patch.dict(
            os.environ, {icons.EASTER_EGG_ENV: "1"}, clear=False
        ):
            self.assertTrue(icons.should_show_easter_egg(roll=1.0))
        with mock.patch.dict(
            os.environ, {icons.EASTER_EGG_ENV: "off"}, clear=False
        ):
            self.assertFalse(icons.should_show_easter_egg(roll=0.0))
        with mock.patch.dict(
            os.environ, {icons.EASTER_EGG_ENV: "maybe"}, clear=False
        ):
            self.assertTrue(icons.should_show_easter_egg(roll=0.0))

    def test_missing_alt_icon_never_shows_the_button(self):
        with mock.patch.object(
            icons, "alt_icon_available", return_value=False
        ):
            self.assertFalse(icons.should_show_easter_egg(force=True))


if __name__ == "__main__":
    unittest.main()
