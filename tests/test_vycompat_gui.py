#!/usr/bin/env python3
"""Tests for the compatibility tool GUI helpers (no display required)."""

import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["VYCOMPAT_EASTER_EGG"] = "0"

try:
    import vycompat_gui  # noqa: E402
    import vycompat_icons  # noqa: E402
except ImportError as exc:  # tkinter missing on this Python
    raise unittest.SkipTest(f"tkinter not available: {exc}")


def fake_vehicle(name, source="none", category="tractors", year=None, xml="a.xml"):
    return {
        "xml": xml,
        "name": name,
        "brand": "TEST",
        "category": category,
        "own_year": year if source == "own" else None,
        "source": source,
        "year": year,
        "addon_vehicle_key": f"FS25_Test/{xml[:-4]}",
        "addon_mod_key": "FS25_Test",
        "vy_key": f"FS25_Test_{xml[:-4]}",
    }


def fake_mod(file_name="FS25_Test.zip", status="unsupported", title="Test Mod",
             vehicles=None, env="FS25_Test"):
    return {
        "file": file_name,
        "path": f"/mods/{file_name}",
        "kind": "zip",
        "custom_environment": env,
        "title": title,
        "version": "1.0.0.0",
        "desc_version": 93,
        "status": status,
        "error": None,
        "vehicles": vehicles or [],
        "missing": [],
        "non_vehicle_items": 0,
    }


def fake_base_item(raw_xml, source="none", name="Model", category="tractors"):
    return {
        "raw_xml": raw_xml,
        "key": raw_xml.replace("$data/", "base_data_").replace("/", "_")[:-4],
        "brand": "BRAND",
        "name": name,
        "category": category,
        "source": source,
        "year": 2000 if source != "none" else None,
    }


class StatusTextTest(unittest.TestCase):
    def test_supported_in_the_mod_itself(self):
        self.assertEqual(
            vycompat_gui.status_text("supported", ["own"]),
            "Supported \u2014 in the mod itself",
        )

    def test_supported_in_vehicle_years_mod(self):
        self.assertEqual(
            vycompat_gui.status_text("supported", ["vy", "vy"]),
            "Supported \u2014 in the Vehicle Years mod",
        )

    def test_supported_by_compatibility_tool(self):
        self.assertEqual(
            vycompat_gui.status_text("supported", ["addon-mod"]),
            "Supported \u2014 added by the compatibility tool",
        )
        self.assertEqual(
            vycompat_gui.status_text("supported", ["addon-vehicle", "addon-base"]),
            "Supported \u2014 added by the compatibility tool",
        )

    def test_supported_mixed_sources(self):
        text = vycompat_gui.status_text("supported", ["own", "vy", "addon-mod"])
        self.assertIn("in the mod itself", text)
        self.assertIn("in the Vehicle Years mod", text)
        self.assertIn("added by the compatibility tool", text)

    def test_needs_years_texts(self):
        self.assertEqual(
            vycompat_gui.status_text("unsupported", ["none", "none"], 2, 2),
            "Needs years (2 vehicles)",
        )
        self.assertEqual(
            vycompat_gui.status_text("unsupported", ["none"], 1, 1),
            "Needs years (1 vehicle)",
        )
        self.assertEqual(
            vycompat_gui.status_text("partial", ["vy", "none"], 1, 2),
            "Needs years (1 of 2)",
        )

    def test_compact_status_for_advanced_table(self):
        addon = vycompat_gui.mod_row(
            fake_mod(
                status="supported",
                vehicles=[fake_vehicle("V", source="addon-mod", year=1965)],
            )
        )
        self.assertEqual(
            vycompat_gui.tree_status(addon, advanced=True),
            "Supported - tool",
        )
        self.assertEqual(
            vycompat_gui.tree_status(addon, advanced=False),
            "Supported \u2014 compatibility tool",
        )

        partial = vycompat_gui.mod_row(
            fake_mod(
                status="partial",
                vehicles=[
                    fake_vehicle("A", source="vy", year=1965),
                    fake_vehicle("B", source="none"),
                ],
            )
        )
        self.assertEqual(
            vycompat_gui.tree_status(partial, advanced=True), "Needs years 1/2"
        )

        base = vycompat_gui.base_row(
            [fake_base_item("$data/vehicles/a/a.xml", source="vy")]
        )
        self.assertEqual(
            vycompat_gui.tree_status(base, advanced=True), "Supported - VY"
        )

        in_db = vycompat_gui.mod_row(
            fake_mod(
                status="supported",
                vehicles=[fake_vehicle("V", source="vy", year=1965)],
            )
        )
        self.assertEqual(
            vycompat_gui.tree_status(in_db, advanced=False),
            "Supported \u2014 Vehicle Years",
        )
        own = vycompat_gui.mod_row(
            fake_mod(
                status="supported",
                vehicles=[fake_vehicle("V", source="own", year=1965)],
            )
        )
        self.assertEqual(
            vycompat_gui.tree_status(own, advanced=False),
            "Supported \u2014 mod itself",
        )


class GuiRowsTest(unittest.TestCase):
    def test_rows_sorted_with_problems_first_advanced(self):
        mods = [
            fake_mod("FS25_Good.zip", "supported", "Good"),
            fake_mod("FS25_Skip.zip", "skipped", "Skip", env="FS25_Skip"),
            fake_mod("FS25_Bad.zip", "unsupported", "Bad", env="FS25_Bad"),
            fake_mod("FS25_Mid.zip", "partial", "Mid", env="FS25_Mid"),
        ]
        rows = vycompat_gui.gui_rows(mods, advanced=True)
        self.assertEqual(
            [row["status"] for row in rows],
            ["unsupported", "partial", "supported", "skipped"],
        )
        self.assertEqual(rows[0]["label"], "FS25_Bad.zip")

    def test_simple_mode_hides_non_vehicle_and_skipped(self):
        mods = [
            fake_mod("FS25_Car.zip", "supported", "Car"),
            fake_mod("FS25_Map.zip", "no-vehicles", "Map", env="FS25_Map"),
            fake_mod("FS22_Old.zip", "skipped", "Old", env="FS22_Old"),
        ]
        simple = vycompat_gui.gui_rows(mods)
        self.assertEqual([row["label"] for row in simple], ["Car"])
        advanced = vycompat_gui.gui_rows(mods, advanced=True)
        self.assertEqual(len(advanced), 3)

    def test_supported_row_states_how(self):
        mod = fake_mod(
            "FS25_Addon.zip", "supported", "Addon",
            vehicles=[fake_vehicle("A", "addon-vehicle", year=1967)],
        )
        row = vycompat_gui.gui_rows([mod])[0]
        self.assertEqual(row["status_text"], "Supported \u2014 added by the compatibility tool")
        self.assertEqual(row["missing"], 0)

    def test_base_row_pinned_on_top_when_missing(self):
        mods = [fake_mod("FS25_Bad.zip", "unsupported", "Bad", env="FS25_Bad")]
        base = [
            fake_base_item("$data/vehicles/a/b/b.xml", "vy"),
            fake_base_item("$data/vehicles/c/d/d.xml", "none"),
        ]
        rows = vycompat_gui.gui_rows(mods, base)
        self.assertEqual(rows[0]["kind"], "base")
        self.assertEqual(rows[0]["missing"], 1)
        self.assertEqual(rows[0]["status"], "unsupported")

    def test_base_row_appended_when_complete(self):
        mods = [fake_mod("FS25_Bad.zip", "unsupported", "Bad", env="FS25_Bad")]
        base = [fake_base_item("$data/vehicles/a/b/b.xml", "vy")]
        rows = vycompat_gui.gui_rows(mods, base)
        self.assertEqual(rows[-1]["kind"], "base")
        self.assertEqual(rows[-1]["status"], "supported")
        self.assertEqual(rows[-1]["status_text"], "Supported \u2014 in the Vehicle Years mod")


class SearchTest(unittest.TestCase):
    def test_search_text_includes_title_file_vehicle_and_keys(self):
        row = vycompat_gui.mod_row(
            fake_mod(
                file_name="FS25_Test.zip", title="Test Mod",
                vehicles=[fake_vehicle("Tractor X", xml="tractor.xml")],
            )
        )
        for query in (
            "test mod", "FS25_Test.zip", "Tractor X", "tractor.xml",
            "FS25_Test/tractor", "tractors", "TEST",
        ):
            self.assertTrue(
                vycompat_gui.row_matches_search(row, query),
                f"{query!r} should match",
            )

    def test_multiword_search_is_and(self):
        row = vycompat_gui.mod_row(
            fake_mod(
                title="Baler Pack",
                vehicles=[fake_vehicle("Round Baler", xml="baler.xml")],
            )
        )
        self.assertTrue(vycompat_gui.row_matches_search(row, "baler round"))
        self.assertFalse(vycompat_gui.row_matches_search(row, "baler plow"))

    def test_empty_search_matches_everything(self):
        row = vycompat_gui.mod_row(fake_mod())
        self.assertTrue(vycompat_gui.row_matches_search(row, ""))
        self.assertTrue(vycompat_gui.row_matches_search(row, "   "))

    def test_base_rows_are_searchable(self):
        row = vycompat_gui.base_row(
            [fake_base_item("$data/vehicles/a/b/b.xml", name="Model B")]
        )
        self.assertTrue(vycompat_gui.row_matches_search(row, "base game"))
        self.assertTrue(vycompat_gui.row_matches_search(row, "model b"))
        self.assertTrue(vycompat_gui.row_matches_search(row, "base_data"))
        self.assertFalse(vycompat_gui.row_matches_search(row, "tractor z"))


class PreviewHelpersTest(unittest.TestCase):
    def test_summary_counts_actions_and_pending(self):
        entries = [
            {"action": "updated", "table": "MOD_YEARS", "key": "A", "year": 2, "old_year": 1},
            {"action": "added", "table": "MOD_YEARS", "key": "B", "year": 3},
            {"action": "added", "table": "MOD_YEARS", "key": "C", "year": 4},
            {"action": "unchanged", "table": "MOD_YEARS", "key": "D", "year": 5},
        ]
        summary = vycompat_gui.preview_summary(entries, pending=2)
        self.assertIn("1 entry changed", summary)
        self.assertIn("2 entries added", summary)
        self.assertIn("1 already present", summary)
        self.assertIn("2 lines skipped", summary)

    def test_action_text_and_order(self):
        updated = {
            "action": "updated", "table": "MOD_YEARS", "key": "A",
            "year": 1970, "old_year": 1965,
        }
        added = {
            "action": "added", "table": "MOD_YEARS", "key": "B", "year": 1980,
        }
        unchanged = {
            "action": "unchanged", "table": "MOD_YEARS", "key": "C", "year": 1990,
        }
        self.assertEqual(
            vycompat_gui.preview_action_text(updated), "CHANGE 1965 -> 1970"
        )
        self.assertEqual(vycompat_gui.preview_action_text(added), "ADD 1980")
        self.assertEqual(
            vycompat_gui.preview_action_text(unchanged), "1990 (unchanged)"
        )
        ordered = vycompat_gui.sorted_preview_entries(
            [unchanged, added, updated]
        )
        self.assertEqual([entry["key"] for entry in ordered], ["A", "B", "C"])

    def test_snapshot_time_formatting(self):
        self.assertEqual(
            vycompat_gui.format_snapshot_time("2026-10-20T01:23:45+02:00"),
            "2026-10-20 01:23",
        )
        self.assertEqual(vycompat_gui.format_snapshot_time(None), "unknown time")


class GuiDetailsTest(unittest.TestCase):
    def test_simple_details_supported_has_no_keys(self):
        mod = fake_mod(
            "FS25_Addon.zip", "supported", "Addon",
            vehicles=[fake_vehicle("A", "addon-vehicle", year=1967)],
        )
        text = vycompat_gui.format_mod_details_simple(mod)
        self.assertIn("Supported \u2014 added by the compatibility tool", text)
        self.assertIn("1967", text)
        self.assertNotIn("MOD_VEHICLE_YEARS", text)
        self.assertNotIn("descVersion", text)

    def test_simple_details_unsupported_lists_vehicles_without_keys(self):
        mod = fake_mod(
            status="unsupported",
            vehicles=[fake_vehicle("One"), fake_vehicle("Two", xml="b.xml")],
        )
        text = vycompat_gui.format_mod_details_simple(mod)
        self.assertIn("Needs years for 2 vehicles:", text)
        self.assertIn("\u2022 One \u2014 needs a year", text)
        self.assertIn("\u2022 Two \u2014 needs a year", text)
        self.assertNotIn("MOD_YEARS", text)

    def test_simple_details_partial_marks_each_source(self):
        mod = fake_mod(
            "FS25_Mix.zip", "partial", "Mix",
            vehicles=[
                fake_vehicle("A", "vy", year=1980),
                fake_vehicle("B", xml="b.xml"),
            ],
        )
        text = vycompat_gui.format_mod_details_simple(mod)
        self.assertIn("Needs years for 1 of 2 vehicles:", text)
        self.assertIn("A \u2014 1980", text)
        self.assertIn("B \u2014 needs a year", text)

    def test_advanced_details_has_suggested_keys(self):
        mod = fake_mod(
            status="unsupported",
            vehicles=[fake_vehicle("One"), fake_vehicle("Two", xml="b.xml")],
        )
        text = vycompat_gui.format_mod_details(mod)
        self.assertIn("descVersion", text)
        self.assertIn('MOD_YEARS["FS25_Test"] = ?,', text)
        self.assertIn('MOD_VEHICLE_YEARS["FS25_Test/a"] = ?,', text)
        self.assertIn('MOD_VEHICLE_YEARS["FS25_Test/b"] = ?,', text)

    def test_format_details_dispatch(self):
        mod = fake_mod(status="unsupported", vehicles=[fake_vehicle("One")])
        row = vycompat_gui.gui_rows([mod])[0]
        simple = vycompat_gui.format_details(row)
        advanced = vycompat_gui.format_details(row, advanced=True)
        self.assertNotIn("MOD_VEHICLE_YEARS", simple)
        self.assertIn("MOD_VEHICLE_YEARS", advanced)

    def test_base_details_simple_and_advanced(self):
        base = [
            fake_base_item("$data/vehicles/a/b/b.xml", "vy"),
            fake_base_item("$data/vehicles/c/d/d.xml", "none", name="Model D"),
        ]
        simple = vycompat_gui.format_base_details_simple(base)
        self.assertIn("1 base game vehicle needs a year:", simple)
        self.assertIn("\u2022 Model D", simple)
        advanced = vycompat_gui.format_base_details(base)
        self.assertIn("$data/vehicles/c/d/d.xml | BRAND | Model D | tractors", advanced)

    def test_base_details_complete(self):
        text = vycompat_gui.format_base_details_simple(
            [fake_base_item("$data/vehicles/a/b/b.xml", "vy")]
        )
        self.assertIn("All supported \u2014 in the Vehicle Years mod", text)


class GuiWindowTest(unittest.TestCase):
    def test_window_constructs_when_display_available(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        try:
            root.withdraw()
            app = vycompat_gui.VycompatApp(root)
            self.assertTrue(app.scan_btn)
            self.assertEqual(app.summary_var.get().split(" - ")[0], "No scan yet")
            # simple mode: no advanced widgets, single status column
            self.assertEqual(app.adv_buttons.winfo_manager(), "")
            self.assertEqual(app.adv_options.winfo_manager(), "")
            self.assertNotIn("vehicles", str(app.tree.cget("displaycolumns")))
            # "Add years..." is always visible but only enabled for mods in need
            self.assertEqual(app.add_years_btn.winfo_manager(), "pack")
            self.assertEqual(str(app.add_years_btn.cget("state")), "disabled")

            app.advanced_var.set(True)
            app.on_advanced_toggle()
            self.assertEqual(app.adv_buttons.winfo_manager(), "pack")
            self.assertEqual(app.adv_options.winfo_manager(), "pack")
            self.assertIn("vehicles", str(app.tree.cget("displaycolumns")))

            app.advanced_var.set(False)
            app.on_advanced_toggle()
            self.assertEqual(app.adv_buttons.winfo_manager(), "")
            self.assertEqual(app.adv_options.winfo_manager(), "")
        finally:
            root.destroy()


class SearchAppTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def make_app(self):
        app = vycompat_gui.VycompatApp(self.root)
        app.last = {
            "mods": [
                fake_mod(
                    "FS25_Tractor.zip", "unsupported", "Tractor Mod",
                    vehicles=[fake_vehicle("Tractor X", xml="tractor.xml")],
                ),
                fake_mod(
                    "FS25_Baler.zip", "unsupported", "Baler Mod",
                    env="FS25_Baler",
                    vehicles=[fake_vehicle("Round Baler", xml="baler.xml")],
                ),
            ],
            "base_items": None,
        }
        app.refresh_rows()
        return app

    def test_search_filters_rows_and_updates_count(self):
        app = self.make_app()
        self.assertEqual(len(app.rows_by_iid), 2)

        app.search_var.set("baler round")
        self.assertEqual(len(app.rows_by_iid), 1)
        row = next(iter(app.rows_by_iid.values()))
        self.assertEqual(row["mod"]["title"], "Baler Mod")
        self.assertEqual(app.tree_count_label.cget("text"), "1 of 2 shown")

        app.clear_search()
        self.assertEqual(len(app.rows_by_iid), 2)
        self.assertEqual(app.tree_count_label.cget("text"), "2 shown")

    def test_search_matches_addon_key_and_shows_empty_hint(self):
        app = self.make_app()
        app.search_var.set("FS25_Test/tractor")
        self.assertEqual(len(app.rows_by_iid), 1)

        app.search_var.set("zzz-no-match")
        self.assertEqual(len(app.rows_by_iid), 0)
        details = app.details.get("1.0", "end")
        self.assertIn("zzz-no-match", details)
        self.assertIn("Clear the search", details)

    def test_search_entry_is_always_visible_and_ctrl_f_selects(self):
        app = self.make_app()
        self.assertEqual(app.search_entry.winfo_manager(), "pack")
        self.assertEqual(app.addon_history_btn.winfo_manager(), "pack")
        self.assertEqual(app._focus_search(), "break")


class ChangesDialogTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def plan(self):
        return {
            "changed": True,
            "entries": [
                {
                    "table": "MOD_YEARS", "key": "FS25_Old", "year": 1970,
                    "old_year": 1965, "action": "updated",
                },
                {
                    "table": "MOD_VEHICLE_YEARS", "key": "FS25_Pack/b",
                    "year": 1968, "old_year": None, "action": "added",
                },
            ],
            "version": "1.0.4.0",
            "new_version": "1.0.5.0",
            "description_updated": True,
        }

    def test_dialog_lists_changes_and_confirms(self):
        dialog = vycompat_gui.ChangesDialog(
            self.root, self.plan(), Path("/tmp/addon"),
            install_dir=Path("/tmp/mods"),
        )
        try:
            values = [
                dialog.tree.item(iid, "values")
                for iid in dialog.tree.get_children()
            ]
            self.assertIn(
                ("MOD_YEARS", "FS25_Old", "CHANGE 1965 -> 1970"),
                values,
            )
            self.assertIn(
                (
                    "MOD_VEHICLE_YEARS", "FS25_Pack/b", "ADD 1968",
                ),
                values,
            )
            self.assertIn("1 entry changed", dialog.summary_label.cget("text"))
            self.assertIn("1.0.5.0", dialog.version_label.cget("text"))
            self.assertEqual(str(dialog.confirm_btn.cget("text")), "WRITE & REBUILD")
            dialog._confirm()
        finally:
            try:
                dialog.destroy()
            except Exception:
                pass
        self.assertTrue(dialog.result)

    def test_no_change_dialog_has_no_write_button(self):
        plan = self.plan()
        plan["changed"] = False
        plan["entries"] = [
            {
                "table": "MOD_YEARS", "key": "FS25_Old", "year": 1965,
                "old_year": 1965, "action": "unchanged",
            }
        ]
        dialog = vycompat_gui.ChangesDialog(
            self.root, plan, Path("/tmp/addon")
        )
        try:
            self.assertEqual(str(dialog.confirm_btn.cget("text")), "CLOSE")
            self.assertIsNone(dialog.result)
        finally:
            dialog.destroy()


class AddonHistoryDialogTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        import shutil
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_lists_snapshots_and_restores_without_installing(self):
        source = make_addon_source(self.tmp)
        snapshot = vycompat_gui.history.snapshot_addon(
            source, reason="unit test"
        )
        dialog = vycompat_gui.AddonHistoryDialog(
            self.root, source, install_dir=self.tmp / "mods"
        )
        try:
            self.assertEqual(len(dialog.snapshots), 1)
            self.assertEqual(str(dialog.restore_btn.cget("state")), "normal")
            self.assertFalse(dialog.install_var.get())
            self.assertIn("unit test", dialog.selected_var.get())
            dialog._restore()
        finally:
            try:
                dialog.destroy()
            except Exception:
                pass
        self.assertEqual(
            dialog.result,
            {"snapshot": snapshot["path"], "install": False},
        )

    def test_empty_history_disables_restore(self):
        source = make_addon_source(self.tmp)
        dialog = vycompat_gui.AddonHistoryDialog(self.root, source)
        try:
            self.assertEqual(str(dialog.restore_btn.cget("state")), "disabled")
            self.assertIn("No snapshots", dialog.selected_var.get())
            self.assertIsNone(dialog.result)
        finally:
            dialog.destroy()


class YearDialogTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def make_dialog(self, sources):
        vehicles = [
            fake_vehicle(f"V{index}", source=source, xml=f"v{index}.xml")
            for index, source in enumerate(sources)
        ]
        mod = fake_mod(
            status="unsupported" if "none" in sources else "supported",
            vehicles=vehicles,
        )
        missing = vycompat_gui.vy.missing_vehicles(mod)
        return vycompat_gui.YearDialog(self.root, mod, missing, None)

    def test_default_mode_is_whole_mod_when_all_missing(self):
        dialog = self.make_dialog(("none", "none"))
        self.assertEqual(dialog.mode_var.get(), "mod")
        self.assertEqual(str(dialog.vehicle_entries[0].cget("state")), "disabled")
        dialog.destroy()

    def test_default_mode_is_per_vehicle_when_partial(self):
        dialog = self.make_dialog(("vy", "none"))
        self.assertEqual(dialog.mode_var.get(), "vehicle")
        self.assertEqual(str(dialog.vehicle_entries[0].cget("state")), "normal")
        dialog.destroy()

    def test_save_whole_mod_year(self):
        dialog = self.make_dialog(("none", "none"))
        dialog.shared_var.set("1990")
        dialog._save()
        self.assertEqual(dialog.result, {"mode": "mod", "year": 1990, "install": False})

    def test_save_per_vehicle_years(self):
        dialog = self.make_dialog(("vy", "none", "none"))
        self.assertEqual(dialog.mode_var.get(), "vehicle")
        dialog.vehicle_vars["FS25_Test/v1"].set("1991")
        dialog.vehicle_vars["FS25_Test/v2"].set("1992")
        dialog._save()
        self.assertEqual(
            dialog.result,
            {
                "mode": "vehicle",
                "years": {"FS25_Test/v1": 1991, "FS25_Test/v2": 1992},
                "install": False,
            },
        )

    def test_invalid_year_shows_inline_error(self):
        dialog = self.make_dialog(("none",))
        dialog.shared_var.set("not a year")
        dialog._save()
        self.assertIsNone(dialog.result)
        self.assertIn("not a year", dialog.error_var.get())
        dialog.destroy()


def make_addon_source(tmp, lua=None):
    source = tmp / "FS25_VehicleYears_CompatibilityTool"
    source.mkdir()
    (source / "vehicle_years_addon.lua").write_text(
        lua
        if lua is not None
        else "local MOD_VEHICLE_YEARS = {\n}\n\nlocal MOD_YEARS = {\n}\n\n"
        "local BASE_GAME_YEARS = {\n}\n",
        encoding="utf-8",
    )
    (source / "modDesc.xml").write_text(
        "<modDesc><version>1.0.0.0</version><description><en><![CDATA[\n"
        "Supported mods:\n\nSupported mods with per-vehicle years:\n\n"
        "]]></en></description></modDesc>",
        encoding="utf-8",
    )
    (source / "icon_VY.dds").write_bytes(b"dds")
    return source


class AddonSetupFlowTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_create_prompt_scaffolds_and_installs(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        mods = tmp / "mods"
        mods.mkdir()
        source = tmp / vycompat_gui.vy.ADDON_MOD_NAME
        app = vycompat_gui.VycompatApp(self.root)
        report = {
            "source": str(source),
            "zip": str(tmp / vycompat_gui.vy.ADDON_ZIP_NAME),
            "installed": str(mods / vycompat_gui.vy.ADDON_ZIP_NAME),
        }

        calls = []

        class FakeDialog:
            def __init__(self, parent, mode, source_dir, install_dir, th=None):
                self.result = True
                self.mode = mode
                self.install_dir = install_dir
                calls.append((mode, source_dir, install_dir))

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_DIR", source
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods
        ), mock.patch.object(
            vycompat_gui, "AddonSetupDialog", FakeDialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            vycompat_gui.vy, "scaffold_addon", return_value=report
        ) as scaffold, mock.patch.object(
            vycompat_gui.vy, "set_source_addon_dir"
        ) as set_source, mock.patch.object(
            app, "notify"
        ) as notify:
            ready = app.ensure_addon_ready(mods)

        self.assertTrue(ready)
        self.assertEqual(calls[0][0], "create")
        scaffold.assert_called_once_with(source, install_dir=mods)
        set_source.assert_called_once_with(str(source))
        self.assertEqual(app.addon_var.get(), "installed")
        self.assertIn("created and installed", notify.call_args[0][0])

    def test_startup_check_prompts_for_a_known_folder(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        app = vycompat_gui.VycompatApp(self.root)
        app.folder_var.set(str(tmp))
        with mock.patch.object(app, "ensure_addon_ready") as ensure:
            app._check_addon_on_startup()
        ensure.assert_called_once_with(tmp)

    def test_installed_zip_without_source_offers_extract(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        mods = tmp / "mods"
        mods.mkdir()
        installed = mods / vycompat_gui.vy.ADDON_ZIP_NAME
        installed.write_bytes(b"zip")
        destination = tmp / "editable" / vycompat_gui.vy.ADDON_MOD_NAME
        source_lua = destination / "vehicle_years_addon.lua"
        app = vycompat_gui.VycompatApp(self.root)
        app.folder_var.set(str(mods))
        original_dir = vycompat_gui.vy.SOURCE_ADDON_DIR
        original_lua = vycompat_gui.vy.SOURCE_ADDON_LUA
        self.addCleanup(
            setattr, vycompat_gui.vy, "SOURCE_ADDON_DIR", original_dir
        )
        self.addCleanup(
            setattr, vycompat_gui.vy, "SOURCE_ADDON_LUA", original_lua
        )
        calls = []

        class FakeDialog:
            def __init__(self, parent, mode, source_dir, install_dir, th=None):
                self.result = True
                calls.append((mode, source_dir, install_dir))

        def fake_extract(zip_path, source_dir):
            source_dir.mkdir(parents=True)
            (source_dir / "vehicle_years_addon.lua").write_text(
                "local MOD_YEARS = {}\n", encoding="utf-8"
            )
            (source_dir / "modDesc.xml").write_text(
                "<modDesc><version>1.0.0.0</version></modDesc>",
                encoding="utf-8",
            )
            return {"source": str(source_dir)}

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source_lua
        ), mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_DIR", destination
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods
        ), mock.patch.object(
            vycompat_gui, "AddonSetupDialog", FakeDialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            vycompat_gui.vy, "extract_addon_zip", side_effect=fake_extract
        ) as extract, mock.patch.object(
            app, "notify"
        ):
            ready = app.ensure_addon_source()

        self.assertTrue(ready)
        self.assertEqual(calls[0][0], "extract")
        extract.assert_called_once_with(installed, destination)
        self.assertTrue(source_lua.is_file())

    def test_declining_prompt_writes_nothing(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        mods = tmp / "mods"
        mods.mkdir()
        source = tmp / vycompat_gui.vy.ADDON_MOD_NAME
        app = vycompat_gui.VycompatApp(self.root)

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.result = False

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods
        ), mock.patch.object(
            vycompat_gui, "AddonSetupDialog", FakeDialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            vycompat_gui.vy, "scaffold_addon"
        ) as scaffold:
            ready = app.ensure_addon_ready(mods)

        self.assertFalse(ready)
        self.assertFalse(scaffold.called)
        self.assertIn(str(mods), app._addon_setup_dismissed)


class AddYearsFlowTest(unittest.TestCase):
    """app.add_years() wiring, with the addon and mods folder redirected to tmp."""

    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def make_source(self, tmp, lua=None):
        return make_addon_source(tmp, lua)

    def make_app_with_row(self, dialog_result):
        app = vycompat_gui.VycompatApp(self.root)
        mod = fake_mod(
            status="unsupported",
            vehicles=[
                fake_vehicle("Tractor X", xml="tractor.xml"),
                fake_vehicle("Plow Y", xml="plow.xml"),
            ],
        )
        row = {"kind": "mod", "mod": mod, "missing": 2}
        iid = app.tree.insert("", "end", values=(mod["file"], "Needs years (2)", 2, 2))
        app.rows_by_iid[iid] = row
        app.tree.selection_set(iid)

        class FakeDialog:
            def __init__(self, parent, mod_arg, missing, install_dir):
                self.result = dialog_result

        return app, mod, FakeDialog

    def test_add_years_updates_addon_and_installs(self):
        import shutil
        import tempfile
        import zipfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = self.make_source(tmp)
        mods_dir = tmp / "mods"
        app, mod, fake_dialog = self.make_app_with_row(
            {"mode": "mod", "year": 1965, "install": True}
        )

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods_dir
        ), mock.patch.object(
            vycompat_gui, "YearDialog", fake_dialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            app, "confirm_addon_changes", return_value=True
        ), mock.patch.object(
            app, "start_scan"
        ) as start_scan, mock.patch.object(
            app, "notify"
        ) as notify, mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.add_years()

        self.assertFalse(show_error.called)
        self.assertTrue(notify.called)
        lua = (source / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        self.assertIn('["FS25_Test"] = 1965', lua)
        desc = (source / "modDesc.xml").read_text(encoding="utf-8")
        self.assertIn("<version>1.0.1.0</version>", desc)
        self.assertIn("- FS25_Test (Test Mod) - 1965", desc)
        installed = mods_dir / vycompat_gui.vy.ADDON_ZIP_NAME
        self.assertTrue(installed.is_file())
        with zipfile.ZipFile(installed) as zf:
            self.assertIn("vehicle_years_addon.lua", zf.namelist())
        self.assertEqual(app.addon_var.get(), "installed")
        self.assertEqual(app._reselect_file, mod["file"])
        self.assertTrue(start_scan.called)

    def test_add_years_reports_nothing_to_change(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = self.make_source(
            tmp, lua='local MOD_YEARS = {\n    ["FS25_Test"] = 1965,\n}\n'
        )
        mods_dir = tmp / "mods"
        app, mod, fake_dialog = self.make_app_with_row(
            {"mode": "mod", "year": 1965, "install": True}
        )

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods_dir
        ), mock.patch.object(
            vycompat_gui, "YearDialog", fake_dialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            app, "confirm_addon_changes", return_value=True
        ), mock.patch.object(
            app, "start_scan"
        ) as start_scan, mock.patch.object(
            app, "notify"
        ) as notify, mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.add_years()

        self.assertFalse(show_error.called)
        self.assertTrue(notify.called)
        self.assertFalse(start_scan.called)
        self.assertFalse(mods_dir.exists())
        self.assertIsNone(app._reselect_file)

    def test_preview_cancel_writes_nothing(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = self.make_source(tmp)
        app, mod, fake_dialog = self.make_app_with_row(
            {"mode": "mod", "year": 1965, "install": True}
        )

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=tmp / "mods"
        ), mock.patch.object(
            vycompat_gui, "YearDialog", fake_dialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            app, "confirm_addon_changes", return_value=False
        ), mock.patch.object(
            app, "start_scan"
        ) as start_scan, mock.patch.object(
            app, "notify"
        ) as notify, mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.add_years()

        self.assertFalse(show_error.called)
        self.assertFalse(notify.called)
        self.assertFalse(start_scan.called)
        self.assertIn(
            "cancelled",
            app.status_var.get().lower(),
        )
        lua = (source / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        self.assertNotIn("FS25_Test", lua)
        self.assertFalse((source / ".vycompat_history").exists())
        self.assertFalse((tmp / "mods").exists())

    def test_successful_export_creates_history_snapshot(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = self.make_source(tmp)
        app, mod, fake_dialog = self.make_app_with_row(
            {"mode": "mod", "year": 1965, "install": False}
        )

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=None
        ), mock.patch.object(
            vycompat_gui, "YearDialog", fake_dialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            app, "confirm_addon_changes", return_value=True
        ), mock.patch.object(
            app, "start_scan"
        ), mock.patch.object(
            app, "notify"
        ), mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.add_years()

        self.assertFalse(show_error.called)
        snapshots = vycompat_gui.history.list_addon_snapshots(source)
        self.assertEqual(len(snapshots), 1)
        self.assertIn("Add years", snapshots[0]["reason"])


class HistoryFlowTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_restore_from_history_updates_mode_and_rescans(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = make_addon_source(tmp)
        app = vycompat_gui.VycompatApp(self.root)
        selected = {"snapshot": str(tmp / "snap.zip"), "install": True}
        report = {
            "restored": selected["snapshot"],
            "previous_snapshot": str(tmp / "previous.zip"),
            "version": "1.0.4.0",
            "zip": str(tmp / "FS25_VehicleYears_CompatibilityTool.zip"),
            "installed": str(tmp / "mods" / "FS25_VehicleYears_CompatibilityTool.zip"),
        }

        class FakeHistoryDialog:
            def __init__(self, parent, source_dir, install_dir=None, th=None):
                self.result = selected

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=tmp / "mods"
        ), mock.patch.object(
            vycompat_gui, "AddonHistoryDialog", FakeHistoryDialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            vycompat_gui.history, "restore_addon_snapshot", return_value=report
        ) as restore, mock.patch.object(
            app, "start_scan"
        ) as start_scan, mock.patch.object(
            app, "notify"
        ) as notify, mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.show_addon_history()

        self.assertFalse(show_error.called)
        self.assertTrue(restore.called)
        self.assertEqual(restore.call_args.kwargs["install_dir"], tmp / "mods")
        self.assertEqual(app.addon_var.get(), "installed")
        self.assertTrue(start_scan.called)
        self.assertTrue(notify.called)
        self.assertIn("Restored addon", notify.call_args[0][0])


class CopyYearsTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_copies_prompt_with_items_for_missing_mods(self):
        app = vycompat_gui.VycompatApp(self.root)
        app.last = {
            "mods": [
                fake_mod(status="unsupported", vehicles=[fake_vehicle("Tractor X")])
            ]
        }
        with mock.patch.object(app.root, "clipboard_clear") as clear, \
                mock.patch.object(app.root, "clipboard_append") as append, \
                mock.patch.object(app, "notify") as notify:
            app.copy_years()
        self.assertTrue(clear.called)
        self.assertTrue(append.called)
        copied = append.call_args[0][0]
        self.assertIn("Find the real-world production year", copied)
        self.assertIn(vycompat_gui.vy.CHATGPT_ITEM_MARKER, copied)
        self.assertIn("FS25_Test/a = ?", copied)
        self.assertNotIn("FS25_Test = ?", copied)
        self.assertTrue(notify.called)
        self.assertIn("Copied 1", notify.call_args[0][0])

    def test_copy_without_scan_shows_hint(self):
        app = vycompat_gui.VycompatApp(self.root)
        with mock.patch.object(app, "notify") as notify:
            app.copy_years()
        self.assertTrue(notify.called)
        self.assertIn("Scan a folder first", notify.call_args[0][0])


class PasteYearsDialogTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def make_dialog(self):
        dialog = vycompat_gui.PasteYearsDialog(self.root, None)
        dialog.text.delete("1.0", "end")
        return dialog

    def test_apply_parses_years(self):
        dialog = self.make_dialog()
        dialog.text.insert("1.0", "FS25_A = 1965\nFS25_A/a = 1966\nFS25_B = ?\n")
        dialog._apply()
        self.assertEqual(
            dialog.result,
            {
                "mod_years": {"FS25_A": 1965},
                "vehicle_years": {"FS25_A/a": 1966},
                "pending": ["FS25_B"],
                "install": False,
            },
        )

    def test_prefills_clipboard_with_prompt_and_pending_items(self):
        text, _ = vycompat_gui.vy.chatgpt_template(
            [fake_mod(status="unsupported", vehicles=[fake_vehicle("Tractor X")])]
        )
        dialog = vycompat_gui.PasteYearsDialog(self.root, None)
        dialog.text.delete("1.0", "end")
        with mock.patch.object(dialog, "clipboard_get", return_value=text):
            dialog._prefill_clipboard()
        inserted = dialog.text.get("1.0", "end")
        self.assertIn("ITEMS TO VERIFY:", inserted)
        self.assertIn("FS25_Test/a = ?", inserted)
        dialog.destroy()

    def test_apply_accepts_parenthesised_chatgpt_output(self):
        dialog = self.make_dialog()
        dialog.text.insert(
            "1.0",
            "FS25_A/a = (year: 1983, certainty: unsure, guess: none)\n"
            "FS25_A/b = (year: unknown, certainty: unknown, guess: none)\n",
        )
        dialog._apply()
        self.assertIsNotNone(dialog.result)
        self.assertEqual(dialog.result["vehicle_years"], {"FS25_A/a": 1983})
        self.assertEqual(dialog.result["pending"], ["FS25_A/b"])

    def test_apply_accepts_unknown_with_chatgpt_columns(self):
        dialog = self.make_dialog()
        dialog.text.insert(
            "1.0",
            "FS25_A/a = 1988 | sure | none\n"
            "FS25_A/b = unknown | unknown | none\n",
        )
        dialog._apply()
        self.assertIsNotNone(dialog.result)
        self.assertEqual(dialog.result["vehicle_years"], {"FS25_A/a": 1988})
        self.assertEqual(dialog.result["mod_years"], {})
        self.assertEqual(dialog.result["pending"], ["FS25_A/b"])

    def test_apply_accepts_chatgpt_prompt_output(self):
        text, _ = vycompat_gui.vy.chatgpt_template(
            [fake_mod(status="unsupported", vehicles=[fake_vehicle("Tractor X")])]
        )
        filled = text.replace("FS25_Test/a = ?", "FS25_Test/a = 1965")
        dialog = self.make_dialog()
        dialog.text.insert("1.0", filled)
        dialog._apply()
        self.assertIsNotNone(dialog.result)
        self.assertEqual(dialog.result["vehicle_years"], {"FS25_Test/a": 1965})
        self.assertEqual(dialog.result["mod_years"], {})
        self.assertEqual(dialog.result["pending"], [])

    def test_invalid_year_keeps_dialog_open(self):
        dialog = self.make_dialog()
        dialog.text.insert("1.0", "FS25_A = abc\n")
        dialog._apply()
        self.assertIsNone(dialog.result)
        self.assertIn("abc", dialog.error_var.get())
        dialog.destroy()

    def test_no_years_shows_error(self):
        dialog = self.make_dialog()
        dialog.text.insert("1.0", "# only comments\n\n")
        dialog._apply()
        self.assertIsNone(dialog.result)
        self.assertIn("No years found", dialog.error_var.get())
        dialog.destroy()


class PasteYearsFlowTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_paste_applies_entries_and_installs(self):
        import shutil
        import tempfile
        import zipfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = make_addon_source(tmp)
        mods_dir = tmp / "mods"

        app = vycompat_gui.VycompatApp(self.root)
        app.last = {
            "mods": [
                fake_mod(
                    status="unsupported",
                    vehicles=[fake_vehicle("Tractor X", xml="a.xml")],
                )
            ]
        }
        result = {
            "mod_years": {"FS25_Test": 1965},
            "vehicle_years": {"FS25_Test/a": 1966},
            "pending": ["FS25_Test/b"],
            "install": True,
        }

        class FakeDialog:
            def __init__(self, parent, install_dir):
                self.result = result

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA", source / "vehicle_years_addon.lua"
        ), mock.patch.object(
            vycompat_gui.vy, "default_mods_dir", return_value=mods_dir
        ), mock.patch.object(
            vycompat_gui, "PasteYearsDialog", FakeDialog
        ), mock.patch.object(
            app.root, "wait_window"
        ), mock.patch.object(
            app, "confirm_addon_changes", return_value=True
        ), mock.patch.object(
            app, "start_scan"
        ) as start_scan, mock.patch.object(
            app, "notify"
        ) as notify, mock.patch.object(
            app, "show_error"
        ) as show_error:
            app.paste_years()

        self.assertFalse(show_error.called)
        self.assertTrue(notify.called)
        message = notify.call_args[0][0]
        self.assertIn("Skipped 1 line", message)
        lua = (source / "vehicle_years_addon.lua").read_text(encoding="utf-8")
        self.assertIn('["FS25_Test"] = 1965', lua)
        self.assertIn('["FS25_Test/a"] = 1966', lua)
        desc = (source / "modDesc.xml").read_text(encoding="utf-8")
        self.assertIn("<version>1.0.1.0</version>", desc)
        self.assertIn("- FS25_Test (Test Mod) - 1965", desc)
        self.assertIn("\n- FS25_Test (Test Mod)\n  - Tractor X - 1966", desc)
        installed = mods_dir / vycompat_gui.vy.ADDON_ZIP_NAME
        self.assertTrue(installed.is_file())
        with zipfile.ZipFile(installed) as zf:
            self.assertIn("vehicle_years_addon.lua", zf.namelist())
        self.assertEqual(app.addon_var.get(), "installed")
        self.assertTrue(start_scan.called)


class EasterEggAppTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_forced_button_is_colourful_and_packed(self):
        app = vycompat_gui.VycompatApp(self.root, easter_egg=True)
        self.assertIsNotNone(app.easter_btn)
        self.assertEqual(app.easter_btn.winfo_manager(), "pack")
        self.assertEqual(app.easter_btn.cget("text"), "AMAZING ICON")
        self.assertIn(app.easter_btn.cget("bg"), app._easter_colors)
        app._cycle_easter_color()
        self.assertIn(app.easter_btn.cget("bg"), app._easter_colors)

    def test_disabled_button_is_not_created(self):
        app = vycompat_gui.VycompatApp(self.root, easter_egg=False)
        self.assertIsNone(app.easter_btn)

    def test_apply_alt_icon_snapshots_and_installs(self):
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        source = tmp / "FS25_VehicleYears_CompatibilityTool"
        source.mkdir()
        (source / "vehicle_years_addon.lua").write_text(
            "local MOD_YEARS = {}\n", encoding="utf-8"
        )
        (source / "modDesc.xml").write_text(
            "<modDesc><version>1.0.0.0</version></modDesc>",
            encoding="utf-8",
        )
        (source / "icon.png").write_bytes(vycompat_icons.main_icon_bytes())
        mods = tmp / "mods"
        mods.mkdir()

        app = vycompat_gui.VycompatApp(self.root, easter_egg=True)
        app.folder_var.set(str(mods))
        app.ensure_addon_source = mock.Mock(return_value=True)

        class FakeDialog:
            def __init__(self, *args, **kwargs):
                self.result = {"icon": "alt", "install": True}

        with mock.patch.object(
            vycompat_gui.vy, "SOURCE_ADDON_LUA",
            source / "vehicle_years_addon.lua",
        ), mock.patch.object(
            app, "addon_install_dir", return_value=mods
        ), mock.patch.object(
            vycompat_gui, "AltIconDialog", FakeDialog
        ), mock.patch.object(
            self.root, "wait_window"
        ), mock.patch.object(
            vycompat_gui.history, "snapshot_addon"
        ) as snapshot, mock.patch.object(
            vycompat_gui.vy, "set_addon_icon",
            return_value={"installed": str(mods / vycompat_gui.vy.ADDON_ZIP_NAME)},
        ) as set_icon, mock.patch.object(
            app, "notify"
        ) as notify:
            app.show_alt_icon()

        snapshot.assert_called_once_with(
            source, reason="before alternate mod icon"
        )
        set_icon.assert_called_once_with(
            source, vycompat_icons.alt_icon_bytes(), install_dir=mods
        )
        self.assertIn("Mod icon changed", notify.call_args[0][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
