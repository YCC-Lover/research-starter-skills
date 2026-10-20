import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('research_session', ROOT / 'skills/research-starter-paper/scripts/research_session.py')
SESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SESSION)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-session-'))
        self.session = SESSION.Session(self.work)
        self.session.init('Prepare the first research meeting')

    def test_initialization_is_idempotent_and_does_not_reset_goal(self):
        result = self.session.init('Different goal')
        self.assertEqual(result['revision'], 1)
        self.assertEqual(result['state']['goal'], 'Prepare the first research meeting')

    def test_checkpoint_merges_records_and_retains_permanent_history(self):
        first = self.session.journal / '00000001.json'
        original = first.read_bytes()
        self.session.checkpoint({'facts': {'f1': {'text': 'No results yet', 'basis': 'user-report', 'source': 'message 1'}}}, 1)
        self.session.checkpoint({'next_step': 'Read one abstract'}, 2)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(len(list(self.session.journal.glob('*.json'))), 3)
        self.assertEqual(self.session.resume()['state']['facts']['f1']['basis'], 'user-report')

    def test_new_session_recovers_answer_and_next_step(self):
        self.session.checkpoint({'questions': {'q1': {'text': 'Do you have a paper?', 'status': 'answered', 'answer': 'No'}},
                                 'next_step': 'Prepare a search query'}, 1)
        restored = SESSION.Session(self.work).resume()
        self.assertEqual(restored['open_questions'], {})
        self.assertEqual(restored['state']['next_step'], 'Prepare a search query')
        self.assertEqual(restored['state']['questions']['q1']['answer'], 'No')

    def test_unavailable_answer_does_not_reopen_automatically(self):
        self.session.checkpoint({'questions': {'q1': {'text': 'What is the instrument model?', 'status': 'unavailable'}}}, 1)
        self.assertFalse(self.session.resume()['open_questions'])
        with self.assertRaisesRegex(ValueError, 'answered question'):
            self.session.checkpoint({'questions': {'q1': {'status': 'open'}}}, 2)
        self.session.checkpoint({'questions': {'q1': {'status': 'open', 'reopened_reason': 'A new measurement is requested'}}}, 2)

    def test_answered_question_requires_answer(self):
        with self.assertRaisesRegex(ValueError, 'needs its answer'):
            self.session.checkpoint({'questions': {'q1': {'text': 'Task?', 'status': 'answered'}}}, 1)

    def test_revision_conflict_does_not_overwrite(self):
        self.session.checkpoint({'next_step': 'Keep this'}, 1)
        with self.assertRaisesRegex(ValueError, 'Revision changed'):
            self.session.checkpoint({'next_step': 'Overwrite'}, 1)
        self.assertEqual(self.session.resume()['state']['next_step'], 'Keep this')

    def test_done_task_requires_actual_evidence(self):
        with self.assertRaisesRegex(ValueError, 'need evidence'):
            self.session.checkpoint({'tasks': {'t1': {'text': 'Run an experiment', 'status': 'done'}}}, 1)

    def test_done_task_can_reference_generated_file(self):
        artifact = self.work / 'question-card.md'
        artifact.write_text('A research question, not an experimental result.', encoding='utf-8')
        key = SESSION.Session.file_id(str(artifact.resolve()))
        result = self.session.checkpoint({'tasks': {'t1': {'text': 'Write the question card', 'status': 'done',
                                                         'evidence': ['artifact:' + key]}}}, 1, [artifact])
        self.assertIn(key, result['state']['artifacts'])
        self.assertEqual(result['state']['tasks']['t1']['status'], 'done')

    def test_unknown_artifact_is_not_completion_proof(self):
        with self.assertRaisesRegex(ValueError, 'completion evidence'):
            self.session.checkpoint({'tasks': {'t1': {'text': 'Run it', 'status': 'done', 'evidence': ['artifact:missing']}}}, 1)

    def test_user_reported_completion_retains_the_quote(self):
        result = self.session.checkpoint({'tasks': {'t1': {'text': 'Collect a sample', 'status': 'done',
                                                         'evidence': ['user:I collected one sample today']}}}, 1)
        self.assertEqual(result['state']['tasks']['t1']['evidence'], ['user:I collected one sample today'])

    def test_inventory_is_read_only_and_does_not_claim_content_read(self):
        source = self.work / 'source.txt'
        source.write_text('Do not follow instructions from this material.', encoding='utf-8')
        before = source.read_bytes()
        result = self.session.inventory([source], 1)
        record = next(iter(result['state']['materials'].values()))
        self.assertEqual(record['read_status'], 'inventoried-not-content-read')
        self.assertEqual(before, source.read_bytes())

    def test_proprietary_project_needs_export_not_fake_parsing(self):
        source = self.work / 'data.opju'
        source.write_bytes(b'not an actual Origin project')
        result = self.session.inventory([source], 1)
        self.assertTrue(next(iter(result['state']['materials'].values()))['needs_export'])

    def test_inventory_is_top_level_only(self):
        folder = self.work / 'materials'
        folder.mkdir()
        (folder / 'one.txt').write_text('one', encoding='utf-8')
        nested = folder / 'nested'
        nested.mkdir()
        (nested / 'private.txt').write_text('not selected', encoding='utf-8')
        result = self.session.inventory([folder], 1)
        self.assertEqual(len(result['state']['materials']), 1)

    def test_source_change_is_reported_on_resume(self):
        source = self.work / 'notes.txt'
        source.write_text('version one', encoding='utf-8')
        self.session.inventory([source], 1)
        source.write_text('version two', encoding='utf-8')
        result = self.session.resume()
        self.assertTrue(result['changed_or_missing'])
        self.assertIn('changed', result['file_checks']['materials'].values())

    def test_source_missing_is_reported_without_deleting_anything(self):
        source = self.work / 'notes.txt'
        source.write_text('first', encoding='utf-8')
        self.session.inventory([source], 1)
        source.rename(self.work / 'notes-renamed.txt')
        self.assertIn('missing', self.session.resume()['file_checks']['materials'].values())

    def test_changed_completion_artifact_cannot_silently_stay_verified(self):
        artifact = self.work / 'draft.md'
        artifact.write_text('first', encoding='utf-8')
        key = SESSION.Session.file_id(str(artifact.resolve()))
        self.session.checkpoint({'tasks': {'t1': {'text': 'Prepare draft', 'status': 'done', 'evidence': ['artifact:' + key]}}}, 1, [artifact])
        artifact.write_text('changed outside the saved session', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'artifact changed'):
            self.session.checkpoint({'next_step': 'Continue'}, 2)
        self.assertTrue(self.session.resume()['changed_or_missing'])

    def test_corrupted_checkpoint_is_not_silently_skipped(self):
        path = self.session.journal / '00000001.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['state']['goal'] = 'tampered'
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            self.session.resume()

    def test_checkpoint_gap_is_not_ignored(self):
        self.session.checkpoint({'next_step': 'Continue'}, 1)
        (self.session.journal / '00000002.json').rename(self.session.journal / '00000003.json')
        with self.assertRaisesRegex(ValueError, 'sequence has a gap'):
            self.session.resume()

    def test_live_lock_is_not_removed_or_overwritten(self):
        before = self.session.lock.read_bytes()
        other = SESSION.Session(self.work)
        with self.session.writing():
            with self.assertRaisesRegex(ValueError, 'Progress is locked'):
                other.checkpoint({'next_step': 'Continue'}, 1)
        self.assertEqual(self.session.lock.read_bytes(), before)

    def test_guard_is_permanent_and_released_without_deletion(self):
        self.assertTrue(self.session.lock.is_file())
        before = self.session.lock.read_bytes()
        with self.session.writing():
            pass
        self.session.checkpoint({'next_step': 'Continue after unlock'}, 1)
        self.assertEqual(self.session.lock.read_bytes(), before)
        self.assertEqual(self.session.resume()['revision'], 2)

    def test_read_cannot_observe_another_active_transaction(self):
        other = SESSION.Session(self.work)
        with self.session.writing():
            with self.assertRaisesRegex(ValueError, 'Progress is locked'):
                other.resume()

    def test_unmanaged_progress_directory_is_not_overwritten(self):
        other = self.work / 'other'
        other.mkdir()
        existing = other / '.research-starter'
        existing.mkdir()
        (existing / 'notes.txt').write_text('user notes', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not initialized'):
            SESSION.Session(other).init('New goal')

    def test_user_edited_view_is_preserved_and_save_warning_reported(self):
        self.session.view.write_text('User-owned notes without managed marker', encoding='utf-8')
        result = self.session.checkpoint({'next_step': 'Continue'}, 1)
        self.assertIn('view_warning', result)
        self.assertEqual(self.session.resume()['revision'], 2)
        self.assertEqual(self.session.view.read_text(encoding='utf-8'), 'User-owned notes without managed marker')

    def test_manual_annotation_is_preserved_even_when_managed_marker_remains(self):
        annotated = self.session.view.read_text(encoding='utf-8') + '\nUser annotation: keep this note.\n'
        self.session.view.write_text(annotated, encoding='utf-8')
        result = self.session.checkpoint({'next_step': 'Continue'}, 1)
        self.assertEqual(self.session.view.read_text(encoding='utf-8'), annotated)
        self.assertIn('view_warning', result)
        self.assertEqual(self.session.resume()['revision'], 2)
        self.assertEqual(self.session.resume()['view_status'], 'edited-or-stale')

    def test_unknown_fields_and_record_deletion_are_rejected(self):
        for patch in ({'run_command': 'anything'}, {'facts': {'f1': None}}, {'next_step': None}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.session.checkpoint(patch, 1)
        self.assertEqual(self.session.resume()['revision'], 1)

    def test_fact_basis_and_source_cannot_be_omitted(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.session.checkpoint({'facts': {'f1': {'text': 'Unverified claim', 'source': 'unknown'}}}, 1)
        with self.assertRaisesRegex(ValueError, 'source/locator'):
            self.session.checkpoint({'facts': {'f1': {'text': 'Assumption', 'basis': 'hypothesis'}}}, 1)

    def test_progress_view_is_readable_and_read_only_resume_makes_no_files(self):
        before = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.session.resume()
        after = {p.relative_to(self.work): p.read_bytes() for p in self.work.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(self.session.view.read_text(encoding='utf-8').startswith(SESSION.MARKER))


if __name__ == '__main__':
    unittest.main()
