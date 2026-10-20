import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prose_edit', ROOT / 'skills/rsk-paper-writing/scripts/check_prose_edit.py')
PROSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROSE)


class ProseTests(unittest.TestCase):
    def test_prose_can_change_without_touching_locks(self):
        before = '---\ntitle: Fixed\n---\nIt serves as a useful result [source](https://example.org/paper).\n```python\nx = 2\n```\n'
        after = before.replace('It serves as a useful result', 'It is a useful result')
        self.assertTrue(PROSE.compare(before, after)['protected_spans_unchanged'])

    def test_frontmatter_is_protected(self):
        self.assertFalse(PROSE.compare('---\na: one\n---\nText', '---\na: two\n---\nText')['protected_spans_unchanged'])

    def test_variable_fences_and_inline_code_are_protected(self):
        for before, after in [('~~~text\nkeep me\n~~~\n', '~~~text\nchanged\n~~~\n'),
                              ('Use ``a ` b`` here.', 'Use ``a ` c`` here.'),
                              ('```text\nkeep unclosed', '```text\nchanged unclosed')]:
            with self.subTest(before=before):
                self.assertFalse(PROSE.compare(before, after)['protected_spans_unchanged'])

    def test_link_label_can_change_but_nested_target_cannot(self):
        before = '[old](https://example.org/a(b))'
        self.assertTrue(PROSE.compare(before, before.replace('[old]', '[new]'))['protected_spans_unchanged'])
        self.assertFalse(PROSE.compare(before, before.replace('a(b)', 'a(c)'))['protected_spans_unchanged'])

    def test_reference_and_html_targets_are_protected(self):
        for before in ('[ref]: https://example.org/a\n', '<a href="https://example.org/a">Label</a>',
                       '<img src="https://example.org/a"/>', '<https://example.org/a>'):
            with self.subTest(before=before):
                self.assertFalse(PROSE.compare(before, before.replace('/a', '/b'))['protected_spans_unchanged'])

    def test_numbers_units_and_duplicate_counts_are_checked(self):
        for before, after in [('n = 2. n = 2.', 'n = 2.'), ('25%', '26%'), ('10 ms', '10 s'), ('1e-3', '1e-4')]:
            with self.subTest(before=before):
                self.assertFalse(PROSE.compare(before, after)['protected_spans_unchanged'])

    def test_citation_keys_cannot_change(self):
        for before in ('See \\citep[2]{alpha2024}.', 'See [@alpha2024].', 'Use \\ref{fig:a}.'):
            with self.subTest(before=before):
                self.assertFalse(PROSE.compare(before, before.replace('alpha2024', 'beta2024').replace('fig:a', 'fig:b'))['protected_spans_unchanged'])

    def test_math_dollar_delimiters_and_environments_are_protected(self):
        for before in ('$x > y$', '$$x > y$$', r'\(x > y\)', r'\[x > y\]', r'\begin{align}x > y\end{align}'):
            with self.subTest(before=before):
                self.assertFalse(PROSE.compare(before, before.replace('>', '<'))['protected_spans_unchanged'])

    def test_reordering_whole_protected_spans_is_allowed(self):
        self.assertTrue(PROSE.compare('`alpha` then `beta`', '`beta` then `alpha`')['protected_spans_unchanged'])

    def test_semantic_scope_is_not_claimed_as_machine_verified(self):
        result = PROSE.compare('The effect may hold.', 'The effect always holds.')
        self.assertTrue(result['protected_spans_unchanged'])
        self.assertTrue(any('semantic' in item for item in result['limits']))
        self.assertEqual(result['files_written'], 0)


if __name__ == '__main__':
    unittest.main()
