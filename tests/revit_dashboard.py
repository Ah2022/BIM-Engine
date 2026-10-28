#! python3
"""Phase 2 integration: disposable models/database only, run in Revit 2024."""
import os
import sys
import json
import traceback
import uuid
import hashlib
import runpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# pyRevit runner copies scripts; explicit workspace fallback.
if not os.path.isdir(os.path.join(ROOT, 'BIMEngine.extension')):
    ROOT = r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
EXTENSION = os.environ.get('BIMENGINE_EXTENSION_PATH', os.path.join(ROOT, 'BIMEngine.extension'))
sys.path.insert(0, os.path.join(EXTENSION, 'lib'))
RUN = os.path.join(ROOT, 'verification', 'dashboard-' + uuid.uuid4().hex[:8])
os.makedirs(RUN)
os.environ['BIMENGINE_DB_PATH'] = os.path.join(RUN, 'issues.db')
report = dict(status='running', checks=[], run_directory=RUN)
report['extension_path'] = EXTENSION
with open(os.path.join(EXTENSION, 'bin', 'BIMEngine.Core.dll'), 'rb') as stream:
    report['dll_sha256'] = hashlib.sha256(stream.read()).hexdigest()

def record(name, passed, detail=None):
    report['checks'].append(dict(name=name, passed=bool(passed), detail=detail))
    if not passed: raise AssertionError(name + ': ' + str(detail))

def save_report():
    for path in [os.path.join(RUN, 'result.json'), os.path.join(ROOT, 'verification', 'dashboard-result.json')]:
        with open(path, 'w') as stream: json.dump(report, stream, indent=2)

try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from System.Collections.Generic import List
    from bimengine_core import dashboard, database
    from bimengine_core.revit_bridge import scan_and_save, document_key
    runpy.run_path(os.path.join(EXTENSION,'startup.py'),init_globals={'__revit__':__revit__},run_name='__main__')
    from BIMEngine.Core.Dashboard import DashboardController as Controller, DashboardNavigation
    record('extension startup registers the pane', Controller.Page is not None)
    clr.AddReference(os.path.join(ROOT,'tests','DashboardHarness','bin','Release','net48','DashboardHarness.dll'))
    from BIMEngine.Tests import TestEvents
    from System import Action
    from Autodesk.Revit.UI import UIApplication
    TestEvents.Initialize()
    app = __revit__.Application
    config = dict(Categories=['Structural Columns','Structural Framing'], IncludeLinkedDocuments=True,
                  OctreeMaxObjectsPerNode=4, OctreeMaxDepth=8, CandidateQueryPaddingFeet=.01)

    def box(x, y=0, z=0):
        points = [DB.XYZ(x,y,z), DB.XYZ(x+2,y,z), DB.XYZ(x+2,y+2,z), DB.XYZ(x,y+2,z)]
        loop = DB.CurveLoop()
        for i in range(4): loop.Append(DB.Line.CreateBound(points[i], points[(i+1)%4]))
        loops = List[DB.CurveLoop](); loops.Add(loop)
        return DB.GeometryCreationUtilities.CreateExtrusionGeometry(loops, DB.XYZ.BasisZ, 2)

    def shape(doc, x, y=0, z=0, category=DB.BuiltInCategory.OST_StructuralColumns):
        ds = DB.DirectShape.CreateElement(doc, DB.ElementId(category))
        geometry = List[DB.GeometryObject](); geometry.Add(box(x,y,z)); ds.SetShape(geometry)
        return ds

    link = app.NewProjectDocument(DB.UnitSystem.Imperial)
    tx = DB.Transaction(link, 'Dashboard linked fixture'); tx.Start()
    shape(link,0); shape(link,1,1,1)
    tx.Commit(); link_path = os.path.join(RUN,'link.rvt'); link.SaveAs(link_path); link.Close(False)
    doc = app.NewProjectDocument(DB.UnitSystem.Imperial)
    tx = DB.Transaction(doc, 'Dashboard host fixture'); tx.Start()
    levels = list(DB.FilteredElementCollector(doc).OfClass(DB.Level))
    if not levels: DB.Level.Create(doc,0)
    a = shape(doc,0); b = shape(doc,1,1,1); movable_id = b.Id
    c = shape(doc,30,0,15,DB.BuiltInCategory.OST_StructuralFraming); d = shape(doc,31,1,16)
    level_upper = DB.Level.Create(doc, 14); level_upper.Name = 'Dashboard Upper'
    link_type = DB.RevitLinkType.Create(doc, DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(link_path), DB.RevitLinkOptions(False))
    link1 = DB.RevitLinkInstance.Create(doc,link_type.ElementId)
    link2 = DB.RevitLinkInstance.Create(doc,link_type.ElementId)
    DB.ElementTransformUtils.MoveElement(doc,link1.Id,DB.XYZ(100,0,0))
    DB.ElementTransformUtils.MoveElement(doc,link2.Id,DB.XYZ(200,0,0))
    tx.Commit()
    host_path = os.path.join(RUN,'host.rvt'); doc.SaveAs(host_path); doc.Close(False)
    uidoc = __revit__.OpenAndActivateDocument(host_path); doc = uidoc.Document
    from bimengine_core import config as config_module, ui as ui_module
    config_module.USER_CONFIG_PATH=os.path.join(RUN,'scan_config.json')
    config_module.USER_CONFIG_DIR=RUN
    config_module.save_config(config)
    ui_module.alert=lambda owner,text: None
    button_root=os.path.join(EXTENSION,'BIMEngine.tab','ModelScanner.panel')
    command=runpy.run_path(os.path.join(button_root,'RunScan.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    record('Run Scan entry point publishes dashboard results', command['main']() is not None and Controller.Snapshot.Issues.Count==4)
    command=runpy.run_path(os.path.join(button_root,'IssueReport.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    record('Issue Report entry point opens dashboard', command['main']())
    record('real dockable pane registered and visible', __revit__.GetDockablePane(Controller.PaneId).IsShown())
    rows = list(Controller.Snapshot.Issues)
    record('all four host and repeated-link clashes displayed', len(rows)==4 and Controller.Page.VisibleCount==4, len(rows))
    upper = next(r for r in rows if r.Level=='Dashboard Upper')
    Controller.Page.SetFilters('Dashboard Upper', upper.Type, '')
    record('combined level/type filters', Controller.Page.VisibleCount==1)
    other_type=next(r.Type for r in rows if r.Type!=upper.Type)
    Controller.Page.SetFilters('Dashboard Upper',other_type,'')
    record('type filter excludes other clash types', Controller.Page.VisibleCount==0)
    Controller.Page.SetFilters(None,None,'does-not-exist')
    record('search empty state', Controller.Page.VisibleCount==0)
    Controller.Page.SetFilters(None,None,'')
    host = next(r for r in rows if not r.A.LinkId and r.Id != upper.Id)
    Controller.Page.SelectIssue(host.Id)
    DashboardNavigation.Navigate(__revit__,host,'3d',6.0)
    v3 = uidoc.ActiveView
    record('3D view created with active section box', isinstance(v3, DB.View3D) and v3.IsSectionBoxActive)
    box3 = v3.GetSectionBox()
    record('3D section box centered at clash', abs((box3.Min.X+box3.Max.X)/2-host.X)<1e-6)
    DashboardNavigation.Navigate(__revit__,upper,'3d',8.0)
    record('3D view reused and old highlights cleared', uidoc.ActiveView.Id == v3.Id and not v3.GetElementOverrides(DB.ElementId(host.A.ElementId)).ProjectionLineColor.IsValid)
    DashboardNavigation.Navigate(__revit__,host,'2d',6.0)
    record('2D plan created at host level', isinstance(uidoc.ActiveView,DB.ViewPlan) and uidoc.ActiveView.GenLevel.Id.Value==host.LevelId)
    plan_id = uidoc.ActiveView.Id
    DashboardNavigation.Navigate(__revit__,host,'2d',6.0)
    markers = list(DB.FilteredElementCollector(doc,plan_id).OfClass(DB.CurveElement))
    record('plan reused without accumulating markers', uidoc.ActiveView.Id==plan_id and len(markers)==2, len(markers))
    linked = next(r for r in rows if r.A.LinkId)
    DashboardNavigation.Navigate(__revit__,linked,'3d',6.0)
    references = list(uidoc.Selection.GetReferences())
    record('linked subelements selected through correct instance', len(references)==2 and all(r.ElementId==doc.GetElement(linked.A.LinkId).Id for r in references))
    record('transformed linked clash coordinate', linked.X>100)
    DashboardNavigation.Navigate(__revit__,linked,'2d',6.0)
    record('linked clash has 2D marker and plan', isinstance(uidoc.ActiveView,DB.ViewPlan))
    database.update_issue_status(host.Id,'Reviewed','Preserve this coordination note')
    tx=DB.Transaction(doc,'Solve one fixture clash'); tx.Start()
    DB.ElementTransformUtils.MoveElement(doc,DB.ElementId(host.B.ElementId),DB.XYZ(10,0,0)); tx.Commit()
    Controller.Load(__revit__,True)
    record('refresh rescans and removes solved clash', Controller.Snapshot.Issues.Count==3, Controller.Snapshot.Issues.Count)
    old=database.get_issue_by_id(host.Id)
    record('resolved issue retains notes and history', old['Status']=='Resolved' and old['Notes']=='Preserve this coordination note')
    Controller.Load(__revit__,True)
    record('repeat refresh does not duplicate clashes', Controller.Snapshot.Issues.Count==3)
    Controller.Page.SelectIssue(linked.Id)
    __revit__.GetDockablePane(Controller.PaneId).Hide()
    Controller.Show(__revit__)
    record('pane closes and reopens', __revit__.GetDockablePane(Controller.PaneId).IsShown())
    # Real asynchronous ExternalEvent after the script returns. This also verifies
    # the CPython delegate remains callable beyond the ribbon command lifetime.
    report['status']='awaiting-external-event'
    Controller.Request('refresh')
    stage = [0]
    other_path = os.path.join(RUN, 'other.rvt')

    def click_button(label):
        from System.Windows import LogicalTreeHelper, RoutedEventArgs
        from System.Windows.Controls import Button
        def find(node):
            if isinstance(node, Button) and str(node.Content)==label: return node
            try:
                for child in LogicalTreeHelper.GetChildren(node):
                    result = find(child)
                    if result is not None: return result
            except TypeError: pass
            return None
        button = find(Controller.Page)
        if button is None or not button.IsEnabled: raise AssertionError('Button unavailable: '+label)
        button.RaiseEvent(RoutedEventArgs(Button.ClickEvent))

    def render_dashboard():
        from System.Windows import Size, Rect
        from System.Windows.Media import PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap, PngBitmapEncoder, BitmapFrame
        from System.IO import FileStream, FileMode
        from BIMEngine.Core.Dashboard import DashboardPage
        for width in (460, 900):
            page=DashboardPage(); page.Display(Controller.Snapshot); page.SelectIssue(linked.Id)
            page.Measure(Size(width, 1000)); page.Arrange(Rect(0,0,width,1000)); page.UpdateLayout()
            bitmap=RenderTargetBitmap(width,1000,96,96,PixelFormats.Pbgra32); bitmap.Render(page)
            encoder=PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap))
            stream=FileStream(os.path.join(RUN,'dashboard-'+str(width)+'.png'),FileMode.Create)
            try: encoder.Save(stream)
            finally: stream.Dispose()
        record('narrow and wide WPF layouts rendered', True)

    def on_idle(sender, args):
        if Controller.Busy or TestEvents.Pending: return
        try:
            if TestEvents.Error: raise AssertionError(TestEvents.Error)
            if stage[0] == 0:
                record('modeless external-event refresh after command return', Controller.LastError is None and Controller.Snapshot.Issues.Count==3, Controller.LastError)
                render_dashboard()
                Controller.Page.SelectIssue(linked.Id)
                click_button('Show 3D'); stage[0]=1
            elif stage[0] == 1:
                record('Show 3D button executes through external event', Controller.LastError is None and isinstance(uidoc.ActiveView,DB.View3D), Controller.LastError)
                click_button('Show 2D'); stage[0]=2
            elif stage[0] == 2:
                record('Show 2D button executes through external event', Controller.LastError is None and isinstance(uidoc.ActiveView,DB.ViewPlan), Controller.LastError)
                other=app.NewProjectDocument(DB.UnitSystem.Imperial); other.SaveAs(other_path); other.Close(False)
                TestEvents.Request(Action[UIApplication](lambda uiapp: uiapp.OpenAndActivateDocument(other_path))); stage[0]=3
            elif stage[0] == 3:
                if Controller.Snapshot is None: return
                record('project switching clears old results', Controller.Snapshot.Project==document_key(__revit__.ActiveUIDocument.Document) and Controller.Snapshot.Issues.Count==0)
                TestEvents.Request(Action[UIApplication](lambda uiapp: uiapp.OpenAndActivateDocument(host_path))); stage[0]=4
            elif stage[0] == 4:
                if Controller.Snapshot is None or Controller.Snapshot.Project!=document_key(doc): return
                record('switching back reloads saved clashes', Controller.Snapshot.Issues.Count==3)
                TestEvents.Request(Action[UIApplication](lambda uiapp: doc.GetElement(link_type.ElementId).Unload(None)))
                stage[0]=40
            elif stage[0] == 40:
                click_button('Refresh / Rescan'); stage[0]=5
            elif stage[0] == 5:
                record('Refresh button retains linked clashes on partial coverage', Controller.LastError is None and Controller.Snapshot.Issues.Count==3 and Controller.Snapshot.Summary.startswith('Partial'), Controller.Page.Message)
                Controller.Page.SelectIssue(linked.Id); click_button('Show 3D'); stage[0]=6
            elif stage[0] == 6:
                record('unloaded link navigation reports clear error', Controller.LastError is not None and 'unavailable' in Controller.LastError, Controller.LastError)
                TestEvents.Request(Action[UIApplication](lambda uiapp: doc.GetElement(link_type.ElementId).Load()))
                stage[0]=60
            elif stage[0] == 60:
                click_button('Refresh / Rescan'); stage[0]=7
            elif stage[0] == 7:
                record('refresh recovers after link reload', Controller.LastError is None and Controller.Snapshot.Issues.Count==3 and Controller.Snapshot.Summary.startswith('Completed'), Controller.LastError)
                doc.Save()
                report['status']='passed'
                __revit__.Idling -= on_idle
        except Exception:
            report['status']='failed'; report['error']=traceback.format_exc()
            __revit__.Idling -= on_idle
        finally:
            save_report()
    __revit__.Idling += on_idle
    doc.Save()
except Exception:
    report['status']='failed'; report['error']=traceback.format_exc()
finally:
    save_report()
    print(json.dumps(report,indent=2))
