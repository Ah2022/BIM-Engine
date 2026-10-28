# Phase 2.1 verification — BIM Engine 0.3.1

Target: Autodesk Revit 2024, pyRevit CPython, .NET Framework 4.8.

## Implemented behavior

- Actual piping/HVAC system type names flow from collection through SQLite into labels, groups, filters and details. System classification, name and family/type are separate metadata. Connector systems are considered for MEP families; multiple systems and unassigned systems have explicit labels.
- Schema 3 upgrades schema 2 in place with a SQLite backup, retaining identities, statuses and notes.
- Read-only geometry previews provide top view, four 3D corners, and a section perpendicular to either element. Framing uses transformed element bounds, with optional clash focus and bounded nearby context.
- The exact boolean intersection is red. The dashboard 3D preview uses an x-ray overlay so element surfaces cannot hide the overlap. No DirectShape or detail curve is created during preview.
- Explicit pinning creates a named native plan/3D/section, fitted crop/section box, isolation, halftone context and saved camera. Optional plan/section annotation stores a projected overlap extent, clearly labelled as a snapshot.
- DirectContext3D draws transient selected-element and overlap meshes in pinned native views and regenerates them on activation. Only a small ownership/clash metadata record is persisted.
- Cleanup lists current and legacy BIM Engine views and deletes only selected owned views. Active views, sheet-placed views and views with dependent views are protected. Deletion dependencies are probed in a rolled-back subtransaction before actual deletion.
- Model changes invalidate previews. Refresh keeps the existing complete-scan/partial-scan resolution rules and preserves notes.

## Revit API probe and design decision

`verification/preview-probe.json` records the native Revit 2024 probe. Temporary View Properties did not restore the tested crop and section-box changes, and the document remained modified after ending temporary mode. A rolled-back model solid would also disappear when the transaction ends.

Consequently normal inspection uses the approved in-memory dashboard fallback. Native Revit view creation and permanent isolation happen only through **Pin as view**. Transient overlap rendering uses in-memory geometry, not an uncommitted or rolled-back model element.

## Validation

- Release build: zero warnings and errors.
- Python offline suite: 34 passing tests, including schema migration and system rename persistence.
- Spatial/geometry harness: 1,000 randomized spatial queries plus 500 camera/section-axis trials including vertical axes, framing and clipping checks.
- Live Revit acceptance fixture: `tests/revit_inspection.py`. Results and rendered previews are recorded under `verification/inspection-*`; the latest report is `verification/inspection-result.json`.
- Rendered dashboard, top, 3D and section previews are inspected visually. Red overlap visibility was corrected during validation.

## Limits

The live fixture uses actual crossing Soil/Waste pipes, structural context and repeated translated links. It is not certification of every family, very large production model, or GPU configuration. Mirrored and nested Revit links retain the scanner's existing limitations. Complex boolean failures show an incomplete-overlay notice. Nearby context is bounded for responsiveness.

Native Revit isolation works at link-instance granularity; exact linked subelements are distinguished using transient meshes. Pinned views persist, but the red solid requires this add-in to render and is not exported as permanent model geometry. Optional saved annotations describe overlap extent at pin time and do not update automatically.

All live tests use new disposable models and isolated databases. The user's existing Revit project is not used for testing. Restart Revit after installation, then Refresh / Rescan to populate system metadata for existing records.

## Installed-package acceptance — 22 September 2026

Version 0.3.1 passed all 34 live Revit assertions from the installed extension. The transient graphics server rendered 4 times without an error. The preview checks confirmed no increase in element/view count and no document modification. All 25 installed package files matched their SHA-256 manifest.

- Installed results: [inspection-installed-passed.json](verification/inspection-installed-passed.json)
- Workspace results: [inspection-workspace-passed.json](verification/inspection-workspace-passed.json)
- Hash verification: [inspection-installed-hashes.json](verification/inspection-installed-hashes.json)
- Rendered dashboard: [dashboard.png](verification/inspection-4514bb5f/dashboard.png)
- Rendered overlap: [preview-3d.png](verification/inspection-4514bb5f/preview-3d.png)
- Previous extension backup: C:\Users\TK56\AppData\Roaming\pyRevit\BIMEngine-backups\BIMEngine-20260922-090539-a09a46
- Tested DLL SHA-256: cac0cb419361a298ddd2835c1b65aceb9fa8f0173cc0987361005bbf6e76c17e

The installed acceptance run also exercised the actual Show 3D, Show Section and Refresh / Rescan button event handlers after the ribbon command returned, tested active/unrelated/sheet/dependent-view cleanup protection, and verified unloaded-link recovery and note preservation after system rename and clash resolution.
