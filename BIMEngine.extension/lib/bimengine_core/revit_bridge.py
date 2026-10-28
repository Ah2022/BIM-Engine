"""The only Python module that loads the compiled Revit engine."""
import os
import time
from .config import load_config, validate_config

def _load_bimengine_dll():
    import clr
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "bin", "BIMEngine.Core.dll")
    if not os.path.isfile(path):
        raise IOError("Build the Revit 2024 package first. Missing: " + path)
    clr.AddReference(path)
    return path

def validate_document(doc):
    if doc is None or doc.IsFamilyDocument:
        raise ValueError("Open a Revit project document first.")
    if str(doc.Application.VersionNumber) != "2024":
        raise ValueError("This BIM Engine package supports Revit 2024 only.")
    if not str(doc.PathName):
        raise ValueError("Save the project before scanning so its results have a stable project identity.")

def document_key(doc):
    validate_document(doc)
    _load_bimengine_dll()
    from BIMEngine.Core import DocumentIdentity
    return str(DocumentIdentity.Get(doc))

def _build_net_config(data):
    from BIMEngine.Core.Models import ScanConfig
    from System.Collections.Generic import List
    from System import String
    cfg = ScanConfig()
    cfg.Categories = List[String]()
    for category in data["Categories"]:
        cfg.Categories.Add(category)
    for key in ("IncludeLinkedDocuments", "OctreeMaxObjectsPerNode", "OctreeMaxDepth", "CandidateQueryPaddingFeet"):
        setattr(cfg, key, data[key])
    return cfg

def _element_to_dict(el):
    if el is None:
        return None
    result = dict(element_id=int(el.ElementId), category=str(el.Category),
        document_title=str(el.DocumentTitle), document_key=str(getattr(el, "DocumentKey", "") or ""),
        element_unique_id=str(getattr(el, "ElementUniqueId", "") or ""),
        is_linked=bool(el.IsFromLinkedDocument),
        linked_ref_id=str(getattr(el, "LinkedDocumentReferenceId", "") or ""),
        location_x=float(el.LocationX), location_y=float(el.LocationY), location_z=float(el.LocationZ),
        level_name=str(el.LevelName), level_id=int(getattr(el, "LevelId", -1)),
        system_type=str(getattr(el, 'SystemType', '') or ''),
        system_classification=str(getattr(el, 'SystemClassification', '') or ''),
        system_name=str(getattr(el, 'SystemName', '') or ''),
        family_type=str(getattr(el, 'FamilyType', '') or ''))
    if hasattr(el, "Bounds"):
        for kind in ("Min", "Max"):
            for axis in "XYZ":
                result["bounds_{}_{}".format(kind.lower(), axis.lower())] = float(getattr(el.Bounds, kind+axis))
    return result

def _issue_to_dict(issue):
    return dict(engine_source=str(issue.EngineSource), issue_type=str(issue.IssueType),
        element_a=_element_to_dict(issue.ElementA), element_b=_element_to_dict(issue.ElementB),
        overlap_depth_feet=float(issue.OverlapDepthFeet), location_x=float(issue.LocationX),
        location_y=float(issue.LocationY), location_z=float(issue.LocationZ),
        status=str(issue.Status.ToString()), detected_utc=str(issue.DetectedUtc.ToString("o")))

def run_scan(doc, config_dict=None, progress_callback=None):
    validate_document(doc)
    data = validate_config(config_dict if config_dict is not None else load_config())
    _load_bimengine_dll()
    from BIMEngine.Core import ScanEngine, ScanProgress
    callback = ScanProgress(progress_callback) if progress_callback else None
    result = ScanEngine(_build_net_config(data)).RunScan(doc, callback)
    started = time.perf_counter()
    response = dict(elements_collected=int(result.ElementsCollected),
        candidate_pairs_evaluated=int(result.CandidatePairsEvaluated),
        unique_geometry_fetches=int(result.UniqueGeometryFetches),
        issues=[_issue_to_dict(i) for i in result.Issues],
        elements=[_element_to_dict(e) for e in result.Elements],
        elapsed_seconds=float(result.Elapsed.TotalSeconds),
        diagnostics=[str(d) for d in result.Diagnostics], project_key=document_key(doc),
        config=data, timings={str(k): float(result.Timings[k]) for k in result.Timings.Keys})
    response["timings"]["conversion"] = time.perf_counter() - started
    return response

def scan_and_save(doc, config_dict=None, progress_callback=None):
    from .database import save_scan_results
    from .rules import filter_issues
    started = time.perf_counter()
    result = run_scan(doc, config_dict, progress_callback)
    result["issues"] = filter_issues(result["issues"], result["config"])
    before = time.perf_counter()
    result["scan_id"] = save_scan_results(result["issues"], result["elements_collected"],
        result["elapsed_seconds"], project_key=result["project_key"], config=result["config"],
        diagnostics=result["diagnostics"], elements=result["elements"],
        metrics=dict(candidate_pairs=result["candidate_pairs_evaluated"], geometry_fetches=result["unique_geometry_fetches"]))
    result["timings"]["persistence"] = time.perf_counter() - before
    result["total_seconds"] = time.perf_counter() - started
    return result

