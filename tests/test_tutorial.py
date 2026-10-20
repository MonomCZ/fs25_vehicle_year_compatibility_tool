#!/usr/bin/env python3
"""Tests for the compatibility tool in-app tutorial."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import tkinter as tk

    import vycompat_theme as theme
    import vycompat_tutorial as tutorial
except ImportError as exc:  # tkinter missing on this Python
    raise unittest.SkipTest(f"tkinter not available: {exc}")


class TutorialContentTest(unittest.TestCase):
    def test_has_six_steps_with_expected_titles(self):
        self.assertEqual(len(tutorial.TUTORIAL_STEPS), 6)
        titles = [step["title"] for step in tutorial.TUTORIAL_STEPS]
        self.assertEqual(
            titles,
            [
                "Welcome to the compatibility tool",
                "Choose a folder and scan",
                "Read the library",
                "Advanced view and exports",
                "Add missing years",
                "Bulk years and shortcuts",
            ],
        )

    def test_every_step_has_helpful_content(self):
        icons = set()
        for step in tutorial.TUTORIAL_STEPS:
            icons.add(step["icon"])
            self.assertTrue(step["kicker"])
            self.assertTrue(step["lead"])
            self.assertTrue(step["find"])
            self.assertTrue(step["tip"])
            self.assertLessEqual(len(step["title"]), 45)
            self.assertTrue(step["sections"])
            for section in step["sections"]:
                self.assertTrue(section.get("text") or section.get("bullets"))
                for bullet in section.get("bullets", ()):
                    self.assertLessEqual(len(bullet), 160)
        self.assertEqual(
            icons,
            {"welcome", "folder", "list", "sliders", "year", "chat"},
        )

    def test_mentions_the_real_controls_and_safety(self):
        text = repr(tutorial.TUTORIAL_STEPS)
        for label in (
            "SCAN MODS",
            "ADD YEARS...",
            "COPY YEARS...",
            "PASTE YEARS...",
            "F1",
            "F5",
            "HELP",
            "SEARCH",
            "Ctrl+F",
            "WRITE & REBUILD",
            "HISTORY...",
            "read-only",
            "never overwritten",
        ):
            self.assertIn(label, text)


class TutorialWindowTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        self.th = theme.apply_theme(self.root)
        self.dialog = tutorial.TutorialWindow(self.root, th=self.th)
        self.dialog.withdraw()

    def tearDown(self):
        for widget in (getattr(self, "dialog", None), self.root):
            try:
                if widget is not None and widget.winfo_exists():
                    widget.destroy()
            except tk.TclError:
                pass

    def test_navigation_and_footer_state(self):
        self.assertEqual(self.dialog.current, 0)
        self.assertEqual(str(self.dialog.back_btn.cget("state")), "disabled")
        self.assertEqual(str(self.dialog.next_btn.cget("text")), "NEXT")
        self.assertEqual(self.dialog.progress_var.get(), "1 / 6")

        self.dialog.next_step()
        self.assertEqual(self.dialog.current, 1)
        self.assertEqual(str(self.dialog.back_btn.cget("state")), "normal")
        self.assertEqual(self.dialog.progress_var.get(), "2 / 6")

        self.dialog.set_step(5)
        self.assertEqual(str(self.dialog.next_btn.cget("text")), "FINISH")
        self.assertEqual(self.dialog.progress_var.get(), "6 / 6")
        self.dialog._advance()
        self.assertFalse(self.dialog.winfo_exists())

    def test_keyboard_navigation_and_no_modal_grab(self):
        self.assertEqual(self.dialog.grab_current(), None)
        self.assertEqual(
            self.dialog.wm_transient(), ""
        )
        self.dialog._on_right()
        self.assertEqual(self.dialog.current, 1)
        self.dialog._on_left()
        self.assertEqual(self.dialog.current, 0)

    def test_narrow_layout_wraps_and_keeps_footer(self):
        # A tiling WM may ignore geometry requests, so drive the responsive
        # callbacks directly with the width a narrow tile would report.
        self.dialog._on_canvas_configure(SimpleNamespace(width=347))
        self.dialog._on_footer_configure(SimpleNamespace(width=328))
        self.dialog.update_idletasks()

        self.assertEqual(self.dialog._content_width, 347)
        self.assertEqual(self.dialog.footer_inner.winfo_manager(), "pack")
        self.assertEqual(self.dialog.next_btn.winfo_manager(), "pack")
        self.assertEqual(self.dialog.back_btn.winfo_manager(), "pack")
        self.assertEqual(self.dialog.keyboard_hint.winfo_manager(), "")
        self.assertEqual(self.dialog.progress_label.winfo_manager(), "pack")
        self.assertEqual(self.dialog.canvas.itemcget(
            self.dialog._inner_window, "width"
        ), "347")

        # An aggressively tiled window can be narrower than the requested
        # minimum: shorten the header and keep BACK/NEXT on screen.
        self.dialog._on_header_configure(SimpleNamespace(width=280))
        self.assertEqual(
            self.dialog.header_title.cget("text"), "COMPATIBILITY TOOL GUIDE"
        )
        self.assertEqual(self.dialog.icon_canvas.winfo_manager(), "")
        self.assertEqual(self.dialog.header_subtitle.winfo_manager(), "")
        self.dialog._on_footer_configure(SimpleNamespace(width=280))
        self.assertEqual(self.dialog.progress_label.winfo_manager(), "")
        self.assertEqual(
            int(self.dialog.footer_inner.pack_info()["padx"]), 8
        )

        self.dialog._on_header_configure(SimpleNamespace(width=680))
        self.assertEqual(
            self.dialog.header_title.cget("text"), "HOW TO USE THE TOOL"
        )
        self.assertEqual(self.dialog.icon_canvas.winfo_manager(), "grid")
        self.assertEqual(self.dialog.header_subtitle.winfo_manager(), "pack")
        self.dialog._on_footer_configure(SimpleNamespace(width=680))
        self.assertEqual(self.dialog.keyboard_hint.winfo_manager(), "pack")
        self.assertEqual(self.dialog.progress_label.winfo_manager(), "pack")
        self.assertEqual(
            int(self.dialog.footer_inner.pack_info()["padx"]), 16
        )

        wraps = [
            int(label.cget("wraplength"))
            for label, _max_width, _extra in self.dialog._wrap_labels
        ]
        self.assertTrue(wraps)
        self.assertTrue(all(width <= 320 for width in wraps))
        self.assertTrue(all(width >= 100 for width in wraps))

        bbox = self.dialog.canvas.bbox("all")
        self.assertIsNotNone(bbox)
        self.assertGreater(bbox[3] - bbox[1], 0)

    def test_wide_layout_caps_reading_width(self):
        self.dialog._on_canvas_configure(SimpleNamespace(width=1600))
        self.dialog._on_footer_configure(SimpleNamespace(width=1568))
        self.dialog.update_idletasks()

        self.assertEqual(
            self.dialog._content_width,
            tutorial.TutorialWindow.MAX_CONTENT_WIDTH,
        )
        self.assertEqual(self.dialog.keyboard_hint.winfo_manager(), "pack")

        wraps = [
            int(label.cget("wraplength"))
            for label, _max_width, _extra in self.dialog._wrap_labels
        ]
        self.assertTrue(wraps)
        self.assertLessEqual(max(wraps), tutorial.TutorialWindow.MAX_TEXT_WIDTH)

        bbox = self.dialog.canvas.bbox("all")
        self.assertIsNotNone(bbox)
        self.assertLessEqual(
            bbox[2] - bbox[0],
            tutorial.TutorialWindow.MAX_CONTENT_WIDTH,
        )


class TutorialAppIntegrationTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        import vycompat_gui

        self.gui = vycompat_gui
        self.app = vycompat_gui.VycompatApp(self.root)

    def tearDown(self):
        try:
            if self.app.tutorial is not None:
                self.app.tutorial.destroy()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_help_button_and_f1_open_one_tutorial(self):
        self.assertTrue(self.app.help_btn)
        self.assertTrue(self.root.bind("<F1>"))
        self.app.open_tutorial()
        first = self.app.tutorial
        self.assertIsNotNone(first)
        self.assertTrue(first.winfo_exists())
        self.app.open_tutorial()
        self.assertIs(self.app.tutorial, first)
        self.assertEqual(first.grab_current(), None)

    def test_empty_state_points_to_help(self):
        self.app.last = None
        self.assertIn("F1", self.app._empty_details())
        self.app._set_details(self.app._empty_details())
        self.assertIn("F1", self.app.details.get("1.0", "end"))


if __name__ == "__main__":
    unittest.main()
