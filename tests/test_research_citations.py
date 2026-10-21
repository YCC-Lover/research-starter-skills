"""Synthetic resolver clients test the adapter, not live database coverage."""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / 'skills/research-starter-paper/scripts'
sys.path.insert(0, str(ADAPTERS))
SPEC = importlib.util.spec_from_file_location('rsk_citations', ADAPTERS / 'research_citations.py')
CITATIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CITATIONS)
sys.path.insert(0, str(CITATIONS.ENGINE))
sys.path.insert(0, str(CITATIONS.ENGINE / 'scripts'))


class ResolverFixture:
    def doi_lookup_with_title_check(self, doi, title):
        return {'matched': True}

    def title_search(self, title):
        return {'matched': True}

    def lookup(self, entry):
        return {'matched': True}

    def arxiv_id_lookup(self, identifier, title):
        return {'matched': True}


class CitationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-citations-'))
        if os.name == 'nt' and self.work.drive.upper() not in {'D:', 'E:'}:
            raise RuntimeError('Set TEMP to a D/E task directory before testing.')
        self.passport = self.work / 'passport.yaml'
        self.passport.write_text(
            'literature_corpus:\n  - citation_key: example2024\n'
            '    title: Synthetic software test record\n    year: 2024\n'
            '    authors:\n      - family: Example\n'
            '    source_pointer: urn:rsk:synthetic-fixture\n', encoding='utf-8')
        self.manuscript = self.work / 'draft.md'
        self.manuscript.write_text('Synthetic discussion. <!--ref:paper-one-->\n', encoding='utf-8')
        self.join = self.work / 'join.json'
        self.write_join('paper-one')
        self.calls = 0

    def write_join(self, slug):
        self.join.write_text(json.dumps({
            'schema': 'rsk.citation-join.v1',
            'manuscript_sha256': hashlib.sha256(self.manuscript.read_bytes()).hexdigest(),
            'ref_slug_by_key': {'example2024': slug}}), encoding='utf-8')

    def clients(self):
        self.calls += 1
        return {name: ResolverFixture() for name in ('crossref', 'openalex', 'semantic_scholar', 'arxiv')}

    def verify(self, **kwargs):
        return CITATIONS.verify(self.passport, self.manuscript, self.join, self.work,
                                clients_factory=self.clients, **kwargs)

    def test_no_network_authorization_does_not_construct_clients(self):
        with self.assertRaisesRegex(ValueError, 'allow-metadata-network'):
            self.verify()
        self.assertEqual(self.calls, 0)

    def test_real_marker_join_is_used_without_claiming_content_or_reading(self):
        result = self.verify(allow_metadata_network=True, no_cache=True)
        row = result['citation_verification_summary'][0]
        self.assertEqual((row['citation_key'], row['ref_slug']), ('example2024', 'paper-one'))
        self.assertEqual(row['lookup_verified'], 'true')
        self.assertFalse(row['anchor_present'])
        self.assertIn('not_claim_support_or_reading', result['verification_scope'])
        self.assertEqual(result['inputs']['manuscript_sha256'],
                         hashlib.sha256(self.manuscript.read_bytes()).hexdigest())

    def test_stale_join_and_absent_marker_fail_before_clients(self):
        self.manuscript.write_text('Changed draft', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'current manuscript bytes'):
            self.verify(allow_metadata_network=True)
        self.write_join('not-present')
        with self.assertRaisesRegex(ValueError, 'actually present'):
            self.verify(allow_metadata_network=True)
        self.assertEqual(self.calls, 0)

    def test_invalid_corpus_is_rejected_before_network(self):
        self.passport.write_text('literature_corpus:\n  - citation_key: example2024\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Invalid literature corpus'):
            self.verify(allow_metadata_network=True)
        self.assertEqual(self.calls, 0)

    def test_cache_stays_inside_selected_work_directory(self):
        result = self.verify(allow_metadata_network=True)
        self.assertEqual(Path(result['cache_path']), self.work / '.rsk-cache/verification.db')
        self.assertTrue(Path(result['cache_path']).is_file())


if __name__ == '__main__':
    unittest.main()
