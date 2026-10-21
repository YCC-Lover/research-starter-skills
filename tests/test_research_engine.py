import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/research-starter-paper/scripts/research_engine.py'
SPEC = importlib.util.spec_from_file_location('rsk_engine_tests', SCRIPT)
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


class ResearchEngineTests(unittest.TestCase):
    def test_every_registered_mode_has_a_local_entry_and_owner(self):
        catalog = ENGINE.load_catalog()
        counts = {}
        for row in catalog['modes']:
            counts[row['workflow']] = counts.get(row['workflow'], 0) + 1
            resolved = ENGINE.resolve_mode(row['workflow'], row['mode'])
            self.assertTrue(Path(resolved['entry_path']).is_file())
            self.assertTrue(resolved['skills'])
            self.assertEqual(resolved['execution'], 'not_started')
        self.assertEqual(counts, {'deep-research': 8, 'academic-paper': 11,
                                 'academic-paper-reviewer': 6, 'academic-pipeline': 2,
                                 'sr-screener': 8})

    def test_bundle_integrity_is_not_a_model_effectiveness_claim(self):
        result = ENGINE.verify_bundle()
        self.assertTrue(result['content_verified'])
        self.assertFalse(result['execution_verified'])
        self.assertEqual(result['modes'], 35)

    def test_path_escape_is_rejected(self):
        for name in ('../outside.md', '/absolute.md', 'C:/file.md', 'a\\b.md'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ENGINE.safe_file(ENGINE.ENGINE, name)

    def test_unknown_mode_is_not_silently_rerouted(self):
        with self.assertRaisesRegex(ValueError, 'Unknown workflow/mode'):
            ENGINE.resolve_mode('sr-screener', 'systematic-review')

    def test_duplicate_inventory_is_rejected(self):
        work = Path(tempfile.mkdtemp(prefix='rsk-engine-inventory-'))
        catalog = json.loads(ENGINE.CATALOG.read_text(encoding='utf-8'))
        catalog['modes'][-1] = catalog['modes'][0]
        path = work / 'catalog.json'
        path.write_text(json.dumps(catalog), encoding='utf-8')
        with patch.object(ENGINE, 'CATALOG', path), self.assertRaisesRegex(ValueError, 'uniqueness'):
            ENGINE.load_catalog()

    def test_local_environment_keeps_cache_and_temp_in_task(self):
        work = Path(tempfile.mkdtemp(prefix='rsk-engine-env-'))
        directory, env = ENGINE.local_environment(work)
        self.assertEqual(directory, work)
        for key in ('TEMP', 'TMP', 'TMPDIR', 'ARS_VERIFICATION_CACHE_PATH', 'XDG_CACHE_HOME'):
            self.assertTrue(Path(env[key]).is_relative_to(work), key)
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertIn(str(ENGINE.ENGINE), env['PYTHONPATH'].split(os.pathsep))

    def test_network_dispatch_is_not_a_local_command(self):
        with self.assertRaisesRegex(ValueError, 'Not a supported local'):
            ENGINE.run_local('scripts/verify_passport.py', [], Path(tempfile.gettempdir()))

    @unittest.skipUnless(os.name == 'nt', 'Windows-only storage requirement')
    def test_c_drive_work_directory_is_rejected_before_creation(self):
        with self.assertRaisesRegex(ValueError, 'not C'):
            ENGINE.local_environment(Path('C:/rsk-this-must-not-be-created'))


if __name__ == '__main__':
    unittest.main()
