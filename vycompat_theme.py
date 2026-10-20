"""FS25-inspired theme for the compatibility tool's Tkinter GUI.

The visual language follows ``docs/UI_SPEC.md``: a dark,
industrial agricultural palette, muted charcoal panels, restrained
green accents and dense, readable tables.  No game artwork or logos are
used -- the header mark is a small original wheat glyph drawn with Tk
canvas primitives.

The module only *styles* the interface.  It never changes scanner
logic, dialog behaviour or file handling.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------------
# design tokens (spec palette)
# ---------------------------------------------------------------------------

BG = "#171A17"
HEADER = "#1B1F1A"
PANEL = "#222722"
PANEL_RAISED = "#2B312B"
PANEL_SELECTED = "#343D32"
GREEN = "#78A83B"
GREEN_HOVER = "#8DBD4D"
GREEN_DARK = "#3D5D26"
TEXT = "#F0F2ED"
TEXT_MUTED = "#B0B7AC"
TEXT_DIM = "#7F897D"
BORDER = "#41483F"
WARNING = "#D6A84B"
DANGER = "#D65C50"
SUCCESS = "#82B85A"
STATUS_BG = "#121512"

# Semantic alias used by the GUI.
TOAST_BG = {
    "success": GREEN_DARK,
    "info": PANEL_SELECTED,
    "warning": "#4A3B1F",
    "error": "#4A2522",
}
TOAST_ACCENT = {
    "success": GREEN,
    "info": GREEN,
    "warning": WARNING,
    "error": DANGER,
}
TOAST_ICON = {
    "success": "\u2713",
    "info": "i",
    "warning": "!",
    "error": "\u00d7",
}

# Fonts that usually exist on Linux, macOS and Windows.  Tk substitutes
# gracefully when a family is missing, but we still pick from the installed
# list so headings stay condensed where possible.
HEADING_FAMILIES = (
    "Nimbus Sans Narrow",
    "Liberation Sans Narrow",
    "DejaVu Sans Condensed",
    "Roboto Condensed",
    "Arial Narrow",
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "Segoe UI",
)
BODY_FAMILIES = (
    "Noto Sans",
    "DejaVu Sans",
    "Liberation Sans",
    "Segoe UI",
    "Helvetica Neue",
    "Arial",
)
MONO_FAMILIES = (
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
    "Consolas",
    "Menlo",
    "Courier New",
)


def _available_families(root):
    try:
        return set(tkfont.families(root))
    except tk.TclError:
        return set()


def _pick_family(root, candidates):
    installed = _available_families(root)
    for name in candidates:
        if name in installed:
            return name
    try:
        return tkfont.nametofont("TkDefaultFont", root=root).actual("family")
    except tk.TclError:
        return "TkDefaultFont"


class Theme:
    """Resolved fonts and helpers for one Tk root."""

    def __init__(self, root):
        self.root = root
        self.heading_family = _pick_family(root, HEADING_FAMILIES)
        self.body_family = _pick_family(root, BODY_FAMILIES)
        self.mono_family = _pick_family(root, MONO_FAMILIES)

    # -- font helpers ------------------------------------------------------

    def heading(self, size=10, weight="bold"):
        return (self.heading_family, size, weight)

    def body(self, size=10, weight="normal"):
        return (self.body_family, size, weight)

    def mono(self, size=10, weight="normal"):
        return (self.mono_family, size, weight)

    def font_spec(self, family, size=10, weight="normal"):
        """Option-database friendly font string."""
        return f"{{{family}}} {size} {weight}".replace(" normal", "")

    def install_named_fonts(self):
        named = (
            ("TkDefaultFont", self.body_family, 10, "normal"),
            ("TkTextFont", self.body_family, 10, "normal"),
            ("TkMenuFont", self.body_family, 10, "normal"),
            ("TkHeadingFont", self.heading_family, 10, "bold"),
            ("TkCaptionFont", self.body_family, 9, "normal"),
            ("TkSmallCaptionFont", self.body_family, 8, "normal"),
            ("TkIconFont", self.body_family, 9, "normal"),
            ("TkTooltipFont", self.body_family, 9, "normal"),
            ("TkFixedFont", self.mono_family, 10, "normal"),
        )
        for name, family, size, weight in named:
            try:
                tkfont.nametofont(name, root=self.root).configure(
                    family=family, size=size, weight=weight
                )
            except tk.TclError:
                pass


def _check_pixels():
    """Two-pixel stroke check mark inside the 14px indicator box."""
    pixels = set()
    # short down stroke: (3,7) -> (6,10)
    for index in range(4):
        x, y = 3 + index, 7 + index
        pixels.update({(x, y), (x + 1, y), (x, y + 1)})
    # long up stroke: (6,10) -> (13,3)
    for index in range(8):
        x, y = 6 + index, 10 - index
        pixels.update({(x, y), (x + 1, y), (x, y - 1)})
    return {
        (x, y) for x, y in pixels
        if 1 <= x <= 12 and 1 <= y <= 12
    }


def _make_check_image(root, selected=False, disabled=False):
    """Original checkbox art: a dark check on a restrained green square."""
    width, height = 20, 14  # 14px box + 6px transparent label gap
    image = tk.PhotoImage(master=root, width=width, height=height)

    if disabled:
        fill = GREEN_DARK if selected else PANEL
        check = TEXT_DIM
    elif selected:
        fill = GREEN
        check = "#12160F"
    else:
        fill = PANEL_RAISED
        check = None

    for y in range(height):
        for x in range(width):
            if x >= 14:
                image.put(PANEL, (x, y))
                try:
                    image.transparency_set(x, y, True)
                except tk.TclError:
                    pass
                continue
            if x in (0, 13) or y in (0, 13):
                color = BORDER
            else:
                color = fill
            image.put(color, (x, y))

    if check:
        for x, y in _check_pixels():
            image.put(check, (x, y))
    return image


def _install_check_indicator(style, th):
    """Replace clam's X-shaped check mark with a real check mark image."""
    th.check_images = {
        "off": _make_check_image(th.root, selected=False),
        "on": _make_check_image(th.root, selected=True),
        "disabled": _make_check_image(th.root, selected=False, disabled=True),
        "on_disabled": _make_check_image(
            th.root, selected=True, disabled=True
        ),
    }
    name = "FS25.Checkbutton.indicator"
    try:
        style.element_create(
            name,
            "image",
            th.check_images["off"],
            ("selected", th.check_images["on"]),
            ("disabled", th.check_images["disabled"]),
            (("selected", "disabled"), th.check_images["on_disabled"]),
        )
    except tk.TclError:
        # A repeated apply on the same interpreter can hit an existing
        # element; the previously created images are still valid.
        pass

    try:
        style.layout(
            "TCheckbutton",
            [
                (
                    "Checkbutton.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            (name, {"side": "left", "sticky": ""}),
                            (
                                "Checkbutton.focus",
                                {
                                    "side": "left",
                                    "sticky": "w",
                                    "children": [
                                        (
                                            "Checkbutton.label",
                                            {"sticky": "nswe"},
                                        )
                                    ],
                                },
                            ),
                        ],
                    },
                )
            ],
        )
    except tk.TclError:
        pass


def _configure_styles(style, th):
    """Apply the complete FS25-inspired style set to a clam ttk theme."""

    # Defaults ---------------------------------------------------------
    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        fieldbackground=PANEL_RAISED,
        bordercolor=BORDER,
        darkcolor=PANEL,
        lightcolor=PANEL,
        troughcolor=STATUS_BG,
        focuscolor=GREEN,
        font=th.body(10),
    )

    # Frames -----------------------------------------------------------
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Raised.TFrame", background=PANEL_RAISED)
    style.configure("Header.TFrame", background=HEADER)
    style.configure("Status.TFrame", background=STATUS_BG)

    # Labels -----------------------------------------------------------
    style.configure("TLabel", background=BG, foreground=TEXT, font=th.body(10))
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Raised.TLabel", background=PANEL_RAISED, foreground=TEXT)
    style.configure("Header.TLabel", background=HEADER, foreground=TEXT)
    style.configure("Status.TLabel", background=STATUS_BG, foreground=TEXT_MUTED)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=TEXT_MUTED)
    style.configure("Dim.TLabel", background=PANEL, foreground=TEXT_DIM)
    style.configure("Section.TLabel", background=PANEL, foreground=TEXT_DIM,
                    font=th.heading(8, "bold"))
    style.configure("SectionBG.TLabel", background=BG, foreground=TEXT_DIM,
                    font=th.heading(8, "bold"))
    style.configure("Title.TLabel", background=HEADER, foreground=TEXT,
                    font=th.heading(18, "bold"))
    style.configure("Subtitle.TLabel", background=HEADER, foreground=TEXT_MUTED,
                    font=th.body(8))
    style.configure("PageTitle.TLabel", background=BG, foreground=TEXT,
                    font=th.heading(15, "bold"))
    style.configure("Metric.TLabel", background=PANEL, foreground=TEXT,
                    font=th.heading(19, "bold"))
    style.configure("MetricCaption.TLabel", background=PANEL, foreground=TEXT_MUTED,
                    font=th.heading(8, "bold"))
    style.configure("Success.TLabel", background=BG, foreground=SUCCESS)
    style.configure("Warning.TLabel", background=BG, foreground=WARNING)
    style.configure("Danger.TLabel", background=BG, foreground=DANGER)

    # Buttons ----------------------------------------------------------
    style.configure(
        "TButton",
        background=PANEL_RAISED,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=PANEL_RAISED,
        darkcolor=PANEL_RAISED,
        focuscolor=GREEN,
        focusthickness=1,
        padding=(12, 6),
        relief="flat",
        font=th.body(9, "bold"),
        anchor="center",
    )
    style.map(
        "TButton",
        background=[
            ("disabled", PANEL),
            ("pressed", GREEN_DARK),
            ("active", PANEL_SELECTED),
        ],
        foreground=[("disabled", TEXT_DIM), ("active", TEXT)],
        bordercolor=[("focus", GREEN), ("active", GREEN_DARK)],
        lightcolor=[("active", PANEL_SELECTED), ("pressed", GREEN_DARK)],
        darkcolor=[("active", PANEL_SELECTED), ("pressed", GREEN_DARK)],
    )
    style.configure(
        "Primary.TButton",
        background=GREEN,
        foreground="#12160F",
        bordercolor=GREEN,
        lightcolor=GREEN,
        darkcolor=GREEN,
        focuscolor=GREEN_HOVER,
        padding=(14, 7),
        font=th.body(9, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[
            ("disabled", PANEL_RAISED),
            ("pressed", GREEN_DARK),
            ("active", GREEN_HOVER),
        ],
        foreground=[("disabled", TEXT_DIM), ("pressed", TEXT), ("active", "#12160F")],
        bordercolor=[("disabled", BORDER), ("active", GREEN_HOVER)],
        lightcolor=[("active", GREEN_HOVER), ("pressed", GREEN_DARK)],
        darkcolor=[("active", GREEN_HOVER), ("pressed", GREEN_DARK)],
    )
    style.configure(
        "Accent.TButton",
        background=GREEN_DARK,
        foreground=TEXT,
        bordercolor=GREEN_DARK,
        lightcolor=GREEN_DARK,
        darkcolor=GREEN_DARK,
        focuscolor=GREEN,
        padding=(12, 7),
        font=th.body(9, "bold"),
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", PANEL),
            ("pressed", "#2F4A1D"),
            ("active", "#4A702E"),
        ],
        foreground=[("disabled", TEXT_DIM), ("active", TEXT)],
        bordercolor=[("disabled", BORDER), ("active", GREEN)],
        lightcolor=[("active", "#4A702E"), ("pressed", "#2F4A1D")],
        darkcolor=[("active", "#4A702E"), ("pressed", "#2F4A1D")],
    )
    style.configure(
        "Small.TButton",
        padding=(8, 4),
        font=th.body(8, "bold"),
    )

    # Entries / comboboxes ---------------------------------------------
    style.configure(
        "TEntry",
        fieldbackground=PANEL_RAISED,
        foreground=TEXT,
        insertcolor=TEXT,
        bordercolor=BORDER,
        lightcolor=PANEL_RAISED,
        darkcolor=PANEL_RAISED,
        padding=(8, 6),
        relief="flat",
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", PANEL)],
        foreground=[("disabled", TEXT_DIM)],
        bordercolor=[("focus", GREEN), ("active", GREEN_DARK)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=PANEL_RAISED,
        background=PANEL_RAISED,
        foreground=TEXT,
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER,
        lightcolor=PANEL_RAISED,
        darkcolor=PANEL_RAISED,
        padding=(8, 5),
        relief="flat",
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", PANEL_RAISED), ("disabled", PANEL)],
        foreground=[("readonly", TEXT), ("disabled", TEXT_DIM)],
        background=[("active", PANEL_SELECTED), ("pressed", PANEL_SELECTED)],
        bordercolor=[("focus", GREEN), ("active", GREEN_DARK)],
        arrowcolor=[("active", GREEN_HOVER), ("disabled", TEXT_DIM)],
    )

    # Check / radio buttons --------------------------------------------
    for base in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            base,
            background=PANEL,
            foreground=TEXT,
            focuscolor=GREEN,
            focusthickness=1,
            indicatorbackground=PANEL_RAISED,
            indicatorforeground=GREEN,
            upperbordercolor=BORDER,
            lowerbordercolor=BORDER,
            indicatorsize=12,
            indicatormargin=(0, 0, 6, 0),
            padding=(0, 4),
            font=th.body(9),
        )
        style.map(
            base,
            background=[("active", PANEL)],
            foreground=[("disabled", TEXT_DIM)],
            indicatorbackground=[
                ("selected", GREEN),
                ("active", PANEL_SELECTED),
                ("disabled", PANEL),
            ],
            indicatorforeground=[
                ("selected", BG),
                ("disabled", TEXT_DIM),
            ],
            upperbordercolor=[("focus", GREEN), ("active", GREEN_DARK)],
            lowerbordercolor=[("focus", GREEN), ("active", GREEN_DARK)],
        )

    # Treeview ---------------------------------------------------------
    style.configure(
        "Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=TEXT,
        borderwidth=0,
        relief="flat",
        rowheight=34,
        font=th.body(10),
    )
    style.map(
        "Treeview",
        background=[("selected", PANEL_SELECTED)],
        foreground=[("selected", TEXT)],
    )
    style.configure(
        "Treeview.Heading",
        background=PANEL_RAISED,
        foreground=TEXT_MUTED,
        bordercolor=BORDER,
        lightcolor=PANEL_RAISED,
        darkcolor=PANEL_RAISED,
        relief="flat",
        borderwidth=0,
        padding=(10, 7),
        font=th.heading(9, "bold"),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", PANEL_SELECTED)],
        foreground=[("active", TEXT)],
    )

    # Scrollbars -------------------------------------------------------
    for orient in ("Vertical", "Horizontal"):
        name = f"{orient}.TScrollbar"
        style.configure(
            name,
            background=PANEL_RAISED,
            troughcolor=BG,
            bordercolor=BORDER,
            arrowcolor=TEXT_MUTED,
            lightcolor=PANEL_RAISED,
            darkcolor=PANEL_RAISED,
            gripcount=0,
            relief="flat",
            arrowsize=12,
        )
        style.map(
            name,
            background=[("active", PANEL_SELECTED), ("pressed", GREEN_DARK)],
            arrowcolor=[("active", GREEN_HOVER)],
        )

    # Progress / separators / paned window -----------------------------
    style.configure(
        "TProgressbar",
        background=GREEN,
        troughcolor=PANEL,
        bordercolor=BORDER,
        lightcolor=GREEN_HOVER,
        darkcolor=GREEN_DARK,
        thickness=6,
    )
    style.configure("TSeparator", background=BORDER)
    style.configure(
        "TPanedwindow",
        background=BG,
        sashwidth=6,
        sashrelief="flat",
        borderwidth=0,
    )
    style.configure("Sash", background=BORDER, sashthickness=6)


def apply_theme(root):
    """Install the FS25-inspired theme on *root* and return a Theme."""

    th = Theme(root)
    root.configure(bg=BG)
    th.install_named_fonts()

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    _configure_styles(style, th)
    _install_check_indicator(style, th)

    # Option-database colours for widgets ttk does not style directly.
    options = {
        "*Toplevel.background": BG,
        "*Menu.background": PANEL,
        "*Menu.foreground": TEXT,
        "*Menu.activeBackground": PANEL_SELECTED,
        "*Menu.activeForeground": TEXT,
        "*Menu.selectColor": GREEN,
        "*TCombobox*Listbox.background": PANEL_RAISED,
        "*TCombobox*Listbox.foreground": TEXT,
        "*TCombobox*Listbox.selectBackground": PANEL_SELECTED,
        "*TCombobox*Listbox.selectForeground": TEXT,
        "*TCombobox*Listbox.font": th.font_spec(th.body_family, 10),
    }
    for pattern, value in options.items():
        root.option_add(pattern, value)

    try:
        root._vycompat_theme = th
    except (AttributeError, tk.TclError):
        pass

    return th


# ---------------------------------------------------------------------------
# widget helpers
# ---------------------------------------------------------------------------

def card(parent, background=PANEL):
    """A rectangular panel with a subtle one-pixel border."""
    return tk.Frame(
        parent,
        bg=background,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0,
    )


def separator(parent, background=BORDER):
    return tk.Frame(parent, bg=background, height=1, bd=0)


def style_text(widget, background=PANEL, foreground=TEXT, font=None):
    """Apply the dark editor styling to a ``tk.Text`` widget."""
    widget.configure(
        bg=background,
        fg=foreground,
        insertbackground=TEXT,
        selectbackground=GREEN_DARK,
        selectforeground=TEXT,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=GREEN,
        relief="flat",
        borderwidth=0,
        padx=10,
        pady=8,
    )
    if font is not None:
        widget.configure(font=font)


def style_dialog(dialog):
    try:
        dialog.configure(bg=BG)
    except tk.TclError:
        pass


def short_path(path):
    if path is None:
        return ""
    text = str(path)
    home = str(Path.home())
    if text == home:
        return "~"
    if text.startswith(home + "/"):
        return "~" + text[len(home):]
    return text


def center_dialog(dialog, parent=None):
    """Place a dialog over its parent, clamped to the visible screen."""
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    if width <= 1:
        width = dialog.winfo_reqwidth()
    if height <= 1:
        height = dialog.winfo_reqheight()

    screen_w = dialog.winfo_screenwidth()
    screen_h = dialog.winfo_screenheight()

    if parent is not None and parent.winfo_exists() and parent.winfo_ismapped():
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
    else:
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

    # Keep a margin for the window manager title bar / bottom panel.
    x = max(8, min(x, screen_w - width - 8))
    y = max(48, min(y, screen_h - height - 48))
    dialog.geometry(f"+{x}+{y}")


def reveal_dialog(dialog, parent=None):
    """Center, lift and focus a dialog, then take a modal grab."""
    dialog.update_idletasks()
    center_dialog(dialog, parent)
    try:
        dialog.deiconify()
    except tk.TclError:
        pass
    try:
        if parent is not None:
            dialog.transient(parent)
    except tk.TclError:
        pass
    try:
        dialog.lift()
    except tk.TclError:
        pass
    try:
        if parent is not None and parent.winfo_ismapped():
            dialog.wait_visibility()
    except tk.TclError:
        pass
    try:
        dialog.grab_set()
    except tk.TclError:
        pass
    try:
        dialog.focus_force()
    except tk.TclError:
        pass


def draw_brand_mark(canvas, size=38):
    """Draw an original wheat-spike mark (no game assets)."""
    canvas.delete("all")
    canvas.configure(bg=HEADER, highlightthickness=0, width=size, height=size)
    margin = 2
    canvas.create_oval(
        margin, margin, size - margin, size - margin,
        outline=GREEN, width=2,
    )
    cx = size / 2
    top = size * 0.26
    bottom = size * 0.76
    canvas.create_line(cx, bottom, cx, top, fill=GREEN, width=2)
    for offset in (0.34, 0.45, 0.56, 0.67):
        y = size * offset
        canvas.create_line(cx, y, cx - size * 0.15, y - size * 0.07,
                           fill=GREEN, width=2)
        canvas.create_line(cx, y, cx + size * 0.15, y - size * 0.07,
                           fill=GREEN, width=2)
    canvas.create_line(cx - size * 0.10, bottom, cx + size * 0.10, bottom,
                       fill=GREEN, width=2)
