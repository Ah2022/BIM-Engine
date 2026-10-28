# Phase B: list and triage

## Implemented

- Flat sortable grid; optional Level, Pair or Status grouping.
- Separate A/B columns with category glyphs, deterministic system colours and full-label tooltips.
- Status and age badges; level, discipline pair, numeric overlap size and assignee columns.
- New, Open, Reviewed, Ignored, Resolved and MEP vs Structure quick filters.
- Reviewed, Ignore, Add note and Assign actions for one clash, with an inline text editor.
- Ctrl/Shift multi-selection and atomic bulk ignore for selected clashes of one pair type.
- Default ranking: at least one named system first, then overlap size descending.

Triage is project-scoped and runs through the Revit external-event callback. It
writes the existing Status and Notes fields, with an audit entry. Notes append;
assignments append `Assigned to: Name`, and the last assignment is displayed.
No messages are sent and no Revit elements are modified by triage.

The default list contains Open/Reviewed. Explicit status chips combine with OR;
New and MEP vs Structure narrow the result. New means first detected in the latest
scan; reopened issues are Recurring. Legacy scans without per-issue age metadata
show Unknown until another scan. Scan audit JSON stores new IDs without a schema
migration. Ignored/Resolved history is now loaded for filtering; active summary
counts still include only Open/Reviewed.

## Checks

- Final Release net48/x64 build: zero warnings and errors.
- Offline Python suite: 44 passing tests, including age tracking, lifecycle,
  notes/assignment preservation, ignored/resolved retrieval, invalid edits and
  rollback of a cross-project bulk request.
- `tests/revit_phase_b.py` covers the real pane, optional grouping, numeric sorting,
  discipline filtering, keyboard navigation, previews, inline edits, bulk ignore,
  history filters and existing scan/pin/cleanup behavior in disposable models.
- Revit 2024: all 62 integration checks passed against the staged DLL.
- Live results, tested DLL hash and screenshots: `verification/phase-b-result.json`.

Package files are staged in the workspace. Installation into the user's pyRevit
extension directory is not performed; restart Revit after installing the new DLL.
