"""Validate format, source mappings, relative links and public-package privacy."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = re.compile(r'[A-Za-z]:[/\\]Users[/\\]', re.I)
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def validate():
    catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
    assert re.fullmatch(r'\d+\.\d+\.\d+', catalog['version'])
    assert catalog['tutorials_covered'] == catalog['tutorials_total'] == 19
    names = [item['name'] for item in catalog['skills']]
    assert len(names) == len(set(names)) == 7
    partition = []
    all_entries = []
    for item in catalog['skills']:
        folder = ROOT / item['path']
        name = item['name']
        assert folder.resolve().is_relative_to(ROOT / 'skills')
        assert folder.name == name
        content = (folder / 'SKILL.md').read_text(encoding='utf-8')
        match = re.match(r'^---\n(.*?)\n---', content, re.S)
        assert match, name
        front = yaml.safe_load(match.group(1))
        assert front['name'] == name
        assert re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) and len(name) <= 64
        assert isinstance(front['description'], str) and 0 < len(front['description']) <= 1024
        assert '[TODO:' not in content
        metadata = yaml.safe_load((folder / 'agents/openai.yaml').read_text(encoding='utf-8'))
        assert 25 <= len(metadata['interface']['short_description']) <= 64
        assert '$' + name in metadata['interface']['default_prompt']
        assert metadata['policy']['allow_implicit_invocation'] is True
        manifest = json.loads((folder / 'references/source-manifest.json').read_text(encoding='utf-8'))
        entries = manifest['handbooks']
        assert manifest['body_read_count'] == manifest['handbook_count'] == len(entries)
        assert manifest['project_body_read_count'] == manifest['project_handbook_count'] == 19
        assert manifest['revision'] == catalog['upstream_revision']
        assert [e['id'] for e in entries] == item['tutorial_ids']
        for entry in entries:
            assert entry['body_read'] is True and entry['status'] == 'read_and_distilled'
            assert 'local_file' not in entry and 'text_file' not in entry
            assert Path(entry['export_file']).name == entry['export_file']
            assert re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])
            assert entry['pages_read'] == list(range(1, len(entry['pages']) + 1))
            assert entry['distilled_files']
            for guide in entry['distilled_files']:
                assert (ROOT / 'skills' / guide).is_file(), guide
        if name == 'research-starter-paper':
            all_entries = entries
            assert all(e['body_read'] is False for e in manifest['background_sources'])
        else:
            partition.extend(e['id'] for e in entries)
            assert all(e['module'] == name for e in entries)
    assert sorted(partition) == sorted(e['id'] for e in all_entries) == list(range(1, 20))
    for path in ROOT.rglob('*'):
        if '.git' in path.parts or '__pycache__' in path.parts or not path.is_file():
            continue
        assert path.suffix.lower() not in {'.pdf', '.opju', '.png', '.exe', '.zip'}, path
        text = path.read_text(encoding='utf-8')
        assert not PRIVATE_PATH.search(text), path
        assert not SECRET.search(text), path
        if path.suffix == '.md':
            assert '18/19' not in text, path
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if urlsplit(target).scheme or target.startswith('#'):
                    continue
                destination = (path.parent / target.split('#', 1)[0]).resolve()
                assert destination.is_relative_to(ROOT) and destination.exists(), (path, target)
    return {'skills': len(names), 'tutorials_covered': 19, 'public_paths_and_links_valid': True}


if __name__ == '__main__':
    print(json.dumps(validate()))
