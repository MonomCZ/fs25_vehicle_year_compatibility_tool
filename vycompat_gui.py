#!/usr/bin/env python3
"""FS25 Vehicle Year Compatibility Tool - Tkinter front end.

Launch with ``python3 vycompat_gui.py`` or ``python3 vycompat.py --gui``.

Simple by default: only the mod list with a status that says *how* a mod is
covered, plus the vehicles that still need a year. The technical dump (keys,
environment, descVersion, non-vehicle/skipped mods, export buttons) appears
when the "Advanced" checkbox is ticked.

"Add years..." opens a dialog for the selected mod: type one year for the whole
mod or one per vehicle.  The app then shows a review of every added or changed
entry; nothing is written until "Write & rebuild" is confirmed.  It snapshots
the compatibility-addon source, edits the Lua and modDesc, bumps the version,
rebuilds the ZIP and (when selected) installs it into the game mods folder.
"ADDON HISTORY..." lists the local snapshots and can restore one.  "Copy years..."
copies the ChatGPT verification prompt with the per-item KEY = ? list for
everything that still needs a year; fill in the years and paste it back with
"Paste years..." to apply them all at once (with the same review and snapshot).
The SEARCH box and Ctrl+F filter the library by title, ZIP, vehicle, brand,
category or addon key.  Everything else is read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
import time
import traceback
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

import vycompat as vy
import vycompat_history as history
import vycompat_icons as icons
import vycompat_theme as theme
import vycompat_tutorial as tutorial

WINDOW_TITLE = vy.APP_NAME

STATUS_TAG = {
    "unsupported": "bad",
    "partial": "warn",
    "supported": "good",
    "no-vehicles": "muted",
    "skipped": "muted",
    "error": "bad",
}

STATUS_ORDER = {
    "unsupported": 0,
    "partial": 1,
    "error": 2,
    "supported": 3,
    "skipped": 4,
    "no-vehicles": 5,
}

SOURCE_PHRASE = {
    "own": "in the mod itself",
    "vy": "in the Vehicle Years mod",
    "addon-vehicle": "added by the compatibility tool",
    "addon-mod": "added by the compatibility tool",
    "addon-base": "added by the compatibility tool",
}


# ---------------------------------------------------------------------------
# pure data helpers (testable without a display)
# ---------------------------------------------------------------------------

def plural(count, singular):
    return singular if count == 1 else singular + "s"


def source_phrase(source):
    return SOURCE_PHRASE.get(source, source)


def support_phrase(sources):
    """Human explanation of how the years are supplied, e.g. 'in the mod itself'."""
    sources = list(sources)
    phrases = []
    if "own" in sources:
        phrases.append(SOURCE_PHRASE["own"])
    if "vy" in sources:
        phrases.append(SOURCE_PHRASE["vy"])
    if any(source.startswith("addon") for source in sources):
        phrases.append(SOURCE_PHRASE["addon-mod"])
    return " and ".join(phrases) if phrases else "unknown"


def status_text(status, sources, missing=0, total=0):
    if status == "supported":
        return f"Supported \u2014 {support_phrase(sources)}"
    if status == "partial":
        return f"Needs years ({missing} of {total})"
    if status == "unsupported":
        plural = "s" if missing != 1 else ""
        return f"Needs years ({missing} vehicle{plural})"
    if status == "skipped":
        return "Skipped (FS22 or older)"
    if status == "no-vehicles":
        return "Not a vehicle mod"
    return "Error"


def supported_status(row, advanced=False):
    """Says *how* a supported mod is covered, without a clipped table cell."""
    if row["kind"] == "mod":
        sources = [v["source"] for v in row["mod"]["vehicles"]]
    else:
        sources = [item["source"] for item in row["base_items"]]
    if advanced:
        tags = []
        if "own" in sources:
            tags.append("mod")
        if "vy" in sources:
            tags.append("VY")
        if any(source.startswith("addon") for source in sources):
            tags.append("tool")
        if len(tags) == 3:
            return "Supported - all"
        return "Supported - " + "+".join(tags) if tags else "Supported"
    phrases = []
    if "own" in sources:
        phrases.append("mod itself")
    if "vy" in sources:
        phrases.append("Vehicle Years")
    if any(source.startswith("addon") for source in sources):
        phrases.append("compatibility tool")
    if len(phrases) == 3:
        return "Supported \u2014 all sources"
    return "Supported \u2014 " + " + ".join(phrases) if phrases else "Supported"


def compact_status(row):
    """Short status for the advanced table, where the columns are narrow."""
    status = row["status"]
    if status == "supported":
        return supported_status(row, advanced=True)
    if status == "partial":
        return f"Needs years {row['missing']}/{row['vehicles']}"
    if status == "unsupported":
        return f"Needs years ({row['missing']})"
    if status == "skipped":
        return "Skipped (FS22)"
    if status == "no-vehicles":
        return "Not a vehicle"
    return "Error"


def tree_status(row, advanced=False):
    if row["status"] == "supported":
        return supported_status(row, advanced=advanced)
    return compact_status(row) if advanced else row["status_text"]


def row_search_text(row):
    """Searchable text for a library row: mod title, file, vehicles and keys."""
    parts = [
        str(row.get("label") or ""),
        str(row.get("status") or ""),
        str(row.get("status_text") or ""),
    ]
    if row["kind"] == "mod":
        mod = row["mod"]
        parts.extend(
            str(value or "")
            for value in (
                mod.get("file"),
                mod.get("title"),
                mod.get("custom_environment"),
                mod.get("version"),
                mod.get("error"),
            )
        )
        for vehicle in mod.get("vehicles") or []:
            parts.extend(
                str(value if value is not None else "")
                for value in (
                    vehicle.get("name"),
                    vehicle.get("xml"),
                    vehicle.get("brand"),
                    vehicle.get("category"),
                    vehicle.get("year"),
                    vehicle.get("addon_vehicle_key"),
                    vehicle.get("addon_mod_key"),
                    vehicle.get("vy_key"),
                )
            )
    else:
        for item in row.get("base_items") or []:
            parts.extend(
                str(value if value is not None else "")
                for value in (
                    item.get("raw_xml"),
                    item.get("key"),
                    item.get("brand"),
                    item.get("name"),
                    item.get("category"),
                    item.get("year"),
                )
            )
    return " ".join(parts).casefold()


def row_matches_search(row, query):
    """Every whitespace-separated search token must occur in the row."""
    tokens = [token for token in str(query).casefold().split() if token]
    if not tokens:
        return True
    haystack = row_search_text(row)
    return all(token in haystack for token in tokens)


PREVIEW_ACTION_ORDER = {"updated": 0, "added": 1, "unchanged": 2}


def preview_counts(entries):
    counts = {"updated": 0, "added": 0, "unchanged": 0}
    for entry in entries:
        action = entry.get("action")
        if action in counts:
            counts[action] += 1
    return counts


def preview_summary(entries, pending=0):
    counts = preview_counts(entries)
    parts = []
    if counts["updated"]:
        parts.append(
            f"{counts['updated']} "
            f"{'entry' if counts['updated'] == 1 else 'entries'} changed"
        )
    if counts["added"]:
        parts.append(
            f"{counts['added']} "
            f"{'entry' if counts['added'] == 1 else 'entries'} added"
        )
    if counts["unchanged"]:
        parts.append(
            f"{counts['unchanged']} already present"
        )
    if pending:
        parts.append(
            f"{pending} {plural(pending, 'line')} skipped (still ? or no year)"
        )
    return ", ".join(parts) if parts else "No changes."


def preview_action_text(entry):
    action = entry.get("action")
    year = entry.get("year")
    if action == "updated":
        old = entry.get("old_year")
        if old is None:
            return f"CHANGE -> {year}"
        return f"CHANGE {old} -> {year}"
    if action == "added":
        return f"ADD {year}"
    if action == "unchanged":
        return f"{year} (unchanged)"
    return str(action or "")


def preview_action_tag(entry):
    return {
        "updated": "preview-change",
        "added": "preview-add",
        "unchanged": "preview-same",
    }.get(entry.get("action"), "preview-same")


def sorted_preview_entries(entries):
    return sorted(
        entries,
        key=lambda entry: (
            PREVIEW_ACTION_ORDER.get(entry.get("action"), 9),
            str(entry.get("table") or ""),
            str(entry.get("key") or ""),
        ),
    )


def format_snapshot_time(value):
    """2026-10-20T01:23:45+02:00 -> 2026-10-20 01:23."""
    text = str(value or "").replace("T", " ")
    return text[:16] if text else "unknown time"


def mod_row(mod):
    missing = vy.missing_vehicles(mod)
    title = f"  -  {mod['title']}" if mod["title"] else ""
    return {
        "kind": "mod",
        "label": f"{mod['file']}{title}",
        "status": mod["status"],
        "status_text": status_text(
            mod["status"],
            [vehicle["source"] for vehicle in mod["vehicles"]],
            len(missing),
            len(mod["vehicles"]),
        ),
        "missing": len(missing),
        "vehicles": len(mod["vehicles"]),
        "mod": mod,
        "base_items": None,
    }


def base_row(base_items):
    missing = [item for item in base_items if item["source"] == "none"]
    status = "unsupported" if missing else "supported"
    count = len(base_items)
    plural = "" if count == 1 else "s"
    return {
        "kind": "base",
        "label": f"BASE GAME  -  {count} vehicle{plural}",
        "status": status,
        "status_text": status_text(
            status,
            [item["source"] for item in base_items],
            len(missing),
            len(base_items),
        ),
        "missing": len(missing),
        "vehicles": len(base_items),
        "mod": None,
        "base_items": base_items,
    }


def gui_rows(mods, base_items=None, advanced=False):
    """Rows for the tree view: problems first; non-vehicle/skipped only in advanced."""
    rows = [mod_row(mod) for mod in mods]
    if not advanced:
        rows = [row for row in rows if row["status"] not in ("no-vehicles", "skipped")]
        # The simple view is the friendly library: use the mod title (the
        # file name is shown in Details and in the technical advanced view).
        for row in rows:
            if row["kind"] == "mod":
                row["label"] = row["mod"]["title"] or row["mod"]["file"]
    else:
        # Advanced mode is the technical view: show the file name in the
        # narrow list column (the title stays in the details pane).
        for row in rows:
            if row["kind"] == "mod":
                row["label"] = row["mod"]["file"]
    rows.sort(key=lambda row: (STATUS_ORDER.get(row["status"], 9), row["label"].lower()))
    if base_items is not None:
        row = base_row(base_items)
        if row["missing"]:
            rows.insert(0, row)
        else:
            rows.append(row)
    return rows


def format_mod_details_simple(mod):
    """Short, human readable summary - no keys, no technical fields."""
    header = mod["file"] + (f" \u2014 {mod['title']}" if mod["title"] else "")
    lines = [header, ""]
    vehicles = mod["vehicles"]
    missing = vy.missing_vehicles(mod)
    status = mod["status"]

    if status == "error":
        reason = f": {mod['error']}" if mod.get("error") else "."
        lines.append(f"Could not check this mod{reason}")
        return "\n".join(lines)
    if status == "skipped":
        lines.append("Skipped - built for FS22 or an older game.")
        return "\n".join(lines)

    if status == "supported":
        lines.append(f"Supported \u2014 {support_phrase([v['source'] for v in vehicles])}")
    elif status == "partial":
        lines.append(f"Needs years for {len(missing)} of {len(vehicles)} vehicles:")
    else:
        plural = "s" if len(missing) != 1 else ""
        lines.append(f"Needs years for {len(missing)} vehicle{plural}:")
    lines.append("")

    annotate = len({source_phrase(v["source"]) for v in vehicles if v["source"] != "none"}) > 1
    for vehicle in vehicles:
        name = vehicle["name"] or vehicle["xml"]
        if vehicle["source"] == "none":
            lines.append(f"  \u2022 {name} \u2014 needs a year")
            continue
        year = f"{vehicle['year']} " if vehicle["year"] is not None else ""
        if annotate:
            lines.append(f"  \u2022 {name} \u2014 {year}({source_phrase(vehicle['source'])})")
        else:
            lines.append(f"  \u2022 {name} \u2014 {year}".rstrip())
    return "\n".join(lines)


def format_base_details_simple(base_items):
    missing = [item for item in base_items if item["source"] == "none"]
    lines = [f"Base game \u2014 {len(base_items)} vehicles checked", ""]
    if missing:
        if len(missing) == 1:
            lines.append("1 base game vehicle needs a year:")
        else:
            lines.append(f"{len(missing)} base game vehicles need years:")
        for item in missing:
            lines.append(f"  \u2022 {item['name']}")
    else:
        lines.append(
            f"All supported \u2014 {support_phrase([item['source'] for item in base_items])}"
        )
    return "\n".join(lines)


def format_mod_details(mod):
    """Advanced, technical view of one mod."""
    lines = [
        f"File        : {mod['file']}",
    ]
    if mod["title"]:
        lines.append(f"Title       : {mod['title']}")
    lines.append(f"Environment : {mod['custom_environment']}")
    lines.append(f"descVersion : {mod['desc_version']}    version: {mod['version']}")
    lines.append(f"Status      : {status_text(mod['status'], [v['source'] for v in mod['vehicles']], len(vy.missing_vehicles(mod)), len(mod['vehicles']))}")
    if mod.get("error"):
        lines.append(f"Error       : {mod['error']}")
    if mod.get("non_vehicle_items"):
        lines.append(f"Non-vehicle store items skipped: {mod['non_vehicle_items']}")
    lines.append("")

    missing = vy.missing_vehicles(mod)
    if len(missing) > 1 and len(missing) == len(mod["vehicles"]):
        lines.append("All vehicles are missing a year. If they share one year:")
        lines.append(f'    MOD_YEARS["{mod["custom_environment"]}"] = ?,')
        lines.append("")

    if mod["vehicles"]:
        lines.append("Vehicles:")
        for vehicle in mod["vehicles"]:
            year = f" {vehicle['year']}" if vehicle["year"] is not None else ""
            lines.append(f"  [{vehicle['source']}{year}] {vy.vehicle_label(vehicle)}")
            if vehicle["source"] == "none":
                lines.append(
                    f'        MOD_VEHICLE_YEARS["{vehicle["addon_vehicle_key"]}"] = ?,'
                )
    else:
        lines.append("No vehicle/implement store items found.")

    if mod.get("missing"):
        lines.append("")
        lines.append("Referenced files missing from the mod:")
        for name in mod["missing"]:
            lines.append(f"    {name}")
    return "\n".join(lines)


def format_base_details(base_items):
    """Advanced, technical view of the base game scan."""
    missing = [item for item in base_items if item["source"] == "none"]
    lines = [f"{len(base_items)} base game vehicles checked, {len(missing)} without a year", ""]
    if not missing:
        lines.append("All base game vehicles have a year.")
        return "\n".join(lines)
    lines.append("raw_xml | BRAND | Name | category")
    for item in missing:
        lines.append(f'{item["raw_xml"]} | {item["brand"]} | {item["name"]} | {item["category"]}')
    return "\n".join(lines)


def format_details(row, advanced=False):
    if row["kind"] == "base":
        if advanced:
            return format_base_details(row["base_items"])
        return format_base_details_simple(row["base_items"])
    if advanced:
        return format_mod_details(row["mod"])
    return format_mod_details_simple(row["mod"])


# ---------------------------------------------------------------------------
# application
# ---------------------------------------------------------------------------

FILTERS = {
    "all": ("All mods", None),
    "needs": ("Needs years", ("unsupported", "partial", "error")),
    "supported": ("Supported", ("supported",)),
    "hidden": ("Hidden", ("no-vehicles", "skipped")),
}


class NavItem(tk.Frame):
    """A keyboard-accessible library filter row for the left rail."""

    def __init__(self, parent, text, command, th):
        super().__init__(
            parent,
            bg=theme.PANEL,
            cursor="hand2",
            takefocus=1,
            highlightthickness=1,
            highlightbackground=theme.PANEL,
            highlightcolor=theme.GREEN,
            bd=0,
        )
        self.command = command
        self.th = th
        self.selected = False
        self.hovered = False

        self.indicator = tk.Frame(self, bg=theme.PANEL, width=3, bd=0)
        self.indicator.pack(side="left", fill="y")
        self.label = tk.Label(
            self, text=text, bg=theme.PANEL, fg=theme.TEXT_MUTED,
            font=th.body(9), anchor="w", padx=9, pady=7, bd=0,
        )
        self.label.pack(side="left", fill="x", expand=True)
        self.count = tk.Label(
            self, text="", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=th.body(8), anchor="e", padx=9, bd=0,
        )
        self.count.pack(side="right", fill="y")

        for widget in (self, self.label, self.count, self.indicator):
            widget.bind("<Button-1>", self._invoke)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
        self.bind("<Return>", self._invoke)
        self.bind("<space>", self._invoke)
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)

    def _invoke(self, _event=None):
        try:
            self.focus_set()
        except tk.TclError:
            pass
        self.command()
        return "break"

    def _enter(self, _event=None):
        self.hovered = True
        self._paint()

    def _leave(self, _event=None):
        self.hovered = False
        self._paint()

    def _focus_in(self, _event=None):
        self.configure(highlightbackground=theme.GREEN)

    def _focus_out(self, _event=None):
        self.configure(
            highlightbackground=theme.GREEN if self.selected else theme.PANEL
        )

    def _paint(self):
        if self.selected:
            bg = theme.PANEL_SELECTED
            fg = theme.TEXT
        elif self.hovered:
            bg = theme.PANEL_RAISED
            fg = theme.TEXT
        else:
            bg = theme.PANEL
            fg = theme.TEXT_MUTED
        self.configure(bg=bg)
        self.label.configure(bg=bg, fg=fg)
        self.count.configure(
            bg=bg,
            fg=theme.GREEN if self.selected else theme.TEXT_DIM,
        )
        self.indicator.configure(bg=theme.GREEN if self.selected else theme.PANEL)

    def set_selected(self, selected):
        self.selected = bool(selected)
        self.configure(
            highlightbackground=theme.GREEN if self.selected else theme.PANEL
        )
        self._paint()

    def set_count(self, value):
        text = "" if value is None else str(value)
        self.count.configure(text=text)


class MessageDialog(tk.Toplevel):
    """Small themed modal for errors that need the user's attention."""

    def __init__(self, parent, title, message, kind="info", details=None, th=None):
        super().__init__(parent)
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)
        theme.style_dialog(self)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        accent = {
            "success": theme.SUCCESS,
            "warning": theme.WARNING,
            "error": theme.DANGER,
            "info": theme.GREEN,
        }.get(kind, theme.GREEN)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(body, bg=accent, width=4).pack(side="left", fill="y")
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            content, text=message, bg=theme.PANEL, fg=theme.TEXT,
            font=self.th.body(10), justify="left", anchor="w",
            wraplength=520,
        ).pack(anchor="w", fill="x")

        if details:
            details_frame = tk.Frame(content, bg=theme.PANEL)
            details_frame.pack(fill="both", expand=True, pady=(10, 0))
            details_frame.rowconfigure(0, weight=1)
            details_frame.columnconfigure(0, weight=1)
            text = tk.Text(details_frame, width=72, height=8, wrap="word")
            theme.style_text(text, background=theme.PANEL_RAISED,
                             font=self.th.mono(9))
            text.insert("1.0", details)
            text.config(state="disabled")
            text.grid(row=0, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(
                details_frame, orient="vertical", command=text.yview
            )
            text.configure(yscrollcommand=scroll.set)
            scroll.grid(row=0, column=1, sticky="ns")

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(
            buttons, text="CLOSE", style="Primary.TButton", command=self.destroy
        ).pack(side="right")

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self.destroy())
        theme.reveal_dialog(self, parent)


class AltIconDialog(tk.Toplevel):
    """Optional alternate icon for the in-game compatibility mod."""

    ACCENT = "#E85AA6"
    ACCENT_DARK = "#7A4FD9"
    GOLD = "#F2C14E"

    def __init__(self, parent, source_dir, install_dir=None, current="custom",
                 th=None):
        super().__init__(parent)
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)
        self.source_dir = Path(source_dir)
        self.install_dir = Path(install_dir) if install_dir else None
        self.current = current
        self.result = None
        self._preview_images = []

        theme.style_dialog(self)
        self.title("Amazing icon")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(body, bg=self.ACCENT, width=4).pack(side="left", fill="y")
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(side="left", fill="both", expand=True, padx=18, pady=16)

        tk.Label(
            content, text="AMAZING ICON", bg=theme.PANEL, fg=self.ACCENT,
            font=self.th.heading(17, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            content,
            text=(
                "You found the secret mod icon. Make the compatibility mod "
                "stand out in the FS25 mod list?"
            ),
            bg=theme.PANEL, fg=theme.TEXT, font=self.th.body(10),
            anchor="w", justify="left", wraplength=600,
        ).pack(fill="x", pady=(2, 0))

        previews = tk.Frame(content, bg=theme.PANEL)
        previews.pack(fill="x", pady=(14, 4))
        current_path = self.source_dir / vy.ADDON_ICON_NAME
        current_name = {
            "main": "MAIN ICON",
            "alt": "ALT ICON",
            "custom": "CUSTOM ICON",
            "missing": "NO ICON",
        }.get(self.current, "CUSTOM ICON")
        self._add_preview(
            previews, current_path, f"CURRENT: {current_name}", 0
        )
        self._add_preview(
            previews, icons.icon_path(icons.ALT_ICON_NAME),
            "SECRET ALT ICON", 1,
        )

        self.install_var = tk.BooleanVar(value=bool(self.install_dir))
        if self.install_dir is not None:
            ttk.Checkbutton(
                content,
                text="Install the rebuilt ZIP into the game mods folder",
                variable=self.install_var,
            ).pack(anchor="w", pady=(10, 0))
            tk.Label(
                content, text=theme.short_path(self.install_dir),
                bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
                anchor="w", justify="left", wraplength=600,
            ).pack(fill="x", padx=(24, 0), pady=(2, 0))
        else:
            tk.Label(
                content,
                text="The ZIP will be rebuilt but not installed automatically.",
                bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
                anchor="w", justify="left", wraplength=600,
            ).pack(fill="x", pady=(10, 0))

        tk.Label(
            content,
            text=(
                "A source snapshot is saved first. Restart FS25 after "
                "installing to see the new icon."
            ),
            bg=theme.PANEL, fg=theme.TEXT_MUTED, font=self.th.body(8),
            anchor="w", justify="left", wraplength=600,
        ).pack(fill="x", pady=(8, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(
            buttons, text="NOT NOW", style="Small.TButton",
            command=self.destroy,
        ).pack(side="right")

        primary_icon = "main" if self.current == "alt" else "alt"
        primary_text = (
            "RESTORE MAIN ICON" if primary_icon == "main" else "USE ALT ICON"
        )
        ttk.Button(
            buttons, text=primary_text, style="Primary.TButton",
            command=lambda: self._accept(primary_icon),
        ).pack(side="right", padx=(0, 8))
        if self.current in ("custom", "missing"):
            ttk.Button(
                buttons, text="RESTORE MAIN ICON", style="Small.TButton",
                command=lambda: self._accept("main"),
            ).pack(side="right", padx=(0, 8))

        self._primary_icon = primary_icon
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept(self._primary_icon))
        theme.reveal_dialog(self, parent)

    def _add_preview(self, parent, path, caption, column):
        frame = tk.Frame(parent, bg=theme.PANEL)
        frame.grid(row=0, column=column, padx=(0, 24), sticky="n")
        image = None
        try:
            if Path(path).is_file():
                image = tk.PhotoImage(file=str(path))
                factor = max(1, image.width() // 128)
                if factor > 1:
                    image = image.subsample(factor, factor)
        except tk.TclError:
            image = None
        if image is not None:
            self._preview_images.append(image)
            tk.Label(
                frame, image=image, bg=theme.PANEL, bd=0,
                highlightthickness=1, highlightbackground=theme.BORDER,
            ).pack()
        else:
            tk.Label(
                frame, text="(icon missing)", bg=theme.PANEL,
                fg=theme.TEXT_DIM, font=self.th.body(8),
                width=16, height=8,
            ).pack()
        tk.Label(
            frame, text=caption, bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.th.heading(8, "bold"), anchor="w",
        ).pack(fill="x", pady=(5, 0))

    def _accept(self, icon):
        self.result = {
            "icon": icon,
            "install": bool(self.install_var.get()),
        }
        self.destroy()


class AddonSetupDialog(tk.Toplevel):
    """Confirm creating or installing the compatibility addon."""

    def __init__(self, parent, mode, source_dir, install_dir, th=None):
        super().__init__(parent)
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)
        self.result = False
        self.mode = mode
        theme.style_dialog(self)
        self.title(
            {
                "install": "Compatibility addon not installed",
                "extract": "Editable addon source needed",
            }.get(mode, "Compatibility addon not found")
        )
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        if mode == "install":
            message = (
                "The compatibility addon source is ready, but it is not "
                "installed in the selected mods folder.\n\n"
                "Build the ZIP and install Vehicle Years Compatibility Tool "
                "now?"
            )
            labels = ("Source folder", "Install target")
            paths = (str(source_dir), str(install_dir))
        elif mode == "extract":
            message = (
                "The compatibility addon is installed, but no editable source "
                "was found.\n\n"
                "Copy the installed addon to a new source folder so Add years "
                "can edit it? Existing years are preserved."
            )
            labels = ("Installed addon", "New source folder")
            paths = (str(install_dir), str(source_dir))
        else:
            message = (
                "No Vehicle Years compatibility addon was found.\n\n"
                "Create a blank Vehicle Years Compatibility Tool mod and "
                "install it now? You can add years after the scan."
            )
            labels = ("Source folder", "Install target")
            paths = (str(source_dir), str(install_dir))

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Frame(body, bg=theme.WARNING, width=4).pack(side="left", fill="y")
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            content, text=message, bg=theme.PANEL, fg=theme.TEXT,
            font=self.th.body(10), justify="left", anchor="w",
            wraplength=520,
        ).pack(anchor="w", fill="x")

        details = tk.Frame(content, bg=theme.PANEL)
        details.pack(fill="x", pady=(10, 0))
        for label, value in zip(labels, paths):
            row = tk.Frame(details, bg=theme.PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(
                row, text=label.upper(), bg=theme.PANEL, fg=theme.TEXT_DIM,
                font=self.th.heading(8, "bold"), width=14, anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=value, bg=theme.PANEL, fg=theme.TEXT_MUTED,
                font=self.th.mono(9), anchor="w", justify="left",
                wraplength=390,
            ).pack(side="left", fill="x", expand=True)

        tk.Label(
            content,
            text=(
                "Nothing is written until you press the button below."
                if mode == "create" else
                "The installed addon is copied; existing years are preserved."
                if mode == "extract" else
                "The existing source is reused; no years are changed."
            ),
            bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
            anchor="w", justify="left", wraplength=520,
        ).pack(anchor="w", fill="x", pady=(10, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(
            buttons, text="NOT NOW", style="Small.TButton",
            command=self.destroy,
        ).pack(side="right")
        primary = ttk.Button(
            buttons,
            text={
                "install": "INSTALL EXISTING",
                "extract": "EXTRACT SOURCE",
            }.get(mode, "CREATE BLANK MOD"),
            style="Primary.TButton",
            command=self._accept,
        )
        primary.pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._accept())
        theme.reveal_dialog(self, parent)

    def _accept(self):
        self.result = True
        self.destroy()


class VycompatApp:
    def __init__(self, root, easter_egg=None):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.minsize(980, 620)
        self.root.geometry("1280x760")
        self.theme = theme.apply_theme(root)

        self._window_icon = None
        self._apply_window_icon()
        self.easter_egg_visible = icons.should_show_easter_egg(
            force=easter_egg
        )
        self.easter_btn = None
        self._easter_colors = (
            "#D94F9E", "#7A4FD9", "#2BB3C0", "#E0A82E",
        )
        self._easter_color_index = 0

        self.closing = False
        self.last = None
        self.rows_by_iid = {}
        self.scanning = False
        self._reselect_file = None
        self._hover_iid = None
        self._toast_after = None
        self._empty_view = False
        self._pane_sash_done = False
        self._hscroll_after_id = None
        self._startup_after = None
        self._addon_setup_dismissed = set()
        self.tutorial = None

        self.folder_var = tk.StringVar()
        self.base_var = tk.BooleanVar(value=False)
        self.nonfs25_var = tk.BooleanVar(value=False)
        self.advanced_var = tk.BooleanVar(value=False)
        self.addon_var = tk.StringVar(value="installed")
        self.filter_var = tk.StringVar(value="all")
        self.search_var = tk.StringVar()
        self.summary_var = tk.StringVar(
            value="No scan yet - pick a folder and press Scan."
        )
        self.status_var = tk.StringVar(value="Ready")
        self.header_status_var = tk.StringVar(value="READY")
        self.page_title_var = tk.StringVar(value="ALL MODS")
        self.metric_mods_var = tk.StringVar(value="\u2014")
        self.metric_vehicles_var = tk.StringVar(value="\u2014")
        self.metric_supported_var = tk.StringVar(value="\u2014")
        self.metric_need_var = tk.StringVar(value="\u2014")

        default_mods = vy.default_mods_dir()
        self.folder_var.set(str(default_mods) if default_mods else "")

        self._build()
        self.root.bind("<Destroy>", self._cancel_hscroll_sync, add="+")
        self.root.bind("<Destroy>", self._cancel_startup_check, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<F5>", self._on_rescan)
        self.root.bind("<F1>", self.open_tutorial)
        self.root.bind("<Control-f>", self._focus_search)
        self._startup_after = self.root.after(
            400, self._check_addon_on_startup
        )

    def _apply_window_icon(self):
        """Use the bundled main icon for the window and taskbar."""
        path = icons.icon_path(icons.MAIN_ICON_NAME)
        if not path.is_file():
            return
        try:
            image = tk.PhotoImage(file=str(path))
            self.root.iconphoto(True, image)
            self._window_icon = image
        except tk.TclError:
            self._window_icon = None

    # -- ui construction ---------------------------------------------------

    def _sidebar_section(self, parent, text):
        return tk.Label(
            parent, text=text.upper(), bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.theme.heading(8, "bold"), anchor="w", bd=0,
        )

    def _build_easter_egg_button(self, parent):
        """Add the rare, intentionally colourful alternate-icon button."""
        holder = tk.Frame(parent, bg=theme.PANEL)
        holder.pack(fill="x", pady=(10, 0))
        background = self._easter_colors[self._easter_color_index]
        active = self._easter_colors[
            (self._easter_color_index + 1) % len(self._easter_colors)
        ]
        self.easter_btn = tk.Button(
            holder,
            text="AMAZING ICON",
            command=self.show_alt_icon,
            bg=background,
            fg="#FFF6C7",
            activebackground=active,
            activeforeground="#FFFFFF",
            font=self.theme.heading(9, "bold"),
            relief="flat",
            bd=0,
            padx=8,
            pady=7,
            cursor="hand2",
            highlightthickness=2,
            highlightbackground="#F2C14E",
            highlightcolor="#F2C14E",
        )
        self.easter_btn.pack(fill="x")
        self.easter_btn.bind("<Enter>", self._cycle_easter_color)
        self.easter_btn.bind("<Leave>", self._cycle_easter_color)

    def _cycle_easter_color(self, _event=None):
        if self.easter_btn is None:
            return
        self._easter_color_index = (
            self._easter_color_index + 1
        ) % len(self._easter_colors)
        background = self._easter_colors[self._easter_color_index]
        active = self._easter_colors[
            (self._easter_color_index + 1) % len(self._easter_colors)
        ]
        try:
            self.easter_btn.configure(
                bg=background, activebackground=active
            )
        except tk.TclError:
            pass

    def _build(self):
        root = self.root
        root.configure(bg=theme.BG)

        # ---- header ------------------------------------------------------
        header = tk.Frame(root, bg=theme.HEADER, bd=0)
        header.pack(side="top", fill="x")

        header_inner = tk.Frame(header, bg=theme.HEADER)
        header_inner.pack(fill="x", padx=18, pady=10)

        brand = tk.Frame(header_inner, bg=theme.HEADER)
        brand.pack(side="left")
        mark = tk.Canvas(
            brand, width=38, height=38, bg=theme.HEADER, highlightthickness=0
        )
        mark.pack(side="left", padx=(0, 11))
        theme.draw_brand_mark(mark)

        titles = tk.Frame(brand, bg=theme.HEADER)
        titles.pack(side="left", anchor="w")
        tk.Label(
            titles, text="FS25 VEHICLE YEAR", bg=theme.HEADER, fg=theme.TEXT,
            font=self.theme.heading(18, "bold"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            titles, text="COMPATIBILITY TOOL", bg=theme.HEADER,
            fg=theme.TEXT_MUTED, font=self.theme.body(8), anchor="w",
        ).pack(anchor="w")

        header_right = tk.Frame(header_inner, bg=theme.HEADER)
        header_right.pack(side="right")

        self.scan_btn = ttk.Button(
            header_right, text="SCAN MODS", style="Primary.TButton",
            command=self.start_scan,
        )
        self.scan_btn.pack(side="right", padx=(12, 0))

        status_chip = tk.Frame(
            header_right, bg=theme.PANEL_RAISED,
            highlightbackground=theme.BORDER, highlightthickness=1, bd=0,
        )
        status_chip.pack(side="right")
        chip_inner = tk.Frame(status_chip, bg=theme.PANEL_RAISED)
        chip_inner.pack(padx=10, pady=5)
        self.status_dot = tk.Canvas(
            chip_inner, width=10, height=10, bg=theme.PANEL_RAISED,
            highlightthickness=0,
        )
        self.status_dot.pack(side="left", padx=(0, 6))
        self._status_dot_item = self.status_dot.create_oval(
            2, 2, 8, 8, fill=theme.GREEN, outline=""
        )
        tk.Label(
            chip_inner, textvariable=self.header_status_var,
            bg=theme.PANEL_RAISED, fg=theme.TEXT_MUTED,
            font=self.theme.heading(8, "bold"),
        ).pack(side="left")

        self.help_btn = ttk.Button(
            header_right, text="HELP", style="Small.TButton",
            command=self.open_tutorial,
        )
        self.help_btn.pack(side="right", padx=(8, 0))

        theme.separator(header).pack(side="bottom", fill="x")

        # ---- status bar (packed before the body) -------------------------
        status_bar = tk.Frame(root, bg=theme.STATUS_BG, bd=0)
        status_bar.pack(side="bottom", fill="x")
        self.status_bar = status_bar
        theme.separator(status_bar).pack(side="top", fill="x")
        status_inner = tk.Frame(status_bar, bg=theme.STATUS_BG)
        status_inner.pack(fill="x", padx=18, pady=5)
        tk.Label(
            status_inner, textvariable=self.status_var, bg=theme.STATUS_BG,
            fg=theme.TEXT_MUTED, font=self.theme.body(9), anchor="w",
        ).pack(side="left")
        tk.Label(
            status_inner, text="F5  RESCAN", bg=theme.STATUS_BG,
            fg=theme.TEXT_DIM, font=self.theme.heading(8, "bold"),
        ).pack(side="right", padx=(12, 0))
        self.progress = ttk.Progressbar(
            status_inner, mode="indeterminate", length=140
        )
        self.bottom = status_inner

        # ---- toast (not packed until needed) -----------------------------
        self.toast = tk.Frame(root, bg=theme.TOAST_BG["info"], bd=0)
        self.toast_accent = tk.Frame(
            self.toast, bg=theme.TOAST_ACCENT["info"], width=4, bd=0
        )
        self.toast_accent.pack(side="left", fill="y")
        self.toast_icon = tk.Label(
            self.toast, text=theme.TOAST_ICON["info"],
            bg=theme.TOAST_BG["info"], fg=theme.TOAST_ACCENT["info"],
            font=self.theme.heading(10, "bold"), width=2, bd=0,
        )
        self.toast_icon.pack(side="left", padx=(10, 0), pady=7)
        self.toast_label = tk.Label(
            self.toast, text="", bg=theme.TOAST_BG["info"], fg=theme.TEXT,
            font=self.theme.body(9), anchor="w", justify="left",
            wraplength=780, bd=0,
        )
        self.toast_label.pack(
            side="left", fill="x", expand=True, padx=(4, 12), pady=7
        )

        # ---- body --------------------------------------------------------
        body = tk.Frame(root, bg=theme.BG, bd=0)
        body.pack(fill="both", expand=True)
        self.body = body

        sidebar = tk.Frame(body, bg=theme.PANEL, width=210, bd=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(body, bg=theme.BORDER, width=1, bd=0).pack(side="left", fill="y")

        side = tk.Frame(sidebar, bg=theme.PANEL)
        side.pack(fill="both", expand=True, padx=14, pady=16)

        self._sidebar_section(side, "Library").pack(fill="x", pady=(0, 6))
        self.nav_items = {}
        for key in ("all", "needs", "supported"):
            item = NavItem(
                side, FILTERS[key][0], lambda k=key: self.set_filter(k),
                self.theme,
            )
            item.pack(fill="x", pady=1)
            self.nav_items[key] = item
        self.hidden_nav = NavItem(
            side, FILTERS["hidden"][0], lambda: self.set_filter("hidden"),
            self.theme,
        )
        self.nav_separator = theme.separator(side)
        self.nav_separator.pack(fill="x", pady=12)
        self._update_nav_selection()

        self._sidebar_section(side, "Scan settings").pack(fill="x", pady=(0, 4))
        ttk.Checkbutton(
            side, text="Base game vehicles", variable=self.base_var
        ).pack(anchor="w")
        self.advanced_check = ttk.Checkbutton(
            side, text="Advanced view", variable=self.advanced_var,
            command=self.on_advanced_toggle,
        )
        self.advanced_check.pack(anchor="w")

        self.adv_holder = ttk.Frame(side, style="Panel.TFrame")
        self.adv_holder.pack(fill="x")
        self.adv_options = ttk.Frame(self.adv_holder, style="Panel.TFrame")
        ttk.Checkbutton(
            self.adv_options, text="FS22/older mods", variable=self.nonfs25_var
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            self.adv_options, text="ADDON SOURCE", bg=theme.PANEL,
            fg=theme.TEXT_DIM, font=self.theme.heading(8, "bold"), anchor="w",
        ).pack(fill="x", pady=(8, 3))
        ttk.Combobox(
            self.adv_options, textvariable=self.addon_var,
            values=["installed", "source"], state="readonly", width=12,
        ).pack(fill="x")

        theme.separator(side).pack(fill="x", pady=12)
        self._sidebar_section(side, "Shortcuts").pack(fill="x", pady=(0, 4))
        for text in (
            "F1   Tutorial",
            "F5   Rescan",
            "Ctrl+F  Search",
            "Tab  Move focus",
        ):
            tk.Label(
                side, text=text, bg=theme.PANEL, fg=theme.TEXT_DIM,
                font=self.theme.body(8), anchor="w",
            ).pack(fill="x", pady=1)
        self.addon_setup_btn = ttk.Button(
            side, text="ADDON SETUP...", style="Small.TButton",
            command=self.show_addon_setup,
        )
        self.addon_setup_btn.pack(fill="x", pady=(6, 0))
        self.addon_history_btn = ttk.Button(
            side, text="ADDON HISTORY...", style="Small.TButton",
            command=self.show_addon_history,
        )
        self.addon_history_btn.pack(fill="x", pady=(4, 0))
        if self.easter_egg_visible:
            self._build_easter_egg_button(side)

        tk.Frame(side, bg=theme.PANEL).pack(fill="both", expand=True)
        self.sidebar_note = tk.Label(
            side, text="Scan the mods folder\nto load the library",
            bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.theme.body(8),
            justify="left", anchor="w", wraplength=180,
        )
        self.sidebar_note.pack(fill="x", pady=(8, 0))

        # ---- main content ------------------------------------------------
        main = tk.Frame(body, bg=theme.BG)
        main.pack(side="left", fill="both", expand=True)
        main_inner = tk.Frame(main, bg=theme.BG)
        main_inner.pack(fill="both", expand=True, padx=18, pady=(14, 12))
        main_inner.columnconfigure(0, weight=1)
        main_inner.rowconfigure(3, weight=1)

        # folder card
        folder_card = theme.card(main_inner)
        folder_card.grid(row=0, column=0, sticky="ew")
        folder = tk.Frame(folder_card, bg=theme.PANEL)
        folder.pack(fill="x", padx=14, pady=10)
        tk.Label(
            folder, text="MODS FOLDER", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.theme.heading(8, "bold"), anchor="w",
        ).pack(fill="x")
        folder_row = tk.Frame(folder, bg=theme.PANEL)
        folder_row.pack(fill="x", pady=(4, 0))
        ttk.Entry(folder_row, textvariable=self.folder_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            folder_row, text="BROWSE...", style="Small.TButton",
            command=self.choose_folder,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            folder_row, text="GAME MODS", style="Small.TButton",
            command=self.use_game_folder,
        ).pack(side="left", padx=(6, 0))

        # page title + summary
        page = tk.Frame(main_inner, bg=theme.BG)
        page.grid(row=1, column=0, sticky="ew", pady=(14, 6))
        page.columnconfigure(0, weight=1)
        tk.Label(
            page, textvariable=self.page_title_var, bg=theme.BG,
            fg=theme.TEXT, font=self.theme.heading(15, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.summary_label = tk.Label(
            page, textvariable=self.summary_var, bg=theme.BG,
            fg=theme.TEXT_MUTED, font=self.theme.body(9), anchor="w",
            justify="left", wraplength=900,
        )
        self.summary_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        page.bind(
            "<Configure>",
            lambda event: self.summary_label.configure(
                wraplength=max(300, event.width - 10)
            ),
        )

        # summary metrics
        metrics_card = theme.card(main_inner)
        metrics_card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        metrics = tk.Frame(metrics_card, bg=theme.PANEL)
        metrics.pack(fill="x", padx=8, pady=6)
        specs = (
            (self.metric_mods_var, "MODS SCANNED"),
            (self.metric_vehicles_var, "VEHICLES"),
            (self.metric_supported_var, "SUPPORTED MODS"),
            (self.metric_need_var, "MODS NEED YEARS"),
        )
        self.metric_need_label = None
        for index, (variable, caption) in enumerate(specs):
            block = tk.Frame(metrics, bg=theme.PANEL)
            block.grid(row=0, column=index * 2, sticky="nsew", padx=12, pady=4)
            value = tk.Label(
                block, textvariable=variable, bg=theme.PANEL, fg=theme.TEXT,
                font=self.theme.heading(19, "bold"), anchor="w",
            )
            value.pack(anchor="w")
            tk.Label(
                block, text=caption, bg=theme.PANEL, fg=theme.TEXT_MUTED,
                font=self.theme.heading(8, "bold"), anchor="w",
            ).pack(anchor="w")
            if caption == "MODS NEED YEARS":
                self.metric_need_label = value
            metrics.columnconfigure(index * 2, weight=1)
            if index < 3:
                tk.Frame(metrics, bg=theme.BORDER, width=1).grid(
                    row=0, column=index * 2 + 1, sticky="ns", pady=8
                )

        # mod list + details
        self.pane = pane = ttk.PanedWindow(main_inner, orient="horizontal")
        pane.grid(row=3, column=0, sticky="nsew")
        pane.bind("<Configure>", self._position_initial_sash, add="+")

        left_card = theme.card(pane)
        left = tk.Frame(left_card, bg=theme.PANEL)
        left.pack(fill="both", expand=True)
        left_header = tk.Frame(left, bg=theme.PANEL)
        left_header.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(
            left_header, text="MODS", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.theme.heading(8, "bold"), anchor="w",
        ).pack(side="left")
        self.tree_count_label = tk.Label(
            left_header, text="", bg=theme.PANEL, fg=theme.TEXT_MUTED,
            font=self.theme.body(8), anchor="e",
        )
        self.tree_count_label.pack(side="right")

        search_row = tk.Frame(left, bg=theme.PANEL)
        search_row.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(
            search_row, text="SEARCH", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.theme.heading(8, "bold"), anchor="w",
        ).pack(side="left")
        self.search_entry = ttk.Entry(
            search_row, textvariable=self.search_var,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(7, 0))
        self.search_entry.bind("<Escape>", self._clear_search_event)
        ttk.Button(
            search_row, text="CLEAR", style="Small.TButton",
            command=self.clear_search,
        ).pack(side="left", padx=(6, 0))
        self.search_var.trace_add("write", self._on_search_change)

        tree_wrap = tk.Frame(left, bg=theme.PANEL)
        tree_wrap.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_wrap, columns=("status", "vehicles", "missing"),
            show="tree headings", selectmode="browse",
        )
        self.tree.heading("#0", text="MOD", anchor="w")
        self.tree.heading("status", text="STATUS", anchor="w")
        self.tree.heading("vehicles", text="VEHICLES")
        self.tree.heading("missing", text="MISSING")
        self.tree.column(
            "#0", width=280, minwidth=200, stretch=True, anchor="w"
        )
        self.tree.column("status", width=200, minwidth=120, anchor="w")
        self.tree.column(
            "vehicles", width=70, minwidth=55, anchor="center", stretch=False
        )
        self.tree.column(
            "missing", width=62, minwidth=52, anchor="center", stretch=False
        )
        self.tree.configure(displaycolumns=("status",))
        self.tree.tag_configure("bad", foreground=theme.DANGER)
        self.tree.tag_configure("warn", foreground=theme.WARNING)
        self.tree.tag_configure("good", foreground=theme.SUCCESS)
        self.tree.tag_configure("muted", foreground=theme.TEXT_DIM)
        self.tree.tag_configure("hover", background=theme.PANEL_RAISED)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        tree_hscroll = ttk.Scrollbar(
            tree_wrap, orient="horizontal", command=self.tree.xview
        )
        self.tree_hscroll = tree_hscroll
        self.tree.configure(xscrollcommand=tree_hscroll.set)
        tree_hscroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(tree_wrap, bg=theme.PANEL).grid(
            row=1, column=1, sticky="nsew"
        )
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_tree_leave)
        pane.add(left_card, weight=3)

        right_card = theme.card(pane)
        right = tk.Frame(right_card, bg=theme.PANEL)
        right.pack(fill="both", expand=True)
        right_header = tk.Frame(right, bg=theme.PANEL)
        right_header.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(
            right_header, text="DETAILS", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.theme.heading(8, "bold"), anchor="w",
        ).pack(side="left")
        self.details_copy_btn = ttk.Button(
            right_header, text="COPY", style="Small.TButton",
            command=self.copy_details, state="disabled",
        )
        self.details_copy_btn.pack(side="right")

        text_wrap = tk.Frame(right, bg=theme.PANEL)
        text_wrap.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        text_wrap.rowconfigure(0, weight=1)
        text_wrap.columnconfigure(0, weight=1)
        self.details = tk.Text(
            text_wrap, wrap="none", state="disabled",
            font=self.theme.mono(9), height=18,
        )
        theme.style_text(self.details, font=self.theme.mono(9))
        self.details.grid(row=0, column=0, sticky="nsew")
        details_scroll = ttk.Scrollbar(
            text_wrap, orient="vertical", command=self.details.yview
        )
        self.details.configure(yscrollcommand=details_scroll.set)
        details_scroll.grid(row=0, column=1, sticky="ns")
        details_hscroll = ttk.Scrollbar(
            text_wrap, orient="horizontal", command=self.details.xview
        )
        self.details_hscroll = details_hscroll
        self.details.configure(xscrollcommand=details_hscroll.set)
        details_hscroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(text_wrap, bg=theme.PANEL).grid(row=1, column=1, sticky="nsew")
        pane.add(right_card, weight=2)
        self.tree.bind(
            "<Configure>",
            self._schedule_hscroll_sync,
            add="+",
        )
        self.details.bind(
            "<Configure>",
            self._schedule_hscroll_sync,
            add="+",
        )

        # action bar
        action_card = theme.card(main_inner)
        action_card.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        action = tk.Frame(action_card, bg=theme.PANEL)
        action.pack(fill="x", padx=12, pady=10)
        action.columnconfigure(1, weight=1)

        button_row = tk.Frame(action, bg=theme.PANEL)
        button_row.grid(row=0, column=0, sticky="w")
        self.add_years_btn = ttk.Button(
            button_row, text="ADD YEARS...", style="Accent.TButton",
            command=self.add_years, state="disabled",
        )
        self.add_years_btn.pack(side="left")
        ttk.Button(
            button_row, text="COPY YEARS...", command=self.copy_years
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            button_row, text="PASTE YEARS...", command=self.paste_years
        ).pack(side="left", padx=(8, 0))

        self.add_years_hint = tk.Label(
            action, text="Select a mod that needs years", bg=theme.PANEL,
            fg=theme.TEXT_DIM, font=self.theme.body(8), anchor="w",
            justify="left", wraplength=220,
        )
        self.add_years_hint.grid(
            row=0, column=1, sticky="w", padx=(14, 10)
        )

        adv_holder = tk.Frame(action, bg=theme.PANEL)
        adv_holder.grid(row=0, column=2, sticky="e")
        self.adv_buttons = ttk.Frame(adv_holder, style="Panel.TFrame")
        ttk.Button(
            self.adv_buttons, text="SAVE JSON...", style="Small.TButton",
            command=self.save_json,
        ).pack(side="left")
        ttk.Button(
            self.adv_buttons, text="APPEND YEARS_INFO...", style="Small.TButton",
            command=self.append_years_info,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            self.adv_buttons, text="COPY UNSUPPORTED...", style="Small.TButton",
            command=self.copy_unsupported,
        ).pack(side="left", padx=(6, 0))

        self._set_details(self._empty_details())
        self.on_select()

    # -- small UI helpers --------------------------------------------------

    def _position_initial_sash(self, _event=None):
        """Give the mod list a bit more room than the details pane on first map."""
        if self._pane_sash_done:
            return
        width = self.pane.winfo_width()
        if width < 300:
            return
        position = int(width * 0.58)
        position = max(260, min(position, width - 260))
        try:
            self.pane.sashpos(0, position)
        except tk.TclError:
            return
        self._pane_sash_done = True

    def _on_rescan(self, _event=None):
        self.start_scan()
        return "break"

    def open_tutorial(self, _event=None):
        """Open the guide, or bring the existing one forward."""
        if self.closing:
            return "break"
        existing = self.tutorial
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_set()
                return "break"
        except tk.TclError:
            pass
        self.tutorial = tutorial.TutorialWindow(self.root, th=self.theme)
        return "break"

    def _set_header_status(self, text, color):
        self.header_status_var.set(text.upper())
        self.status_dot.itemconfigure(self._status_dot_item, fill=color)

    def _empty_details(self):
        if not self.last:
            return (
                "No scan yet.\n\n"
                "Pick a mods folder above and press SCAN MODS (or F5).\n"
                "New here? Press F1 for a quick tour."
            )
        if self._empty_view:
            query = self.search_var.get().strip()
            if query:
                return (
                    f'No mods match "{query}".\n\n'
                    "Clear the search or switch filters to see the library."
                )
            return (
                "No mods in this view.\n\n"
                "Switch to All mods in the library rail."
            )
        return "Select a mod to inspect its vehicles and year sources."

    def _focus_search(self, _event=None):
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")
        return "break"

    def clear_search(self):
        if self.search_var.get():
            self.search_var.set("")
        self.search_entry.focus_set()

    def _clear_search_event(self, _event=None):
        self.clear_search()
        self.tree.focus_set()
        return "break"

    def _on_search_change(self, *_args):
        if self.closing:
            return
        if self.last is not None:
            self.refresh_rows(keep_selection=True)

    def _set_details(self, text):
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.config(state="disabled")
        self.details.yview_moveto(0)
        self.details.xview_moveto(0)
        self.details_copy_btn.config(
            state="normal" if text.strip() else "disabled"
        )
        self._schedule_hscroll_sync()

    def _schedule_hscroll_sync(self, _event=None):
        if self._hscroll_after_id is not None:
            try:
                self.root.after_cancel(self._hscroll_after_id)
            except tk.TclError:
                pass
            self._hscroll_after_id = None
        try:
            self._hscroll_after_id = self.root.after_idle(
                self._run_hscroll_sync
            )
        except tk.TclError:
            self._hscroll_after_id = None

    def _run_hscroll_sync(self):
        self._hscroll_after_id = None
        self._sync_horizontal_scrollbars()

    def _cancel_hscroll_sync(self, _event=None):
        if self._hscroll_after_id is not None:
            try:
                self.root.after_cancel(self._hscroll_after_id)
            except tk.TclError:
                pass
            self._hscroll_after_id = None

    def _sync_horizontal_scrollbars(self):
        """Hide horizontal scrollbars that have nothing to scroll."""
        for widget, bar in (
            (self.tree, self.tree_hscroll),
            (self.details, self.details_hscroll),
        ):
            try:
                if not widget.winfo_exists() or not bar.winfo_exists():
                    continue
                first, last = widget.xview()
            except tk.TclError:
                continue
            needed = first > 0.0 or last < 1.0
            managed = bool(bar.winfo_manager())
            try:
                if needed and not managed:
                    bar.grid()
                elif not needed and managed:
                    bar.grid_remove()
            except tk.TclError:
                pass

    def _update_nav_selection(self):
        current = self.filter_var.get()
        for key, item in self.nav_items.items():
            item.set_selected(key == current)
        self.hidden_nav.set_selected(current == "hidden")
        title = FILTERS.get(current, FILTERS["all"])[0]
        self.page_title_var.set(title.upper())

    def _update_nav_counts(self, mods, base_items, advanced):
        rows = gui_rows(mods, base_items, advanced)
        counts = {"all": len(rows), "needs": 0, "supported": 0, "hidden": 0}
        for row in rows:
            status = row["status"]
            if status in ("unsupported", "partial", "error"):
                counts["needs"] += 1
            if status == "supported":
                counts["supported"] += 1
            if status in ("no-vehicles", "skipped"):
                counts["hidden"] += 1
        for key, item in self.nav_items.items():
            item.set_count(counts.get(key, 0))
        self.hidden_nav.set_count(counts["hidden"])

    def _update_metrics(self, mods):
        summary = vy.counts_of(mods)
        self.metric_mods_var.set(str(summary["scanned"]))
        self.metric_vehicles_var.set(str(summary["vehicles_total"]))
        self.metric_supported_var.set(str(summary["supported"]))
        needs = summary["partial"] + summary["unsupported"]
        self.metric_need_var.set(str(needs))
        if self.metric_need_label is not None:
            self.metric_need_label.configure(
                fg=theme.DANGER if needs else theme.SUCCESS
            )

    def _update_sidebar_note(self, payload):
        src = payload.get("src") or {}
        vy_meta = src.get("vy") or {}
        addon_meta = src.get("addon") or {}
        vy_count = src.get("vy_count", 0)
        lines = [f"{vy_count:,} VY year keys"]

        version = addon_meta.get("version")
        kind = addon_meta.get("kind")
        label = {
            "installed-zip": "installed",
            "installed-folder": "installed folder",
            "source-lua": "source",
            "missing": "missing",
        }.get(kind, kind or "")
        if version:
            lines.append(f"Compatibility addon v{version}")
            if label:
                lines.append(label)
        elif kind == "missing":
            lines.append("Compatibility addon: not found")
        else:
            lines.append("Compatibility addon: loaded")
        if vy_meta.get("kind") == "missing":
            lines.append("VY database: not found")
        self.sidebar_note.configure(text="\n".join(lines))

    def on_advanced_toggle(self):
        advanced = self.advanced_var.get()
        if advanced:
            self.adv_options.pack(fill="x", pady=(4, 0))
            self.hidden_nav.pack(
                fill="x", pady=1, before=self.nav_separator
            )
            self.adv_buttons.pack(side="right")
            self.add_years_hint.grid_remove()
            self.tree.configure(
                displaycolumns=("status", "vehicles", "missing")
            )
            self.tree.column("status", width=140, minwidth=115)
        else:
            self.adv_options.pack_forget()
            self.hidden_nav.pack_forget()
            self.adv_buttons.pack_forget()
            self.add_years_hint.grid()
            self.tree.configure(displaycolumns=("status",))
            self.tree.column("status", width=200, minwidth=120)
            if self.filter_var.get() == "hidden":
                self.filter_var.set("all")
        self._update_nav_selection()
        if self.last is not None:
            self.refresh_rows(keep_selection=True)
        else:
            self._set_details(self._empty_details())
            self.on_select()

    def notify(self, text, kind="info", duration=4500):
        """Show a short, non-blocking message above the status bar."""
        if self.closing:
            return
        if kind not in theme.TOAST_BG:
            kind = "info"
        bg = theme.TOAST_BG[kind]
        accent = theme.TOAST_ACCENT[kind]
        icon = theme.TOAST_ICON[kind]
        self.toast.configure(bg=bg)
        self.toast_accent.configure(bg=accent)
        self.toast_icon.configure(text=icon, bg=bg, fg=accent)
        self.toast_label.configure(text=text, bg=bg, fg=theme.TEXT)
        if not self.toast.winfo_manager():
            # Pack before the body so the toast gets its own strip above the
            # status bar even when the window is only 720px high.  Packing it
            # last would let the main content consume the height first.
            self.toast.pack(
                side="bottom",
                fill="x",
                padx=18,
                pady=(0, 6),
                before=self.body,
            )
        if self._toast_after is not None:
            try:
                self.root.after_cancel(self._toast_after)
            except tk.TclError:
                pass
        self._toast_after = self.root.after(duration, self._hide_toast)

    def _hide_toast(self):
        self._toast_after = None
        try:
            self.toast.pack_forget()
        except tk.TclError:
            pass

    def show_error(self, title, message, details=None):
        MessageDialog(
            self.root, title, message, kind="error",
            details=details, th=self.theme,
        )

    # -- filtering / selection --------------------------------------------

    @staticmethod
    def _row_matches(row, key):
        statuses = FILTERS.get(key, FILTERS["all"])[1]
        if statuses is None:
            return True
        return row["status"] in statuses

    def set_filter(self, key):
        if key not in FILTERS:
            return
        if key == "hidden" and not self.advanced_var.get():
            return
        self.filter_var.set(key)
        self._update_nav_selection()
        if self.last is not None:
            self.refresh_rows(keep_selection=False)
        else:
            self._empty_view = False
            self._set_details(self._empty_details())

    def _on_tree_motion(self, event):
        iid = self.tree.identify_row(event.y)
        if iid == self._hover_iid:
            return
        self._clear_hover()
        self._hover_iid = iid
        if iid and iid != "__empty__" and iid in self.rows_by_iid:
            tags = list(self.tree.item(iid, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(iid, tags=tags)

    def _clear_hover(self):
        iid = self._hover_iid
        self._hover_iid = None
        if not iid:
            return
        try:
            if self.tree.exists(iid):
                tags = [
                    tag for tag in self.tree.item(iid, "tags")
                    if tag != "hover"
                ]
                self.tree.item(iid, tags=tags)
        except tk.TclError:
            pass

    def _on_tree_leave(self, _event=None):
        self._clear_hover()

    def refresh_rows(self, keep_selection=False):
        if not self.last:
            return

        mods = self.last["mods"]
        base_items = self.last["base_items"]
        advanced = self.advanced_var.get()

        current_filter = self.filter_var.get()
        if current_filter == "hidden" and not advanced:
            self.filter_var.set("all")
            current_filter = "all"
        self._update_nav_selection()

        selected_key = None
        if keep_selection:
            selection = self.tree.selection()
            row = self.rows_by_iid.get(selection[0]) if selection else None
            if row is not None:
                selected_key = (
                    row["kind"],
                    row["mod"]["file"] if row["kind"] == "mod" else "base",
                )

        rows = gui_rows(mods, base_items, advanced)
        query = self.search_var.get().strip()
        status_filtered = [
            row for row in rows
            if self._row_matches(row, current_filter)
        ]
        filtered = [
            row for row in status_filtered
            if row_matches_search(row, query)
        ]
        self._update_nav_counts(mods, base_items, advanced)
        self._update_metrics(mods)

        self._clear_hover()
        self.tree.delete(*self.tree.get_children())
        self.rows_by_iid = {}
        self._empty_view = not filtered

        for index, row in enumerate(filtered):
            iid = f"row{index}"
            self.rows_by_iid[iid] = row
            vehicles = f"{row['vehicles']}" if row["vehicles"] else ""
            missing = f"{row['missing']}" if row["missing"] else ""
            self.tree.insert(
                "", "end", iid=iid, text=row["label"],
                values=(tree_status(row, advanced), vehicles, missing),
                tags=(STATUS_TAG.get(row["status"], "muted"),),
            )

        if filtered:
            if query and status_filtered:
                self.tree_count_label.configure(
                    text=f"{len(filtered)} of {len(status_filtered)} shown"
                )
            else:
                self.tree_count_label.configure(text=f"{len(filtered)} shown")
        else:
            self.tree_count_label.configure(text="0 shown")
            self.tree.insert(
                "", "end", iid="__empty__",
                text=(
                    "No mods match the search"
                    if query
                    else "No mods in this view"
                ),
                values=("", "", ""), tags=("muted",),
            )

        summary = vy.counts_of(mods)
        needs = summary["partial"] + summary["unsupported"]
        if needs:
            missing_count = summary["vehicles_missing"]
            text = (
                f"{needs} of {summary['vehicle_mods']} vehicle mods need years "
                f"- {missing_count} {plural(missing_count, 'vehicle')} "
                "without a year"
            )
        else:
            text = f"All {summary['vehicle_mods']} vehicle mods are supported"
        if base_items is not None:
            base_missing = sum(
                1 for item in base_items if item["source"] == "none"
            )
            if base_missing:
                text += (
                    f"  -  base game: {base_missing} "
                    f"{plural(base_missing, 'vehicle')} without a year"
                )
            else:
                text += "  -  base game: all supported"
        if advanced:
            text += (
                f"  -  hidden: {summary['no_vehicles']} non-vehicle, "
                f"{summary['skipped']} skipped"
            )
        self.summary_var.set(text)

        target = None
        if self._reselect_file:
            target = next(
                (
                    iid for iid, row in self.rows_by_iid.items()
                    if row["kind"] == "mod"
                    and row["mod"]["file"] == self._reselect_file
                ),
                None,
            )
            self._reselect_file = None
        if target is None and selected_key is not None:
            target = next(
                (
                    iid for iid, row in self.rows_by_iid.items()
                    if (
                        row["kind"],
                        row["mod"]["file"] if row["kind"] == "mod" else "base",
                    ) == selected_key
                ),
                None,
            )
        if target is None:
            target = next(
                (
                    iid for iid, row in self.rows_by_iid.items()
                    if row["missing"]
                ),
                None,
            )
        if target is None:
            target = next(iter(self.rows_by_iid), None)

        if target is not None:
            self.tree.selection_set(target)
            self.tree.see(target)
            self.on_select()
        else:
            self._set_details(self._empty_details())
            self.add_years_btn.config(state="disabled")
            self.details_copy_btn.config(state="disabled")
            self.add_years_hint.config(text="Select a mod that needs years")

    def on_select(self, _event=None):
        selection = self.tree.selection()
        row = self.rows_by_iid.get(selection[0]) if selection else None
        can_add = (
            row is not None
            and row["kind"] == "mod"
            and row["missing"] > 0
        )
        self.add_years_btn.config(state="normal" if can_add else "disabled")
        self.add_years_hint.config(
            text=(
                "Type the year(s) - review the addon changes before anything "
                "is written"
                if can_add
                else "Select a mod that needs years"
            )
        )
        if row is None:
            self._set_details(self._empty_details())
            return
        self._set_details(format_details(row, self.advanced_var.get()))

    # -- actions -----------------------------------------------------------

    def choose_folder(self):
        folder = filedialog.askdirectory(
            title="Select a mods folder",
            initialdir=self.folder_var.get() or str(Path.home()),
        )
        if folder:
            self.folder_var.set(folder)

    def use_game_folder(self):
        default_mods = vy.default_mods_dir()
        if default_mods is None:
            self.notify("Game mods folder not found.", kind="warning", duration=6000)
            return
        self.folder_var.set(str(default_mods))
        self.notify(
            f"Game mods folder selected: {theme.short_path(default_mods)}",
            kind="info", duration=4000,
        )

    def _check_addon_on_startup(self):
        """Prompt immediately when the detected game mods folder has no addon."""
        if self.closing or self.scanning:
            return
        raw = self.folder_var.get().strip()
        if not raw:
            return
        folder = Path(raw).expanduser()
        if folder.is_dir():
            self.ensure_addon_ready(folder)

    def addon_discovery_dirs(self, folder=None):
        """Folders that may contain the compatibility addon or VY database."""
        dirs = []
        if folder:
            dirs.append(Path(folder))
        default_mods = vy.default_mods_dir()
        if default_mods is not None and default_mods not in dirs:
            dirs.append(default_mods)
        return dirs

    def addon_install_dir(self, folder):
        """Prefer the real game mods folder, falling back to the scan folder."""
        default_mods = vy.default_mods_dir()
        return default_mods if default_mods is not None else Path(folder)

    def ensure_addon_ready(self, folder, force=False):
        """Offer to create/install the addon when it is not in the mods folder."""
        state = vy.addon_setup_state(self.addon_discovery_dirs(folder))
        if state["installed"] is not None:
            return True
        key = str(Path(folder))
        if not force and key in self._addon_setup_dismissed:
            return False

        mode = "install" if state["source"] is not None else "create"
        source_dir = (
            Path(state["source"]).parent
            if mode == "install"
            else vy.SOURCE_ADDON_DIR
        )
        install_dir = self.addon_install_dir(folder)
        dialog = AddonSetupDialog(
            self.root, mode, source_dir, install_dir, th=self.theme
        )
        self.root.wait_window(dialog)
        if not dialog.result:
            self._addon_setup_dismissed.add(key)
            self.status_var.set(
                "Compatibility addon setup skipped - nothing was written"
            )
            return False

        try:
            if mode == "install":
                report = vy.install_addon_source(
                    Path(state["source"]).parent, install_dir
                )
            else:
                report = vy.scaffold_addon(source_dir, install_dir=install_dir)
        except FileExistsError as exc:
            current = vy.addon_setup_state(self.addon_discovery_dirs(folder))
            if current["installed"] is not None:
                self.addon_var.set("installed")
                self.notify(
                    f"Compatibility addon ready: {theme.short_path(exc)}",
                    kind="info", duration=6000,
                )
                return True
            self.show_error(
                "Compatibility addon setup failed",
                "The compatibility addon could not be created because a "
                "target file already exists. Nothing was overwritten.",
                details=str(exc),
            )
            return False
        except Exception:
            self.show_error(
                "Compatibility addon setup failed",
                "The compatibility addon could not be created or installed. "
                "No existing mod files were overwritten.",
                details=traceback.format_exc(),
            )
            return False

        if mode == "create":
            vy.set_source_addon_dir(report["source"])
        self._addon_setup_dismissed.discard(key)
        self.addon_var.set("installed")
        state_text = "created and installed" if mode == "create" else "installed"
        self.notify(
            f"Vehicle Years Compatibility Tool {state_text} - "
            f"{theme.short_path(report['installed'] or report['zip'])}",
            kind="success", duration=8000,
        )
        self.status_var.set(
            f"Compatibility addon {state_text}: "
            f"{theme.short_path(report['installed'] or report['zip'])}"
        )
        return True

    def show_alt_icon(self):
        """Open the optional alternate mod-icon dialog."""
        if not icons.alt_icon_available():
            self.notify(
                "The alternate icon asset is missing.",
                kind="warning", duration=6000,
            )
            return
        if not self.ensure_addon_source():
            return

        source = vy.SOURCE_ADDON_LUA.parent
        raw = self.folder_var.get().strip()
        folder = Path(raw).expanduser() if raw else None
        if folder is not None and folder.is_dir():
            install_dir = self.addon_install_dir(folder)
        else:
            install_dir = vy.default_mods_dir()

        current = icons.icon_state(source / vy.ADDON_ICON_NAME)
        dialog = AltIconDialog(
            self.root, source, install_dir=install_dir,
            current=current, th=self.theme,
        )
        self.root.wait_window(dialog)
        choice = dialog.result
        if not choice:
            return

        data = (
            icons.main_icon_bytes()
            if choice["icon"] == "main"
            else icons.alt_icon_bytes()
        )
        if data is None:
            self.notify(
                "The selected icon asset is missing.",
                kind="warning", duration=6000,
            )
            return
        reason = (
            "before default mod icon"
            if choice["icon"] == "main"
            else "before alternate mod icon"
        )
        try:
            history.snapshot_addon(source, reason=reason)
            report = vy.set_addon_icon(
                source,
                data,
                install_dir=install_dir if choice["install"] else None,
            )
        except Exception:
            self.show_error(
                "Mod icon not changed",
                "The addon icon could not be updated. Use ADDON HISTORY... "
                "if you need to restore the previous state. If the game is "
                "running, close it and try again so the ZIP is not locked.",
                details=traceback.format_exc(),
            )
            return

        state = "installed" if report["installed"] else "ZIP rebuilt"
        self.notify(
            f"Mod icon changed - {state}. Restart FS25 to see it.",
            kind="success", duration=8000,
        )
        self.status_var.set(f"Mod icon changed ({state})")
        if self.last is not None:
            self._update_sidebar_note(self.last)

    def show_addon_setup(self):
        raw = self.folder_var.get().strip()
        if not raw:
            default_mods = vy.default_mods_dir()
            if default_mods is None:
                self.notify(
                    "Pick a mods folder first.", kind="warning", duration=6000
                )
                return
            self.folder_var.set(str(default_mods))
            raw = str(default_mods)
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.notify(f"Not a folder: {folder}", kind="warning", duration=6000)
            return
        state = vy.addon_setup_state(self.addon_discovery_dirs(folder))
        if state["installed"] is not None:
            if vy.SOURCE_ADDON_LUA.is_file():
                self.notify(
                    f"Compatibility addon already installed: "
                    f"{theme.short_path(state['installed'])}",
                    kind="info", duration=6000,
                )
            else:
                self.ensure_addon_source()
            return
        if self.ensure_addon_ready(folder, force=True):
            if self.last is not None:
                self._update_sidebar_note(self.last)
        elif not vy.SOURCE_ADDON_LUA.is_file():
            self.notify(
                "No compatibility addon was created.",
                kind="info", duration=5000,
            )

    def ensure_addon_source(self):
        """Ensure Add years / Paste / History has an editable source."""
        if vy.SOURCE_ADDON_LUA.is_file():
            return True
        raw = self.folder_var.get().strip()
        if not raw:
            self.notify("Pick a mods folder first.", kind="warning")
            return False
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.notify(f"Not a folder: {folder}", kind="warning", duration=6000)
            return False

        state = vy.addon_setup_state(self.addon_discovery_dirs(folder))
        if state["installed"] is not None:
            destination = vy.SOURCE_ADDON_DIR
            dialog = AddonSetupDialog(
                self.root, "extract", destination, state["installed"],
                th=self.theme,
            )
            self.root.wait_window(dialog)
            if not dialog.result:
                return False
            try:
                if state["installed_kind"] == "installed-folder":
                    report = vy.copy_addon_source(
                        Path(state["installed"]).parent, destination
                    )
                else:
                    report = vy.extract_addon_zip(
                        state["installed"], destination
                    )
            except FileExistsError as exc:
                self.show_error(
                    "Editable addon source not created",
                    "A source folder already exists at the destination. "
                    "Nothing was overwritten.",
                    details=str(exc),
                )
                return False
            except Exception:
                self.show_error(
                    "Editable addon source not created",
                    "The installed compatibility addon could not be copied "
                    "into an editable source folder.",
                    details=traceback.format_exc(),
                )
                return False
            vy.set_source_addon_dir(report["source"])
            self.notify(
                f"Editable compatibility addon source created - "
                f"{theme.short_path(report['source'])}",
                kind="success", duration=8000,
            )
            return vy.SOURCE_ADDON_LUA.is_file()

        if not self.ensure_addon_ready(folder):
            return False
        return vy.SOURCE_ADDON_LUA.is_file()

    def start_scan(self):
        if self.scanning:
            return
        raw = self.folder_var.get().strip()
        if not raw:
            self.notify("Pick a mods folder first.", kind="warning")
            return
        folder = Path(raw).expanduser()
        if not folder.is_dir():
            self.notify(f"Not a folder: {folder}", kind="warning", duration=6000)
            return

        # Offer addon setup immediately, before the read-only scan starts.
        self.ensure_addon_ready(folder)
        if self.closing:
            return

        discovery_dirs = self.addon_discovery_dirs(folder)
        self.scanning = True
        self.scan_btn.config(state="disabled", text="SCANNING...")
        self._set_header_status("Scanning", theme.WARNING)
        self.progress.pack(side="right", padx=(10, 0))
        self.progress.start(12)
        self.status_var.set(f"Scanning {theme.short_path(folder)} ...")
        self.summary_var.set("Scanning ...")
        threading.Thread(
            target=self._scan_worker,
            args=(
                folder,
                self.base_var.get(),
                self.nonfs25_var.get(),
                self.addon_var.get(),
                discovery_dirs,
            ),
            daemon=True,
        ).start()

    def _scan_worker(self, folder, include_base, include_non_fs25, addon_mode,
                     discovery_dirs):
        started = time.perf_counter()
        try:
            addon, addon_meta = vy.resolve_addon(addon_mode, discovery_dirs)
            vy_args = argparse.Namespace(vy_zip=None, vy_dir=None)
            vy_keys, vy_meta = vy.resolve_vy(vy_args, discovery_dirs)
            mods = vy.scan_mods_dir(
                folder, addon, vy_keys, include_non_fs25
            )

            base_items = None
            game_dir = None
            if include_base:
                game_dir = vy.default_game_dir()
                if game_dir is not None:
                    base_items = vy.scan_base_game(game_dir, addon, vy_keys)

            payload = {
                "mods": mods,
                "base_items": base_items,
                "src": {
                    "mods_dirs": [folder],
                    "game_dir": game_dir,
                    "vy": vy_meta,
                    "vy_count": len(vy_keys),
                    "addon": addon_meta,
                },
                "elapsed": time.perf_counter() - started,
            }
            try:
                self.root.after(0, self._scan_done, payload, None)
            except (tk.TclError, RuntimeError):
                pass
        except Exception:
            error = traceback.format_exc()
            try:
                self.root.after(0, self._scan_done, None, error)
            except (tk.TclError, RuntimeError):
                pass

    def _scan_done(self, payload, error):
        self.scanning = False
        self.progress.stop()
        self.progress.pack_forget()
        self.scan_btn.config(state="normal", text="SCAN MODS")
        if self.closing:
            return
        if error:
            self._set_header_status("Error", theme.DANGER)
            self.status_var.set("Scan failed")
            self.summary_var.set("Scan failed")
            self.show_error(
                "Scan failed",
                "The mods folder could not be scanned. Nothing was written.",
                details=error,
            )
            return

        self.last = payload
        self.refresh_rows()
        self._update_sidebar_note(payload)

        summary = vy.counts_of(payload["mods"])
        missing_total = summary["vehicles_missing"]
        elapsed = f"{payload['elapsed']:.1f} s"
        if missing_total:
            verb = "needs" if missing_total == 1 else "need"
            self.status_var.set(
                f"Done in {elapsed} - {missing_total} "
                f"{plural(missing_total, 'vehicle')} {verb} years"
            )
        else:
            self.status_var.set(
                f"Done in {elapsed} - everything is supported"
            )
        self._set_header_status("Done", theme.GREEN)

    def save_json(self):
        if not self.last:
            self.notify("Scan a folder first.", kind="warning")
            return
        path = filedialog.asksaveasfilename(
            title="Save JSON report", defaultextension=".json",
            initialfile="vycompat-report.json",
        )
        if not path:
            return
        Path(path).write_text(
            vy.format_json(
                self.last["mods"], self.last["base_items"], self.last["src"]
            ) + "\n",
            encoding="utf-8",
        )
        self.notify(
            f"JSON report written to {theme.short_path(path)}",
            kind="success", duration=6000,
        )

    def append_years_info(self):
        if not self.last:
            self.notify("Scan a folder first.", kind="warning")
            return
        body = vy.format_years_info(self.last["mods"])
        if not body:
            self.notify(
                "All scanned vehicles are supported - nothing to append.",
                kind="info",
            )
            return
        workdir = Path(__file__).resolve().parent.parent
        path = filedialog.askopenfilename(
            title="Choose the years_info.txt to append to",
            initialdir=str(workdir),
            initialfile="years_info.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*")],
        )
        if not path:
            return
        section = f"\n--- vycompat scan {date.today().isoformat()} ---\n{body}\n"
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(section)
        self.notify(
            f"years_info section appended to {theme.short_path(path)}",
            kind="success", duration=6000,
        )

    def copy_years(self):
        if not self.last:
            self.notify("Scan a folder first.", kind="warning")
            return
        text, count = vy.chatgpt_template(self.last["mods"])
        if not text:
            self.notify(
                "All scanned mods are supported - nothing to copy.",
                kind="info",
            )
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify(
            f"Copied {count} {plural(count, 'item line')} to the clipboard.",
            kind="success", duration=5000,
        )

    def copy_details(self):
        text = self.details.get("1.0", "end").strip()
        if not text:
            self.notify("Nothing to copy.", kind="info")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify("Details copied to the clipboard.", kind="success")

    def copy_unsupported(self):
        if not self.last:
            self.notify("Scan a folder first.", kind="warning")
            return
        target = filedialog.askdirectory(title="Copy unsupported mods into...")
        if not target:
            return
        copied = vy.copy_unsupported(self.last["mods"], target)
        if not copied:
            self.notify("Nothing to copy.", kind="info")
            return
        copied_count = sum(1 for _name, action in copied if action == "copied")
        self.notify(
            f"{len(copied)} {plural(len(copied), 'mod')} handled - "
            f"{copied_count} copied to {theme.short_path(target)}",
            kind="success", duration=6000,
        )

    def confirm_addon_changes(
        self, plan, install_dir=None, pending=None, title="Review addon changes"
    ):
        """Show the review dialog; True means the user confirmed the write."""
        dialog = ChangesDialog(
            self.root, plan, vy.SOURCE_ADDON_LUA.parent,
            install_dir=install_dir, pending=pending, title=title,
            th=self.theme,
        )
        self.root.wait_window(dialog)
        return bool(dialog.result)

    def show_addon_history(self):
        if not self.ensure_addon_source():
            return
        install_dir = vy.default_mods_dir()
        dialog = AddonHistoryDialog(
            self.root, vy.SOURCE_ADDON_LUA.parent,
            install_dir=install_dir, th=self.theme,
        )
        self.root.wait_window(dialog)
        result = dialog.result
        if not result:
            return
        try:
            report = history.restore_addon_snapshot(
                vy.SOURCE_ADDON_LUA.parent,
                result["snapshot"],
                install_dir=install_dir if result["install"] else None,
            )
        except Exception:
            self.show_error(
                "Restore failed",
                "The addon could not be fully restored. A snapshot of the "
                "state before this restore is in ADDON HISTORY... if you "
                "need to recover.",
                details=traceback.format_exc(),
            )
            return

        self.addon_var.set("installed" if report["installed"] else "source")
        state = "installed" if report["installed"] else "built, not installed"
        self.notify(
            f"Restored addon v{report['version']} from snapshot - {state}",
            kind="success", duration=7000,
        )
        self.status_var.set(
            f"Addon restored to v{report['version']} ({state})"
        )
        self.start_scan()

    def add_years(self):
        selection = self.tree.selection()
        row = self.rows_by_iid.get(selection[0]) if selection else None
        if row is None or row["kind"] != "mod":
            return
        mod = row["mod"]
        missing = vy.missing_vehicles(mod)
        if not missing:
            return
        if not self.ensure_addon_source():
            return

        install_dir = vy.default_mods_dir()
        dialog = YearDialog(self.root, mod, missing, install_dir)
        self.root.wait_window(dialog)
        result = dialog.result
        if not result:
            return

        env = mod["custom_environment"]
        title = mod["title"] or mod["file"]
        if result["mode"] == "mod":
            mod_years = {env: result["year"]}
            vehicle_years = {}
            description_mods = [f"- {env} ({title}) - {result['year']}"]
            description_vehicles = None
        else:
            by_key = {
                vehicle["addon_vehicle_key"]: vehicle
                for vehicle in missing
            }
            mod_years = {}
            vehicle_years = dict(result["years"])
            sub_lines = [
                f"  - {by_key[key]['name'] or by_key[key]['xml']} - {year}"
                for key, year in result["years"].items()
            ]
            description_mods = None
            description_vehicles = [(f"- {env} ({title})", sub_lines)]

        preview_install = install_dir if result["install"] else None
        try:
            plan = vy.plan_addon_years(
                vy.SOURCE_ADDON_LUA.parent,
                mod_years=mod_years,
                vehicle_years=vehicle_years,
                description_mods=description_mods,
                description_vehicles=description_vehicles,
            )
        except Exception:
            self.show_error(
                "Preview failed",
                "The addon changes could not be prepared. Nothing was written.",
                details=traceback.format_exc(),
            )
            return

        if not plan["changed"]:
            self.notify(
                "Nothing to change - those years are already in the addon.",
                kind="info",
            )
            return

        if not self.confirm_addon_changes(
            plan, preview_install, title=f"Review addon changes - {title}"
        ):
            self.status_var.set("Addon changes cancelled - nothing was written")
            return

        snapshot_reason = f"Add years: {env} ({title})"
        try:
            snapshot = history.snapshot_addon(
                vy.SOURCE_ADDON_LUA.parent, reason=snapshot_reason
            )
        except Exception:
            self.show_error(
                "Snapshot failed",
                "No addon changes were written because a safety snapshot "
                "could not be created.",
                details=traceback.format_exc(),
            )
            return

        try:
            report = vy.export_addon_years(
                vy.SOURCE_ADDON_LUA.parent,
                mod_years=mod_years,
                vehicle_years=vehicle_years,
                description_mods=description_mods,
                description_vehicles=description_vehicles,
                install_dir=preview_install,
            )
        except Exception:
            self.show_error(
                "Export failed",
                "The addon could not be updated. Use ADDON HISTORY... to restore "
                "the snapshot if needed.",
                details=traceback.format_exc(),
            )
            return
        report["snapshot"] = snapshot["path"]

        if not report["changed"]:
            self.notify(
                "Nothing to change - those years are already in the addon.",
                kind="info",
            )
            return

        self.finish_addon_export(report, reselect_file=mod["file"])

    def finish_addon_export(self, report, reselect_file=None, pending=None):
        written = sum(
            1 for entry in report["entries"] if entry["action"] != "unchanged"
        )
        parts = [f"Addon updated to v{report['version']}"]
        parts.append("installed" if report["installed"] else "built, not installed")
        if pending:
            parts.append(
                f"Skipped {len(pending)} "
                f"{plural(len(pending), 'line')} that still had ? or no year"
            )
        if report["description_updated"]:
            parts.append("description updated")
        if report.get("snapshot"):
            parts.append("undo available in ADDON HISTORY...")
        self.notify(
            " - ".join(parts), kind="success", duration=7000
        )

        self.addon_var.set("installed" if report["installed"] else "source")
        self._reselect_file = reselect_file
        state = "installed" if report["installed"] else "not installed"
        self.status_var.set(
            f"Addon updated to v{report['version']} ({state}) - {written} "
            f"entr{'y' if written == 1 else 'ies'}"
        )
        self.start_scan()

    def paste_years(self):
        if not self.ensure_addon_source():
            return

        install_dir = vy.default_mods_dir()
        dialog = PasteYearsDialog(self.root, install_dir)
        self.root.wait_window(dialog)
        result = dialog.result
        if not result:
            return

        mod_years = result["mod_years"]
        vehicle_years = result["vehicle_years"]
        mods = self.last["mods"] if self.last else []
        description_mods, description_vehicles = vy.description_entries(
            mod_years, vehicle_years, mods
        )
        preview_install = install_dir if result["install"] else None
        try:
            plan = vy.plan_addon_years(
                vy.SOURCE_ADDON_LUA.parent,
                mod_years=mod_years,
                vehicle_years=vehicle_years,
                description_mods=description_mods,
                description_vehicles=description_vehicles,
            )
        except Exception:
            self.show_error(
                "Preview failed",
                "The addon changes could not be prepared. Nothing was written.",
                details=traceback.format_exc(),
            )
            return

        if not plan["changed"]:
            self.notify(
                "Nothing to change - those years are already in the addon.",
                kind="info",
            )
            return

        count = len(mod_years) + len(vehicle_years)
        if not self.confirm_addon_changes(
            plan, preview_install, pending=result["pending"],
            title=f"Review addon changes - paste ({count} entries)",
        ):
            self.status_var.set("Paste cancelled - nothing was written")
            return

        snapshot_reason = f"Paste years ({count} entries)"
        try:
            snapshot = history.snapshot_addon(
                vy.SOURCE_ADDON_LUA.parent, reason=snapshot_reason
            )
        except Exception:
            self.show_error(
                "Snapshot failed",
                "No addon changes were written because a safety snapshot "
                "could not be created.",
                details=traceback.format_exc(),
            )
            return

        try:
            report = vy.export_addon_years(
                vy.SOURCE_ADDON_LUA.parent,
                mod_years=mod_years,
                vehicle_years=vehicle_years,
                description_mods=description_mods,
                description_vehicles=description_vehicles,
                install_dir=preview_install,
            )
        except Exception:
            self.show_error(
                "Export failed",
                "The addon could not be updated. Use ADDON HISTORY... to restore "
                "the snapshot if needed.",
                details=traceback.format_exc(),
            )
            return
        report["snapshot"] = snapshot["path"]

        if not report["changed"]:
            self.notify(
                "Nothing to change - those years are already in the addon.",
                kind="info",
            )
            return

        self.finish_addon_export(report, pending=result["pending"])

    def _cancel_startup_check(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if self._startup_after is not None:
            try:
                self.root.after_cancel(self._startup_after)
            except tk.TclError:
                pass
            self._startup_after = None

    def _on_close(self):
        self.closing = True
        self._cancel_startup_check()
        self._cancel_hscroll_sync()
        if self._toast_after is not None:
            try:
                self.root.after_cancel(self._toast_after)
            except tk.TclError:
                pass
        self.root.destroy()


class YearDialog(tk.Toplevel):
    """Ask for the year(s) of one mod - either one year or one per vehicle."""

    def __init__(self, parent, mod, missing, install_dir, th=None):
        super().__init__(parent)
        self.mod = mod
        self.missing = missing
        self.install_dir = install_dir
        self.result = None
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)

        theme.style_dialog(self)
        self.title(f"Add years - {mod['file']}")
        self.resizable(False, False)
        self.transient(parent)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(fill="both", expand=True, padx=16, pady=14)

        heading = mod["title"] or mod["file"]
        tk.Label(
            content, text=heading, bg=theme.PANEL, fg=theme.TEXT,
            font=self.th.heading(13, "bold"), anchor="w",
        ).pack(fill="x")
        missing_count = len(missing)
        verb = "needs" if missing_count == 1 else "need"
        tk.Label(
            content,
            text=(
                f"{missing_count} {plural(missing_count, 'vehicle')} "
                f"{verb} a year"
            ),
            bg=theme.PANEL, fg=theme.TEXT_MUTED, font=self.th.body(9),
            anchor="w",
        ).pack(fill="x", pady=(2, 10))

        default_mode = (
            "mod" if len(missing) == len(mod["vehicles"]) else "vehicle"
        )
        self.mode_var = tk.StringVar(value=default_mode)
        self.shared_var = tk.StringVar()

        row = tk.Frame(content, bg=theme.PANEL)
        row.pack(fill="x", pady=2)
        ttk.Radiobutton(
            row, text="One year for the whole mod", value="mod",
            variable=self.mode_var, command=self._sync,
        ).pack(side="left")
        self.shared_entry = ttk.Entry(
            row, textvariable=self.shared_var, width=8
        )
        self.shared_entry.pack(side="left", padx=10)

        ttk.Radiobutton(
            content, text="A different year for each vehicle", value="vehicle",
            variable=self.mode_var, command=self._sync,
        ).pack(anchor="w", pady=(8, 4))

        list_header = tk.Frame(content, bg=theme.PANEL)
        list_header.pack(fill="x", padx=(24, 0), pady=(0, 2))
        tk.Label(
            list_header, text="VEHICLE", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.th.heading(8, "bold"), width=36, anchor="w",
        ).pack(side="left")
        tk.Label(
            list_header, text="YEAR", bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.th.heading(8, "bold"), anchor="w",
        ).pack(side="left", padx=(10, 0))

        list_wrap = tk.Frame(content, bg=theme.PANEL)
        list_wrap.pack(fill="both", expand=True)
        list_wrap.rowconfigure(0, weight=1)
        list_wrap.columnconfigure(0, weight=1)
        canvas_height = min(250, max(40, 30 * len(missing) + 6))
        self.vehicle_canvas = tk.Canvas(
            list_wrap, bg=theme.PANEL, highlightthickness=0,
            width=480, height=canvas_height,
        )
        self.vehicle_canvas.grid(row=0, column=0, sticky="nsew")
        vehicle_scroll = ttk.Scrollbar(
            list_wrap, orient="vertical", command=self.vehicle_canvas.yview
        )
        self.vehicle_canvas.configure(yscrollcommand=vehicle_scroll.set)
        vehicle_scroll.grid(row=0, column=1, sticky="ns")

        vehicles = tk.Frame(self.vehicle_canvas, bg=theme.PANEL)
        self._vehicle_window = self.vehicle_canvas.create_window(
            (0, 0), window=vehicles, anchor="nw"
        )
        vehicles.bind(
            "<Configure>",
            lambda _event: self.vehicle_canvas.configure(
                scrollregion=self.vehicle_canvas.bbox("all")
            ),
        )
        self.vehicle_canvas.bind(
            "<Configure>",
            lambda event: self.vehicle_canvas.itemconfigure(
                self._vehicle_window, width=event.width
            ),
        )

        self.vehicle_vars = {}
        self.vehicle_entries = []
        for vehicle in missing:
            line = tk.Frame(vehicles, bg=theme.PANEL)
            line.pack(fill="x", pady=1)
            tk.Label(
                line, text=vehicle["name"] or vehicle["xml"],
                bg=theme.PANEL, fg=theme.TEXT, font=self.th.body(9),
                width=36, anchor="w",
            ).pack(side="left")
            var = tk.StringVar()
            entry = ttk.Entry(line, textvariable=var, width=8)
            entry.pack(side="left", padx=10)
            self.vehicle_vars[vehicle["addon_vehicle_key"]] = var
            self.vehicle_entries.append(entry)

        self.install_var = tk.BooleanVar(value=True)
        if install_dir is not None:
            ttk.Checkbutton(
                content,
                text="Install the rebuilt addon into the game mods folder",
                variable=self.install_var,
            ).pack(anchor="w", pady=(12, 0))
            tk.Label(
                content, text=theme.short_path(install_dir), bg=theme.PANEL,
                fg=theme.TEXT_DIM, font=self.th.body(8), anchor="w",
                justify="left", wraplength=480,
            ).pack(anchor="w", padx=(24, 0), pady=(2, 0))

        self.error_var = tk.StringVar()
        tk.Label(
            content, textvariable=self.error_var, bg=theme.PANEL,
            fg=theme.DANGER, font=self.th.body(9), anchor="w",
            justify="left", wraplength=480,
        ).pack(fill="x", pady=(8, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons, text="CANCEL", command=self.destroy
        ).pack(side="right")
        ttk.Button(
            buttons, text="SAVE & EXPORT", style="Primary.TButton",
            command=self._save,
        ).pack(side="right", padx=(0, 8))

        self._sync()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())
        theme.reveal_dialog(self, parent)

    def _sync(self):
        self.error_var.set("")
        is_mod = self.mode_var.get() == "mod"
        self.shared_entry.config(state="normal" if is_mod else "disabled")
        for entry in self.vehicle_entries:
            entry.config(state="disabled" if is_mod else "normal")
        if is_mod:
            self.shared_entry.focus_set()
        elif self.vehicle_entries:
            self.vehicle_entries[0].focus_set()

    def _save(self):
        self.error_var.set("")
        install = bool(self.install_var.get()) and self.install_dir is not None
        try:
            if self.mode_var.get() == "mod":
                self.result = {
                    "mode": "mod",
                    "year": vy.validate_year(self.shared_var.get()),
                    "install": install,
                }
            else:
                years = {
                    key: vy.validate_year(var.get())
                    for key, var in self.vehicle_vars.items()
                }
                self.result = {
                    "mode": "vehicle", "years": years, "install": install,
                }
        except ValueError as exc:
            self.error_var.set(str(exc))
            return
        self.destroy()


class PasteYearsDialog(tk.Toplevel):
    """Paste a KEY = YEAR list (from "Copy years...") and apply it."""

    def __init__(self, parent, install_dir, th=None):
        super().__init__(parent)
        self.install_dir = install_dir
        self.result = None
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)

        theme.style_dialog(self)
        self.title("Paste years")
        self.resizable(True, True)
        self.transient(parent)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            content,
            text="Paste the copied list and replace each ? with a year",
            bg=theme.PANEL, fg=theme.TEXT, font=self.th.heading(13, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            content,
            text="KEY = year   -   KEY without / = whole mod, "
                 "KEY with / = single vehicle",
            bg=theme.PANEL, fg=theme.TEXT_MUTED, font=self.th.body(9),
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        text_wrap = tk.Frame(content, bg=theme.PANEL)
        text_wrap.pack(fill="both", expand=True)
        text_wrap.rowconfigure(0, weight=1)
        text_wrap.columnconfigure(0, weight=1)
        self.text = tk.Text(
            text_wrap, width=86, height=16, wrap="none",
            font=self.th.mono(9),
        )
        theme.style_text(
            self.text, background=theme.PANEL_RAISED,
            font=self.th.mono(9),
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            text_wrap, orient="vertical", command=self.text.yview
        )
        self.text.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(
            text_wrap, orient="horizontal", command=self.text.xview
        )
        self.text.configure(xscrollcommand=hscroll.set)
        hscroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(text_wrap, bg=theme.PANEL).grid(
            row=1, column=1, sticky="nsew"
        )

        options = tk.Frame(content, bg=theme.PANEL)
        options.pack(fill="x", pady=(8, 0))
        ttk.Button(
            options, text="PASTE FROM CLIPBOARD", style="Small.TButton",
            command=self.paste_clipboard,
        ).pack(side="left")
        self.install_var = tk.BooleanVar(value=True)
        if install_dir is not None:
            ttk.Checkbutton(
                options,
                text="Install the rebuilt addon into the game mods folder",
                variable=self.install_var,
            ).pack(side="left", padx=(12, 0))

        if install_dir is not None:
            tk.Label(
                content, text=theme.short_path(install_dir), bg=theme.PANEL,
                fg=theme.TEXT_DIM, font=self.th.body(8), anchor="w",
                justify="left", wraplength=620,
            ).pack(fill="x", padx=(0, 0), pady=(2, 0))

        self.error_var = tk.StringVar()
        tk.Label(
            content, textvariable=self.error_var, bg=theme.PANEL,
            fg=theme.DANGER, font=self.th.body(9), anchor="w",
            justify="left", wraplength=620,
        ).pack(fill="x", pady=(8, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(
            buttons, text="CANCEL", command=self.destroy
        ).pack(side="right")
        ttk.Button(
            buttons, text="APPLY YEARS", style="Primary.TButton",
            command=self._apply,
        ).pack(side="right", padx=(0, 8))

        self._prefill_clipboard()
        self.bind("<Escape>", lambda _event: self.destroy())
        theme.reveal_dialog(self, parent)

    def _clipboard_text(self):
        try:
            return self.clipboard_get()
        except tk.TclError:
            return ""

    def _prefill_clipboard(self):
        text = self._clipboard_text()
        if text and re.search(
            r"^\s*[^#\s][^=]*=\s*(\?|\d{4}\b)", text, re.M
        ):
            self.text.insert("1.0", text)

    def paste_clipboard(self):
        self.error_var.set("")
        text = self._clipboard_text()
        if not text:
            self.error_var.set("The clipboard is empty.")
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def _apply(self):
        self.error_var.set("")
        parsed = vy.parse_years_text(self.text.get("1.0", "end"))
        if parsed["errors"]:
            shown = "\n".join(parsed["errors"][:6])
            extra = ""
            if len(parsed["errors"]) > 6:
                extra = f"\n... and {len(parsed['errors']) - 6} more"
            self.error_var.set("Fix these lines first:\n" + shown + extra)
            return
        if not parsed["mod_years"] and not parsed["vehicle_years"]:
            self.error_var.set(
                "No years found - replace ? with a year."
            )
            return
        self.result = {
            "mod_years": parsed["mod_years"],
            "vehicle_years": parsed["vehicle_years"],
            "pending": parsed["pending"],
            "install": bool(self.install_var.get()) and self.install_dir is not None,
        }
        self.destroy()


class ChangesDialog(tk.Toplevel):
    """Review an addon plan before any source file or ZIP is written."""

    def __init__(self, parent, plan, source_dir, install_dir=None,
                 pending=None, title="Review addon changes", th=None):
        super().__init__(parent)
        self.plan = plan
        self.source_dir = Path(source_dir)
        self.install_dir = Path(install_dir) if install_dir else None
        self.pending = list(pending or [])
        self.result = None
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)

        theme.style_dialog(self)
        self.title(title)
        self.resizable(True, True)
        self.minsize(480, 360)
        self.transient(parent)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            content, text="Review addon changes", bg=theme.PANEL,
            fg=theme.TEXT, font=self.th.heading(13, "bold"), anchor="w",
        ).pack(fill="x")
        self.summary_label = tk.Label(
            content, text=preview_summary(plan.get("entries", []), len(self.pending)),
            bg=theme.PANEL, fg=theme.TEXT_MUTED, font=self.th.body(9),
            anchor="w", justify="left", wraplength=700,
        )
        self.summary_label.pack(fill="x", pady=(2, 2))
        if plan.get("changed"):
            version_text = (
                f"Addon version {plan.get('version', '?')} -> "
                f"{plan.get('new_version', '?')}"
            )
        else:
            version_text = f"Addon version {plan.get('version', '?')} (unchanged)"
        self.version_label = tk.Label(
            content, text=version_text, bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.th.body(8), anchor="w",
        )
        self.version_label.pack(fill="x", pady=(0, 8))

        if any(entry.get("action") == "updated" for entry in plan.get("entries", [])):
            self.warning_label = tk.Label(
                content,
                text=(
                    "Amber rows replace an existing addon year after you "
                    "confirm. Store years inside mods and the Vehicle Years "
                    "database are never overwritten at runtime."
                ),
                bg=theme.PANEL, fg=theme.WARNING, font=self.th.body(8),
                anchor="w", justify="left", wraplength=700,
            )
            self.warning_label.pack(fill="x", pady=(0, 6))
        else:
            self.warning_label = None

        tree_wrap = tk.Frame(content, bg=theme.PANEL)
        tree_wrap.pack(fill="both", expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_wrap, columns=("table", "key", "change"),
            show="headings", selectmode="browse", height=9,
        )
        self.tree.heading("table", text="TABLE", anchor="w")
        self.tree.heading("key", text="KEY", anchor="w")
        self.tree.heading("change", text="CHANGE", anchor="w")
        self.tree.column("table", width=145, minwidth=110, stretch=False)
        self.tree.column("key", width=380, minwidth=180, stretch=True)
        self.tree.column("change", width=165, minwidth=130, stretch=False)
        self.tree.tag_configure("preview-change", foreground=theme.WARNING)
        self.tree.tag_configure("preview-add", foreground=theme.SUCCESS)
        self.tree.tag_configure("preview-same", foreground=theme.TEXT_DIM)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(
            tree_wrap, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(xscrollcommand=hscroll.set)
        hscroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(tree_wrap, bg=theme.PANEL).grid(
            row=1, column=1, sticky="nsew"
        )

        entries = sorted_preview_entries(plan.get("entries", []))
        for index, entry in enumerate(entries):
            self.tree.insert(
                "", "end", iid=f"change{index}",
                values=(
                    entry.get("table", ""),
                    entry.get("key", ""),
                    preview_action_text(entry),
                ),
                tags=(preview_action_tag(entry),),
            )
        if not entries:
            self.tree.insert(
                "", "end", iid="change-empty",
                values=("", "No entries to write.", ""),
                tags=("preview-same",),
            )

        paths = tk.Frame(
            content, bg=theme.PANEL_RAISED, highlightbackground=theme.BORDER,
            highlightthickness=1, bd=0,
        )
        paths.pack(fill="x", pady=(10, 0))
        path_inner = tk.Frame(paths, bg=theme.PANEL_RAISED)
        path_inner.pack(fill="x", padx=10, pady=8)
        self.path_labels = []
        zip_path = self.source_dir.parent / vy.ADDON_ZIP_NAME
        path_rows = [
            ("Source", self.source_dir),
            ("ZIP", zip_path),
            (
                "Install",
                self.install_dir
                if self.install_dir
                else "No - rebuild the ZIP only",
            ),
        ]
        for label, value in path_rows:
            line = tk.Frame(path_inner, bg=theme.PANEL_RAISED)
            line.pack(fill="x", pady=1)
            tk.Label(
                line, text=f"{label}:", bg=theme.PANEL_RAISED,
                fg=theme.TEXT_DIM, font=self.th.heading(8, "bold"),
                width=8, anchor="w",
            ).pack(side="left")
            value_label = tk.Label(
                line, text=theme.short_path(value), bg=theme.PANEL_RAISED,
                fg=theme.TEXT, font=self.th.body(8), anchor="w",
                justify="left", wraplength=580,
            )
            value_label.pack(side="left", fill="x", expand=True)
            self.path_labels.append(value_label)

        note = (
            "The modDesc description will also be extended."
            if plan.get("description_updated")
            else "The modDesc version is bumped; its description section was "
                 "not found, so no description lines will be added."
        )
        if not plan.get("changed"):
            note = "There is nothing to write."
        self.note_label = tk.Label(
            content, text=note, bg=theme.PANEL, fg=theme.TEXT_DIM,
            font=self.th.body(8), anchor="w", justify="left", wraplength=700,
        )
        self.note_label.pack(fill="x", pady=(6, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons, text="CANCEL", command=self.destroy
        ).pack(side="right")
        if plan.get("changed"):
            self.confirm_btn = ttk.Button(
                buttons, text="WRITE & REBUILD", style="Primary.TButton",
                command=self._confirm,
            )
            self.confirm_btn.pack(side="right", padx=(0, 8))
        else:
            self.confirm_btn = ttk.Button(
                buttons, text="CLOSE", style="Primary.TButton",
                command=self.destroy,
            )
            self.confirm_btn.pack(side="right", padx=(0, 8))

        content.bind("<Configure>", self._reflow)
        self.bind("<Escape>", lambda _event: self.destroy())
        if plan.get("changed"):
            self.bind("<Return>", lambda _event: self._confirm())
        theme.reveal_dialog(self, parent)

    def _reflow(self, event):
        width = max(300, event.width - 30)
        for label in (
            self.summary_label, self.version_label, self.note_label,
            *self.path_labels,
        ):
            try:
                label.configure(wraplength=width)
            except tk.TclError:
                pass
        if self.warning_label is not None:
            try:
                self.warning_label.configure(wraplength=width)
            except tk.TclError:
                pass

    def _confirm(self):
        if not self.plan.get("changed"):
            self.destroy()
            return
        self.result = True
        self.destroy()


class AddonHistoryDialog(tk.Toplevel):
    """Choose a local addon snapshot to restore and rebuild."""

    def __init__(self, parent, source_dir, install_dir=None, th=None):
        super().__init__(parent)
        self.source_dir = Path(source_dir)
        self.install_dir = Path(install_dir) if install_dir else None
        self.snapshots = history.list_addon_snapshots(self.source_dir)
        self.by_iid = {}
        self.result = None
        self.th = th or getattr(parent, "_vycompat_theme", None)
        if self.th is None:
            self.th = theme.apply_theme(parent)

        theme.style_dialog(self)
        self.title("Addon history")
        self.resizable(True, True)
        self.minsize(480, 360)
        self.transient(parent)

        outer = tk.Frame(self, bg=theme.BORDER)
        outer.pack(fill="both", expand=True, padx=14, pady=14)
        body = tk.Frame(outer, bg=theme.PANEL)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        content = tk.Frame(body, bg=theme.PANEL)
        content.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(
            content, text="Addon snapshots", bg=theme.PANEL, fg=theme.TEXT,
            font=self.th.heading(13, "bold"), anchor="w",
        ).pack(fill="x")
        self.help_label = tk.Label(
            content,
            text=(
                "A snapshot is made before every addon export and before "
                "every restore. Restoring rebuilds the ZIP; installing it "
                "into the game mods folder is a separate opt-in."
            ),
            bg=theme.PANEL, fg=theme.TEXT_MUTED, font=self.th.body(9),
            anchor="w", justify="left", wraplength=700,
        )
        self.help_label.pack(fill="x", pady=(2, 8))

        tree_wrap = tk.Frame(content, bg=theme.PANEL)
        tree_wrap.pack(fill="both", expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_wrap, columns=("created", "version", "reason"),
            show="headings", selectmode="browse", height=8,
        )
        self.tree.heading("created", text="CREATED", anchor="w")
        self.tree.heading("version", text="VERSION", anchor="w")
        self.tree.heading("reason", text="REASON", anchor="w")
        self.tree.column("created", width=150, minwidth=125, stretch=False)
        self.tree.column("version", width=90, minwidth=75, stretch=False)
        self.tree.column("reason", width=400, minwidth=180, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(
            tree_wrap, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(xscrollcommand=hscroll.set)
        hscroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(tree_wrap, bg=theme.PANEL).grid(
            row=1, column=1, sticky="nsew"
        )

        first = None
        for index, snapshot in enumerate(self.snapshots):
            iid = f"snapshot{index}"
            self.by_iid[iid] = snapshot
            self.tree.insert(
                "", "end", iid=iid,
                values=(
                    format_snapshot_time(snapshot["created"]),
                    snapshot["version"],
                    snapshot["reason"],
                ),
            )
            if first is None:
                first = iid
        if not self.snapshots:
            self.tree.insert(
                "", "end", iid="snapshot-empty",
                values=("", "", "No snapshots yet - export or restore first."),
            )

        self.selected_var = tk.StringVar(
            value=(
                "Select a snapshot to restore."
                if self.snapshots
                else "No snapshots available."
            )
        )
        self.selected_label = tk.Label(
            content, textvariable=self.selected_var, bg=theme.PANEL,
            fg=theme.TEXT_MUTED, font=self.th.body(8), anchor="w",
            justify="left", wraplength=700,
        )
        self.selected_label.pack(fill="x", pady=(8, 0))
        self.history_label = tk.Label(
            content,
            text=(
                f"History folder: "
                f"{theme.short_path(history.history_path(self.source_dir))}"
            ),
            bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
            anchor="w", justify="left", wraplength=700,
        )
        self.history_label.pack(fill="x", pady=(2, 0))

        self.install_var = tk.BooleanVar(value=False)
        self.install_hint = None
        if self.install_dir is not None:
            ttk.Checkbutton(
                content,
                text="Install the rebuilt addon into the game mods folder",
                variable=self.install_var,
            ).pack(anchor="w", pady=(10, 0))
            self.install_hint = tk.Label(
                content, text=theme.short_path(self.install_dir),
                bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
                anchor="w", justify="left", wraplength=700,
            )
            self.install_hint.pack(fill="x", padx=(24, 0), pady=(2, 0))
        else:
            self.install_hint = tk.Label(
                content,
                text="The rebuilt ZIP will not be installed automatically.",
                bg=theme.PANEL, fg=theme.TEXT_DIM, font=self.th.body(8),
                anchor="w", justify="left", wraplength=700,
            )
            self.install_hint.pack(fill="x", pady=(8, 0))

        buttons = tk.Frame(content, bg=theme.PANEL)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons, text="CANCEL", command=self.destroy
        ).pack(side="right")
        self.restore_btn = ttk.Button(
            buttons, text="RESTORE & REBUILD", style="Primary.TButton",
            command=self._restore, state="disabled",
        )
        self.restore_btn.pack(side="right", padx=(0, 8))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        if first is not None:
            self.tree.selection_set(first)
            self.tree.see(first)
            self._on_select()
        content.bind("<Configure>", self._reflow)
        self.bind("<Escape>", lambda _event: self.destroy())
        theme.reveal_dialog(self, parent)

    def _reflow(self, event):
        width = max(260, event.width - 30)
        for label in (
            self.help_label, self.selected_label, self.history_label,
            self.install_hint,
        ):
            if label is None:
                continue
            try:
                label.configure(wraplength=width)
            except tk.TclError:
                pass

    def _on_select(self, _event=None):
        selection = self.tree.selection()
        snapshot = self.by_iid.get(selection[0]) if selection else None
        if snapshot is None:
            self.restore_btn.config(state="disabled")
            return
        created = format_snapshot_time(snapshot["created"])
        self.selected_var.set(
            f"Restore addon v{snapshot['version']} from {created} "
            f"({snapshot['reason']})."
        )
        self.restore_btn.config(state="normal")

    def _restore(self):
        selection = self.tree.selection()
        snapshot = self.by_iid.get(selection[0]) if selection else None
        if snapshot is None:
            return
        self.result = {
            "snapshot": snapshot["path"],
            "install": (
                bool(self.install_var.get())
                and self.install_dir is not None
            ),
        }
        self.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=f"{vy.TOOL}-gui",
        description="FS25 Vehicle Year Compatibility Tool GUI",
    )
    parser.add_argument(
        "--easter-egg", dest="easter_egg", action="store_true", default=None,
        help="always show the optional alternate-icon button",
    )
    parser.add_argument(
        "--no-easter-egg", dest="easter_egg", action="store_false",
        help="never show the optional alternate-icon button",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"{vy.APP_NAME} {vy.__version__}",
    )
    args = parser.parse_args(argv)

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"{vy.TOOL}: cannot open a window: {exc}", file=sys.stderr)
        return 2
    VycompatApp(root, easter_egg=args.easter_egg)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
