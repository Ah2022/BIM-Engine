# BIM Engine 0.3 — Revit 2024 clash dashboard

This pyRevit extension scans selected host and loaded linked-model categories for
positive-volume solid intersections. It uses CPython for configuration and SQLite,
a compiled .NET Framework 4.8 library for Revit geometry, and a WPF dockable dashboard.

Phase 2.1 adds system-specific clash labels (for example Soil Pipe vs Waste Pipe),
geometry previews for 2D, 3D and sections, four camera corners, explicit view pinning,
and cleanup of selected generated views. See [PHASE2_1_VERIFICATION.md](../PHASE2_1_VERIFICATION.md).

The supplied baseline's compile, DLL-loading, CPython UI, linked identity and
persistence defects have been fixed. See [VERIFICATION.md](../VERIFICATION.md) for
the executed checks and their limits. The original assessment remains in
[PYREVIT_IMPLEMENTATION_PLAN.md](../PYREVIT_IMPLEMENTATION_PLAN.md).

## Build and install

Requirements: Revit 2024, pyRevit with CPython 3, .NET SDK with net48 build support.
This package is restricted to Revit 2024; Revit 2025 requires a separate .NET 8 build.

From this directory in PowerShell:

```powershell
./build.ps1
./install.ps1
```

Build creates `BIMEngine.extension/bin/BIMEngine.Core.dll` and a SHA-256 manifest
covering all package files. Install validates the manifest, stages the new package,
and moves an existing extension to a timestamped backup under
`%APPDATA%/pyRevit/BIMEngine-backups` before installing.

Restart Revit after replacing a loaded C# library. The tab is **BIMEngine** and
the panel is **ModelScanner**. No separate .addin manifest, RevitAPI redistribution,
System.Data.SQLite DLL or native SQLite interop package is needed.

To roll back, close Revit, move the current extension outside the Extensions folder
and restore the recorded backup as `BIMEngine.extension`. The installer writes the
exact backup path to `verification/installation.json`.

## Use

1. Open and save a Revit project.
2. **Scan**, **Settings**, and **Issue Report** open the same dashboard. Choose
   category chips and **Include links** in the top Scan panel, then press **Scan**.
   Progress appears inline. The model stays read-only while scanning; results are
   saved after completion. Scope starts with the project's last scan, or user
   defaults for a project with no scan. Advanced engine settings remain in JSON.
3. The summary shows active clashes and the latest scan's new/resolved counts.
   **Details** expands scope, raw statistics, and coverage diagnostics. Older scans
   without change counts show a dash. New counts mean first-seen issues; reopened
   issues count as active. Filters affect the list, never scan scope.
4. Selecting a row automatically previews its geometry in **3D**. Use **2D** and
   **Section** tabs above the viewport to switch modes. A is teal, B orange, and
   overlap red. Wheel zooms; drag pans; **Fit Preview** resets.
5. The viewport gear contains rotation, section axis, nearby context, focus, and
   context distance. **Overlap size** is a volume-derived score in mm, not
   penetration depth. Internal-feet coordinates are in the clash-details tooltip.
6. With the clash list focused, **Up/Down** moves between rows, **Enter** opens 3D,
   and **Space** selects the elements in Revit. **Ctrl+F** focuses search, including
   in the floating dashboard. Shortcuts preserve text editing and control keys.
7. Previews leave the project unchanged. **Pin as view** creates a named native
   view. **Delete generated views** lets you choose tagged views to delete;
   active, sheet-placed, dependent-parent, and unrelated user views are protected.
8. Scan again to update results. Complete scans of the same scope mark absent
   clashes Resolved while preserving history and notes. Partial scans retain them.

### List and triage (Phase B)

The list is flat by default. Click column headings to sort, or choose **Group by**
Level, Pair (system/category pair type), or Status. A/B columns have category icons
and stable colours by system type; grey means Unassigned. Hover for full labels.

**Open** and **Reviewed** are shown when no status chip is selected. Selected status
chips combine; **New** and **MEP vs Structure** further narrow the list. Ignored and
Resolved chips retrieve saved history. Clear Filters restores the active list.
**New** means first detected in the latest scan, **Recurring** means previously
known (including reopened issues). Older scans without age tracking show Unknown.

**Most likely real** puts clashes with a named system first, then larger overlap.
This is a review order, not an additional geometry test. Overlap remains the
volume-derived size score. Largest overlap and Newest first are also available.

Select one clash for **Reviewed**, **Ignore**, **Add note**, or **Assign**. Notes
append to existing text; assignment appends `Assigned to: Name` and the latest
assignment is displayed in the list. Select a pair type using the Type filter,
then Ctrl/Shift+click multiple rows and use **Mark selected ignored**. Bulk ignore
requires one pair type and changes only the selected rows, in one transaction.
Status, notes and assignments persist across scans. These edits do not alter the
Revit model or send notifications. Changing rows closes an unsaved note editor.

### Layout and review flow (Phase C)

**Undock** opens a floating dashboard. At 1040 device-independent pixels of usable
content width, the list sits on the left and the review card/viewport on the right.
Narrower floating windows and docked panes use the stacked layout. The splitter
resizes the two panes; controls and details scroll within their available space,
while list and viewport sizes adapt proportionally to the window.

The **Now reviewing** card shows A versus B, host level, and system information.
Use its copy icon to copy both element IDs; the button has an accessible **Copy IDs**
name. **More details** retains family, document, classification and notes. Internal
coordinates remain in the card tooltip.

**Previous** and **Next** follow the currently filtered, sorted list and stop at its
ends. The position indicator counts only visible clashes. Navigation selects one
row, updates the card, and triggers its automatic 3D preview. The navigation bar
stays outside the scrollable details region.

The dashboard reads Revit's overall light/dark theme and listens for theme changes.
Backgrounds, text, controls, status badges, selections and system colours update
without reopening the pane. Geometry keeps its A/B/overlap semantic colours.

The header shows the last scan scope and coverage warnings. Results retained from
other saved scopes remain active until a complete scan of their own scope resolves
them. Filters affect presentation, never the rescan scope. Level grouping uses the
highest host level at/below the clash elevation; original element levels remain in
the details. Locations below all host levels are Unassigned and can use Show 3D.

Model changes invalidate the current preview. Refresh updates the clash list;
opening a preview also recalculates its geometry. The native Revit temporary-view
mode does not restore all crop/section-box changes in Revit 2024, so inspection
uses the in-memory dashboard viewport. Only explicit pinning changes the model.
Pinned linked-model views isolate link instances and overlay the exact clashing
subelements; native Revit isolation cannot isolate individual linked elements.
Nearby preview context is capped at 60 elements / approximately 150,000 triangles.
A notice identifies partial geometry/context; this is not a whole-model renderer.

Advanced settings are in `%APPDATA%/pyRevit/BIMEngine/scan_config.json`.
Supported values:

| Setting | Values |
| --- | --- |
| Categories | Nonempty list of supported labels shown in the Scan panel |
| IncludeLinkedDocuments | true / false |
| OctreeMaxObjectsPerNode | Integer 1–4096; default 16 |
| OctreeMaxDepth | Integer 1–16; default 8 |
| CandidateQueryPaddingFeet | 0–1 feet; default 0.01; candidate search only, not clearance checking |

The database lives at `%APPDATA%/pyRevit/BIMEngine/bimengine_issues.db`.
Tests can use `BIMENGINE_DB_PATH` to select an isolated database.

## Behavior and limits

- Host and repeated linked instances have separate scan identities, even when their
  Revit numeric IDs match. Persisted identities include project/document identity,
  link instance UniqueId and element UniqueId.
- All usable solids are collected recursively, including nested families.
- A candidate element's geometry is fetched once per scan, including empty results.
- Multiple solid intersections produce one issue per element pair.
- **Overlap size** is cube root of the largest solid-pair intersection volume,
  converted to millimetres for display. It is not penetration depth.
- Boolean failures, missing geometry, unloaded links, mirrored link geometry and
  nested Revit links produce incomplete-coverage diagnostics. Mirrored links and
  nested Revit links are not fully supported in this release. Nested family
  instances are supported.
- Repeat scans update issues and snapshots without duplicating them. Notes and
  reviewed/ignored states survive. A resolved issue that recurs reopens.
- Only complete scans of exactly the same configuration scope automatically resolve
  unseen issues. Partial scans and different category/link scopes do not.
- A report with no records means no issues are recorded in the saved scan scopes;
  it does not certify the entire model.
- Scanning runs on Revit's API thread. The progress window uses a separate UI thread,
  but collection/booleans are not background Revit API operations. Individual Revit
  geometry operations cannot be interrupted midway.
- Project identity includes path; Save As to a different path starts a separate
  project history. Unsaved projects must be saved before scanning.
- BCF export, clearance checks, AI, calculations and advanced rule filters remain
  future features. They are not implemented by this release.

## Database upgrade

Schema version 3 adds system metadata in place, retaining v2 issues, notes and states.
A `.pre-v3-*.bak` SQLite backup is created before the upgrade.
Schema version 2 added project-scoped issue identity and scan records. Before
upgrading an older database, the application makes a SQLite backup beside it.
Original tables are retained as `Legacy_*`, including notes and statuses.
Old records lack trustworthy project identity, so they are not assigned to a
project automatically or mixed into new reports. Run a new scan for v2 results;
historical records remain available in the backup and legacy tables.

## Architecture

```text
pyRevit CPython buttons
  -> Python config / bridge / rules / SQLite
  -> BIMEngine.Core.dll
       collection -> octree -> distinct pairs -> cached solids -> intersections
       .NET category/progress dialogs + WPF dockable dashboard
       ExternalEvent navigation and refresh coordinator
  -> plain Python records -> transactional persistence
```

The Python package imports without CLR outside Revit. The bridge loads the engine;
UI helpers call compiled controls. Extension startup registers the pane; the
compiled coordinator retains a Python snapshot/rescan delegate. Revit actions
from the modeless pane execute through ExternalEvent. Idling detects project
changes and clears/reloads project-scoped snapshots.
The spatial source has no Autodesk dependency.

## Tests

```powershell
python -m unittest discover -s tests -v
dotnet run --project tests/SpatialHarness/SpatialHarness.csproj -c Release
pyrevit run tests/revit_integration.py --revit=2024
pyrevit run tests/revit_extended.py --revit=2024
pyrevit run tests/revit_nested.py --revit=2024
dotnet build tests/DashboardHarness/DashboardHarness.csproj -c Release
./tests/run-dashboard-verification.ps1 -ScriptPath "$PWD/tests/revit_inspection.py"
```

Revit fixture scripts currently identify this workspace with their `ROOT` constant;
adjust it if moving the repository. The UI smoke test can pause at Revit's
**Journal Error / Enter interactive mode** prompt because the runner is replaying
a journal while testing modal dialogs. Continue only the isolated test session.
The final verification run completed after dismissing that journal prompt.

The dashboard runner removes the automatic Quit line from its own generated
pyRevit test journal so modeless external events can complete. It leaves its
isolated Revit session open for inspection. Results are written to
`verification/inspection-result.json`; wait for `status: passed` (or `failed`).
Set `BIMENGINE_EXTENSION_PATH` to the installed extension to verify deployment.
Use absolute script paths with the pyRevit CLI; relative paths can fail silently.

Tests create new fixture projects and databases under `verification`; they never
modify the user's existing project. UI confirmations are captured by a test shim;
category/progress/report controls and host selection use the production code.
