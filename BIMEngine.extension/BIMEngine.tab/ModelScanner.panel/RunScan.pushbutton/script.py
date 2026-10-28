#! python3
# -*- coding: utf-8 -*-
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "lib")))
from bimengine_core.dashboard import show


def main():
    try:
        show(__revit__)
    except Exception as ex:
        from Autodesk.Revit.UI import TaskDialog
        TaskDialog.Show("BIM Engine", str(ex))


if __name__ == "__main__":
    main()
