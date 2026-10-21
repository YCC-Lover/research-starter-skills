"""CLI-only synthetic export tests. Retain fixtures; no models, network or cleanup."""

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'skills/research-starter-paper/resources/research-engine'
SCRIPTS = ENGINE / 'sr-screener/scripts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_entries(path):
    # The exporter writes comment headers followed by a JSON-compatible YAML sequence.
    return json.loads('\n'.join(line for line in path.read_text(encoding='utf-8').splitlines()
                                if not line.startswith('#')))


class ScreeningExportTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get('TMPDIR') or tempfile.gettempdir()).resolve()
        if os.name == 'nt' and base.drive.upper() == 'C:':
            self.fail('Set TEMP/TMP/TMPDIR to an explicit non-C test directory')
        self.root = Path(tempfile.mkdtemp(prefix='rsk-export-', dir=base))
        self.work = self.root / 'work'
        self.out = self.root / 'exports'
        self.config = self.root / 'config.json'
        self.dump(self.config, {'batching': {'max_records': 1},
                               'models': {'A': 'configured-not-observed'},
                               'model_labels': {'A': 'unattested-label'},
                               'agent_type': 'screening_reviewer_agent'})
        self.protocol = self.root / 'protocol.md'
        self.protocol.write_text(
            '# Synthetic software fixture, not real review approval\n'
            'Include controlled polymer experiments with treatment and comparator. '
            'Exclude unrelated populations under E2, retaining uncertainty for full-text review. '
            'Do not infer missing methodology, data, authorship, execution, human approval or model identity. '
            'These records and decisions test software behavior only.\n', encoding='utf-8')
        self.source = self.root / 'synthetic.ris'
        self.source.write_text('\n'.join(
            f'TY  - JOUR\nTI  - Synthetic {topic} experiment\nAU  - Example, Researcher\n'
            'PY  - 2024\nAB  - Synthetic record for software tests only.\nER  - \n'
            for topic in ('polymer', 'ceramic', 'metal')), encoding='utf-8')

    @staticmethod
    def dump(path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

    @staticmethod
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))

    def cli(self, script, *args, success=True):
        env = {**os.environ, 'TEMP': str(self.root), 'TMP': str(self.root), 'TMPDIR': str(self.root),
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        # -S deterministically exercises stdlib CSV fallback, avoiding third-party temp cleanup.
        result = subprocess.run([sys.executable, '-B', '-S', str(SCRIPTS / script), *map(str, args)],
                                cwd=self.root, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def prepare(self):
        self.cli('prepare_records.py', '--inputs', self.source, '--work', self.work, '--config', self.config)
        path = self.root / 'plan.json'
        self.cli('build_workflow.py', 'ta', '--work', self.work, '--protocol', self.protocol,
                 '--config', self.config, '--jobs', 'pilot', '--pilot-n', '3', '--out', path)
        self.plan = self.read(path)

    def merge(self, n=3, stage='ta', decision='include'):
        plan = self.plan if stage == 'ta' else self.ft_plan
        ids = plan['authorized_ids'] if stage == 'ta' else [row['id'] for row in self.read(self.work / 'ft_manifest.json')]
        allowed = set(ids[:n])
        batches = {row['batch']: row['ids'] for row in self.read(self.work / 'manifest.json')}
        responses = []
        for call in plan['calls']:
            target = call['label'].split(':', 1)[1].split('@', 1)[0]
            ids = batches[target] if stage == 'ta' else [target]
            decisions = [{'id': rid, 'd': decision, 'code': 'INC' if decision == 'include' else 'UNC',
                          'why': 'Synthetic fixture, not a model decision.', 'where': 'p1 Synthetic fixture'}
                         for rid in ids if rid in allowed]
            if decisions:
                responses.append({'label': call['label'], 'decisions': decisions})
        result_path = self.root / (uuid.uuid4().hex + '-responses.json')
        self.dump(result_path, responses)
        self.cli('merge_decisions.py', '--work', self.work, '--config', self.config,
                 '--stage', stage, '--from', result_path)

    def prepare_ft(self):
        self.merge()
        pdfs = self.root / 'pdfs'
        pdfs.mkdir()
        for rid in self.plan['authorized_ids']:
            (pdfs / (rid + '.pdf')).write_bytes(b'%PDF-1.4\nSynthetic placeholder; never parsed.\n%%EOF\n')
        self.cli('prepare_fulltext.py', '--work', self.work, '--config', self.config, '--pdf-dir', pdfs)
        path = self.root / 'ft-plan.json'
        self.cli('build_workflow.py', 'ft', '--work', self.work, '--protocol', self.protocol,
                 '--config', self.config, '--jobs', 'all', '--out', path)
        self.ft_plan = self.read(path)

    def export(self, *extra, stage='ta', success=True):
        result = self.cli('build_outputs.py', '--work', self.work, '--out', self.out,
                          '--config', self.config, '--stage', stage, *extra, success=success)
        if not success:
            return result
        line = next(line for line in result.stdout.splitlines() if line.startswith('handoff manifest: '))
        path = Path(line.split(': ', 1)[1])
        manifest = self.read(path)
        self.assertEqual(manifest['schema'], 'rsk.screening-exports.v1')
        self.assertEqual(manifest['stage'], stage)
        self.assertEqual(manifest['current_context']['context_id'] if manifest['current_context'] else None,
                         manifest['context_id'])
        self.assert_artifacts(path, manifest)
        return path, manifest

    def assert_artifacts(self, path, manifest):
        names = set()
        for artifact in manifest['artifacts']:
            base = path.parent if artifact['base'] == 'export' else self.work
            target = base / artifact['path']
            self.assertEqual(artifact['sha256'], sha(target))
            self.assertEqual(artifact['size_bytes'], target.stat().st_size)
            for key in ('status', 'stage', 'screening_complete', 'context_id', 'input_snapshot_sha256',
                        'final_handoff_authorized'):
                self.assertEqual(artifact[key], manifest[key])
            if artifact['base'] == 'export':
                names.add(artifact['path'])
        self.assertEqual(names, {p.name for p in path.parent.iterdir() if p != path})

    def attestation(self, manifest, **changes):
        data = {'schema': 'rsk.screening-export-attestation.v1', 'stage': manifest['stage'],
                'context_id': manifest['context_id'], 'input_snapshot_sha256': manifest['input_snapshot_sha256'],
                'attested_by': 'Synthetic test signatory (not a real approval)',
                'attested_at': '2026-10-21T00:00:00Z', 'human_signoff': True}
        data.update(changes)
        path = self.root / (uuid.uuid4().hex + '-attestation.json')
        self.dump(path, data)
        return path

    def test_incomplete_progress_is_labeled_and_all_exports_are_bound(self):
        self.prepare()
        self.merge(n=1)
        path, manifest = self.export()
        self.assertFalse(manifest['screening_complete'])
        self.assertFalse(manifest['final_handoff_authorized'])
        self.assertIn('PRELIMINARY', path.parent.name)
        self.assertEqual(len(manifest['pending_ids']), 2)
        corpus = path.parent / 'TA_literature_corpus.yaml'
        self.assertIn('# PRELIMINARY', corpus.read_text(encoding='utf-8'))
        entries = corpus_entries(corpus)
        self.assertEqual(len(entries), 1)
        schema = self.read(ENGINE / 'shared/contracts/passport/literature_corpus_entry.schema.json')
        self.assertLessEqual(set(schema['required']), entries[0].keys())
        self.assertLessEqual(entries[0].keys(), schema['properties'].keys())
        self.assertIn('PRELIMINARY', entries[0]['tags'])
        self.assertIn('manifest=TA_handoff_manifest.json', entries[0]['user_notes'])
        ris = (path.parent / 'TA_1_include.ris').read_text(encoding='utf-8')
        self.assertIn('N1  - PRELIMINARY', ris)
        self.assertEqual(ris.count('ER  -'), 1)
        with (path.parent / 'TA_screening_log_All_Records.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['Export status'], 'PRELIMINARY')
        self.assertEqual(rows[0]['Context ID'], manifest['context_id'])
        counts = self.read(path.parent / 'TA_prisma_counts.json')
        self.assertFalse(counts['complete'])
        self.assertEqual(counts['export_status']['status'], 'preliminary')
        self.assertIn('PRELIMINARY', (path.parent / 'TA_methods_selection.md').read_text(encoding='utf-8'))

    def test_complete_is_not_human_signoff_or_model_execution(self):
        self.prepare()
        self.merge()
        path, manifest = self.export()
        self.assertTrue(manifest['screening_complete'])
        self.assertFalse(manifest['final_handoff_authorized'])
        self.assertEqual(manifest['human_signoff'], {'status': 'unknown', 'approved': None})
        self.assertEqual(manifest['runtime'], {'status': 'unknown', 'name': None})
        self.assertTrue(all(v == {'status': 'unknown', 'identity': None} for v in manifest['models'].values()))
        methods = (path.parent / 'TA_methods_selection.md').read_text(encoding='utf-8')
        for fabricated in ('running in Claude Code', 'configured-not-observed', 'unattested-label',
                           'could only read', 'were assessed independently'):
            self.assertNotIn(fabricated, methods)
        self.assertIn('unknown (not attested)', methods)
        self.export('--finalize', success=False)

    def test_explicit_finalization_uses_only_bound_attestation(self):
        self.prepare()
        self.merge()
        _, manifest = self.export()
        attestation = self.attestation(manifest, runtime='Synthetic declared runtime', models={'A': 'synthetic-model-A'})
        _, preliminary = self.export('--attestation', attestation)
        self.assertFalse(preliminary['final_handoff_authorized'])
        path, final = self.export('--attestation', attestation, '--finalize')
        self.assertEqual(final['status'], 'final')
        self.assertTrue(final['final_handoff_authorized'])
        self.assertEqual(final['human_signoff'], {'status': 'input_attested', 'approved': True})
        self.assertEqual(final['models']['A']['identity'], 'synthetic-model-A')
        self.assertEqual(final['models']['B']['status'], 'unknown')
        self.assertEqual(final['attestation']['sha256'], sha(attestation))
        self.assertIn('not independently verified', (path.parent / 'TA_methods_selection.md').read_text(encoding='utf-8'))

    def test_incomplete_cannot_be_final_even_with_attestation(self):
        self.prepare()
        self.merge(n=1)
        _, manifest = self.export()
        result = self.export('--attestation', self.attestation(manifest), '--finalize', success=False)
        self.assertIn('screening_incomplete_or_stale', result.stderr)

    def test_attestation_rejects_wrong_context_stage_hash_and_types(self):
        self.prepare()
        self.merge()
        _, manifest = self.export()
        for changes in ({'stage': 'ft'}, {'context_id': 'foreign'}, {'input_snapshot_sha256': 'wrong'},
                        {'human_signoff': 'true'}, {'models': {'A': ''}}, {'attested_at': '2026-10-21'},
                        {'human_signoff': False}):
            with self.subTest(changes=changes):
                self.export('--attestation', self.attestation(manifest, **changes), '--finalize', success=False)

    def test_attestation_expires_when_decision_bytes_change(self):
        self.prepare()
        self.merge()
        _, manifest = self.export()
        attestation = self.attestation(manifest)
        decisions = self.read(self.work / 'decisions.json')
        first = next(iter(decisions.values()))
        first['final']['why'] = 'Changed synthetic evidence statement.'
        self.dump(self.work / 'decisions.json', decisions)
        self.export('--attestation', attestation, '--finalize', success=False)

    def test_missing_or_stale_context_stays_inspectable_not_final(self):
        self.cli('prepare_records.py', '--inputs', self.source, '--work', self.work, '--config', self.config)
        _, unstarted = self.export()
        self.assertIsNone(unstarted['current_context'])
        self.assertFalse(unstarted['screening_complete'])
        self.assertEqual(unstarted['corpus_entries'], 0)

    def test_protocol_edit_invalidates_context_without_dropping_progress(self):
        self.prepare()
        self.merge()
        self.protocol.write_text(self.protocol.read_text(encoding='utf-8') + '\nSynthetic amendment.\n', encoding='utf-8')
        path, manifest = self.export()
        self.assertIsNone(manifest['current_context'])
        self.assertFalse(manifest['screening_complete'])
        self.assertEqual(len(corpus_entries(path.parent / 'TA_literature_corpus.yaml')), 3)

    def test_corpus_schema_rejections_are_retained_not_silent(self):
        self.source.write_text(self.source.read_text(encoding='utf-8').replace('AU  - Example, Researcher\n', '', 1),
                               encoding='utf-8')
        self.prepare()
        self.merge()
        path, manifest = self.export()
        self.assertEqual(len(manifest['corpus_rejected_ids']), 1)
        self.assertEqual(manifest['corpus_entries'], 2)
        rejected = self.read(path.parent / 'TA_corpus_rejections.json')['rejected']
        self.assertEqual(rejected[0]['reason'], 'no authors')
        self.assertIn('Synthetic', rejected[0]['record']['title'])
        self.assertEqual((path.parent / 'TA_1_include.ris').read_text(encoding='utf-8').count('ER  -'), 3)
        self.export('--attestation', self.attestation(manifest), '--finalize', success=False)

    def test_repeated_exports_preserve_prior_snapshot_and_detect_tampering(self):
        self.prepare()
        self.merge(n=1)
        old_path, manifest = self.export()
        before = {p: p.read_bytes() for p in old_path.parent.iterdir()}
        self.merge()
        new_path, _ = self.export()
        self.assertNotEqual(old_path.parent, new_path.parent)
        self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))
        artifact = next(a for a in manifest['artifacts'] if a['path'].endswith('_1_include.ris'))
        target = old_path.parent / artifact['path']
        target.write_bytes(target.read_bytes() + b'changed synthetic bytes\n')
        self.assertNotEqual(sha(target), artifact['sha256'])

    def test_fulltext_incomplete_and_awaiting_classification_are_not_final(self):
        self.prepare()
        self.prepare_ft()
        self.merge(n=1, stage='ft')
        _, partial = self.export(stage='ft')
        self.assertFalse(partial['screening_complete'])
        self.assertEqual(partial['context_id'], self.ft_plan['context']['context_id'])
        self.merge(stage='ft', decision='unclear')
        path, unclear = self.export(stage='ft')
        self.assertTrue(unclear['screening_complete'])
        self.assertIn('fulltext_awaiting_classification', unclear['handoff_blockers'])
        self.assertEqual(self.read(path.parent / 'FT_prisma_counts.json')['reports_unclear_awaiting_classification'], 3)
        self.export('--attestation', self.attestation(unclear), '--finalize', stage='ft', success=False)

    def test_fulltext_complete_finalization_does_not_invent_runtime(self):
        self.prepare()
        self.prepare_ft()
        self.merge(stage='ft')
        _, preliminary = self.export(stage='ft')
        self.assertTrue(preliminary['screening_complete'])
        path, final = self.export('--attestation', self.attestation(preliminary), '--finalize', stage='ft')
        self.assertTrue(final['final_handoff_authorized'])
        self.assertEqual(final['runtime']['status'], 'unknown')
        self.assertTrue(all(v['status'] == 'unknown' for v in final['models'].values()))
        self.assertEqual(len(corpus_entries(path.parent / 'FT_literature_corpus.yaml')), 3)


if __name__ == '__main__':
    unittest.main()
