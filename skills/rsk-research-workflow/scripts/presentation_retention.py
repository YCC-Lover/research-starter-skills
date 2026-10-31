"""Retain presentation transaction files instead of deleting task artifacts."""

import errno
import json
import os
import stat
import tempfile
import uuid
from pathlib import Path


def checked_path(value):
    root_value = os.environ.get('RSK_PRESENTATION_WORK_ROOT')
    if not root_value:
        raise ValueError('Presentation retention requires an explicit work root.')
    raw_root, raw_path = Path(root_value), Path(value)
    if not raw_root.is_absolute() or '..' in raw_root.parts or '..' in raw_path.parts:
        raise ValueError('Use canonical absolute retention paths without parent traversal.')
    root = raw_root.absolute()
    path = raw_path.absolute()
    if not path.is_relative_to(root) or path == root:
        raise ValueError('Refusing retention outside the presentation work root: ' + str(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0)
                                 & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
            raise ValueError('Linked presentation paths are not supported: ' + str(part))
    return root.resolve(), path.resolve()


def retain(value, missing_ok=False, empty_only=False):
    root, path = checked_path(value)
    if not path.exists():
        if missing_ok:
            return
        raise FileNotFoundError(path)
    if empty_only and any(path.iterdir()):
        raise OSError(errno.ENOTEMPTY, 'Directory not empty', str(path))
    archive = root / '.rsk-retained' / uuid.uuid4().hex
    checked_path(archive)
    archive.mkdir(parents=True, exist_ok=False)
    target = archive / path.name
    checked_path(target)
    path.rename(target)
    (archive / 'retention.json').write_text(json.dumps({
        'source': path.relative_to(root).as_posix(), 'retained_name': path.name,
        'action': 'rename-not-delete',
    }, ensure_ascii=True) + '\n', encoding='utf-8')


def unlink(path, missing_ok=False, **kwargs):
    if kwargs:
        raise ValueError('Unsupported unlink arguments; no files were deleted.')
    _, target = checked_path(path)
    if target.is_dir():
        raise IsADirectoryError(target)
    return retain(target, missing_ok=missing_ok)


def rmdir(path, **kwargs):
    if kwargs:
        raise ValueError('Unsupported rmdir arguments; no directories were deleted.')
    return retain(path, empty_only=True)


def rmtree(path, ignore_errors=False, **kwargs):
    if kwargs:
        raise ValueError('Unsupported cleanup arguments; retained outputs require review.')
    try:
        return retain(path)
    except OSError:
        if not ignore_errors:
            raise


class TemporaryDirectory:
    """Compatible scratch-directory lifetime without recursive finalization."""

    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False, **kwargs):
        if kwargs:
            raise ValueError('Unsupported temporary-directory options.')
        base = Path(dir or tempfile.gettempdir())
        checked_path(base / 'temporary-directory-probe')
        self.name = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=base)

    def __class_getitem__(cls, item):
        return cls

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        self.cleanup()

    def cleanup(self):
        # Keep the same name so crash recovery and native export diagnostics work.
        checked_path(self.name)
