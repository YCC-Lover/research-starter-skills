import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('validator', ROOT / 'scripts/validate_skills.py')
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-validation-test-'))
        self.package = self.work / 'package'
        shutil.copytree(ROOT, self.package, ignore=shutil.ignore_patterns('.git', '__pycache__'))

    def test_package_passes(self):
        self.assertEqual(VALIDATOR.validate(self.package)['skills'], 7)

    def test_optimized_python_still_rejects_invalid_coverage(self):
        path = self.package / 'catalog.json'
        catalog = json.loads(path.read_text(encoding='utf-8'))
        catalog['tutorials_covered'] = 18
        path.write_text(json.dumps(catalog), encoding='utf-8')
        result = subprocess.run([sys.executable, '-O', str(ROOT / 'scripts/validate_skills.py'),
                                 '--root', str(self.package)], capture_output=True, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('coverage mismatch', result.stderr)

    def test_unknown_image_is_rejected(self):
        (self.package / 'unreviewed.png').write_bytes(b'not a reviewed image')
        with self.assertRaisesRegex(ValueError, 'Unapproved binary'):
            VALIDATOR.validate(self.package)

    def test_citation_version_mismatch_is_rejected(self):
        path = self.package / 'CITATION.cff'
        text = path.read_text(encoding='utf-8')
        import yaml
        metadata = yaml.safe_load(text)
        metadata['version'] = '0.0.0'
        path.write_text(yaml.safe_dump(metadata), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Citation version mismatch'):
            VALIDATOR.validate(self.package)

    def test_broken_link_is_rejected(self):
        (self.package / 'extra.md').write_text('[Broken](missing-guide.md)', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Broken or escaping link'):
            VALIDATOR.validate(self.package)

    def test_private_path_is_rejected(self):
        (self.package / 'extra.txt').write_text('C:' + '/Users/private/draft.txt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Private user path'):
            VALIDATOR.validate(self.package)

    def test_changed_image_checksum_is_rejected(self):
        manifest = self.package / 'docs/images/manifest.json'
        if not manifest.exists():
            self.skipTest('The package has no images yet.')
        assets = json.loads(manifest.read_text(encoding='utf-8'))
        assets['images'][0]['sha256'] = '0' * 64
        manifest.write_text(json.dumps(assets), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            VALIDATOR.validate(self.package)


if __name__ == '__main__':
    unittest.main()
