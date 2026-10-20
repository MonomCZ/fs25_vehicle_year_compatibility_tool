#!/usr/bin/env python3
"""Tests for local addon snapshots, history listing and undo."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vycompat  # noqa: E402
import vycompat_history as history  # noqa: E402


LUA = """local MOD_VEHICLE_YEARS = {
}

local MOD_YEARS = {
    ["FS25_Old"] = 1965,
}

local BASE_GAME_YEARS = {
}
"""

MODDESC = """<modDesc><version>1.0.4.0</version><description><en><![CDATA[
Supported mods:
- FS25_Old (Old) - 1965

]]></en></description></modDesc>"""


def make_source(tmp):
    source = Path(tmp) / "FS25_VehicleYears_CompatibilityTool"
    source.mkdir()
    (source / "vehicle_years_addon.lua").write_text(LUA, encoding="utf-8")
    (source / "modDesc.xml").write_text(MODDESC, encoding="utf-8")
    (source / "icon_VY.dds").write_bytes(b"dds")
    return source


class AddonHistoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.source = make_source(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_snapshot_creates_archive_and_manifest(self):
        snapshot = history.snapshot_addon(self.source, reason="unit test")
        archive = Path(snapshot["path"])
        manifest = Path(snapshot["manifest"])
        self.assertTrue(archive.is_file())
        self.assertTrue(manifest.is_file())
        self.assertEqual(snapshot["version"], "1.0.4.0")
        self.assertEqual(snapshot["reason"], "unit test")
        with zipfile.ZipFile(archive) as zf:
            self.assertEqual(
                sorted(zf.namelist()),
                ["icon_VY.dds", "modDesc.xml", "vehicle_years_addon.lua"],
            )

        listed = history.list_addon_snapshots(self.source)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["path"], snapshot["path"])
        self.assertEqual(listed[0]["reason"], "unit test")

    def test_restore_undoes_source_and_rebuilds_zip(self):
        snapshot = history.snapshot_addon(self.source, reason="before edit")
        (self.source / "vehicle_years_addon.lua").write_text(
            LUA.replace('["FS25_Old"] = 1965', '["FS25_Old"] = 1970'),
            encoding="utf-8",
        )
        (self.source / "modDesc.xml").write_text(
            MODDESC.replace("1.0.4.0", "1.0.5.0"), encoding="utf-8"
        )

        report = history.restore_addon_snapshot(
            self.source, snapshot["path"]
        )

        restored_lua = (self.source / "vehicle_years_addon.lua").read_text(
            encoding="utf-8"
        )
        self.assertIn('["FS25_Old"] = 1965', restored_lua)
        self.assertNotIn('["FS25_Old"] = 1970', restored_lua)
        self.assertEqual(report["version"], "1.0.4.0")
        self.assertTrue(Path(report["zip"]).is_file())
        self.assertIsNone(report["installed"])
        self.assertTrue(Path(report["previous_snapshot"]).is_file())

        # The current state was snapshotted before the restore, so the undo
        # itself can be undone.
        listed = history.list_addon_snapshots(self.source)
        self.assertEqual(len(listed), 2)
        self.assertTrue(
            any("Before restoring" in item["reason"] for item in listed)
        )

    def test_restore_only_installs_when_asked(self):
        snapshot = history.snapshot_addon(self.source)
        (self.source / "vehicle_years_addon.lua").write_text(
            LUA.replace('["FS25_Old"] = 1965', '["FS25_Old"] = 1970'),
            encoding="utf-8",
        )
        install_dir = self.tmp / "mods"

        report = history.restore_addon_snapshot(
            self.source, snapshot["path"], install_dir=install_dir
        )

        self.assertEqual(
            report["installed"], str(install_dir / vycompat.ADDON_ZIP_NAME)
        )
        self.assertTrue(
            (install_dir / vycompat.ADDON_ZIP_NAME).is_file()
        )
        with zipfile.ZipFile(install_dir / vycompat.ADDON_ZIP_NAME) as zf:
            self.assertIn("vehicle_years_addon.lua", zf.namelist())

    def test_restore_rejects_unsafe_archive(self):
        bad = self.tmp / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("../evil.lua", "bad")
        with self.assertRaises(ValueError):
            history.restore_addon_snapshot(self.source, bad)
        self.assertIn(
            '["FS25_Old"] = 1965',
            (self.source / "vehicle_years_addon.lua").read_text(encoding="utf-8"),
        )

    def test_missing_source_and_snapshot_raise(self):
        with self.assertRaises(FileNotFoundError):
            history.snapshot_addon(self.tmp / "missing")
        with self.assertRaises(FileNotFoundError):
            history.restore_addon_snapshot(
                self.source, self.tmp / "missing.zip"
            )

    def test_empty_history(self):
        self.assertEqual(history.list_addon_snapshots(self.source), [])
        history_dir = history.history_path(self.source)
        history_dir.mkdir()
        (history_dir / "not-json.json").write_text("{", encoding="utf-8")
        (history_dir / "array.json").write_text("[]", encoding="utf-8")
        (history_dir / "null.json").write_text("null", encoding="utf-8")
        self.assertEqual(history.list_addon_snapshots(self.source), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
