"""Exercise actual bundled helper contracts through the local launcher."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'skills/research-starter-paper/scripts/research_engine.py'


class LocalResearchToolsTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-local-tools-'))

    def call(self, script, *args):
        return subprocess.run([sys.executable, '-B', str(LAUNCHER), 'run-local',
                               '--work-dir', str(self.work), script, '--', *map(str, args)],
                              cwd=self.work, capture_output=True, text=True, encoding='utf-8',
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'},
                              timeout=60)

    def test_changed_numbers_and_references_are_detected(self):
        source = self.work / 'source.md'
        revision = self.work / 'revision.md'
        source.write_text('The observed change was 12% [@source2024].\n', encoding='utf-8')
        revision.write_text('The observed change was 21% [@different2025].\n', encoding='utf-8')
        result = self.call('scripts/check_revision_token_conservation.py', 'pair',
                           '--source', source, '--revision', revision, '--strict')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('12', result.stdout)
        self.assertIn('21', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_advisory_exit_zero_does_not_mean_tokens_conserved(self):
        source = self.work / 'before.md'
        revision = self.work / 'after.md'
        source.write_text('The result was 12%.\n', encoding='utf-8')
        revision.write_text('The result was 21%.\n', encoding='utf-8')
        result = self.call('scripts/check_revision_token_conservation.py', 'pair',
                           '--source', source, '--revision', revision)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)['conserved'])

    def test_unchanged_protected_tokens_pass(self):
        source = self.work / 'source.md'
        revision = self.work / 'revision.md'
        source.write_text('The result was 12% [@source2024].\n', encoding='utf-8')
        revision.write_text('We observed a result of 12% [@source2024].\n', encoding='utf-8')
        result = self.call('scripts/check_revision_token_conservation.py', 'pair',
                           '--source', source, '--revision', revision)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_reproducibility_optout_is_distinct_from_missing_field(self):
        path = self.work / 'passport.yaml'
        path.write_text('repro_lock: null\n', encoding='utf-8')
        opted_out = self.call('scripts/check_repro_lock.py', path)
        self.assertEqual(opted_out.returncode, 0, opted_out.stderr)
        self.assertIn('WARN', opted_out.stderr)
        path.write_text('project: synthetic\n', encoding='utf-8')
        missing = self.call('scripts/check_repro_lock.py', path)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('missing', missing.stdout)

    def test_invalid_experiment_provenance_is_not_accepted(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest('Optional runtime dependency jsonschema is unavailable.')
        path = self.work / 'passport.yaml'
        path.write_text('experiment_provenance:\n  - experiment_id: synthetic\n', encoding='utf-8')
        result = self.call('scripts/check_experiment_provenance.py', path)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn('required', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_run_ledger_preserves_exact_words_and_file_changes(self):
        passport = self.work / 'passport.yaml'
        passport.write_text('project: synthetic test\n', encoding='utf-8')
        entry = self.work / 'entry.json'
        words = 'Synthetic instruction: review only; do not rewrite the manuscript.'
        entry.write_text(json.dumps({'kind': 'initial_instructions', 'user_words': words}), encoding='utf-8')
        recorded = self.call('scripts/run_ledger.py', 'append', '--passport-path', passport, '--entry-file', entry)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        draft = self.work / 'draft.md'
        draft.write_text('Synthetic version one.\n', encoding='utf-8')
        entry.write_text(json.dumps({'kind': 'file_reference', 'path': str(draft), 'role': 'input draft'}), encoding='utf-8')
        recorded = self.call('scripts/run_ledger.py', 'append', '--passport-path', passport, '--entry-file', entry)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        shown = self.call('scripts/run_ledger.py', 'show', '--passport-path', passport)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn(words, shown.stdout)
        draft.write_text('Synthetic changed version.\n', encoding='utf-8')
        report = self.call('scripts/run_ledger.py', 'report', '--passport-path', passport)
        self.assertEqual(report.returncode, 1, report.stderr + report.stdout)
        self.assertIn('changed', report.stdout)

    def test_anchoring_is_idempotent_and_hash_bound(self):
        draft = self.work / 'draft.md'
        draft.write_text('# Synthetic heading\n\nOne paragraph with 12 samples.\n\nAnother paragraph.\n', encoding='utf-8')
        manifest = self.work / 'blocks.json'
        result = self.call('scripts/ars_anchorize_draft.py', draft, '--manifest-out', manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        anchored = draft.read_bytes()
        first = manifest.read_bytes()
        result = self.call('scripts/ars_anchorize_draft.py', draft, '--manifest-out', manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(draft.read_bytes(), anchored)
        self.assertEqual(manifest.read_bytes(), first)
        self.assertTrue(json.loads(first)['blocks'])


if __name__ == '__main__':
    unittest.main()
