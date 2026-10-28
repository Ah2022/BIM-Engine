# -*- coding: utf-8 -*-
"""
BIM Engine Core (Python layer).

Sits between pyRevit's UI scripts and BIMEngine.Core.dll (C# geometry
pipeline). Handles:
  - revit_bridge.py: wrapper around the compiled ScanEngine, converts
    between Revit objects and serializable dicts
  - database.py: SQLite persistence (standalone bimengine_issues.db)
  - rules.py: Rule Engine (filtering, deduplication, Phase 1 passthrough)
  - bcf.py: BCF Manager (schema-ready, not populated yet)
  - calc.py: Calculation Engine (schema-ready, not populated yet)

Public API:
  from bimengine_core import run_scan, get_open_issues, save_config, load_config
"""

from .revit_bridge import run_scan, scan_and_save
from .database import get_open_issues, get_issue_by_id, update_issue_status
from .config import save_config, load_config

__all__ = [
    "run_scan",
    "scan_and_save",
    "get_open_issues",
    "get_issue_by_id",
    "update_issue_status",
    "save_config",
    "load_config",
]
