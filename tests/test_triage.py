import copy
import unittest
import test_baseline as baseline
from test_baseline import database, issue, config
from bimengine_core.dashboard import make_snapshot


class TriageTests(unittest.TestCase):
    setUp = baseline.DatabaseTests.setUp
    tearDown = baseline.DatabaseTests.tearDown

    def save(self, rows, project='A'):
        database.save_scan_results(rows, 2, .1, project_key=project, config=config.DEFAULT_CONFIG)

    def snapshot(self):
        return make_snapshot('A', 'A', database.get_open_issues('A', include_closed=True), [], database.get_latest_scan('A'))

    def test_new_recurring_and_legacy_age(self):
        self.save([issue()])
        self.assertEqual('New', self.snapshot()['Issues'][0]['Age'])
        self.save([issue()])
        self.assertEqual('Recurring', self.snapshot()['Issues'][0]['Age'])
        self.save([])
        self.save([issue()])
        self.assertEqual('Recurring', self.snapshot()['Issues'][0]['Age'])
        latest = database.get_latest_scan('A'); latest['Changes'].pop('new_ids')
        legacy = make_snapshot('A', 'A', database.get_open_issues('A'), [], latest)
        self.assertEqual('Unknown', legacy['Issues'][0]['Age'])

    def test_status_note_assignment_survive_rescan(self):
        self.save([issue()])
        database.triage_issues('A', [1], 'review')
        database.triage_issues('A', [1], 'note', 'Check with structure')
        database.triage_issues('A', [1], 'assign', 'Sam')
        database.triage_issues('A', [1], 'assign', 'Amira')
        self.save([issue()])
        row = self.snapshot()['Issues'][0]
        self.assertEqual('Reviewed', row['Status'])
        self.assertEqual('Amira', row['Assignee'])
        self.assertEqual('Check with structure\nAssigned to: Sam\nAssigned to: Amira', row['Notes'])

    def test_bulk_ignore_and_closed_rows_are_queryable(self):
        second = copy.deepcopy(issue()); second['element_b']['element_id'] = 3
        self.save([issue(), second])
        database.triage_issues('A', [1, 2], 'ignore')
        self.save([issue(), second])
        self.assertEqual([], database.get_open_issues('A'))
        snap = self.snapshot()
        self.assertEqual(['Ignored', 'Ignored'], [r['Status'] for r in snap['Issues']])
        self.assertTrue(snap['SummaryStrip'].startswith('0 active'))

    def test_wrong_project_bulk_request_rolls_back_every_row(self):
        self.save([issue()]); self.save([issue()], 'B')
        with self.assertRaises(ValueError):
            database.triage_issues('A', [1, 2], 'ignore')
        self.assertEqual('Open', database.get_issue_by_id(1)['Status'])
        self.assertEqual('Open', database.get_issue_by_id(2)['Status'])

    def test_resolved_note_preserves_resolution(self):
        self.save([issue()]); self.save([])
        before = database.get_issue_by_id(1)['ResolvedUtc']
        database.triage_issues('A', [1], 'note', 'Verified')
        row = database.get_issue_by_id(1)
        self.assertEqual(('Resolved', before), (row['Status'], row['ResolvedUtc']))
        self.assertEqual('Resolved', self.snapshot()['Issues'][0]['Status'])

    def test_invalid_edits_do_not_mutate(self):
        self.save([issue()])
        for action, text in [('note', '  '), ('assign', 'Sam\nAmira'), ('delete', '')]:
            with self.assertRaises(ValueError):
                database.triage_issues('A', [1], action, text)
        self.assertEqual('Open', database.get_issue_by_id(1)['Status'])

    def test_mep_structure_pair_is_symmetric(self):
        data = issue(); data['element_b']['category'] = 'Structural Framing'
        self.save([data]); row = self.snapshot()['Issues'][0]
        self.assertTrue(row['IsMepStructure'])
        self.assertEqual('Plumbing ↔ Structure', row['DisciplinePair'])
        data['element_a'], data['element_b'] = data['element_b'], data['element_a']
        self.save([data]); self.assertTrue(self.snapshot()['Issues'][0]['IsMepStructure'])
