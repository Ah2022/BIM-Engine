# BIM Engine: analysis, test results and pyRevit implementation plan

Assessment date: 20 September 2026. Target for the first release: Revit 2024.

**Implementation update:** The findings below describe the original baseline.
The fixes have now been implemented and deployed as 0.2.0. See
[VERIFICATION.md](VERIFICATION.md) for the current results and remaining limits,
and [README.md](README.md) for installation and use.

## Verdict

The supplied add-in is **not ready to deploy or claim as working**. It already has
a pyRevit extension structure, but its C# library does not compile and its Python
UI uses functions unsupported by the selected engine. The spatial index passed
offline checks; several persistence and integration acceptance checks failed.

This assessment adds tests and evidence without changing the application code or
installing the extension into the user's pyRevit profile. A successful end-to-end
Revit scan has not been performed. The build and runtime blockers below prevent
that verification of the supplied version.

## What the README describes versus what the code does

The intended flow is sound: pyRevit buttons -> Python configuration/coordination ->
C# collection and geometry -> plain Python records -> rules -> SQLite -> report.
The expensive Revit API calls remain on Revit's API thread. A compiled library
does not make them asynchronous or guarantee an unblocked UI.

- Three buttons already exist: Settings, Run Scan and Issue Report.
- ScanEngine collects selected host and loaded linked categories, builds an octree,
  narrows pairs and checks solid intersections. It returns .NET objects; the bridge
  converts them to Python dictionaries.
- RunScan's UI script, rather than the public Python `run_scan` function, applies
  rules and saves results. Calling the public function alone does not persist.
- SQLite creates eight application tables. Basic storage, status updates and
  rollback work in offline tests.
- Rules are passthrough. BCF, calculations, AI and RFI features are placeholders.
  No clearance checking is implemented, despite extension.json mentioning it.
- Only the first positive-volume solid is tested for each element. This is not
  complete clash coverage for multi-solid or deeply nested families.
- The displayed overlap is cube root of intersection volume, not penetration depth.
- The report does not display the Level column mentioned in the README.
- The README's absence-of-toolchain statement does not apply to this machine.
  Revit API assemblies, .NET SDK and pyRevit are installed here.

## Executed verification

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Build against installed Revit 2024 API, Release x64/net48 | FAIL: 4 CS0104 errors | `verification/build-baseline.txt` |
| Python baseline acceptance suite | 11 tests: 6 pass, 4 assertion failures, 1 loader error | `verification/python-baseline.txt` |
| Real C# octree source, 500 entries, 1,000 seeded randomized queries | PASS: exact agreement with brute force | `verification/spatial-baseline.txt` |
| Empty tree, retained entry count, touching AABBs, candidate self exclusion | PASS | Same spatial harness |
| Host/link ID collision | Reproduced duplicate-key exception using ScanEngine's lookup expression | Same spatial harness; no live Revit geometry |
| Installed CPython forms backend | Source confirms unsupported ProgressBar and SelectFromList stubs | Local pyRevit `_cpy.py` |
| Real Revit solid booleans, link transforms and complete button flow | NOT RUN | Blocked by baseline build/UI defects |
| Model-scale speed and responsiveness | NOT MEASURED | Requires a defined Revit fixture and benchmark model |

The Python suite uses a temporary database, a synthetic package wrapper to bypass
the eager CLR import, and a stub CLR only for loader/serialization tests. It does
not establish actual pythonnet or pyRevit compatibility. Initial sandbox temporary
file failures were resolved by an approved rerun; the retained log is the final
run, after correcting test-harness connection cleanup.

Installed environment: .NET SDK 8.0.420; Revit 2024 API 24.0.4.427; pyRevit CLI
6.4.0.26100+0515; configured CPython engine 3123. pyRevit reports attachments for
Revit 2020-2025 and a running Revit 2024 instance. This is not proof the new
extension is loaded. Restore succeeded but NuGet vulnerability metadata could
not be retrieved (NU1900); the build failure itself is from C# source errors.

## Findings in implementation order

| Priority | Finding | Required change |
| --- | --- | --- |
| P0 | `SpatialElement` conflicts with Autodesk's class in ElementCollector and SolidCache; ScanEngine also imports both namespaces | Alias or rename the internal DTO consistently, rebuild to discover any further errors |
| P0 | All buttons use `#! python3`; RunScan uses forms.ProgressBar and Settings uses forms.SelectFromList, both unsupported in the installed CPython backend | Keep CPython for stdlib SQLite and replace UI calls with a tested CPython-compatible .NET UI; do not simply remove the shebang and assume SQLite works in IronPython |
| P0 | Bridge loader never checks the documented extension/bin location | Resolve extension root once, load the absolute DLL path, centralize DLL loading and remove obsolete SQLite DLL advice |
| P0 | Scan lookup, octree keys, deduplication and solid cache use only numeric ElementId | Carry a distinct scan identity for every host/link-instance element through every stage; repeated instances of one link must stay distinct |
| P1 | Bridge drops LinkedDocumentReferenceId; database expects `linked_ref_id` | Serialize complete element identity, bounds and levels, including both sides of each issue |
| P1 | Model identity is document title; different projects with the same title can merge | Define stable project/document identity and link-instance context; persist element UniqueId plus numeric ID for navigation |
| P1 | Every scan inserts new issues; existing element rows never refresh | Add canonical pair keys, scan records, migrations, transactional upserts and scope-aware lifecycle rules |
| P1 | Report reads every project's issues and linkifies all IDs in the active host | Scope by active project/scan; show both documents and link instances; only create navigation links proven to address the right model |
| P1 | Empty report claims the model is clean even with no recorded scan | Distinguish never scanned, completed scan with no findings, partial/failed scan and historical results |
| P1 | First-solid-only extraction and one nesting level can miss clashes | Cache all valid solids recursively, apply correct transforms and evaluate solid pairs; collapse results to one element-pair issue |
| P1 | Boolean InvalidOperationException becomes 'no clash' | Record an indeterminate result and diagnostic; never certify a clean scan when checks failed |
| P2 | Two config implementations diverge; shallow defaults share the category list | Single validated config module, deep-copy defaults, atomic saves and useful errors for invalid values |
| P2 | User cancellation is checked only at coarse stages and per candidate, persistence has no UI error handling | Add cancellation checkpoints and a clear result state; persist only completed scans; handle locked/read-only database errors |
| P2 | Geometry-fetch/pair ratio is described as proof of caching | Assert fetches equal distinct requested element identities, including cached nulls; one pair legitimately requires two fetches |
| P2 | Revit 2024 IDs are read using IntegerValue | Use the 64-bit Value property consistently for a 2024-only target and test large IDs |

The checked-in failing tests assert intended acceptance behavior. They should
become passing tests as these fixes are implemented, not be suppressed.

## Implementation milestones and gates

### 1. Establish a runnable Revit 2024 package

Fix namespace ambiguity, build against Revit 2024, and emit the resulting DLL
to a versioned staging package. Keep net48 for this first target. Add a Revit
version guard so pyRevit attachments to other Revit releases cannot accidentally
load it. Revit 2025 needs a separate .NET 8 build and its own verification.

Keep the existing CPython architecture. Use a small compatible WinForms/.NET UI
for category selection, progress and alerts, with Revit's window as owner. Prove
it in the installed engine before expanding the UI. Explicitly wrap the callback
in the ScanProgress delegate if required by the installed pythonnet version.
Keep API calls on the Revit API thread and avoid arbitrary reentrant event pumps.

Centralize config and DLL path helpers; make CLR imports lazy so database/config
can be imported offline. Correct the explicit script lib paths (currently four
parent hops point above the extension; three reach the extension root), or rely
on pyRevit's managed lib path. Validate project-document context before scanning.

Gate: clean compiler result; DLL loaded in Revit 2024; Settings opens and roundtrips
selected categories; callbacks work; unsupported Revit versions stop clearly.

### 2. Correct identity and geometry

Assign unique per-scan keys or a composite identity including document and link
instance, separate from the actual Revit ElementId. Use the same identity in
spatial entries, lookups, self-exclusion, pair deduplication and caches. Serialize
stable identities for persistence rather than persisting transient scan keys.

Cache all valid solids per identity, including empty results. Traverse nested
instances, verify transform composition and dispose owned transient geometry.
Track unsupported geometry and boolean failures separately from negative checks.
Define minimum intersection volume and display units explicitly.

Gate: host versus link with overlapping numeric IDs, two instances of one linked
model, transformed links, nested families and secondary-solid-only clashes all
produce the expected identities and findings.

### 3. Make issues persistent and trustworthy

Introduce schema versioning and a backed-up migration. Add scan identity, project
scope, start/completion state, configuration scope and diagnostics. Use stable,
ordered element-pair keys to update recurring issues without losing notes or
review status. Refresh snapshots on every completed observation.

Distinguish absence in a completed scan from absence in an incomplete scan. Only
resolve unseen issues when their elements/categories/link scope were actually
covered; cancelled scans, unloaded links and narrower category selections must
not auto-resolve unrelated issues. Define reopening behavior for resolved clashes.

Gate: repeat/reversed-pair scans do not duplicate; unrelated projects stay separate;
failed batches roll back; status/notes survive; moving an element refreshes its
snapshot; cancellation does not publish a completed scan.

### 4. Finish UI and deployment

Report both element identities, document/link context, levels, scan time and
diagnostics. Label the volume-derived metric accurately. Provide safe host
selection and tested linked-element navigation, or plain text when unavailable.
Expose current scope and progress without implying that zero findings proves
the whole model is clash-free.

Create a repeatable build/package script, an install procedure with rollback and
a package version/hash manifest. Stage and inspect the package before copying to
`%APPDATA%/pyRevit/Extensions`. No RevitAPI DLLs should be shipped. No SQLite .NET
DLLs are needed for the chosen CPython sqlite3 route. Restart Revit after changing
a loaded C# DLL; a pyRevit reload alone is not a dependable assembly replacement.

Gate: a clean Revit session loads all three buttons, settings and database survive
restart, and failed loads/storage produce actionable messages.

### 5. Verify inside Revit before release

Use a dedicated disposable test project with recorded element identities and
known geometry. Keep its issue database separate from real project data. Record
Revit/pyRevit/engine versions, DLL hash, input configuration, actual result and
expected result for every case below.

| Fixture / action | Required result |
| --- | --- |
| Two disjoint selected solids | Zero clashes |
| Face-touching solids | Zero positive-volume clashes |
| Two boxes with known 1 ft³ overlap | One pair; volume-derived score 1 ft; expected centroid |
| Bounding boxes overlap but solids do not | Candidate exists, no clash |
| Clash only in a family's second solid | Detected |
| Nested family geometry | Correct clash and host-coordinate location |
| Host/link share numeric ID | No exception, identities remain distinct |
| Same linked model placed twice | Independent instance results |
| Translated, rotated and mirrored links | Correct transformed geometry, or explicit unsupported diagnostic |
| Unloaded link / element without usable solids | Explicit coverage diagnostic; no false clean claim |
| Forced boolean failure | Indeterminate check count, not silent negative |
| Repeated scan / reversed pair order | No duplicate issue, notes preserved |
| Move/fix element and rescan same complete scope | Refreshed snapshot and agreed issue lifecycle |
| Two projects with identical titles | No cross-project results or incorrect selection |
| Cancel during a large scan | Stops at supported checkpoint; no completed partial scan |
| No document / family document / unsupported Revit version | Clear guard message |
| Invalid config / locked database | Clear recoverable error |
| Revit restart and report navigation | Persisted results and correct target selection |

For performance, record collection, indexing, candidate generation, geometry,
Python conversion, persistence and total wall time separately on sparse and dense
models. Repeat at least three times and report the distribution, counts and memory.
Require one extraction per distinct requested identity. Compare octree recall with
all-pairs checks on a small fixture. Establish an acceptable runtime on the user's
representative model; no speed claim is justified by API-free namespaces alone.

Release gate: all offline acceptance tests pass, all required in-Revit cases have
recorded passing evidence, no unresolved P0/P1 findings, and agreed performance
criteria are met. Until then, status remains unverified for production use.

## Reproduce the offline checks

Run from the repository root with a working CPython 3 and .NET 8 SDK:

```powershell
python tests/test_baseline.py
dotnet run --project tests/SpatialHarness/SpatialHarness.csproj -c Release -p:NuGetAudit=false
dotnet build BIMEngine.Core/BIMEngine.Core.csproj -c Release -p:Platform=x64 -p:REVIT_API_PATH="C:/Program Files/Autodesk/Revit 2024"
```

The current Python tests intentionally return nonzero on the supplied defects.
The spatial harness returns success after its positive checks and its explicit
baseline collision reproduction; that reproduction must become a positive
identity regression test once identity handling is repaired. Its net8 build
validates API-free source logic, not the net48 Revit DLL or Autodesk geometry.

## Primary references

- [pyRevit CPython forms backend](https://docs.pyrevitlabs.io/reference/pyrevit/forms/_cpy/): unsupported UI stubs; verified against the installed source as well.
- [Autodesk Revit 2025 API changes](https://help.autodesk.com/view/RVT/2025/ENU/?caas=caas%2Fblog%2Fthebuildingcoder.typepad.com%2F2024%2F04%2Fwhats-new-in-the-revit-2025-api.html): .NET 8 rebuild requirement.
