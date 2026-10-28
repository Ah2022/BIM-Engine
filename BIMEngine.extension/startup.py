#! python3
"""Register the compiled dockable pane once per Revit session."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
try:
    from bimengine_core.dashboard import initialize
    initialize(__revit__)
except Exception as error:
    print('BIM Engine dashboard startup: {}'.format(error))
