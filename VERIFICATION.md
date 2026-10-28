# BIM Engine 0.2.0 verification

Date: 20 September 2026. Target: Revit 2024, build 24.0.4.427; pyRevit
6.4.0.26100+0515; actual in-Revit Python runtime: CPython 3.12.3.

## Result

The implemented scanner, persistence layer and three button entry points passed
the checks below inside real Revit 2024. The extension is installed at
`C:/Users/TK56/AppData/Roaming/pyRevit/Extensions/BIMEngine.extension`.
Restart the user's normal Revit session to replace any already loaded old DLL.
The user's existing model was not edited or closed by the tests.

## Executed checks

| Layer | Result | Evidence |
| --- | --- | --- |
| Release x64/net48 build against Revit 2024 | Pass, zero warnings/errors | [build log](verification/build-fixed.txt) |
| Offline Python acceptance tests | 23 passed | [Python log](verification/python-fixed.txt) |
| Spatial index | 1,000 seeded randomized queries matched brute force; boundary/empty tree/count checks passed | [spatial log](verification/spatial-fixed.txt) |
| Host plus repeated linked-instance identities | Distinct candidate pairs with identical numeric Revit IDs | Same spatial log |
| Real Revit core fixture | 12 passed | [core results](verification/latest-revit-result.json) |
| Real Revit rotated/mirrored/unloaded links | 5 passed | [link results](verification/revit-extended-result.json) |
| Real Revit nested family geometry | 2 passed | [nested results](verification/revit-nested-result.json) |
| Real Revit button entry points / controls | 4 passed | [UI results](verification/revit-ui-result.json) |
| Deployed files match build manifest | 23 files checked, zero mismatches | [installed hashes](verification/installed-hashes.json) |

The 12 core checks cover disjoint and touching solids, known overlap volume and
centroid, secondary-solid clashes, bounding-box false positives, diagnostics,
geometry-cache counts, duplicate-free rescans, repeated linked instances,
serialization, cancellation without persistence, and identity after reopening.
The link fixture verifies rotated host coordinates, explicit mirrored/unloaded
coverage diagnostics, and preservation of existing issues during partial scans.
The nested fixture verifies a secondary solid through two nested family instances
and confirms that transforms are applied once.

The UI fixture opened the real category dialog, used the real progress window,
ran the production Run Scan script, displayed the real report grid with four
issues, and tested host-element selection from a report row. The final test sorts
the grid first and compares the exact selected IDs with the chosen row. Confirmation
message boxes were captured by a test shim. Revit's journal playback paused at
the modal category dialog; the journal warning was dismissed in the isolated
test session before the fixture completed. The test timer retried the disabled
Save button while that warning was present; this accounts for repeated dialog
actions in the raw log. This was a runner/journal limitation, not a failed scan.
The final core and UI results record the installed extension path and DLL SHA-256,
so their evidence can be matched to the deployed package manifest.

## Fixes that live testing caught

Offline compilation was not treated as proof of runtime compatibility. The first
live test exposed pythonnet's refusal to initialize `List[String]` from a Python
list, so the bridge now explicitly adds each category. A button test exposed an
exception importing this installation's `pyrevit.script` output machinery under
CPython. The buttons now use the compiled .NET dialogs and grid without importing
that module or unsupported `pyrevit.forms` helpers.

## Deployment and rollback

The installer validates every package file before staging, preserves the previous
extension outside pyRevit's extension discovery folder, and writes the install
location and exact backup path to [installation.json](verification/installation.json).
The original pre-fix extension backup is recorded separately in
[installation-initial.json](verification/installation-initial.json).
The installed package includes no .NET/native SQLite dependencies or Revit API DLLs.

Existing legacy databases are not modified until used by the new extension. At
that point the migration makes a SQLite backup and preserves original tables as
`Legacy_*`. Historical records cannot safely be assigned to a host project from
their old document-title-only identity, so the new project reports require a new
scan. Notes and historical rows remain in the backup and legacy tables.

## Limits of the verification

- These are controlled fixtures, not an exhaustive certification of every family,
  model or Revit boolean-kernel case. The Level column depends on available family
  parameters; an unresolved level is shown as `Unknown`.
- Mirrored link geometry and nested Revit links explicitly produce partial coverage.
  Nested family geometry was tested successfully.
- No forced degenerate-solid boolean exception or production-size performance
  benchmark was executed. Exception paths report indeterminate coverage in code;
  real scan timings from the small fixtures are included in the core JSON results.
- Revit 2025 and other releases are intentionally unsupported by this build.
- The user's ongoing Revit process was not restarted, so its ribbon may still use
  the previously loaded extension until restart. Tests used separate Revit sessions.
- BCF, clearance checking and advanced rule/AI engines remain outside Phase 1.

The detailed reproduction commands are in [README.md](README.md).

Final machine-readable summary: [summary.json](verification/summary.json).
Final installed DLL SHA-256:
`F6B1D2635C4E69ADDC21149D4FDCD435162AA4382457E1272F54B87826CDCC54`.
The core and sorted-report UI checks both ran against that installed binary.
