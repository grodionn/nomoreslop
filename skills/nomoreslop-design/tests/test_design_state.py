import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/design_state.py'
spec = importlib.util.spec_from_file_location('tested_design_state', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'view.html').write_text('<h1>Current</h1>', encoding='utf-8')
        (self.root / 'content.md').write_text('Current', encoding='utf-8')

    def state(self):
        return {'schema_version': 1, 'mode': 'new', 'content_path': 'content.md',
                'intent': {'visitor': 'Compare real works', 'material': 'Three actual works', 'distinctive_result': 'Synchronized view of the same detail'},
                'brief': [{'id': 'scope', 'status': 'delegated', 'basis': {'type': 'delegation', 'reference': 'user turn 1', 'text': 'Choose all design decisions using the supplied material'}}],
                'decisions': [], 'checks': [self.check()]}

    def check(self):
        return {'id': 'view', 'kind': 'visual', 'status': 'passed',
                'files': {'view.html': module.file_hash(self.root / 'view.html')},
                'environment': {'method': 'browser-render', 'viewport': {'width': 1440, 'height': 900}},
                'action': 'Open current comparison', 'observation': 'Three works retain common scale',
                'evidence': ['work/current-wide.png']}

    def test_current_hashes_are_only_structurally_consistent(self):
        result = module.check_state(self.state(), self.root)
        self.assertEqual(result['status'], 'structurally_consistent')
        self.assertIn('declarations', result['warnings'][0])

    def test_replacing_file_reopens_only_affected_check(self):
        state = self.state()
        other = self.check(); other.update(id='other', files={'content.md': module.file_hash(self.root / 'content.md')}, kind='copy')
        state['checks'].append(other)
        (self.root / 'view.html').write_text('<h1>Changed</h1>', encoding='utf-8')
        result = module.check_state(state, self.root)
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['stale'], [{'check': 'view', 'path': 'view.html'}])

    def test_proposed_is_not_a_closed_answer(self):
        state = self.state(); state['brief'][0]['status'] = 'proposed'
        self.assertEqual(module.check_state(state, self.root)['status'], 'incomplete')

    def test_claimed_delegation_requires_reference_and_text(self):
        state = self.state(); state['brief'][0]['basis'] = {'type': 'delegation'}
        self.assertEqual(module.check_state(state, self.root)['status'], 'invalid')

    def test_missing_material_not_solved_by_contact(self):
        state = self.state(); state['intent']['material'] = ''; state['intent']['contact'] = '@studio'
        self.assertEqual(module.check_state(state, self.root)['status'], 'incomplete')

    def test_dom_harness_cannot_claim_visual_render(self):
        state = self.state(); state['checks'][0]['environment']['method'] = 'happy-dom'
        self.assertEqual(module.check_state(state, self.root)['status'], 'invalid')

    def test_unverified_retains_concrete_reason_and_pending(self):
        state = self.state(); state['checks'][0] = {'kind': 'visual', 'status': 'unverified', 'reason': 'Browser unavailable'}
        self.assertEqual(module.check_state(state, self.root)['status'], 'incomplete')

    def test_failed_cannot_be_passed_by_other_success(self):
        state = self.state(); state['checks'].append({'kind': 'function', 'status': 'failed'})
        self.assertEqual(module.check_state(state, self.root)['status'], 'invalid')

    def test_project_path_escape_rejected(self):
        state = self.state(); state['checks'][0]['files'] = {'../outside.html': '0' * 64}
        self.assertEqual(module.check_state(state, self.root)['status'], 'invalid')

    def test_local_fix_does_not_require_new_brief(self):
        state = {'schema_version': 1, 'mode': 'local', 'brief': [], 'checks': [self.check()]}
        self.assertEqual(module.check_state(state, self.root, 'local')['status'], 'structurally_consistent')

    def test_malformed_arrays_are_explicit_errors(self):
        state = self.state(); state['brief'] = 'incorrect'; state['decisions'] = 4
        self.assertEqual(module.check_state(state, self.root)['status'], 'invalid')

    def test_nested_checks_also_get_freshness_check(self):
        state = self.state(); state['checks'] = []
        state['decisions'] = [{'id': 'gallery', 'checks': [self.check()]}]
        self.assertEqual(module.check_state(state, self.root)['status'], 'structurally_consistent')

    def test_init_does_not_overwrite_existing_state(self):
        target = self.root / 'state.json'
        result = subprocess.run([sys.executable, str(SCRIPT), 'init', '--output', str(target)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        before = target.read_bytes()
        again = subprocess.run([sys.executable, str(SCRIPT), 'init', '--output', str(target)], capture_output=True)
        self.assertEqual(again.returncode, 2); self.assertEqual(target.read_bytes(), before)

    def test_snapshot_hashes_only_selected_files(self):
        result = subprocess.run([sys.executable, str(SCRIPT), 'snapshot', '--project', str(self.root), '--path', 'view.html'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(set(json.loads(result.stdout)['files']), {'view.html'})


if __name__ == '__main__':
    unittest.main()
