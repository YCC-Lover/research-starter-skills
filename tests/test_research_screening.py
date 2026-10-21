"""Synthetic integration checks; reviewer responses here are fixtures, not model runs."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/research-starter-paper/resources/research-engine/sr-screener/scripts'


class ScreeningIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='rsk-screening-'))
        self.work = self.root / 'review'
        inputs = self.root / 'inputs'
        inputs.mkdir()
        self.records = inputs / 'synthetic.ris'
        entries = []
        for title in ('Synthetic thermal polymer experiment with an eligible comparator',
                      'Synthetic thermal polymer experiment with an eligible comparator',
                      'Synthetic durability experiment with a different treatment'):
            entries.append('TY  - JOUR\nTI  - ' + title + '\nAU  - Example, Author\n'
                           'PY  - 2024\nAB  - Synthetic test record, not a real publication. '
                           'A controlled polymer experiment is described.\nER  - \n')
        self.records.write_text('\n'.join(entries), encoding='utf-8')
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps({'review_title': 'Synthetic software test',
                                          'batching': {'max_records': 1}}), encoding='utf-8')
        self.protocol = self.root / 'protocol.md'
        self.protocol.write_text(
            '# Synthetic screening protocol for software tests\n'
            'This fixture is not an actual user protocol approval. Include controlled experiments '
            'on polymers with a treatment and a comparator. Exclude unrelated populations under E2. '
            'Retain uncertain records for full-text review. Do not infer missing methods or outcomes. '
            'The fixture tests state handling, not screening accuracy.\n', encoding='utf-8')

    def call(self, name, *args, success=True):
        env = {**os.environ, 'TEMP': str(self.root), 'TMP': str(self.root),
               'TMPDIR': str(self.root), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / name), *map(str, args)],
                                cwd=self.root, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=45)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def prepare(self):
        self.call('prepare_records.py', '--inputs', self.records, '--work', self.work,
                  '--config', self.config)

    def plan(self, suffix='first', pilot_n=1):
        out = self.root / (suffix + '.json')
        self.call('build_workflow.py', 'ta', '--work', self.work, '--config', self.config,
                  '--protocol', self.protocol, '--jobs', 'pilot', '--pilot-n', pilot_n, '--out', out)
        return json.loads(out.read_text(encoding='utf-8'))

    def test_import_deduplicates_but_preserves_raw_records(self):
        original = self.records.read_bytes()
        self.prepare()
        counts = json.loads((self.work / 'identification.json').read_text(encoding='utf-8'))
        self.assertEqual((counts['raw_total'], counts['unique_total'], counts['duplicates_removed']), (3, 2, 1))
        self.assertEqual(len(json.loads((self.work / 'raw_records.json').read_text(encoding='utf-8'))), 3)
        self.assertEqual(self.records.read_bytes(), original)

    def test_forced_reimport_does_not_delete_or_overwrite_prior_batches(self):
        self.prepare()
        before = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.call('prepare_records.py', '--inputs', self.records, '--work', self.work, '--force', success=False)
        after = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_native_plan_is_context_bound_and_not_execution(self):
        self.prepare()
        plan = self.plan()
        self.assertEqual(plan['schema'], 'rsk.screening-dispatch.v1')
        self.assertEqual(plan['dispatch_count'], 2)
        self.assertEqual(plan['execution'], 'not_started')
        self.assertEqual({row['role'] for row in plan['calls']}, {'A', 'B'})
        for row in plan['calls']:
            self.assertTrue(row['label'].endswith('@' + plan['context']['context_id']))
            self.assertEqual(row['model'], '')
            self.assertTrue(Path(row['prompt_file']).is_file())
            self.assertEqual(row['execution'], 'not_started')
        self.assertEqual(list(self.work.rglob('*.workflow.js')), [])

    def test_full_run_is_blocked_without_passing_pilot(self):
        self.prepare()
        self.plan()
        result = self.call('build_workflow.py', 'ta', '--work', self.work, '--config', self.config,
                           '--protocol', self.protocol, '--jobs', 'all', success=False)
        self.assertIn('pilot', result.stderr.lower())

    def test_amendment_preserves_superseded_decisions_as_files(self):
        self.prepare()
        previous = self.plan()
        old = self.work / 'decisions.json'
        saved = b'{"synthetic":"older decisions"}\n'
        old.write_bytes(saved)
        self.protocol.write_text(self.protocol.read_text(encoding='utf-8') +
                                 '\nAmendment: require a stated observation period.\n', encoding='utf-8')
        current = self.plan('amended')
        self.assertNotEqual(previous['context']['context_id'], current['context']['context_id'])
        archived = list((self.work / 'revision_archive').glob('*/decisions.json'))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_bytes(), saved)
        self.assertFalse(old.exists())

    def test_stale_context_results_do_not_become_screening_decisions(self):
        self.prepare()
        plan = self.plan()
        rid = plan['authorized_ids'][0]
        source = self.root / 'stale-results.json'
        source.write_text(json.dumps([{'label': row['label'].split('@')[0] + '@wrong-context',
                                      'decisions': [{'id': rid, 'd': 'include', 'code': 'INC',
                                                     'why': 'Synthetic response fixture.'}]}
                                     for row in plan['calls']]), encoding='utf-8')
        self.call('merge_decisions.py', '--work', self.work, '--config', self.config, '--from', source)
        decisions = json.loads((self.work / 'decisions.json').read_text(encoding='utf-8'))
        self.assertEqual(decisions, {})
        audit = json.loads((self.work / 'decision_audit.json').read_text(encoding='utf-8'))
        self.assertTrue(all(item['accepted_context'] is None for item in audit))


if __name__ == '__main__':
    unittest.main()
