import copy
import json
import pathlib
import sqlite3
import types
import unittest
from contextlib import closing
import test_baseline as baseline
from test_baseline import issue, database, config

class LifecycleTests(unittest.TestCase):
    setUp = baseline.DatabaseTests.setUp
    tearDown = baseline.DatabaseTests.tearDown
    def save(self, issues, project='project-A', diagnostics=None, cfg=None):
        return database.save_scan_results(issues, 2, .1, project_key=project,
            config=cfg or config.DEFAULT_CONFIG, diagnostics=diagnostics)

    def test_reverse_pair_preserves_notes_and_review(self):
        data = issue()
        self.save([data])
        database.update_issue_status(1, 'Reviewed', 'Keep this note')
        data['element_a'], data['element_b'] = data['element_b'], data['element_a']
        self.save([data])
        self.assertEqual(1, len(database.get_open_issues('project-A')))
        row = database.get_issue_by_id(1)
        self.assertEqual(('Reviewed', 'Keep this note'), (row['Status'], row['Notes']))

    def test_same_title_different_projects(self):
        self.save([issue()])
        self.save([issue()], 'project-B')
        self.assertEqual(1, len(database.get_open_issues('project-A')))
        self.assertEqual(1, len(database.get_open_issues('project-B')))

    def test_repeated_link_instances_stay_separate(self):
        first, second = issue(), issue()
        for data, instance in ((first,'link-A'), (second,'link-B')):
            data['element_b'].update(is_linked=True, linked_ref_id=instance, document_key='linked-model')
        self.save([first,second])
        self.assertEqual(2, len(database.get_open_issues('project-A')))

    def test_clean_scope_resolves_then_reopens(self):
        self.save([issue()])
        self.save([])
        self.assertEqual([], database.get_open_issues('project-A'))
        self.save([issue()])
        self.assertEqual('Open', database.get_issue_by_id(1)['Status'])
        self.assertIsNone(database.get_issue_by_id(1)['ResolvedUtc'])

    def test_partial_scan_does_not_resolve(self):
        self.save([issue()])
        self.save([], diagnostics=['Unloaded link'])
        self.assertEqual(1, len(database.get_open_issues('project-A')))
        self.assertEqual('Partial', database.get_latest_scan('project-A')['State'])

    def test_narrower_scope_does_not_resolve(self):
        self.save([issue()])
        cfg = copy.deepcopy(config.DEFAULT_CONFIG)
        cfg['Categories'] = ['Pipes']
        self.save([], cfg=cfg)
        self.assertEqual(1, len(database.get_open_issues('project-A')))

    def test_invalid_status_rejected(self):
        self.save([issue()])
        with self.assertRaises(ValueError): database.update_issue_status(1, 'banana')

    def test_atomic_failed_scan_has_no_record(self):
        data=issue()
        del data['status']
        with self.assertRaises(KeyError): self.save([data])
        self.assertIsNone(database.get_latest_scan('project-A'))

    def test_legacy_migration_retains_data_and_backup(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            for table in ('Models','Elements','Issues','IssueLinks','BCFTopics','AIRecommendations','RFIs','AuditHistory'):
                conn.execute('CREATE TABLE '+table+' (Value TEXT)')
            conn.execute("INSERT INTO Issues VALUES ('historic note')")
        self.save([issue()])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual('historic note', conn.execute('SELECT Value FROM Legacy_Issues').fetchone()[0])
            self.assertEqual(3, conn.execute('PRAGMA user_version').fetchone()[0])
        self.assertEqual(1, len(list(pathlib.Path(self.tmp.name).glob('*.bak'))))

class ValidationTests(unittest.TestCase):
    def test_bad_config(self):
        for key, value in [('Categories',[]),('OctreeMaxDepth',100),('OctreeMaxObjectsPerNode',0),
                           ('CandidateQueryPaddingFeet',float('nan')),('IncludeLinkedDocuments','yes')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                config.validate_config({key:value})

    def test_document_guards(self):
        from bimengine_core.revit_bridge import validate_document
        for doc in (None, types.SimpleNamespace(IsFamilyDocument=True),
                    types.SimpleNamespace(IsFamilyDocument=False,Application=types.SimpleNamespace(VersionNumber='2025')),
                    types.SimpleNamespace(IsFamilyDocument=False,Application=types.SimpleNamespace(VersionNumber='2024'),PathName='')):
            with self.assertRaises(ValueError): validate_document(doc)

    def test_package_import_does_not_require_clr(self):
        import subprocess
        import sys
        result=subprocess.run([sys.executable,'-c',
            "import sys; sys.path.insert(0, {!r}); import bimengine_core; assert 'clr' not in sys.modules".format(str(baseline.LIB))],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)

if __name__ == '__main__': unittest.main(verbosity=2)
