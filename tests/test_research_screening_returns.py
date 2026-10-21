"""Native return fixtures exercise cumulative replay, not model accuracy."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import test_research_screening as screening_fixture

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / 'skills/research-starter-paper/scripts'
sys.path.insert(0, str(ADAPTERS))
SPEC = importlib.util.spec_from_file_location('native_screening_returns', ADAPTERS / 'research_screening.py')
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)


class NativeScreeningReturnTests(unittest.TestCase):
    def setUp(self):
        self.fixture = screening_fixture.ScreeningIntegrationTests('test_import_deduplicates_but_preserves_raw_records')
        self.fixture.setUp()
        self.fixture.config.write_text(json.dumps({'batching': {'max_records': 3}}), encoding='utf-8')
        self.fixture.prepare()
        self.plan = self.fixture.plan()
        self.plan_path = self.fixture.root / 'first.json'

    def collect_call(self, plan_path, call, actor):
        path = self.fixture.root / (actor + '-response.json')
        path.write_text(json.dumps({'decisions': [
            {'id': rid, 'd': 'exclude', 'code': 'E2', 'why': 'Synthetic return fixture only.'}
            for rid in self.plan['authorized_ids']]}), encoding='utf-8')
        return NATIVE.collect(plan_path, call['label'], path, actor)

    def merge(self):
        self.assertEqual(NATIVE.merge(self.fixture.work, 'ta', self.fixture.config), 0)
        return json.loads((self.fixture.work / 'decisions.json').read_text(encoding='utf-8'))

    def test_incremental_qc_replays_prior_ab_returns(self):
        for call in self.plan['calls']:
            self.collect_call(self.plan_path, call, 'fixture-context-' + call['role'])
        self.assertEqual(len(self.merge()), 2)
        qc_plan = self.fixture.root / 'qc-plan.json'
        self.fixture.call('build_workflow.py', 'ta', '--work', self.fixture.work,
                          '--config', self.fixture.config, '--protocol', self.fixture.protocol,
                          '--jobs', 'recheck', '--out', qc_plan)
        call = json.loads(qc_plan.read_text(encoding='utf-8'))['calls'][0]
        self.collect_call(qc_plan, call, 'fixture-context-qc')
        decisions = self.merge()
        self.assertEqual(len(decisions), 2)
        self.assertEqual({row['final']['d'] for row in decisions.values()}, {'exclude'})
        self.assertEqual(len(list((self.fixture.work / 'codex-results').glob('*.meta.json'))), 3)

    def test_reused_context_for_other_role_is_rejected(self):
        self.collect_call(self.plan_path, self.plan['calls'][0], 'same-fixture-context')
        with self.assertRaisesRegex(ValueError, 'different actor contexts'):
            self.collect_call(self.plan_path, self.plan['calls'][1], 'same-fixture-context')

    def test_changed_prompt_or_return_is_rejected(self):
        call = self.plan['calls'][0]
        result = self.collect_call(self.plan_path, call, 'fixture-a')
        Path(result['result']).write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'differ from their receipt'):
            self.merge()
        Path(call['prompt_file']).write_text('changed prompt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Prompt bytes changed'):
            self.collect_call(self.plan_path, call, 'fixture-b')


if __name__ == '__main__':
    unittest.main()
