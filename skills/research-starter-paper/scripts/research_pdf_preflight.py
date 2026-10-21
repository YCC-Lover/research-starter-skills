"""Publish the bundled PDF preflight's stdout as a new, explicit local sidecar.

Usage: python -B research_pdf_preflight.py ABSOLUTE_PDF --task-dir ABSOLUTE_DIR
       --output ABSOLUTE_DIR/new.json [--classify-content]

The task directory must already exist on D:/E: on Windows. On POSIX, supply an
explicit caller-approved absolute task directory. Output must be its direct child. Existing
files, symlinks, junctions/reparse points, hardlinked inputs, device paths and
path traversal are refused. Missing/unreadable inputs cannot be fingerprinted
and are adapter errors; readable malformed PDFs and missing parser dependencies
retain upstream UNAVAILABLE. FAIL/UNAVAILABLE are data, not CLI failures.

Requires Python 3.10+; tested here on native Windows/Python 3.13, local files.
POSIX publication is not tested here. Launch/import with bytecode disabled.
Supported boundary: trusted local runtime/dependencies and a caller-controlled
task directory, not a filesystem sandbox. On Windows, open directory handles
deny deletion/renaming and the input handle denies writes/deletion during the
call. POSIX path checks require a stable, non-hostile namespace. Neither path
claims equivalence to upstream's descriptor-relative POSIX publication, a
transactional snapshot, or protection against privileged/mount manipulation.
Publication is exclusive but NOT atomic: a reader can see an incomplete file.
On any write/verification error the file is retained, never removed or retried.
Consumers must wait for successful completion and revalidate the PDF hash.

Only the fixed local upstream CLI is called, in stdout-only mode. Optional
classification is explicitly requested, advisory-only and not OCR. No model,
network, installer, cleanup, or upstream --output/diagnostics route is invoked.
Upstream JSON is preserved, including its optional STRUCTURE_ONLY field. Without
classification the legacy payload omits that field but is still structural only.
The timeout bounds the direct child, not an OS-level process/resource sandbox.
"""

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys


UPSTREAM = (Path(__file__).resolve().parents[1] /
            'resources/research-engine/scripts/pdf_read_preflight.py')
MAX_PDF_BYTES = 128 * 1024 * 1024
MAX_JSON_BYTES = 1024 * 1024
COUNTS = ('declared_page_count', 'enumerated_page_count', 'reader_page_count')
BASE_FIELDS = {'schema', 'verdict', 'file', 'sha256', *COUNTS,
               'warnings', 'generated_at', 'tool'}
CONTENT_FIELDS = {'verdict_scope', 'content_advisory', 'content_classification'}
CONTENT_UNAVAILABLE_REASONS = {
    'DEPENDENCY_ABSENT', 'CLASSIFIER_ERROR', 'INVALID_CLASSIFIER_RESULT',
    'WORKER_LAUNCH_ERROR', 'WORKER_IO_ERROR', 'WORKER_TIMEOUT',
    'WORKER_STDOUT_LIMIT', 'WORKER_STDERR_LIMIT', 'WORKER_SIGNAL',
    'WORKER_NONZERO_EXIT', 'WORKER_MALFORMED_OUTPUT', 'WORKER_INVALID_OUTPUT',
}


class PreflightError(ValueError):
    """The adapter cannot safely publish a fingerprint-bound result."""


def _absolute_path(value):
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or raw.startswith(('\\\\', '//'))
            or any(ord(c) < 32 for c in raw)):
        raise PreflightError('Expected an explicit local absolute path.')
    path = Path(raw)
    pieces = raw.replace('\\', '/').split('/')
    if not path.is_absolute() or any(p in ('.', '..') for p in pieces):
        raise PreflightError('Relative paths and traversal are forbidden.')
    isreserved = getattr(os.path, 'isreserved', None)
    for part in path.parts[1:]:
        if (':' in part or part.endswith((' ', '.')) or
                (os.name == 'nt' and isreserved is not None and isreserved(part)) or
                any(c in part for c in '<>"|?*') or
                part.split('.')[0].upper() in
                {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$',
                 *(f'COM{i}' for i in range(1, 10)),
                 *(f'LPT{i}' for i in range(1, 10))}):
            raise PreflightError('Ambiguous, device or alternate-stream path.')
    return path


def _check_node(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) & 0x400):
        raise PreflightError(f'Linked/reparse path is forbidden: {path}')
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise PreflightError(f'Expected a directory: {path}')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise PreflightError(f'Expected a single-linked regular file: {path}')
    return info


def _identity(info):
    return info.st_dev, info.st_ino


def _fingerprint(fd):
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise PreflightError('Input is not a single-linked regular file.')
    if before.st_size > MAX_PDF_BYTES:
        raise PreflightError('Input exceeds the 128 MiB adapter limit.')
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while chunk := os.read(fd, 1024 * 1024):
        total += len(chunk)
        if total > MAX_PDF_BYTES:
            raise PreflightError('Input exceeds the 128 MiB adapter limit.')
        digest.update(chunk)
    after = os.fstat(fd)
    stamp = lambda s: (_identity(s), s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    if stamp(before) != stamp(after) or total != after.st_size:
        raise PreflightError('Input changed while fingerprinting.')
    return stamp(after), digest.hexdigest()


@contextmanager
def _windows_handle(path, *, directory=False, create=False):
    # OPEN_REPARSE_POINT checks the opened object; ancestor handles stay held.
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD,
                                  wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL

    class TagInfo(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]

    kernel.GetFileInformationByHandleEx.argtypes = (
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    access = 0x80 if directory else (0xC0000000 if create else 0x80000000)
    sharing = 3 if directory else (0 if create else 1)
    flags = 0x00200000 | (0x02000000 if directory else 0)
    handle = kernel.CreateFileW(str(path), access, sharing, None,
                                1 if create else 3, flags, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        tag = TagInfo()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(tag),
                                                  ctypes.sizeof(tag)):
            raise ctypes.WinError(ctypes.get_last_error())
        if tag.attributes & 0x400 or bool(tag.attributes & 0x10) != directory:
            raise PreflightError('Opened path is a reparse point or wrong file type.')
        if directory:
            yield None
        else:
            import msvcrt
            fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if create else os.O_RDONLY))
            handle = None
            try:
                yield fd
            finally:
                os.close(fd)
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)


@contextmanager
def _file_handle(path, *, create=False):
    if os.name == 'nt':
        with _windows_handle(path, create=create) as fd:
            yield fd
        return
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY
    fd = os.open(path, flags | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        yield fd
    finally:
        os.close(fd)


def _hold_directories(stack, directories):
    seen = set()
    held = []
    for directory in directories:
        for path in (*reversed(directory.parents), directory):
            if path in seen:
                continue
            before = _check_node(path, directory=True)
            if os.name == 'nt':
                stack.enter_context(_windows_handle(path, directory=True))
            if _identity(_check_node(path, directory=True)) != _identity(before):
                raise PreflightError('Directory changed during validation.')
            held.append((path, _identity(before)))
            seen.add(path)
    return held


def _check_directories(held):
    for path, identity in held:
        if _identity(_check_node(path, directory=True)) != identity:
            raise PreflightError('Directory changed during preflight.')


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PreflightError('Duplicate JSON key.')
            result[key] = value
        return result

    def constant(_):
        raise PreflightError('Non-finite JSON number.')

    if not isinstance(raw, bytes) or len(raw) > MAX_JSON_BYTES:
        raise PreflightError('Preflight JSON exceeds the adapter limit.')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PreflightError('Invalid preflight JSON.') from exc


def _validate_result(raw, pdf, digest, classify_content):
    result = _strict_json(raw)
    expected = BASE_FIELDS | (CONTENT_FIELDS if classify_content else set())
    if not isinstance(result, dict) or set(result) != expected:
        raise PreflightError('Unknown/missing preflight fields.')
    if (result['schema'] != 'pdf_read_preflight/1' or result['file'] != str(pdf)
            or result['sha256'] != digest):
        raise PreflightError('Preflight schema or input fingerprint mismatch.')
    version = '1.1.0' if classify_content else '1.0.0'
    if result['tool'] != 'pdf_read_preflight/' + version:
        raise PreflightError('Unsupported upstream tool version.')
    if result['verdict'] not in ('PASS', 'FAIL', 'UNAVAILABLE'):
        raise PreflightError('Unknown structural verdict.')
    counts = [result[k] for k in COUNTS]
    if any(v is not None and type(v) is not int for v in counts):
        raise PreflightError('Invalid page counts.')
    warnings = result['warnings']
    if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
        raise PreflightError('Invalid warnings.')
    try:
        when = datetime.fromisoformat(result['generated_at'])
        if when.utcoffset() is None:
            raise ValueError('Missing timezone')
    except (TypeError, ValueError) as exc:
        raise PreflightError('Invalid generation timestamp.') from exc
    if result['verdict'] == 'PASS' and (
            any(v is None or v <= 0 for v in counts) or len(set(counts)) != 1 or warnings):
        raise PreflightError('PASS lacks agreeing positive counts or has warnings.')
    if result['verdict'] == 'FAIL' and (None in counts or len(set(counts)) == 1):
        raise PreflightError('FAIL lacks the upstream page-count disagreement.')
    if classify_content:
        _validate_content(result)
    return result


def _validate_content(result):
    content = result['content_classification']
    fields = {'schema', 'requested', 'status', 'reason', 'classification',
              'confidence', 'pages_needing_ocr'}
    if (result['verdict_scope'] != 'STRUCTURE_ONLY' or not isinstance(content, dict)
            or set(content) != fields or content['schema'] != 'pdf_content_classification/1'
            or content['requested'] is not True or not isinstance(content['reason'], str)
            or not content['reason']):
        raise PreflightError('Invalid structural-only classifier contract.')
    if content['status'] == 'UNAVAILABLE':
        advisory = 'CONTENT_UNAVAILABLE' if result['verdict'] == 'PASS' else 'STRUCTURAL_UNAVAILABLE'
        if (result['content_advisory'] != advisory or
                any(content[k] is not None for k in ('classification', 'confidence', 'pages_needing_ocr'))
                or (result['verdict'] == 'PASS' and content['reason'] not in CONTENT_UNAVAILABLE_REASONS)
                or (result['verdict'] != 'PASS' and content['reason'] != 'STRUCTURAL_NOT_PASS')):
            raise PreflightError('Unavailable classifier carries an invalid advisory.')
        return
    confidence, pages = content['confidence'], content['pages_needing_ocr']
    if (content['status'] != 'CLASSIFIED' or content['reason'] != 'CLASSIFIED'
            or result['verdict'] != 'PASS'
            or content['classification'] not in ('TEXT_AVAILABLE', 'OCR_RECOMMENDED')
            or result['content_advisory'] != content['classification']
            or type(confidence) not in (int, float) or not 0 <= confidence <= 1
            or not math.isfinite(confidence) or not isinstance(pages, list) or len(pages) > 50000
            or any(type(p) is not int or p < 0 or p >= result['reader_page_count'] for p in pages)
            or pages != sorted(set(pages))
            or (content['classification'] == 'TEXT_AVAILABLE' and pages)):
        raise PreflightError('Invalid classifier advisory; structural verdict cannot be upgraded.')


def publish_preflight(pdf, *, task_dir, output, classify_content=False, timeout=60):
    """Return unchanged validated upstream JSON after exclusive publication."""
    if os.fspath(output).endswith(('/', '\\')):
        raise PreflightError('Output must name a file, not a directory spelling.')
    pdf, task, output = map(_absolute_path, (pdf, task_dir, output))
    if (os.name == 'nt' and task.drive.upper() not in ('D:', 'E:')) or task.parent == task:
        raise PreflightError('Task directory must be explicit and non-root (D/E on Windows).')
    if output.parent != task or output.suffix.lower() != '.json' or output == pdf:
        raise PreflightError('Output must be a new .json directly inside task_dir, distinct from input.')
    if type(classify_content) is not bool or type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise PreflightError('Invalid classifier option or timeout (maximum 300 seconds).')
    upstream = _absolute_path(UPSTREAM)
    with ExitStack() as stack:
        held = _hold_directories(stack, (task, pdf.parent, upstream.parent))
        _check_node(upstream)
        _check_node(pdf)
        if os.path.lexists(output):
            raise PreflightError('Output already exists; no clobber is permitted.')
        fd = stack.enter_context(_file_handle(pdf))
        if _identity(os.fstat(fd)) != _identity(_check_node(pdf)):
            raise PreflightError('Input identity changed.')
        before, digest = _fingerprint(fd)
        env = dict(os.environ)
        env.update(TEMP=str(task), TMP=str(task), TMPDIR=str(task),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONNOUSERSITE='1')
        command = [sys.executable, '-B', '-s', str(upstream), str(pdf)]
        if classify_content:
            command.append('--classify-content')
        completed = subprocess.run(command, cwd=task, env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=timeout, check=False, shell=False)
        if completed.returncode != 0:
            raise PreflightError(f'Upstream preflight exited {completed.returncode}; no sidecar published.')
        result = _validate_result(completed.stdout, pdf, digest, classify_content)
        _check_directories(held)
        if (_identity(_check_node(pdf)) != before[0] or _fingerprint(fd) != (before, digest)):
            raise PreflightError('Input changed after preflight; no sidecar published.')
        payload = (json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2) + '\n').encode('utf-8')
        with _file_handle(output, create=True) as out:
            info = os.fstat(out)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PreflightError('Output is not a single-linked regular file; retained.')
            view = memoryview(payload)
            while view:
                written = os.write(out, view)
                if written <= 0:
                    raise PreflightError('Sidecar write stalled; partial output retained.')
                view = view[written:]
            os.fsync(out)
            if _fingerprint(out)[1] != hashlib.sha256(payload).hexdigest():
                raise PreflightError('Output bytes changed; retained.')
        _check_directories(held)
        if _identity(_check_node(output)) != _identity(info):
            raise PreflightError('Output identity changed; retained.')
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf')
    parser.add_argument('--task-dir', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--classify-content', action='store_true')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args(argv)
    try:
        result = publish_preflight(args.pdf, task_dir=args.task_dir, output=args.output,
                                   classify_content=args.classify_content, timeout=args.timeout)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'PDF preflight adapter refused: {exc}\nAny created output is retained; no cleanup ran.\n')
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
