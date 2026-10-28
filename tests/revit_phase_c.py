#! python3
"""Phase 2.1 acceptance fixture. Only new models and isolated SQLite/config files."""
import os,sys,json,uuid,traceback,hashlib,runpy,time
ROOT=r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
EXTENSION=os.environ.get('BIMENGINE_EXTENSION_PATH',os.path.join(ROOT,'BIMEngine.extension'))
sys.path.insert(0,os.path.join(EXTENSION,'lib'))
RUN=os.path.join(ROOT,'verification','phase-c-'+uuid.uuid4().hex[:8]);os.makedirs(RUN)
os.environ['BIMENGINE_DB_PATH']=os.path.join(RUN,'issues.db')
report={'status':'running','checks':[],'run_directory':RUN,'extension_path':EXTENSION}
with open(os.path.join(EXTENSION,'bin','BIMEngine.Core.dll'),'rb') as stream:report['dll_sha256']=hashlib.sha256(stream.read()).hexdigest()
def check(name,passed,detail=None):
    report['checks'].append({'name':name,'passed':bool(passed),'detail':detail})
    if not passed:raise AssertionError(name+': '+str(detail))
def save():
    for path in [os.path.join(RUN,'result.json'),os.path.join(ROOT,'verification','phase-c-result.json')]:
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
    command['main']();check('Scan entry opens unified pane',__revit__.GetDockablePane(Controller.PaneId).IsShown())
    Controller.Load(__revit__,True)
    check('inline scan collects actual pipe systems',Controller.Snapshot.Issues.Count>0)
    command=runpy.run_path(os.path.join(root,'IssueReport.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    check('production dashboard opens',command['main']())
    rows=list(Controller.Snapshot.Issues)
    from System.Reflection import BindingFlags
    def field(name):
        return Controller.Page.GetType().GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).GetValue(Controller.Page)
    grid=field('grid')
    check('grid is flat by default',grid.Items.GroupDescriptions.Count==0)
    check('A and B have separate sortable columns',any(str(c.Header)=='A' and str(c.SortMemberPath)=='A.ShortLabel' for c in grid.Columns) and any(str(c.Header)=='B' for c in grid.Columns))
    check('new badge available on first scan',all(r.Age=='New' for r in rows))
    grouping=field('grouping')
    for group,path in [('Level','Level'),('Pair','Type'),('Status','Status')]:
        grouping.SelectedItem=group
        check('optional grouping '+group,grid.Items.GroupDescriptions.Count==1 and grid.Items.GroupDescriptions[0].PropertyName==path)
    grouping.SelectedIndex=0
    check('grouping returns to flat',grid.Items.GroupDescriptions.Count==0)
    check('default rank known systems then overlap',grid.Items.SortDescriptions[0].PropertyName=='KnownSystemRank' and grid.Items.SortDescriptions[1].PropertyName=='VolumeScore')
    field('sorting').SelectedIndex=1
    scores=[r.VolumeScore for r in grid.Items]
    check('overlap sort is numeric descending',scores==sorted(scores,reverse=True))
    field('sorting').SelectedIndex=0
    def filter_chip(label,enabled):
        from System.Windows import RoutedEventArgs
        from System.Windows.Controls.Primitives import ButtonBase
        chip=field('quickFilters')[label]
        chip.IsChecked=enabled;chip.RaiseEvent(RoutedEventArgs(ButtonBase.ClickEvent))
    filter_chip('MEP vs Structure',True)
    check('MEP vs Structure filter narrows list',0<Controller.Page.VisibleCount<len(rows) and all(r.IsMepStructure for r in grid.Items))
    filter_chip('MEP vs Structure',False)
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
    def render_page(width=620, height=1000):
        from System.Windows import Size,Rect
        from System.Windows.Media import PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap,PngBitmapEncoder,BitmapFrame
        from System.IO import FileStream,FileMode
        from BIMEngine.Core.Dashboard import DashboardPage
        page=DashboardPage();page.Display(Controller.Snapshot);page.SelectIssue(host.Id)
        page.ShowInspection(Session.Scene,'3d',0,False,True,False,3.0)
        page.Measure(Size(width,height));page.Arrange(Rect(0,0,width,height));page.UpdateLayout()
        bitmap=RenderTargetBitmap(width,height,96,96,PixelFormats.Pbgra32);bitmap.Render(page)
        encoder=PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream=FileStream(os.path.join(RUN,'dashboard-{}-{}.png'.format(width,height)),FileMode.Create)
        try:encoder.Save(stream)
        finally:stream.Dispose()
    DashboardNavigation.Navigate(__revit__,host,'3d',3.0)
    from BIMEngine.Core.Dashboard import DashboardTheme
    from Autodesk.Revit.UI import UIThemeManager,UITheme
    check('initial palette follows Revit theme',DashboardTheme.Palette.Dark==(UIThemeManager.CurrentTheme==UITheme.Dark))
    render_page(460,700)
    render_page(900,1000)
    from System.Windows import Size,Rect
    from System.Windows.Controls import Grid
    def render_root(name):
        from System.Windows.Media import PixelFormats
        from System.Windows.Media.Imaging import RenderTargetBitmap,PngBitmapEncoder,BitmapFrame
        from System.IO import FileStream,FileMode
        root=field('dashboardRoot');root.UpdateLayout()
        bitmap=RenderTargetBitmap(int(root.ActualWidth),int(root.ActualHeight),96,96,PixelFormats.Pbgra32);bitmap.Render(root)
        encoder=PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap))
        stream=FileStream(os.path.join(RUN,name+'.png'),FileMode.Create)
        try:encoder.Save(stream)
        finally:stream.Dispose()
    toggle=Controller.Page.GetType().GetMethod('ToggleFloating',BindingFlags.Instance|BindingFlags.NonPublic)
    toggle.Invoke(Controller.Page,None)
    window=field('floatingWindow')
    def resize(width,height):
        window.Width=width;window.Height=height
        window.Measure(Size(width,height));window.Arrange(Rect(0,0,width,height));window.UpdateLayout()
    resize(1280,900)
    check('wide floating layout is two panes',Controller.Page.IsSideBySide and Grid.GetColumn(field('reviewPane'))==2)
    check('review card displays A B level and systems',str(host.A.ElementId) in field('reviewA').Text and str(host.B.ElementId) in field('reviewB').Text and host.Level in field('reviewLevel').Text and host.A.SystemType in field('reviewSystem').Text)
    check('copy IDs has accessible name',__import__('System.Windows.Automation',fromlist=['AutomationProperties']).AutomationProperties.GetName(field('copyIds'))=='Copy IDs')
    for dark,label in [(False,'light'),(True,'dark')]:
        DashboardTheme.Palette.SetDark(dark)
        window.UpdateLayout()
        render_root('floating-'+label)
        check(label+' brushes stay live',not DashboardTheme.Background.IsFrozen and DashboardTheme.Background.Color==DashboardTheme.Palette.Background)
    DashboardTheme.FollowRevit()
    resize(760,700)
    check('narrow floating layout stacks at breakpoint',not Controller.Page.IsSideBySide and Grid.GetRow(field('reviewPane'))==2)
    check('short window keeps list and viewport allocated',field('grid').ActualHeight>50 and field('preview').ActualHeight>50)
    render_root('floating-narrow')
    resize(1280,900)
    check('expanding returns to two panes',Controller.Page.IsSideBySide)
    window.Close()
    Controller.Page.UpdateLayout()
    check('docking returns to stacked layout',not Controller.Page.IsSideBySide)
    move=Controller.Page.GetType().GetMethod('MoveReview',BindingFlags.Instance|BindingFlags.NonPublic)
    from System import Array,Object,Int32
    ordered=list(field('grid').Items)
    Controller.Page.SelectIssue(ordered[0].Id)
    move.Invoke(Controller.Page,Array[Object]([Int32(1)]))
    check('Next follows displayed sort order',Controller.Page.Selected.Id==ordered[1].Id)
    move.Invoke(Controller.Page,Array[Object]([Int32(-1)]))
    check('Previous follows displayed sort order',Controller.Page.Selected.Id==ordered[0].Id)
    move.Invoke(Controller.Page,Array[Object]([Int32(-1)]))
    check('Previous stops at first clash',Controller.Page.Selected.Id==ordered[0].Id and not field('previousClash').IsEnabled)
    Controller.Page.SetFilters(None,None,'no-matching-review-row')
    check('empty list disables review navigation',not field('nextClash').IsEnabled and not field('previousClash').IsEnabled)
    Controller.Page.SetFilters(None,None,'')
    Controller.Page.SelectIssue(host.Id)
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
        from System.Windows.Controls.Primitives import ButtonBase
        from System.Windows import RoutedEventArgs
        from System.Windows.Media import VisualTreeHelper
        pending=[Controller.Page]
        while pending:
            node=pending.pop()
            if isinstance(node,ButtonBase) and str(node.Content)==label:
                if not node.IsEnabled:raise AssertionError('Button disabled: '+label)
                node.RaiseEvent(RoutedEventArgs(ButtonBase.ClickEvent));return
            for index in range(VisualTreeHelper.GetChildrenCount(node)):pending.append(VisualTreeHelper.GetChild(node,index))
        raise AssertionError('Button missing: '+label)
    report['status']='awaiting-external-events';stage=[0]
    Controller.Page.SelectIssue(linked_row.Id);Controller.Page.SelectIssue(host.Id)
    def on_idle(sender,args):
        if Controller.Busy or TestEvents.Pending:return
        try:
            if TestEvents.Error:raise AssertionError(TestEvents.Error)
            if stage[0]==0:
                if Session.Row is None or Session.Row.Id!=host.Id or Session.Mode!='3d':return
                check('automatic 3D selection preview leaves document untouched',Controller.LastError is None and not doc.IsModified,Controller.LastError)
                from System.Reflection import BindingFlags
                global Key
                from System.Windows.Input import Keyboard, Key, KeyEventArgs
                from System.Windows import PresentationSource
                grid=Controller.Page.GetType().GetField('grid',BindingFlags.Instance|BindingFlags.NonPublic).GetValue(Controller.Page)
                grid.Focus()
                global keypress
                def keypress(key):
                    event=KeyEventArgs(Keyboard.PrimaryDevice,PresentationSource.FromVisual(grid),0,key)
                    event.RoutedEvent=Keyboard.PreviewKeyDownEvent
                    grid.RaiseEvent(event)
                    check('keyboard '+str(key)+' handled',event.Handled)
                original=grid.SelectedIndex
                keypress(Key.Down);check('Down advances clash selection',grid.SelectedIndex==min(original+1,grid.Items.Count-1))
                keypress(Key.Up);check('Up reverses clash selection',grid.SelectedIndex==max(0,min(original+1,grid.Items.Count-1)-1))
                keypress(Key.Enter);stage[0]=90
            elif stage[0]==90:
                check('Enter opens 3D for current row',Controller.LastError is None and Session.Mode=='3d' and Session.Row.Id==Controller.Page.Selected.Id)
                keypress(Key.Space);stage[0]=91
            elif stage[0]==91:
                check('Space selects two elements in Revit',Controller.LastError is None and uidoc.Selection.GetReferences().Count==2)
                click_button('Section');stage[0]=1
            elif stage[0]==1:
                check('modeless section event succeeds',Controller.LastError is None and Session.Mode=='section',Controller.LastError)
                # Pin remains after restart; regenerates transient overlap on activation.
                TestEvents.Request(Action[UIApplication](lambda app: setattr(app.ActiveUIDocument,'ActiveView',doc.GetElement(DB.ElementId(pinned[1])))));stage[0]=2
            elif stage[0]==2:
                uidoc.RefreshActiveView()
                check('DirectContext3D overlay renders without model geometry',OverlapOverlay.LastError is None and OverlapOverlay.RenderCount>0,OverlapOverlay.LastError)
                report['overlay_render_count']=OverlapOverlay.RenderCount
                tx=DB.Transaction(doc,'Solve fixture host clash');tx.Start();DB.ElementTransformUtils.MoveElement(doc,DB.ElementId(b_id),DB.XYZ(30,0,0));tx.Commit()
                click_button('Scan');stage[0]=3
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
                Controller.Page.SelectIssue(linked_row.Id)
                click_button('Reviewed');stage[0]=9
            elif stage[0]==9:
                check('inline review persisted',database.get_issue_by_id(linked_row.Id)['Status']=='Reviewed')
                Controller.Page.SelectIssue(linked_row.Id);click_button('Add note')
                field('triageText').Text='Coordinate with structural team'
                click_button('Save note');stage[0]=10
            elif stage[0]==10:
                check('inline note persisted',database.get_issue_by_id(linked_row.Id)['Notes']=='Coordinate with structural team')
                Controller.Page.SelectIssue(linked_row.Id);click_button('Assign')
                field('triageText').Text='Amira'
                click_button('Save assignment');stage[0]=11
            elif stage[0]==11:
                check('assignment preserves note',database.get_issue_by_id(linked_row.Id)['Notes']=='Coordinate with structural team\nAssigned to: Amira')
                linked=[r for r in Controller.Snapshot.Issues if r.A.LinkId and r.Type==linked_row.Type and r.Status in ('Open','Reviewed')]
                check('two matching linked clashes available',len(linked)>=2)
                field('grid').SelectedItems.Clear()
                for row in linked:field('grid').SelectedItems.Add(row)
                click_button('Mark selected ignored');stage[0]=12
            elif stage[0]==12:
                check('bulk ignore writes all selected rows',all(r.Status=='Ignored' for r in Controller.Snapshot.Issues if r.A.LinkId and r.Type==linked_row.Type))
                filter_chip('Ignored',True)
                check('Ignored chip retrieves saved ignored clashes',Controller.Page.VisibleCount>=2 and all(r.Status=='Ignored' for r in field('grid').Items))
                check('assignment returned in snapshot',next(r for r in Controller.Snapshot.Issues if r.Id==linked_row.Id).Assignee=='Amira')
                filter_chip('Ignored',False);filter_chip('Resolved',True)
                check('Resolved chip retrieves history',any(r.Id==host.Id for r in field('grid').Items))
                filter_chip('Resolved',False);filter_chip('New',True)
                check('New chip excludes recurring rows after repeat scan',Controller.Page.VisibleCount==0)
                filter_chip('New',False)
                Session.End();doc.Save();report['status']='passed';__revit__.Idling-=on_idle
        except Exception:
            report['status']='failed';report['error']=traceback.format_exc();__revit__.Idling-=on_idle
        finally:save()
    __revit__.Idling+=on_idle
except Exception:
    report['status']='failed';report['error']=traceback.format_exc()
finally:save()
