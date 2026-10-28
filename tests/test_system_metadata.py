import pathlib
import sqlite3
import unittest
from contextlib import closing
import test_baseline as baseline
from test_baseline import issue, database, config
from bimengine_core.dashboard import make_snapshot

class SystemMetadataTests(unittest.TestCase):
    setUp=baseline.DatabaseTests.setUp
    tearDown=baseline.DatabaseTests.tearDown

    def save(self,data):
        database.save_scan_results([data],2,.1,project_key='P',config=config.DEFAULT_CONFIG)

    def test_actual_types_not_generic_classification(self):
        data=issue()
        data['element_a'].update(system_type='Soil',system_classification='Sanitary',system_name='S-1',family_type='Pipe : PVC')
        data['element_b'].update(system_type='Waste',system_classification='Sanitary',system_name='W-1',family_type='Pipe : PVC')
        self.save(data)
        snap=make_snapshot('P','P',database.get_open_issues('P'),[],database.get_latest_scan('P'))
        row=snap['Issues'][0]
        self.assertEqual('Soil Pipe ↔ Waste Pipe',row['Type'])
        self.assertEqual('S-1',row['A']['SystemName'])
        self.assertEqual('Pipe : PVC',row['B']['FamilyType'])

    def test_rename_does_not_duplicate_issue_or_lose_notes(self):
        data=issue();data['element_a']['system_type']='Soil';self.save(data)
        database.update_issue_status(1,'Reviewed','Keep note')
        data['element_a']['system_type']='Black Water';self.save(data)
        rows=database.get_open_issues('P')
        self.assertEqual(1,len(rows));self.assertEqual('Black Water',rows[0]['system_type_a'])
        self.assertEqual('Reviewed',rows[0]['status']);self.assertEqual('Keep note',rows[0]['notes'])

    def test_v2_migration_preserves_rows_and_makes_backup(self):
        self.save(issue());database.update_issue_status(1,'Reviewed','Prior version note')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            for column in ('SystemType','SystemClassification','SystemName','FamilyType'):
                conn.execute('ALTER TABLE Elements DROP COLUMN '+column)
            conn.execute('PRAGMA user_version=2')
        rows=database.get_open_issues('P')
        self.assertEqual('Prior version note',rows[0]['notes'])
        self.assertIsNone(rows[0]['system_type_a'])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(3,conn.execute('PRAGMA user_version').fetchone()[0])
        backups=list(pathlib.Path(self.tmp.name).glob('*.pre-v3-*.bak'))
        self.assertEqual(1,len(backups))
        with closing(sqlite3.connect(str(backups[0]))) as conn:
            self.assertEqual(2,conn.execute('PRAGMA user_version').fetchone()[0])
        database.get_open_issues('P')
        self.assertEqual(1,len(list(pathlib.Path(self.tmp.name).glob('*.pre-v3-*.bak'))))

    def test_missing_and_multiple_system_labels(self):
        data=issue();data['element_b']['system_type']='Multiple systems: Supply / Return';self.save(data)
        row=make_snapshot('P','P',database.get_open_issues('P'),[],None)['Issues'][0]
        self.assertIn('Unassigned Pipe',row['Type'])
        self.assertIn('Multiple systems: Supply / Return Pipe',row['Type'])
