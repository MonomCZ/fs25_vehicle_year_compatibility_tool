"""In-app tutorial for the FS25 Vehicle Year Compatibility Tool GUI.

The guide deliberately uses a normal, non-modal ``Toplevel`` instead of a
fixed-size dialog or a spotlight overlay.  Tiling window managers such as
Hyprland can move, tile and resize it freely; the text column re-wraps and the
body scrolls, while the navigation footer always stays visible.

There are no external images.  The small step icons are original Tk canvas
line art built from the same charcoal/green palette as the rest of the app.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import vycompat_theme as theme

# ---------------------------------------------------------------------------
# content (kept as plain data so it can be tested without a display)
# ---------------------------------------------------------------------------

TUTORIAL_STEPS = (
    {
        "kicker": "START HERE",
        "title": "Welcome to the compatibility tool",
        "icon": "welcome",
        "lead": (
            "The tool finds FS25 vehicles and implements that still have no "
            "production year. It reads mod ZIPs and unpacked mod folders "
            "without extracting or changing them."
        ),
        "sections": (
            {
                "heading": "Three places a year can come from",
                "bullets": (
                    "The mod itself \u2014 a <year> tag in the item XML.",
                    "Vehicle Years \u2014 the database inside "
                    "FS25_Vehicle_Years.zip.",
                    "The compatibility addon \u2014 MOD_YEARS, "
                    "MOD_VEHICLE_YEARS and BASE_GAME_YEARS.",
                ),
            },
            {
                "heading": "You are in control",
                "text": (
                    "A scan is read-only. Writes happen only when you export "
                    "years, use one of the optional Advanced exports, or "
                    "leave the install box ticked while rebuilding the "
                    "compatibility addon."
                ),
            },
        ),
        "find": "Reopen this guide at any time with F1 or the HELP button.",
        "tip": "Use the left and right arrow keys to move through the guide; "
               "Esc closes it.",
    },
    {
        "kicker": "SCAN",
        "title": "Choose a folder and scan",
        "icon": "folder",
        "lead": (
            "The folder at the top is where the scanner looks for mod ZIPs "
            "and unpacked mod folders."
        ),
        "sections": (
            {
                "heading": "Pick the mods folder",
                "bullets": (
                    "Type or paste a path into MODS FOLDER, or press "
                    "BROWSE... to choose one.",
                    "Press GAME MODS to jump to the installed FS25 mods "
                    "folder.",
                    "Tick Base game vehicles in the left rail to include "
                    "vehicles that ship with the game.",
                    "If no compatibility addon is found, a setup prompt "
                    "appears. Nothing is written unless you confirm it.",
                ),
            },
            {
                "heading": "Start the scan",
                "text": (
                    "Press SCAN MODS in the header, or press F5. Scans run in "
                    "the background, so the window stays responsive."
                ),
            },
        ),
        "find": "If the result is empty, make sure the folder directly "
                "contains the ZIP files or mod folders.",
        "tip": "Use F5 later to rescan after adding or updating mods.",
    },
    {
        "kicker": "LIBRARY",
        "title": "Read the library",
        "icon": "list",
        "lead": (
            "Problem mods are listed first. The status column says whether a "
            "mod needs years and, for supported mods, where its years come "
            "from."
        ),
        "sections": (
            {
                "heading": "Status at a glance",
                "bullets": (
                    "Needs years \u2014 one or more vehicles or implements "
                    "still need a year.",
                    "Supported \u2014 the mod itself, Vehicle Years, the "
                    "compatibility addon, or a combination of them supplies "
                    "the years.",
                    "Select a row to see every item and its year in DETAILS.",
                ),
            },
            {
                "heading": "Filter the list",
                "text": (
                    "The left rail filters All mods, Needs years and "
                    "Supported. Hidden appears in Advanced for maps, "
                    "placeables and FS22 or older mods."
                ),
            },
            {
                "heading": "Find a mod",
                "text": (
                    "SEARCH (or Ctrl+F) matches titles, ZIP names, vehicles, "
                    "brands, categories and addon keys."
                ),
            },
        ),
        "find": "Simple view uses friendly mod titles. Advanced view shows "
                "the ZIP file names instead.",
        "tip": "The Details pane explains the full source for each vehicle, "
               "not just the short status.",
    },
    {
        "kicker": "ADVANCED",
        "title": "Advanced view and exports",
        "icon": "sliders",
        "lead": (
            "Tick Advanced view when you need technical details or one of "
            "the optional reports."
        ),
        "sections": (
            {
                "heading": "What Advanced adds",
                "bullets": (
                    "ZIP file names, environment, descVersion, vehicle and "
                    "missing counts.",
                    "The Hidden filter for non-vehicle mods and FS22 or "
                    "older mods.",
                    "ADDON SOURCE, to read the installed addon ZIP or the "
                    "source Lua.",
                ),
            },
            {
                "heading": "Export buttons",
                "bullets": (
                    "SAVE JSON... writes a machine-readable report.",
                    "APPEND YEARS_INFO... adds unresolved items to a "
                    "years_info.txt file.",
                    "COPY UNSUPPORTED... copies mods that need years into a "
                    "folder you choose.",
                ),
            },
        ),
        "find": "The export buttons appear in the action bar only while "
                "Advanced view is ticked.",
        "tip": "Reports are optional; they do not change the mods themselves.",
    },
    {
        "kicker": "ADD YEARS",
        "title": "Add missing years",
        "icon": "year",
        "lead": (
            "For one mod at a time, let the tool update the compatibility "
            "addon for you. If it is missing, ADDON SETUP... can create a "
            "blank Vehicle Years Compatibility Tool mod."
        ),
        "sections": (
            {
                "heading": "Fill the gaps",
                "bullets": (
                    "Filter Needs years, select the mod, then press "
                    "ADD YEARS...",
                    "Choose one year for the whole mod or a different year "
                    "for each vehicle.",
                    "Years must be between 1900 and 2030.",
                    "SAVE & EXPORT opens a review of every added or changed "
                    "entry; nothing is written until WRITE & REBUILD.",
                    "The compatibility addon Lua and modDesc are updated, the "
                    "version is bumped and the ZIP is rebuilt.",
                    "Leave the install box ticked to copy the rebuilt "
                    "compatibility addon into the game mods folder; untick it "
                    "to only build it.",
                ),
            },
            {
                "heading": "After saving",
                "bullets": (
                    "Restart the game or reload the save so the new "
                    "compatibility addon is loaded.",
                    "A snapshot is taken before each write. Use ADDON HISTORY... to "
                    "restore an older compatibility addon and rebuild its ZIP.",
                    "Existing years are never overwritten: the mod's own year "
                    "and the Vehicle Years database still win.",
                ),
            },
        ),
        "find": "Select a mod whose status says Needs years to enable ADD "
                "YEARS... in the action bar.",
        "tip": "If you only want a ZIP to install later, untick the install "
               "box.",
    },
    {
        "kicker": "BULK YEARS",
        "title": "Bulk years and shortcuts",
        "icon": "chat",
        "lead": (
            "For many unresolved items, use Copy years and Paste years with "
            "an external AI, then apply everything in one go."
        ),
        "sections": (
            {
                "heading": "The copy-and-paste workflow",
                "bullets": (
                    "COPY YEARS... copies a verification prompt and one "
                    "KEY = ? line for every item that still needs a year.",
                    "Paste it into ChatGPT or another assistant, fill in the "
                    "years, then press PASTE YEARS... and paste the answer.",
                    "Lines marked ? or unknown are skipped. Existing years "
                    "are left alone.",
                    "Review the complete plan, then confirm; the same "
                    "snapshot and ADDON HISTORY... undo apply.",
                    "The app exports all filled entries together.",
                ),
            },
            {
                "heading": "Keyboard",
                "text": (
                    "F1 opens this guide, F5 rescans, Ctrl+F searches, Tab "
                    "moves focus, the left and right arrow keys change steps, "
                    "and Esc closes the guide."
                ),
            },
        ),
        "find": "Nothing is written until you confirm the review or press "
                "Write & rebuild.",
        "tip": "That is the whole tour. Press Finish to close it and go back "
               "to the library.",
    },
)


# ---------------------------------------------------------------------------
# responsive tutorial window
# ---------------------------------------------------------------------------

class TutorialWindow(tk.Toplevel):
    """A non-modal, resize-friendly guide to the compatibility tool GUI.

    The window is intentionally *not* transient, does not grab input and does
    not position itself using screen coordinates.  That keeps it usable as a
    normal tiled window under Hyprland and other tiling window managers.
    """

    INITIAL_GEOMETRY = "680x620"
    MIN_WIDTH = 340
    MIN_HEIGHT = 240
    MAX_CONTENT_WIDTH = 860
    MAX_TEXT_WIDTH = 760
    HORIZONTAL_PADDING = 48

    def __init__(self, parent, th=None, start_step=0):
        super().__init__(parent)
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)

        self.current = 0
        self._content_width = 620
        self._wrap_labels = []
        self._scroll_after = None
        self._focus_after = None
        self._closing = False

        theme.style_dialog(self)
        self.title("How to use the compatibility tool")
        self.geometry(self.INITIAL_GEOMETRY)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.resizable(True, True)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

        self.bind("<Escape>", self._on_close)
        self.bind("<Left>", self._on_left)
        self.bind("<Right>", self._on_right)
        self.bind("<Home>", lambda _event: self.set_step(0))
        self.bind("<End>", lambda _event: self.set_step(len(TUTORIAL_STEPS) - 1))
        self.bind("<Prior>", lambda _event: self._scroll(-1))
        self.bind("<Next>", lambda _event: self._scroll(1))
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", self._on_wheel)
        self.bind("<Button-5>", self._on_wheel)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.set_step(start_step)
        self._focus_after = self.after_idle(self._initial_focus)

    # -- construction ------------------------------------------------------

    def _build_header(self):
        header = tk.Frame(self, bg=theme.HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        self.header = header
        self.icon_canvas = tk.Canvas(
            header, width=34, height=34, bg=theme.HEADER,
            highlightthickness=0, bd=0,
        )
        self.icon_canvas.grid(row=0, column=0, padx=(16, 10), pady=10)

        self.header_titles = tk.Frame(header, bg=theme.HEADER)
        self.header_titles.grid(row=0, column=1, sticky="w")
        self.header_title = tk.Label(
            self.header_titles, text="HOW TO USE THE TOOL", bg=theme.HEADER,
            fg=theme.TEXT, font=self.th.heading(12, "bold"), anchor="w",
        )
        self.header_title.pack(anchor="w")
        self.header_subtitle = tk.Label(
            self.header_titles, text="Quick guide", bg=theme.HEADER,
            fg=theme.TEXT_MUTED, font=self.th.body(8), anchor="w",
        )
        self.header_subtitle.pack(anchor="w")

        self.close_btn = ttk.Button(
            header, text="CLOSE", style="Small.TButton", command=self._on_close,
        )
        self.close_btn.grid(row=0, column=2, padx=(10, 16), pady=10)

        theme.separator(header).grid(
            row=1, column=0, columnspan=3, sticky="ew"
        )
        header.bind("<Configure>", self._on_header_configure)

    def _build_body(self):
        content = tk.Frame(self, bg=theme.BG)
        content.grid(row=1, column=0, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        self.body_wrap = content

        self.canvas = tk.Canvas(
            content, bg=theme.BG, highlightthickness=0, bd=0,
            xscrollincrement=1, yscrollincrement=24,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(
            content, orient="vertical", command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.inner = tk.Frame(self.canvas, bg=theme.BG)
        self._inner_window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw",
        )
        self.step_frame = tk.Frame(self.inner, bg=theme.BG)
        self.step_frame.pack(fill="both", expand=True, padx=24, pady=18)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.inner.bind("<Configure>", self._on_inner_configure)

    def _build_footer(self):
        footer = tk.Frame(self, bg=theme.PANEL)
        footer.grid(row=2, column=0, sticky="ew")
        theme.separator(footer).pack(side="top", fill="x")
        inner = tk.Frame(footer, bg=theme.PANEL)
        inner.pack(fill="x", padx=16, pady=9)
        self.footer_inner = inner

        self.progress_var = tk.StringVar(value="1 / 1")
        self.progress_label = tk.Label(
            inner, textvariable=self.progress_var, bg=theme.PANEL,
            fg=theme.TEXT_DIM, font=self.th.heading(8, "bold"), anchor="w",
        )
        self.progress_label.pack(side="left")

        self.keyboard_hint = tk.Label(
            inner, text="\u2190 \u2192  STEP     ESC  CLOSE", bg=theme.PANEL,
            fg=theme.TEXT_DIM, font=self.th.body(8), anchor="w",
        )
        self.keyboard_hint.pack(side="left", padx=(16, 0))

        self.next_btn = ttk.Button(
            inner, text="NEXT", style="Primary.TButton", command=self._advance,
        )
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(
            inner, text="BACK", command=self.previous_step,
        )
        self.back_btn.pack(side="right", padx=(0, 8))

        inner.bind("<Configure>", self._on_footer_configure)

    # -- responsive layout -------------------------------------------------

    def _on_canvas_configure(self, event):
        width = max(1, event.width)
        content_width = min(width, self.MAX_CONTENT_WIDTH)
        x = max(0, (width - content_width) // 2)
        self._content_width = content_width
        self.canvas.coords(self._inner_window, x, 0)
        self.canvas.itemconfigure(self._inner_window, width=content_width)
        self._update_wraps()
        self._schedule_scrollregion()
        self.canvas.xview_moveto(0)

    def _on_inner_configure(self, _event=None):
        self._schedule_scrollregion()

    def _on_header_configure(self, event):
        # A tiling WM can ignore the requested minimum size.  Below the
        # normal minimum, drop the decorative icon and shorten the title so
        # the CLOSE button remains reachable.
        if event.width < 340:
            if self.icon_canvas.winfo_manager():
                self.icon_canvas.grid_remove()
            if self.header_subtitle.winfo_manager():
                self.header_subtitle.pack_forget()
            if self.header_title.cget("text") != "COMPATIBILITY TOOL GUIDE":
                self.header_title.configure(text="COMPATIBILITY TOOL GUIDE")
        else:
            if not self.icon_canvas.winfo_manager():
                self.icon_canvas.grid()
            if not self.header_subtitle.winfo_manager():
                self.header_subtitle.pack(anchor="w")
            if self.header_title.cget("text") != "HOW TO USE THE TOOL":
                self.header_title.configure(text="HOW TO USE THE TOOL")

    def _on_footer_configure(self, event):
        # At narrow widths the keyboard reminder is the first thing to go,
        # then the step counter and some padding.  BACK/NEXT stay visible at
        # every width the window can reasonably be tiled to.
        if event.width < 560:
            if self.keyboard_hint.winfo_manager():
                self.keyboard_hint.pack_forget()
        elif not self.keyboard_hint.winfo_manager():
            self.keyboard_hint.pack(side="left", padx=(16, 0))

        if event.width < 300:
            if self.progress_label.winfo_manager():
                self.progress_label.pack_forget()
            self.footer_inner.pack_configure(padx=8)
        else:
            if not self.progress_label.winfo_manager():
                if self.keyboard_hint.winfo_manager():
                    self.progress_label.pack(
                        side="left", before=self.keyboard_hint
                    )
                else:
                    self.progress_label.pack(side="left")
            self.footer_inner.pack_configure(padx=16)

    def _wrap_width(self, max_width, extra=0):
        available = self._content_width - self.HORIZONTAL_PADDING - extra
        return max(140, min(max_width, available))

    def _register_wrap(self, label, max_width=None, extra=0):
        max_width = max_width or self.MAX_TEXT_WIDTH
        self._wrap_labels.append((label, max_width, extra))
        label.configure(wraplength=self._wrap_width(max_width, extra))
        return label

    def _update_wraps(self):
        for label, max_width, extra in self._wrap_labels:
            try:
                label.configure(
                    wraplength=self._wrap_width(max_width, extra)
                )
            except tk.TclError:
                pass

    def _schedule_scrollregion(self):
        if self._scroll_after is not None:
            return
        try:
            self._scroll_after = self.after_idle(self._apply_scrollregion)
        except tk.TclError:
            self._scroll_after = None

    def _apply_scrollregion(self):
        self._scroll_after = None
        if self._closing:
            return
        try:
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.configure(scrollregion=bbox)
            else:
                self.canvas.configure(scrollregion=(0, 0, 0, 0))
        except tk.TclError:
            pass

    # -- step rendering ----------------------------------------------------

    def set_step(self, index):
        if not TUTORIAL_STEPS:
            return
        index = max(0, min(int(index), len(TUTORIAL_STEPS) - 1))
        self.current = index
        step = TUTORIAL_STEPS[index]
        self._clear_step()
        self._draw_icon(step.get("icon", "welcome"))
        self._render_step(step)
        self._update_footer()
        self.canvas.yview_moveto(0)
        self._schedule_scrollregion()

    def _clear_step(self):
        self._wrap_labels = []
        for child in self.step_frame.winfo_children():
            child.destroy()

    def _render_step(self, step):
        tk.Label(
            self.step_frame, text=step.get("kicker", "").upper(),
            bg=theme.BG, fg=theme.GREEN, font=self.th.heading(8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))

        self.step_title = tk.Label(
            self.step_frame, text=step["title"], bg=theme.BG,
            fg=theme.TEXT, font=self.th.heading(20, "bold"), anchor="w",
            justify="left",
        )
        self.step_title.pack(fill="x")
        self._register_wrap(self.step_title, self.MAX_TEXT_WIDTH)

        if step.get("lead"):
            lead = tk.Label(
                self.step_frame, text=step["lead"], bg=theme.BG,
                fg=theme.TEXT_MUTED, font=self.th.body(11), anchor="w",
                justify="left",
            )
            lead.pack(fill="x", pady=(6, 14))
            self._register_wrap(lead, self.MAX_TEXT_WIDTH)

        for section in step.get("sections", ()):
            self._render_section(section)

        if step.get("find"):
            self._render_callout(
                "WHERE TO FIND IT", step["find"], theme.GREEN,
                background=theme.PANEL,
            )
        if step.get("tip"):
            self._render_callout(
                "TIP", step["tip"], theme.WARNING,
                background=theme.PANEL_RAISED,
            )

        tk.Frame(self.step_frame, bg=theme.BG, height=4).pack(fill="x")

    def _render_section(self, section):
        if section.get("heading"):
            heading = tk.Label(
                self.step_frame, text=section["heading"].upper(),
                bg=theme.BG, fg=theme.TEXT, font=self.th.heading(9, "bold"),
                anchor="w",
            )
            heading.pack(fill="x", pady=(8, 3))
            self._register_wrap(heading, self.MAX_TEXT_WIDTH)

        if section.get("text"):
            text = tk.Label(
                self.step_frame, text=section["text"], bg=theme.BG,
                fg=theme.TEXT_MUTED, font=self.th.body(10), anchor="w",
                justify="left",
            )
            text.pack(fill="x")
            self._register_wrap(text, self.MAX_TEXT_WIDTH)

        bullets = section.get("bullets", ())
        if bullets:
            body = "\n".join("\u2022  " + bullet for bullet in bullets)
            label = tk.Label(
                self.step_frame, text=body, bg=theme.BG, fg=theme.TEXT_MUTED,
                font=self.th.body(10), anchor="w", justify="left",
            )
            label.pack(fill="x")
            self._register_wrap(label, self.MAX_TEXT_WIDTH)

    def _render_callout(self, caption, text, accent, background):
        outer = tk.Frame(
            self.step_frame, bg=background, bd=0,
            highlightbackground=theme.BORDER, highlightthickness=1,
        )
        outer.pack(fill="x", pady=(10, 0))
        tk.Frame(outer, bg=accent, width=3).pack(side="left", fill="y")
        content = tk.Frame(outer, bg=background)
        content.pack(side="left", fill="both", expand=True, padx=11, pady=8)
        tk.Label(
            content, text=caption, bg=background, fg=accent,
            font=self.th.heading(8, "bold"), anchor="w",
        ).pack(fill="x")
        label = tk.Label(
            content, text=text, bg=background, fg=theme.TEXT_MUTED,
            font=self.th.body(9), anchor="w", justify="left",
        )
        label.pack(fill="x", pady=(2, 0))
        self._register_wrap(label, self.MAX_TEXT_WIDTH - 20, extra=24)

    def _update_footer(self):
        total = len(TUTORIAL_STEPS)
        self.progress_var.set(f"{self.current + 1} / {total}")
        self.back_btn.config(
            state="normal" if self.current > 0 else "disabled"
        )
        self.next_btn.config(
            text="FINISH" if self.current == total - 1 else "NEXT"
        )

    def _draw_icon(self, kind):
        canvas = self.icon_canvas
        canvas.delete("all")
        canvas.create_rectangle(
            2, 2, 32, 32, fill=theme.GREEN_DARK, outline=theme.BORDER
        )
        ink = theme.GREEN_HOVER
        if kind == "folder":
            canvas.create_line(7, 12, 7, 25, 27, 25, 27, 13, 17, 13,
                               16, 10, 7, 10, 7, 12, fill=ink, width=2)
            canvas.create_line(10, 17, 24, 17, fill=ink, width=1)
        elif kind == "list":
            for y in (11, 17, 23):
                canvas.create_rectangle(8, y - 2, 12, y + 2,
                                        fill=theme.GREEN, outline="")
                canvas.create_line(15, y, 27, y, fill=ink, width=2)
        elif kind == "sliders":
            for y, knob in ((11, 21), (17, 13), (23, 24)):
                canvas.create_line(8, y, 26, y, fill=ink, width=1)
                canvas.create_rectangle(knob - 2, y - 3, knob + 2, y + 3,
                                        fill=theme.GREEN, outline="")
        elif kind == "year":
            canvas.create_rectangle(9, 9, 26, 26, outline=ink, width=2)
            canvas.create_line(9, 14, 26, 14, fill=ink, width=1)
            canvas.create_line(13, 7, 13, 11, fill=ink, width=2)
            canvas.create_line(22, 7, 22, 11, fill=ink, width=2)
            canvas.create_text(17, 21, text="20", fill=theme.GREEN,
                               font=self.th.heading(7, "bold"))
        elif kind == "chat":
            canvas.create_line(8, 10, 27, 10, 27, 22, 17, 22, 12, 26,
                               12, 22, 8, 22, 8, 10, fill=ink, width=2)
            for x in (13, 17, 21):
                canvas.create_rectangle(x, 15, x + 2, 17,
                                        fill=theme.GREEN, outline="")
        else:  # welcome wheat
            canvas.create_line(17, 26, 17, 8, fill=ink, width=2)
            for y in (11, 16, 21):
                canvas.create_line(17, y, 11, y - 3, fill=ink, width=2)
                canvas.create_line(17, y, 23, y - 3, fill=ink, width=2)
            canvas.create_line(13, 26, 21, 26, fill=theme.GREEN, width=2)

    # -- navigation --------------------------------------------------------

    def previous_step(self):
        if self.current > 0:
            self.set_step(self.current - 1)
        return "break"

    def next_step(self):
        if self.current < len(TUTORIAL_STEPS) - 1:
            self.set_step(self.current + 1)
        return "break"

    def _advance(self):
        if self.current >= len(TUTORIAL_STEPS) - 1:
            self._on_close()
        else:
            self.set_step(self.current + 1)
        return "break"

    def _on_left(self, _event=None):
        self.previous_step()
        return "break"

    def _on_right(self, _event=None):
        self.next_step()
        return "break"

    def _scroll(self, direction):
        try:
            self.canvas.yview_scroll(direction * 3, "units")
        except tk.TclError:
            pass
        return "break"

    def _on_wheel(self, event):
        if getattr(event, "num", None) == 4:
            delta = -3
        elif getattr(event, "num", None) == 5:
            delta = 3
        else:
            delta = -3 if getattr(event, "delta", 0) > 0 else 3
        try:
            self.canvas.yview_scroll(delta, "units")
        except tk.TclError:
            pass
        return "break"

    def _initial_focus(self):
        self._focus_after = None
        try:
            if self.winfo_exists():
                self.lift()
                self.focus_set()
        except tk.TclError:
            pass

    def _on_close(self, _event=None):
        self._closing = True
        if self._scroll_after is not None:
            try:
                self.after_cancel(self._scroll_after)
            except tk.TclError:
                pass
            self._scroll_after = None
        self.destroy()
        return "break"

    def destroy(self):
        self._closing = True
        for attr in ("_scroll_after", "_focus_after"):
            after_id = getattr(self, attr, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attr, None)
        super().destroy()
