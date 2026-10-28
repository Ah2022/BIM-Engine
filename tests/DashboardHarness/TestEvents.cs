using System;
using Autodesk.Revit.UI;

namespace BIMEngine.Tests
{
    // Test-only adapter: document switches and link load/unload must not happen
    // inside Idling API event handlers. This assembly is never installed.
    public sealed class TestEvents : IExternalEventHandler
    {
        private static ExternalEvent externalEvent;
        private static Action<UIApplication> callback;
        public static bool Pending { get; private set; }
        public static string Error { get; private set; }
        public static void Initialize() { externalEvent = ExternalEvent.Create(new TestEvents()); }
        public static void Request(Action<UIApplication> action)
        {
            callback = action; Error = null; Pending = true; externalEvent.Raise();
        }
        public string GetName() => "BIM Engine isolated fixture action";
        public void Execute(UIApplication app)
        {
            try { callback(app); }
            catch (Exception ex) { Error = ex.ToString(); }
            finally { callback = null; Pending = false; }
        }
    }
}
