"""Deterministic adapter tests; all temporary artifacts are deliberately retained.

Run with RSK_PDF_TEST_ROOT pointing to an existing approved task directory (D/E
on Windows). No parser
or classifier is installed by these tests. Parser-dependent tests explicitly
skip when pypdf is absent; protocol fixtures are not real parsing measurements.
"""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/research-starter-paper/scripts/research_pdf_preflight.py'
SPEC = importlib.util.spec_from_file_location('research_pdf_preflight_tests', SCRIPT)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None
RUN = subprocess.run


def synthetic_pdf(declared=1):
    """A blank one-page PDF with a classic xref; no external generator needed."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               f'<< /Type /Pages /Kids [3 0 R] /Count {declared} >>'.encode(),
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
    data = b'%PDF-1.4\n'
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 4\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data + f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


class PdfPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get('RSK_PDF_TEST_ROOT')
        if not configured:
            raise unittest.SkipTest('Set RSK_PDF_TEST_ROOT to an explicit D/E task directory.')
        base = ADAPTER._absolute_path(configured)
        if not base.is_dir() or (os.name == 'nt' and base.drive.upper() not in ('D:', 'E:')):
            raise RuntimeError('Test root must exist on D/E.')
        cls.retained = Path(tempfile.mkdtemp(prefix='pdf-preflight-tests-', dir=base))
        print(f'\nRetained PDF preflight artifacts: {cls.retained}', flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='case-', dir=self.retained))
        self.pdf = self.work / 'synthetic source.pdf'
        self.pdf.write_bytes(synthetic_pdf())
        self.output = self.work / 'sidecar.json'

    def publish(self, **kwargs):
        return ADAPTER.publish_preflight(self.pdf, task_dir=self.work, output=self.output, **kwargs)

    def result(self, verdict='PASS', classify=False):
        result = {'schema': 'pdf_read_preflight/1', 'verdict': verdict,
                  'file': str(self.pdf), 'sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                  'declared_page_count': 1, 'enumerated_page_count': 1,
                  'reader_page_count': 1, 'warnings': [],
                  'generated_at': '2026-10-21T00:00:00+00:00', 'tool': 'pdf_read_preflight/1.0.0'}
        if verdict == 'FAIL':
            result['declared_page_count'] = 2
        if verdict == 'UNAVAILABLE':
            result.update({key: None for key in ADAPTER.COUNTS})
            result['warnings'] = ['pypdf-not-installed: protocol fixture']
        if classify:
            result.update(tool='pdf_read_preflight/1.1.0', verdict_scope='STRUCTURE_ONLY',
                          content_advisory='CONTENT_UNAVAILABLE' if verdict == 'PASS' else 'STRUCTURAL_UNAVAILABLE',
                          content_classification={'schema': 'pdf_content_classification/1', 'requested': True,
                                                  'status': 'UNAVAILABLE', 'reason': 'DEPENDENCY_ABSENT' if verdict == 'PASS' else 'STRUCTURAL_NOT_PASS',
                                                  'classification': None, 'confidence': None, 'pages_needing_ocr': None})
        return result

    def response(self, result=None, raw=None, returncode=0):
        return subprocess.CompletedProcess([], returncode,
                                           raw if raw is not None else json.dumps(result).encode(), b'')

    def test_real_stdout_only_preflight_on_synthetic_pdf(self):
        result = self.publish()
        self.assertEqual(json.loads(self.output.read_bytes()), result)
        self.assertEqual(result['sha256'], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual(result['verdict'], 'PASS' if HAS_PYPDF else 'UNAVAILABLE')
        if not HAS_PYPDF:
            self.assertTrue(any('pypdf-not-installed' in w for w in result['warnings']))

    def test_dependency_absence_and_classifier_unavailable_are_real_upstream_states(self):
        def without_site(command, **kwargs):
            kwargs['env']['PYTHONPATH'] = ''
            return RUN([command[0], '-S', *command[1:]], **kwargs)
        with patch.object(ADAPTER.subprocess, 'run', side_effect=without_site):
            result = self.publish(classify_content=True)
        self.assertEqual(result['verdict'], 'UNAVAILABLE')
        self.assertEqual(result['verdict_scope'], 'STRUCTURE_ONLY')
        self.assertEqual(result['content_advisory'], 'STRUCTURAL_UNAVAILABLE')
        self.assertEqual(result['content_classification']['reason'], 'STRUCTURAL_NOT_PASS')

    @unittest.skipUnless(HAS_PYPDF, 'pypdf absent: real parser PASS/FAIL cannot be verified')
    def test_real_parser_count_mismatch_remains_fail(self):
        self.pdf.write_bytes(synthetic_pdf(declared=2))
        self.assertEqual(self.publish()['verdict'], 'FAIL')

    @unittest.skipUnless(HAS_PYPDF, 'pypdf absent: repair-warning semantics require parser')
    def test_real_parser_trailing_data_remains_unavailable(self):
        self.pdf.write_bytes(synthetic_pdf() + b'broken incremental update')
        self.assertEqual(self.publish()['verdict'], 'UNAVAILABLE')

    @unittest.skipUnless(HAS_PYPDF, 'pypdf absent: classifier path needs structural PASS')
    def test_real_missing_optional_classifier_preserves_structural_pass(self):
        if importlib.util.find_spec('pdf_inspector') is not None:
            self.skipTest('Absence test requires pdf_inspector to be absent; no dependency is removed.')
        result = self.publish(classify_content=True)
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['verdict_scope'], 'STRUCTURE_ONLY')
        self.assertEqual(result['content_advisory'], 'CONTENT_UNAVAILABLE')
        self.assertEqual(result['content_classification']['reason'], 'DEPENDENCY_ABSENT')

    def test_structural_verdicts_are_preserved_from_validated_protocol_fixtures(self):
        for verdict in ('PASS', 'FAIL', 'UNAVAILABLE'):
            with self.subTest(verdict=verdict):
                self.output = self.work / (verdict + '.json')
                expected = self.result(verdict)
                with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(expected)):
                    self.assertEqual(self.publish(), expected)

    def test_classifier_advisory_does_not_upgrade_structural_verdict(self):
        for verdict in ('PASS', 'FAIL', 'UNAVAILABLE'):
            self.output = self.work / (verdict + '.json')
            expected = self.result(verdict, classify=True)
            with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(expected)):
                self.assertEqual(self.publish(classify_content=True), expected)
        for classification, pages in (('TEXT_AVAILABLE', []), ('OCR_RECOMMENDED', [0])):
            self.output = self.work / (classification + '.json')
            expected = self.result(classify=True)
            expected['content_advisory'] = classification
            expected['content_classification'].update(status='CLASSIFIED', reason='CLASSIFIED',
                                                       classification=classification, confidence=0.75,
                                                       pages_needing_ocr=pages)
            with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(expected)):
                self.assertEqual(self.publish(classify_content=True), expected)

    def test_invalid_json_or_semantics_never_creates_output(self):
        bad = [b'[]', b'{}', b'{', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff',
               b' ' * (ADAPTER.MAX_JSON_BYTES + 1)]
        for key, value in [('sha256', '0' * 64), ('file', str(self.output)), ('verdict', 'CLEAN'),
                           ('declared_page_count', True), ('warnings', ['repair']),
                           ('schema', 'wrong'), ('tool', 'unknown'), ('generated_at', 'yesterday')]:
            result = self.result()
            result[key] = value
            bad.append(json.dumps(result).encode())
        bad.append(json.dumps(self.result()).encode() + b'{}')
        for raw in bad:
            with self.subTest(raw=raw[:80]), patch.object(ADAPTER.subprocess, 'run', return_value=self.response(raw=raw)):
                with self.assertRaises(ADAPTER.PreflightError):
                    self.publish()
                self.assertFalse(self.output.exists())

    def test_invalid_classifier_scope_or_claim_is_rejected(self):
        good = self.result(classify=True)
        mutations = []
        for key, value in [('verdict_scope', 'CONTENT_VERIFIED'), ('content_advisory', 'TEXT_AVAILABLE')]:
            row = copy.deepcopy(good)
            row[key] = value
            mutations.append(row)
        row = copy.deepcopy(good)
        row['content_classification']['reason'] = 'INVENTED_STATE'
        mutations.append(row)
        row = self.result('FAIL', classify=True)
        row['content_classification'].update(status='CLASSIFIED', reason='CLASSIFIED',
                                             classification='TEXT_AVAILABLE', confidence=1, pages_needing_ocr=[])
        row['content_advisory'] = 'TEXT_AVAILABLE'
        mutations.append(row)
        for confidence, pages in ((True, []), (10 ** 400, []), (0.5, [True]), (0.5, [1])):
            row = copy.deepcopy(good)
            row['content_advisory'] = 'OCR_RECOMMENDED'
            row['content_classification'].update(status='CLASSIFIED', reason='CLASSIFIED',
                                                 classification='OCR_RECOMMENDED', confidence=confidence,
                                                 pages_needing_ocr=pages)
            mutations.append(row)
        for row in mutations:
            with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(row)):
                with self.assertRaises(ADAPTER.PreflightError):
                    self.publish(classify_content=True)
        self.assertFalse(self.output.exists())

    def test_command_and_child_storage_are_explicit(self):
        with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(self.result())) as run:
            self.publish()
        command = run.call_args.args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[-2:], [str(ADAPTER.UPSTREAM), str(self.pdf)])
        self.assertNotIn('--output', command)
        self.assertNotIn('--classifier-diagnostics', command)
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs['shell'])
        self.assertEqual(kwargs['cwd'], self.work)
        for key in ('TEMP', 'TMP', 'TMPDIR'):
            self.assertEqual(kwargs['env'][key], str(self.work))
        self.assertEqual(kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')

    def test_existing_output_is_never_clobbered_or_dispatched(self):
        self.output.write_bytes(b'keep me')
        with patch.object(ADAPTER.subprocess, 'run') as run:
            with self.assertRaises(ADAPTER.PreflightError):
                self.publish()
            run.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b'keep me')

    def test_exclusive_create_rejects_output_appearing_after_preflight(self):
        def race(*args, **kwargs):
            self.output.write_bytes(b'other writer')
            return self.response(self.result())
        with patch.object(ADAPTER.subprocess, 'run', side_effect=race):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual(self.output.read_bytes(), b'other writer')

    def test_path_escape_aliases_and_c_drive_are_refused_before_dispatch(self):
        invalid = [dict(output=self.work / '..' / 'escape.json'),
                   dict(output=self.work / 'nested' / 'sidecar.json'),
                   dict(output=self.pdf), dict(output='relative.json'),
                   dict(output=str(self.output) + '/'),
                   dict(output=self.work / 'alias.json:stream'),
                   dict(output=self.work / 'NUL.json'), dict(task_dir='C:/forbidden')]
        for changes in invalid:
            options = dict(task_dir=self.work, output=self.output)
            options.update(changes)
            with self.subTest(changes=changes), patch.object(ADAPTER.subprocess, 'run') as run:
                with self.assertRaises(ADAPTER.PreflightError):
                    ADAPTER.publish_preflight(self.pdf, **options)
                run.assert_not_called()

    def test_python310_reserved_name_fallback(self):
        with patch.object(ADAPTER.os.path, 'isreserved', None, create=True):
            self.assertEqual(ADAPTER._absolute_path(self.pdf), self.pdf)
            for name in ('NUL.json', 'COM1.pdf', 'AUX.txt', 'x.json:stream', 'trailing. '):
                with self.subTest(name=name), self.assertRaises(ADAPTER.PreflightError):
                    ADAPTER._absolute_path(self.work / name)

    def test_hardlinked_input_and_existing_hardlinked_output_are_refused(self):
        alias = self.work / 'hardlink.pdf'
        os.link(self.pdf, alias)
        with patch.object(ADAPTER.subprocess, 'run') as run:
            with self.assertRaises(ADAPTER.PreflightError):
                self.publish()
            run.assert_not_called()
        other = self.work / 'other.pdf'
        other.write_bytes(synthetic_pdf())
        os.link(alias, self.output)
        with self.assertRaises(ADAPTER.PreflightError):
            ADAPTER.publish_preflight(other, task_dir=self.work, output=self.output)
        self.assertEqual(alias.read_bytes(), synthetic_pdf())

    def test_symlink_input_is_refused(self):
        alias = self.work / 'symbolic.pdf'
        try:
            alias.symlink_to(self.pdf)
        except OSError as exc:
            self.skipTest(f'Symlink creation unavailable: {exc}')
        with self.assertRaises(ADAPTER.PreflightError):
            ADAPTER.publish_preflight(alias, task_dir=self.work, output=self.output)

    def test_link_metadata_is_refused_even_without_symlink_creation_privilege(self):
        for mode, attributes, links in ((stat.S_IFLNK, 0, 1), (stat.S_IFREG, 0x400, 1),
                                        (stat.S_IFREG, 0, 2)):
            info = SimpleNamespace(st_mode=mode, st_file_attributes=attributes, st_nlink=links)
            with patch.object(Path, 'lstat', return_value=info):
                with self.assertRaises(ADAPTER.PreflightError):
                    ADAPTER._check_node(self.pdf)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_junction_task_directory_is_refused(self):
        target = self.work / 'target'
        target.mkdir()
        junction = self.work / 'junction'
        result = RUN(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(target)],
                     capture_output=True, check=False)
        if result.returncode:
            self.skipTest('Junction creation unavailable: ' + result.stderr.decode(errors='replace'))
        with self.assertRaises(ADAPTER.PreflightError):
            ADAPTER.publish_preflight(self.pdf, task_dir=junction, output=junction / 'out.json')
        nested = target / 'nested'
        nested.mkdir()
        with self.assertRaises(ADAPTER.PreflightError):
            ADAPTER.publish_preflight(self.pdf, task_dir=junction / 'nested',
                                      output=junction / 'nested' / 'out.json')
        linked_input = target / 'source.pdf'
        linked_input.write_bytes(synthetic_pdf())
        with self.assertRaises(ADAPTER.PreflightError):
            ADAPTER.publish_preflight(junction / 'source.pdf', task_dir=self.work, output=self.output)
        self.assertFalse((target / 'out.json').exists())
        self.assertEqual(list(nested.iterdir()), [])

    def test_changed_input_fingerprint_is_refused_before_publication(self):
        real = ADAPTER._fingerprint
        calls = 0
        def changed(fd):
            nonlocal calls
            calls += 1
            stamp, digest = real(fd)
            return stamp, digest if calls == 1 else '0' * 64
        with patch.object(ADAPTER, '_fingerprint', side_effect=changed), \
                patch.object(ADAPTER.subprocess, 'run', return_value=self.response(self.result())):
            with self.assertRaisesRegex(ADAPTER.PreflightError, 'Input changed'):
                self.publish()
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows sharing-lock test')
    def test_windows_input_and_task_directory_are_held_during_child_call(self):
        expected = self.result()
        def mutate(*args, **kwargs):
            with self.assertRaises(OSError):
                self.pdf.write_bytes(b'changed')
            with self.assertRaises(OSError):
                self.work.rename(self.work.with_name(self.work.name + '-moved'))
            return self.response(expected)
        with patch.object(ADAPTER.subprocess, 'run', side_effect=mutate):
            self.publish()
        self.assertEqual(self.pdf.read_bytes(), synthetic_pdf())

    def test_write_failure_retains_partial_file_without_cleanup(self):
        real_write = os.write
        calls = 0
        def fail(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, data[:10])
            raise OSError('synthetic disk failure')
        with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(self.result())), \
                patch.object(ADAPTER.os, 'write', side_effect=fail):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual(self.output.stat().st_size, 10)

    def test_upstream_error_timeout_missing_input_and_directory_do_not_publish(self):
        for effect in (subprocess.TimeoutExpired(['python'], 1), OSError('cannot start')):
            with patch.object(ADAPTER.subprocess, 'run', side_effect=effect):
                with self.assertRaises((OSError, subprocess.TimeoutExpired)):
                    self.publish()
            self.assertFalse(self.output.exists())
        with patch.object(ADAPTER.subprocess, 'run', return_value=self.response(raw=b'{}', returncode=2)):
            with self.assertRaises(ADAPTER.PreflightError):
                self.publish()
        for path in (self.work / 'absent.pdf', self.work):
            with self.assertRaises((OSError, ADAPTER.PreflightError)):
                ADAPTER.publish_preflight(path, task_dir=self.work, output=self.output)
        self.assertFalse(self.output.exists())

    def test_non_ascii_input_and_output_paths_work(self):
        self.pdf = self.work / '\u7814\u7a76 source.pdf'
        self.pdf.write_bytes(synthetic_pdf())
        self.output = self.work / '\u7ed3\u679c sidecar.json'
        result = self.publish()
        self.assertEqual(result['file'], str(self.pdf))
        self.assertEqual(json.loads(self.output.read_bytes()), result)

    def test_cli_returns_upstream_json_and_explicit_sidecar(self):
        env = dict(os.environ, TEMP=str(self.work), TMP=str(self.work), TMPDIR=str(self.work),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='', PYTHONUTF8='1', PYTHONNOUSERSITE='1')
        completed = RUN([sys.executable, '-B', '-s', str(SCRIPT), str(self.pdf),
                         '--task-dir', str(self.work), '--output', str(self.output)],
                        cwd=self.work, env=env, capture_output=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors='replace'))
        result = json.loads(completed.stdout)
        self.assertEqual(json.loads(self.output.read_bytes()), result)
        self.assertIn(result['verdict'], ('PASS', 'UNAVAILABLE'))


if __name__ == '__main__':
    unittest.main()
