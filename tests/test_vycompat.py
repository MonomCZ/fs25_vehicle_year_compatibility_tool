#!/usr/bin/env python3
"""Tests for the compatibility tool core (stdlib unittest, synthetic mod ZIPs)."""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vycompat  # noqa: E402  (import after sys.path tweak)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def moddesc(title="Test Mod", desc_version=93, env=None, items=()):
    env_line = f"  <customEnvironment>{env}</customEnvironment>\n" if env else ""
    item_lines = "".join(
        f'  <storeItem rootNode="{root_node}" xmlFilename="{xml}"/>\n'
        for xml, root_node in items
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<modDesc descVersion="{desc_version}">
  <version>1.0.0.0</version>
{env_line}  <title><en>{title}</en></title>
  <storeItems>
{item_lines}  </storeItems>
</modDesc>
"""


def vehicle_xml(name, category="tractors", brand="TEST", year=None, tag="vehicle"):
    year_line = f"    <year>{year}</year>\n" if year is not None else ""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<{tag} type="tractor">
  <storeData>
    <name><en>{name}</en></name>
    <brand>{brand}</brand>
    <category>{category}</category>
{year_line}  </storeData>
</{tag}>
"""


def write_zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def make_mod(directory, name, items, desc_version=93, env=None, title="Test Mod"):
    """items: list of (xml file name, vehicle name, kwargs) tuples."""
    files = {}
    store_items = []
    for item in items:
        xml_file, veh_name = item[0], item[1]
        kwargs = item[2] if len(item) > 2 else {}
        files[xml_file] = vehicle_xml(veh_name, **kwargs)
        store_items.append((xml_file, "vehicle"))
    files["modDesc.xml"] = moddesc(title=title, desc_version=desc_version, env=env, items=store_items)
    path = Path(directory) / f"{name}.zip"
    write_zip(path, files)
    return path


def fake_addon(mod_years=None, per_vehicle=None, base=None):
    return {
        "MOD_YEARS": mod_years or {},
        "MOD_VEHICLE_YEARS": per_vehicle or {},
        "BASE_GAME_YEARS": base or {},
    }


class VycompatTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # -- parsing helpers ---------------------------------------------------

    def test_parse_lua_tables(self):
        lua = """
-- header comment
local MOD_VEHICLE_YEARS = {
    -- per vehicle
    ["A/B"] = 1967,
    ["A/C"] = 1968,
}

local MOD_YEARS = {
    ["FS25_X"] = 1965, -- inline comment
}

local BASE_GAME_YEARS = {
    ["base_data_vehicles_brand_model_model"] = 2023,
}

local other = {
    ["not_this"] = 1,
}
"""
        tables = vycompat.parse_lua_tables(lua)
        self.assertEqual(tables["MOD_VEHICLE_YEARS"], {"A/B": 1967, "A/C": 1968})
        self.assertEqual(tables["MOD_YEARS"], {"FS25_X": 1965})
        self.assertEqual(
            tables["BASE_GAME_YEARS"], {"base_data_vehicles_brand_model_model": 2023}
        )

    def test_parse_lua_tables_missing_table(self):
        tables = vycompat.parse_lua_tables("local MOD_YEARS = {}\n")
        self.assertEqual(tables["MOD_YEARS"], {})
        self.assertEqual(tables["MOD_VEHICLE_YEARS"], {})

    def test_blank_addon_template_has_empty_tables(self):
        tables = vycompat.parse_lua_tables(vycompat.addon_template.BLANK_LUA)
        self.assertEqual(tables, vycompat.EMPTY_TABLES)

    def test_source_dir_env_override(self):
        override = self.tmp / "custom-addon"
        with mock.patch.dict(
            os.environ, {"VYCOMPAT_ADDON_DIR": str(override)}, clear=False
        ):
            self.assertEqual(vycompat.default_source_addon_dir(), override)

    def test_key_normalization(self):
        self.assertEqual(vycompat.norm_rel("xml/Example.xml"), "xml/Example")
        self.assertEqual(vycompat.norm_rel(".\\scripts\\x.XML"), "scripts/x")
        self.assertEqual(vycompat.norm_rel("./Z2511.xml"), "Z2511")
        self.assertEqual(vycompat.mod_vy_key("FS25_Mod", "vehicles/x/a.xml"), "FS25_Mod_vehicles_x_a")
        self.assertEqual(vycompat.base_key("$data/vehicles/brand/model/model.xml"),
                         "base_data_vehicles_brand_model_model")
        self.assertEqual(vycompat.base_key("data/vehicles/brand/model/model.xml"),
                         "base_data_vehicles_brand_model_model")

    def test_source_addon_env_override(self):
        source = self.tmp / "custom_addon"
        source.mkdir()
        with mock.patch.dict(os.environ, {"VYCOMPAT_ADDON_DIR": str(source)}):
            self.assertEqual(vycompat.default_source_addon_dir(), source)

    # -- mod scanning ------------------------------------------------------

    def test_mod_supported_via_addon_mod_year(self):
        make_mod(self.tmp, "FS25_Test", [("a.xml", "Tractor A")])
        addon = fake_addon(mod_years={"FS25_Test": 1970})
        result = vycompat.scan_mod(self.tmp / "FS25_Test.zip", addon, {})
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["vehicles"][0]["source"], "addon-mod")
        self.assertEqual(result["vehicles"][0]["year"], 1970)

    def test_mod_partial_via_addon_per_vehicle(self):
        make_mod(self.tmp, "FS25_Pack", [("a.xml", "Tractor A"), ("xml/b.xml", "Tractor B")])
        addon = fake_addon(per_vehicle={"FS25_Pack/xml/b": 1968})
        result = vycompat.scan_mod(self.tmp / "FS25_Pack.zip", addon, {})
        self.assertEqual(result["status"], "partial")
        missing = vycompat.missing_vehicles(result)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["xml"], "a.xml")
        self.assertEqual(missing[0]["addon_vehicle_key"], "FS25_Pack/a")

    def test_mod_unsupported_suggests_keys(self):
        make_mod(self.tmp, "FS25_New", [("v/one.xml", "One"), ("v/two.xml", "Two")])
        result = vycompat.scan_mod(self.tmp / "FS25_New.zip", fake_addon(), {})
        self.assertEqual(result["status"], "unsupported")
        keys = [v["addon_vehicle_key"] for v in vycompat.missing_vehicles(result)]
        self.assertEqual(keys, ["FS25_New/v/one", "FS25_New/v/two"])
        self.assertEqual(result["custom_environment"], "FS25_New")

    def test_mod_own_year_wins(self):
        make_mod(self.tmp, "FS25_Own", [("a.xml", "Own Tractor", {"year": 1999})])
        result = vycompat.scan_mod(self.tmp / "FS25_Own.zip", fake_addon(), {})
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["vehicles"][0]["source"], "own")
        self.assertEqual(result["vehicles"][0]["year"], 1999)

    def test_mod_supported_via_vy_database(self):
        make_mod(self.tmp, "FS25_Vy", [("vehicles/a/a.xml", "From VY")])
        vy = {"FS25_Vy_vehicles_a_a": 1985}
        result = vycompat.scan_mod(self.tmp / "FS25_Vy.zip", fake_addon(), vy)
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["vehicles"][0]["source"], "vy")
        self.assertEqual(result["vehicles"][0]["year"], 1985)

    def test_custom_environment_used_for_keys(self):
        make_mod(self.tmp, "FS25_File", [("a.xml", "Env Tractor")], env="FS25_EnvName")
        vy = {"FS25_EnvName_a": 1971}
        result = vycompat.scan_mod(self.tmp / "FS25_File.zip", fake_addon(), vy)
        self.assertEqual(result["custom_environment"], "FS25_EnvName")
        self.assertEqual(result["status"], "supported")

    def test_fs22_mod_skipped(self):
        make_mod(self.tmp, "FS22_Old", [("a.xml", "Old Tractor")], desc_version=60)
        result = vycompat.scan_mod(self.tmp / "FS22_Old.zip", fake_addon(), {})
        self.assertEqual(result["status"], "skipped")

    def test_fs22_mod_included_on_request(self):
        make_mod(self.tmp, "FS22_Old", [("a.xml", "Old Tractor")], desc_version=60)
        result = vycompat.scan_mod(self.tmp / "FS22_Old.zip", fake_addon(), {}, include_non_fs25=True)
        self.assertEqual(result["status"], "unsupported")

    def test_non_vehicle_mod(self):
        files = {
            "modDesc.xml": moddesc(items=[("barn.xml", "placeable")]),
            "barn.xml": "<placeable type=\"farmBuilding\"><storeData>"
                        "<name><en>Barn</en></name><category>farmhouses</category>"
                        "</storeData></placeable>",
        }
        path = self.tmp / "FS25_Barn.zip"
        write_zip(path, files)
        result = vycompat.scan_mod(path, fake_addon(), {})
        self.assertEqual(result["status"], "no-vehicles")

    def test_scan_mods_dir_reads_zips_and_folders(self):
        make_mod(self.tmp, "FS25_ZipMod", [("a.xml", "Zip Tractor")])
        folder = self.tmp / "FS25_FolderMod"
        folder.mkdir()
        write_zip(self.tmp / "unrelated.zip", {"notes.txt": "hi"})  # ignored: no modDesc
        (folder / "modDesc.xml").write_text(
            moddesc(items=[("a.xml", "vehicle")]), encoding="utf-8"
        )
        (folder / "a.xml").write_text(vehicle_xml("Folder Tractor"), encoding="utf-8")

        results = vycompat.scan_mods_dir(self.tmp, fake_addon(), {})
        by_file = {r["file"]: r["status"] for r in results}
        self.assertEqual(
            sorted(by_file),
            ["FS25_FolderMod", "FS25_ZipMod.zip", "unrelated.zip"],
        )
        self.assertEqual(by_file["FS25_FolderMod"], "unsupported")
        self.assertEqual(by_file["FS25_ZipMod.zip"], "unsupported")
        self.assertEqual(by_file["unrelated.zip"], "error")  # zip without modDesc.xml

    # -- base game ---------------------------------------------------------

    def test_base_game_scan(self):
        data = self.tmp / "game" / "data"
        (data / "vehicles" / "brand" / "model").mkdir(parents=True)
        (data / "vehicles" / "brand" / "model" / "model.xml").write_text(
            vehicle_xml("Model One", brand="BRAND"), encoding="utf-8"
        )
        (data / "vehicles" / "brand" / "other").mkdir(parents=True)
        (data / "vehicles" / "brand" / "other" / "other.xml").write_text(
            vehicle_xml("Model Two", brand="BRAND"), encoding="utf-8"
        )
        addon = fake_addon(base={"base_data_vehicles_brand_model_model": 2018})
        items = vycompat.scan_base_game(self.tmp / "game", addon, {})
        self.assertEqual(len(items), 2)
        by_key = {item["key"]: item for item in items}
        self.assertEqual(by_key["base_data_vehicles_brand_model_model"]["source"], "addon-base")
        self.assertEqual(by_key["base_data_vehicles_brand_other_other"]["source"], "none")

    # -- reports -----------------------------------------------------------

    def test_years_info_format(self):
        make_mod(self.tmp, "FS25_New", [("a.xml", "One", {"category": "tractors"})],
                 title="New Mod")
        make_mod(self.tmp, "FS25_Many", [("a.xml", "A"), ("b.xml", "B")])
        mods = [
            vycompat.scan_mod(self.tmp / "FS25_New.zip", fake_addon(), {}),
            vycompat.scan_mod(self.tmp / "FS25_Many.zip", fake_addon(), {}),
        ]
        body = vycompat.format_years_info(mods)
        self.assertIn("FS25_New.zip - One (tractors) -", body)
        self.assertIn("FS25_Many.zip - per vehicle:", body)
        self.assertIn("  A (tractors) -", body)

    def test_lua_suggest_format(self):
        make_mod(self.tmp, "FS25_New", [("a.xml", "One")])
        make_mod(self.tmp, "FS25_Mix", [("a.xml", "A"), ("b.xml", "B")])
        addon = fake_addon(per_vehicle={"FS25_Mix/a": 1960})
        mods = [
            vycompat.scan_mod(self.tmp / "FS25_New.zip", fake_addon(), {}),
            vycompat.scan_mod(self.tmp / "FS25_Mix.zip", addon, {}),
        ]
        text = vycompat.format_lua_suggest(mods)
        self.assertIn('["FS25_New"] = ?,', text)
        self.assertIn('["FS25_New/a"] = ?,', text)
        self.assertIn('["FS25_Mix/b"] = ?,', text)
        self.assertNotIn('["FS25_Mix"] = ?,', text)  # partial mod: no whole-mod suggestion

    def test_json_report_structure(self):
        make_mod(self.tmp, "FS25_New", [("a.xml", "One")])
        mods = [vycompat.scan_mod(self.tmp / "FS25_New.zip", fake_addon(), {})]
        src = {
            "mods_dirs": [self.tmp],
            "game_dir": None,
            "vy": {"kind": "missing", "path": None},
            "vy_count": 0,
            "addon": vycompat.addon_info(fake_addon(), "9.9.9.9", "fake.lua", "source-lua"),
        }
        payload = json.loads(vycompat.format_json(mods, None, src))
        self.assertEqual(payload["name"], vycompat.APP_NAME)
        self.assertEqual(payload["tool"], "vycompat")
        self.assertEqual(payload["summary"]["unsupported"], 1)
        self.assertEqual(payload["mods"][0]["file"], "FS25_New.zip")
        self.assertEqual(payload["sources"]["addon"]["version"], "9.9.9.9")

    def test_copy_unsupported(self):
        make_mod(self.tmp, "FS25_New", [("a.xml", "One")])
        make_mod(self.tmp, "FS25_Ok", [("a.xml", "A")], title="Fine")
        mods = [
            vycompat.scan_mod(self.tmp / "FS25_New.zip", fake_addon(), {}),
            vycompat.scan_mod(self.tmp / "FS25_Ok.zip", fake_addon(mod_years={"FS25_Ok": 1990}), {}),
        ]
        target = self.tmp / "out"
        copied = vycompat.copy_unsupported(mods, target)
        self.assertEqual(copied, [("FS25_New.zip", "copied")])
        self.assertTrue((target / "FS25_New.zip").is_file())
        self.assertFalse((target / "FS25_Ok.zip").exists())


class DefaultPathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_native_documents_mods_folder(self):
        mods = self.tmp / "Documents" / "My Games" / "FarmingSimulator2025" / "mods"
        mods.mkdir(parents=True)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            vycompat, "HOME", self.tmp
        ), mock.patch.object(vycompat, "STEAM_ROOTS", []):
            self.assertEqual(vycompat.default_mods_dir(), mods)

    def test_onedrive_documents_mods_folder(self):
        one_drive = self.tmp / "OneDrive"
        mods = one_drive / "Documents" / "My Games" / "FarmingSimulator2025" / "mods"
        mods.mkdir(parents=True)
        with mock.patch.dict(
            os.environ, {"OneDrive": str(one_drive)}, clear=True
        ), mock.patch.object(vycompat, "HOME", self.tmp), mock.patch.object(
            vycompat, "STEAM_ROOTS", []
        ):
            self.assertEqual(vycompat.default_mods_dir(), mods)

    def test_proton_mods_folder(self):
        steam = self.tmp / "steam"
        mods = (
            steam / "steamapps" / "compatdata" / vycompat.COMPATDATA_ID
            / "pfx" / "drive_c" / "users" / "steamuser" / "Documents"
            / "My Games" / "FarmingSimulator2025" / "mods"
        )
        mods.mkdir(parents=True)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            vycompat, "HOME", self.tmp
        ), mock.patch.object(
            vycompat, "_steam_roots", return_value=[steam / "steamapps"]
        ):
            self.assertEqual(vycompat.default_mods_dir(), mods)

    def test_steam_game_folder(self):
        game = (
            self.tmp / "steam" / "steamapps" / "common"
            / vycompat.GAME_DIR_NAME
        )
        game.mkdir(parents=True)
        with mock.patch.object(
            vycompat, "_steam_roots",
            return_value=[self.tmp / "steam" / "steamapps"],
        ):
            self.assertEqual(vycompat.default_game_dir(), game)


if __name__ == "__main__":
    unittest.main(verbosity=2)
