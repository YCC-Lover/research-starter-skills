"""Identify byte-bound, unchanged mirror modules for inherited geometry findings."""

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET


def unchanged_mirror_groups(checker, root, result):
    """Never exempt changed text, changed context, or unverified prototypes."""
    svg_path = getattr(checker, '_rsk_current_svg_path', None)
    if svg_path is None or Path(svg_path).parent.name != 'svg_output':
        return set()
    project = Path(svg_path).parent.parent.resolve()
    templates = project / 'templates'
    try:
        manifest = json.loads((templates / 'template_execution_manifest.json').read_text(encoding='utf-8'))
        if (manifest.get('schema') != 'ppt-master.template-execution-manifest.v1' or
                manifest.get('replication_mode') != 'mirror' or
                manifest.get('source_geometry_unchanged') is not True or
                not re.fullmatch('[0-9a-f]{64}', str(manifest.get('source_package_sha256', '')))):
            return set()
        entries = [entry for entry in manifest['templates']
                   if entry['prototype'] == Path(svg_path).name]
        if len(entries) != 1:
            return set()
        prototype = templates / entries[0]['prototype']
        if not prototype.resolve().is_relative_to(templates.resolve()) or prototype.is_symlink():
            return set()
        dependencies = manifest['source_files_sha256']
        if not isinstance(dependencies, dict) or not dependencies:
            return set()
        for relative, expected in dependencies.items():
            path = templates / relative
            if (not path.resolve().is_relative_to(project) or path.is_symlink() or
                    hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                return set()
        raw = prototype.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entries[0]['source_svg_sha256']:
            return set()
        original = ET.fromstring(raw)
        if original.tag != root.tag or original.attrib != root.attrib:
            return set()
        if any(node.get('data-pptx-native-ref') for node in original.iter()):
            from native_payloads import hydrate_native_payload_refs
            hydrate_native_payload_refs(original, prototype)
        def context(tree):
            return (tree.text, [ET.tostring(node) for node in tree
                                if node.tag.rsplit('}', 1)[-1] != 'g'])

        if context(original) != context(root):
            return set()
        groups = [node for node in original if node.tag.rsplit('}', 1)[-1] == 'g' and node.get('id')]
        by_id = {node.get('id'): node for node in groups}
        if len(by_id) != len(groups):
            return set()
        unchanged = {id(node) for node in root if node.get('id') in by_id and
                     ET.tostring(node) == ET.tostring(by_id[node.get('id')])}
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, ImportError):
        return set()
    if unchanged:
        result.setdefault('info', {}).setdefault('inherited', []).append({
            'kind': 'unchanged-mirror-module-geometry',
            'message': 'Text geometry remains source-owned in ' + str(len(unchanged)) +
                       ' exact, context-identical modules; edited modules remain checked.',
        })
    return unchanged
