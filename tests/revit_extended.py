#! python3
"""Additional geometry/coverage checks using new isolated project documents."""
import os
import sys
import json
import math
import traceback
ROOT=r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
sys.path.insert(0,os.path.join(ROOT,'BIMEngine.extension','lib'))
report={'status':'running','checks':[]}
def record(name,condition,details=None):
    report['checks'].append(dict(name=name,passed=bool(condition),details=details))
    if not condition: raise AssertionError(name+': '+str(details))
try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from System.Collections.Generic import List
    from bimengine_core.revit_bridge import run_scan,scan_and_save,document_key
    from bimengine_core import database
    with open(os.path.join(ROOT,'verification','latest-revit-result.json')) as stream:
        fixture=json.load(stream)['run_directory']
    os.environ['BIMENGINE_DB_PATH']=os.path.join(fixture,'extended-issues.db')
    app=__revit__.Application
    doc=app.OpenDocumentFile(os.path.join(fixture,'host.rvt'))
    cfg=dict(Categories=['Structural Columns'],IncludeLinkedDocuments=True,OctreeMaxDepth=8,
             OctreeMaxObjectsPerNode=4,CandidateQueryPaddingFeet=.01)
    baseline=scan_and_save(doc,cfg)
    links=list(DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance))
    link=links[1]
    tx=DB.Transaction(doc,'Rotate test link');tx.Start()
    center=link.GetTotalTransform().Origin
    axis=DB.Line.CreateBound(center,center+DB.XYZ.BasisZ)
    DB.ElementTransformUtils.RotateElement(doc,link.Id,axis,math.pi/2)
    tx.Commit()
    rotated=scan_and_save(doc,cfg)
    target=[i for i in rotated['issues'] if i['element_a']['linked_ref_id']==str(link.UniqueId)]
    record('rotated link clash count and host centroid',len(rotated['issues'])==4 and len(target)==1
           and abs(target[0]['location_x']-(center.X-1.5))<1e-7 and abs(target[0]['location_y']-1.5)<1e-7)
    # Mirror a link instance: supported outcome is explicit partial coverage.
    tx=DB.Transaction(doc,'Mirror test link');tx.Start()
    DB.ElementTransformUtils.MirrorElement(doc,link.Id,DB.Plane.CreateByNormalAndOrigin(DB.XYZ.BasisX,center))
    tx.Commit()
    mirrored=scan_and_save(doc,cfg)
    record('mirrored geometry is explicitly incomplete',any('Mirrored link' in d for d in mirrored['diagnostics']),mirrored['diagnostics'])
    record('partial geometry does not resolve existing issues',len(database.get_open_issues(document_key(doc)))==4)
    # Closing without saving restores the reusable fixture.
    doc.Close(False)
    doc=app.OpenDocumentFile(os.path.join(fixture,'host.rvt'))
    links=list(DB.FilteredElementCollector(doc).OfClass(DB.RevitLinkInstance))
    link_type=doc.GetElement(links[0].GetTypeId())
    link_type.Unload(None)
    unloaded=scan_and_save(doc,cfg)
    record('unloaded link coverage is explicit',any('Unloaded link' in d for d in unloaded['diagnostics']))
    record('unloaded links preserve historic issues',len(database.get_open_issues(document_key(doc)))==4)
    doc.Close(False)
    report['status']='passed'
except Exception:
    report['status']='failed';report['error']=traceback.format_exc()
finally:
    with open(os.path.join(ROOT,'verification','revit-extended-result.json'),'w') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
