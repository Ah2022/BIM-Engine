# Phase 2 — implementation and verification

Verified on 21 September 2026 against the installed BIM Engine **0.3.0** package
in Revit 2024. Build: .NET Framework 4.8, x64; zero compiler warnings/errors.

## Delivered

- A WPF dockable pane, registered by pyRevit startup, opened by Issue Report.
- Level → category-pair grouping, combined level/type/search filters, count and
  scan scope/coverage summary. Selection opens element/model details and notes.
- A pan/zoom top-down bounds schematic with two element colors and clash marker.
- Show 2D creates/reuses a dedicated floor plan with a clash-height view range,
  location marker, and focused zoom. Show 3D reuses a section-box view with an
  adjustable context radius. Host overrides are cleared between selections;
  linked selection uses element references through the correct link instance.
- Refresh repeats the last saved project scan scope. Complete scans mark absent
  clashes Resolved and remove them from the active list while retaining notes
  and history. Partial scans keep absent issues active and display a warning.
  Cancellation/failure before persistence does not save a replacement scan.
- Modeless Revit calls use a compiled ExternalEvent handler. Project switching
  clears and reloads project-specific data. No schema migration was required.

## Evidence

- [Offline tests](verification/phase2-python.txt): **30 passed**, including
  dashboard serialization, bounds/link identity, level fallback, type ordering,
  resolution/reopening with notes retained, partial scans and scope isolation.
- Spatial harness: 1,000 randomized queries agree with brute force; repeated
  linked instances remain distinct. Existing geometry algorithms were preserved.
- [Revit integration results](verification/dashboard-result.json): **29 passed**; live startup,
  production Run Scan and Issue Report entry points, filters, navigation,
  linked references, resolved issue history, modeless button events, project
  switching, link unload/partial refresh and recovery all passed.
- [Package verification](verification/phase2-package-check.json): all 25 installed
  package files match the build manifest. The tested DLL matches the installed
  SHA-256: `0e17bf781771dc6af6ed33b8f15bd25cca4684122ac477389f0508c275257b70`.
- Actual WPF control renders were inspected at
  [460 px](verification/dashboard-18db8449/dashboard-460.png) and
  [900 px](verification/dashboard-18db8449/dashboard-900.png). The initial clipped
  preview was corrected by allocating more inspector height and scrolling details
  separately. These are WPF renders, not desktop screenshots.

Tests created disposable host/link/second-project files and isolated SQLite/config
files under `verification/dashboard-18db8449`. The user's active project was not
edited, closed, or rescanned. Revit's standard runner auto-exits too early for
modeless tests; `tests/run-dashboard-verification.ps1` removes Quit from only its
own generated journal so external events can finish. A test-only external-event
adapter performs project switching/link loading in valid API contexts.

## Installation and use

Installed at `%APPDATA%/pyRevit/Extensions/BIMEngine.extension`.
The final installation and its immediate rollback backup are recorded in
[installation.json](verification/installation.json). The pre-Phase-2 package is
preserved at `%APPDATA%/pyRevit/BIMEngine-backups/BIMEngine-20260921-103509-d84187`.

**Restart Revit** to replace its already-loaded engine DLL. Then open a saved
project and choose **BIMEngine → ModelScanner → Issue Report**. Use **Refresh /
Rescan** to update the previous scan scope and remove solved clashes. Use Settings
and Run Scan when changing the scan scope. Older scopes are not resolved by a
different/narrower scope.

## Verification limits

The controlled fixtures are not a performance benchmark or a certification of
every model/family. Native docking registration, visibility and reopening were
tested; manual title-bar dragging/floating and mouse pan gestures were not
automated. Desktop screenshot capture was unavailable in this session, so layout
verification used the actual WPF controls rendered inside Revit. Existing Phase 1
geometry coverage limitations (including nested/mirrored Revit links) remain.
The schematic shows projected bounding boxes; Show 2D supplies real Revit context.
