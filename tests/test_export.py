#!/usr/bin/env python3
"""Tests for the addon export helpers: add years, rebuild the ZIP, install."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vycompat  # noqa: E402
import vycompat_icons  # noqa: E402


LUA_TEMPLATE = """-- test addon
local MOD_VEHICLE_YEARS = {
    ["FS25_Pack/a"] = 1967,
}

local MOD_YEARS = {
    ["FS25_Old"] = 1965,
}

local BASE_GAME_YEARS = {
    ["base_data_vehicles_a_b_b"] = 2000,
}
"""

MODDESC_TEMPLATE = """<?xml version="1.0" encoding="utf-8" standalone="no" ?>
<modDesc descVersion="104">
    <author>Test</author>
    <version>{version}</version>
    <iconFilename>icon.dds</iconFilename>
    <title>
        <en>Vehicle Years Compatibility Tool</en>
    </title>
    <description>
        <en>
            <![CDATA[
Supported mods:
- FS25_Old (Old Mod) - 1965

Supported mods with per-vehicle years:
- FS25_Pack (Pack)
  - A - 1967

Supported base game vehicles:
- Something - 2000
            ]]>
        </en>
    </description>
</modDesc>
"""


def make_source(directory, version="1.0.4.0"):
    source = Path(directory)
    source.mkdir(parents=True, exist_ok=True)
    (source / "vehicle_years_addon.lua").write_text(LUA_TEMPLATE, encoding="utf-8")
    (source / "modDesc.xml").write_text(
        MODDESC_TEMPLATE.format(version=version), encoding="utf-8"
    )
    (source / "icon.dds").write_bytes(b"DDS fake")
    return source


class ScaffoldAddonTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_creates_valid_empty_mod_and_installs_zip(self):
        source = self.tmp / "source" / vycompat.ADDON_MOD_NAME
        install_dir = self.tmp / "mods"
        report = vycompat.scaffold_addon(source, install_dir=install_dir)

        self.assertTrue((source / "modDesc.xml").is_file())
        self.assertTrue((source / "vehicle_years_addon.lua").is_file())
        icon = source / "icon.png"
        self.assertTrue(icon.is_file())
        self.assertTrue(icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(icon.read_bytes(), vycompat_icons.main_icon_bytes())
        self.assertEqual(
            vycompat.parse_lua_tables(
                (source / "vehicle_years_addon.lua").read_text(encoding="utf-8")
            ),
            vycompat.EMPTY_TABLES,
        )
        moddesc = (source / "modDesc.xml").read_text(encoding="utf-8")
        self.assertIn("<en>Vehicle Years Compatibility Tool</en>", moddesc)
        self.assertIn("<iconFilename>icon.png</iconFilename>", moddesc)
        self.assertIn("<dependency>FS25_Vehicle_Years</dependency>", moddesc)
        self.assertIn("Supported mods:\n\nSupported mods", moddesc)

        zip_path = self.tmp / "source" / vycompat.ADDON_ZIP_NAME
        installed = install_dir / vycompat.ADDON_ZIP_NAME
        self.assertTrue(zip_path.is_file())
        self.assertTrue(installed.is_file())
        self.assertEqual(report["installed"], str(installed))
        with zipfile.ZipFile(installed) as zf:
            self.assertEqual(
                sorted(zf.namelist()),
                ["icon.png", "modDesc.xml", "vehicle_years_addon.lua"],
            )
            self.assertIn(
                "Vehicle Years Compatibility Tool",
                zf.read("modDesc.xml").decode(),
            )

    def test_blank_scaffold_supports_later_year_edits(self):
        source = self.tmp / "source" / vycompat.ADDON_MOD_NAME
        vycompat.scaffold_addon(source)
        plan = vycompat.plan_addon_years(
            source,
            mod_years={"FS25_New": 1999},
            description_mods=["- FS25_New (New Mod) - 1999"],
        )
        self.assertTrue(plan["changed"])
        self.assertEqual(plan["new_version"], "1.0.1.0")
        self.assertTrue(plan["description_updated"])
        self.assertEqual(
            vycompat.parse_lua_tables(plan["lua"])["MOD_YEARS"]["FS25_New"],
            1999,
        )
        self.assertIn("- FS25_New (New Mod) - 1999", plan["description"])

    def test_never_overwrites_an_existing_source_or_install(self):
        source = self.tmp / "source" / vycompat.ADDON_MOD_NAME
        source.mkdir(parents=True)
        (source / "existing.lua").write_text("-- keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            vycompat.scaffold_addon(source, install_dir=self.tmp / "mods")
        self.assertTrue((source / "existing.lua").is_file())

        clean = self.tmp / "clean" / vycompat.ADDON_MOD_NAME
        install_dir = self.tmp / "mods2"
        install_dir.mkdir()
        (install_dir / vycompat.ADDON_ZIP_NAME).write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            vycompat.scaffold_addon(clean, install_dir=install_dir)
        self.assertFalse(clean.exists())
        self.assertEqual(
            (install_dir / vycompat.ADDON_ZIP_NAME).read_bytes(), b"keep"
        )

    def test_install_existing_source_rebuilds_and_installs(self):
        source = make_source(self.tmp / vycompat.ADDON_MOD_NAME)
        install_dir = self.tmp / "mods"
        report = vycompat.install_addon_source(source, install_dir)
        self.assertEqual(
            report["installed"], str(install_dir / vycompat.ADDON_ZIP_NAME)
        )
        self.assertTrue(Path(report["zip"]).is_file())
        with zipfile.ZipFile(report["installed"]) as zf:
            self.assertIn("vehicle_years_addon.lua", zf.namelist())

    def test_extract_installed_zip_preserves_years_without_overwriting(self):
        source = make_source(self.tmp / vycompat.ADDON_MOD_NAME)
        installed = self.tmp / "mods" / vycompat.ADDON_ZIP_NAME
        installed.parent.mkdir()
        vycompat.build_addon_zip(source, installed)
        destination = self.tmp / "editable" / vycompat.ADDON_MOD_NAME

        report = vycompat.extract_addon_zip(installed, destination)

        self.assertEqual(report["source"], str(destination))
        self.assertTrue((destination / "modDesc.xml").is_file())
        self.assertTrue((destination / "icon.dds").is_file())
        tables = vycompat.parse_lua_tables(
            (destination / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        )
        self.assertEqual(tables["MOD_YEARS"]["FS25_Old"], 1965)
        with self.assertRaises(FileExistsError):
            vycompat.extract_addon_zip(installed, destination)

    def test_copy_unpacked_installed_addon_to_source(self):
        source = make_source(self.tmp / "mods" / vycompat.ADDON_MOD_NAME)
        (source / ".vycompat_history").mkdir()
        (source / ".vycompat_history" / "old.json").write_text(
            "{}", encoding="utf-8"
        )
        destination = self.tmp / "editable" / vycompat.ADDON_MOD_NAME

        report = vycompat.copy_addon_source(source, destination)

        self.assertEqual(report["source"], str(destination))
        tables = vycompat.parse_lua_tables(
            (destination / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        )
        self.assertEqual(tables["MOD_YEARS"]["FS25_Old"], 1965)
        self.assertFalse((destination / ".vycompat_history").exists())
        with self.assertRaises(FileExistsError):
            vycompat.copy_addon_source(source, destination)


class SetAddonIconTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_replaces_icon_rebuilds_and_installs_without_touching_years(self):
        source = make_source(self.tmp / vycompat.ADDON_MOD_NAME)
        original_lua = (source / "vehicle_years_addon.lua").read_text(
            encoding="utf-8"
        )
        install_dir = self.tmp / "mods"

        report = vycompat.set_addon_icon(
            source, vycompat_icons.alt_icon_bytes(), install_dir=install_dir
        )

        self.assertEqual(
            (source / "icon.png").read_bytes(),
            vycompat_icons.alt_icon_bytes(),
        )
        self.assertEqual(
            (source / "vehicle_years_addon.lua").read_text(encoding="utf-8"),
            original_lua,
        )
        moddesc = (source / "modDesc.xml").read_text(encoding="utf-8")
        self.assertIn("<iconFilename>icon.png</iconFilename>", moddesc)
        self.assertNotIn("1.0.5.0", moddesc)
        self.assertEqual(
            report["installed"], str(install_dir / vycompat.ADDON_ZIP_NAME)
        )
        self.assertTrue(Path(report["zip"]).is_file())
        with zipfile.ZipFile(report["installed"]) as zf:
            self.assertEqual(
                zf.read("icon.png"), vycompat_icons.alt_icon_bytes()
            )

    def test_rebuilds_without_installing(self):
        source = make_source(self.tmp / vycompat.ADDON_MOD_NAME)
        report = vycompat.set_addon_icon(
            source, vycompat_icons.main_icon_bytes()
        )
        self.assertIsNone(report["installed"])
        self.assertTrue(Path(report["zip"]).is_file())

    def test_rejects_non_png_data_without_writing(self):
        source = make_source(self.tmp / vycompat.ADDON_MOD_NAME)
        with self.assertRaises(ValueError):
            vycompat.set_addon_icon(source, b"not a png")
        self.assertFalse((source / "icon.png").exists())

    def test_moddesc_icon_element_can_be_inserted(self):
        text = "<modDesc><version>1.0.0.0</version></modDesc>"
        updated = vycompat.update_addon_moddesc_icon(text)
        self.assertIn("<iconFilename>icon.png</iconFilename>", updated)


class AddonSetupStateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_prefers_installed_zip_and_detects_unpacked_folder(self):
        mods = self.tmp / "mods"
        mods.mkdir()
        zip_path = mods / vycompat.ADDON_ZIP_NAME
        zip_path.write_bytes(b"zip")
        state = vycompat.addon_setup_state([mods])
        self.assertEqual(state["installed"], zip_path)
        self.assertFalse(state["needs_setup"])

        zip_path.unlink()
        folder = mods / vycompat.ADDON_MOD_NAME
        folder.mkdir()
        (folder / "vehicle_years_addon.lua").write_text(
            "local MOD_YEARS = {}\n", encoding="utf-8"
        )
        state = vycompat.addon_setup_state([mods])
        self.assertEqual(state["installed"], folder / "vehicle_years_addon.lua")
        self.assertFalse(state["needs_setup"])

    def test_resolve_addon_reads_installed_folder_tables(self):
        mods = self.tmp / "mods"
        mods.mkdir()
        source = mods / vycompat.ADDON_MOD_NAME
        source.mkdir()
        (source / "vehicle_years_addon.lua").write_text(
            'local MOD_YEARS = {\n    ["FS25_Test"] = 1999,\n}\n'
            "local MOD_VEHICLE_YEARS = {}\n"
            "local BASE_GAME_YEARS = {}\n",
            encoding="utf-8",
        )
        (source / "modDesc.xml").write_text(
            "<modDesc><version>2.0.0.0</version></modDesc>", encoding="utf-8"
        )
        tables, info = vycompat.resolve_addon("installed", [mods])
        self.assertEqual(info["kind"], "installed-folder")
        self.assertEqual(info["version"], "2.0.0.0")
        self.assertEqual(tables["MOD_YEARS"]["FS25_Test"], 1999)


class ValidateYearTest(unittest.TestCase):
    def test_accepts_valid_years(self):
        self.assertEqual(vycompat.validate_year("1965"), 1965)
        self.assertEqual(vycompat.validate_year(2030), 2030)
        self.assertEqual(vycompat.validate_year(" 1900 "), 1900)

    def test_rejects_invalid_years(self):
        for bad in ("", "abc", "1500", "1899", "2031", "19.65"):
            with self.assertRaises(ValueError):
                vycompat.validate_year(bad)


class BumpVersionTest(unittest.TestCase):
    def test_content_bump(self):
        self.assertEqual(vycompat.bump_version("1.0.4.0"), "1.0.5.0")
        self.assertEqual(vycompat.bump_version("2.3.9.7"), "2.3.10.7")

    def test_short_versions(self):
        self.assertEqual(vycompat.bump_version("1.0"), "1.1")
        self.assertEqual(vycompat.bump_version("1"), "2")


class UpdateAddonLuaTest(unittest.TestCase):
    def test_adds_new_entries(self):
        text, entries = vycompat.update_addon_lua(
            LUA_TEMPLATE,
            mod_years={"FS25_New": 1990},
            vehicle_years={"FS25_Pack/b": 1968},
        )
        tables = vycompat.parse_lua_tables(text)
        self.assertEqual(tables["MOD_YEARS"]["FS25_New"], 1990)
        self.assertEqual(tables["MOD_VEHICLE_YEARS"]["FS25_Pack/b"], 1968)
        # existing entries stay
        self.assertEqual(tables["MOD_YEARS"]["FS25_Old"], 1965)
        self.assertEqual(tables["BASE_GAME_YEARS"]["base_data_vehicles_a_b_b"], 2000)
        actions = {(entry["table"], entry["key"]): entry["action"] for entry in entries}
        self.assertEqual(actions[("MOD_YEARS", "FS25_New")], "added")
        self.assertEqual(actions[("MOD_VEHICLE_YEARS", "FS25_Pack/b")], "added")

    def test_updates_existing_entry(self):
        text, entries = vycompat.update_addon_lua(LUA_TEMPLATE, mod_years={"FS25_Old": 1970})
        self.assertEqual(vycompat.parse_lua_tables(text)["MOD_YEARS"]["FS25_Old"], 1970)
        self.assertEqual(entries[0]["action"], "updated")
        self.assertEqual(entries[0]["old_year"], 1965)
        # no duplicate key was inserted
        self.assertEqual(text.count('["FS25_Old"]'), 1)

    def test_unchanged_entry(self):
        text, entries = vycompat.update_addon_lua(LUA_TEMPLATE, mod_years={"FS25_Old": 1965})
        self.assertEqual(text, LUA_TEMPLATE)
        self.assertEqual(entries[0]["action"], "unchanged")

    def test_missing_table_raises(self):
        with self.assertRaises(ValueError):
            vycompat.update_addon_lua("local MOD_YEARS = {}\n", vehicle_years={"A/b": 1967})


class UpdateAddonDescriptionTest(unittest.TestCase):
    def test_mod_lines_inserted_into_right_section(self):
        text, updated = vycompat.update_addon_description(
            MODDESC_TEMPLATE, mod_lines=["- FS25_New (New Mod) - 1990"]
        )
        self.assertTrue(updated)
        self.assertIn("- FS25_New (New Mod) - 1990\n\nSupported mods with per-vehicle years:", text)
        # per-vehicle section untouched
        self.assertIn("- FS25_Old (Old Mod) - 1965\n- FS25_New (New Mod) - 1990", text)

    def test_per_vehicle_block_inserted(self):
        text, updated = vycompat.update_addon_description(
            MODDESC_TEMPLATE,
            per_vehicle=[("- FS25_New (New Mod)", ["  - Tractor X - 1990", "  - Plow Y - 1991"])],
        )
        self.assertTrue(updated)
        self.assertIn(
            "- FS25_New (New Mod)\n  - Tractor X - 1990\n  - Plow Y - 1991"
            "\n\nSupported base game vehicles:",
            text,
        )

    def test_missing_section_reports_not_updated(self):
        text, updated = vycompat.update_addon_description(
            "<modDesc><description>nothing here</description></modDesc>",
            mod_lines=["- X (Y) - 1990"],
        )
        self.assertFalse(updated)
        self.assertNotIn("- X (Y) - 1990", text)

    def test_version_update(self):
        text = vycompat.update_addon_moddesc_version(MODDESC_TEMPLATE, "1.0.5.0")
        self.assertIn("<version>1.0.5.0</version>", text)
        self.assertEqual(text.count("<version>"), 1)


class ExportAddonYearsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_full_export_with_install(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        install_dir = self.tmp / "mods"
        zip_path = self.tmp / "FS25_VehicleYears_CompatibilityTool.zip"

        report = vycompat.export_addon_years(
            source,
            mod_years={"FS25_New": 1990},
            vehicle_years={},
            description_mods=["- FS25_New (New Mod) - 1990"],
            install_dir=install_dir,
            zip_path=zip_path,
        )

        self.assertTrue(report["changed"])
        self.assertEqual(report["version"], "1.0.5.0")
        self.assertTrue(report["description_updated"])
        self.assertTrue(zip_path.is_file())
        installed = install_dir / vycompat.ADDON_ZIP_NAME
        self.assertTrue(installed.is_file())
        self.assertEqual(report["installed"], str(installed))
        self.assertEqual(installed.read_bytes(), zip_path.read_bytes())

        with zipfile.ZipFile(zip_path) as zf:
            names = sorted(zf.namelist())
            self.assertEqual(names, ["icon.dds", "modDesc.xml", "vehicle_years_addon.lua"])
            lua = zf.read("vehicle_years_addon.lua").decode()
            moddesc = zf.read("modDesc.xml").decode()
        self.assertIn('["FS25_New"] = 1990,', lua)
        self.assertEqual(vycompat.parse_lua_tables(lua)["MOD_YEARS"]["FS25_Old"], 1965)
        self.assertIn("<version>1.0.5.0</version>", moddesc)
        self.assertIn("- FS25_New (New Mod) - 1990", moddesc)

        # source files updated too
        self.assertIn(
            '["FS25_New"] = 1990,',
            (source / "vehicle_years_addon.lua").read_text(encoding="utf-8"),
        )

    def test_nothing_changes_when_year_already_present(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        before_lua = (source / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        before_desc = (source / "modDesc.xml").read_text(encoding="utf-8")
        zip_path = self.tmp / "FS25_VehicleYears_CompatibilityTool.zip"

        report = vycompat.export_addon_years(
            source, mod_years={"FS25_Old": 1965}, zip_path=zip_path
        )

        self.assertFalse(report["changed"])
        self.assertIsNone(report["zip"])
        self.assertFalse(zip_path.exists())
        self.assertEqual((source / "vehicle_years_addon.lua").read_text(encoding="utf-8"), before_lua)
        self.assertEqual((source / "modDesc.xml").read_text(encoding="utf-8"), before_desc)

    def test_update_existing_year(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        zip_path = self.tmp / "addon.zip"
        report = vycompat.export_addon_years(
            source, mod_years={"FS25_Old": 1966}, zip_path=zip_path
        )
        self.assertEqual(report["entries"][0]["action"], "updated")
        self.assertIn(
            '["FS25_Old"] = 1966,',
            (source / "vehicle_years_addon.lua").read_text(encoding="utf-8"),
        )

    def test_missing_addon_files_raise(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            vycompat.export_addon_years(empty, mod_years={"FS25_New": 1990})

    def test_zip_skips_tmp_and_hidden_files_and_keeps_nested_assets(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        (source / "leftover.tmp").write_text("x", encoding="utf-8")
        (source / ".hidden").write_text("x", encoding="utf-8")
        assets = source / "data" / "icons"
        assets.mkdir(parents=True)
        (assets / "nested.dds").write_bytes(b"asset")
        (source / ".vycompat_history").mkdir()
        (source / ".vycompat_history" / "old.zip").write_bytes(b"old")
        out = self.tmp / "out.zip"
        vycompat.build_addon_zip(source, out)
        with zipfile.ZipFile(out) as zf:
            names = sorted(zf.namelist())
        self.assertEqual(
            names,
            [
                "data/icons/nested.dds",
                "icon.dds",
                "modDesc.xml",
                "vehicle_years_addon.lua",
            ],
        )

    def test_export_uses_default_zip_location(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        report = vycompat.export_addon_years(source, mod_years={"FS25_New": 1990})
        self.assertEqual(
            report["zip"], str(self.tmp / "FS25_VehicleYears_CompatibilityTool.zip")
        )
        self.assertTrue(Path(report["zip"]).is_file())
        self.assertIsNone(report["installed"])


class PlanAddonYearsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_plan_previews_without_writing(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        lua_path = source / "vehicle_years_addon.lua"
        desc_path = source / "modDesc.xml"
        before_lua = lua_path.read_text(encoding="utf-8")
        before_desc = desc_path.read_text(encoding="utf-8")

        plan = vycompat.plan_addon_years(
            source,
            mod_years={"FS25_New": 1990},
            description_mods=["- FS25_New (New Mod) - 1990"],
        )

        self.assertTrue(plan["changed"])
        self.assertEqual(plan["version"], "1.0.4.0")
        self.assertEqual(plan["new_version"], "1.0.5.0")
        self.assertTrue(plan["description_updated"])
        self.assertIn('["FS25_New"] = 1990', plan["lua"])
        self.assertIn("<version>1.0.5.0</version>", plan["description"])
        # Nothing was written and no ZIP was produced.
        self.assertEqual(lua_path.read_text(encoding="utf-8"), before_lua)
        self.assertEqual(desc_path.read_text(encoding="utf-8"), before_desc)
        self.assertFalse(
            (source.parent / vycompat.ADDON_ZIP_NAME).exists()
        )

    def test_plan_reports_unchanged_and_updated_entries(self):
        source = make_source(self.tmp / "FS25_VehicleYears_CompatibilityTool")
        same = vycompat.plan_addon_years(
            source, mod_years={"FS25_Old": 1965}
        )
        self.assertFalse(same["changed"])
        self.assertEqual(same["entries"][0]["action"], "unchanged")
        self.assertEqual(same["entries"][0]["old_year"], 1965)
        self.assertEqual(same["new_version"], same["version"])
        self.assertFalse(same["description_updated"])

        changed = vycompat.plan_addon_years(
            source, mod_years={"FS25_Old": 1966}
        )
        self.assertTrue(changed["changed"])
        self.assertEqual(changed["entries"][0]["action"], "updated")
        self.assertEqual(changed["entries"][0]["old_year"], 1965)
        self.assertEqual(changed["entries"][0]["year"], 1966)

    def test_plan_missing_files_raise(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            vycompat.plan_addon_years(empty, mod_years={"FS25_New": 1990})


def scan_vehicle(key, name, source="none", category="tractors"):
    return {
        "addon_vehicle_key": key,
        "name": name,
        "xml": key.partition("/")[2] + ".xml",
        "source": source,
        "category": category,
    }


def scan_mod(env, file_name, title, vehicles):
    return {
        "file": file_name,
        "custom_environment": env,
        "title": title,
        "vehicles": vehicles,
    }


class MissingTemplateTest(unittest.TestCase):
    def test_lists_whole_mod_and_missing_vehicles(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [scan_vehicle("FS25_A/a", "A tractor")],
            ),
            scan_mod(
                "FS25_B", "FS25_B.zip", "Mod B",
                [
                    scan_vehicle("FS25_B/x", "X", source="vy"),
                    scan_vehicle("FS25_B/y", "Y"),
                ],
            ),
            scan_mod(
                "FS25_C", "FS25_C.zip", "Mod C",
                [scan_vehicle("FS25_C/z", "Z", source="own")],
            ),
        ]
        text, count = vycompat.missing_template(mods)
        self.assertEqual(count, 4)
        self.assertEqual(text.count(" = ?"), 4)
        self.assertIn("FS25_A = ?", text)
        self.assertIn("FS25_A/a = ?", text)
        self.assertIn("FS25_B = ?", text)
        self.assertIn("FS25_B/y = ?", text)
        self.assertNotIn("FS25_B/x = ?", text)
        self.assertNotIn("FS25_C", text)
        self.assertIn("# Mod A (FS25_A.zip)", text)
        self.assertIn("A tractor", text)

    def test_empty_when_everything_supported(self):
        mods = [scan_mod("FS25_C", "FS25_C.zip", "Mod C", [scan_vehicle("FS25_C/z", "Z", "own")])]
        self.assertEqual(vycompat.missing_template(mods), ("", 0))

    def test_skips_mods_without_environment(self):
        mods = [scan_mod(None, "FS25_X.zip", "X", [scan_vehicle("FS25_X/a", "A")])]
        self.assertEqual(vycompat.missing_template(mods), ("", 0))


class ChatGptTemplateTest(unittest.TestCase):
    def test_prompt_is_included_verbatim(self):
        mods = [
            scan_mod("FS25_A", "FS25_A.zip", "Mod A", [scan_vehicle("FS25_A/a", "A")])
        ]
        text, count = vycompat.chatgpt_template(mods)
        prompt_head = vycompat.CHATGPT_VERIFICATION_PROMPT.split(
            vycompat.CHATGPT_ITEM_MARKER
        )[0]
        self.assertTrue(text.startswith(prompt_head))
        self.assertIn(vycompat.CHATGPT_ITEM_MARKER, text)
        self.assertNotIn(vycompat.CHATGPT_ITEM_PLACEHOLDER, text)
        self.assertIn("`certainty` must be `sure`, `unsure`, or `unknown`.", text)
        self.assertIn(
            "A guess is speculative and must not be presented as a verified fact.",
            text,
        )
        self.assertIn("MOD_KEY/ITEM_KEY = YEAR | CERTAINTY | GUESS", text)
        self.assertIn("split an entry across lines", text)
        self.assertEqual(count, 1)

    def test_all_item_types_are_listed(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [
                    scan_vehicle("FS25_A/tractor", "Tractor", category="tractors"),
                    scan_vehicle("FS25_A/baler", "Baler", category="balers"),
                    scan_vehicle("FS25_A/trailer", "Trailer", category="trailers"),
                    scan_vehicle(
                        "FS25_A/handtool", "Shovel", category="handToolsMisc"
                    ),
                ],
            )
        ]
        text, count = vycompat.chatgpt_template(mods)
        self.assertEqual(count, 4)
        for key in (
            "FS25_A/tractor",
            "FS25_A/baler",
            "FS25_A/trailer",
            "FS25_A/handtool",
        ):
            self.assertIn(f"{key} = ?", text)

    def test_only_individual_items_and_never_whole_mod(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [
                    scan_vehicle("FS25_A/x", "X", source="vy"),
                    scan_vehicle("FS25_A/y", "Y"),
                ],
            ),
            scan_mod(
                "FS25_B", "FS25_B.zip", "Mod B",
                [scan_vehicle("FS25_B/z", "Z", source="own")],
            ),
        ]
        text, count = vycompat.chatgpt_template(mods)
        self.assertEqual(count, 1)
        self.assertNotIn("FS25_A = ?", text)
        self.assertNotIn("FS25_B = ?", text)
        listing = text.split(vycompat.CHATGPT_ITEM_MARKER, 1)[1]
        item_lines = [line.strip() for line in listing.splitlines() if line.strip()]
        self.assertTrue(item_lines)
        for line in item_lines:
            self.assertIn("/", line)
            self.assertTrue(line.endswith(" = ?"))
            self.assertEqual(line.count("="), 1)

    def test_empty_when_nothing_missing(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [scan_vehicle("FS25_A/a", "A", source="vy")],
            )
        ]
        self.assertEqual(vycompat.chatgpt_template(mods), ("", 0))

    def test_strip_keeps_only_item_lines(self):
        mods = [
            scan_mod("FS25_A", "FS25_A.zip", "Mod A", [scan_vehicle("FS25_A/a", "A")])
        ]
        text, _ = vycompat.chatgpt_template(mods)
        self.assertEqual(vycompat.strip_verification_prompt(text), "FS25_A/a = ?")

    def test_strip_leaves_plain_text_alone(self):
        self.assertEqual(
            vycompat.strip_verification_prompt("FS25_A = 1965\n"), "FS25_A = 1965\n"
        )

    def test_round_trip_through_parser(self):
        mods = [
            scan_mod("FS25_A", "FS25_A.zip", "Mod A", [scan_vehicle("FS25_A/a", "A")]),
            scan_mod(
                "FS25_B", "FS25_B.zip", "Mod B",
                [scan_vehicle("FS25_B/y", "Y", category="balers")],
            ),
        ]
        text, count = vycompat.chatgpt_template(mods)
        years = iter(range(1960, 2030))
        filled = []
        for line in text.splitlines():
            if line.endswith(" = ?"):
                line = line[:-4] + f" = {next(years)}"
            filled.append(line)
        parsed = vycompat.parse_years_text("\n".join(filled))
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["pending"], [])
        self.assertEqual(parsed["mod_years"], {})
        self.assertEqual(len(parsed["vehicle_years"]), count)
        self.assertEqual(parsed["vehicle_years"], {"FS25_A/a": 1960, "FS25_B/y": 1961})


class ParseYearsTextTest(unittest.TestCase):
    def test_parses_mod_and_vehicle_years(self):
        text = "# comment\nFS25_A = 1965\nFS25_B/y = 1970  # trailing comment\n\n"
        parsed = vycompat.parse_years_text(text)
        self.assertEqual(parsed["mod_years"], {"FS25_A": 1965})
        self.assertEqual(parsed["vehicle_years"], {"FS25_B/y": 1970})
        self.assertEqual(parsed["pending"], [])
        self.assertEqual(parsed["errors"], [])

    def test_question_marks_are_pending(self):
        parsed = vycompat.parse_years_text("FS25_A = ?\nFS25_B/y = ?  # x\nFS25_C = \n")
        self.assertEqual(parsed["pending"], ["FS25_A", "FS25_B/y", "FS25_C"])
        self.assertEqual(parsed["mod_years"], {})
        self.assertEqual(parsed["vehicle_years"], {})
        self.assertEqual(parsed["errors"], [])

    def test_chatgpt_columns_and_unknown_are_supported(self):
        text = (
            "FS25_A = 1988 | sure | none\n"
            "FS25_B/b = unknown | unknown | none\n"
            "FS25_C/c = UNKNOWN | unsure | 1975\n"
            "FS25_D/d = 1990|sure|none\n"
        )
        parsed = vycompat.parse_years_text(text)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["mod_years"], {"FS25_A": 1988})
        self.assertEqual(parsed["vehicle_years"], {"FS25_D/d": 1990})
        self.assertEqual(parsed["pending"], ["FS25_B/b", "FS25_C/c"])

    def test_parenthesised_chatgpt_output_is_supported(self):
        text = (
            "FS25_A = (year: 1983, certainty: unsure, guess: none)\n"
            "FS25_B/b = {year: unknown, certainty: unknown, guess: none)\n"
            "FS25_C/c = year: 1990\n"
            "FS25_D/d = (1985, sure, none)\n"
        )
        parsed = vycompat.parse_years_text(text)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["mod_years"], {"FS25_A": 1983})
        self.assertEqual(
            parsed["vehicle_years"], {"FS25_C/c": 1990, "FS25_D/d": 1985}
        )
        self.assertEqual(parsed["pending"], ["FS25_B/b"])

    def test_wrapped_keys_are_pending_and_orphan_values_ignored(self):
        text = (
            "FS25_A/a = (year: 1983, certainty: sure, guess: none)\n"
            "FS25_A/b\n"
            "FS25_A/c\n"
            "{year: unknown, certainty: unknown, guess: none)\n"
            "{year: unknown, certainty: unknown, guess: none)\n"
        )
        parsed = vycompat.parse_years_text(text)
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["vehicle_years"], {"FS25_A/a": 1983})
        self.assertEqual(parsed["pending"], ["FS25_A/b", "FS25_A/c"])

    def test_invalid_years_are_errors(self):
        parsed = vycompat.parse_years_text("FS25_A = abc\nFS25_B = 1800\nFS25_C = 1965\n")
        self.assertEqual(len(parsed["errors"]), 2)
        self.assertEqual(parsed["mod_years"], {"FS25_C": 1965})

    def test_missing_equals_is_error(self):
        parsed = vycompat.parse_years_text("FS25_A 1965\n")
        self.assertEqual(len(parsed["errors"]), 1)
        self.assertEqual(parsed["mod_years"], {})

    def test_normalizes_vehicle_keys(self):
        parsed = vycompat.parse_years_text(
            "FS25_A/vehicles\\Tractor.xml = 1965\nFS25_A/./other.xml = 1966\n"
        )
        self.assertEqual(
            parsed["vehicle_years"],
            {"FS25_A/vehicles/Tractor": 1965, "FS25_A/other": 1966},
        )

    def test_duplicate_keys_last_wins(self):
        parsed = vycompat.parse_years_text("FS25_A = 1965\nFS25_A = 1966\n")
        self.assertEqual(parsed["mod_years"], {"FS25_A": 1966})

    def test_template_round_trip(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [scan_vehicle("FS25_A/a", "A tractor")],
            ),
            scan_mod(
                "FS25_B", "FS25_B.zip", "Mod B",
                [
                    scan_vehicle("FS25_B/x", "X", source="vy"),
                    scan_vehicle("FS25_B/y", "Y"),
                ],
            ),
        ]
        text, count = vycompat.missing_template(mods)
        years = iter(range(1960, 2030))
        filled = []
        for line in text.splitlines():
            if "=" in line and not line.strip().startswith("#"):
                line = line.replace("?", str(next(years)), 1)
            filled.append(line)
        parsed = vycompat.parse_years_text("\n".join(filled))
        self.assertEqual(parsed["errors"], [])
        self.assertEqual(parsed["pending"], [])
        self.assertEqual(
            len(parsed["mod_years"]) + len(parsed["vehicle_years"]), count
        )


class DescriptionEntriesTest(unittest.TestCase):
    def test_builds_mod_and_vehicle_lines(self):
        mods = [
            scan_mod(
                "FS25_A", "FS25_A.zip", "Mod A",
                [scan_vehicle("FS25_A/a", "Tractor A")],
            )
        ]
        description_mods, description_vehicles = vycompat.description_entries(
            {"FS25_A": 1965}, {"FS25_A/a": 1966}, mods
        )
        self.assertEqual(description_mods, ["- FS25_A (Mod A) - 1965"])
        self.assertEqual(
            description_vehicles, [("- FS25_A (Mod A)", ["  - Tractor A - 1966"])]
        )

    def test_unknown_mod_falls_back_to_key(self):
        description_mods, description_vehicles = vycompat.description_entries(
            {"FS25_X": 1965}, {"FS25_X/deep/t.xml": 1966}, []
        )
        self.assertEqual(description_mods, ["- FS25_X (FS25_X) - 1965"])
        self.assertEqual(
            description_vehicles, [("- FS25_X (FS25_X)", ["  - deep/t.xml - 1966"])]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
