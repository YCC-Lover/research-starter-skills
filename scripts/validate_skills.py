"""Validate format, source mappings, relative links and public-package privacy."""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = re.compile(r'[A-Za-z]:[/\\]Users[/\\]', re.I)
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def require(condition, message):
    if not condition:
        raise ValueError(str(message))


def local_file(root, relative):
    require(isinstance(relative, str) and not urlsplit(relative).scheme,
            'Expected a repository-relative path: ' + str(relative))
    path = root / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(root),
            'Unsafe repository path: ' + relative)
    require(path.is_file(), 'Missing file: ' + relative)
    return path


def validate(root=ROOT):
    root = Path(root).resolve()
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8'))
    require(re.fullmatch(r'\d+\.\d+\.\d+', catalog['version']), 'Invalid package version.')
    require(catalog['tutorials_covered'] == catalog['tutorials_total'] == 19, 'Tutorial coverage mismatch.')
    names = [item['name'] for item in catalog['skills']]
    require(len(names) == len(set(names)) == 7, 'Expected seven distinct skills.')
    partition = []
    all_entries = []
    for item in catalog['skills']:
        folder = root / item['path']
        name = item['name']
        require(item['path'] == 'skills/' + name and folder.resolve().is_relative_to(root / 'skills'),
                'Invalid skill path: ' + name)
        content = (folder / 'SKILL.md').read_text(encoding='utf-8')
        match = re.match(r'^---\n(.*?)\n---', content, re.S)
        require(match, 'Missing YAML frontmatter: ' + name)
        front = yaml.safe_load(match.group(1))
        require(front['name'] == name, 'Skill name mismatch: ' + name)
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and len(name) <= 64, 'Invalid name: ' + name)
        require(isinstance(front['description'], str) and 0 < len(front['description']) <= 1024,
                'Invalid description: ' + name)
        require('[TODO:' not in content, 'Unfinished placeholder: ' + name)
        metadata = yaml.safe_load((folder / 'agents/openai.yaml').read_text(encoding='utf-8'))
        require(25 <= len(metadata['interface']['short_description']) <= 64, 'Invalid UI description: ' + name)
        require('$' + name in metadata['interface']['default_prompt'], 'Missing invocation prompt: ' + name)
        require(metadata['policy']['allow_implicit_invocation'] is True, 'Unexpected invocation policy: ' + name)
        manifest = json.loads((folder / 'references/source-manifest.json').read_text(encoding='utf-8'))
        entries = manifest['handbooks']
        require(manifest['body_read_count'] == manifest['handbook_count'] == len(entries), 'Module coverage: ' + name)
        require(manifest['project_body_read_count'] == manifest['project_handbook_count'] == 19, 'Project coverage: ' + name)
        require(manifest['revision'] == catalog['upstream_revision'], 'Source revision mismatch: ' + name)
        require([e['id'] for e in entries] == item['tutorial_ids'], 'Tutorial mapping mismatch: ' + name)
        for entry in entries:
            require(entry['body_read'] is True and entry['status'] == 'read_and_distilled', 'Unread tutorial: ' + name)
            require('local_file' not in entry and 'text_file' not in entry, 'Private provenance path: ' + name)
            require(Path(entry['export_file']).name == entry['export_file'], 'Export path must be a filename: ' + name)
            require(re.fullmatch(r'[0-9a-f]{64}', entry['sha256']), 'Invalid source checksum: ' + name)
            require(entry['pages_read'] == list(range(1, len(entry['pages']) + 1)), 'Incomplete page mapping: ' + name)
            require(entry['distilled_files'], 'Missing distilled references: ' + name)
            for guide in entry['distilled_files']:
                local_file(root, 'skills/' + guide)
        if name == 'research-starter-paper':
            all_entries = entries
            require(all(e['body_read'] is False for e in manifest['background_sources']), 'Unsupported background-read claim.')
        else:
            partition.extend(e['id'] for e in entries)
            require(all(e['module'] == name for e in entries), 'Wrong module mapping: ' + name)
    require(sorted(partition) == sorted(e['id'] for e in all_entries) == list(range(1, 20)), 'Tutorial partition mismatch.')

    citation = root / 'CITATION.cff'
    if citation.is_file():
        metadata = yaml.safe_load(citation.read_text(encoding='utf-8'))
        require(str(metadata['version']) == catalog['version'], 'Citation version mismatch.')
        require(metadata['repository-code'] == catalog['repository'], 'Citation repository mismatch.')
        require(any(reference.get('url') == catalog['upstream_repository']
                    for reference in metadata.get('references', [])), 'Missing upstream citation.')

    approved_images = set()
    asset_manifest = root / 'docs/images/manifest.json'
    if asset_manifest.is_file():
        for asset in json.loads(asset_manifest.read_text(encoding='utf-8'))['images']:
            path = local_file(root, asset['path'])
            require(path.suffix.lower() == '.png' and path.parent == root / 'docs/images', 'Unexpected asset location.')
            require(path not in approved_images, 'Duplicate image manifest entry.')
            data = path.read_bytes()
            require(len(data) <= 3_000_000 and data[:8] == b'\x89PNG\r\n\x1a\n', 'Invalid or oversized PNG.')
            require(data[12:16] == b'IHDR', 'Missing PNG header.')
            dimensions = struct.unpack('>II', data[16:24])
            require(list(dimensions) == [asset['width'], asset['height']], 'Image dimensions mismatch.')
            require(hashlib.sha256(data).hexdigest() == asset['sha256'], 'Image checksum mismatch.')
            require(asset['kind'] in {'original-diagram', 'synthetic-data-plot', 'illustrative-output'}, 'Unknown image origin.')
            require(asset['creator'] and asset['description'], 'Missing asset attribution.')
            local_file(root, asset['source'])
            if asset['kind'] == 'synthetic-data-plot':
                local_file(root, asset['data_source'])
            approved_images.add(path)

    for path in root.rglob('*'):
        if '.git' in path.parts or '__pycache__' in path.parts:
            continue
        require(not path.is_symlink() and path.resolve().is_relative_to(root), 'Linked package file: ' + str(path))
        if not path.is_file():
            continue
        if path in approved_images:
            continue
        require(path.suffix.lower() not in {'.pdf', '.opju', '.png', '.jpg', '.jpeg', '.exe', '.zip'},
                'Unapproved binary or raw source file: ' + str(path.relative_to(root)))
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as error:
            raise ValueError('Unapproved binary file: ' + str(path.relative_to(root))) from error
        require(not PRIVATE_PATH.search(text), 'Private user path: ' + str(path.relative_to(root)))
        require(not SECRET.search(text), 'Possible secret: ' + str(path.relative_to(root)))
        if path.suffix == '.md':
            require('18/19' not in text, 'Stale coverage statement: ' + str(path.relative_to(root)))
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if urlsplit(target).scheme or target.startswith('#'):
                    continue
                relative = unquote(target.split('#', 1)[0].strip('<>'))
                destination = (root / relative.lstrip('/') if relative.startswith('/') else path.parent / relative).resolve()
                require(destination.is_relative_to(root) and destination.exists(),
                        'Broken or escaping link: ' + str(path.relative_to(root)) + ' -> ' + target)
    return {'skills': len(names), 'tutorials_covered': 19, 'public_paths_and_links_valid': True,
            'approved_images': len(approved_images)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Package root to validate.')
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except (ValueError, OSError, KeyError, TypeError, struct.error, yaml.YAMLError) as error:
        parser.exit(1, 'Validation failed: ' + str(error) + '\n')
    print(json.dumps(result))
