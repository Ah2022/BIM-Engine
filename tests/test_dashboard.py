import copy
import json
import unittest
import test_baseline as baseline
from test_baseline import database, issue, config
from bimengine_core.dashboard import make_snapshot


class DashboardTests(unittest.TestCase):
    setUp = baseline.DatabaseTests.setUp
    tearDown = baseline.DatabaseTests.tearDown

    def snapshot(self, levels=None):
        return make_snapshot('project-A', 'Project A', database.get_open_issues('project-A'),
                             levels or [('Ground', 0, 100), ('First', 10, 101)], database.get_latest_scan('project-A'))

    def save(self, data, diagnostics=None, cfg=None):
        database.save_scan_results(data, 2, .1, project_key='project-A', config=cfg or config.DEFAULT_CONFIG, diagnostics=diagnostics)

    def test_preview_bounds_coordinates_and_identity_survive_database(self):
        data = issue()
        data.update(location_x=101, location_y=202, location_z=12)
        data['element_a'].update(document_key='host', bounds_min_x=100, bounds_min_y=201, bounds_max_x=103, bounds_max_y=205)
        data['element_b'].update(document_key='link', is_linked=True, linked_ref_id='instance-2')
        self.save([data])
        row = self.snapshot()['Issues'][0]
        self.assertEqual(('First', 101, 101, 202, 12), (row['Level'], row['LevelId'], row['X'], row['Y'], row['Z']))
        self.assertEqual('host', row['A']['DocumentKey'])
        self.assertEqual((100, 205), (row['A']['MinX'], row['A']['MaxY']))
        self.assertEqual('instance-2', row['B']['LinkId'])

    def test_level_fallback_and_origin_are_valid(self):
        data = issue(); data.update(location_x=0, location_y=0, location_z=0)
        self.save([data])
        self.assertEqual('Ground', self.snapshot()['Issues'][0]['Level'])
        self.assertEqual('Unassigned', self.snapshot([('Above', 10, 101)])['Issues'][0]['Level'])

    def test_pair_type_is_order_independent(self):
        data = issue()
        self.save([data]); first = self.snapshot()['Issues'][0]['Type']
        data['element_a'], data['element_b'] = data['element_b'], data['element_a']
        self.save([data])
        self.assertEqual(first, self.snapshot()['Issues'][0]['Type'])

    def test_refresh_removes_solved_but_preserves_history_and_notes(self):
        self.save([issue()]); database.update_issue_status(1, 'Reviewed', 'Coordination note')
        self.save([])
        self.assertEqual([], self.snapshot()['Issues'])
        self.assertEqual('Resolved', database.get_issue_by_id(1)['Status'])
        self.assertEqual('Coordination note', database.get_issue_by_id(1)['Notes'])
        self.save([issue()])
        self.assertEqual('Open', self.snapshot()['Issues'][0]['Status'])
        self.assertEqual('Coordination note', self.snapshot()['Issues'][0]['Notes'])

    def test_partial_refresh_does_not_hide_unsolved_clashes(self):
        self.save([issue()]); self.save([], diagnostics=['Unloaded link'])
        snap = self.snapshot()
        self.assertEqual(1, len(snap['Issues']))
        self.assertIn('absent clashes retained', snap['Summary'])
        self.assertIn('Unloaded link', snap['Summary'])

    def test_other_scope_and_project_remain_separate(self):
        self.save([issue()]); cfg = copy.deepcopy(config.DEFAULT_CONFIG); cfg['Categories'] = ['Pipes']
        self.save([], cfg=cfg)
        self.assertEqual(1, len(self.snapshot()['Issues']))
        self.assertEqual([], make_snapshot('other', 'Other', database.get_open_issues('other'), [], None)['Issues'])

    def test_empty_project_shows_rescan_instruction(self):
        self.assertIn('press Scan', self.snapshot()['Summary'])

    def test_scan_summary_changes_persist_and_are_scope_safe(self):
        self.save([issue()])
        self.assertEqual('1 active · 1 new · 0 resolved', self.snapshot()['SummaryStrip'])
        self.save([issue()])
        self.assertEqual('1 active · 0 new · 0 resolved', self.snapshot()['SummaryStrip'])
        self.save([], diagnostics=['Unloaded link'])
        self.assertEqual('1 active · 0 new · 0 resolved · coverage warning', self.snapshot()['SummaryStrip'])
        cfg = copy.deepcopy(config.DEFAULT_CONFIG); cfg['Categories'] = ['Ducts']
        self.save([], cfg=cfg)
        self.assertEqual('1 active · 0 new · 0 resolved', self.snapshot()['SummaryStrip'])
        self.assertEqual(cfg, self.snapshot()['ScanConfig'])
        self.save([])
        self.assertEqual('0 active · 0 new · 1 resolved', self.snapshot()['SummaryStrip'])
        self.save([issue()])
        self.assertEqual('1 active · 0 new · 0 resolved', self.snapshot()['SummaryStrip'])

    def test_older_scan_does_not_invent_change_counts(self):
        self.save([issue()])
        latest = database.get_latest_scan('project-A'); latest.pop('Changes')
        snap = make_snapshot('project-A', 'Project A', database.get_open_issues('project-A'), [], latest)
        self.assertEqual('1 active · — new · — resolved', snap['SummaryStrip'])

    def test_raw_scan_metrics_are_available_in_details(self):
        database.save_scan_results([issue()], 2, .1, project_key='project-A', config=config.DEFAULT_CONFIG,
                                   metrics=dict(candidate_pairs=3, geometry_fetches=2))
        self.assertIn('Candidate pairs: 3 | Geometry fetches: 2', self.snapshot()['Summary'])
