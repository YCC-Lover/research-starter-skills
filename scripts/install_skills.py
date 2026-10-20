"""Install the complete bundle without deleting existing files."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = '.research-starter-skills-install.json'


def unlinked_path(value):
    path = Path(value).expanduser().absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('Linked paths are not supported: ' + str(part))
        if part.exists():
            attributes = getattr(part.lstat(), 'st_file_attributes', 0)
            if attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                raise ValueError('Reparse-point paths are not supported: ' + str(part))
    return path.resolve()


def bundle():
    catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    sources = []
    names = set()
    for item in catalog['skills']:
        name = item['name']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64 or name in names:
            raise ValueError('Invalid or duplicate skill name in catalog.')
        names.add(name)
        if item['path'] != 'skills/' + name:
            raise ValueError('Skill paths must match their catalog names.')
        source = unlinked_path(ROOT / item['path'])
        if not source.is_dir() or not (source / 'SKILL.md').is_file():
            raise ValueError('Invalid skill source path: ' + item['path'])
        files = []
        for file in sorted(source.rglob('*')):
            unlinked_path(file)
            if file.is_file():
                files.append(file)
        sources.append((name, source, files))
    if not sources:
        raise ValueError('The catalog contains no skills.')
    return catalog, sources


def target_directory(destination):
    destination = unlinked_path(destination)
    if destination.is_relative_to(ROOT) or ROOT.is_relative_to(destination):
        raise ValueError('The destination must not overlap the source repository.')
    if destination.exists() and not destination.is_dir():
        raise ValueError('The destination must be a directory.')
    return destination


def check_installation(destination):
    destination = target_directory(destination)
    catalog, sources = bundle()
    receipt_path = unlinked_path(destination / RECEIPT)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else None
    if receipt is not None and (not isinstance(receipt, dict) or receipt.get('schema_version') != 1
                                or not isinstance(receipt.get('files'), dict)
                                or not isinstance(receipt.get('package_version'), str)):
        raise ValueError('Invalid installation receipt; retain it and inspect the installation.')
    statuses = []
    for name, source, files in sources:
        missing, modified, local_changes = [], [], []
        for file in files:
            relative = file.relative_to(source)
            target = destination / name / relative
            unlinked_path(target)
            if not target.is_file():
                missing.append(relative.as_posix())
            elif target.read_bytes() != file.read_bytes():
                modified.append(relative.as_posix())
            key = name + '/' + relative.as_posix()
            if receipt and key in receipt['files'] and target.is_file():
                if hashlib.sha256(target.read_bytes()).hexdigest() != receipt['files'][key]:
                    local_changes.append(relative.as_posix())
        statuses.append({'name': name, 'missing': missing, 'modified': modified,
                         'local_changes_since_install': local_changes,
                         'current': not missing and not modified})
    return {'version': catalog['version'], 'destination': str(destination),
            'installed_version': receipt['package_version'] if receipt else None,
            'receipt_status': 'recorded-not-proof-of-discovery' if receipt else 'not-recorded',
            'current': all(skill['current'] for skill in statuses), 'skills': statuses,
            'next_step': 'Open a new Codex chat and confirm the intended skill is discovered.'
            if all(skill['current'] for skill in statuses)
            else 'Inspect differences; update only with an explicit backup and a local-edit decision.'}


def diagnose_environment(destination):
    modules = {}
    for name in ('numpy', 'PIL', 'pymupdf', 'docx'):
        try:
            modules[name] = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            modules[name] = False
    return {'installation': check_installation(destination),
            'commands_found': {name: shutil.which(name) is not None
                               for name in ('codex', 'pdftotext', 'pdftoppm', 'latexmk')},
            'python_modules_found': modules, 'network_checked': False,
            'origin_interface_checked': False, 'files_written': 0,
            'limits': 'Discovery only; no commands, document parsing, model calls or network requests were executed.'}


def install(destination, update=False, backup_dir=None, dry_run=False):
    destination = target_directory(destination)
    catalog, sources = bundle()
    planned = []
    for name, source, files in sources:
        target = destination / name
        if target.exists() and (not update or not target.is_dir()):
            raise ValueError('Destination exists; use --update with --backup-dir: ' + str(target))
        for file in files:
            planned.append((file, target / file.relative_to(source)))

    overwrites = [(source, target) for source, target in planned if target.exists()]
    receipt_path = unlinked_path(destination / RECEIPT)
    if receipt_path.exists() and (not receipt_path.is_file() or receipt_path.stat().st_nlink > 1):
        raise ValueError('Installation receipt is not a regular unlinked file.')
    if receipt_path.exists() and not update:
        raise ValueError('Installation receipt already exists; use --update with --backup-dir.')
    for _, target in planned:
        unlinked_path(target)
        if target.exists() and (not target.is_file() or target.stat().st_nlink > 1):
            raise ValueError('Destination is not a regular file: ' + str(target))
        ancestor = target.parent
        while ancestor != destination.parent:
            if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
                raise ValueError('Unsafe destination directory: ' + str(ancestor))
            ancestor = ancestor.parent

    backup = None
    if update:
        if backup_dir is None:
            raise ValueError('--update requires an explicit --backup-dir.')
        backup_root = unlinked_path(backup_dir)
        if backup_root.is_relative_to(destination) or destination.is_relative_to(backup_root):
            raise ValueError('Backup and installation directories must not overlap.')
        if backup_root.is_relative_to(ROOT) or ROOT.is_relative_to(backup_root):
            raise ValueError('Backup and source repository must not overlap.')
        if backup_root.exists() and not backup_root.is_dir():
            raise ValueError('The backup path must be a directory.')
        if (overwrites or receipt_path.exists()) and not dry_run:
            backup = backup_root / ('snapshot-' + uuid.uuid4().hex)
            backup.mkdir(parents=True, exist_ok=False)
            for _, target in overwrites:
                saved = backup / target.relative_to(destination)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            if receipt_path.exists():
                shutil.copy2(receipt_path, backup / RECEIPT)

    if not dry_run:
        for source, target in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        receipt = {'schema_version': 1, 'package_version': catalog['version'],
                   'files': {target.relative_to(destination).as_posix():
                             hashlib.sha256(source.read_bytes()).hexdigest()
                             for source, target in planned}}
        receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'installed': [name for name, _, _ in sources] if not dry_run else [],
            'version': catalog['version'], 'destination': str(destination),
            'backup': str(backup) if backup else None, 'deleted_files': 0,
            'receipt': str(receipt_path) if not dry_run else None,
            'dry_run': dry_run, 'files_to_copy': len(planned), 'files_to_backup': len(overwrites)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    parser.add_argument('--dest', default=str(home / 'skills'))
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--backup-dir')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='Validate and preview without writing files.')
    modes.add_argument('--check', action='store_true', help='Compare installed files with this package without writing.')
    modes.add_argument('--doctor', action='store_true', help='Read-only installation and optional-tool discovery; no network.')
    args = parser.parse_args()
    try:
        if args.check or args.doctor:
            if args.update or args.backup_dir:
                parser.error('--check/--doctor cannot be combined with update or backup options.')
            result = diagnose_environment(args.dest) if args.doctor else check_installation(args.dest)
        else:
            result = install(args.dest, args.update, args.backup_dir, args.dry_run)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    if args.check and not result['current']:
        parser.exit(1)


if __name__ == '__main__':
    main()
