#! python3
"""Phase 2.1 acceptance fixture. Only new models and isolated SQLite/config files."""
import os,sys,json,uuid,traceback,hashlib,runpy,time
ROOT=r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
EXTENSION=os.environ.get('BIMENGINE_EXTENSION_PATH',os.path.join(ROOT,'BIMEngine.extension'))
sys.path.insert(0,os.path.join(EXTENSION,'lib'))
RUN=os.path.join(ROOT,'verification','inspection-'+uuid.uuid4().hex[:8]);os.makedirs(RUN)
os.environ['BIMENGINE_DB_PATH']=os.path.join(RUN,'issues.db')
report={'status':'running','checks':[],'run_directory':RUN,'extension_path':EXTENSION}
with open(os.path.join(EXTENSION,'bin','BIMEngine.Core.dll'),'rb') as stream:report['dll_sha256']=hashlib.sha256(stream.read()).hexdigest()
def check(name,passed,detail=None):
    report['checks'].append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed:raise AssertionError(name+': '+str(detail))
def save():
    for path in [os.path.join(RUN,'result.json'),os.path.join(ROOT,'verification','inspection-result.json')]:
        with open(path,'w') as stream:json.dump(report,stream,indent=2)
try:
    import clr
    clr.AddReference('RevitAPI')
    from Autodesk.Revit import DB
    from Autodesk.Revit.DB.Plumbing import Pipe,PipeType,PipingSystemType
    from Autodesk.Revit.UI import UIApplication
    from System import Action
    from System.Collections.Generic import List
    from bimengine_core import dashboard,database,config,ui
    from bimengine_core.revit_bridge import scan_and_save,document_key
    dashboard.initialize(__revit__)
    from BIMEngine.Core.Dashboard import DashboardController as Controller,DashboardNavigation,InspectionSession as Session,PinnedClashViews as Pins,InspectionGeometry,OverlapOverlay
    from BIMEngine.Core.Collection import SystemMetadata
    clr.AddReference(os.path.join(ROOT,'tests','DashboardHarness','bin','Release','net48','DashboardHarness.dll'))
    from BIMEngine.Tests import TestEvents
    TestEvents.Initialize()
    config.USER_CONFIG_PATH=os.path.join(RUN,'config.json');config.USER_CONFIG_DIR=RUN
    cfg=dict(config.DEFAULT_CONFIG);cfg['Categories']=['Pipes','Structural Framing'];config.save_config(cfg)
    app=__revit__.Application
    def pipes(doc):
        levels=list(DB.FilteredElementCollector(doc).OfClass(DB.Level))
        level=levels[0] if levels else DB.Level.Create(doc,0)
        pipe_type=next(iter(DB.FilteredElementCollector(doc).OfClass(PipeType)))
        soil=PipingSystemType.Create(doc,DB.MEPSystemClassification.Sanitary,'Soil')
        waste=PipingSystemType.Create(doc,DB.MEPSystemClassification.Sanitary,'Waste')
        a=Pipe.Create(doc,soil.Id,pipe_type.Id,level.Id,DB.XYZ(-8,0,3),DB.XYZ(8,0,3))
        b=Pipe.Create(doc,waste.Id,pipe_type.Id,level.Id,DB.XYZ(0,-6,3.25),DB.XYZ(0,6,3.25))
        for pipe in (a,b):pipe.get_Parameter(DB.BuiltInParameter.RBS_PIPE_DIAMETER_PARAM).Set(1.0)
        return a,b,soil,waste
    linked=app.NewProjectDocument(DB.UnitSystem.Imperial)
    tx=DB.Transaction(linked,'Linked pipes');tx.Start();pipes(linked);tx.Commit()
    linked_path=os.path.join(RUN,'link.rvt');linked.SaveAs(linked_path);linked.Close(False)
    doc=app.NewProjectDocument(DB.UnitSystem.Imperial)
    tx=DB.Transaction(doc,'Inspection fixture');tx.Start()
    pa,pb,soil,waste=pipes(doc);a_id=pa.Id.Value;b_id=pb.Id.Value;soil_id=soil.Id.Value
    points=[DB.XYZ(2,-1,2),DB.XYZ(3,-1,2),DB.XYZ(3,1,2),DB.XYZ(2,1,2)]
    loop=DB.CurveLoop()
    for i in range(4):loop.Append(DB.Line.CreateBound(points[i],points[(i+1)%4]))
    loops=List[DB.CurveLoop]();loops.Add(loop)
    solid=DB.GeometryCreationUtilities.CreateExtrusionGeometry(loops,DB.XYZ.BasisZ,2)
    beam=DB.DirectShape.CreateElement(doc,DB.ElementId(DB.BuiltInCategory.OST_StructuralFraming))
    shape=List[DB.GeometryObject]();shape.Add(solid);beam.SetShape(shape)
    # A regular, user-owned view for proving cleanup protections and activation.
    ft=next(t for t in DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType) if t.ViewFamily==DB.ViewFamily.ThreeDimensional)
    user_view=DB.View3D.CreateIsometric(doc,ft.Id);user_view.Name='User coordination view';user_view_id=user_view.Id.Value
    lt=DB.RevitLinkType.Create(doc,DB.ModelPathUtils.ConvertUserVisiblePathToModelPath(linked_path),DB.RevitLinkOptions(False));link_type_id=lt.ElementId.Value
    for x in (100,200):
        instance=DB.RevitLinkInstance.Create(doc,lt.ElementId)
        DB.ElementTransformUtils.MoveElement(doc,instance.Id,DB.XYZ(x,0,0))
    tx.Commit()
    host_path=os.path.join(RUN,'host.rvt');doc.SaveAs(host_path);doc.Close(False)
    uidoc=__revit__.OpenAndActivateDocument(host_path);doc=uidoc.Document
    uidoc.ActiveView=doc.GetElement(DB.ElementId(user_view_id))
    ui.alert=lambda owner,text:None
    root=os.path.join(EXTENSION,'BIMEngine.tab','ModelScanner.panel')
    command=runpy.run_path(os.path.join(root,'RunScan.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    result=command['main']();check('production scan collects actual pipe systems',result is not None)
    command=runpy.run_path(os.path.join(root,'IssueReport.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    check('production dashboard opens',command['main']())
    rows=list(Controller.Snapshot.Issues)
    host=next(r for r in rows if not r.A.LinkId and set((r.A.ElementId,r.B.ElementId))==set((a_id,b_id)))
    linked_row=next(r for r in rows if r.A.LinkId and r.B.LinkId)
    check('Soil Pipe versus Waste Pipe displayed',host.Type=='Soil Pipe ↔ Waste Pipe',host.Type)
    check('same classification preserves distinct system types',host.A.SystemClassification==host.B.SystemClassification and host.A.SystemType!=host.B.SystemType)
    check('system names collected from linked documents',linked_row.Type=='Soil Pipe ↔ Waste Pipe')
    Controller.Page.SetFilters(None,host.Type,'');check('system-pair filter excludes beam clash',Controller.Page.VisibleCount<len(rows))
    Controller.Page.SetFilters(None,None,'');Controller.Page.SelectIssue(host.Id)
    doc.Save()
    before_count=DB.FilteredElementCollector(doc).GetElementCount()
    before_views=DB.FilteredElementCollector(doc).OfClass(DB.View).GetElementCount()
    start=time.perf_counter()
    for mode in ('2d','3d','section'):
        DashboardNavigation.Navigate(__revit__,host,mode,3.0)
        check(mode+' preview contains real intersection',Session.Scene.HasOverlap and Session.Scene.OverlapVolume>0)
    report['first_preview_seconds']=time.perf_counter()-start
    old_scene=Session.Scene
    for i in range(12):DashboardNavigation.Navigate(__revit__,host,'rotate',3.0)
    check('four-corner rotation cycles and caches geometry',Session.Corner==0 and Session.Scene.Equals(old_scene))
    check('all preview modes leave document unmodified',not doc.IsModified)
    check('previews add no views or model elements',before_count==DB.FilteredElementCollector(doc).GetElementCount() and before_views==DB.FilteredElementCollector(doc).OfClass(DB.View).GetElementCount())
    DashboardNavigation.Navigate(__revit__,linked_row,'3d',3.0)
    check('linked preview uses transformed geometry and exact overlap',Session.Scene.HasOverlap and Session.Scene.Clash.X>90)
    DashboardNavigation.Navigate(__revit__,linked_row,'select',3.0)
    refs=list(uidoc.Selection.GetReferences())
    check('linked selection resolves exact instance',len(refs)==2 and all(r.ElementId==doc.GetElement(linked_row.A.LinkId).Id for r in refs))

    def render(mode):
        from System.Windows import Size,Rect
        from System.Windows.Media import PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap,PngBitmapEncoder,BitmapFrame
        from System.IO import FileStream,FileMode
        from BIMEngine.Core.Dashboard import InspectionViewport
        viewport=InspectionViewport();viewport.Display(Session.Scene,mode,Session.Corner,Session.UseB,True,False,3.0)
        viewport.Measure(Size(900,650));viewport.Arrange(Rect(0,0,900,650));viewport.UpdateLayout()
        bitmap=RenderTargetBitmap(900,650,96,96,PixelFormats.Pbgra32);bitmap.Render(viewport)
        encoder=PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream=FileStream(os.path.join(RUN,'preview-'+mode+'.png'),FileMode.Create)
        try:encoder.Save(stream)
        finally:stream.Dispose()
    for mode in ('2d','3d','section'):render(mode)
    def render_page():
        from System.Windows import Size,Rect
        from System.Windows.Media import PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap,PngBitmapEncoder,BitmapFrame
        from System.IO import FileStream,FileMode
        from BIMEngine.Core.Dashboard import DashboardPage
        page=DashboardPage();page.Display(Controller.Snapshot);page.SelectIssue(host.Id)
        page.ShowInspection(Session.Scene,'3d',0,False,True,False,3.0)
        page.Measure(Size(620,1000));page.Arrange(Rect(0,0,620,1000));page.UpdateLayout()
        bitmap=RenderTargetBitmap(620,1000,96,96,PixelFormats.Pbgra32);bitmap.Render(page)
        encoder=PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream=FileStream(os.path.join(RUN,'dashboard.png'),FileMode.Create)
        try:encoder.Save(stream)
        finally:stream.Dispose()
    DashboardNavigation.Navigate(__revit__,host,'3d',3.0)
    render_page()
    pinned=[]
    for mode in ('2d','3d','section'):
        DashboardNavigation.Navigate(__revit__,host,mode,3.0)
        view=Pins.Pin(__revit__,host,Session.Scene,mode,3.0,0,False,True,False,'Pinned '+mode,mode!='3d')
        pinned.append(view.Id.Value)
        check('explicit pin creates '+mode+' view',Pins.IsOwned(view))
        if mode=='2d':check('pinned plan crop active and fitted',view.CropBoxActive and view.CropBox.Max.X-view.CropBox.Min.X<30)
        if mode=='3d':check('pinned 3D section box and camera saved',view.IsSectionBoxActive and view.IsLocked)
        if mode=='section':check('pinned section cuts through clash',isinstance(view,DB.ViewSection))
    from System import Int64
    active=List[Int64]();active.Add(pinned[2]);rejected=False
    try:Pins.Delete(__revit__,active)
    except Exception:rejected=True
    check('cleanup refuses active pinned view',rejected and doc.GetElement(DB.ElementId(pinned[2])) is not None)
    uidoc.ActiveView=doc.GetElement(DB.ElementId(user_view_id))
    from System import Int64
    rejected=False
    unrelated=List[Int64]();unrelated.Add(user_view_id)
    try:Pins.Delete(__revit__,unrelated)
    except Exception:rejected=True
    check('cleanup refuses unrelated user view',rejected and doc.GetElement(DB.ElementId(user_view_id)) is not None)
    tx=DB.Transaction(doc,'Place protected pin on sheet');tx.Start()
    sheet=DB.ViewSheet.Create(doc,DB.ElementId.InvalidElementId)
    viewport=DB.Viewport.Create(doc,sheet.Id,DB.ElementId(pinned[1]),DB.XYZ.Zero)
    tx.Commit()
    protected=List[Int64]();protected.Add(pinned[1]);rejected=False
    try:Pins.Delete(__revit__,protected)
    except Exception:rejected=True
    check('cleanup refuses sheet-placed pinned views',rejected and doc.GetElement(DB.ElementId(pinned[1])) is not None)
    tx=DB.Transaction(doc,'Dependent plan fixture');tx.Start()
    dependent=doc.GetElement(DB.ElementId(pinned[0])).Duplicate(DB.ViewDuplicateOption.AsDependent)
    tx.Commit()
    parent=List[Int64]();parent.Add(pinned[0]);rejected=False
    try:Pins.Delete(__revit__,parent)
    except Exception:rejected=True
    check('cleanup refuses parent with dependent views',rejected and doc.GetElement(dependent) is not None)
    tx=DB.Transaction(doc,'Remove fixture dependent');tx.Start();doc.Delete(dependent);tx.Commit()
    remove=List[Int64]();remove.Add(pinned[0]);remove.Add(pinned[2])
    report['deletion_dependencies']=[]
    for view_id in (pinned[0],pinned[2]):
        tx=DB.Transaction(doc,'Inspect delete dependencies');tx.Start();deleted=list(doc.Delete(DB.ElementId(view_id)));tx.RollBack()
        for eid in deleted:
            element=doc.GetElement(eid)
            report['deletion_dependencies'].append(dict(view=view_id,id=eid.Value,kind=element.GetType().FullName,category=str(element.Category.Name) if element.Category else '',owner=element.OwnerViewId.Value))
    check('cleanup removes selected owned views and annotations' ,Pins.Delete(__revit__,remove)==2)
    check('unselected pinned view survives',doc.GetElement(DB.ElementId(pinned[1])) is not None)
    database.update_issue_status(host.Id,'Reviewed','Retain note through system rename')
    tx=DB.Transaction(doc,'Rename system');tx.Start();doc.GetElement(DB.ElementId(soil_id)).Name='Black Water';tx.Commit()
    Controller.Load(__revit__,True)
    check('system rename preserves issue and note',database.get_issue_by_id(host.Id)['Notes']=='Retain note through system rename' and any(r.Id==host.Id and 'Black Water' in r.Type for r in Controller.Snapshot.Issues))
    doc.Save()
    Controller.Page.SelectIssue(host.Id)
    def click_button(label):
        from System.Windows.Controls import Button
        from System.Windows import RoutedEventArgs
        from System.Windows.Media import VisualTreeHelper
        pending=[Controller.Page]
        while pending:
            node=pending.pop()
            if isinstance(node,Button) and str(node.Content)==label:
                if not node.IsEnabled:raise AssertionError('Button disabled: '+label)
                node.RaiseEvent(RoutedEventArgs(Button.ClickEvent));return
            for index in range(VisualTreeHelper.GetChildrenCount(node)):pending.append(VisualTreeHelper.GetChild(node,index))
        raise AssertionError('Button missing: '+label)
    report['status']='awaiting-external-events';stage=[0]
    click_button('Show 3D')
    def on_idle(sender,args):
        if Controller.Busy or TestEvents.Pending:return
        try:
            if TestEvents.Error:raise AssertionError(TestEvents.Error)
            if stage[0]==0:
                check('modeless preview event leaves document untouched',Controller.LastError is None and not doc.IsModified,Controller.LastError)
                click_button('Show Section');stage[0]=1
            elif stage[0]==1:
                check('modeless section event succeeds',Controller.LastError is None and Session.Mode=='section',Controller.LastError)
                # Pin remains after restart; regenerates transient overlap on activation.
                TestEvents.Request(Action[UIApplication](lambda app: setattr(app.ActiveUIDocument,'ActiveView',doc.GetElement(DB.ElementId(pinned[1])))));stage[0]=2
            elif stage[0]==2:
                uidoc.RefreshActiveView()
                check('DirectContext3D overlay renders without model geometry',OverlapOverlay.LastError is None and OverlapOverlay.RenderCount>0,OverlapOverlay.LastError)
                report['overlay_render_count']=OverlapOverlay.RenderCount
                tx=DB.Transaction(doc,'Solve fixture host clash');tx.Start();DB.ElementTransformUtils.MoveElement(doc,DB.ElementId(b_id),DB.XYZ(30,0,0));tx.Commit()
                click_button('Refresh / Rescan');stage[0]=3
            elif stage[0]==3:
                check('refresh resolves solved clash and retains note',database.get_issue_by_id(host.Id)['Status']=='Resolved' and database.get_issue_by_id(host.Id)['Notes']=='Retain note through system rename')
                TestEvents.Request(Action[UIApplication](lambda app: doc.GetElement(DB.ElementId(link_type_id)).Unload(None)));stage[0]=4
            elif stage[0]==4:
                Controller.Request('refresh');stage[0]=5
            elif stage[0]==5:
                check('partial refresh retains linked clashes',Controller.Snapshot.Summary.startswith('Partial') and any(r.Id==linked_row.Id for r in Controller.Snapshot.Issues))
                Controller.Page.SelectIssue(linked_row.Id);Controller.Request('3d');stage[0]=6
            elif stage[0]==6:
                check('unloaded-link preview fails clearly',Controller.LastError is not None and 'unavailable' in Controller.LastError,Controller.LastError)
                TestEvents.Request(Action[UIApplication](lambda app: doc.GetElement(DB.ElementId(link_type_id)).Load()));stage[0]=7
            elif stage[0]==7:
                Controller.Request('refresh');stage[0]=8
            elif stage[0]==8:
                check('reload and refresh recover',Controller.LastError is None and Controller.Snapshot.Summary.startswith('Completed'))
                Session.End();doc.Save();report['status']='passed';__revit__.Idling-=on_idle
        except Exception:
            report['status']='failed';report['error']=traceback.format_exc();__revit__.Idling-=on_idle
        finally:save()
    __revit__.Idling+=on_idle
except Exception:
    report['status']='failed';report['error']=traceback.format_exc()
finally:save()
