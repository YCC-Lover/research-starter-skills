"""Deterministic presentation-adapter tests; all scratch artifacts are retained.

Minimal resource packs, synthetic XML and mocked launches below are unit fixtures,
not evidence that the real upstream tools, attribution guard, or PPTX export ran.
Set RSK_PRESENTATION_TEST_ROOT to retain fixtures in a chosen task directory.
"""

import ast
import base64
import copy
import errno
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/rsk-research-workflow/scripts'
TEST_ROOT = Path(os.environ.get('RSK_PRESENTATION_TEST_ROOT', tempfile.gettempdir())).resolve()
PINNED_COMMIT = '5e8856be0da8e6bc85c4aa28acc614478f7b7137'
HOST_RUN = subprocess.run


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = load_module('rsk_test_presentation_source', SCRIPTS / 'presentation_source.py')
RETENTION = load_module('rsk_test_presentation_retention', SCRIPTS / 'presentation_retention.py')
LAUNCH = load_module('rsk_test_presentation_launch', SCRIPTS / 'presentation_launch.py')
MIRROR = load_module('rsk_test_presentation_mirror', SCRIPTS / 'presentation_mirror.py')
with patch.dict(sys.modules, {'presentation_source': SOURCE}):
    PRESENTATIONS = load_module('rsk_test_research_presentations', SCRIPTS / 'research_presentations.py')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_row(name, data, binary=False):
    row = {'path': name, 'bytes': len(data), 'sha256': sha256(data)}
    row.update({'base64': base64.b64encode(data).decode('ascii')} if binary else
               {'text': data.decode('utf-8')})
    return row


def source_envelope(rows):
    raw = ''.join(json.dumps(row, ensure_ascii=True) + '\n' for row in rows).encode('utf-8')
    return {'encoding': 'zlib+base64-jsonl', 'decoded_bytes': len(raw),
            'jsonl_sha256': sha256(raw),
            'data': base64.b64encode(zlib.compress(raw)).decode('ascii')}


class RetainedFixtures(unittest.TestCase):
    def setUp(self):
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=str(TEST_ROOT)))
        self.counter = 0

    def write_envelope(self, envelope):
        self.counter += 1
        path = self.work / ('synthetic-pack-' + str(self.counter) + '.json')
        raw = json.dumps(envelope, ensure_ascii=True).encode('utf-8')
        path.write_bytes(raw)
        return path, sha256(raw)

    def write_pack(self, rows):
        return self.write_envelope(source_envelope(rows))

    def symlink(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            if os.name == 'nt' and error.winerror in (1, 50, 1314):
                self.skipTest('Host cannot create symlinks: ' + str(error))
            raise

    def junction(self, link, target):
        completed = HOST_RUN(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                             capture_output=True, timeout=10)
        if completed.returncode:
            self.skipTest('Host cannot create junctions: ' + completed.stderr.decode(errors='replace'))


class PresentationSourceTests(RetainedFixtures):
    def verification_resource(self, omit=(), route_commit=PINNED_COMMIT):
        self.counter += 1
        skill = self.work / ('synthetic-verification-' + str(self.counter))
        resource = skill / 'resources/presentation-engine'
        resource.mkdir(parents=True)
        (skill / 'references').mkdir()
        routes = {'source_commit': route_commit,
                  'routes': {'synthetic': 'workflows/synthetic-route.md'},
                  'profiles': {'synthetic': 'workflows/synthetic-profile.md'},
                  'supporting_authorities': {'synthetic': 'references/synthetic-authority.md'}}
        (skill / 'references/presentation-capabilities.json').write_text(json.dumps(routes), encoding='utf-8')
        names = {'SKILL.md', 'LICENSE', 'SPONSORS.md', 'SPONSORS_CN.md', 'workflows/routing.md'}
        names.update('scripts/' + name for name in
                     PRESENTATIONS.LOCAL_TOOLS | PRESENTATIONS.NETWORK_TOOLS | PRESENTATIONS.SERVER_TOOLS)
        for section in ('routes', 'profiles', 'supporting_authorities'):
            names.update(routes[section].values())
        names.difference_update(omit)
        rows = [source_row(name, b'# Synthetic unit fixture only.\n') for name in sorted(names)]
        pack, digest = self.write_pack(rows)
        pack.rename(resource / 'resources.json')
        manifest = {'schema_version': 1, 'pack': 'resources.json', 'pack_sha256': digest,
                    'resource_count': len(rows), 'source_commit': PINNED_COMMIT,
                    'source_version': 'synthetic-unit-fixture'}
        (resource / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return skill, resource, len(rows)

    def test_synthetic_content_verification_does_not_claim_execution(self):
        skill, resource, count = self.verification_resource()
        with patch.object(PRESENTATIONS, 'RESOURCE', resource), patch.object(PRESENTATIONS, 'SKILL', skill), \
                patch.object(PRESENTATIONS.subprocess, 'run') as run:
            report = PRESENTATIONS.verify()
        run.assert_not_called()
        self.assertEqual(report['source_commit'], PINNED_COMMIT)
        self.assertEqual(report['resource_files'], count)
        self.assertIs(report['content_verified'], True)
        self.assertIs(report['execution_verified'], False)

    def test_required_resources_cannot_be_omitted_even_with_valid_hashes_and_count(self):
        for name in ('LICENSE', 'SPONSORS.md', 'scripts/project_manager.py', 'workflows/synthetic-route.md'):
            with self.subTest(name=name):
                skill, resource, count = self.verification_resource(omit=(name,))
                with patch.object(PRESENTATIONS, 'RESOURCE', resource), \
                        patch.object(PRESENTATIONS, 'SKILL', skill), \
                        self.assertRaisesRegex(ValueError, 'Missing presentation resources'):
                    PRESENTATIONS.verify()

    def test_capability_routes_must_match_pinned_resource_commit(self):
        skill, resource, count = self.verification_resource(route_commit='0' * 40)
        with patch.object(PRESENTATIONS, 'RESOURCE', resource), patch.object(PRESENTATIONS, 'SKILL', skill), \
                self.assertRaisesRegex(ValueError, 'another source version'):
            PRESENTATIONS.verify()

    def test_synthetic_text_and_binary_resources_round_trip_exact_bytes(self):
        rows = [source_row('scripts/example.py', 'title = "\u4e2d\u6587"\r\n'.encode('utf-8')),
                source_row('assets/example.bin', b'\x00\xff\r\n', binary=True)]
        pack, digest = self.write_pack(rows)
        decoded = list(SOURCE.source_rows(pack, digest))
        self.assertEqual([row for row, data in decoded], rows)
        self.assertEqual([data for row, data in decoded],
                         [rows[0]['text'].encode('utf-8'), b'\x00\xff\r\n'])

    def test_outer_pack_tampering_is_rejected_before_decoding(self):
        pack, digest = self.write_pack([source_row('file.txt', b'synthetic')])
        pack.write_bytes(pack.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'stream hash'):
            list(SOURCE.source_rows(pack, digest))

    def test_envelope_encoding_size_and_decoded_digest_are_checked(self):
        good = source_envelope([source_row('file.txt', b'synthetic')])
        for field, value in (('encoding', 'plain-jsonl'), ('decoded_bytes', 0),
                             ('decoded_bytes', 80_000_001), ('decoded_bytes', good['decoded_bytes'] - 1),
                             ('decoded_bytes', good['decoded_bytes'] + 1), ('jsonl_sha256', '0' * 64)):
            with self.subTest(field=field, value=value):
                envelope = dict(good, **{field: value})
                pack, digest = self.write_envelope(envelope)
                with self.assertRaises(ValueError):
                    list(SOURCE.source_rows(pack, digest))

    def test_invalid_base64_truncation_and_trailing_compressed_data_are_rejected(self):
        good = source_envelope([source_row('file.txt', b'synthetic')])
        compressed = base64.b64decode(good['data'])
        for payload in (b'not base64!', base64.b64encode(compressed[:-2]),
                        base64.b64encode(compressed + b'trailing'),
                        base64.b64encode(compressed + zlib.compress(b'second stream'))):
            with self.subTest(payload=payload):
                pack, digest = self.write_envelope(dict(good, data=payload.decode('ascii')))
                with self.assertRaises(ValueError):
                    list(SOURCE.source_rows(pack, digest))

    def test_rehashed_pack_cannot_disguise_invalid_per_file_bytes(self):
        good = source_row('file.txt', b'synthetic')
        for field, value in (('bytes', good['bytes'] + 1), ('sha256', '0' * 64), ('text', 'changed')):
            with self.subTest(field=field):
                pack, digest = self.write_pack([dict(good, **{field: value})])
                with self.assertRaisesRegex(ValueError, 'resource bytes'):
                    list(SOURCE.source_rows(pack, digest))
        pack, digest = self.write_pack([{'path': 'file.bin', 'bytes': 1,
                                        'sha256': sha256(b'x'), 'base64': '!'}])
        with self.assertRaises(ValueError):
            list(SOURCE.source_rows(pack, digest))

    def test_absolute_parent_alias_and_duplicate_resource_paths_are_rejected(self):
        for name in ('', '.', '../escape', 'a/../../escape', '/absolute', 'C:/escape', 'C:escape',
                     'a\\escape', './file', 'a//file', 'a/./file', 'a/', '//host/share/file'):
            with self.subTest(name=name):
                pack, digest = self.write_pack([source_row(name, b'synthetic')])
                with self.assertRaises(ValueError):
                    list(SOURCE.source_rows(pack, digest))
        row = source_row('same.txt', b'synthetic')
        pack, digest = self.write_pack([row, row])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            list(SOURCE.source_rows(pack, digest))

    def test_manifest_identity_and_resource_count_are_checked(self):
        resource = self.work / 'synthetic-resource'
        resource.mkdir()
        pack, digest = self.write_pack([source_row('file.txt', b'synthetic')])
        pack.rename(resource / 'resources.json')
        manifest_path = resource / 'manifest.json'
        good = {'schema_version': 1, 'source_commit': PINNED_COMMIT, 'pack': 'resources.json',
                'pack_sha256': digest, 'resource_count': 1, 'source_version': 'synthetic-unit-fixture'}
        with patch.object(PRESENTATIONS, 'RESOURCE', resource):
            for field, value in (('schema_version', 2), ('source_commit', '0' * 40),
                                 ('pack', '../outside.json'), ('resource_count', 2)):
                with self.subTest(field=field):
                    manifest_path.write_text(json.dumps(dict(good, **{field: value})), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        PRESENTATIONS.verify()


class PresentationAdaptationTests(unittest.TestCase):
    def adapt(self, text):
        result, calls = SOURCE.adapt_python(text.encode('utf-8'))
        compile(result, '<synthetic-adaptation-fixture>', 'exec')
        return result.decode('utf-8'), calls

    def test_docstring_future_imports_shebang_and_attribution_gate_are_preserved(self):
        source = ('#!/usr/bin/env python\n# coding: utf-8\n'
                  '"""Synthetic \u4e2d\u6587 module.\nNot upstream execution evidence.\n"""\n'
                  'from __future__ import annotations\nfrom __future__ import generator_stop\n'
                  'import os\nfrom attribution_guard import require_attribution\n'
                  'require_attribution()\nos.remove("scratch")\n')
        result, calls = self.adapt(source)
        self.assertEqual(calls, 1)
        self.assertTrue(result.startswith(source[:source.index('import os')]))
        self.assertEqual(ast.get_docstring(ast.parse(result)), ast.get_docstring(ast.parse(source)))
        self.assertLess(result.index('from __future__ import generator_stop'), result.index('import _rsk_retention'))
        self.assertIn('from attribution_guard import require_attribution\nrequire_attribution()\n', result)
        self.assertIn('_rsk_retention.unlink("scratch")', result)

    def test_utf8_ast_byte_columns_handle_chinese_before_multiple_calls(self):
        source = ('import os\nfrom pathlib import Path\n'
                  '\u6807\u9898 = "\u4e2d\u6587"; os.remove("\u65e7\u7a3f"); Path("\u8349\u7a3f").unlink(missing_ok=True)\n')
        result, calls = self.adapt(source)
        self.assertEqual(calls, 2)
        self.assertIn('\u6807\u9898 = "\u4e2d\u6587"; _rsk_retention.unlink("\u65e7\u7a3f"); '
                      '_rsk_retention.unlink(Path("\u8349\u7a3f"), missing_ok=True)', result)

    def test_concrete_cleanup_calls_route_to_retention_with_original_arguments(self):
        source = ('import os, shutil, tempfile\n'
                  'tempfile.TemporaryDirectory(prefix="fixture", dir=base)\n'
                  'shutil.rmtree(folder, ignore_errors=True)\nos.unlink(file)\nos.rmdir(empty)\n'
                  'path.unlink(missing_ok=True)\n(folder / "child").rmdir()\n')
        result, calls = self.adapt(source)
        self.assertEqual(calls, 6)
        for expected in ('_rsk_retention.TemporaryDirectory(prefix="fixture", dir=base)',
                         '_rsk_retention.rmtree(folder, ignore_errors=True)',
                         '_rsk_retention.unlink(file)', '_rsk_retention.rmdir(empty)',
                         '_rsk_retention.unlink(path, missing_ok=True)',
                         '_rsk_retention.rmdir(folder / "child")'):
            self.assertIn(expected, result)

    def test_xml_and_container_remove_are_not_cleanup_and_keep_exact_bytes(self):
        source = (b'from xml.etree.ElementTree import Element\r\n'
                  b'parent = Element("parent")\r\nchild = Element("child")\r\n'
                  b'parent.append(child)\r\nparent.remove(child)\r\n'
                  b'values = [child]\r\nvalues.remove(child)\r\n'
                  b'# os.remove("only a comment")\r\nlabel = "shutil.rmtree(x)"\r\n')
        result, calls = SOURCE.adapt_python(source)
        self.assertEqual((result, calls), (source, 0))
        namespace = {}
        exec(compile(result, '<synthetic-xml-fixture>', 'exec'), namespace)
        self.assertEqual(list(namespace['parent']), [])
        self.assertEqual(namespace['values'], [])

    def test_xml_remove_is_unchanged_when_os_remove_in_same_file_is_adapted(self):
        result, calls = self.adapt('import os\nparent.remove(child)\nos.remove("scratch")\n')
        self.assertEqual(calls, 1)
        self.assertIn('parent.remove(child)\n', result)
        self.assertNotIn('_rsk_retention.remove', result)

    def test_multiline_calls_keep_keywords_and_non_cleanup_bytes(self):
        result, calls = self.adapt('"""Synthetic."""\nfrom __future__ import (\n    annotations,\n)\n'
                                   'import shutil\nshutil.rmtree(\n    scratch,\n    ignore_errors=True,\n)\n')
        self.assertEqual(calls, 1)
        self.assertIn('_rsk_retention.rmtree(\n    scratch,\n    ignore_errors=True,\n)', result)

    def test_mirror_checker_patch_rejects_unreviewed_base_sha_even_with_matching_fragments(self):
        source = (b'from native_payloads import NativePayloadError, hydrate_native_payload_refs\n'
                  b'class SyntheticChecker:\n'
                  b'    def check(self, svg_file, root, result):\n'
                  b'        svg_path = Path(svg_file)\n'
                  b'        unchanged_groups = self._unchanged_txbody_group_ids(root)\n'
                  b"        viewbox = _parse_viewbox_values(root.get('viewBox') or '')\n")
        compile(source, '<synthetic-unreviewed-checker>', 'exec')
        with self.assertRaisesRegex(ValueError, 'exact source bytes'):
            SOURCE.adapt_mirror_checker(source)


class PresentationMirrorTests(RetainedFixtures):
    def setUp(self):
        super().setUp()
        self.project = self.work / 'synthetic-mirror-project'
        self.templates = self.project / 'templates'
        self.templates.mkdir(parents=True)
        self.svg = self.project / 'svg_output/slide.svg'
        self.svg.parent.mkdir()
        self.prototype = self.templates / self.svg.name
        self.raw = (b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="80" '
                    b'viewBox="0 0 100 80" font-family="Arial">'
                    b'<g id="title" transform="translate(1 1)"><text>Synthetic title</text></g>'
                    b'<g id="formula" transform="translate(5 20)" data-synthetic="formula">'
                    b'<text x="2" y="3" font-size="14">x<tspan baseline-shift="super">2</tspan>'
                    b' + y = 1</text></g></svg>')
        self.prototype.write_bytes(self.raw)
        self.root = ET.fromstring(self.raw)
        self.svg.write_bytes(self.raw)
        self.dependency = self.templates / 'contracts/source.json'
        self.dependency.parent.mkdir()
        self.dependency.write_bytes(b'{"synthetic":"dependency, not upstream evidence"}\n')
        self.manifest = {
            'schema': 'ppt-master.template-execution-manifest.v1',
            'replication_mode': 'mirror', 'source_geometry_unchanged': True,
            'source_package_sha256': sha256(b'Synthetic package identity, not an upstream package.'),
            'templates': [{'prototype': self.svg.name, 'source_svg_sha256': sha256(self.raw)}],
            'source_files_sha256': {self.svg.name: sha256(self.raw),
                                    'contracts/source.json': sha256(self.dependency.read_bytes())},
        }
        self.save_manifest(self.manifest)
        self.checker = SimpleNamespace(_rsk_current_svg_path=self.svg)

    def save_manifest(self, value):
        (self.templates / 'template_execution_manifest.json').write_text(json.dumps(value), encoding='utf-8')

    def inherited(self, root=None, result=None):
        root = self.root if root is None else root
        result = {} if result is None else result
        self.svg.write_bytes(ET.tostring(root, encoding='utf-8'))
        return MIRROR.unchanged_mirror_groups(self.checker, root, result), result

    def assert_no_inheritance(self, root=None):
        groups, result = self.inherited(root)
        self.assertEqual(groups, set())
        self.assertEqual(result, {})

    def test_unchanged_formula_is_inherited_but_edited_title_and_existing_errors_are_not_exempted(self):
        self.root[0][0].text = 'Edited synthetic title'
        result = {'errors': ['Synthetic new overflow remains a quality finding.']}
        groups, result = self.inherited(result=result)
        self.assertEqual(groups, {id(self.root[1])})
        self.assertNotIn(id(self.root[0]), groups)
        self.assertEqual(result['errors'], ['Synthetic new overflow remains a quality finding.'])
        self.assertEqual(result['info']['inherited'][0]['kind'], 'unchanged-mirror-module-geometry')

    def test_changed_formula_text_sequence_or_attributes_is_not_inherited(self):
        changes = (
            ('text', lambda group: setattr(group[0], 'text', 'Edited formula')),
            ('tspan text', lambda group: setattr(group[0][0], 'text', '3')),
            ('text tail', lambda group: setattr(group[0][0], 'tail', ' + changed tail')),
            ('group attribute', lambda group: group.set('transform', 'translate(50 20)')),
            ('text attribute', lambda group: group[0].set('font-size', '40')),
        )
        for name, change in changes:
            with self.subTest(change=name):
                root = copy.deepcopy(self.root)
                change(root[1])
                groups, result = self.inherited(root)
                self.assertNotIn(id(root[1]), groups)
                self.assertEqual(groups, {id(root[0])})

    def test_changed_root_tag_or_attributes_disables_inheritance(self):
        for attribute, value in (('width', '200'), ('viewBox', '0 0 200 80'),
                                 ('font-family', 'Synthetic Different Font'), ('tag', 'different-root')):
            with self.subTest(attribute=attribute):
                root = copy.deepcopy(self.root)
                if attribute == 'tag':
                    root.tag = value
                else:
                    root.set(attribute, value)
                self.assert_no_inheritance(root)

    def test_changed_root_style_context_does_not_exempt_identical_formula_groups(self):
        style = ET.Element('{http://www.w3.org/2000/svg}style')
        style.text = 'text { font-size: 14px; }'
        self.root.insert(0, style)
        raw = ET.tostring(self.root, encoding='utf-8')
        self.prototype.write_bytes(raw)
        manifest = copy.deepcopy(self.manifest)
        manifest['templates'][0]['source_svg_sha256'] = sha256(raw)
        manifest['source_files_sha256'][self.svg.name] = sha256(raw)
        self.save_manifest(manifest)
        groups, result = self.inherited()
        self.assertEqual(groups, {id(self.root[1]), id(self.root[2])})
        style.text = 'text { font-size: 140px; }'
        self.assert_no_inheritance()

    def test_changed_root_text_disables_inheritance(self):
        for text in ('\n', 'Synthetic changed root text'):
            with self.subTest(text=text):
                root = copy.deepcopy(self.root)
                root.text = text
                self.assert_no_inheritance(root)

    def test_changed_added_removed_or_reordered_defs_context_never_grants_inheritance(self):
        namespace = '{http://www.w3.org/2000/svg}'
        definitions = ET.Element(namespace + 'defs')
        clip = ET.SubElement(definitions, namespace + 'clipPath', id='synthetic-clip')
        ET.SubElement(clip, namespace + 'rect', width='40', height='20')
        style = ET.Element(namespace + 'style')
        style.text = 'g { clip-path: url(#synthetic-clip); }'
        self.root.insert(0, definitions)
        self.root.insert(1, style)
        raw = ET.tostring(self.root, encoding='utf-8')
        self.prototype.write_bytes(raw)
        manifest = copy.deepcopy(self.manifest)
        manifest['templates'][0]['source_svg_sha256'] = sha256(raw)
        manifest['source_files_sha256'][self.svg.name] = sha256(raw)
        self.save_manifest(manifest)
        groups, result = self.inherited()
        self.assertEqual(groups, {id(self.root[2]), id(self.root[3])})
        original_groups = [ET.tostring(node) for node in self.root if node.tag == namespace + 'g']

        for change in ('definition attribute', 'add definitions', 'remove definitions', 'reorder context'):
            with self.subTest(change=change):
                root = copy.deepcopy(self.root)
                if change == 'definition attribute':
                    root[0][0][0].set('width', '80')
                elif change == 'add definitions':
                    ET.SubElement(root, namespace + 'defs', id='synthetic-added-definitions')
                else:
                    definitions = root[0]
                    root.remove(definitions)
                    if change == 'reorder context':
                        root.insert(1, definitions)
                self.assertEqual([ET.tostring(node) for node in root if node.tag == namespace + 'g'],
                                 original_groups)
                self.assert_no_inheritance(root)

    def test_invalid_source_manifest_never_grants_inheritance(self):
        for field, value in (('schema', 'unreviewed-schema'), ('replication_mode', 'adapt'),
                             ('source_geometry_unchanged', False), ('source_geometry_unchanged', 'true'),
                             ('source_package_sha256', 'invalid'), ('source_files_sha256', {}),
                             ('source_files_sha256', [])):
            with self.subTest(field=field, value=value):
                manifest = copy.deepcopy(self.manifest)
                manifest[field] = value
                self.save_manifest(manifest)
                self.assert_no_inheritance()

    def test_changed_prototype_hash_or_raw_bytes_disables_inheritance(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['templates'][0]['source_svg_sha256'] = '0' * 64
        self.save_manifest(manifest)
        with self.subTest(change='declared prototype hash'):
            self.assert_no_inheritance()
        changed = self.raw + b'\n'
        self.prototype.write_bytes(changed)
        manifest = copy.deepcopy(self.manifest)
        manifest['source_files_sha256'][self.svg.name] = sha256(changed)
        self.save_manifest(manifest)
        with self.subTest(change='raw prototype bytes despite matching dependency hash'):
            self.assert_no_inheritance()

    def test_changed_dependency_hash_or_content_disables_inheritance(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['source_files_sha256']['contracts/source.json'] = '0' * 64
        self.save_manifest(manifest)
        with self.subTest(change='declared dependency hash'):
            self.assert_no_inheritance()
        self.save_manifest(self.manifest)
        self.dependency.write_bytes(self.dependency.read_bytes() + b' ')
        with self.subTest(change='dependency contents'):
            self.assert_no_inheritance()

    def test_dependency_paths_outside_project_are_refused_even_when_hashes_match(self):
        outside = self.work / 'outside-contract.json'
        outside.write_bytes(b'{"synthetic":"outside project"}\n')
        for name in ('../../outside-contract.json', str(outside)):
            with self.subTest(path=name):
                manifest = copy.deepcopy(self.manifest)
                manifest['source_files_sha256'][name] = sha256(outside.read_bytes())
                self.save_manifest(manifest)
                self.assert_no_inheritance()

    def test_missing_or_ambiguous_prototype_entries_never_grant_inheritance(self):
        entry = self.manifest['templates'][0]
        for entries in ([], [entry, entry], [dict(entry, prototype='../../outside.svg')]):
            with self.subTest(entries=entries):
                manifest = copy.deepcopy(self.manifest)
                manifest['templates'] = entries
                self.save_manifest(manifest)
                self.assert_no_inheritance()

    def test_only_direct_child_groups_can_be_inherited(self):
        formula = self.root[1]
        self.root.remove(formula)
        wrapper = ET.SubElement(self.root, '{http://www.w3.org/2000/svg}g', id='new-wrapper')
        wrapper.append(formula)
        groups, result = self.inherited()
        self.assertEqual(groups, {id(self.root[0])})
        self.assertNotIn(id(formula), groups)


class PresentationWorkDirectoryTests(RetainedFixtures):
    def test_work_and_process_local_cache_and_temp_paths(self):
        work = PRESENTATIONS.checked_work(self.work / 'task')
        original_environment = dict(os.environ)
        environment = PRESENTATIONS.environment(work)
        self.assertTrue(work.is_absolute())
        self.assertTrue(work.is_relative_to(TEST_ROOT))
        for key in ('TEMP', 'TMP', 'TMPDIR', 'XDG_CACHE_HOME', 'MPLCONFIGDIR', 'PIP_CACHE_DIR'):
            self.assertTrue(Path(environment[key]).is_relative_to(work), key)
        self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(environment['RSK_PRESENTATION_WORK_ROOT'], str(work))
        self.assertEqual(dict(os.environ), original_environment)

    @unittest.skipUnless(os.name == 'nt', 'Windows drive validation')
    def test_explicit_d_and_e_drives_are_accepted_without_creating_absolute_fixtures(self):
        for drive in ('D:', 'E:'):
            candidate = Path(drive + os.sep) / 'synthetic-not-created'
            with self.subTest(drive=drive), patch.object(Path, 'mkdir') as mkdir:
                self.assertEqual(PRESENTATIONS.checked_work(candidate), candidate)
            mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_relative_c_drive_and_installed_skill_overlap_are_rejected_before_mkdir(self):
        candidates = [Path('relative-task'), PRESENTATIONS.SKILL, PRESENTATIONS.SKILL.parent,
                      PRESENTATIONS.SKILL / 'scratch']
        if os.name == 'nt':
            candidates += [Path('C:/forbidden-task'), Path('D:relative-task')]
        with patch.object(Path, 'mkdir') as mkdir:
            for candidate in candidates:
                with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                    PRESENTATIONS.checked_work(candidate)
        mkdir.assert_not_called()

    def test_parent_components_cannot_hide_installed_skill_overlap(self):
        skill = self.work / 'installed-skill'
        scratch = self.work / 'scratch'
        scratch.mkdir()
        with patch.object(PRESENTATIONS, 'SKILL', skill), self.assertRaises(ValueError):
            PRESENTATIONS.checked_work(scratch / '..' / skill.name)

    def test_symlink_work_directory_and_its_children_are_rejected(self):
        target = self.work / 'target'
        target.mkdir()
        link = self.work / 'linked'
        self.symlink(link, target, directory=True)
        for candidate in (link, link / 'child'):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                PRESENTATIONS.checked_work(candidate)
        self.assertEqual(list(target.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction validation')
    def test_junction_work_directory_and_its_children_are_rejected(self):
        target = self.work / 'target'
        target.mkdir()
        link = self.work / 'junction'
        self.junction(link, target)
        for candidate in (link, link / 'child'):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                PRESENTATIONS.checked_work(candidate)
        self.assertEqual(list(target.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows reparse-point metadata')
    def test_reparse_metadata_is_rejected_without_symlink_privilege(self):
        candidate = self.work / 'reparse'
        candidate.mkdir()
        original = Path.lstat

        def metadata(path, *args, **kwargs):
            if path == candidate:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'lstat', metadata):
            with self.assertRaises(ValueError):
                PRESENTATIONS.checked_work(candidate / 'child')


class PresentationRetentionTests(RetainedFixtures):
    def setUp(self):
        super().setUp()
        environment = patch.dict(os.environ, {'RSK_PRESENTATION_WORK_ROOT': str(self.work)})
        environment.start()
        self.addCleanup(environment.stop)

    def retained_records(self):
        return sorted(self.work.glob('.rsk-retained/*/retention.json'))

    def test_unlink_renames_original_bytes_and_records_provenance_without_deletion(self):
        source = self.work / 'draft.bin'
        raw = b'\x00\xff\r\nsynthetic original'
        source.write_bytes(raw)
        with patch.object(os, 'unlink', side_effect=AssertionError('Deletion is forbidden')), \
                patch.object(os, 'rmdir', side_effect=AssertionError('Deletion is forbidden')), \
                patch.object(shutil, 'rmtree', side_effect=AssertionError('Recursive deletion is forbidden')):
            RETENTION.unlink(source)
        self.assertFalse(source.exists())
        records = self.retained_records()
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0].parent / source.name).read_bytes(), raw)
        self.assertEqual(json.loads(records[0].read_bytes()),
                         {'source': 'draft.bin', 'retained_name': 'draft.bin', 'action': 'rename-not-delete'})

    def test_rmtree_retains_nested_directory_and_duplicate_names_do_not_clobber(self):
        for raw in (b'first synthetic artifact', b'second synthetic artifact'):
            source = self.work / 'tree'
            (source / 'nested').mkdir(parents=True)
            (source / 'nested/file.bin').write_bytes(raw)
            with patch.object(shutil, 'rmtree', side_effect=AssertionError('Recursive deletion is forbidden')):
                RETENTION.rmtree(source)
            self.assertFalse(source.exists())
        records = self.retained_records()
        self.assertEqual(len(records), 2)
        self.assertEqual({(record.parent / 'tree/nested/file.bin').read_bytes() for record in records},
                         {b'first synthetic artifact', b'second synthetic artifact'})

    def test_replacement_temporary_directory_context_and_cleanup_keep_same_directory(self):
        with patch.dict(os.environ, {'RSK_PRESENTATION_WORK_ROOT': str(TEST_ROOT)}), \
                patch.object(tempfile, 'TemporaryDirectory', side_effect=AssertionError('Automatic cleanup forbidden')), \
                patch.object(shutil, 'rmtree', side_effect=AssertionError('Recursive deletion forbidden')):
            temporary = RETENTION.TemporaryDirectory(prefix='synthetic-retention-', dir=str(TEST_ROOT))
            with temporary as name:
                path = Path(name) / 'diagnostic.txt'
                path.write_bytes(b'synthetic diagnostic')
            temporary.cleanup()
            temporary.cleanup()
        self.assertEqual(path.read_bytes(), b'synthetic diagnostic')
        self.assertTrue(Path(name).is_dir())
        self.assertEqual(RETENTION.TemporaryDirectory[str], RETENTION.TemporaryDirectory)

    def test_rmdir_only_retains_empty_directory_and_unlink_does_not_move_directories(self):
        folder = self.work / 'folder'
        folder.mkdir()
        source = folder / 'keep.txt'
        source.write_bytes(b'keep')
        with self.assertRaises(OSError) as caught:
            RETENTION.rmdir(folder)
        self.assertEqual(caught.exception.errno, errno.ENOTEMPTY)
        with self.assertRaises(IsADirectoryError):
            RETENTION.unlink(folder)
        self.assertEqual(source.read_bytes(), b'keep')
        empty = self.work / 'empty'
        empty.mkdir()
        RETENTION.rmdir(empty)
        self.assertTrue((self.retained_records()[0].parent / 'empty').is_dir())

    def test_missing_paths_and_unsupported_options_never_trigger_cleanup(self):
        missing = self.work / 'missing'
        RETENTION.unlink(missing, missing_ok=True)
        RETENTION.rmtree(missing, ignore_errors=True)
        for function in (RETENTION.unlink, RETENTION.rmdir, RETENTION.rmtree):
            with self.subTest(function=function.__name__), self.assertRaises(FileNotFoundError):
                function(missing)
        source = self.work / 'keep.txt'
        source.write_bytes(b'keep')
        for function, options in ((RETENTION.unlink, {'dir_fd': 1}), (RETENTION.rmdir, {'dir_fd': 1}),
                                  (RETENTION.rmtree, {'onerror': None}),
                                  (RETENTION.TemporaryDirectory, {'delete': True, 'dir': str(TEST_ROOT)})):
            with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                function(source, **options)
        self.assertEqual(source.read_bytes(), b'keep')
        self.assertEqual(self.retained_records(), [])

    def test_work_root_itself_outside_paths_and_missing_root_are_rejected(self):
        for value in (self.work, self.work.parent / 'outside-retention-test'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RETENTION.checked_path(value)
        with patch.dict(os.environ, {'RSK_PRESENTATION_WORK_ROOT': ''}), self.assertRaises(ValueError):
            RETENTION.checked_path(self.work / 'file')
        with self.assertRaises(ValueError):
            RETENTION.rmtree(self.work.parent / 'outside-retention-test', ignore_errors=True)

    def test_parent_components_cannot_escape_retention_root(self):
        root = self.work / 'root'
        root.mkdir()
        outside = self.work / 'outside.txt'
        outside.write_bytes(b'synthetic outside-root material')
        with patch.dict(os.environ, {'RSK_PRESENTATION_WORK_ROOT': str(root)}), self.assertRaises(ValueError):
            RETENTION.checked_path(root / '..' / outside.name)
        self.assertEqual(outside.read_bytes(), b'synthetic outside-root material')

    def test_symlink_file_and_linked_parent_are_rejected_without_touching_target(self):
        target = self.work / 'target'
        target.mkdir()
        source = target / 'keep.txt'
        source.write_bytes(b'keep')
        file_link = self.work / 'file-link'
        self.symlink(file_link, source)
        directory_link = self.work / 'directory-link'
        self.symlink(directory_link, target, directory=True)
        for path in (file_link, directory_link / source.name):
            with self.subTest(path=path), self.assertRaises(ValueError):
                RETENTION.unlink(path)
        self.assertEqual(source.read_bytes(), b'keep')
        self.assertEqual(self.retained_records(), [])

    def test_linked_archive_directory_is_refused_before_rename(self):
        source = self.work / 'keep.txt'
        source.write_bytes(b'keep')
        target = self.work / 'archive-target'
        target.mkdir()
        self.symlink(self.work / '.rsk-retained', target, directory=True)
        with self.assertRaises(ValueError):
            RETENTION.unlink(source)
        self.assertEqual(source.read_bytes(), b'keep')
        self.assertEqual(list(target.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction validation')
    def test_junction_retention_parent_and_archive_are_refused(self):
        target = self.work / 'target'
        target.mkdir()
        source = target / 'keep.txt'
        source.write_bytes(b'keep')
        link = self.work / 'junction'
        self.junction(link, target)
        with self.assertRaises(ValueError):
            RETENTION.unlink(link / source.name)
        self.junction(self.work / '.rsk-retained', target)
        with self.assertRaises(ValueError):
            RETENTION.unlink(source)
        self.assertEqual(source.read_bytes(), b'keep')
        self.assertEqual(list(target.iterdir()), [source])

    @unittest.skipUnless(os.name == 'nt', 'Windows reparse-point metadata')
    def test_reparse_point_in_retention_parent_is_refused(self):
        parent = self.work / 'reparse'
        parent.mkdir()
        original = Path.lstat

        def metadata(path, *args, **kwargs):
            if path == parent:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'lstat', metadata):
            with self.assertRaises(ValueError):
                RETENTION.checked_path(parent / 'file')


class PresentationPreparedRuntimeTests(RetainedFixtures):
    def setUp(self):
        super().setUp()
        skill = self.work / 'synthetic-skill'
        (skill / 'scripts').mkdir(parents=True)
        for name in ('presentation_source.py', 'presentation_retention.py', 'presentation_mirror.py'):
            (skill / 'scripts' / name).write_bytes((SCRIPTS / name).read_bytes())
        resource = skill / 'resources/presentation-engine'
        resource.mkdir(parents=True)
        rows = [source_row('scripts/attribution_guard.py', b'# Synthetic guard; launch is mocked.\n'),
                source_row('scripts/project_manager.py', b'import os\nos.remove("synthetic-scratch")\n'),
                source_row('assets/example.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>\n'),
                source_row('contracts/example.json', b'{"synthetic":true}\n'),
                source_row('contracts/example.yaml', b'synthetic: true\n'),
                source_row('workflows/synthetic.md', b'# Synthetic workflow contract\n'),
                source_row('LICENSE', b'Synthetic license fixture, not upstream terms.\n'),
                source_row('SPONSORS.md', b'Synthetic declaration fixture, not upstream attribution.\n')]
        self.rows = rows
        pack, digest = self.write_pack(rows)
        pack.rename(resource / 'resources.json')
        self.synthetic_manifest = {'schema_version': 1, 'source_commit': PINNED_COMMIT,
                                   'source_version': 'synthetic-unit-fixture', 'pack': 'resources.json',
                                   'pack_sha256': digest, 'resource_count': len(rows)}
        (resource / 'manifest.json').write_text(json.dumps(self.synthetic_manifest), encoding='utf-8')
        self.skill = skill
        self.task = self.work / 'task'
        for name, value in (('SKILL', skill), ('RESOURCE', resource)):
            change = patch.object(PRESENTATIONS, name, value)
            change.start()
            self.addCleanup(change.stop)
        change = patch.object(PRESENTATIONS.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 0, stdout='', stderr=''))
        self.launch = change.start()
        self.addCleanup(change.stop)

    def prepare(self, **options):
        return PRESENTATIONS.prepare(self.task, **options)

    def test_synthetic_prepare_records_hashes_adaptation_and_mocked_guard_command(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        self.assertTrue(runtime.is_relative_to(self.task))
        self.assertEqual(len(receipt['files']), self.synthetic_manifest['resource_count'] + 2)
        for name, expected in receipt['files'].items():
            self.assertEqual(sha256((runtime / name).read_bytes()), expected)
        self.assertEqual((runtime / 'scripts/_rsk_retention.py').read_bytes(),
                         (SCRIPTS / 'presentation_retention.py').read_bytes())
        self.assertEqual((runtime / 'scripts/_rsk_mirror.py').read_bytes(),
                         (SCRIPTS / 'presentation_mirror.py').read_bytes())
        self.assertEqual(receipt['adaptation_sources']['presentation_mirror.py'],
                         sha256((SCRIPTS / 'presentation_mirror.py').read_bytes()))
        self.assertEqual(receipt['adapted_files'][0]['cleanup_calls_adapted'], 1)
        self.assertEqual(receipt['adapted_files'][0]['path'], 'scripts/project_manager.py')
        self.assertEqual(receipt['adapted_files'][0]['functional_patches'], [])
        self.assertIn(b'_rsk_retention.unlink', (runtime / 'scripts/project_manager.py').read_bytes())
        self.launch.assert_called_once()
        self.assertEqual(self.launch.call_args.args[0],
                         [sys.executable, '-B', str(runtime / 'scripts/attribution_guard.py')])
        self.assertEqual(self.launch.call_args.kwargs['cwd'], self.task)
        self.assertEqual(self.launch.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(self.launch.call_args.kwargs['timeout'], 30)
        saved = json.loads((self.task / '.rsk-presentation-runtime.json').read_bytes())
        self.assertEqual(saved, receipt)
        self.assertEqual(self.prepare(), receipt)
        self.launch.assert_called_once()

    def test_explicit_refresh_archives_receipt_and_preserves_old_runtime_and_project(self):
        original = self.prepare()
        state = self.task / '.rsk-presentation-runtime.json'
        original_state = state.read_bytes()
        old_runtime = Path(original['runtime'])
        old_files = {name: (old_runtime / name).read_bytes() for name in original['files']}
        project = self.task / 'projects/synthetic-research/source.md'
        project.parent.mkdir(parents=True)
        material = b'# Synthetic research material, not an actual research result.\r\n'
        project.write_bytes(material)
        adapter = self.skill / 'scripts/presentation_source.py'
        adapter.write_bytes(adapter.read_bytes() + b'# Synthetic adapter upgrade.\n')
        with self.assertRaisesRegex(ValueError, 'adapter changed'):
            self.prepare()

        def guard(command, **options):
            self.assertEqual(state.read_bytes(), original_state)
            self.assertFalse((self.task / '.rsk-runtime-history').exists())
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

        self.launch.side_effect = guard
        output = io.StringIO()
        arguments = ['research_presentations.py', 'prepare', '--work-dir', str(self.task), '--refresh']
        with patch.object(sys, 'argv', arguments), redirect_stdout(output), \
                patch.object(shutil, 'rmtree', side_effect=AssertionError('Recursive deletion forbidden')), \
                patch.object(os, 'unlink', side_effect=AssertionError('Deletion forbidden')), \
                patch.object(os, 'rmdir', side_effect=AssertionError('Deletion forbidden')):
            self.assertEqual(PRESENTATIONS.main(), 0)

        refreshed = json.loads(state.read_bytes())
        runtime = Path(refreshed['runtime'])
        self.assertNotEqual(runtime, old_runtime)
        self.assertTrue(runtime.is_relative_to(self.task))
        self.assertNotEqual(refreshed['adaptation_sources'], original['adaptation_sources'])
        self.assertEqual(json.loads(output.getvalue())['runtime'], str(runtime))
        self.assertEqual(self.launch.call_count, 2)
        self.assertEqual(self.launch.call_args.args[0],
                         [sys.executable, '-B', str(runtime / 'scripts/attribution_guard.py')])
        for name, expected in refreshed['files'].items():
            self.assertEqual(sha256((runtime / name).read_bytes()), expected)
        history = list((self.task / '.rsk-runtime-history').glob('*.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].read_bytes(), original_state)
        self.assertEqual({name: (old_runtime / name).read_bytes() for name in original['files']}, old_files)
        self.assertEqual(project.read_bytes(), material)
        self.assertEqual(self.prepare(), refreshed)
        self.assertEqual(self.launch.call_count, 2)

    def test_failed_synthetic_guard_retains_runtime_without_publishing_receipt(self):
        self.launch.return_value = subprocess.CompletedProcess([], 1, stdout='', stderr='synthetic guard failure')
        with self.assertRaisesRegex(ValueError, 'attribution guard failed'):
            self.prepare()
        self.assertFalse((self.task / '.rsk-presentation-runtime.json').exists())
        retained = list(self.task.glob('.ppt-master-runtime/*/scripts/project_manager.py'))
        self.assertEqual(len(retained), 1)
        self.assertIn(b'_rsk_retention.unlink', retained[0].read_bytes())

    def test_changed_cached_script_or_retention_helper_is_rejected_and_retained(self):
        for name in ('scripts/project_manager.py', 'scripts/_rsk_retention.py', 'scripts/_rsk_mirror.py'):
            with self.subTest(name=name):
                self.task = self.work / ('task-' + Path(name).stem)
                receipt = self.prepare()
                path = Path(receipt['runtime']) / name
                path.write_bytes(path.read_bytes() + b'# synthetic cache tampering\n')
                tampered = path.read_bytes()
                before = self.launch.call_count
                with self.assertRaisesRegex(ValueError, 'runtime changed'):
                    self.prepare()
                self.assertEqual(path.read_bytes(), tampered)
                self.assertEqual(self.launch.call_count, before)

    def test_missing_cached_file_is_rejected_without_rebuilding(self):
        receipt = self.prepare()
        path = Path(receipt['runtime']) / 'scripts/project_manager.py'
        retained = path.with_suffix('.py.retained')
        path.rename(retained)
        with self.assertRaises(OSError):
            self.prepare()
        self.assertTrue(retained.is_file())
        self.launch.assert_called_once()

    def test_default_full_check_detects_changed_svg_and_retains_it(self):
        receipt = self.prepare()
        svg = Path(receipt['runtime']) / 'assets/example.svg'
        changed = b'<svg><!-- Synthetic media tampering. --></svg>\n'
        svg.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            self.prepare()
        self.assertEqual(svg.read_bytes(), changed)
        self.launch.assert_called_once()

    def test_fast_media_skip_is_not_full_resource_verification(self):
        receipt = self.prepare()
        svg = Path(receipt['runtime']) / 'assets/example.svg'
        svg.write_bytes(b'<svg><!-- Synthetic changed media. --></svg>\n')
        with patch.object(PRESENTATIONS, 'digest', wraps=PRESENTATIONS.digest) as digest:
            self.assertEqual(self.prepare(full_check=False), receipt)
        self.assertNotIn(svg, [call.args[0] for call in digest.call_args_list])
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            self.prepare(full_check=True)
        self.launch.assert_called_once()

    def test_fast_check_still_rejects_changed_python_json_contracts_and_declarations(self):
        names = ('scripts/project_manager.py', 'scripts/_rsk_retention.py', 'scripts/_rsk_mirror.py',
                 'contracts/example.json', 'contracts/example.yaml', 'workflows/synthetic.md', 'LICENSE', 'SPONSORS.md')
        for index, name in enumerate(names):
            with self.subTest(name=name):
                self.task = self.work / ('task-' + str(index))
                receipt = self.prepare()
                path = Path(receipt['runtime']) / name
                changed = path.read_bytes() + b'\n# Synthetic cache tampering.\n'
                path.write_bytes(changed)
                calls = self.launch.call_count
                with self.assertRaisesRegex(ValueError, 'runtime changed'):
                    self.prepare(full_check=False)
                self.assertEqual(path.read_bytes(), changed)
                self.assertEqual(self.launch.call_count, calls)

    def test_first_fast_preparation_still_validates_source_media_bytes(self):
        rows = copy.deepcopy(self.rows)
        next(row for row in rows if row['path'] == 'assets/example.svg')['text'] = 'changed source bytes'
        raw = json.dumps(source_envelope(rows)).encode('utf-8')
        resource = self.skill / 'resources/presentation-engine'
        (resource / 'resources.json').write_bytes(raw)
        manifest = dict(self.synthetic_manifest, pack_sha256=sha256(raw))
        (resource / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'resource bytes'):
            self.prepare(full_check=False)
        self.assertFalse((self.task / '.rsk-presentation-runtime.json').exists())
        self.assertTrue(list(self.task.glob('.ppt-master-runtime/*')))
        self.launch.assert_not_called()

    def test_fast_check_does_not_allow_media_receipt_paths_to_escape_runtime(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        outside = self.task / 'outside.svg'
        outside.write_bytes(b'<svg><!-- Synthetic outside-runtime media. --></svg>\n')
        changed = copy.deepcopy(receipt)
        changed['files']['../../outside.svg'] = sha256(outside.read_bytes())
        with self.assertRaises(ValueError):
            PRESENTATIONS.runtime_check(runtime, self.task, changed, full_check=False)

    def test_changed_adapter_binding_requires_a_fresh_task(self):
        self.prepare()
        adapter = self.skill / 'scripts/presentation_source.py'
        adapter.write_bytes(adapter.read_bytes() + b'# synthetic adapter change\n')
        with self.assertRaisesRegex(ValueError, 'adapter changed'):
            self.prepare()
        self.launch.assert_called_once()

    def test_foreign_pack_identity_or_runtime_outside_work_is_rejected(self):
        receipt = self.prepare()
        for field, value in (('pack_sha256', '0' * 64), ('runtime', str(self.work / 'outside-runtime'))):
            with self.subTest(field=field):
                changed = dict(receipt, **{field: value})
                with self.assertRaisesRegex(ValueError, 'runtime path or source identity'):
                    PRESENTATIONS.runtime_check(Path(changed['runtime']), self.task, changed)

    def test_parent_components_cannot_hide_runtime_escape(self):
        self.task.mkdir()
        inside = self.task / 'inside'
        inside.mkdir()
        outside = self.work / 'outside-runtime'
        (outside / 'scripts').mkdir(parents=True)
        raw = b'# Synthetic runtime outside the authorized task.\n'
        (outside / 'scripts/project_manager.py').write_bytes(raw)
        runtime = inside / '..' / '..' / outside.name
        receipt = {'pack_sha256': self.synthetic_manifest['pack_sha256'],
                   'files': {'scripts/project_manager.py': sha256(raw)}}
        with self.assertRaises(ValueError):
            PRESENTATIONS.runtime_check(runtime, self.task, receipt)

    def test_receipt_file_paths_cannot_escape_prepared_runtime(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        outside = self.task / 'outside.txt'
        outside.write_bytes(b'synthetic outside-runtime artifact')
        changed = copy.deepcopy(receipt)
        changed['files']['../../outside.txt'] = sha256(outside.read_bytes())
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            PRESENTATIONS.runtime_check(runtime, self.task, changed)

    def test_symlink_cached_file_is_rejected_even_with_matching_bytes(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        path = runtime / 'scripts/project_manager.py'
        original = self.work / 'retained-original.py'
        path.rename(original)
        self.symlink(path, original)
        with self.assertRaisesRegex(ValueError, 'runtime changed'):
            self.prepare()
        self.assertEqual(sha256(original.read_bytes()), receipt['files']['scripts/project_manager.py'])

    def test_linked_runtime_ancestor_is_rejected_even_when_hashes_match(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        original = self.work / 'retained-runtime-parent'
        runtime.parent.rename(original)
        self.symlink(runtime.parent, original, directory=True)
        with self.assertRaises(ValueError):
            self.prepare()

    @unittest.skipUnless(os.name == 'nt', 'Windows junction validation')
    def test_junction_runtime_ancestor_is_rejected_even_when_hashes_match(self):
        receipt = self.prepare()
        runtime = Path(receipt['runtime'])
        original = self.work / 'retained-runtime-parent'
        runtime.parent.rename(original)
        self.junction(runtime.parent, original)
        with self.assertRaises(ValueError):
            self.prepare()


class PresentationLauncherTests(RetainedFixtures):
    def forward(self, system, platform, error=None):
        script = self.work / '\u4e2d\u6587 synthetic tool.py'
        arguments = [str(script), '--input', 'synthetic material with spaces']

        def dispatch(path, run_name):
            self.assertEqual(path, str(script.resolve()))
            self.assertEqual(run_name, '__main__')
            self.assertEqual(sys.argv, arguments)
            self.assertEqual(sys.path[0], str(script.parent))
            if error is not None:
                raise error

        with patch.object(LAUNCH, 'os', SimpleNamespace(name=system)), \
                patch.object(LAUNCH, 'platform', platform), \
                patch.object(sys, 'argv', ['presentation_launch.py', *arguments]), \
                patch.object(sys, 'path', list(sys.path)), \
                patch.object(LAUNCH.runpy, 'run_path', side_effect=dispatch) as run:
            LAUNCH.main()
        run.assert_called_once_with(str(script.resolve()), run_name='__main__')

    def test_windows_launcher_forwards_arguments_and_uses_process_local_native_fallback(self):
        platform = SimpleNamespace(_wmi=object(), _uname_cache=object())
        self.forward('nt', platform)
        self.assertIsNone(platform._wmi)
        self.assertIsNone(platform._uname_cache)

    def test_non_windows_launcher_does_not_modify_platform_state(self):
        wmi, cache = object(), object()
        platform = SimpleNamespace(_wmi=wmi, _uname_cache=cache)
        self.forward('posix', platform)
        self.assertIs(platform._wmi, wmi)
        self.assertIs(platform._uname_cache, cache)

    def test_windows_without_optional_wmi_attribute_does_not_modify_platform_state(self):
        cache = object()
        platform = SimpleNamespace(_uname_cache=cache)
        self.forward('nt', platform)
        self.assertFalse(hasattr(platform, '_wmi'))
        self.assertIs(platform._uname_cache, cache)

    def test_launcher_preserves_tool_exit_status(self):
        with self.assertRaises(SystemExit) as caught:
            self.forward('posix', SimpleNamespace(), error=SystemExit(23))
        self.assertEqual(caught.exception.code, 23)


class PresentationRunnerTests(RetainedFixtures):
    def setUp(self):
        super().setUp()
        self.runtime = self.work / 'synthetic-runtime-not-executed'
        change = patch.object(PRESENTATIONS, 'prepare', return_value={'runtime': str(self.runtime)})
        self.prepare = change.start()
        self.addCleanup(change.stop)
        change = patch.object(PRESENTATIONS.subprocess, 'run',
                              return_value=subprocess.CompletedProcess([], 7))
        self.launch = change.start()
        self.addCleanup(change.stop)

    def tool_arguments(self, tool):
        self.prepare.assert_called_with(self.work, full_check=False)
        command = self.launch.call_args.args[0]
        launcher = str(SCRIPTS / 'presentation_launch.py')
        script = str(self.runtime / 'scripts' / tool)
        launcher_index = command.index(launcher)
        tool_index = command.index(script)
        self.assertEqual(command[:launcher_index], [sys.executable, '-B'])
        self.assertEqual(tool_index, launcher_index + 1)
        return command[tool_index + 1:]

    def test_unknown_and_update_tools_are_rejected_before_preparation(self):
        for name in ('../outside.py', '/absolute.py', 'update.py', 'git', 'source_to_md/../image_gen.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                PRESENTATIONS.run_tool(name, [], self.work, allow_network=True, allow_server=True)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()

    def test_all_network_and_server_tools_require_their_respective_options(self):
        for names, options in ((PRESENTATIONS.NETWORK_TOOLS, {'allow_server': True}),
                               (PRESENTATIONS.SERVER_TOOLS, {'allow_network': True})):
            for name in sorted(names):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    PRESENTATIONS.run_tool(name, [], self.work, **options)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()

    def test_url_arguments_require_network_permission_even_for_local_tools(self):
        for url in ('http://example.invalid/source', 'https://example.invalid/source',
                    'HTTPS://example.invalid/source'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'URL input'):
                PRESENTATIONS.run_tool('source_to_md.py', [url], self.work)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()

    def test_explicit_network_and_server_options_dispatch_only_the_requested_tool(self):
        for tool, options in (('image_search.py', {'allow_network': True}),
                              ('source_to_md/web_to_md.py', {'allow_network': True}),
                              ('confirm_ui/server.py', {'allow_server': True}),
                              ('source_to_md.py', {'allow_network': True})):
            with self.subTest(tool=tool):
                arguments = ['https://example.invalid/source'] if options.get('allow_network') else []
                result = PRESENTATIONS.run_tool(tool, arguments, self.work, **options)
                self.assertEqual(result, 7)
                self.assertEqual(self.tool_arguments(tool), arguments)
                self.assertEqual(self.launch.call_args.kwargs['cwd'], self.work)
                environment = self.launch.call_args.kwargs['env']
                self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
                for key in ('TEMP', 'TMP', 'TMPDIR'):
                    self.assertTrue(Path(environment[key]).is_relative_to(self.work))

    def test_nested_tool_pythonpath_defaults_precede_inherited_directories(self):
        defaults = [str(self.runtime / 'scripts'), str(self.runtime)]
        inherited_paths = [str(self.work / 'inherited modules'), str(self.work / 'additional-modules')]
        cases = ((None, []), ('', []), (os.pathsep.join(inherited_paths), inherited_paths))
        tool = 'source_to_md/ppt_to_md.py'
        for inherited, tail in cases:
            with self.subTest(inherited=inherited), patch.dict(os.environ):
                os.environ.pop('PYTHONPATH', None)
                if inherited is not None:
                    os.environ['PYTHONPATH'] = inherited
                original_environment = dict(os.environ)
                self.assertEqual(PRESENTATIONS.run_tool(tool, [], self.work), 7)
                self.assertEqual(self.tool_arguments(tool), [])
                environment = self.launch.call_args.kwargs['env']
                self.assertEqual(environment['PYTHONPATH'].split(os.pathsep), [*defaults, *tail])
                self.assertEqual(dict(os.environ), original_environment)

    def test_fresh_svg_export_defaults_to_quiet_transition_without_motion_configuration(self):
        project = self.work / 'synthetic-fresh-project'
        project.mkdir()
        output = self.work / 'synthetic-not-exported.pptx'
        arguments = [str(project), '-o', str(output)]
        self.assertFalse((project / 'animations.json').exists())
        self.assertEqual(PRESENTATIONS.run_tool('svg_to_pptx.py', list(arguments), self.work), 7)
        self.assertEqual(self.tool_arguments('svg_to_pptx.py'), [*arguments, '-t', 'none'])
        self.prepare.assert_called_once_with(self.work, full_check=False)
        self.launch.assert_called_once()
        self.assertFalse((project / 'animations.json').exists())
        self.assertFalse(output.exists())

    def test_svg_export_preserves_existing_motion_roundtrip_and_explicit_options(self):
        project = self.work / 'synthetic-fresh-project'
        project.mkdir()
        configured = self.work / 'synthetic-configured-project'
        configured.mkdir()
        configuration = configured / 'animations.json'
        original = b'{"synthetic":"existing motion configuration"}\r\n'
        configuration.write_bytes(original)
        narration = str(self.work / 'synthetic-narration.wav')
        inherited_motion = str(self.work / 'synthetic-original.pptx')
        options = (['--roundtrip'], ['-t', 'fade'], ['--transition', 'fade'], ['--transition=fade'],
                   ['--animation-config', str(configuration)], ['--animation-config=' + str(configuration)],
                   ['--recorded-narration', narration], ['--recorded-narration=' + narration],
                   ['--inherit-motion-from', inherited_motion], ['--inherit-motion-from=' + inherited_motion],
                   ['--no-animations'], ['--help'], ['-h'])
        cases = [[str(configured)], *[[str(project), *choice] for choice in options], ['--help']]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assertEqual(PRESENTATIONS.run_tool('svg_to_pptx.py', list(arguments), self.work), 7)
                self.assertEqual(self.tool_arguments('svg_to_pptx.py'), arguments)
                self.assertEqual(configuration.read_bytes(), original)

    def test_server_permission_does_not_authorize_network_arguments(self):
        with self.assertRaisesRegex(ValueError, 'URL input'):
            PRESENTATIONS.run_tool('confirm_ui/server.py', ['http://example.invalid'],
                                   self.work, allow_server=True)
        self.prepare.assert_not_called()

    def test_project_init_defaults_to_task_directory_and_preserves_explicit_directory(self):
        PRESENTATIONS.run_tool('project_manager.py', ['init', 'synthetic'], self.work)
        self.assertEqual(self.tool_arguments('project_manager.py')[-2:], ['--dir', str(self.work / 'projects')])
        arguments = ['init', 'synthetic', '--dir', str(self.work / 'explicit-projects')]
        PRESENTATIONS.run_tool('project_manager.py', list(arguments), self.work)
        self.assertEqual(self.tool_arguments('project_manager.py'), arguments)

    def test_import_sources_defaults_to_copy_and_refuses_move_before_preparation(self):
        with self.assertRaisesRegex(ValueError, 'original research materials'):
            PRESENTATIONS.run_tool('project_manager.py', ['import-sources', '--move'], self.work)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()
        PRESENTATIONS.run_tool('project_manager.py', ['import-sources', 'synthetic-source'], self.work)
        self.assertEqual(self.tool_arguments('project_manager.py')[-1], '--copy')
        PRESENTATIONS.run_tool('project_manager.py', ['import-sources', '--copy'], self.work)
        self.assertEqual(self.tool_arguments('project_manager.py').count('--copy'), 1)

    def test_cli_forwards_explicit_options_and_strips_argument_separator(self):
        arguments = ['research_presentations.py', 'run', '--work-dir', str(self.work),
                     '--allow-network', '--allow-server', 'source_to_md.py', '--', 'https://example.invalid']
        with patch.object(sys, 'argv', arguments), patch.object(PRESENTATIONS, 'run_tool', return_value=9) as run:
            self.assertEqual(PRESENTATIONS.main(), 9)
        run.assert_called_once_with('source_to_md.py', ['https://example.invalid'], self.work, True, True)

    def test_doctor_does_not_prepare_execute_or_claim_network_verification(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['research_presentations.py', 'doctor']), \
                patch.object(PRESENTATIONS.importlib.util, 'find_spec', return_value=None), \
                patch.object(PRESENTATIONS.shutil, 'which', return_value=None), redirect_stdout(output):
            self.assertEqual(PRESENTATIONS.main(), 0)
        report = json.loads(output.getvalue())
        self.assertIs(report['network_checked'], False)
        self.assertEqual(report['model_calls'], 0)
        self.prepare.assert_not_called()
        self.launch.assert_not_called()


if __name__ == '__main__':
    print('Synthetic presentation fixtures are retained under: ' + str(TEST_ROOT), flush=True)
    unittest.main()
