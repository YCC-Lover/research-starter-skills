import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_skills.py')
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)
NAMES = [s['name'] for s in json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))['skills']]


class InstallTests(unittest.TestCase):
    def setUp(self):
        # Leave fixtures in the configured work directory; no recursive cleanup.
        self.work = Path(tempfile.mkdtemp(prefix='rsk-install-test-'))
        self.destination = self.work / 'installed'

    def test_clean_install_keeps_sibling_layout(self):
        result = INSTALLER.install(self.destination)
        self.assertEqual(result['installed'], NAMES)
        self.assertEqual(result['deleted_files'], 0)
        for name in NAMES:
            self.assertTrue((self.destination / name / 'SKILL.md').is_file())
        router = self.destination / 'research-starter-paper'
        self.assertTrue((router / '../rsk-paper-writing/SKILL.md').resolve().is_file())

    def test_collision_aborts_before_partial_install(self):
        target = self.destination / NAMES[-1]
        target.mkdir(parents=True)
        marker = target / 'user-file.txt'
        marker.write_text('preserve', encoding='utf-8')
        with self.assertRaises(ValueError):
            INSTALLER.install(self.destination)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve')
        self.assertFalse((self.destination / NAMES[0]).exists())

    def test_update_requires_explicit_backup(self):
        INSTALLER.install(self.destination)
        with self.assertRaises(ValueError):
            INSTALLER.install(self.destination, update=True)

    def test_update_backs_up_changes_and_preserves_unrelated_files(self):
        INSTALLER.install(self.destination)
        skill = self.destination / 'rsk-paper-writing'
        edited = skill / 'SKILL.md'
        edited.write_text('local edits', encoding='utf-8')
        extra = skill / 'my-notes.txt'
        extra.write_text('my notes', encoding='utf-8')
        result = INSTALLER.install(self.destination, update=True, backup_dir=self.work / 'backups')
        saved = Path(result['backup']) / 'rsk-paper-writing/SKILL.md'
        self.assertEqual(saved.read_text(encoding='utf-8'), 'local edits')
        self.assertEqual(extra.read_text(encoding='utf-8'), 'my notes')
        self.assertEqual(edited.read_bytes(), (ROOT / 'skills/rsk-paper-writing/SKILL.md').read_bytes())

    def test_codex_home_selects_another_profile(self):
        home = self.work / 'another-codex-profile'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/install_skills.py')],
                                env={**os.environ, 'CODEX_HOME': str(home)},
                                capture_output=True, text=True, check=True)
        self.assertEqual(Path(json.loads(result.stdout)['destination']), (home / 'skills').resolve())
        self.assertTrue((home / 'skills/rsk-research-workflow/references/conferences.md').is_file())

    def test_source_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            INSTALLER.install(ROOT / 'skills', update=True, backup_dir=self.work / 'backups')


if __name__ == '__main__':
    unittest.main()
