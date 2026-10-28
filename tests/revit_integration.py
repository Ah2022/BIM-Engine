#! python3
"""Run with pyrevit run --revit=2024; creates only new disposable documents.

Output and isolated database live under verification/revit-<unique run>.
Does not alter or close any document that existed before the test.
"""
import os
import sys
import json
import traceback
import uuid
import time
import hashlib

ROOT = r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
EXTENSION = os.environ.get('BIMENGINE_EXTENSION_PATH', os.path.join(ROOT, 'BIMEngine.extension'))
sys.path.insert(0, os.path.join(EXTENSION, 'lib'))
RUN = os.path.join(ROOT, 'verification', 'revit-' + uuid.uuid4().hex[:8])
os.makedirs(RUN)
os.environ['BIMENGINE_DB_PATH'] = os.path.join(RUN, 'issues.db')
report = dict(status='running', checks=[], run_directory=RUN)
report['extension_path'] = EXTENSION
with open(os.path.join(EXTENSION,'bin','BIMEngine.Core.dll'),'rb') as binary:
    report['dll_sha256'] = hashlib.sha256(binary.read()).hexdigest()

def record(name, condition, details=None):
    report['checks'].append(dict(name=name, passed=bool(condition), details=details))
    if not condition: raise AssertionError(name + ': ' + str(details))

try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from System.Collections.Generic import List
    from bimengine_core.revit_bridge import run_scan, scan_and_save, document_key, _load_bimengine_dll
    from bimengine_core import database
    _load_bimengine_dll()
    from BIMEngine.Core.Geometry import IntersectionService
    from BIMEngine.Core import ScanProgressWindow
    uiapp = __revit__
    app = uiapp.Application
    report['revit'] = str(app.VersionNumber)
    report['python'] = sys.version
    config = dict(Categories=['Structural Columns'], IncludeLinkedDocuments=False,
        OctreeMaxObjectsPerNode=4, OctreeMaxDepth=8, CandidateQueryPaddingFeet=.01)

    def box(x, y=0, z=0, size=2):
        points = [DB.XYZ(x,y,z), DB.XYZ(x+size,y,z), DB.XYZ(x+size,y+size,z), DB.XYZ(x,y+size,z)]
        loop = DB.CurveLoop()
        for i in range(4): loop.Append(DB.Line.CreateBound(points[i], points[(i+1)%4]))
        loops = List[DB.CurveLoop]()
        loops.Add(loop)
        return DB.GeometryCreationUtilities.CreateExtrusionGeometry(loops, DB.XYZ.BasisZ, size)

    def shape(doc, solids):
        ds = DB.DirectShape.CreateElement(doc, DB.ElementId(DB.BuiltInCategory.OST_StructuralColumns))
        geometry = List[DB.GeometryObject]()
        for solid in solids: geometry.Add(solid)
        ds.SetShape(geometry)
        return ds

    check = IntersectionService()
    record('disjoint solids', not check.CheckHardClash(box(0), box(5)).IsClash)
    record('face touching solids', not check.CheckHardClash(box(0), box(2)).IsClash)
    overlap = check.CheckHardClash(box(0), box(1,1,1))
    record('known overlap volume and centroid', overlap.IsClash and abs(overlap.OverlapDepthFeet-1)<1e-8
           and abs(overlap.Location.X-1.5)<1e-8)

    doc = app.NewProjectDocument(DB.UnitSystem.Imperial)
    transaction = DB.Transaction(doc, 'Create BIM Engine test fixture')
    transaction.Start()
    a=shape(doc,[box(0)])
    b=shape(doc,[box(1,1,1)])
    shape(doc,[box(10)])
    shape(doc,[box(12)])
    shape(doc,[box(20)])
    shape(doc,[box(24)])
    shape(doc,[box(30),box(40)])
    shape(doc,[box(41)])
    shape(doc,[box(60),box(66)])
    shape(doc,[box(63)])
    transaction.Commit()
    doc.SaveAs(os.path.join(RUN,'host.rvt'))
    owner = int(uiapp.MainWindowHandle.ToInt64())
    progress = ScanProgressWindow(owner)
    try:
        result = scan_and_save(doc, config, progress.Update)
    finally:
        progress.Dispose()
    record('host scan: secondary solid detected and bbox false positive excluded', len(result['issues'])==2, len(result['issues']))
    record('no geometry diagnostics', not result['diagnostics'], result['diagnostics'])
    record('cache bounded by element count', result['unique_geometry_fetches']<=result['elements_collected'])
    again=scan_and_save(doc, config)
    record('repeat scan does not duplicate', len(database.get_open_issues(document_key(doc)))==2)
    report['timings']=[result['timings'],again['timings']]

    linked = app.NewProjectDocument(DB.UnitSystem.Imperial)
    tx=DB.Transaction(linked,'Create linked test fixture'); tx.Start()
    la=shape(linked,[box(0)]); lb=shape(linked,[box(1,1,1)])
    tx.Commit()
    link_path=os.path.join(RUN,'link.rvt')
    linked.SaveAs(link_path)
    linked.Close(False)
    tx=DB.Transaction(doc,'Place two linked instances'); tx.Start()
    link_type=DB.RevitLinkType.Create(doc,DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(link_path),DB.RevitLinkOptions(False))
    instance1=DB.RevitLinkInstance.Create(doc,link_type.ElementId)
    instance2=DB.RevitLinkInstance.Create(doc,link_type.ElementId)
    DB.ElementTransformUtils.MoveElement(doc,instance1.Id,DB.XYZ(100,0,0))
    DB.ElementTransformUtils.MoveElement(doc,instance2.Id,DB.XYZ(200,0,0))
    tx.Commit()
    config['IncludeLinkedDocuments']=True
    result=scan_and_save(doc,config)
    record('two instances of one link stay distinct',len(result['issues'])==4,len(result['issues']))
    record('link identity serialized',len(set(e['linked_ref_id'] for e in result['elements'] if e['is_linked']))==2)
    record('linked scan has no diagnostics',not result['diagnostics'],result['diagnostics'])
    report['timings'].append(result['timings'])
    calls=[]
    def cancel(stage,current,total):
        calls.append(stage)
        raise RuntimeError('Intentional cancellation test')
    before=database.get_latest_scan(document_key(doc))['ScanId']
    cancelled=False
    try: scan_and_save(doc,config,cancel)
    except Exception: cancelled=True
    record('cancelled scan is not persisted',cancelled and database.get_latest_scan(document_key(doc))['ScanId']==before)
    doc.Save()
    doc.Close(False)
    # Reopen and rescan, proving stable identity across document lifetime.
    reopened=app.OpenDocumentFile(os.path.join(RUN,'host.rvt'))
    scan_and_save(reopened,config)
    record('reopen preserves issue identity',len(database.get_open_issues(document_key(reopened)))==4)
    reopened.Close(False)
    report['status']='passed'
except Exception:
    report['status']='failed'
    report['error']=traceback.format_exc()
finally:
    with open(os.path.join(RUN,'result.json'),'w') as stream:
        json.dump(report,stream,indent=2)
    with open(os.path.join(ROOT,'verification','latest-revit-result.json'),'w') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
