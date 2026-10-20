#!/usr/bin/env python3
"""Tests for the FS25-inspired compatibility tool theme (no scanner required)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vycompat_theme as theme


class PaletteTest(unittest.TestCase):
    def test_palette_tokens(self):
        self.assertEqual(theme.BG, "#171A17")
        self.assertEqual(theme.PANEL, "#222722")
        self.assertEqual(theme.PANEL_RAISED, "#2B312B")
        self.assertEqual(theme.GREEN, "#78A83B")
        self.assertEqual(theme.TEXT, "#F0F2ED")
        self.assertEqual(theme.BORDER, "#41483F")
        self.assertEqual(theme.DANGER, "#D65C50")
        self.assertEqual(theme.SUCCESS, "#82B85A")

    def test_toast_semantics(self):
        self.assertEqual(set(theme.TOAST_BG), {"success", "info", "warning", "error"})
        self.assertEqual(set(theme.TOAST_ACCENT), set(theme.TOAST_BG))
        self.assertEqual(set(theme.TOAST_ICON), set(theme.TOAST_BG))
        for kind in theme.TOAST_BG:
            self.assertTrue(theme.TOAST_ICON[kind])


class ThemeTest(unittest.TestCase):
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
        except Exception:
            pass

    def test_apply_theme_installs_clam_and_styles(self):
        from tkinter import ttk

        th = theme.apply_theme(self.root)
        style = ttk.Style(self.root)
        self.assertEqual(style.theme_use(), "clam")
        self.assertEqual(style.lookup("Primary.TButton", "background"), theme.GREEN)
        self.assertEqual(style.lookup("Accent.TButton", "background"), theme.GREEN_DARK)
        self.assertEqual(style.lookup("Treeview", "background"), theme.PANEL)
        self.assertEqual(
            style.lookup("Treeview.Heading", "background"), theme.PANEL_RAISED
        )
        self.assertEqual(style.lookup("TEntry", "fieldbackground"), theme.PANEL_RAISED)
        self.assertEqual(style.lookup("TCheckbutton", "background"), theme.PANEL)
        self.assertEqual(style.lookup("TLabel", "background"), theme.BG)
        self.assertTrue(th.heading_family)
        self.assertTrue(th.body_family)
        self.assertTrue(th.mono_family)
        self.assertIs(getattr(self.root, "_vycompat_theme"), th)

    def test_custom_check_indicator(self):
        from tkinter import ttk

        th = theme.apply_theme(self.root)
        style = ttk.Style(self.root)
        self.assertIn("FS25.Checkbutton.indicator", str(style.layout("TCheckbutton")))
        self.assertEqual(
            set(th.check_images), {"off", "on", "disabled", "on_disabled"}
        )
        self.assertNotEqual(
            th.check_images["off"].get(5, 5), th.check_images["on"].get(5, 5)
        )
        # The check mark itself is dark on the selected image, not a green X.
        self.assertEqual(th.check_images["on"].get(6, 10), (18, 22, 15))

    def test_font_helpers_return_tuples(self):
        th = theme.Theme(self.root)
        heading = th.heading(12, "bold")
        self.assertEqual(len(heading), 3)
        self.assertEqual(heading[1], 12)
        self.assertEqual(heading[2], "bold")
        self.assertEqual(th.body(10)[1], 10)
        self.assertEqual(th.mono(9)[1], 9)
        self.assertTrue(th.heading_family)
        self.assertTrue(th.body_family)
        self.assertTrue(th.mono_family)
        spec = th.font_spec(th.body_family, 10)
        self.assertIn(th.body_family, spec)
        self.assertIn("10", spec)

    def test_style_text_colors(self):
        import tkinter as tk

        text = tk.Text(self.root)
        theme.style_text(text, font=("TkFixedFont", 9))
        self.assertEqual(text.cget("background"), theme.PANEL)
        self.assertEqual(text.cget("foreground"), theme.TEXT)
        self.assertEqual(text.cget("insertbackground"), theme.TEXT)
        self.assertEqual(text.cget("selectbackground"), theme.GREEN_DARK)
        self.assertEqual(text.cget("highlightbackground"), theme.BORDER)
        text.destroy()

    def test_card_and_separator(self):
        card = theme.card(self.root)
        self.assertEqual(card.cget("background"), theme.PANEL)
        self.assertEqual(card.cget("highlightbackground"), theme.BORDER)
        self.assertEqual(int(card.cget("highlightthickness")), 1)
        sep = theme.separator(self.root)
        self.assertEqual(sep.cget("background"), theme.BORDER)
        self.assertEqual(int(sep.cget("height")), 1)

    def test_short_path(self):
        home = Path.home()
        self.assertEqual(theme.short_path(home / "mods"), "~/mods")
        self.assertEqual(theme.short_path("/opt/fs25/mods"), "/opt/fs25/mods")
        self.assertEqual(theme.short_path(None), "")

    def test_center_dialog_clamps_to_screen(self):
        import tkinter as tk

        dialog = tk.Toplevel(self.root)
        dialog.geometry("400x300+90000+90000")
        theme.center_dialog(dialog, None)
        dialog.update_idletasks()
        geometry = dialog.geometry()
        self.assertRegex(geometry, r"^\d+x\d+[+-]\d+[+-]\d+$")
        size, x, y = geometry.replace("+", " +").replace("-", " -").split()
        width, height = (int(part) for part in size.split("x"))
        self.assertGreaterEqual(int(x), 0)
        self.assertGreaterEqual(int(y), 0)
        self.assertLessEqual(int(x) + width, dialog.winfo_screenwidth())
        self.assertLessEqual(int(y) + height, dialog.winfo_screenheight())
        dialog.destroy()

    def test_brand_mark_draws_original_glyph(self):
        import tkinter as tk

        canvas = tk.Canvas(self.root, width=38, height=38)
        theme.draw_brand_mark(canvas)
        self.assertGreaterEqual(len(canvas.find_all()), 5)
        canvas.destroy()


if __name__ == "__main__":
    unittest.main()
