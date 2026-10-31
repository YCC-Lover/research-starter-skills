"""Run real pinned presentation tools on retained synthetic files, without a model."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import yaml
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / 'skills/rsk-research-workflow/scripts/research_presentations.py'


class NativePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not importlib.util.find_spec('pptx'):
            raise unittest.SkipTest('Install requirements-presentations.txt for native export tests.')
        cls.work = Path(tempfile.mkdtemp(prefix='rsk-native-ppt-', dir=os.environ.get(
            'RSK_PRESENTATION_TEST_ROOT', tempfile.gettempdir())))
        cls.project = cls.work / 'synthetic'
        (cls.project / 'svg_output').mkdir(parents=True)
        (cls.project / 'notes').mkdir()
        cls.env = {**os.environ, 'TEMP': str(cls.work), 'TMP': str(cls.work),
                   'TMPDIR': str(cls.work), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        cls.counter = 0
        print('Retained real native-presentation fixtures: ' + str(cls.work), flush=True)
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" lang="en-US">
<rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>
<rect x="64" y="76" width="8" height="52" fill="#127F70"/>
<text id="title" x="96" y="116" font-family="Arial" font-size="44" fill="#20282A">Synthetic native export check</text>
<text id="body" x="96" y="210" font-family="Arial" font-size="28" fill="#20282A">The ratio is defined, not fitted to experimental data.</text>
<text id="formula" x="96" y="320" font-family="Arial" font-size="34" fill="#127F70">Ratio = <tspan data-pptx-inline-formula="\\frac{a}{b}">a/b</tspan></text>
<line x1="96" y1="540" x2="1184" y2="540" stroke="#CC563E" stroke-width="3"/>
<text id="footer" x="96" y="596" font-family="Arial" font-size="22" fill="#50595C">Synthetic software fixture. No scientific result is claimed.</text>
</svg>'''
        (cls.project / 'svg_output/01_probe.svg').write_text(svg, encoding='utf-8')
        (cls.project / 'notes/01_probe.md').write_text(
            'This is a synthetic software validation slide. The ratio is a definition, not a measured result.\n',
            encoding='utf-8')
        cls.invoke('svg_quality_checker.py', str(cls.project), '--quick-generate', '--stage', 'final',
                   '--canonical-authoring', '--json')
        cls.source = cls.work / 'native-source.pptx'
        cls.invoke('svg_to_pptx.py', str(cls.project), '--quick-generate', '--with-notes',
                   '-o', str(cls.source), '-t', 'none')

    @classmethod
    def invoke(cls, tool, *arguments, success=True):
        cls.counter += 1
        completed = subprocess.run([sys.executable, '-B', str(ADAPTER), 'run',
                                   '--work-dir', str(cls.work), tool, '--', *arguments],
                                  cwd=cls.work, env=cls.env, text=True, encoding='utf-8',
                                  capture_output=True, timeout=240)
        (cls.work / ('command-' + str(cls.counter) + '.log')).write_text(
            completed.stdout + '\n' + completed.stderr, encoding='utf-8')
        if success and completed.returncode:
            raise AssertionError(tool + ': ' + (completed.stdout + completed.stderr)[-6000:])
        return completed

    def test_native_text_math_and_notes_exist_in_real_export(self):
        with zipfile.ZipFile(self.source) as package:
            self.assertIsNone(package.testzip())
            slide = ET.fromstring(package.read('ppt/slides/slide1.xml'))
            ns = {'m': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
                  'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
                  'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
            self.assertTrue(slide.findall('.//m:oMath', ns))
            self.assertTrue(slide.findall('.//p:sp', ns))
            self.assertIn('Synthetic native export check', ''.join(slide.itertext()))
            self.assertIn(b'synthetic software validation', package.read('ppt/notesSlides/notesSlide1.xml'))
        checked = self.invoke('pptx_delivery_check.py', str(self.source))
        report = json.loads(checked.stdout)
        self.assertEqual(report['schema'], 'ppt-master.pptx-delivery-check.v1')
        readback = self.work / 'actual-readback.md'
        self.invoke('source_to_md/ppt_to_md.py', str(self.source), '-o', str(readback))
        self.assertIn('Synthetic native export check', readback.read_text(encoding='utf-8'))

    def test_identity_roundtrip_keeps_slide_and_inheritance_bytes(self):
        workspace = self.work / 'roundtrip'
        self.invoke('pptx_to_svg.py', str(self.source), '-o', str(workspace),
                    '--inheritance-mode', 'both', '--roundtrip')
        self.invoke('svg_quality_checker.py', str(workspace), '--roundtrip', '--json')
        target = self.work / 'identity-roundtrip.pptx'
        result = self.invoke('svg_to_pptx.py', str(workspace), '--roundtrip', '-o', str(target))
        self.assertIn('passthrough=1', result.stdout)
        self.assertIn('rebuilt=0', result.stdout)
        with zipfile.ZipFile(self.source) as source, zipfile.ZipFile(target) as output:
            names = [name for name in source.namelist() if name == 'ppt/slides/slide1.xml'
                     or name.startswith(('ppt/slideMasters/', 'ppt/slideLayouts/'))]
            self.assertTrue(names)
            for name in names:
                self.assertEqual(source.read(name), output.read(name), name)
        self.assertTrue((workspace / 'sources/source.pptx').is_file())

    def test_mirror_reuse_preserves_math_and_rejects_new_text_overflow(self):
        imported, mirror = self.work / 'template-import', self.work / 'mirror'
        self.invoke('pptx_template_import.py', str(self.source), '-o', str(imported),
                    '--inheritance-mode', 'both')
        self.invoke('mirror_template_materialize.py', str(imported), str(mirror), '--kind', 'deck')
        spec = next((mirror / 'templates').glob('design_spec.deck.*.md'))
        front, body = spec.read_text(encoding='utf-8')[4:].split('\n---\n', 1)
        metadata = yaml.safe_load(front)
        metadata['deck_id'] = 'native-fixture'
        body = body.replace('<!-- TODO -->', 'Synthetic source-bound validation prototype; no real experiment or brand.')
        spec.write_text('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n' + body, encoding='utf-8')
        spec.rename(spec.with_name('design_spec.deck.native-fixture.md'))
        self.invoke('project_manager.py', 'init', 'reuse', '--quick-generate',
                    '--dir', str(self.work / 'projects'))
        project = next((self.work / 'projects').iterdir())
        self.invoke('apply_template.py', str(project), '--root', str(mirror))
        prototype = project / 'templates/001_cover.svg'
        page = project / 'svg_output/001_cover.svg'
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        root = ET.fromstring(prototype.read_bytes())
        title = next(node for node in root.iter() if node.text == 'Synthetic native export check')
        title.text = 'Reused native template'
        ET.ElementTree(root).write(page, encoding='utf-8', xml_declaration=True)
        self.invoke('svg_quality_checker.py', str(project), '--quick-generate',
                    '--stage', 'final', '--canonical-authoring', '--json')
        report = project / 'validation/svg_quality_report.json'
        self.assertIn('unchanged-mirror-module-geometry', report.read_text(encoding='utf-8'))
        output = self.work / 'reused-native.pptx'
        self.invoke('svg_to_pptx.py', str(project), '--quick-generate',
                    '--primary-language', 'en-US', '-o', str(output))
        with zipfile.ZipFile(output) as package:
            xml = package.read('ppt/slides/slide1.xml')
            self.assertIn(b'Reused native template', xml)
            self.assertIn(b'oMath', xml)
            self.assertTrue(any(name.startswith('ppt/slideMasters/slideMaster') for name in package.namelist()))
        good_page = page.read_bytes()
        title.text = 'Introduced overflow ' * 200
        ET.ElementTree(root).write(page, encoding='utf-8', xml_declaration=True)
        failed = self.invoke('svg_quality_checker.py', str(project), '--quick-generate',
                             '--stage', 'final', '--canonical-authoring', '--json', success=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('exceeds', failed.stdout)
        (self.work / 'intentionally-overflowing-template.svg').write_bytes(page.read_bytes())
        (self.work / 'introduced-overflow-quality.json').write_bytes(report.read_bytes())
        page.write_bytes(good_page)


if __name__ == '__main__':
    unittest.main()
