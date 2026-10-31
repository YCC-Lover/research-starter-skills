"""Reproduce the PPT Master resource stream from canonical, pinned Git blobs."""

import argparse
import base64
import hashlib
import json
import subprocess
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN = '5e8856be0da8e6bc85c4aa28acc614478f7b7137'
PREFIX = 'skills/ppt-master/'
OUTPUT = ROOT / 'skills/rsk-research-workflow/resources/presentation-engine'


def build(source, git, refresh=False):
    def command(*args):
        return subprocess.check_output([git, *args], cwd=source)
    if command('rev-parse', 'HEAD').decode().strip() != PIN:
        raise ValueError('Use the recorded upstream commit, not a moving branch.')
    if command('status', '--porcelain').strip():
        raise ValueError('The upstream checkout has local changes.')
    if OUTPUT.exists() and not refresh:
        raise ValueError('Resource destination exists; review an update explicitly.')
    files = command('ls-tree', '-rz', '--full-tree', PIN, PREFIX).split(b'\0')
    rows = []
    process = subprocess.Popen([git, 'cat-file', '--batch'], cwd=source,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for entry in files:
            if not entry:
                continue
            metadata, raw_path = entry.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            name = raw_path.decode('utf-8')[len(PREFIX):]
            if mode != '100644' and mode != '100755' or kind != 'blob':
                raise ValueError('Linked or non-blob resource: ' + name)
            process.stdin.write((oid + '\n').encode())
            process.stdin.flush()
            header = process.stdout.readline().decode().split()
            if len(header) != 3 or header[0] != oid or header[1] != 'blob':
                raise ValueError('Unexpected Git object response.')
            size = int(header[2])
            data = process.stdout.read(size)
            if len(data) != size or process.stdout.read(1) != b'\n':
                raise ValueError('Incomplete Git blob.')
            row = {'path': name, 'git_blob': oid, 'bytes': size,
                   'sha256': hashlib.sha256(data).hexdigest()}
            try:
                row['text'] = data.decode('utf-8')
            except UnicodeDecodeError:
                row['base64'] = base64.b64encode(data).decode('ascii')
            rows.append(row)
    finally:
        process.stdin.close()
        process.stdout.close()
        process.wait(timeout=30)
    OUTPUT.mkdir(parents=True, exist_ok=refresh)
    payload = b''.join((json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
                       for row in rows)
    packed = (json.dumps({'encoding': 'zlib+base64-jsonl', 'decoded_bytes': len(payload),
                          'jsonl_sha256': hashlib.sha256(payload).hexdigest(),
                          'data': base64.b64encode(zlib.compress(payload, level=9)).decode('ascii')},
                         separators=(',', ':')) + '\n').encode('utf-8')
    (OUTPUT / 'resources.json').write_bytes(packed)
    manifest = {'schema_version': 1, 'source_repository': 'https://github.com/hugohe3/ppt-master',
                'source_commit': PIN, 'source_version': '6.8.0', 'license': 'MIT',
                'resource_count': len(rows), 'source_bytes': sum(row['bytes'] for row in rows),
                'pack_sha256': hashlib.sha256(packed).hexdigest(),
                'pack_bytes': len(packed), 'pack': 'resources.json',
                'scope': 'Complete upstream skill package; no repository example projects.',
                'adaptation': 'Runtime-only recorded cleanup retention and hash-bound unchanged-mirror geometry context patch; upstream attribution gates unchanged.'}
    (OUTPUT / 'manifest.json').write_bytes((json.dumps(manifest, indent=2) + '\n').encode('utf-8'))
    for name in ('LICENSE', 'templates/icons/THIRD_PARTY_NOTICES.md',
                 'templates/sounds/THIRD_PARTY_NOTICES.md'):
        row = next(row for row in rows if row['path'] == name)
        target = OUTPUT / ('LICENSE' if name == 'LICENSE' else name.split('/')[1] + '-NOTICES.txt')
        target.write_bytes(row['text'].encode('utf-8'))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--git', default='git')
    parser.add_argument('--refresh', action='store_true', help='Explicitly regenerate the recorded source artifact.')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.git, args.refresh)))
