"""Reproduce the pinned, on-demand research runtime; never execute source code."""

import argparse
import difflib
import hashlib
import json
import posixpath
import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = Path('skills/research-starter-paper/resources/research-engine')
SOURCE_URL = 'https://github.com/Imbad0202/academic-research-skills'
SOURCE_COMMIT = '3224a27a2571cefef0fddfd437004cb006f2b0cb'
WORKFLOWS = ('deep-research', 'academic-paper', 'academic-paper-reviewer',
             'academic-pipeline', 'sr-screener')
TREE_ROOTS = {*WORKFLOWS, 'shared', 'commands', 'agents', 'scripts', 'evals'}
ROOT_FILES = {'LICENSE', 'NOTICE.md', 'THIRD_PARTY.md', 'MODE_REGISTRY.md',
              'requirements-dev.txt', 'requirements-pdf-content-classifier.txt'}
PATCH_RECORD = ROOT / 'skills/research-starter-paper/references/research-engine-patches.json'
RUNTIME_PATCH = ROOT / 'scripts/research-engine-runtime.patch'
LINK = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def selected(relative):
    parts = PurePosixPath(relative).parts
    if relative in ROOT_FILES:
        return True
    if parts[0] == 'docs':
        return (len(parts) == 2 and relative.endswith('.md')) or (
            len(parts) > 2 and parts[1] == 'design' and
            PurePosixPath(relative).suffix in {'.md', '.yaml'})
    if parts[0] not in TREE_ROOTS:
        return False
    if any(p in {'tests', '__pycache__', 'runs'} for p in parts):
        return False
    if parts[-1].startswith('test_') or parts[-1].endswith('.pyc'):
        return False
    return True


def target_name(relative):
    for workflow in WORKFLOWS:
        if relative == workflow + '/SKILL.md':
            return workflow + '/WORKFLOW.md'
    return relative


def resolve_link(parent, relative):
    parts = []
    for part in (*parent.parts, *PurePosixPath(relative).parts):
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return '/'.join(parts)


def render_markdown(text, relative, included, tracked=None):
    """Keep runtime links local; point historical/development links at the pin."""
    changes = []

    def link(match):
        original = match.group(2)
        target = original.strip('<>')
        if urlsplit(target).scheme or target.startswith('#'):
            return match.group(0)
        path, separator, anchor = target.partition('#')
        parent = PurePosixPath(relative).parent
        resolved = resolve_link(parent, unquote(path))
        known = tracked if tracked is not None else included
        if resolved not in known:
            components = list(PurePosixPath(unquote(path)).parts)
            while components and components[0] == '..':
                components.pop(0)
            candidate = resolve_link(PurePosixPath('.'), '/'.join(components))
            if candidate in known or (candidate and any(
                    name.startswith(candidate.rstrip('/') + '/') for name in known)):
                resolved = candidate
                path = posixpath.relpath(resolved, parent.as_posix())
        if resolved is None:
            raise ValueError('Escaping source link cannot be resolved: ' + relative + ' -> ' + target)
        fragment = separator + anchor
        if resolved in included:
            replacement = path
            if resolved.endswith('/SKILL.md') and resolved.split('/')[0] in WORKFLOWS:
                replacement = path.removesuffix('SKILL.md') + 'WORKFLOW.md'
        elif any(item.startswith(resolved.rstrip('/') + '/') for item in included):
            replacement = path
        else:
            replacement = SOURCE_URL + '/blob/' + SOURCE_COMMIT + '/' + quote(resolved, safe='/')
        replacement += fragment
        if replacement != target:
            changes.append({'from': original, 'to': replacement})
        return '[' + match.group(1) + '](' + replacement + ')'

    rendered = LINK.sub(link, text)
    for workflow in WORKFLOWS:
        rendered = rendered.replace(workflow + '/SKILL.md', workflow + '/WORKFLOW.md')
    return rendered, changes


def read_git_blobs(source, relatives, git):
    requests = ''.join(SOURCE_COMMIT + ':' + name + '\n' for name in relatives).encode('utf-8')
    stream = subprocess.run([git, '-C', str(source), 'cat-file', '--batch'],
                            input=requests, capture_output=True, check=True).stdout
    offset = 0
    result = {}
    for relative in relatives:
        end = stream.index(b'\n', offset)
        fields = stream[offset:end].split()
        if len(fields) != 3 or fields[1] != b'blob':
            raise ValueError('Source is not a Git blob: ' + relative)
        size = int(fields[2])
        offset = end + 1
        data = stream[offset:offset + size]
        if len(data) != size or stream[offset + size:offset + size + 1] != b'\n':
            raise ValueError('Incomplete Git blob: ' + relative)
        result[relative] = (fields[0].decode('ascii'), data)
        offset += size + 1
    if offset != len(stream):
        raise ValueError('Unexpected trailing Git object data.')
    return result


def build(source, destination, git='git', write=False, update_source_hashes=False,
          sync_resources=False, export_patch=False, adapted=False):
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Source and output must not overlap.')
    commit = subprocess.check_output([git, '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError('Source revision differs from the audited pin: ' + commit)
    status = subprocess.check_output([git, '-C', str(source), 'status', '--porcelain'], text=True)
    if status.strip():
        raise ValueError('Source checkout must be clean.')
    tracked = subprocess.check_output([git, '-C', str(source), 'ls-files', '-z']).decode().split('\0')
    included = {p for p in tracked if p and selected(p)}
    blobs = read_git_blobs(source, sorted(included), git)
    files, pending = [], []
    for relative in sorted(included):
        path = source / relative
        if path.is_symlink() or not path.resolve().is_relative_to(source):
            raise ValueError('Unsupported linked source: ' + relative)
        blob_oid, raw = blobs[relative]
        text = raw.decode('utf-8')
        if '\0' in text:
            raise ValueError('Unexpected binary source: ' + relative)
        transformations = []
        if path.suffix == '.md':
            text, transformations = render_markdown(text, relative, included, set(tracked))
        # Git's checkout may be CRLF; keep distributed text platform-independent.
        data = text.replace('\r\n', '\n').encode('utf-8')
        target = target_name(relative)
        files.append({'source': relative, 'path': target,
                      'source_blob_oid': blob_oid,
                      'source_sha256': hashlib.sha256(raw).hexdigest(),
                      'sha256': hashlib.sha256(data).hexdigest(),
                      'link_adaptations': transformations})
        pending.append((target, data))
    manifest = {'schema_version': 1, 'source_repository': SOURCE_URL,
                'source_commit': SOURCE_COMMIT, 'license': 'CC-BY-NC-4.0',
                'copyright': 'Copyright (c) 2026 Cheng-I Wu',
                'scope': 'Runtime instructions, contracts, helpers and optional evaluation assets; '
                         'not upstream development CI, historical result runs or test suites.',
                'adaptations': ['Internal workflow entries renamed to WORKFLOW.md.',
                                'Development/history links point to pinned source.',
                                'Distributed line endings normalized to LF.'],
                'files': files}
    if sum(map(bool, (write, update_source_hashes, sync_resources, export_patch))) > 1:
        raise ValueError('Choose one output operation.')
    if adapted and not write:
        raise ValueError('--adapted requires a fresh --write output.')
    patch_records = json.loads(PATCH_RECORD.read_text(encoding='utf-8'))['files']
    patches = {row['path']: row for row in patch_records}
    if len(patches) != len(patch_records):
        raise ValueError('Duplicate runtime patch record.')
    if sync_resources:
        previous = json.loads((destination / 'source-manifest.json').read_text(encoding='utf-8'))
        old = {row['path']: row for row in previous['files']}
        new = {row['path']: row for row in files}
        if previous['source_commit'] != commit or set(old) - set(new):
            raise ValueError('Resource expansion cannot remove files or change the source pin.')
        observed = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        if observed != set(old) | {'source-manifest.json'}:
            raise ValueError('Unregistered or missing existing runtime resources.')
        for name, row in old.items():
            expected = patches.get(name, row)['sha256']
            if hashlib.sha256((destination / name).read_bytes()).hexdigest() != expected:
                raise ValueError('Existing resource changed before expansion: ' + name)
        for name, patch in patches.items():
            if name not in new or patch['base_sha256'] != new[name]['sha256']:
                raise ValueError('Expansion would require a runtime patch rebase: ' + name)
        for name, data in pending:
            if name in patches:
                continue
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            if not output.exists() or output.read_bytes() != data:
                output.write_bytes(data)
        (destination / 'source-manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    if export_patch:
        sections = []
        bases = dict(pending)
        for name in sorted(patches):
            row = patches[name]
            base = bases[name]
            current = (destination / name).read_bytes()
            if (hashlib.sha256(base).hexdigest() != row['base_sha256'] or
                    hashlib.sha256(current).hexdigest() != row['sha256']):
                raise ValueError('Patch content differs from reviewed hashes: ' + name)
            sections.extend(difflib.unified_diff(
                base.decode('utf-8').splitlines(keepends=True),
                current.decode('utf-8').splitlines(keepends=True),
                fromfile='a/' + name, tofile='b/' + name))
        RUNTIME_PATCH.write_bytes(''.join(sections).encode('utf-8'))
    if update_source_hashes:
        manifest_path = destination / 'source-manifest.json'
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        old = {row['path']: row['sha256'] for row in previous['files']}
        new = {row['path']: row['sha256'] for row in files}
        if old != new or previous['source_commit'] != commit:
            raise ValueError('Source hash migration must not change runtime bytes, inventory or source pin.')
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    if write:
        if destination.exists():
            raise ValueError('Refusing an existing output. Generate into a new directory and inspect differences.')
        destination.mkdir(parents=True)
        for target, data in pending:
            output = destination / target
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        (destination / 'source-manifest.json').write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
        if adapted:
            for row in patch_records:
                if row['base_sha256'] != next(f['sha256'] for f in files if f['path'] == row['path']):
                    raise ValueError('Runtime patch source binding changed: ' + row['path'])
            subprocess.run([git, '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                            'apply', '--no-index', '--check', str(RUNTIME_PATCH)],
                           cwd=destination, check=True)
            subprocess.run([git, '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
                            'apply', '--no-index', str(RUNTIME_PATCH)],
                           cwd=destination, check=True)
            for row in patch_records:
                if hashlib.sha256((destination / row['path']).read_bytes()).hexdigest() != row['sha256']:
                    raise ValueError('Replayed runtime patch checksum mismatch: ' + row['path'])
    return {'files': len(files), 'bytes': sum(len(data) for _, data in pending),
            'source_commit': commit, 'written': bool(write or sync_resources or update_source_hashes or export_patch),
            'runtime_patch_replayed': bool(adapted), 'destination': str(destination),
            'counts': {name: sum(f['source'].startswith(name + '/') for f in files)
                       for name in sorted(TREE_ROOTS | {'docs'})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / DESTINATION)
    parser.add_argument('--git', default='git')
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--update-source-hashes', action='store_true',
                        help='Bind checkout-era provenance to canonical Git blobs without changing runtime bytes.')
    parser.add_argument('--sync-resources', action='store_true',
                        help='Expand the resource closure after verifying existing bytes; never removes files.')
    parser.add_argument('--export-runtime-patch', action='store_true',
                        help='Export only reviewed, hash-bound runtime adaptations for reproducible builds.')
    parser.add_argument('--adapted', action='store_true',
                        help='Replay reviewed runtime adaptations into a fresh output.')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.git, args.write, args.update_source_hashes,
                           args.sync_resources, args.export_runtime_patch, args.adapted), indent=2))


if __name__ == '__main__':
    main()
