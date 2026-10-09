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
        path = self.package / 'examples/first-run/evidence.md'
        path.write_text(path.read_text(encoding='utf-8') + '\nChanged fixture.\n', encoding='utf-8')
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
