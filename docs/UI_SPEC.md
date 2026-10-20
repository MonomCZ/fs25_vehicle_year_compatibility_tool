# UI Specification --- FS25 Vehicle Year Compatibility Tool

## Goal

Build a polished desktop-style interface for the **FS25 Vehicle Year
Compatibility Tool**, a companion tool for Farming Simulator 25 mod metadata.
The app helps
users inspect mod vehicles and implements, find or enter real-world
production years, review confidence, and copy a structured prompt/data
block for ChatGPT.

The visual direction should feel like a **Farming Simulator 25 in-game
menu**, not a generic admin dashboard. Use the game as visual
inspiration, but do not copy official logos, trademarks, or exact
copyrighted screens/assets. Create an original interface that evokes the
same agricultural machinery atmosphere.

## Core design principles

1.  **Dark, industrial, agricultural UI** --- charcoal panels, muted
    grey surfaces, restrained green accents, white text.
2.  **Information first** --- mod names, item names, years, and
    certainty must be easy to scan.
3.  **Game-menu structure** --- strong horizontal header, compact
    navigation, large content panels, subtle separators, clear selected
    states.
4.  **Practical, not flashy** --- no glassmorphism, neon gradients,
    oversized rounded cards, or generic SaaS dashboard styling.
5.  **Desktop-first** --- optimize for 1280×720 and 1920×1080, while
    remaining usable at smaller window sizes.
6.  **Readable density** --- show many items without making the
    interface feel cramped.
7.  **Keyboard-friendly** --- visible focus states, sensible tab order,
    and shortcuts where useful.

## Visual identity

### Color palette

Use these as starting tokens. Keep contrast accessible.

-   `--bg`: `#171A17` --- main application background
-   `--panel`: `#222722` --- primary content panels
-   `--panel-raised`: `#2B312B` --- raised panels, dropdowns, hover
    surfaces
-   `--panel-selected`: `#343D32` --- selected row or selected
    navigation item
-   `--green`: `#78A83B` --- primary FS-style agricultural accent
-   `--green-hover`: `#8DBD4D` --- hover/active accent
-   `--green-dark`: `#3D5D26` --- subdued green backgrounds
-   `--text`: `#F0F2ED` --- primary text
-   `--text-muted`: `#B0B7AC` --- secondary text
-   `--text-dim`: `#7F897D` --- tertiary text, disabled labels
-   `--border`: `#41483F` --- panel and row separators
-   `--warning`: `#D6A84B` --- uncertain values or warnings
-   `--danger`: `#D65C50` --- errors and destructive actions
-   `--success`: `#82B85A` --- confirmed/success states

Do not use bright green for every element. Reserve it for selection,
primary actions, toggles, progress, and important indicators.

### Typography

-   Use a clean, condensed or semi-condensed sans-serif for headings if
    available.
-   Use a neutral sans-serif for body text and controls.
-   Use tabular numerals for years and numeric values when supported.
-   Headings should be bold and compact; body text should remain
    readable.
-   Avoid futuristic sci-fi fonts, playful rounded fonts, and excessive
    uppercase text.
-   Suggested hierarchy:
    -   App title: 22--28 px, bold
    -   Page title: 20--24 px, semibold
    -   Panel title: 15--17 px, semibold
    -   Body: 13--15 px
    -   Metadata/help text: 11--12 px

## Window layout

### Main shell

Use a full-window dark background with these areas:

1.  **Top header** --- app name, current workspace/project, status, and
    main actions.
2.  **Left navigation rail** --- compact navigation for the app's main
    sections.
3.  **Main content area** --- the active page, using panels and dense
    list/table layouts.
4.  **Optional bottom status bar** --- item count, current file/mod
    folder, unsaved changes, and background task status.

The layout should feel like a game menu adapted for a desktop utility:
stable, aligned, and panel-based.

### Header

-   Height: approximately 58--68 px.
-   Left: small original app mark/icon and
    `FS25 Vehicle Year Compatibility Tool`.
-   Optional subtitle: `FS25 mod metadata`.
-   Center or main area: current section/workspace title when
    appropriate.
-   Right: status indicator, settings button, and primary action when
    relevant.
-   Use a thin bottom border, not a large shadow.
-   Keep the header visible while navigating between sections.

### Navigation

Use a narrow left rail or compact vertical sidebar, approximately
190--220 px wide when labels are visible.

Suggested sections: - **Overview** - **Mod Library** - **Year Review** -
**ChatGPT Export** - **Settings**

Navigation behavior: - Selected section uses a muted green background or
a left green indicator bar. - Icons are simple, consistent line icons. -
Labels are always visible on desktop. - Avoid colorful emoji icons. -
Keep the number of navigation entries low. The rare, explicitly opt-in
**AMAZING ICON** easter-egg button is the one intentional exception; it stays
hidden unless the 10% roll or a force switch enables it.

### Content panels

-   Use rectangular panels with subtle borders and small corner radii
    (2--6 px).
-   Avoid giant rounded cards.
-   Use consistent internal padding, approximately 16--22 px.
-   Separate areas with borders and spacing rather than heavy shadows.
-   Tables and lists should align perfectly.

## Main screens

### 1. Overview

Purpose: quickly show the current scan/review state.

Include: - Page heading: `Overview` - A compact summary row: - Total
mods - Total vehicles/items - Years verified - Items needing review - A
prominent `Scan mods` or `Refresh library` action. - A `Continue review`
panel showing the next unresolved items. - A recent activity list, if
the app has actual activity data. - A clear empty state when no mod
folder has been selected.

Do not invent stats or show fake activity. If no data is available, show
neutral placeholders and a clear next step.

### 2. Mod Library

Purpose: browse detected mods and their contents.

Use a dense table/list rather than a grid of giant cards.

Suggested columns: - Mod / package - Item count - Verified years - Needs
review - Scan status

Behavior: - Search field at the top. - Filters for `All`,
`Needs review`, `Verified`, and `Unknown`. - Selecting a mod opens its
item list or a detail panel. - Show file/mod names without truncating
important identifiers unnecessarily. - Long paths may be truncated
visually but must be accessible via tooltip or copy action. - Use subtle
row hover and selected-row styling.

### 3. Year Review

This is the app's most important screen.

Use a split layout: - **Left/main area (about 65--70%)**: item table. -
**Right detail panel (about 30--35%)**: selected item's metadata and
year controls.

Table columns: - Item / vehicle name - Mod - Production year -
Certainty - Review status

Certainty values must be exactly: - `sure` - `unsure` - `unknown`

Style the certainty indicator consistently: - `sure`: subdued green
indicator and label - `unsure`: muted amber indicator and label -
`unknown`: neutral grey indicator and label

Do not rely on color alone; always show the text label.

For the selected item, show: - Item name - Mod/package name - Relevant
source/model identifier if available - Current year - Certainty -
Guess/research note when applicable - Source links or source notes if
the app supports them - Editable controls for year, certainty, and guess

Validation: - Accept realistic production years only within the app's
defined valid range. - If certainty is `unknown`, allow a `guess`
value/note to be present. - Do not silently replace unknown data with
invented facts. - Make unsaved edits obvious and provide clear
Save/Apply and Cancel/Reset actions if editing is local.

Bulk actions may be included, but must clearly show how many items will
be affected and must never silently overwrite unrelated fields.

### 4. ChatGPT Export

Purpose: make research easy to hand off to ChatGPT while preserving data
integrity.

Layout: - Heading: `ChatGPT Export` - Short explanation of what will be
copied. - A large, readable code/text preview in a monospaced font. -
Primary action: `Copy prompt + data` - Secondary action:
`Copy data only` - Optional action: `Export .txt` or `Export .json` if
supported.

The copied content should include the special research prompt plus the
selected item data when the user chooses `Copy prompt + data`.

The export preview must preserve: - Original item order - IDs and all
fields that are not explicitly editable by the workflow - The exact
allowed fields being updated (`year`, `certainty`, and `guess`) where
relevant

The UI must make it clear whether the user is copying all items, only
selected items, or only items needing review.

After copying, show a small status message such as
`Copied to clipboard`. Do not claim copying succeeded until the copy
action actually succeeds.

### 5. Settings

Include only settings the app actually supports, for example: - Mod
folder location - Scan behavior - Export behavior - Theme options, if
implemented - API key configuration, if the app supports an API-backed
research mode

If API-key mode exists: - Keep the key masked by default. - Explain what
the key is used for. - Do not show the secret in logs or normal UI. -
Provide a separate no-API-key workflow using copy/paste with ChatGPT. -
Never make API mode the only way to use the app.

## Components and interaction details

### Buttons

-   Primary button: green fill, dark readable text, restrained radius.
-   Secondary button: dark panel fill with border.
-   Destructive button: muted red, only for genuinely destructive
    actions.
-   Disabled buttons should be visibly disabled and must not look
    clickable.
-   Button labels should describe the action, e.g. `Scan mods`,
    `Save changes`, `Copy prompt + data`.

### Inputs

-   Dark field background, subtle border, light text.
-   Green focus outline or border.
-   Clear labels above fields; do not rely on placeholder text as the
    only label.
-   Search should support clearing its contents quickly.
-   Numeric year fields should reject invalid input gracefully and
    explain the issue.

### Tables and lists

-   Use a consistent row height around 38--46 px.
-   Use subtle horizontal dividers.
-   Highlight hover rows gently.
-   Selected rows should have a visible green marker or tinted
    background.
-   Support sorting where it helps.
-   Keep headers readable while scrolling if practical.
-   Provide useful empty states for no results and no selected mod.

### Dialogs and notifications

-   Use compact dialogs for confirmation and settings that need focused
    attention.
-   Never use a confirmation dialog for harmless actions such as opening
    a page.
-   Confirm destructive or bulk-overwrite actions.
-   Use short, non-blocking notifications for copy success, save
    success, and errors.
-   Errors should explain what happened and what the user can do next.

### Loading and progress

-   Scanning should show real progress when measurable.
-   If exact progress is unavailable, use an indeterminate progress
    indicator rather than a fake percentage.
-   Disable only controls that genuinely cannot be used during the
    operation.
-   Show a useful failure state if scanning or parsing fails.

## Icon and imagery direction

-   Prefer simple monochrome line icons.
-   Use original generic agriculture/tool/file icons.
-   Do not use Farming Simulator logos, official game logos,
    screenshots, or extracted game assets unless the project owner has
    explicit rights to use them.
-   Do not decorate every panel with tractor images. This is a
    productivity tool, not a game launcher.
-   If imagery is used, keep it subtle and functional.
-   `Icons/ALTicon.png` is a user-supplied, non-MIT easter egg; do not use it
    as normal navigation or marketing artwork.

## Motion

-   Keep animations short (roughly 100--180 ms).
-   Use transitions for hover, selection, opening panels, and
    notifications.
-   Avoid large animated backgrounds, parallax, bouncing elements, or
    excessive motion.
-   Respect reduced-motion preferences where supported.

## Accessibility and usability

-   Maintain strong text contrast.
-   Never use color as the only way to communicate certainty or status.
-   Make all actions keyboard accessible.
-   Provide visible focus states.
-   Use meaningful labels for icon-only controls.
-   Ensure the interface remains usable at 1280×720.
-   Long filenames, item names, and file paths must not break the
    layout.
-   Avoid tiny text for important information.

## Responsive behavior

At 1280 px and wider: - Show the full sidebar and split review layout.

At narrower desktop widths: - Allow the sidebar to collapse. - Let the
detail panel become a drawer or move below the table. - Keep the main
action buttons accessible. - Avoid horizontal overflow where possible.

At 720 px height: - Keep the header compact. - Allow the content panel
to scroll independently. - Do not let fixed footers cover table rows or
controls.

## Data integrity rules

The UI must support the app's core rule: **change only the fields
explicitly allowed by the current operation**.

For the year-research workflow: - Editable output fields are `year`,
`certainty`, and `guess`. - Preserve IDs, paths, names, ordering, and
every unrelated field exactly. - Clearly distinguish a
researched/verified year from a guess. - Never present a guess as a
verified fact. - Do not silently discard unknown entries. - Show which
items are selected before applying bulk actions or exporting.

## Implementation guidance

Before implementing: 1. Inspect the existing project structure and
identify its current framework, styling system, and reusable components.
2. Preserve the current stack unless there is a clear technical reason
to change it. 3. Implement the visual system as reusable design tokens
rather than scattering hex values throughout the app. 4. Build the shell
and navigation first, then the Year Review table, then the export
workflow. 5. Use real application data and existing logic. Do not
replace working functionality with mock data. 6. Keep UI components
small and reusable. 7. Make every visible control functional. Do not add
decorative buttons that do nothing. 8. Run the available lint,
type-check, and build commands after changes, and fix issues introduced
by the implementation. 9. If a requested detail conflicts with the
existing app architecture, explain the conflict and choose the smallest
safe change. 10. Do not rewrite unrelated parts of the application.

## Definition of done

The implementation is complete when: - The interface consistently
follows the dark FS25-inspired visual direction. - Navigation and every
visible button work. - The Year Review table is readable with realistic
data density. - `sure`, `unsure`, and `unknown` are clearly
distinguishable by both label and visual treatment. - The copy/export
workflow preserves item order and all fields that should not change. -
Empty, loading, success, and error states are handled. - The layout
works at 1280×720 and 1920×1080. - Existing app functionality still
works. - The project builds successfully.
