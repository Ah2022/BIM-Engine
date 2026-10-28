"""Offline acceptance tests for the supplied baseline; failures are release blockers.

No Revit calls, user settings or production database writes. CLR is stubbed only
for bridge serialization/path tests; this does NOT validate pythonnet interop.
"""
import importlib.util
import pathlib
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import closing
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIB = ROOT / 'BIMEngine.extension' / 'lib'
PACKAGE = LIB / 'bimengine_core'
sys.path.insert(0, str(LIB))
from bimengine_core import database, config, rules


def element(eid=1):
    return dict(element_id=eid, category='Pipes', document_title='Test Model',
                is_linked=False, location_x=1, location_y=2, location_z=3,
                level_name='Level 1')


def issue():
    return dict(engine_source='ClashDetector', issue_type='HardClash',
                element_a=element(), element_b=element(2), overlap_depth_feet=.1,
                location_x=1, location_y=2, location_z=3, status='Open',
                detected_utc='2026-09-20T00:00:00Z')


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(pathlib.Path(self.tmp.name) / 'test.db')
        self.mock = patch.object(database, '_get_db_path', return_value=self.path)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.tmp.cleanup()

    def test_empty_report(self):
        self.assertEqual([], database.get_open_issues())

    def test_schema_and_roundtrip(self):
        database.save_scan_results([issue()], 2, .5)
        rows = database.get_open_issues()
        self.assertEqual(1, len(rows))
        self.assertEqual(1, rows[0]['revit_element_id_a'])
        with closing(sqlite3.connect(self.path)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        self.assertEqual(9, len(tables))

    def test_status_roundtrip(self):
        database.save_scan_results([issue()], 2, .5)
        self.assertTrue(database.update_issue_status(1, 'Resolved', 'Fixed'))
        self.assertEqual([], database.get_open_issues())
        self.assertIsNotNone(database.get_issue_by_id(1)['ResolvedUtc'])
        self.assertFalse(database.update_issue_status(999, 'Resolved'))

    def test_failed_batch_rolls_back(self):
        bad = issue()
        del bad['status']
        with self.assertRaises(KeyError):
            database.save_scan_results([issue(), bad], 2, .5)
        self.assertEqual([], database.get_open_issues())

    def test_repeat_scan_has_one_open_issue(self):
        database.save_scan_results([issue()], 2, .5)
        database.save_scan_results([issue()], 2, .5)
        self.assertEqual(1, len(database.get_open_issues()))

    def test_element_snapshot_refreshes(self):
        data = issue()
        database.save_scan_results([data], 2, .5)
        data['element_a']['location_x'] = 99
        database.save_scan_results([data], 2, .5)
        with closing(sqlite3.connect(self.path)) as conn:
            x = conn.execute('SELECT LocationX FROM Elements WHERE RevitElementId=1').fetchone()[0]
        self.assertEqual(99, x)


class ConfigTests(unittest.TestCase):
    def test_corrupt_json_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'config.json'
            path.write_text('{broken')
            with patch.object(config, 'USER_CONFIG_PATH', str(path)):
                self.assertEqual(config.DEFAULT_CONFIG, config.load_config())

    def test_default_categories_are_independent(self):
        with patch.object(config.os.path, 'isfile', return_value=False):
            first, second = config.load_config(), config.load_config()
        self.assertIsNot(first['Categories'], second['Categories'])

    def test_rules_are_phase_one_passthrough(self):
        data = [issue()]
        self.assertEqual(data, rules.filter_issues(data))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.clr = types.ModuleType('clr')
        self.clr.AddReference = lambda path: None
        with patch.dict(sys.modules, {'clr': self.clr}):
            spec = importlib.util.spec_from_file_location('bimengine_core.bridge_test', PACKAGE / 'revit_bridge.py')
            self.bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.bridge)

    def test_documented_bin_path_loads(self):
        expected = ROOT / 'BIMEngine.extension' / 'bin' / 'BIMEngine.Core.dll'
        with patch('os.path.isfile', side_effect=lambda p: pathlib.Path(p).resolve() == expected.resolve()):
            with patch.dict(sys.modules, {'clr': self.clr}):
                self.assertEqual(expected.resolve(), pathlib.Path(self.bridge._load_bimengine_dll()).resolve())

    def test_serialization_preserves_link_instance(self):
        e = types.SimpleNamespace(ElementId=1, Category='Pipes', DocumentTitle='Link',
            IsFromLinkedDocument=True, LinkedDocumentReferenceId='link-instance-A',
            LocationX=1, LocationY=2, LocationZ=3, LevelName='L1')
        obj = types.SimpleNamespace(EngineSource='ClashDetector', IssueType='HardClash',
            ElementA=e, ElementB=None, OverlapDepthFeet=.1, LocationX=1, LocationY=2,
            LocationZ=3, Status=types.SimpleNamespace(ToString=lambda: 'Open'),
            DetectedUtc=types.SimpleNamespace(ToString=lambda fmt: '2026-09-20'))
        result = self.bridge._issue_to_dict(obj)
        self.assertEqual('link-instance-A', result['element_a'].get('linked_ref_id'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
