using System;
using System.Collections.Generic;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace BIMEngine.Core.Dashboard
{
    public static class DashboardNavigation
    {
        public static void Navigate(UIApplication app,ClashRow row,string action,double margin)
        {
            if(action=="end") { InspectionSession.End(); app.ActiveUIDocument?.RefreshActiveView(); return; }
            if(action=="cleanup")
            {
                var ids=InspectionDialogs.Cleanup(app);
                if(ids.Length>0)PinnedClashViews.Delete(app,ids);
                return;
            }
            var doc=app.ActiveUIDocument?.Document;
            if(row==null||doc==null||DocumentIdentity.Get(doc)!=row.Project)
                throw new InvalidOperationException("Clash belongs to another project. Reopen Issue Report.");
            if(action=="select")
            {
                var a=InspectionGeometry.Resolve(doc,row.A,out var linkA);
                var b=InspectionGeometry.Resolve(doc,row.B,out var linkB);
                app.ActiveUIDocument.Selection.SetReferences(new List<Reference> {
                    linkA==null?new Reference(a):new Reference(a).CreateLinkReference(linkA),
                    linkB==null?new Reference(b):new Reference(b).CreateLinkReference(linkB) });
                return;
            }
            if(action=="pin")
            {
                if(InspectionSession.Scene==null||InspectionSession.Row?.Id!=row.Id)
                    throw new InvalidOperationException("Select a clash and wait for its preview before pinning.");
                // Revalidate current geometry after model changes, never pin a stale snapshot.
                InspectionSession.Begin(app,row,InspectionSession.Mode,margin);
                string initial="BIM Engine - Clash "+row.Id+" - "+InspectionSession.Mode.ToUpperInvariant()+" - "+DateTime.Now.ToString("yyyyMMdd-HHmmss");
                if(InspectionDialogs.Pin(app,initial,InspectionSession.Mode!="3d",out var name,out var annotation))
                    PinnedClashViews.Pin(app,row,InspectionSession.Scene,InspectionSession.Mode,margin,InspectionSession.Corner,InspectionSession.UseB,InspectionSession.ShowContext,InspectionSession.FocusClash,name,annotation);
                return;
            }
            if(action=="rotate")
            {
                InspectionSession.Begin(app,row,"3d",margin);InspectionSession.Rotate();return;
            }
            if(action=="2d"||action=="3d"||action=="section")
            { InspectionSession.Begin(app,row,action,margin);return; }
            throw new InvalidOperationException("Unknown dashboard action: "+action);
        }
    }
}
