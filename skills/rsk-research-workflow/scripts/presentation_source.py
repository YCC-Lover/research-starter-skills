"""Read the pinned resource stream and apply the recorded retention adaptation."""

import ast
import base64
import hashlib
import json
import io
import zlib
from pathlib import PurePosixPath


def resource_path(name):
    if not isinstance(name, str) or not name:
        raise ValueError('Empty presentation resource path.')
    relative = PurePosixPath(name)
    if (not relative.parts or relative.is_absolute() or '..' in relative.parts or
            '\\' in name or ':' in name or relative.as_posix() != name):
        raise ValueError('Unsafe presentation resource path: ' + name)
    return relative


def source_rows(pack, expected_hash):
    digest = hashlib.sha256()
    with pack.open('rb') as stream:
        for line in stream:
            digest.update(line)
    if digest.hexdigest() != expected_hash:
        raise ValueError('Presentation resource stream hash differs from its manifest.')
    envelope = json.loads(pack.read_text(encoding='utf-8'))
    if envelope['encoding'] != 'zlib+base64-jsonl' or not 0 < envelope['decoded_bytes'] <= 80_000_000:
        raise ValueError('Unsupported or oversized presentation resource stream.')
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(base64.b64decode(envelope['data'], validate=True),
                                 envelope['decoded_bytes'] + 1)
    if (len(decoded) != envelope['decoded_bytes'] or not decoder.eof or decoder.unused_data or
            hashlib.sha256(decoded).hexdigest() != envelope['jsonl_sha256']):
        raise ValueError('Invalid compressed presentation resource stream.')
    names = set()
    with io.TextIOWrapper(io.BytesIO(decoded), encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            name = row['path']
            resource_path(name)
            if name in names:
                raise ValueError('Unsafe or duplicate presentation resource path: ' + name)
            names.add(name)
            data = (row['text'].encode('utf-8') if 'text' in row else
                    base64.b64decode(row['base64'], validate=True))
            if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Invalid presentation resource bytes: ' + name)
            yield row, data


def adapt_python(data):
    """Replace concrete cleanup calls, leaving attribution gates and all other text intact."""
    text = data.decode('utf-8')
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    offsets, total = [], 0
    for line in lines:
        offsets.append(total)
        total += len(line)

    def position(line, column):
        return offsets[line - 1] + len(lines[line - 1].encode('utf-8')[:column].decode('utf-8'))

    changes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        function = node.func
        owner = function.value.id if isinstance(function.value, ast.Name) else None
        target, argument = None, None
        if function.attr == 'TemporaryDirectory' and owner == 'tempfile':
            target = 'TemporaryDirectory'
        elif function.attr == 'rmtree' and owner == 'shutil':
            target = 'rmtree'
        elif function.attr in ('unlink', 'rmdir'):
            target = function.attr
            if owner != 'os':
                argument = ast.get_source_segment(text, function.value)
        elif function.attr == 'remove' and owner == 'os':
            target = 'unlink'
        if target:
            start = position(function.lineno, function.col_offset)
            end = position(function.end_lineno, function.end_col_offset)
            changes.append((start, end, '_rsk_retention.' + target))
            if argument is not None:
                opening = text.index('(', end, position(node.end_lineno, node.end_col_offset)) + 1
                changes.append((opening, opening, argument + (', ' if node.args or node.keywords else '')))
    if not changes:
        return data, 0
    insertion = 0
    for index, node in enumerate(tree.body):
        if ((index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
             and isinstance(node.value.value, str)) or
                isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            insertion = offsets[node.end_lineno - 1] + len(lines[node.end_lineno - 1])
        else:
            if not insertion:
                insertion = offsets[node.lineno - 1]
            break
    changes.append((insertion, insertion, '\nimport _rsk_retention\n'))
    for start, end, replacement in sorted(changes, reverse=True):
        text = text[:start] + replacement + text[end:]
    ast.parse(text)
    return text.encode('utf-8'), sum(' _rsk_retention.' in item[2] or
                                    item[2].startswith('_rsk_retention.') for item in changes)


def adapt_mirror_checker(data):
    """Preserve unchanged source-module geometry without exempting authored changes."""
    if hashlib.sha256(data).hexdigest() != '58d7f5ba4d738ffd25e796fbdd74626a1f05fe93a6233090c3da1702a7a650f4':
        raise ValueError('The reviewed mirror checker patch requires its exact source bytes.')
    text = data.decode('utf-8')
    replacements = [
        ('from native_payloads import NativePayloadError, hydrate_native_payload_refs\n',
         'from native_payloads import NativePayloadError, hydrate_native_payload_refs\n'
         'from _rsk_mirror import unchanged_mirror_groups\n'),
        ('        svg_path = Path(svg_file)\n',
         '        svg_path = Path(svg_file)\n        self._rsk_current_svg_path = svg_path\n'),
        ('        unchanged_groups = self._unchanged_txbody_group_ids(root)\n'
         "        viewbox = _parse_viewbox_values(root.get('viewBox') or '')\n",
         '        unchanged_groups = self._unchanged_txbody_group_ids(root)\n'
         '        unchanged_groups.update(unchanged_mirror_groups(self, root, result))\n'
         "        viewbox = _parse_viewbox_values(root.get('viewBox') or '')\n"),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('Mirror checker patch target changed or is ambiguous.')
        text = text.replace(old, new, 1)
    ast.parse(text)
    return text.encode('utf-8')
