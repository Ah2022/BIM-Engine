"""Validated per-user configuration, shared by all buttons."""
import copy
import json
import math
import os
import tempfile
import warnings

USER_CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "pyRevit", "BIMEngine")
USER_CONFIG_PATH = os.path.join(USER_CONFIG_DIR, "scan_config.json")
ISSUE_DB_PATH = os.path.join(USER_CONFIG_DIR, "bimengine_issues.db")
ALL_CATEGORIES = ["Pipes", "Ducts", "Cable Trays", "Structural Framing", "Structural Columns",
                  "Duct Terminals", "Air Terminals", "Pipe Accessories"]
DEFAULT_CONFIG = {
    "Categories": ALL_CATEGORIES[:5], "IncludeLinkedDocuments": True,
    "OctreeMaxObjectsPerNode": 16, "OctreeMaxDepth": 8, "CandidateQueryPaddingFeet": .01
}

def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError("Scan configuration must be a JSON object.")
    result = copy.deepcopy(DEFAULT_CONFIG)
    result.update(data)
    categories = result["Categories"]
    if not isinstance(categories, list) or not categories or any(c not in ALL_CATEGORIES for c in categories):
        raise ValueError("Choose at least one supported category.")
    result["Categories"] = list(dict.fromkeys(categories))
    if type(result["IncludeLinkedDocuments"]) is not bool:
        raise ValueError("IncludeLinkedDocuments must be true or false.")
    for key, upper in (("OctreeMaxObjectsPerNode", 4096), ("OctreeMaxDepth", 16)):
        if type(result[key]) is not int or not 1 <= result[key] <= upper:
            raise ValueError("{} must be an integer between 1 and {}.".format(key, upper))
    padding = result["CandidateQueryPaddingFeet"]
    if type(padding) not in (int, float) or not math.isfinite(padding) or not 0 <= padding <= 1:
        raise ValueError("CandidateQueryPaddingFeet must be between 0 and 1 feet.")
    return result

def load_config():
    if not os.path.isfile(USER_CONFIG_PATH):
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(USER_CONFIG_PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except json.JSONDecodeError:
        warnings.warn("Invalid scan_config.json; using defaults. Open Settings to save a valid configuration.")
        return copy.deepcopy(DEFAULT_CONFIG)
    return validate_config(data)

def save_config(data):
    data = validate_config(data)
    os.makedirs(USER_CONFIG_DIR, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="scan-", suffix=".json", dir=USER_CONFIG_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
        os.replace(path, USER_CONFIG_PATH)
    finally:
        if os.path.exists(path):
            os.remove(path)

def ensure_database_dir():
    path = os.environ.get("BIMENGINE_DB_PATH", ISSUE_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    return path

