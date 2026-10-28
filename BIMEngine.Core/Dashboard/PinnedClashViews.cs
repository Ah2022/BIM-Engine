using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.ExtensibleStorage;
using Autodesk.Revit.UI;

namespace BIMEngine.Core.Dashboard
{
    public sealed class PinRecord
    {
        public bool Selected { get; set; }
        public long Id { get; set; }
        public string Name { get; set; }
        public string Created { get; set; }
        public string Kind { get; set; }
        public string Protection { get; set; }
    }
    public static class PinnedClashViews
    {
        private static readonly Guid TagId=new Guid("D046B4B1-D26F-4AA4-A008-8B2D64B8E287");
        private static readonly Guid LegacyId=new Guid("C04F6AD8-48BF-452A-9899-71C73F9BCE55");
        private static Schema Tag()
        {
            var schema=Schema.Lookup(TagId);if(schema!=null)return schema;
            var b=new SchemaBuilder(TagId);b.SetSchemaName("BIMEnginePinnedClash");b.SetReadAccessLevel(AccessLevel.Public);b.SetWriteAccessLevel(AccessLevel.Public);
            foreach(var field in new[]{"Clash","Created","Mode"})b.AddSimpleField(field,typeof(string));
            return b.Finish();
        }
        public static bool IsOwned(View view)
        {
            var current=Schema.Lookup(TagId);var legacy=Schema.Lookup(LegacyId);
            return current!=null&&view.GetEntity(current).IsValid()||legacy!=null&&view.GetEntity(legacy).IsValid();
        }
        public static List<PinRecord> List(Document doc)
        {
            var placed=new HashSet<long>(new FilteredElementCollector(doc).OfClass(typeof(Viewport)).Cast<Viewport>().Select(v=>v.ViewId.Value));
            var schema=Schema.Lookup(TagId);
            return new FilteredElementCollector(doc).OfClass(typeof(View)).Cast<View>().Where(v=>!v.IsTemplate&&IsOwned(v)).Select(v=> {
                var entity=schema==null?null:v.GetEntity(schema);bool pinned=entity!=null&&entity.IsValid();
                return new PinRecord {Id=v.Id.Value,Name=v.Name,Created=pinned?entity.Get<string>("Created"):"Phase 2 legacy",Kind=pinned?entity.Get<string>("Mode"):"Legacy generated view",
                    Protection=placed.Contains(v.Id.Value)?"Placed on sheet":v.GetDependentViewIds().Count>0?"Has dependent views":""};
            }).OrderBy(x=>x.Created).ToList();
        }
        public static int Delete(UIApplication app,IEnumerable<long> selected)
        {
            var doc=app.ActiveUIDocument.Document;var rows=List(doc).ToDictionary(x=>x.Id);
            var ids=selected.Distinct().ToList();
            foreach(var id in ids)
                if(!rows.ContainsKey(id)||rows[id].Protection!=""||id==app.ActiveUIDocument.ActiveView.Id.Value)
                    throw new InvalidOperationException("Cleanup cannot delete unrelated, active, sheet-placed, or parent views with dependents.");
            using(var tx=new Transaction(doc,"BIM Engine – remove selected pinned views"))
            {
                tx.Start();
                foreach(var id in ids)
                {
                    // Verify actual deletion dependencies in a rollback subtransaction first.
                    ICollection<ElementId> deleted;
                    using(var probe=new SubTransaction(doc))
                    {
                        probe.Start();deleted=doc.Delete(new ElementId(id)).ToArray();probe.RollBack();
                    }
                    foreach(var dependent in deleted)
                    {
                        if(dependent.Value==id)continue;
                        var element=doc.GetElement(dependent);
                        // Revit also deletes opaque internal records (base Element, no category/owner).
                        bool opaqueInternal=element!=null&&element.GetType()==typeof(Element)&&element.Category==null&&element.OwnerViewId==ElementId.InvalidElementId;
                        bool internalViewPart=opaqueInternal || (element is Viewport internalViewport&&internalViewport.ViewId.Value==id&&internalViewport.SheetId==ElementId.InvalidElementId) || element is SketchPlane || element is Sketch ||
                            element?.Category?.Id.Value==(long)BuiltInCategory.OST_IOSSketchGrid || element?.Category?.Id.Value==(long)BuiltInCategory.OST_Viewers || element?.Category?.Id.Value==(long)BuiltInCategory.OST_Views;
                        if(element is View || element is ElementType || element?.OwnerViewId.Value!=id&&!internalViewPart)
                            throw new InvalidOperationException("This view has dependencies outside its own annotations. Cleanup cancelled: " + rows[id].Name+
                                " ("+element?.GetType().Name+", "+element?.Category?.Name+", type "+element?.GetTypeId().Value+", runtime "+element?.GetType().FullName+", owner "+element?.OwnerViewId.Value+")");
                    }
                    doc.Delete(new ElementId(id));
                }
                tx.Commit();
            }
            OverlapOverlay.Clear();return ids.Count;
        }
        public static View Pin(UIApplication app,ClashRow row,InspectionScene scene,string mode,double padding,int corner,bool axisB,bool showContext,bool focus,string name,bool annotate)
        {
            var ui=app.ActiveUIDocument;var doc=ui?.Document;
            if(doc==null||scene==null||row.Project!=DocumentIdentity.Get(doc)||scene.Project!=row.Project||scene.IssueId!=row.Id)
                throw new InvalidOperationException("Open a current clash preview before pinning.");
            if(string.IsNullOrWhiteSpace(name))throw new InvalidOperationException("Enter a view name.");
            if(new FilteredElementCollector(doc).OfClass(typeof(View)).Cast<View>().Any(v=>v.Name==name))throw new InvalidOperationException("A view with that name already exists. Choose another name.");
            var a=InspectionGeometry.Resolve(doc,row.A,out var linkA);var b=InspectionGeometry.Resolve(doc,row.B,out var linkB);
            scene.Frame(padding,focus,out var min,out var max);
            scene.Axes(mode,corner,axisB,out var right,out var up,out var forward);
            var family=mode=="3d"?ViewFamily.ThreeDimensional:mode=="section"?ViewFamily.Section:ViewFamily.FloorPlan;
            var type=new FilteredElementCollector(doc).OfClass(typeof(ViewFamilyType)).Cast<ViewFamilyType>().FirstOrDefault(t=>t.ViewFamily==family);
            if(type==null)throw new InvalidOperationException("This project has no suitable view family type.");
            View view;
            using(var tx=new Transaction(doc,"BIM Engine – pin clash view"))
            {
                tx.Start();
                if(mode=="3d")
                {
                    var v=View3D.CreateIsometric(doc,type.Id);view=v;v.IsSectionBoxActive=true;
                    v.SetSectionBox(new BoundingBoxXYZ {Min=InspectionGeometry.XYZ(min),Max=InspectionGeometry.XYZ(max)});
                    v.SetOrientation(new ViewOrientation3D(InspectionGeometry.XYZ((min+max)*.5-forward*Math.Max(10,(max-min).Length*2)),InspectionGeometry.XYZ(up),InspectionGeometry.XYZ(forward)));
                    v.SaveOrientationAndLock();
                }
                else if(mode=="section")
                {
                    var transform=Transform.Identity;transform.Origin=InspectionGeometry.XYZ(scene.Clash);
                    transform.BasisX=InspectionGeometry.XYZ(up.Cross(forward));transform.BasisY=InspectionGeometry.XYZ(up);transform.BasisZ=InspectionGeometry.XYZ(forward);
                    var points=InspectionGeometry.Bounds(new BoundingBoxXYZ {Min=InspectionGeometry.XYZ(min),Max=InspectionGeometry.XYZ(max)})
                        .Select(p=>transform.Inverse.OfPoint(InspectionGeometry.XYZ(p))).ToArray();
                    view=ViewSection.CreateSection(doc,type.Id,new BoundingBoxXYZ {Transform=transform,
                        Min=new XYZ(points.Min(p=>p.X),points.Min(p=>p.Y),0),Max=new XYZ(points.Max(p=>p.X),points.Max(p=>p.Y),Math.Max(padding,points.Max(p=>p.Z)))});
                }
                else
                {
                    var level=new FilteredElementCollector(doc).OfClass(typeof(Level)).Cast<Level>().Where(l=>l.ProjectElevation<=scene.Clash.Z+1e-6).OrderByDescending(l=>l.ProjectElevation).FirstOrDefault();
                    if(level==null)throw new InvalidOperationException("No host level lies at/below this clash. Pin a section or 3D view.");
                    var plan=ViewPlan.Create(doc,type.Id,level.Id);view=plan;
                    var range=plan.GetViewRange();double offset=scene.Clash.Z-level.ProjectElevation;
                    foreach(var plane in new[]{PlanViewPlane.TopClipPlane,PlanViewPlane.CutPlane,PlanViewPlane.BottomClipPlane,PlanViewPlane.ViewDepthPlane})range.SetLevelId(plane,level.Id);
                    range.SetOffset(PlanViewPlane.TopClipPlane,Math.Max(offset+padding,max.Z-level.ProjectElevation));
                    range.SetOffset(PlanViewPlane.CutPlane,offset);
                    range.SetOffset(PlanViewPlane.BottomClipPlane,Math.Min(offset-padding,min.Z-level.ProjectElevation));
                    range.SetOffset(PlanViewPlane.ViewDepthPlane,Math.Min(offset-padding,min.Z-level.ProjectElevation));plan.SetViewRange(range);
                    plan.CropBox=new BoundingBoxXYZ { Min=InspectionGeometry.XYZ(min),Max=InspectionGeometry.XYZ(max) };
                    plan.CropBoxActive=true;plan.CropBoxVisible=false;
                }
                view.Name=name;view.DetailLevel=ViewDetailLevel.Fine;
                var visible=new HashSet<long>();
                if(showContext)visible.UnionWith(scene.NativeContextIds);
                var selectedIds=new[]{linkA?.Id??a.Id,linkB?.Id??b.Id};
                foreach(var id in selectedIds)visible.Add(id.Value);
                var gray=new OverrideGraphicSettings().SetHalftone(true).SetSurfaceTransparency(80);
                foreach(var id in visible)view.SetElementOverrides(new ElementId(id),gray);
                int side=0;
                foreach(var pair in new[]{Tuple.Create(a,linkA),Tuple.Create(b,linkB)})
                {
                    var c=InspectionViewport.ColorFor(side++);
                    if(pair.Item2!=null)continue; // link remains halftone; selected subelements get transient meshes.
                    view.SetElementOverrides(pair.Item1.Id,new OverrideGraphicSettings().SetProjectionLineColor(new Color(c.R,c.G,c.B)).SetCutLineColor(new Color(c.R,c.G,c.B)).SetProjectionLineWeight(5).SetSurfaceTransparency(45));
                }
                doc.Regenerate();
                view.IsolateElementsTemporary(visible.Select(id=>new ElementId(id)).ToList());
                view.ConvertTemporaryHideIsolateToPermanent();
                if(annotate&&mode!="3d"&&scene.HasOverlap)Annotate(doc,view,scene,row.Id);
                var entity=new Entity(Tag());
                entity.Set("Created",DateTime.UtcNow.ToString("o"));entity.Set("Mode",mode);
                entity.Set("Clash",new JavaScriptSerializer().Serialize(row));view.SetEntity(entity);
                tx.Commit();
            }
            ui.ActiveView=view;ui.GetOpenUIViews().FirstOrDefault(v=>v.ViewId==view.Id)?.ZoomToFit();
            OverlapOverlay.Show(doc,view,scene);ui.RefreshActiveView();return view;
        }
        private static void Annotate(Document doc,View view,InspectionScene scene,long issue)
        {
            var origin=view.Origin;var right=view.RightDirection;var up=view.UpDirection;
            var points=scene.Meshes.Where(m=>m.Role==2).SelectMany(m=>m.Points).Select(p=>InspectionGeometry.XYZ(p)-origin).ToArray();
            double minX=points.Min(p=>p.DotProduct(right)),maxX=points.Max(p=>p.DotProduct(right));
            double minY=points.Min(p=>p.DotProduct(up)),maxY=points.Max(p=>p.DotProduct(up));
            if(maxX-minX<.01)maxX=minX+.01;if(maxY-minY<.01)maxY=minY+.01;
            var corners=new[]{origin+right*minX+up*minY,origin+right*maxX+up*minY,origin+right*maxX+up*maxY,origin+right*minX+up*maxY};
            for(int i=0;i<4;i++)
            {
                var curve=doc.Create.NewDetailCurve(view,Line.CreateBound(corners[i],corners[(i+1)%4]));
                view.SetElementOverrides(curve.Id,new OverrideGraphicSettings().SetProjectionLineColor(new Color(255,40,65)).SetProjectionLineWeight(5));
            }
            var textType=doc.GetDefaultElementTypeId(ElementTypeGroup.TextNoteType);
            if(textType!=ElementId.InvalidElementId)TextNote.Create(doc,view.Id,corners[3]+up*.25,"Clash #"+issue+" – projected overlap extent (snapshot)",textType);
        }
        public static bool RestoreOverlay(UIApplication app)
        {
            var view=app.ActiveUIDocument?.ActiveView;var schema=Schema.Lookup(TagId);
            OverlapOverlay.Clear();
            if(view==null||schema==null)return false;
            var entity=view.GetEntity(schema);if(!entity.IsValid())return false;
            var row=new JavaScriptSerializer().Deserialize<ClashRow>(entity.Get<string>("Clash"));
            var scene=InspectionGeometry.Build(view.Document,row,6);
            OverlapOverlay.Show(view.Document,view,scene);app.ActiveUIDocument.RefreshActiveView();return true;
        }
    }
}
