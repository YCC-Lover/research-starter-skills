import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('behavior_validator', ROOT / 'scripts/validate_behavior_eval.py')
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class BehaviorRecordTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-behavior-record-test-'))
        self.package = self.work / 'package'
        shutil.copytree(ROOT, self.package, ignore=shutil.ignore_patterns('.git', '__pycache__'))

    def test_recorded_artifacts_are_consistent(self):
        result = VALIDATOR.validate(self.package)
        self.assertEqual(result['records'], result['cases'] * 2)

    def test_changed_input_invalidates_record(self):
        path = self.package / 'evals/history/2026-10-09-sources.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['inputs']['examples/first-run/evidence.md'] += '\nChanged archived source.\n'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            VALIDATOR.validate(self.package)

    def test_archived_run_is_not_relabelled_as_current(self):
        data = json.loads((self.package / 'evals/runs.json').read_text(encoding='utf-8'))
        old = next(item for item in data['runs'] if item['id'] == '2026-10-09-v1.2.0')
        self.assertEqual(old['state'], 'historical')
        result = VALIDATOR.validate(self.package)
        self.assertTrue(result['archived_snapshots_match'])

    def test_unrelated_ui_metadata_does_not_invalidate_explicit_task_runs(self):
        path = self.package / 'skills/rsk-paper-writing/agents/openai.yaml'
        path.write_text(path.read_text(encoding='utf-8') + '\n# UI-only maintenance\n', encoding='utf-8')
        VALIDATOR.validate(self.package)

    def test_dependency_impact_is_scoped_to_the_relevant_case(self):
        cases = {'cases': [
            {'id': 'A', 'files': ['a.md'], 'dependencies': ['skills/one/SKILL.md']},
            {'id': 'B', 'files': ['b.md'], 'dependencies': ['skills/two/SKILL.md']} ]}
        for relative, text in [('cases.json', json.dumps(cases)), ('a.md', 'one'), ('b.md', 'two'),
                               ('skills/one/SKILL.md', 'old'), ('skills/two/SKILL.md', 'stable')]:
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        sources = {'cases': cases, 'inputs': {'a.md': 'one', 'b.md': 'two'},
                   'skills': {'skills/one/SKILL.md': 'old', 'skills/two/SKILL.md': 'stable'}}
        (self.work / 'skills/one/SKILL.md').write_text('changed', encoding='utf-8')
        impact = VALIDATOR.run_impact(self.work, {'cases': 'cases.json'}, {'records': []}, sources)
        self.assertEqual([case['case_id'] for case in impact], ['A'])

    def test_current_dependency_changes_require_new_evidence(self):
        # Synthetic parser fixture only, never a claimed model execution.
        dependency = 'skills/unit/SKILL.md'
        case = {'id': 'UNIT', 'skill': 'unit', 'files': ['unit-input.md'],
                'dependencies': [dependency], 'checks': ['unit-test-only']}
        sources = {'cases': {'cases': [case]}, 'inputs': {'unit-input.md': 'unit input'},
                   'skills': {dependency: 'unit guidance'}}
        snapshot = VALIDATOR.source_snapshot(sources)
        report = {'package_version': json.loads((self.package / 'catalog.json').read_text(encoding='utf-8'))['version'],
                  'protocol': {'independent_context_per_task': True}, 'snapshot': snapshot, 'records': []}
        for variant in ('baseline', 'skill'):
            references = [] if variant == 'baseline' else [dependency]
            report['records'].append({'case_id': 'UNIT', 'variant': variant,
                                      'response': {'answer': 'unit fixture', 'references_read': references},
                                      'reference_snapshot': {p: snapshot['skill_files_sha256'][p] for p in references},
                                      'judgment': {'checks': [{'index': 0, 'status': '通过',
                                                              'reason': 'parser fixture', 'evidence': 'unit fixture'}]}})
        index = {'schema_version': 2, 'required_current_cases': ['UNIT'], 'runs': [
            {'id': 'UNIT', 'state': 'current', 'cases': 'evals/unit-cases.json',
             'report': 'evals/unit-report.json', 'sources': 'evals/unit-sources.json'}]}
        for relative, text in [('unit-input.md', 'unit input'), (dependency, 'unit guidance'),
                               ('evals/unit-cases.json', json.dumps(sources['cases'])),
                               ('evals/unit-report.json', json.dumps(report)),
                               ('evals/unit-sources.json', json.dumps(sources)),
                               ('evals/runs.json', json.dumps(index))]:
            path = self.package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        VALIDATOR.validate(self.package)
        ui = self.package / 'skills/unit/agents/openai.yaml'
        ui.parent.mkdir(parents=True, exist_ok=True)
        ui.write_text('interface: {display_name: "UI-only change"}\n', encoding='utf-8')
        VALIDATOR.validate(self.package)
        (self.package / dependency).write_text('changed guidance', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            VALIDATOR.validate(self.package)

    def test_missing_variant_is_rejected(self):
        path = self.package / 'evals/results.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['records'].pop()
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
            VALIDATOR.validate(self.package)

    def test_judgment_cannot_quote_nonexistent_answer(self):
        path = self.package / 'evals/results.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['records'][0]['judgment']['checks'][0]['evidence'] = 'not in the real answer'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'evidence is not in'):
            VALIDATOR.validate(self.package)
