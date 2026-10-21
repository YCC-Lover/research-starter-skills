"""Native Windows CLI checks using retained synthetic data, never cleanup."""

import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'skills/research-starter-paper/resources/research-engine'
SCRIPTS = ENGINE / 'scripts'
FIXTURES = SCRIPTS / 'fixtures'
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(SCRIPTS))
BINDING = importlib.import_module('review_criteria_binding')
PACKET = importlib.import_module('build_submission_packet_manifest')
REVIEW = importlib.import_module('resolve_review_target_context')
AUTHORITY = importlib.import_module('resolve_human_subjects_authority')
REVISION = importlib.import_module('revision_roadmap')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


@unittest.skipUnless(os.name == 'nt', 'Real Windows CLI and handle tests')
class PacketBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(os.environ.get('RSK_PACKET_BINDING_TEST_ROOT', tempfile.gettempdir()))
        if base.drive.upper() not in ('D:', 'E:') or os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
            raise RuntimeError('Use a D:/E: work directory and PYTHONDONTWRITEBYTECODE=1')
        cls.retained = Path(tempfile.mkdtemp(prefix='packet-binding-', dir=base))
        print(f'\nRetained packet/binding fixtures: {cls.retained}', flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='case-', dir=self.retained))
        self.inputs = self.work / 'inputs \u6d4b\u8bd5'
        self.inputs.mkdir()
        self.packet = self.work / 'packet \u00e9'
        self.packet.mkdir()

    def write_json(self, path, value):
        path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\r\n').encode('utf-8'))
        return path

    def cli(self, script, *args, code=0):
        env = {**os.environ, 'TEMP': str(self.work), 'TMP': str(self.work),
               'TMPDIR': str(self.work), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        flags = ['-B', '-O'] if sys.flags.optimize else ['-B']
        result = subprocess.run([sys.executable, *flags, str(SCRIPTS / script), *map(str, args)],
                                cwd=self.work, env=env, capture_output=True,
                                text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def binding_inputs(self):
        registry = read_json(FIXTURES / 'review_target_context/synthetic-registry.json')
        declaration = read_json(FIXTURES / 'review_target_context/exact-declaration.json')
        self.context = self.write_json(self.inputs / 'review context.json', REVIEW.resolve(declaration, registry))
        self.registry = self.write_json(self.inputs / 'review registry.json', registry)
        self.manifest = self.work / 'binding \u6d4b\u8bd5.json'

    def init_args(self, *, context=None, output=None):
        return ['init', '--context', context or self.context, '--registry', self.registry,
                '--context-ref', 'inputs/context.json', '--registry-ref', 'inputs/registry.json',
                '--target-review-id', 'synthetic-review', '--output', output or self.manifest]

    def binding_init(self):
        self.binding_inputs()
        self.cli('review_criteria_binding.py', *self.init_args())

    def binding_validate_args(self):
        return ['validate', '--manifest', self.manifest, '--context', self.context,
                '--registry', self.registry]

    def binding_artifact(self, consumer='formative_planning', role='FORMATIVE'):
        marker = self.cli('review_criteria_binding.py', 'marker', '--manifest', self.manifest,
                          '--consumer', consumer, '--role', role).stdout.rstrip('\n')
        relative = f'{consumer}-{role} \u00e9.md'
        raw = ('# Synthetic output\r\n' + BINDING._render_conflict_line(read_json(self.manifest))
               + '\n' + marker + '\nEnd.\r\n').encode('utf-8')
        (self.work / relative).write_bytes(raw)
        return relative, raw

    def record_args(self, consumer, specs):
        args = ['record', '--manifest', self.manifest, '--consumer', consumer]
        for role, relative in specs:
            args.extend(['--artifact', f'{role}={relative}'])
        return args

    def packet_inputs(self):
        context = read_json(FIXTURES / 'human_subjects_authority/us-gdpr-two-axis.json')
        for fact_id, value in PACKET.ENVELOPE_FACTS:
            context['declared_facts'].append({'fact_id': fact_id, 'value_type': 'boolean',
                                            'state': 'declared', 'value': value,
                                            'provenance': 'author_declared'})
        registry = read_json(ENGINE / 'shared/human_subjects_authority_registry.json')
        self.pcontext = self.write_json(self.inputs / 'packet-context.json', context)
        self.pregistry = self.write_json(self.inputs / 'packet-registry.json', registry)
        self.resolved = self.write_json(self.inputs / 'resolved.json', AUTHORITY.resolve(context, registry))
        inventory = read_json(FIXTURES / 'submission_packet_manifest/base_inventory.json')
        for index, artifact in enumerate(inventory['artifacts']):
            relative = f'nested \u6d4b\u8bd5/item {index}.bin'
            raw = b'Synthetic software fixture\r\n\x00\xff\x1a' + bytes([index])
            path = self.packet / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            artifact.update(relative_path=relative, declared_sha256=digest(raw), declared_size_bytes=len(raw))
        self.inventory = self.write_json(self.inputs / 'inventory.json', inventory)
        self.pmanifest = self.work / 'packet-manifest.json'
        (self.packet / 'not-inventoried.txt').write_bytes(b'Unlisted synthetic input must be ignored.')
        return inventory

    def packet_args(self, command='build', *, root=None, inventory=None, output=None):
        args = [command, '--packet-root', root or self.packet, '--inventory', inventory or self.inventory,
                '--context', self.pcontext, '--registry', self.pregistry, '--resolved', self.resolved]
        if command == 'build':
            args.extend(['--output', output or self.pmanifest])
        else:
            args.extend(['--manifest', self.pmanifest])
            if command == 'render':
                args.extend(['--output', output or self.work / 'packet-render.md'])
        return args

    def test_binding_all_consumers_cli_exact_hashes_and_idempotency(self):
        self.binding_init()
        initial = read_json(self.manifest)
        self.assertEqual(initial['context_authority']['context_sha256'], digest(self.context.read_bytes()))
        self.assertEqual(initial['context_authority']['registry_sha256'], digest(self.registry.read_bytes()))
        self.assertNotIn(b'\r\n', self.manifest.read_bytes())
        for consumer, roles in BINDING.ROLES.items():
            specs, expected = [], {}
            for role in roles:
                relative, raw = self.binding_artifact(consumer, role)
                specs.append((role, relative))
                expected[role] = digest(raw)
            args = self.record_args(consumer, specs)
            self.cli('review_criteria_binding.py', *args)
            before, timestamp = self.manifest.read_bytes(), self.manifest.stat().st_mtime_ns
            self.cli('review_criteria_binding.py', *args)
            self.assertEqual((self.manifest.read_bytes(), self.manifest.stat().st_mtime_ns), (before, timestamp))
            receipt = next(row for row in read_json(self.manifest)['receipts'] if row['consumer_id'] == consumer)
            self.assertEqual({row['role']: row['artifact_sha256'] for row in receipt['artifacts']}, expected)
        self.cli('review_criteria_binding.py', *self.binding_validate_args(), '--require-complete')
        authority = read_json(self.manifest)['context_authority']
        findings = self.write_json(self.inputs / 'findings.json', {
            'schema_version': BINDING.FINDINGS_VERSION, 'target_review_id': 'synthetic-review',
            'resolved_digest': authority['resolved_digest'],
            'selected_criterion_ids': authority['selected_criterion_ids'], 'findings': [],
        })
        self.cli('review_criteria_binding.py', 'validate-findings', *self.binding_validate_args()[1:],
                 '--findings', findings, '--require-complete')

    def test_binding_changed_missing_and_conflicting_inputs(self):
        self.binding_init()
        relative, _ = self.binding_artifact()
        args = self.record_args('formative_planning', [('FORMATIVE', relative)])
        self.cli('review_criteria_binding.py', *args)
        before = self.manifest.read_bytes()
        with (self.work / relative).open('ab') as handle:
            handle.write(b'changed')
        self.cli('review_criteria_binding.py', *args, code=3)
        self.assertEqual(self.manifest.read_bytes(), before)
        with self.context.open('ab') as handle:
            handle.write(b' ')
        self.cli('review_criteria_binding.py', *self.binding_validate_args(), code=2)
        self.context.rename(self.context.with_name('retained-context.json'))
        self.cli('review_criteria_binding.py', *self.binding_validate_args(), code=2)

    def test_binding_strict_json_limits_and_relative_escapes(self):
        self.binding_init()
        for index, raw in enumerate((b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff',
                                     b' ' * (BINDING.MAX_JSON_BYTES + 1))):
            path = self.inputs / f'invalid-{index}.json'
            path.write_bytes(raw)
            output = self.work / f'rejected-{index}.json'
            self.cli('review_criteria_binding.py', *self.init_args(context=path, output=output), code=2)
            self.assertFalse(output.exists())
        relative, raw = self.binding_artifact()
        outside = self.work.parent / (self.work.name + '-outside.md')
        outside.write_bytes(raw)
        for name in ('../' + outside.name, outside.as_posix(), 'D:relative', 'a//b',
                     'NUL', 'draft:stream', 'a\\b'):
            with self.subTest(name=name):
                self.cli('review_criteria_binding.py',
                         *self.record_args('formative_planning', [('FORMATIVE', name)]), code=2)
        (self.work / relative).write_bytes(b'x' * (BINDING.MAX_ARTIFACT_BYTES + 1))
        self.cli('review_criteria_binding.py',
                 *self.record_args('formative_planning', [('FORMATIVE', relative)]), code=2)

    def test_binding_hardlink_and_junction_inputs(self):
        import _winapi

        self.binding_inputs()
        link = self.work / 'hardlink.json'
        os.link(self.context, link)
        result = self.cli('review_criteria_binding.py', *self.init_args(context=link), code=2)
        self.assertIn('hardlinked', result.stderr)
        junction = self.work / 'junction'
        _winapi.CreateJunction(str(self.inputs), str(junction))
        result = self.cli('review_criteria_binding.py',
                          *self.init_args(context=junction / self.context.name), code=2)
        self.assertIn('bundle root cannot be opened safely', result.stderr)
        self.assertFalse(self.manifest.exists())

    def test_binding_read_once_parse_and_hash_same_bytes(self):
        self.binding_inputs()
        original = BINDING._read_windows_bytes
        seen, captured = [], {}

        def changing_read(path, limit):
            raw = original(path, limit)
            seen.append(path)
            captured[path] = raw
            path.write_bytes(b'changed after checked read')
            return raw

        with patch.object(BINDING, '_read_windows_bytes', side_effect=changing_read):
            self.assertEqual(BINDING.main(list(map(str, self.init_args()))), 0)
        self.assertEqual(seen, [self.context, self.registry])
        authority = read_json(self.manifest)['context_authority']
        self.assertEqual(authority['context_sha256'], digest(captured[self.context]))
        self.assertEqual(authority['registry_sha256'], digest(captured[self.registry]))

    def test_windows_binding_write_failures_retain_partial_outputs(self):
        def fail_after_prefix(fd, raw):
            os.write(fd, raw[:5])
            raise OSError('synthetic write failure')

        created = self.work / 'partial-create.json'
        existing = self.work / 'existing.json'
        existing.write_bytes(b'original bytes')
        with patch.object(BINDING, '_write_all', side_effect=fail_after_prefix):
            with self.assertRaisesRegex(OSError, 'synthetic write failure'):
                BINDING._atomic_create(created, {'fixture': True})
            with self.assertRaisesRegex(OSError, 'synthetic write failure'):
                BINDING._atomic_replace(existing, {'fixture': True})
        self.assertEqual(len(created.read_bytes()), 5)
        self.assertEqual(existing.read_bytes(), b'original bytes')
        partials = list(self.work.glob('.existing.json.*'))
        self.assertEqual(len(partials), 1)
        self.assertEqual(len(partials[0].read_bytes()), 5)

    def test_packet_build_validate_render_cli(self):
        inventory = self.packet_inputs()
        self.cli('build_submission_packet_manifest.py', *self.packet_args())
        self.cli('build_submission_packet_manifest.py', *self.packet_args('validate'))
        self.cli('build_submission_packet_manifest.py', *self.packet_args('render'))
        manifest = read_json(self.pmanifest)
        self.assertEqual(len(manifest['packet_observations']), len(inventory['artifacts']))
        expected = {row['artifact_id']: row for row in inventory['artifacts']}
        for row in manifest['packet_observations']:
            self.assertEqual(row['status'], 'DOCUMENTED')
            self.assertEqual(row['observed_sha256'], expected[row['artifact_id']]['declared_sha256'])
            self.assertEqual(row['observed_size_bytes'], expected[row['artifact_id']]['declared_size_bytes'])
        self.assertEqual(manifest['administrative_status']['authorization_status']['value'], 'not_provided')
        self.assertEqual(manifest['acceptance_boundary']['status'], 'ACCEPTANCE_UNVERIFIED')
        rendered = (self.work / 'packet-render.md').read_text(encoding='utf-8')
        self.assertIn('does not authorize recruitment', rendered)
        self.assertNotIn('Synthetic software fixture', rendered)

    def test_packet_changed_missing_and_stale_manifest_cli(self):
        inventory = self.packet_inputs()
        self.cli('build_submission_packet_manifest.py', *self.packet_args())
        first, second, _ = inventory['artifacts']
        (self.packet / first['relative_path']).write_bytes(b'changed')
        missing = self.packet / second['relative_path']
        missing.rename(missing.with_name('retained-missing.bin'))
        self.cli('build_submission_packet_manifest.py', *self.packet_args('validate'), code=2)
        changed = self.work / 'changed-manifest.json'
        self.cli('build_submission_packet_manifest.py', *self.packet_args(output=changed))
        rows = {row['artifact_id']: row for row in read_json(changed)['packet_observations']}
        self.assertEqual(rows[first['artifact_id']]['observed_sha256'], digest(b'changed'))
        self.assertEqual(rows[first['artifact_id']]['reason_codes'],
                         ['ARTIFACT_DIGEST_MISMATCH', 'ARTIFACT_SIZE_MISMATCH'])
        self.assertEqual(rows[second['artifact_id']]['state'], 'not_located')
        missing_parent = copy.deepcopy(inventory)
        missing_parent['artifacts'][0]['relative_path'] = 'missing-parent/file'
        rows = PACKET.observe_submission_packet(missing_parent, self.packet)
        self.assertEqual(next(row for row in rows if row['artifact_id'] == first['artifact_id'])['state'], 'not_located')

    def test_packet_unsafe_paths_and_nonregular_cli(self):
        inventory = self.packet_inputs()
        for index, relative in enumerate(('../outside', 'D:/outside', 'D:outside', 'a\\b',
                                         'a//b', 'a/../b', 'NUL', 'draft:stream', 'draft.', 'directory')):
            changed = copy.deepcopy(inventory)
            changed['artifacts'][0]['relative_path'] = relative
            path = self.write_json(self.inputs / f'unsafe-{index}.json', changed)
            if relative == 'directory':
                (self.packet / 'directory').mkdir()
            with self.subTest(relative=relative):
                self.cli('build_submission_packet_manifest.py', *self.packet_args(inventory=path), code=2)
                self.assertFalse(self.pmanifest.exists())
        for root in (self.packet.anchor, self.work / 'missing-root'):
            self.cli('build_submission_packet_manifest.py', *self.packet_args(root=root), code=2)

    def test_packet_hardlinks_junctions_and_metadata_input_links_cli(self):
        import _winapi

        inventory = self.packet_inputs()
        target = self.packet / inventory['artifacts'][0]['relative_path']
        os.link(target, self.work / 'outside-hardlink')
        result = self.cli('build_submission_packet_manifest.py', *self.packet_args(), code=2)
        self.assertIn('hardlinked', result.stderr)
        junction = self.work / 'packet-junction'
        _winapi.CreateJunction(str(self.packet), str(junction))
        result = self.cli('build_submission_packet_manifest.py', *self.packet_args(root=junction), code=2)
        self.assertIn('bundle root cannot be opened safely', result.stderr)
        meta = self.work / 'linked-inventory.json'
        os.link(self.inventory, meta)
        result = self.cli('build_submission_packet_manifest.py', *self.packet_args(inventory=meta), code=2)
        self.assertIn('cannot read JSON input', result.stderr)
        self.assertIn('hardlinked', result.stderr)
        self.assertFalse(self.pmanifest.exists())

    def test_packet_junction_member_fails_not_missing(self):
        import _winapi

        inventory = self.packet_inputs()
        original = self.packet / 'nested \u6d4b\u8bd5'
        retained = self.work / 'retained-packet-members'
        original.rename(retained)
        _winapi.CreateJunction(str(retained), str(original))
        self.cli('build_submission_packet_manifest.py', *self.packet_args(), code=2)
        self.assertFalse(self.pmanifest.exists())

    def test_packet_closed_gate_does_not_touch_missing_root(self):
        self.packet_inputs()
        self.cli('build_submission_packet_manifest.py', 'build', '--inventory', self.inventory,
                 '--packet-root', self.work / 'missing-root', '--output', self.pmanifest)
        manifest = read_json(self.pmanifest)
        self.assertEqual(manifest['packet_observations'], [])
        self.assertEqual(manifest['administrative_status']['submission_readiness'], 'unresolved')

    def test_packet_read_once_hash_and_size_use_same_bytes(self):
        inventory = self.packet_inputs()
        original = REVISION.ArtifactStore._open_relative
        seen = []

        def changing_read(store, relative, label):
            raw = original(store, relative, label)
            seen.append(relative)
            with self.assertRaises(OSError) as caught:
                self.packet.rename(self.work / 'renamed-packet')
            self.assertIn(caught.exception.winerror, (5, 32))
            (self.packet / relative).write_bytes(b'changed after checked read')
            return raw

        with patch.object(REVISION.ArtifactStore, '_open_relative', new=changing_read):
            rows = PACKET.observe_submission_packet(inventory, self.packet)
        self.assertEqual(seen, [row['relative_path'] for row in inventory['artifacts']])
        self.assertTrue(all(row['status'] == 'DOCUMENTED' for row in rows))

    def test_cli_existing_writers_fail_closed_not_missing(self):
        self.binding_inputs()
        with self.context.open('r+b'):
            self.cli('review_criteria_binding.py', *self.init_args(), code=2)
        inventory = self.packet_inputs()
        with (self.packet / inventory['artifacts'][0]['relative_path']).open('r+b'):
            self.cli('build_submission_packet_manifest.py', *self.packet_args(), code=2)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.pmanifest.exists())

    def test_packet_strict_json_and_byte_limits(self):
        self.packet_inputs()
        for index, raw in enumerate((b'{"x":1,"x":2}', b'{"x":Infinity}', b'\xff')):
            path = self.inputs / f'invalid-{index}.json'
            path.write_bytes(raw)
            self.cli('build_submission_packet_manifest.py', *self.packet_args(inventory=path), code=2)
        with patch.object(PACKET, 'MAX_MANIFEST_BYTES', 8):
            with self.assertRaises(PACKET.ContractError):
                PACKET.load_json(self.inventory)
        with patch.object(PACKET, 'MAX_TOTAL_BYTES', 1):
            with self.assertRaisesRegex(PACKET.ContractError, 'total limit'):
                PACKET.observe_submission_packet(read_json(self.inventory), self.packet)

    def test_symlinks_rejected_by_both_clis_when_available(self):
        self.binding_inputs()
        link = self.work / 'symlink.json'
        try:
            link.symlink_to(self.context)
        except OSError as exc:
            if exc.winerror in (1, 50, 1314):
                self.skipTest(f'Host cannot create symlinks: {exc}')
            raise
        result = self.cli('review_criteria_binding.py', *self.init_args(context=link), code=2)
        self.assertIn('cannot safely read explicit input', result.stderr)
        self.packet_inputs()
        result = self.cli('build_submission_packet_manifest.py', *self.packet_args(inventory=link), code=2)
        self.assertIn('cannot safely read explicit input', result.stderr)


if __name__ == '__main__':
    unittest.main()
