import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_dry_run_does_not_create_destination_or_backup(self):
        result = INSTALLER.install(self.destination, dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertGreater(result['files_to_copy'], 0)
        self.assertFalse(self.destination.exists())
        INSTALLER.install(self.destination)
        backups = self.work / 'backups'
        INSTALLER.install(self.destination, update=True, backup_dir=backups, dry_run=True)
        self.assertFalse(backups.exists())

    def test_check_reports_missing_and_changed_files_without_writing(self):
        check = INSTALLER.check_installation(self.destination)
        self.assertFalse(check['current'])
        self.assertFalse(self.destination.exists())
        INSTALLER.install(self.destination)
        self.assertTrue(INSTALLER.check_installation(self.destination)['current'])
        edited = self.destination / 'rsk-paper-writing/SKILL.md'
        edited.write_text('local edits', encoding='utf-8')
        check = INSTALLER.check_installation(self.destination)
        status = next(skill for skill in check['skills'] if skill['name'] == 'rsk-paper-writing')
        self.assertEqual(status['modified'], ['SKILL.md'])
        self.assertEqual(edited.read_text(encoding='utf-8'), 'local edits')

    def test_symlink_destination_is_rejected_before_resolution(self):
        real = self.work / 'real'
        real.mkdir()
        linked = self.work / 'linked'
        try:
            linked.symlink_to(real, target_is_directory=True)
        except OSError:
            self.skipTest('Creating directory symlinks is not available.')
        with self.assertRaises(ValueError):
            INSTALLER.install(linked)
        self.assertEqual(list(real.iterdir()), [])

    def test_hardlinked_destination_is_not_overwritten(self):
        INSTALLER.install(self.destination)
        target = self.destination / 'rsk-paper-writing/SKILL.md'
        shared = self.work / 'shared.md'
        try:
            os.link(target, shared)
        except OSError:
            self.skipTest('Creating hardlinks is not available.')
        before = shared.read_bytes()
        with self.assertRaises(ValueError):
            INSTALLER.install(self.destination, update=True, backup_dir=self.work / 'backups')
        self.assertEqual(shared.read_bytes(), before)
        self.assertFalse((self.work / 'backups').exists())

    def test_linked_backup_directory_is_rejected(self):
        INSTALLER.install(self.destination)
        real = self.work / 'real-backups'
        real.mkdir()
        linked = self.work / 'linked-backups'
        try:
            linked.symlink_to(real, target_is_directory=True)
        except OSError:
            self.skipTest('Creating directory symlinks is not available.')
        with self.assertRaises(ValueError):
            INSTALLER.install(self.destination, update=True, backup_dir=linked)
        self.assertEqual(list(real.iterdir()), [])

    def test_catalog_path_must_match_skill_name(self):
        malformed = {'version': '1.0.0', 'skills': [{'name': 'rsk-paper-writing',
                      'path': 'skills/rsk-rebuttal'}]}
        with patch.object(INSTALLER.json, 'loads', return_value=malformed):
            with self.assertRaises(ValueError):
                INSTALLER.install(self.destination)
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
