"""Native activity CLI tests using synthetic evidence, never model output.

Set RSK_ACTIVITY_TEST_ROOT to an existing approved task directory (D/E on
Windows) and PYTHONDONTWRITEBYTECODE=1. mkdtemp artifacts are always retained.
No delete commands, cleanup fixtures, network calls or package installs run.
"""

import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'skills/research-starter-paper/resources/research-engine'
sys.path.insert(0, str(ENGINE))
ACTIVITY = importlib.import_module('scripts.adjudication_activity')
SCRIPT = ENGINE / 'scripts/adjudication_activity.py'
STORE_ID = 'ADJ-ACTIVITY-STORE-synthetic'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(domain, value):
    return hashlib.sha256(domain + canonical(value)).hexdigest()


class AdjudicationActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get('RSK_ACTIVITY_TEST_ROOT')
        if not configured:
            raise unittest.SkipTest('Set RSK_ACTIVITY_TEST_ROOT to an explicit approved directory.')
        base = Path(configured)
        if not base.is_absolute() or not base.is_dir():
            raise RuntimeError('Test root must be an existing absolute directory.')
        if os.name == 'nt' and base.drive.upper() not in ('D:', 'E:'):
            raise RuntimeError('Windows test artifacts must remain on D/E.')
        cls.retained = Path(tempfile.mkdtemp(prefix='activity-tests-', dir=base))
        print(f'\nRetained synthetic activity fixtures: {cls.retained}', flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='case-', dir=self.retained))
        self.root = self.work / 'artifacts \u6d4b\u8bd5'
        self.root.mkdir()
        self.store = self.work / 'activity store.json'

    def cli(self, command, *arguments, code=0):
        self.assertIn(command, {'init-store', 'build-input', 'append-run', 'render', 'validate'})
        env = dict(os.environ, TEMP=str(self.work), TMP=str(self.work), TMPDIR=str(self.work),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONNOUSERSITE='1')
        optimization = ['-O'] if sys.flags.optimize else []
        completed = subprocess.run([sys.executable, '-B', '-s', *optimization, str(SCRIPT), command,
                                    *map(str, arguments)], cwd=self.work, env=env,
                                   stdin=subprocess.DEVNULL, capture_output=True,
                                   encoding='utf-8', timeout=60, check=False, shell=False)
        self.assertEqual(completed.returncode, code, completed.stdout + completed.stderr)
        self.assertNotIn('Traceback', completed.stderr)
        if os.name == 'nt' and code == 0 and command in {'init-store', 'build-input', 'append-run'}:
            self.assertIn('namespace crash durability is not guaranteed', completed.stderr)
        return completed

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical(value) + b'\n')

    def fixture(self, run_id='RUN-synthetic', *, bad_interaction=False):
        rows = [dict(source_family=family, capture_state='not_applicable',
                     reason_code='not_applicable_for_run', artifacts=[])
                for family in ACTIVITY.SOURCE_FAMILIES]
        for index, mandatory in ((3, False), (4, True)):
            interaction = 'INTERACTION-checkpoint' if mandatory else 'INTERACTION-request'
            record = dict(actor_role='user', source='explicit_session_user_action',
                          stage='pipeline_stage_3', interaction_id=interaction,
                          interaction_sha256=digest(b'ars.adjudication-activity.interaction/1.0\0',
                                                    dict(run_id=run_id, interaction_id=interaction)))
            if mandatory:
                record.update(response_id='RESPONSE-test', checkpoint_id='CHECKPOINT-test',
                              checkpoint_type='MANDATORY', disposition='pause')
                kind = 'mandatory-checkpoint'
            else:
                record.update(request_id='REQUEST-test', action='justify_finding', finding_id='FINDING-test')
                kind = 'explicit-user-request'
                if bad_interaction:
                    record['interaction_sha256'] = '0' * 64
            path = self.root / run_id / (kind + '.json')
            self.write_json(path, dict(schema_version=f'adjudication-{kind}-log/1.0',
                                       run_id=run_id, records=[record]))
            rows[index].update(capture_state='captured', reason_code=None,
                               artifacts=[dict(artifact_id=f'ARTIFACT-{index}',
                                               artifact_role=ACTIVITY.ROLE_ORDER[ACTIVITY.SOURCE_FAMILIES[index]][0],
                                               artifact_group_id=f'SOURCE-GROUP-{index}',
                                               artifact_group_stage=None,
                                               relative_path=path.relative_to(self.root).as_posix(),
                                               sha256=hashlib.sha256(path.read_bytes()).hexdigest())])
        state = dict(run_id=run_id, pipeline_state='completed', current_stage='6',
                     stages={'6': {'status': 'completed'}}, adjudication_activity_sources=rows)
        state_path = self.root / run_id / 'terminal.json'
        self.write_json(state_path, state)
        return state_path, self.work / (run_id + '-input.json')

    def build(self, state, manifest, code=0):
        return self.cli('build-input', '--state', state, '--artifact-root', self.root,
                        '--store-id', STORE_ID, '--output', manifest, code=code)

    def append(self, manifest, code=0):
        return self.cli('append-run', '--store', self.store, '--artifact-root', self.root,
                        '--input', manifest, code=code)

    def test_actual_cli_init_build_append_render_validate_and_provenance(self):
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID)
        for run_id in ('RUN-first', 'RUN-second'):
            state, manifest = self.fixture(run_id)
            self.build(state, manifest)
            self.append(manifest)
        result = self.cli('validate', '--store', self.store)
        self.assertIn('retained_runs=2; revision=2; next_sequence=3', result.stdout)
        raw = self.store.read_bytes()
        value = json.loads(raw)
        self.assertEqual(raw, canonical(value) + b'\n')
        self.assertEqual(value['data_minimization'], ACTIVITY.DATA_MINIMIZATION)
        for run in value['runs']:
            manifest = json.loads((self.work / (run['run_id'] + '-input.json')).read_bytes())
            self.assertEqual(run['input_receipt_sha256'],
                             digest(b'ars.adjudication-activity.input/1.0\0', manifest))
            self.assertEqual(run['record_sha256'], digest(b'ars.adjudication-activity.run/1.0\0',
                             {key: item for key, item in run.items() if key != 'record_sha256'}))
            self.assertEqual([event['event_type'] for row in run['sources'] for event in row['events']],
                             ['finding_justification_requested', 'mandatory_checkpoint_non_proceed'])
        self.assertNotIn(str(self.work).encode(), raw)
        rendered = self.cli('render', '--store', self.store, '--window', '2').stdout
        self.assertIn('adjudication_count=4', rendered)
        for notice in (ACTIVITY.LIMITATION, ACTIVITY.ADVISORY, ACTIVITY.COVERAGE):
            self.assertIn(notice, rendered)
        self.assertEqual(self.store.read_bytes(), raw)
        self.assertEqual(self.store.with_name(self.store.name + '.lock').stat().st_size, 0)

    def test_append_initializes_missing_store_and_retry_is_idempotent(self):
        state, manifest = self.fixture()
        self.build(state, manifest)
        self.append(manifest)
        original = self.store.read_bytes()
        self.assertIn('already_appended', self.append(manifest).stdout)
        self.assertEqual(self.store.read_bytes(), original)
        self.assertIn('INSUFFICIENT_HISTORY', self.cli('render', '--store', self.store).stdout)

    def test_create_never_clobbers_store_or_manifest(self):
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID)
        original = self.store.read_bytes()
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID, code=5)
        self.assertEqual(self.store.read_bytes(), original)
        state, manifest = self.fixture()
        self.build(state, manifest)
        manifest_raw = manifest.read_bytes()
        self.build(state, manifest, code=5)
        self.assertEqual(manifest.read_bytes(), manifest_raw)

    def test_changed_source_hash_does_not_mutate_store(self):
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID)
        original = self.store.read_bytes()
        state, manifest = self.fixture()
        self.build(state, manifest)
        source = state.parent / 'explicit-user-request.json'
        source.write_bytes(source.read_bytes() + b' ')
        self.assertIn('ERROR:SOURCE', self.append(manifest, code=3).stderr)
        self.assertEqual(self.store.read_bytes(), original)

    def test_terminal_hash_and_sealed_inventory_are_enforced(self):
        state, manifest = self.fixture()
        self.build(state, manifest)
        original = state.read_bytes()
        state.write_bytes(original + b' ')
        self.assertIn('terminal receipt raw-byte hash mismatch', self.append(manifest, code=3).stderr)
        state.write_bytes(original)
        value = json.loads(manifest.read_bytes())
        value['sources'][0].update(capture_state='unavailable', reason_code='source_not_provided')
        self.write_json(manifest, value)
        self.assertIn('sealed terminal inventory', self.append(manifest, code=3).stderr)
        self.assertFalse(self.store.exists())

    def test_rehashed_source_with_false_interaction_provenance_is_rejected(self):
        state, manifest = self.fixture(bad_interaction=True)
        self.assertIn('interaction digest is invalid', self.build(state, manifest, code=3).stderr)
        self.assertFalse(manifest.exists())

    def test_invalid_terminal_and_strict_json_are_rejected(self):
        state, manifest = self.fixture()
        value = json.loads(state.read_bytes())
        value['pipeline_state'] = 'in_progress'
        self.write_json(state, value)
        self.build(state, manifest, code=3)
        for raw in (b'{"x":1,"x":2}', b'{"x":1.1}', b'{"x":NaN}', b'\xef\xbb\xbf{}'):
            state.write_bytes(raw)
            self.build(state, manifest, code=3)
        self.assertFalse(manifest.exists())

    def test_validate_rejects_noncanonical_and_changed_record_digest(self):
        state, manifest = self.fixture()
        self.build(state, manifest)
        self.append(manifest)
        raw = self.store.read_bytes()
        self.store.write_bytes(raw + b'\n')
        self.cli('validate', '--store', self.store, code=4)
        value = json.loads(raw)
        value['runs'][0]['record_sha256'] = '0' * 64
        self.write_json(self.store, value)
        self.assertIn('run record digest mismatch', self.cli('validate', '--store', self.store, code=4).stderr)

    def test_actual_input_size_cap_before_append(self):
        oversized = self.work / 'oversized-input.json'
        oversized.write_bytes(b' ' * (ACTIVITY.MAX_INPUT + 1))
        self.assertIn('ERROR:CAP', self.append(oversized, code=5).stderr)
        self.assertFalse(self.store.exists())

    def test_actual_artifact_cap_and_exact_binary_bytes(self):
        path = self.root / 'binary.bin'
        raw = bytes(range(256)) * 8200 + b'\r\n\x1a\x00\xff'
        path.write_bytes(raw)
        self.assertEqual(ACTIVITY._read_artifact_relative(self.root, path.name, len(raw)), raw)
        with self.assertRaises(ACTIVITY.ActivityError) as caught:
            ACTIVITY._read_artifact_relative(self.root, path.name, len(raw) - 1)
        self.assertEqual(caught.exception.code, 'CAP')
        self.assertEqual(ACTIVITY._read_limited_identity(path, len(raw), code='INPUT')[0], raw)

    def test_terminal_seal_helper_preserves_hash_binding_and_idempotence(self):
        state, _ = self.fixture()
        value = json.loads(state.read_bytes())
        rows = value.pop('adjudication_activity_sources')
        pending = copy.deepcopy(rows)
        for row in pending:
            for artifact in row['artifacts']:
                artifact.pop('sha256')
        self.write_json(state, value)
        self.assertEqual(ACTIVITY.seal_terminal_inventory(state, self.root, pending), rows)
        sealed = state.read_bytes()
        self.assertEqual(ACTIVITY.seal_terminal_inventory(state, self.root, pending), rows)
        self.assertEqual(state.read_bytes(), sealed)

    def test_aggregate_artifact_and_action_record_caps_are_preserved(self):
        state, manifest = self.fixture()
        self.build(state, manifest)
        value = json.loads(manifest.read_bytes())
        for name in ('MAX_ARTIFACT_TOTAL', 'MAX_EVENTS_RUN'):
            with self.subTest(limit=name), patch.object(ACTIVITY, name, 1):
                with self.assertRaises(ACTIVITY.ActivityError) as caught:
                    ACTIVITY._extract_run(value, self.root, 1)
                self.assertEqual(caught.exception.code, 'CAP')

    def test_same_run_with_different_receipt_is_conflict_not_an_overwrite(self):
        state, manifest = self.fixture()
        self.build(state, manifest)
        self.append(manifest)
        original = self.store.read_bytes()
        value = json.loads(manifest.read_bytes())
        value['sources'][0].update(capture_state='unavailable', reason_code='source_not_provided')
        self.write_json(manifest, value)
        self.assertIn('ERROR:CONFLICT', self.append(manifest, code=5).stderr)
        self.assertEqual(self.store.read_bytes(), original)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows path and sharing checks')
    def test_windows_unsafe_artifact_paths_are_rejected(self):
        for relative in ('../outside', '/outside', 'a//b', 'a/./b', 'a\\b', 'C:outside',
                         'a:stream', 'NUL', 'COM1.txt', 'LPT\u00b2', 'trailing.', 'trailing '):
            with self.subTest(relative=relative), self.assertRaises(ACTIVITY.ActivityError):
                ACTIVITY._read_artifact_relative(self.root, relative, 100)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows junctions')
    def test_windows_junctions_cannot_escape_reads_or_writes(self):
        import _winapi
        outside = self.work / 'outside'
        outside.mkdir()
        (outside / 'file').write_bytes(b'outside')
        link = self.root / 'junction'
        _winapi.CreateJunction(str(outside), str(link))
        for root, relative in ((self.root, 'junction/file'), (link, 'file')):
            with self.assertRaises(ACTIVITY.ActivityError):
                ACTIVITY._read_artifact_relative(root, relative, 100)
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._atomic_create(link / 'new.json', b'{}\n')
        self.cli('init-store', '--store', link / 'store.json', '--store-id', STORE_ID, code=3)
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ['file'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows hardlinks')
    def test_windows_hardlinked_inputs_stores_and_locks_are_rejected(self):
        file = self.root / 'file'
        file.write_bytes(b'{}\n')
        alias = self.work / 'alias'
        os.link(file, alias)
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._read_limited(file, 100, code='INPUT')
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._read_artifact_relative(self.root, file.name, 100)
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._atomic_replace(file, b'other', expected_identity=ACTIVITY._path_identity(file))
        self.assertEqual(alias.read_bytes(), b'{}\n')
        os.link(file, self.store.with_name(self.store.name + '.lock'))
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID, code=7)
        self.assertFalse(self.store.exists())

    @unittest.skipUnless(os.name == 'nt', 'Native Windows byte-range lock contention')
    def test_windows_busy_and_nonempty_lock_fail_closed(self):
        self.cli('init-store', '--store', self.store, '--store-id', STORE_ID)
        with ACTIVITY._store_lock(self.store, exclusive=True):
            self.cli('init-store', '--store', self.store, '--store-id', STORE_ID, code=7)
        self.cli('validate', '--store', self.store)
        self.store.with_name(self.store.name + '.lock').write_bytes(b'not empty')
        self.cli('validate', '--store', self.store, code=7)

    @unittest.skipUnless(os.name == 'nt', 'Windows staging failure retention')
    def test_windows_write_failure_retains_staging_file_and_original(self):
        self.store.write_bytes(b'original')
        def partial(fd, raw):
            os.write(fd, raw[:3])
            raise OSError('synthetic write failure')
        with patch.object(ACTIVITY, '_write_all', side_effect=partial), \
                patch.object(os, 'unlink', side_effect=AssertionError('No deletion permitted')):
            with self.assertRaises(ACTIVITY.ActivityError) as caught:
                ACTIVITY._atomic_replace(self.store, b'changed',
                                         expected_identity=ACTIVITY._path_identity(self.store))
        self.assertEqual(caught.exception.code, 'WRITE')
        self.assertEqual(self.store.read_bytes(), b'original')
        staged = list(self.work.glob('.activity store.json.*'))
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0].read_bytes(), b'cha')

    @unittest.skipUnless(os.name == 'nt', 'Windows no-clobber rename')
    def test_windows_create_race_preserves_other_writer_and_staging_file(self):
        original = os.rename
        def race(source, destination):
            Path(destination).write_bytes(b'other writer')
            return original(source, destination)
        with patch.object(os, 'rename', side_effect=race), \
                patch.object(os, 'unlink', side_effect=AssertionError('No deletion permitted')):
            with self.assertRaises(ACTIVITY.ActivityError) as caught:
                ACTIVITY._atomic_create(self.store, b'intended')
        self.assertEqual(caught.exception.code, 'CONFLICT')
        self.assertEqual(self.store.read_bytes(), b'other writer')
        self.assertEqual([p.read_bytes() for p in self.work.glob('.activity store.json.*')], [b'intended'])

    @unittest.skipUnless(os.name == 'nt', 'Windows identity conflict protection')
    def test_windows_identity_conflict_does_not_replace_target(self):
        self.store.write_bytes(b'original')
        expected = ACTIVITY._path_identity(self.store)
        self.store.rename(self.work / 'retained-original')
        self.store.write_bytes(b'replacement')
        with self.assertRaises(ACTIVITY.ActivityError) as caught:
            ACTIVITY._atomic_replace(self.store, b'intended', expected_identity=expected)
        self.assertEqual(caught.exception.code, 'CONFLICT')
        self.assertEqual(self.store.read_bytes(), b'replacement')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows sharing and data flush')
    def test_windows_publication_holds_ancestors_and_fsyncs_only_files(self):
        real_write, real_fsync = ACTIVITY._write_all, os.fsync
        flushed = []
        def write(fd, raw):
            with self.assertRaises(OSError):
                self.work.rename(self.work.with_name(self.work.name + '-moved'))
            real_write(fd, raw)
        def fsync(fd):
            self.assertTrue(stat.S_ISREG(os.fstat(fd).st_mode))
            flushed.append(fd)
            real_fsync(fd)
        with patch.object(ACTIVITY, '_write_all', side_effect=write), \
                patch.object(os, 'fsync', side_effect=fsync), \
                patch.object(os, 'fchmod', create=True, side_effect=AssertionError('Not a Windows ACL API')), \
                patch.object(os, 'unlink', side_effect=AssertionError('No deletion permitted')):
            ACTIVITY._atomic_create(self.store, b'first')
            ACTIVITY._atomic_replace(self.store, b'second',
                                     expected_identity=ACTIVITY._path_identity(self.store))
        self.assertEqual(len(flushed), 2)
        self.assertEqual(self.store.read_bytes(), b'second')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows fsync failure retention')
    def test_windows_fsync_failure_does_not_publish_or_cleanup(self):
        with patch.object(os, 'fsync', side_effect=OSError('synthetic flush failure')), \
                patch.object(os, 'unlink', side_effect=AssertionError('No deletion permitted')):
            with self.assertRaises(ACTIVITY.ActivityError) as caught:
                ACTIVITY._atomic_create(self.store, b'retained')
        self.assertEqual(caught.exception.code, 'WRITE')
        self.assertFalse(self.store.exists())
        self.assertEqual([p.read_bytes() for p in self.work.glob('.activity store.json.*')], [b'retained'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows sharing prevents live writers')
    def test_windows_open_writer_prevents_artifact_read(self):
        path = self.root / 'source'
        path.write_bytes(b'original')
        with path.open('r+b'):
            with self.assertRaises(ACTIVITY.ActivityError):
                ACTIVITY._read_artifact_relative(self.root, path.name, 100)
        self.assertEqual(ACTIVITY._read_artifact_relative(self.root, path.name, 100), b'original')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows file symlink')
    def test_windows_file_symlink_is_rejected(self):
        source = self.root / 'source'
        source.write_bytes(b'original')
        link = self.root / 'link'
        try:
            link.symlink_to(source)
        except OSError as exc:
            if exc.winerror in (1, 50, 1314):
                self.skipTest(f'Host cannot create symlinks: {exc}')
            raise
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._read_artifact_relative(self.root, link.name, 100)
        with self.assertRaises(ACTIVITY.ActivityError):
            ACTIVITY._read_limited(link, 100, code='INPUT')


if __name__ == '__main__':
    unittest.main()
