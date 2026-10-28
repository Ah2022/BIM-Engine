using System;
using System.Collections.Generic;
using System.Linq;
using System.Web.Script.Serialization;
using Autodesk.Revit.UI;
using Autodesk.Revit.UI.Events;

namespace BIMEngine.Core.Dashboard
{
    public sealed class ClashElement
    {
        public long ElementId { get; set; }
        public string UniqueId { get; set; }
        public string LinkId { get; set; }
        public string DocumentKey { get; set; }
        public string Document { get; set; }
        public string Category { get; set; }
        public string DisplayType { get; set; }
        public string SystemType { get; set; }
        public string SystemClassification { get; set; }
        public string SystemName { get; set; }
        public string FamilyType { get; set; }
        public string Level { get; set; }
        public double? MinX { get; set; }
        public double? MinY { get; set; }
        public double? MaxX { get; set; }
        public double? MaxY { get; set; }
        public string ShortLabel => (DisplayType ?? Category) + " #" + ElementId;
        public bool HasSystem => !string.IsNullOrWhiteSpace(SystemType) && !SystemType.Equals("Unassigned", StringComparison.OrdinalIgnoreCase);
        public string CategoryIcon => Category == "Pipes" ? "○" : Category == "Ducts" ? "▭" : Category == "Cable Trays" ? "⊏" : Category == "Structural Framing" ? "I" : Category == "Structural Columns" ? "▣" : "◇";
        [ScriptIgnore]
        public System.Windows.Media.Brush SystemBrush
        {
            get
            {
                if (!HasSystem) return DashboardPage.Muted;
                uint hash = 2166136261;
                foreach (char ch in SystemType.ToUpperInvariant()) hash = unchecked((hash ^ ch) * 16777619);
                return DashboardTheme.Systems[hash % DashboardTheme.Systems.Length];
            }
        }
        public string Label => (DisplayType ?? Category) + " #" + ElementId + " | " + Document +
            (string.IsNullOrEmpty(LinkId) ? "" : " | link " + LinkId.Substring(0, Math.Min(8, LinkId.Length))) + " | " + Level;
    }

    public sealed class ClashRow
    {
        public long Id { get; set; }
        public string Project { get; set; }
        public string Level { get; set; }
        public long LevelId { get; set; }
        public string Type { get; set; }
        public string Classification { get; set; }
        public string Status { get; set; }
        public string Notes { get; set; }
        public string Age { get; set; }
        public string DisciplinePair { get; set; }
        public bool IsMepStructure { get; set; }
        public string Assignee { get; set; }
        public int KnownSystemRank => A.HasSystem || B.HasSystem ? 1 : 0;
        [ScriptIgnore]
        public System.Windows.Media.Brush StatusBrush => Status == "Open" ? DashboardPage.Teal : Status == "Reviewed" ? DashboardTheme.Reviewed : DashboardPage.Muted;
        [ScriptIgnore]
        public System.Windows.Media.Brush AgeBrush => Age == "New" ? DashboardPage.Teal : DashboardPage.Muted;
        public double X { get; set; }
        public double Y { get; set; }
        public double Z { get; set; }
        public double VolumeScore { get; set; }
        public ClashElement A { get; set; }
        public ClashElement B { get; set; }
        public string Elements => (A.DisplayType ?? A.Category) + " #" + A.ElementId + " / " + (B.DisplayType ?? B.Category) + " #" + B.ElementId;
        public bool Matches(string level, string type, string search)
        {
            return (string.IsNullOrEmpty(level) || Level == level) &&
                (string.IsNullOrEmpty(type) || Type == type) &&
                (string.IsNullOrWhiteSpace(search) ||
                 (Id + " " + Type + " " + Level + " " + A.Label + " " + B.Label + " " + A.SystemName + " " + B.SystemName + " " + A.FamilyType + " " + B.FamilyType + " " + Notes)
                    .IndexOf(search.Trim(), StringComparison.OrdinalIgnoreCase) >= 0);
        }
    }

    public sealed class DashboardSnapshot
    {
        public string Project { get; set; }
        public string Title { get; set; }
        public string Summary { get; set; }
        public string SummaryStrip { get; set; }
        public BIMEngine.Core.Models.ScanConfig ScanConfig { get; set; }
        public List<ClashRow> Issues { get; set; } = new List<ClashRow>();
    }

    public delegate string SnapshotLoader(UIApplication app, bool rescan);
    public delegate void TriageWriter(UIApplication app, string payload);

    // All Revit operations run in command / ExternalEvent contexts. WPF only queues requests.
    public static class DashboardController
    {
        public static readonly DockablePaneId PaneId = new DockablePaneId(new Guid("836184A4-62B1-4EBC-B9DF-1282C16A58C2"));
        public static SnapshotLoader Loader { get; set; }
        public static TriageWriter Writer { get; set; }
        public static DashboardPage Page { get; private set; }
        public static DashboardSnapshot Snapshot { get; private set; }
        private static ExternalEvent externalEvent;
        private static Handler handler;
        private static bool busy;
        private static string observedProject;
        private static string observedView;
        public static bool Busy => busy;
        public static string LastError { get; private set; }

        public static void Initialize(UIApplication app)
        {
            if (Page != null) return;
            DashboardTheme.FollowRevit();
            var page = new DashboardPage();
            page.OwnerHandle = app.MainWindowHandle;
            var requestHandler = new Handler();
            var requestEvent = ExternalEvent.Create(requestHandler);
            try { app.RegisterDockablePane(PaneId, "BIM Engine · Clashes", page); }
            catch { requestEvent.Dispose(); throw; }
            Page = page;
            handler = requestHandler;
            externalEvent = requestEvent;
            app.Idling += OnIdle;
            app.ThemeChanged += (s, e) => DashboardTheme.FollowRevit();
            app.Application.DocumentChanged += (s,e) => { InspectionSession.Invalidate(e.GetDocument()); OverlapOverlay.Clear(); observedView=null; };
            app.Application.DocumentClosing += (s,e) => { InspectionSession.End(); observedView=null; };
        }

        private static string ActiveKey(UIApplication app)
        {
            var doc = app.ActiveUIDocument?.Document;
            return doc == null || doc.IsFamilyDocument || string.IsNullOrEmpty(doc.PathName) ? null : DocumentIdentity.Get(doc);
        }

        private static void OnIdle(object sender, IdlingEventArgs args)
        {
            var app = sender as UIApplication;
            if (app == null || busy) return;
            string key = ActiveKey(app);
            string view=key==null?null:key+"|"+app.ActiveUIDocument.ActiveView.Id.Value;
            if (key == observedProject)
            {
                if(view!=observedView)
                {
                    observedView=view;OverlapOverlay.Clear();
                    if(key!=null&&PinnedClashViews.IsOwned(app.ActiveUIDocument.ActiveView))Request("overlay");
                }
                return;
            }
            InspectionSession.End();observedView=view;
            observedProject = key;
            Snapshot = null;
            Page.Clear("Loading active project…");
            if (key == null) Page.Clear("Open and save a project to view its clashes.");
            else if (Loader != null) Request("load");
        }

        public static void Show(UIApplication app)
        {
            Load(app, false);
            app.GetDockablePane(PaneId).Show();
            Page.ActivateFloating();
        }

        public static void Load(UIApplication app, bool rescan)
        {
            InspectionSession.End();
            string project = ActiveKey(app);
            observedProject = project;
            if (project == null)
            {
                Snapshot = null;
                Page.Clear("Open and save a project to view its clashes.");
                return;
            }
            if (Loader == null) throw new InvalidOperationException("Open Issue Report to initialize the dashboard.");
            var serializer = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
            var snapshot = serializer.Deserialize<DashboardSnapshot>(Loader(app, rescan));
            if (snapshot.Project != project) throw new InvalidOperationException("Dashboard project changed while loading.");
            Snapshot = snapshot;
            LastError = null;
            Page.Display(snapshot);
        }

        public static void Request(string action)
        {
            if (busy || handler == null) return;
            if (action != "load" && action != "refresh" && action!="end" && action!="cleanup" && action!="overlay" && Page.Selected == null) return;
            handler.Action = action;
            handler.Row = Page.Selected;
            handler.Project = Snapshot?.Project ?? observedProject;
            handler.Margin = Page.ContextFeet;
            busy = true;
            Page.SetBusy(true, action == "refresh" ? "Scanning selected scope…" : "Opening clash…");
            if (action == "refresh") Page.UpdateScanProgress("Starting scan…", 0, 0);
            var status = externalEvent.Raise();
            if (status != ExternalEventRequest.Accepted && status != ExternalEventRequest.Pending)
            {
                busy = false;
                handler.Action = null;
                Page.SetBusy(false, "Revit is busy. Try again when the current command finishes.");
            }
        }

        public static void RequestTriage(string action, long[] ids, string text)
        {
            if (busy || handler == null || ids.Length == 0 || Snapshot == null) return;
            handler.Payload = new JavaScriptSerializer().Serialize(new { Project = Snapshot.Project, Ids = ids, Action = action, Text = text });
            Request("triage");
        }

        private sealed class Handler : IExternalEventHandler
        {
            public string Action, Project, Payload;
            public ClashRow Row;
            public double Margin;
            public string GetName() => "BIM Engine Dashboard";
            public void Execute(UIApplication app)
            {
                string action = Action;
                Action = null;
                try
                {
                    if (Project != ActiveKey(app))
                        throw new InvalidOperationException("Active project changed. Reopen Issue Report before continuing.");
                    if ((action == "3d" || action == "2d" || action == "section") && Row?.Id != Page.Selected?.Id)
                    { Page.SetBusy(false, "Ready"); return; }
                    if (action == "refresh" || action == "load") Load(app, action == "refresh");
                    else if (action == "triage")
                    {
                        if (Writer == null) throw new InvalidOperationException("Reopen the dashboard to initialize triage.");
                        Writer(app, Payload);
                        Page.TriageSaved();
                        Load(app, false);
                    }
                    else if(action=="overlay")PinnedClashViews.RestoreOverlay(app);
                    else DashboardNavigation.Navigate(app, Row, action, Margin);
                    LastError = null;
                    Page.SetBusy(false, action == "refresh"
                        ? (Snapshot?.Summary?.StartsWith("Partial", StringComparison.Ordinal) == true
                            ? "Scan complete · coverage warning. See Details."
                            : "Scan complete.")
                        : (action=="2d"||action=="3d"||action=="section"||action=="rotate")
                            ? "Temporary preview · project unchanged. "+InspectionSession.Scene?.Notice : action == "triage" ? "Triage saved." : "Ready");
                }
                catch (Exception ex)
                {
                    LastError = ex.Message;
                    Page.SetBusy(false, ex.Message);
                }
                finally { busy = false; Row = null; Payload = null; }
            }
        }
    }
}
