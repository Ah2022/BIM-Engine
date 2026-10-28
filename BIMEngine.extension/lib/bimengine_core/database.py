"""Versioned SQLite storage. Each scan and issue belongs to one host project."""
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from .config import ensure_database_dir

SCHEMA_VERSION = 3

def _now():
    return datetime.now(timezone.utc).isoformat()

def _get_db_path():
    return ensure_database_dir()

def _key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

def _init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS Models (
        ModelId INTEGER PRIMARY KEY, ModelKey TEXT UNIQUE NOT NULL,
        ProjectKey TEXT NOT NULL, DocumentKey TEXT, DocumentTitle TEXT NOT NULL,
        IsLinked INTEGER NOT NULL, LinkUniqueId TEXT, LastScannedUtc TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS Elements (
        ElementPk INTEGER PRIMARY KEY, ModelId INTEGER NOT NULL REFERENCES Models(ModelId),
        RevitElementId INTEGER NOT NULL, ElementUniqueId TEXT NOT NULL,
        Category TEXT, LevelName TEXT, LevelId INTEGER,
        SystemType TEXT, SystemClassification TEXT, SystemName TEXT, FamilyType TEXT,
        LocationX REAL, LocationY REAL, LocationZ REAL,
        BoundsMinX REAL, BoundsMinY REAL, BoundsMinZ REAL,
        BoundsMaxX REAL, BoundsMaxY REAL, BoundsMaxZ REAL,
        UNIQUE(ModelId, ElementUniqueId));
    CREATE TABLE IF NOT EXISTS Scans (
        ScanId TEXT PRIMARY KEY, ProjectKey TEXT NOT NULL, ScopeKey TEXT NOT NULL,
        ConfigJson TEXT NOT NULL, State TEXT NOT NULL, CompletedUtc TEXT NOT NULL,
        ElementsCollected INTEGER, ElapsedSeconds REAL, DiagnosticsJson TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS Issues (
        IssueId INTEGER PRIMARY KEY, ProjectKey TEXT NOT NULL, PairKey TEXT UNIQUE NOT NULL,
        EngineSource TEXT NOT NULL, IssueType TEXT NOT NULL,
        ElementPkA INTEGER REFERENCES Elements(ElementPk), ElementPkB INTEGER REFERENCES Elements(ElementPk),
        OverlapDepthFeet REAL, LocationX REAL, LocationY REAL, LocationZ REAL,
        Status TEXT NOT NULL, DetectedUtc TEXT NOT NULL, ResolvedUtc TEXT, Notes TEXT,
        LastScanId TEXT REFERENCES Scans(ScanId), ScopeKey TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS IX_Issues_ProjectStatus ON Issues(ProjectKey, Status);
    CREATE TABLE IF NOT EXISTS IssueLinks (LinkId INTEGER PRIMARY KEY, IssueIdA INTEGER, IssueIdB INTEGER, LinkType TEXT);
    CREATE TABLE IF NOT EXISTS BCFTopics (TopicId TEXT PRIMARY KEY, IssueId INTEGER, Title TEXT, Status TEXT, CreationDate TEXT, ExportedFilePath TEXT);
    CREATE TABLE IF NOT EXISTS AIRecommendations (RecommendationId INTEGER PRIMARY KEY, IssueId INTEGER, SuggestedAction TEXT, Confidence REAL, GeneratedUtc TEXT, ModelUsed TEXT);
    CREATE TABLE IF NOT EXISTS RFIs (RfiId INTEGER PRIMARY KEY, IssueId INTEGER, RfiNumber TEXT, Subject TEXT, Body TEXT, Status TEXT, CreatedUtc TEXT, DueDate TEXT);
    CREATE TABLE IF NOT EXISTS AuditHistory (AuditId INTEGER PRIMARY KEY, EntityType TEXT, EntityId TEXT, Action TEXT, Details TEXT, PerformedBy TEXT, PerformedUtc TEXT);
    """)
    conn.execute("PRAGMA user_version=3")
    conn.commit()

def _connect():
    path = _get_db_path()
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError("Database schema is newer than this BIM Engine build.")
        legacy = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='Models'").fetchone()
        if legacy and version < 2:
            backup_path = path + ".pre-v2-" + uuid.uuid4().hex + ".bak"
            with closing(sqlite3.connect(backup_path)) as backup:
                conn.backup(backup)
            # Legacy records lack stable project identity. Preserve them exactly,
            # rather than guessing their project and linking them to the wrong model.
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                for table in ("Models", "Elements", "Issues", "IssueLinks", "BCFTopics", "AIRecommendations", "RFIs", "AuditHistory"):
                    conn.execute('ALTER TABLE "{}" RENAME TO "Legacy_{}"'.format(table, table))
                conn.execute("PRAGMA user_version=1")
        if version == 2:
            with closing(sqlite3.connect(path + '.pre-v3-' + uuid.uuid4().hex + '.bak')) as backup:
                conn.backup(backup)
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                for column in ('SystemType', 'SystemClassification', 'SystemName', 'FamilyType'):
                    conn.execute('ALTER TABLE Elements ADD COLUMN ' + column + ' TEXT')
                conn.execute('PRAGMA user_version=3')
        elif version < SCHEMA_VERSION:
            _init_schema(conn)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception:
        conn.close()
        raise

def _identity(element):
    return [element.get("document_key") or element["document_title"],
            element.get("linked_ref_id") or "", element.get("element_unique_id") or str(element["element_id"])]

def _upsert_element(conn, project_key, element):
    identity = _identity(element)
    model_key = _key([project_key] + identity[:2])
    conn.execute("""INSERT INTO Models(ModelKey, ProjectKey, DocumentKey, DocumentTitle, IsLinked, LinkUniqueId, LastScannedUtc)
        VALUES(?,?,?,?,?,?,?) ON CONFLICT(ModelKey) DO UPDATE SET DocumentTitle=excluded.DocumentTitle, LastScannedUtc=excluded.LastScannedUtc""",
        (model_key, project_key, identity[0], element["document_title"], int(element["is_linked"]), identity[1], _now()))
    model_id = conn.execute("SELECT ModelId FROM Models WHERE ModelKey=?", (model_key,)).fetchone()[0]
    columns = ["ModelId", "RevitElementId", "ElementUniqueId", "Category", "LevelName", "LevelId",
        "LocationX", "LocationY", "LocationZ", "BoundsMinX", "BoundsMinY", "BoundsMinZ", "BoundsMaxX", "BoundsMaxY", "BoundsMaxZ"]
    values = [model_id, element["element_id"], identity[2], element["category"], element.get("level_name"), element.get("level_id")]
    values += [element.get("location_"+axis, 0) for axis in "xyz"]
    values += [element.get("bounds_"+kind+"_"+axis) for kind in ("min", "max") for axis in "xyz"]
    columns += ['SystemType', 'SystemClassification', 'SystemName', 'FamilyType']
    values += [element.get(field, '') for field in ('system_type', 'system_classification', 'system_name', 'family_type')]
    conn.execute("INSERT INTO Elements ({}) VALUES ({}) ON CONFLICT(ModelId,ElementUniqueId) DO UPDATE SET {}".format(
        ",".join(columns), ",".join("?" for _ in columns),
        ",".join(c+"=excluded."+c for c in columns if c not in ("ModelId", "ElementUniqueId"))), values)
    return conn.execute("SELECT ElementPk FROM Elements WHERE ModelId=? AND ElementUniqueId=?", (model_id, identity[2])).fetchone()[0]

def save_scan_results(issues_list, elements_collected, elapsed_seconds, project_key="offline",
                      config=None, diagnostics=None, elements=None, metrics=None):
    config = config or {}
    diagnostics = diagnostics or []
    scope = dict(categories=sorted(config.get("Categories", [])), linked=config.get("IncludeLinkedDocuments", False),
                 padding=config.get("CandidateQueryPaddingFeet", .01), engine="ClashDetector")
    scope_key = _key(scope)
    scan_id = uuid.uuid4().hex
    with closing(_connect()) as conn, conn:
        new_count, resolved_count, new_ids = 0, 0, []
        conn.execute("INSERT INTO Scans VALUES(?,?,?,?,?,?,?,?,?)",
            (scan_id, project_key, scope_key, json.dumps(config), "Partial" if diagnostics else "Completed",
             _now(), elements_collected, elapsed_seconds, json.dumps(diagnostics)))
        for element in elements or []:
            _upsert_element(conn, project_key, element)
        for issue in issues_list:
            a, b = issue["element_a"], issue["element_b"]
            if b and _identity(b) < _identity(a):
                a, b = b, a
            pk_a = _upsert_element(conn, project_key, a)
            pk_b = _upsert_element(conn, project_key, b) if b else None
            pair_key = _key([project_key, issue["engine_source"], issue["issue_type"], _identity(a), _identity(b) if b else None])
            is_new = not conn.execute("SELECT 1 FROM Issues WHERE PairKey=?", (pair_key,)).fetchone()
            if is_new:
                new_count += 1
            conn.execute("""INSERT INTO Issues(ProjectKey,PairKey,EngineSource,IssueType,ElementPkA,ElementPkB,
                OverlapDepthFeet,LocationX,LocationY,LocationZ,Status,DetectedUtc,LastScanId,ScopeKey)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(PairKey) DO UPDATE SET
                ElementPkA=excluded.ElementPkA, ElementPkB=excluded.ElementPkB,
                OverlapDepthFeet=excluded.OverlapDepthFeet, LocationX=excluded.LocationX,
                LocationY=excluded.LocationY, LocationZ=excluded.LocationZ,
                Status=CASE WHEN Issues.Status='Resolved' THEN 'Open' ELSE Issues.Status END,
                ResolvedUtc=NULL, LastScanId=excluded.LastScanId, ScopeKey=excluded.ScopeKey""",
                (project_key,pair_key,issue["engine_source"],issue["issue_type"],pk_a,pk_b,
                 issue["overlap_depth_feet"],issue["location_x"],issue["location_y"],issue["location_z"],
                 issue["status"],issue["detected_utc"],scan_id,scope_key))
            if is_new:
                new_ids.append(conn.execute("SELECT IssueId FROM Issues WHERE PairKey=?", (pair_key,)).fetchone()[0])
        # Only complete scans of exactly the same scope can resolve unseen clashes.
        # Offline legacy calls carry no scope and deliberately do not auto-resolve.
        if config and not diagnostics:
            resolved_count = conn.execute("""UPDATE Issues SET Status='Resolved',ResolvedUtc=?
                WHERE ProjectKey=? AND ScopeKey=? AND LastScanId<>? AND EngineSource='ClashDetector'
                AND Status IN ('Open','Reviewed')""", (_now(),project_key,scope_key,scan_id)).rowcount
        conn.execute("INSERT INTO AuditHistory(EntityType,EntityId,Action,Details,PerformedBy,PerformedUtc) VALUES(?,?,?,?,?,?)",
            ("Scan",scan_id,"ScanRun",json.dumps(dict(issues=len(issues_list),diagnostics=len(diagnostics),
                new=new_count, new_ids=new_ids, resolved=resolved_count, metrics=metrics or {})),os.getenv("USERNAME"),_now()))
    return scan_id

def get_open_issues(project_key=None, include_closed=False):
    if not os.path.isfile(_get_db_path()):
        return []
    with closing(_connect()) as conn:
        sql = """SELECT i.IssueId AS issue_id,i.EngineSource AS engine_source,i.IssueType AS issue_type,
            i.OverlapDepthFeet AS overlap_depth_feet,i.DetectedUtc AS detected_utc,i.Status AS status,
            i.Notes AS notes,i.LastScanId AS last_scan_id,
            i.LocationX AS location_x,i.LocationY AS location_y,i.LocationZ AS location_z,
            ea.SystemType AS system_type_a,ea.SystemClassification AS system_classification_a,ea.SystemName AS system_name_a,ea.FamilyType AS family_type_a,
            eb.SystemType AS system_type_b,eb.SystemClassification AS system_classification_b,eb.SystemName AS system_name_b,eb.FamilyType AS family_type_b,
            ma.DocumentKey AS document_key_a,mb.DocumentKey AS document_key_b,
            ea.BoundsMinX AS min_x_a,ea.BoundsMinY AS min_y_a,ea.BoundsMaxX AS max_x_a,ea.BoundsMaxY AS max_y_a,
            eb.BoundsMinX AS min_x_b,eb.BoundsMinY AS min_y_b,eb.BoundsMaxX AS max_x_b,eb.BoundsMaxY AS max_y_b,
            ea.Category AS category_a,ea.RevitElementId AS revit_element_id_a,ea.ElementUniqueId AS unique_id_a,
            ea.LevelName AS level_a,ma.DocumentTitle AS document_a,ma.LinkUniqueId AS linked_ref_id_a,
            eb.Category AS category_b,eb.RevitElementId AS revit_element_id_b,eb.ElementUniqueId AS unique_id_b,
            eb.LevelName AS level_b,mb.DocumentTitle AS document_b,mb.LinkUniqueId AS linked_ref_id_b
            FROM Issues i JOIN Elements ea ON ea.ElementPk=i.ElementPkA JOIN Models ma ON ma.ModelId=ea.ModelId
            LEFT JOIN Elements eb ON eb.ElementPk=i.ElementPkB LEFT JOIN Models mb ON mb.ModelId=eb.ModelId
            WHERE 1=1"""
        if not include_closed:
            sql += " AND i.Status IN ('Open','Reviewed')"
        args = []
        if project_key is not None:
            sql += " AND i.ProjectKey=?"
            args.append(project_key)
        return [dict(row) for row in conn.execute(sql+" ORDER BY i.IssueId DESC", args)]

def get_latest_scan(project_key):
    if not os.path.isfile(_get_db_path()):
        return None
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM Scans WHERE ProjectKey=? ORDER BY CompletedUtc DESC LIMIT 1", (project_key,)).fetchone()
        if not row:
            return None
        result = dict(row)
        audit = conn.execute("SELECT Details FROM AuditHistory WHERE EntityType='Scan' AND EntityId=? AND Action='ScanRun' ORDER BY AuditId DESC LIMIT 1", (row['ScanId'],)).fetchone()
        result['Changes'] = json.loads(audit[0]) if audit else {}
        return result

def get_issue_by_id(issue_id):
    if not os.path.isfile(_get_db_path()):
        return None
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM Issues WHERE IssueId=?", (issue_id,)).fetchone()
        return dict(row) if row else None

def update_issue_status(issue_id, status, notes=None):
    if status not in ("Open", "Reviewed", "Resolved", "Ignored"):
        raise ValueError("Unsupported issue status.")
    if not os.path.isfile(_get_db_path()):
        return False
    with closing(_connect()) as conn, conn:
        cursor = conn.execute("UPDATE Issues SET Status=?,ResolvedUtc=?,Notes=COALESCE(?,Notes) WHERE IssueId=?",
            (status, _now() if status == "Resolved" else None, notes, issue_id))
        if cursor.rowcount:
            conn.execute("INSERT INTO AuditHistory(EntityType,EntityId,Action,Details,PerformedBy,PerformedUtc) VALUES(?,?,?,?,?,?)",
                ("Issue",str(issue_id),"StatusChanged",status,os.getenv("USERNAME"),_now()))
        return cursor.rowcount > 0


def triage_issues(project_key, issue_ids, action, text=''):
    """Atomic, project-scoped edits. Notes/assignments append without overwriting history."""
    ids = list(dict.fromkeys(issue_ids))
    if not ids or any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError('Select one or more clashes.')
    if action not in ('review', 'ignore', 'note', 'assign'):
        raise ValueError('Unsupported triage action.')
    if action != 'ignore' and len(ids) != 1:
        raise ValueError('Select one clash for this action.')
    text = text.strip()
    if action in ('note', 'assign') and not text:
        raise ValueError('Enter a note or assignee first.')
    if len(text) > 4000 or (action == 'assign' and ('\n' in text or '\r' in text)):
        raise ValueError('Use a single line for an assignee and at most 4000 characters.')
    with closing(_connect()) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        rows = []
        for issue_id in ids:
            row = conn.execute('SELECT * FROM Issues WHERE ProjectKey=? AND IssueId=?', (project_key, issue_id)).fetchone()
            if row is None:
                raise ValueError('A selected clash no longer belongs to this project. Reload the list.')
            rows.append(row)
        for row in rows:
            status = {'review': 'Reviewed', 'ignore': 'Ignored'}.get(action, row['Status'])
            notes = row['Notes'] or ''
            if action in ('note', 'assign'):
                entry = ('Assigned to: ' if action == 'assign' else '') + text
                notes = notes + ('\n' if notes else '') + entry
            conn.execute('UPDATE Issues SET Status=?, Notes=?, ResolvedUtc=? WHERE IssueId=? AND ProjectKey=?',
                         (status, notes, row['ResolvedUtc'] if status == 'Resolved' else None, row['IssueId'], project_key))
            conn.execute('INSERT INTO AuditHistory(EntityType,EntityId,Action,Details,PerformedBy,PerformedUtc) VALUES(?,?,?,?,?,?)',
                         ('Issue', str(row['IssueId']), 'Triage', json.dumps(dict(action=action, text=text)), os.getenv('USERNAME'), _now()))
    return len(ids)

