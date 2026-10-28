# Phase A UI improvements

Implemented in the WPF dashboard and Python scan bridge:

- Unified category chips, Include links, Scan, and inline progress. Existing ribbon
  Scan/Settings entries open this panel; scan success no longer opens an alert.
- One-line active/new/resolved summary, with raw scan statistics and coverage in
  Details. Change counts are stored in the existing scan audit record without a
  database schema migration. Older scans display unknown change counts as dashes.
- Debounced automatic 3D preview through Revit ExternalEvent; 3D/2D/Section tabs.
- Gear popup for rotation, axis, context distance, nearby context, and focus.
- Overlap size and Delete generated views labels; internal-feet XYZ in tooltip.
- Clash-list Up/Down, Enter, Space and dashboard-wide Ctrl+F shortcuts.
- Narrow panes scroll vertically to preserve usable list and viewport sizes.

## Validation

- Release net48/x64 build: 0 warnings, 0 errors; extension DLL and manifest staged.
- Offline Python suite: 37 tests passed, including new/resolved count persistence,
  partial coverage, changed scopes, reopened issues, old scans, and raw statistics.
- Revit 2024 fixture: see `verification/phase-a-result.json` for final status,
  DLL hash, isolated run directory, and individual checks. The fixture uses only
  newly created models and its own SQLite/config files.
- Real ExternalEvent checks cover auto-preview, view tabs, inline scanning,
  Up/Down/Enter/Space, linked elements, partial coverage, resolution and history.
- WPF renders cover widths 460, 620 and 900 pixels. Ctrl+F and the floating-window
  shortcut route were reviewed in code; physical Ctrl+F input was not automated.

The package is staged in this workspace, not installed into the user's pyRevit
extension directory. Restart Revit after installation to load the rebuilt DLL.
