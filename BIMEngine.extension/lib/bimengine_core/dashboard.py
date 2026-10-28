"""JSON snapshots; callbacks execute only inside a Revit API context."""
import json
from .database import get_open_issues, get_latest_scan, triage_issues
from .revit_bridge import document_key, scan_and_save, _load_bimengine_dll
from .config import load_config


def element_label(row, side):
    category = row.get('category_' + side) or 'Unknown'
    system = row.get('system_type_' + side) or ''
    singular = {'Pipes': 'Pipe', 'Ducts': 'Duct', 'Cable Trays': 'Cable Tray',
                'Structural Framing': 'Beam', 'Structural Columns': 'Column'}.get(category, category)
    if system:
        return system if system.casefold().endswith(singular.casefold()) else system + ' ' + singular
    if category in ('Pipes', 'Ducts', 'Pipe Accessories', 'Duct Terminals', 'Air Terminals'):
        return 'Unassigned ' + singular
    return singular


def discipline(category):
    if category in ('Structural Framing', 'Structural Columns'):
        return 'Structure'
    if category in ('Pipes', 'Pipe Accessories'):
        return 'Plumbing'
    if category in ('Ducts', 'Duct Terminals', 'Air Terminals'):
        return 'HVAC'
    if category == 'Cable Trays':
        return 'Electrical'
    return 'Other'


def make_snapshot(project, title, rows, levels, latest, scan_config=None):
    """Pure conversion, independently testable outside Revit."""
    result = []
    changes = latest.get('Changes', {}) if latest else {}
    new_ids = set(changes.get('new_ids', []))
    levels = sorted(levels, key=lambda level: level[1])
    for row in rows:
        z = row['location_z']
        below = [level for level in levels if z is not None and level[1] <= z + 1e-6]
        level = below[-1] if below else None
        item = dict(Id=row['issue_id'], Project=project, Level=level[0] if level else 'Unassigned',
                    LevelId=level[2] if level else -1,
                    Type=' ↔ '.join(sorted([element_label(row, 'a'), element_label(row, 'b')])),
                    Classification=row['issue_type'], Status=row['status'], Notes=row.get('notes') or '',
                    X=row['location_x'], Y=row['location_y'], Z=z,
                    VolumeScore=(row['overlap_depth_feet'] or 0) * 304.8)
        pair = sorted([discipline(row.get('category_a')), discipline(row.get('category_b'))])
        item['DisciplinePair'] = ' ↔ '.join(pair)
        item['IsMepStructure'] = 'Structure' in pair and any(d in pair for d in ('Plumbing', 'HVAC', 'Electrical'))
        item['Age'] = ('New' if row['issue_id'] in new_ids else 'Recurring') if 'new_ids' in changes else 'Unknown'
        item['Assignee'] = next((line[len('Assigned to: '):] for line in reversed(item['Notes'].splitlines()) if line.startswith('Assigned to: ')), '')
        for side in ('a', 'b'):
            item[side.upper()] = dict(
                UniqueId=row.get('unique_id_' + side) or '',
                ElementId=row.get('revit_element_id_' + side) or -1,
                LinkId=row.get('linked_ref_id_' + side) or '',
                DocumentKey=row.get('document_key_' + side) or '',
                Document=row.get('document_' + side) or '', Category=row.get('category_' + side) or '',
                DisplayType=element_label(row, side),
                SystemType=row.get('system_type_' + side) or 'Unassigned',
                SystemClassification=row.get('system_classification_' + side) or '',
                SystemName=row.get('system_name_' + side) or '',
                FamilyType=row.get('family_type_' + side) or '',
                Level=row.get('level_' + side) or 'Unassigned',
                MinX=row.get('min_x_' + side), MinY=row.get('min_y_' + side),
                MaxX=row.get('max_x_' + side), MaxY=row.get('max_y_' + side))
        result.append(item)
    if latest:
        config = json.loads(latest['ConfigJson'])
        scope = ', '.join(config.get('Categories', [])) + (' + links' if config.get('IncludeLinkedDocuments') else ' | host only')
        summary = '{} | {} | {}'.format(latest['State'], latest['CompletedUtc'], scope)
        if latest['State'] == 'Partial':
            summary += '\nIncomplete coverage; absent clashes retained. ' + '; '.join(json.loads(latest['DiagnosticsJson']))
    else:
        summary = 'No saved scan. Choose categories and press Scan.'
    changes = latest.get('Changes', {}) if latest else {}
    strip = '{} active'.format(sum(r['Status'] in ('Open', 'Reviewed') for r in result))
    if latest:
        strip += ' · {} new · {} resolved'.format(changes.get('new', '—'), changes.get('resolved', '—'))
        if latest['State'] == 'Partial':
            strip += ' · coverage warning'
        summary += '\nScan: {}\nElements: {} | Engine time: {:.2f}s'.format(
            latest['ScanId'], latest['ElementsCollected'], latest['ElapsedSeconds'])
        metrics = changes.get('metrics', {})
        if metrics:
            summary += '\nCandidate pairs: {} | Geometry fetches: {}'.format(
                metrics.get('candidate_pairs', '—'), metrics.get('geometry_fetches', '—'))
    else:
        strip += ' · No saved scan'
    return dict(Project=project, Title=title, Summary=summary, SummaryStrip=strip, Issues=result,
                ScanConfig=scan_config or (config if latest else load_config()))


def snapshot(uiapp, rescan):
    from Autodesk.Revit.DB import FilteredElementCollector, Level
    from BIMEngine.Core.Dashboard import DashboardController
    doc = uiapp.ActiveUIDocument.Document if uiapp.ActiveUIDocument else None
    project = document_key(doc)
    if rescan:
        latest = get_latest_scan(project)
        config = json.loads(latest['ConfigJson']) if latest else load_config()
        config.update(json.loads(DashboardController.Page.ScanScopeJson))
        scan_and_save(doc, config, DashboardController.Page.UpdateScanProgress)
    levels = [(str(level.Name), float(level.ProjectElevation), int(level.Id.Value))
              for level in FilteredElementCollector(doc).OfClass(Level)]
    return json.dumps(make_snapshot(project, str(doc.Title), get_open_issues(project, include_closed=True), levels, get_latest_scan(project)))


def triage(uiapp, payload):
    request = json.loads(payload)
    project = document_key(uiapp.ActiveUIDocument.Document)
    if request['Project'] != project:
        raise ValueError('Active project changed; no triage changes saved.')
    ids = request['Ids']
    if len(ids) > 1:
        rows = [r for r in get_open_issues(project, include_closed=True) if r['issue_id'] in ids]
        pairs = {tuple(sorted([element_label(r, 'a'), element_label(r, 'b')])) for r in rows}
        if len(pairs) != 1:
            raise ValueError('Bulk ignore requires clashes of the same pair type.')
    triage_issues(project, ids, request['Action'], request.get('Text') or '')


def initialize(uiapp):
    _load_bimengine_dll()
    from BIMEngine.Core.Dashboard import DashboardController, SnapshotLoader, TriageWriter
    DashboardController.Initialize(uiapp)
    DashboardController.Loader = SnapshotLoader(snapshot)
    DashboardController.Writer = TriageWriter(triage)


def show(uiapp):
    initialize(uiapp)
    from BIMEngine.Core.Dashboard import DashboardController
    DashboardController.Show(uiapp)


def publish(uiapp):
    initialize(uiapp)
    from BIMEngine.Core.Dashboard import DashboardController
    DashboardController.Load(uiapp, False)
