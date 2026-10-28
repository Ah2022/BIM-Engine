using System;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace BIMEngine.Core.Dashboard
{
    public static class InspectionSession
    {
        public static InspectionScene Scene { get; private set; }
        public static ClashRow Row { get; private set; }
        public static string Mode { get; private set; }="2d";
        public static int Corner { get; private set; }
        public static bool UseB { get; set; }
        public static bool ShowContext { get; set; }=true;
        public static bool FocusClash { get; set; }
        public static double Padding { get; set; }=6;
        private static Document document;
        private static bool stale=true;
        private static double geometryPadding;
        public static void Invalidate(Document changed)
        {
            if(document!=null&&document.Equals(changed)) { stale=true;OverlapOverlay.Clear();DashboardController.Page?.ClearInspection(); }
        }
        public static string Begin(UIApplication app,ClashRow row,string mode,double padding)
        {
            var doc=app.ActiveUIDocument?.Document;
            if(doc==null||row==null||DocumentIdentity.Get(doc)!=row.Project)throw new InvalidOperationException("Clash belongs to another project. Reopen Issue Report.");
            if(stale||Scene==null||Scene.Project!=row.Project||Scene.IssueId!=row.Id||Math.Abs(geometryPadding-padding)>1e-6)
            {
                Scene=InspectionGeometry.Build(doc,row,padding);geometryPadding=padding;Corner=0;
                // Prefer the MEP curve over structural context as the default cut direction.
                UseB=!(row.A.Category=="Pipes"||row.A.Category=="Ducts")&&(row.B.Category=="Pipes"||row.B.Category=="Ducts");
            }
            stale=false;document=doc;Row=row;Mode=mode;Padding=padding;
            Present();
            return "Temporary " + (mode=="section"?"section":mode.ToUpperInvariant()) + " preview · project unchanged. " + Scene.Notice;
        }
        public static void Rotate() { Corner=(Corner+1)%4;Present(); }
        public static void Present() { if(Scene!=null&&!stale)DashboardController.Page?.ShowInspection(Scene,Mode,Corner,UseB,ShowContext,FocusClash,Padding); }
        public static void End()
        {
            Scene=null;Row=null;document=null;stale=true;OverlapOverlay.Clear();DashboardController.Page?.ClearInspection();
        }
        public static bool IsStale=>stale;
    }
}
