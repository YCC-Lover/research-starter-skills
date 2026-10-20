import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProseCapabilityTests(unittest.TestCase):
    def test_all_declared_patterns_have_their_actual_guide_section(self):
        manifest = json.loads((ROOT / 'docs/PROSE_CAPABILITIES.json').read_text(encoding='utf-8'))
        self.assertEqual([p['id'] for p in manifest['patterns']], ['P' + str(i).zfill(2) for i in range(1, 27)])
        for pattern in manifest['patterns']:
            text = (ROOT / pattern['target']).read_text(encoding='utf-8')
            self.assertIn('### ' + pattern['section'], text)

    def test_component_license_is_distributed_with_the_guide(self):
        path = ROOT / 'skills/rsk-paper-writing/references/third-party-notices.md'
        text = path.read_text(encoding='utf-8')
        self.assertIn('Copyright (c) 2025 Siqi Chen', text)
        self.assertIn('The above copyright notice and this permission notice shall be included', text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', text)
        self.assertIn('8c307f367c91bd974002f10f2be2965d642c13df', text)

    def test_other_editing_capabilities_are_mapped_without_claiming_outcomes(self):
        manifest = json.loads((ROOT / 'docs/PROSE_CAPABILITIES.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['other_capabilities']), 15)
        self.assertTrue(manifest['coverage_is_not_effectiveness_proof'])
        for item in manifest['other_capabilities']:
            self.assertTrue((ROOT / item['target']).is_file())
        self.assertRegex(manifest['source']['revision'], r'^[0-9a-f]{40}$')


if __name__ == '__main__':
    unittest.main()
