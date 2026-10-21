"""Real-filesystem tests. Synthetic artifacts are retained, never cleaned up.

Set RSK_REVISION_TEST_ROOT (or TEMP/TMP/TMPDIR) to an approved work directory.
Windows runs require D: or E:, and PYTHONDONTWRITEBYTECODE=1.
"""

import copy
import errno
import hashlib
import importlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'skills/research-starter-paper/resources/research-engine'
sys.path.insert(0, str(ENGINE))
REVISION = importlib.import_module('scripts.revision_roadmap')
ANCHORS = importlib.import_module('scripts.ars_anchorize_draft')


def entry(relative, raw):
    return {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}


class RevisionStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = Path(os.environ.get('RSK_REVISION_TEST_ROOT', tempfile.gettempdir()))
        if os.name == 'nt' and (base.drive.upper() not in ('D:', 'E:')
                                or os.environ.get('PYTHONDONTWRITEBYTECODE') != '1'):
            raise RuntimeError('Set a D:/E: test work directory and PYTHONDONTWRITEBYTECODE=1')
        cls.retained = Path(tempfile.mkdtemp(prefix='revision-store-', dir=base))
        print(f'\nRetained revision-store fixtures: {cls.retained}', flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=self.retained))
        self.root = self.work / 'bundle'
        self.root.mkdir()

    def write(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return entry(relative, raw)

    def store(self):
        return REVISION.ArtifactStore(self.root)

    def test_unicode_spaces_and_exact_raw_bytes(self):
        renamed = self.work / 'bundle \u6d4b\u8bd5 \u00e9'
        self.root.rename(renamed)
        self.root = renamed
        raw = b'\xef\xbb\xbf{"text":"\xe6\xb5\x8b\xe8\xaf\x95"}\r\n\x00\xff\x1a'
        ref = self.write('folder \u6d4b\u8bd5 \U0001f9ea/paper \u00e9.bin', raw)
        artifact = self.store().read(ref, 'raw fixture')
        self.assertEqual(artifact.relative_path, ref['path'])
        self.assertEqual(artifact.raw, raw)
        self.assertEqual(REVISION.bytes_hash(artifact.raw), ref['sha256'])
        self.assertNotEqual(ref['sha256'], hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest())

    def test_empty_and_multichunk_artifacts(self):
        store = self.store()
        for name, raw in [('empty', b''), ('large', bytes(range(256)) * 8200)]:
            with self.subTest(name=name):
                self.assertEqual(store.read(self.write(name, raw), name).raw, raw)

    def test_cache_is_read_once_even_after_change_and_missing_input(self):
        ref = self.write('draft.md', b'original\r\n')
        store = self.store()
        first = store.read(ref, 'first')
        (self.root / ref['path']).write_bytes(b'changed\n')
        self.assertIs(store.read(ref, 'changed but cached'), first)
        (self.root / ref['path']).rename(self.root / 'retained-draft.md')
        self.assertIs(store.read(ref, 'missing but cached'), first)
        self.assertEqual(first.raw, b'original\r\n')
        with self.assertRaisesRegex(REVISION.ContractError, 'conflicting sha256'):
            store.read(entry(ref['path'], b'changed\n'), 'conflicting declaration')
        with self.assertRaises(REVISION.ContractError):
            self.store().read(ref, 'missing in new store')

    def test_hash_mismatch_is_not_cached(self):
        ref = self.write('draft.md', b'original')
        store = self.store()
        (self.root / ref['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(REVISION.ContractError, 'sha256 mismatch'):
            store.read(ref, 'changed')
        (self.root / ref['path']).write_bytes(b'original')
        self.assertEqual(store.read(ref, 'restored').raw, b'original')

    def test_relative_path_escape_and_unnormalized_paths(self):
        (self.work / 'outside').write_bytes(b'outside')
        store = self.store()
        for name in ('../outside', 'a/../../outside', '/outside', '', './draft',
                     'a//draft', 'a/./draft', 'a/../draft', 'a/', 'a\\draft'):
            with self.subTest(name=name), self.assertRaises(REVISION.ContractError):
                store.read(entry(name, b'outside'), 'unsafe path')

    def test_directory_artifact_and_missing_root(self):
        (self.root / 'directory').mkdir()
        with self.assertRaises(REVISION.ContractError):
            self.store().read(entry('directory', b''), 'directory')
        with self.assertRaises(REVISION.ContractError):
            REVISION.ArtifactStore(self.work / 'missing')
        file = self.root / 'file'
        file.write_bytes(b'file')
        with self.assertRaises(REVISION.ContractError):
            REVISION.ArtifactStore(file)

    def test_size_limit_and_failure_handle_release(self):
        ref = self.write('limited', b'123456789')
        store = self.store()
        with patch.object(REVISION, 'MAX_ARTIFACT_BYTES', 8):
            with self.assertRaisesRegex(REVISION.ContractError, 'exceeds 8 bytes'):
                store.read(ref, 'oversize')
        self.assertEqual(store.read(ref, 'normal limit').raw, b'123456789')
        (self.root / 'limited').rename(self.root / 'retained-limited')
        self.root.rename(self.work / 'retained-bundle')

    def make_bundle(self):
        # Empty finding sets exercise a real review_noop chain, not model output.
        def put(name, value):
            return self.write(name, (json.dumps(value, sort_keys=True) + '\r\n').encode())

        base = ANCHORS.anchorize_text('# Synthetic fixture\n\nNo research result is claimed.\n')
        draft = self.write('draft.md', base.encode())
        manifest = put('blocks.json', ANCHORS.build_manifest(base.encode(), REVISION.parse_document(base)))
        receipt = put('receipt.json', {
            'schema_version': 'integrity-pass-receipt/1.0', 'receipt_id': 'INTEGRITY-PASS-test',
            'checked_draft_sha256': draft['sha256'], 'verdict': 'PASS', 'open_issue_count': 0,
            'issued_by': 'integrity_verification_agent',
        })
        roadmap = put('roadmap.json', {
            'schema_version': 'revision-roadmap/1.0', 'revision_round': 1,
            'base_draft_sha256': draft['sha256'], 'block_manifest_sha256': manifest['sha256'],
            'items': [], 'total_items': 0,
            'obligation_counts': {'must_fix': 0, 'should_fix': 0, 'consider': 0},
            'editorial_decision': 'Accept', 'consensus_summary': 'Synthetic empty finding set.',
            'dissenting_opinions': [],
        })
        surface = put('surfaces.json', {
            'schema_version': 'claim-surface-manifest/1.0', 'revision_round': 1,
            'roadmap_sha256': roadmap['sha256'], 'base_draft_sha256': draft['sha256'],
            'claim_intent_sources': [], 'surfaces': [],
        })
        author = put('author.json', {
            'schema_version': 'author-adjudication/1.0', 'revision_round': 1,
            'roadmap_sha256': roadmap['sha256'], 'base_draft_sha256': draft['sha256'],
            'claim_surface_manifest_sha256': surface['sha256'], 'adjudication_status': 'complete',
            'author_events': [{'event_id': 'AUTHOR-EVENT-test',
                               'source': 'explicit_session_user_message', 'actor_role': 'author',
                               'input_sha256': hashlib.sha256(b'synthetic test event').hexdigest()}],
            'display_order': {'mode': 'source_traceability', 'item_ids': [],
                              'author_event_id': 'AUTHOR-EVENT-test'},
            'author_adjudications': [], 'collateral_authorizations': [],
        })
        return {
            'schema_version': 'revision-evidence-bundle/1.0',
            'chain_start': {'first_revision_round': 1, 'draft': draft, 'block_manifest': manifest,
                            'integrity_pass_receipt': receipt},
            'rounds': [{'kind': 'review_noop', 'revision_round': 1, 'pre_round_draft': draft,
                        'pre_round_block_manifest': manifest, 'revision_roadmap': roadmap,
                        'claim_surface_manifest': surface, 'author_adjudication': author,
                        'post_round_draft': draft}],
            'final_draft': draft,
        }

    def test_valid_bundle_and_schema_checks(self):
        bundle = self.make_bundle()
        REVISION.validate_bundle(bundle, root=self.root)
        invalid = copy.deepcopy(bundle)
        invalid['unexpected'] = True
        with self.assertRaisesRegex(REVISION.ContractError, 'Additional properties'):
            REVISION.validate_bundle(invalid, root=self.root)

    def test_changed_and_missing_bundle_inputs(self):
        bundle = self.make_bundle()
        REVISION.validate_bundle(bundle, root=self.root)
        for name in ('draft.md', 'blocks.json', 'receipt.json', 'roadmap.json',
                     'surfaces.json', 'author.json'):
            with self.subTest(name=name):
                path = self.root / name
                raw = path.read_bytes()
                path.write_bytes(raw + b' ')
                with self.assertRaisesRegex(REVISION.ContractError, 'sha256 mismatch'):
                    REVISION.validate_bundle(bundle, root=self.root)
                path.write_bytes(raw)
                retained = path.with_name(name + '.retained')
                path.rename(retained)
                with self.assertRaises(REVISION.ContractError):
                    REVISION.validate_bundle(bundle, root=self.root)
                path.write_bytes(raw)
        REVISION.validate_bundle(bundle, root=self.root)

    def test_rehashed_invalid_receipt_still_fails_contract(self):
        bundle = self.make_bundle()
        receipt = json.loads((self.root / 'receipt.json').read_bytes())
        receipt['checked_draft_sha256'] = '0' * 64
        bundle['chain_start']['integrity_pass_receipt'] = self.write(
            'receipt-invalid.json', json.dumps(receipt).encode())
        with self.assertRaisesRegex(REVISION.ContractError, 'not bound to chain-start draft'):
            REVISION.validate_bundle(bundle, root=self.root)

    @unittest.skipUnless(os.name == 'nt', 'Real Windows handle semantics')
    def test_windows_path_aliases_and_streams(self):
        store = self.store()
        for name in ('C:/outside', 'C:outside', '//server/share/file', '\\\\?\\D:\\file',
                     'draft:stream', 'draft::$DATA', 'NUL', 'nul.txt', 'CON', 'COM1.txt',
                     'LPT\u00b2', 'CONOUT$', 'draft.', 'draft ', 'a /draft', 'a./draft',
                     'a?b', 'a*b', 'a|b', 'a<b', 'a>b', 'a"b', 'a\x00b', 'a\nb'):
            with self.subTest(name=name), self.assertRaises(REVISION.ContractError):
                store.read(entry(name, b''), 'unsafe alias')
        for root in (Path('D:relative'), Path('\\\\server\\share'),
                     Path('\\\\?\\' + str(self.root)), self.root / '..' / 'bundle'):
            with self.subTest(root=root), self.assertRaises(REVISION.ContractError):
                REVISION.ArtifactStore(root)

    @unittest.skipUnless(os.name == 'nt', 'Windows hardlink policy')
    def test_hardlinked_artifact(self):
        ref = self.write('original', b'linked bytes')
        try:
            os.link(self.root / 'original', self.work / 'outside-hardlink')
        except OSError as exc:
            if exc.winerror in (1, 50, 1314):
                self.skipTest(f'Host cannot create hardlinks: {exc}')
            raise
        with self.assertRaisesRegex(REVISION.ContractError, 'hardlinked'):
            self.store().read(ref, 'hardlink')

    def test_file_symlink(self):
        outside = self.work / 'outside'
        outside.write_bytes(b'outside')
        try:
            (self.root / 'link').symlink_to(outside)
        except OSError as exc:
            if os.name == 'nt' and exc.winerror in (1, 50, 1314):
                self.skipTest(f'Host cannot create symlinks: {exc}')
            raise
        with self.assertRaises(REVISION.ContractError):
            self.store().read(entry('link', b'outside'), 'symlink')

    @unittest.skipUnless(os.name == 'nt', 'Windows root and directory reparse policy')
    def test_directory_and_root_symlink(self):
        outside = self.work / 'outside'
        outside.mkdir()
        (outside / 'file').write_bytes(b'outside')
        link = self.root / 'link'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            if exc.winerror in (1, 50, 1314):
                self.skipTest(f'Host cannot create directory symlinks: {exc}')
            raise
        with self.assertRaises(REVISION.ContractError):
            self.store().read(entry('link/file', b'outside'), 'directory link')
        with self.assertRaises(REVISION.ContractError):
            REVISION.ArtifactStore(link)

    @unittest.skipUnless(os.name == 'nt', 'Real Windows junctions')
    def test_junction_in_artifact_root_and_root_ancestor(self):
        import _winapi

        outside = self.work / 'outside'
        outside.mkdir()
        (outside / 'nested').mkdir()
        (outside / 'file').write_bytes(b'outside')
        link = self.root / 'junction'
        _winapi.CreateJunction(str(outside), str(link))
        with self.assertRaises(REVISION.ContractError):
            self.store().read(entry('junction/file', b'outside'), 'junction')
        for root in (link, link / 'nested'):
            with self.subTest(root=root), self.assertRaises(REVISION.ContractError):
                REVISION.ArtifactStore(root)

    @unittest.skipUnless(os.name == 'nt', 'Real Windows share modes')
    def test_existing_writer_prevents_read(self):
        ref = self.write('draft', b'original')
        store = self.store()
        with (self.root / 'draft').open('r+b'):
            with self.assertRaises(REVISION.ContractError):
                store.read(ref, 'writer already open')
        self.assertEqual(store.read(ref, 'writer closed').raw, b'original')

    @unittest.skipUnless(os.name == 'nt', 'Real Windows share modes')
    def test_live_read_prevents_ancestor_file_rename_and_write(self):
        ref = self.write('nested/draft', b'original')
        store = self.store()
        entered, release = threading.Event(), threading.Event()
        results, errors = [], []
        original_read = store._windows.read_chunk

        def held_read(handle, size):
            entered.set()
            if not release.wait(15):
                raise RuntimeError('Timed out waiting for share-mode checks')
            return original_read(handle, size)

        def read():
            try:
                results.append(store.read(ref, 'held read'))
            except Exception as exc:
                errors.append(exc)

        # Only the timing gate is patched. Opens, reads, renames and writes use
        # the actual Windows APIs; os and security checks are never patched.
        with patch.object(store._windows, 'read_chunk', side_effect=held_read):
            worker = threading.Thread(target=read)
            worker.start()
            try:
                self.assertTrue(entered.wait(10), errors)
                for path in (self.root, self.root / 'nested', self.root / 'nested/draft'):
                    with self.subTest(path=path), self.assertRaises(OSError) as caught:
                        path.rename(path.with_name(path.name + '-renamed'))
                    self.assertIn(caught.exception.winerror, (5, 32))
                with self.assertRaises(OSError) as caught:
                    (self.root / 'nested/draft').write_bytes(b'changed')
                self.assertEqual(caught.exception.errno, errno.EACCES)
            finally:
                release.set()
                worker.join(20)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([result.raw for result in results], [b'original'])
        (self.root / 'nested/draft').write_bytes(b'writer works after read')
        (self.root / 'nested/draft').rename(self.root / 'nested/retained-draft')
        (self.root / 'nested').rename(self.root / 'retained-nested')
        self.root.rename(self.work / 'retained-bundle')

    @unittest.skipUnless(os.name == 'nt', 'Windows root identity binding')
    def test_root_substitution_between_creation_and_read(self):
        ref = self.write('draft', b'original')
        store = self.store()
        self.root.rename(self.work / 'retained-original-root')
        self.root.mkdir()
        self.write('draft', b'original')
        with self.assertRaisesRegex(REVISION.ContractError, 'root changed'):
            store.read(ref, 'replacement root')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction substitution')
    def test_directory_replaced_by_junction_after_store_creation(self):
        import _winapi

        ref = self.write('nested/draft', b'original')
        store = self.store()
        original = self.root / 'nested'
        retained = self.work / 'retained-directory'
        original.rename(retained)
        _winapi.CreateJunction(str(retained), str(original))
        with self.assertRaises(REVISION.ContractError):
            store.read(ref, 'replacement junction with identical bytes')

    @unittest.skipUnless(os.name == 'nt', 'Real Windows metadata access')
    def test_metadata_change_during_read_fails_fingerprint(self):
        import ctypes
        from ctypes import wintypes as w

        ref = self.write('draft', b'original')
        store = self.store()
        reader = store._windows
        original_read = reader.read_chunk
        set_time = ctypes.WinDLL('kernel32', use_last_error=True).SetFileTime
        set_time.argtypes = [w.HANDLE, ctypes.POINTER(w.FILETIME),
                             ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME)]
        set_time.restype = w.BOOL
        changed = False

        def change_metadata(handle, size):
            nonlocal changed
            raw = original_read(handle, size)
            if not changed:
                changed = True
                info = reader.info(handle, directory=False)
                ticks = (info.written.dwHighDateTime << 32 | info.written.dwLowDateTime) + 100000000
                stamp = w.FILETIME(ticks & 0xFFFFFFFF, ticks >> 32)
                # WRITE_ATTRIBUTES is not blocked by share modes. Exercise the
                # fingerprint using a real metadata handle, not fabricated stats.
                metadata = reader.create(str(self.root / 'draft'), 0x100, 7, None, 3, 0, None)
                if metadata == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if not set_time(metadata, None, None, ctypes.byref(stamp)):
                        raise ctypes.WinError(ctypes.get_last_error())
                finally:
                    reader.close(metadata)
            return raw

        with patch.object(reader, 'read_chunk', side_effect=change_metadata):
            with self.assertRaisesRegex(REVISION.ContractError, 'changed while read'):
                store.read(ref, 'metadata changed')
        self.assertTrue(changed)
        self.assertEqual(store.read(ref, 'stable metadata').raw, b'original')


if __name__ == '__main__':
    unittest.main()
