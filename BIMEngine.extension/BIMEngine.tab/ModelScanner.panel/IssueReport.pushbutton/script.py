#! python3
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib')))

def main():
    try:
        from bimengine_core.dashboard import show
        show(__revit__)
        return True
    except Exception as error:
        from Autodesk.Revit.UI import TaskDialog
        TaskDialog.Show('BIM Engine Dashboard', str(error))
        return False

if __name__ == '__main__':
    main()
