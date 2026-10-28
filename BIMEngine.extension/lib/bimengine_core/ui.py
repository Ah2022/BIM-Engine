"""CPython-compatible UI backed by compiled WinForms; no pyrevit.forms."""
from .revit_bridge import _load_bimengine_dll, validate_document

def get_context(uiapp):
    doc = uiapp.ActiveUIDocument.Document if uiapp.ActiveUIDocument else None
    validate_document(doc)
    return doc, int(uiapp.MainWindowHandle.ToInt64())

def alert(owner, message):
    _load_bimengine_dll()
    from BIMEngine.Core import DesktopUi
    DesktopUi.Alert(owner, str(message))

def choose_categories(owner, choices, selected):
    _load_bimengine_dll()
    from BIMEngine.Core import DesktopUi
    from System import Array, String
    result = DesktopUi.ChooseCategories(owner, Array[String](choices), Array[String](selected))
    return list(result) if result is not None else None

def progress_window(owner):
    _load_bimengine_dll()
    from BIMEngine.Core import ScanProgressWindow
    return ScanProgressWindow(owner)

def show_report(owner, summary, columns, rows):
    _load_bimengine_dll()
    from BIMEngine.Core import DesktopUi
    from System import Array, String
    return int(DesktopUi.ShowReport(owner, summary, Array[String](columns),
        Array[Array[String]]([Array[String]([str(v) if v is not None else "-" for v in row]) for row in rows])))

