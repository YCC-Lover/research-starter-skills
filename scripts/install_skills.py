"""Install the complete bundle without deleting existing files."""

import argparse
import json
import os
import re
import shutil
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def install(destination, update=False, backup_dir=None):
    destination = Path(destination).expanduser().resolve()
    sources = ROOT / 'skills'
    if destination.is_relative_to(sources) or sources.is_relative_to(destination):
        raise ValueError('The destination must not overlap the source skill directory.')
    catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    planned = []
    names = []
    for item in catalog['skills']:
        name = item['name']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64 or name in names:
            raise ValueError('Invalid or duplicate skill name in catalog.')
        names.append(name)
        source = (ROOT / item['path']).resolve()
        if not source.is_relative_to(sources) or not (source / 'SKILL.md').is_file():
            raise ValueError('Invalid skill source path: ' + item['path'])
        target = destination / name
        if target.exists() and (not update or not target.is_dir()):
            raise ValueError('Destination exists; use --update with --backup-dir: ' + str(target))
        for file in source.rglob('*'):
            if file.is_symlink():
                raise ValueError('Symlinked source files are not supported: ' + str(file))
            if file.is_file():
                planned.append((file, target / file.relative_to(source)))

    overwrites = [(source, target) for source, target in planned if target.exists()]
    for _, target in planned:
        if target.is_symlink() or (target.exists() and not target.is_file()):
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
        backup_root = Path(backup_dir).expanduser().resolve()
        if backup_root.is_relative_to(destination) or destination.is_relative_to(backup_root):
            raise ValueError('Backup and installation directories must not overlap.')
        if backup_root.is_relative_to(sources) or sources.is_relative_to(backup_root):
            raise ValueError('Backup and source directories must not overlap.')
        if os.name == 'nt' and backup_root.drive.upper() == 'C:':
            raise ValueError('Use a non-C backup directory on Windows, preferably D or E.')
        if overwrites:
            backup = backup_root / ('snapshot-' + uuid.uuid4().hex)
            for _, target in overwrites:
                saved = backup / target.relative_to(destination)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)

    for source, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return {'installed': names, 'destination': str(destination),
            'backup': str(backup) if backup else None, 'deleted_files': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    parser.add_argument('--dest', default=str(home / 'skills'))
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--backup-dir')
    args = parser.parse_args()
    try:
        result = install(args.dest, args.update, args.backup_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
