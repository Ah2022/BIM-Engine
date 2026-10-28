# Phase C layout and workflow

Implemented responsive floating/docked layouts, the Now reviewing card, Copy IDs
icon, Previous/Next navigation and light/dark Revit theme integration.

## Layout

- A floating host with at least 1040 DIPs of content width uses list-left and
  review-right columns. Narrow floating windows and docked hosts remain stacked.
- Star-sized pane rows/columns and proportional inner scroll limits replace the
  prior fixed-height page. Next/Previous remain visible outside the card scroller.
- Both custom Undock windows and native floating host HWNDs are recognized.
- Next/Previous follow the displayed filtered/sorted items, clear bulk selection,
  stop at list boundaries and schedule the existing automatic 3D preview.

## Theme

`DashboardTheme.FollowRevit` reads `UIThemeManager.CurrentTheme` at startup;
`UIApplication.ThemeChanged` reapplies it. Bound palette brushes remain live in
WPF styles/templates. Buttons, dropdowns, text inputs, selection colours, the
review card and viewport background follow the palette. Colour properties remain
excluded from pinned-view metadata serialization.

API signatures were checked against the installed Revit 2024 RevitAPIUI XML docs.
The fixture checks the initial host theme and renders both palettes without
changing the user's saved Revit theme preference. Native drag-to-float detection
is implemented; the automated layout checks exercise the explicit Undock window.

## Validation

- Final Release build: 0 warnings, 0 errors.
- All 76 Revit 2024 integration checks passed against the staged DLL; package hashes match.
- `tests/revit_phase_c.py` extends the real Revit regression fixture with wide/narrow
  floating transitions, dock restoration, short-window sizing, card contents,
  accessible Copy IDs name, both palette renders and navigation order/boundaries.
- The fixture also covers existing scanning, previews, keyboard, pinning/cleanup,
  sorting, filters, inline triage and bulk ignore, using disposable models and DB.
- Final status, check list, run directory, and tested DLL hash are recorded in
  `verification/phase-c-result.json`. Screenshots are in its run directory.

The extension is built and staged in the workspace; installation into the user's
pyRevit extension directory is not performed. Restart Revit after installing it.
