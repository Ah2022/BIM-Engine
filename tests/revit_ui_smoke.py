#! python3
"""Exercise real CPython button entry points in a fresh Revit runner session.
The timer interacts only with this test's BIM Engine dialogs.
"""
import os
import sys
import json
import runpy
import traceback
import hashlib
ROOT = r'C:\Users\TK56\Downloads\BIMEngine_Phase1_Hybrid'
EXTENSION=os.environ.get('BIMENGINE_EXTENSION_PATH',os.path.join(ROOT,'BIMEngine.extension'))
sys.path.insert(0, os.path.join(EXTENSION,'lib'))
report={'status':'running','checks':[]}
report['extension_path']=EXTENSION
with open(os.path.join(EXTENSION,'bin','BIMEngine.Core.dll'),'rb') as binary:
    report['dll_sha256']=hashlib.sha256(binary.read()).hexdigest()
try:
    import clr
    clr.AddReference('System.Windows.Forms')
    from System.Windows.Forms import Application, Timer, Button, CheckedListBox
    from bimengine_core import config, database
    from bimengine_core.revit_bridge import document_key
    runpy.run_path(os.path.join(ROOT,'tests','revit_integration.py'),init_globals={'__revit__':__revit__},run_name='__main__')
    with open(os.path.join(ROOT,'verification','latest-revit-result.json')) as stream:
        previous=json.load(stream)
    fixture=previous['run_directory']
    os.environ['BIMENGINE_DB_PATH']=os.path.join(fixture,'ui-issues.db')
    config.USER_CONFIG_DIR=fixture
    config.USER_CONFIG_PATH=os.path.join(fixture,'ui-config.json')
    cfg=dict(config.DEFAULT_CONFIG)
    cfg['Categories']=['Structural Columns']
    config.save_config(cfg)
    uidoc=__revit__.OpenAndActivateDocument(os.path.join(fixture,'host.rvt'))
    doc=uidoc.Document
    root=os.path.join(EXTENSION,'BIMEngine.tab','ModelScanner.panel')

    timer=Timer()
    timer.Interval=250
    clicked=[]
    expected_selection=[]
    def tick(sender,args):
        for form in list(Application.OpenForms):
            if form.Text == 'BIM Engine - Categories':
                checked=[c for c in form.Controls if isinstance(c,CheckedListBox)][0]
                selected=[str(item) for item in checked.CheckedItems]
                if selected!=['Structural Columns']:
                    raise AssertionError('Saved categories not preselected: '+str(selected))
                button=[c for c in form.Controls if isinstance(c,Button)][0]
                clicked.append('categories-save')
                button.PerformClick()
    timer.Tick += tick
    timer.Start()
    # Alert is a native MessageBox, so use a test shim to capture only confirmation
    # messages. Category dialog and progress window are the real production controls.
    from bimengine_core import ui
    messages=[]
    ui.alert=lambda owner,message: messages.append(str(message))
    runpy.run_path(os.path.join(root,'Settings.pushbutton','script.py'),init_globals={'__revit__':__revit__},run_name='__main__')
    report['checks'].append({'name':'settings dialog saves selected categories','passed':any(m.startswith('Saved categories: Structural Columns') for m in messages) and config.load_config()['Categories']==['Structural Columns']})
    command=runpy.run_path(os.path.join(root,'RunScan.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    result=command['main']()
    issues=database.get_open_issues(document_key(doc))
    report['checks'].append({'name':'Run Scan entry point persists expected clashes','passed':result is not None and len(issues)==4,'actual':len(issues)})
    command=runpy.run_path(os.path.join(root,'IssueReport.pushbutton','script.py'),init_globals={'__revit__':__revit__})
    success=command['main']()
    from BIMEngine.Core.Dashboard import DashboardController, DashboardNavigation
    report['checks'].append({'name':'dockable report displays four real issues','passed':DashboardController.Page.VisibleCount==4})
    host_row=next(row for row in sorted(DashboardController.Snapshot.Issues,key=lambda row:row.Id) if not row.A.LinkId and not row.B.LinkId)
    DashboardController.Page.SelectIssue(host_row.Id)
    expected_selection[:]=[host_row.A.ElementId,host_row.B.ElementId]
    DashboardNavigation.Navigate(__revit__,DashboardController.Page.Selected,'select',6.0)
    clicked.append('report-select-host')
    timer.Stop()
    report['messages']=messages
    report['dialog_actions']={name:clicked.count(name) for name in set(clicked)}
    actual_selection=sorted(int(e.Value) for e in uidoc.Selection.GetElementIds())
    report['checks'].append({'name':'Issue Report selects exact host elements by issue identity','passed':success and 'report-select-host' in clicked and actual_selection==sorted(expected_selection),'expected':sorted(expected_selection),'actual':actual_selection})
    report['status']='passed' if all(c['passed'] for c in report['checks']) else 'failed'
except Exception:
    report['status']='failed'
    report['error']=traceback.format_exc()
finally:
    with open(os.path.join(ROOT,'verification','revit-ui-result.json'),'w') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps(report,indent=2))
