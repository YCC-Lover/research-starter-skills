"""Synthetic native CLI tests; retain all fixtures under an explicit D/E root.

Set RSK_INQUIRY_TEST_ROOT or TEMP/TMP/TMPDIR and PYTHONDONTWRITEBYTECODE=1.
No models, networks, cleanup, or production passports are used.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "skills/research-starter-paper/resources/research-engine"
SCRIPT = ENGINE / "scripts/inquiry_branch_ledger.py"
PROFILE = ENGINE / "shared/research_workflow_profiles/field_general.json"
PROJECT = "synthetic-inquiry-test"

# This subprocess exercises the real argument parser and main, with failures
# injected only in the test process. os._exit also tests OS lock release.
FAULT_RUNNER = r'''
import os
from pathlib import Path
import sys
sys.path.insert(0, sys.argv.pop(1))
import inquiry_branch_ledger as ledger
fault = sys.argv.pop(1)
def audit(event, args):
    if event in {"os.remove", "os.rmdir", "shutil.rmtree", "socket.connect"}:
        raise AssertionError("forbidden test operation: " + event)
sys.addaudithook(audit)
if fault.startswith("crash:"):
    original = ledger.commit_ledger_transaction
    def commit(*args, **kwargs):
        def crash(phase):
            if phase == fault.split(":", 1)[1]:
                os._exit(73)
        kwargs["crash_hook"] = crash
        return original(*args, **kwargs)
    ledger.commit_ledger_transaction = commit
elif fault.startswith("partial:"):
    original = ledger._write_exclusive_durable
    def write(path, data, **kwargs):
        if path.name.endswith(fault.split(":", 1)[1]):
            actual_write = os.write
            calls = 0
            def partial(fd, raw):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return actual_write(fd, raw[:19])
                raise OSError("synthetic partial write failure")
            os.write = partial
            try:
                return original(path, data, **kwargs)
            finally:
                os.write = actual_write
        return original(path, data, **kwargs)
    ledger._write_exclusive_durable = write
elif fault == "retention-failure":
    original = ledger._move_durable
    def move(source, target, **kwargs):
        if ".retained-" in target.name:
            raise OSError("synthetic retention failure")
        return original(source, target, **kwargs)
    ledger._move_durable = move
sys.exit(ledger.main(sys.argv[1:]))
'''

LOCK_HOLDER = r'''
import os
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import file_lock
fd = os.open(sys.argv[2], os.O_RDWR | os.O_CREAT, 0o600)
try:
    file_lock.acquire(fd, exclusive=True, timeout=0)
    print(file_lock.BACKEND, flush=True)
    sys.stdin.readline()
finally:
    file_lock.release(fd)
    os.close(fd)
'''


class InquiryLedgerCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        explicit = next((os.environ[name] for name in (
            "RSK_INQUIRY_TEST_ROOT", "TEMP", "TMP", "TMPDIR"
        ) if os.environ.get(name)), None)
        if not explicit:
            raise RuntimeError("Set an explicit retained inquiry test work directory")
        base = Path(explicit)
        if not base.is_absolute() or not base.is_dir():
            raise RuntimeError("Inquiry test root must be an existing absolute directory")
        if os.name == "nt" and (
            base.resolve().drive.upper() not in {"D:", "E:"}
            or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1"
        ):
            raise RuntimeError("Use a D:/E: root and PYTHONDONTWRITEBYTECODE=1")
        cls.retained = Path(tempfile.mkdtemp(prefix="inquiry-ledger-", dir=base))
        print(f"\nRetained inquiry CLI fixtures: {cls.retained}", flush=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="case-", dir=self.retained))
        self.workspace = self.work / "workspace \u6d4b\u8bd5"
        self.workspace.mkdir()
        self.passport = self.workspace / "passport \u00e9.yaml"
        self.original_passport = (
            "# Synthetic passport; no real research or consent.\r\n"
            "project_ref: synthetic-inquiry-test\r\n"
            "note: 'Keep quotes and comment \u6d4b\u8bd5'\r\n"
        ).encode("utf-8")
        self.passport.write_bytes(self.original_passport)
        self.target = self.workspace / "ledger \u00e9.json"
        self.profile = self.work / "profile.json"
        self.profile.write_bytes(PROFILE.read_bytes())
        self.env = dict(os.environ)
        self.env.update(TEMP=str(self.work), TMP=str(self.work), TMPDIR=str(self.work),
                        PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        self.env.pop("ARS_INQUIRY_LEDGER", None)
        self.counter = 0

    def cli(self, *args, fault=None, expected=0, env=None):
        command = [sys.executable, "-B"]
        if fault:
            command += ["-c", FAULT_RUNNER, str(SCRIPT.parent), fault]
        else:
            command += [str(SCRIPT)]
        result = subprocess.run(
            command + [str(arg) for arg in args], cwd=self.work,
            env=env or self.env, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, expected, result.stderr.decode("utf-8"))
        return result

    def save(self, raw, suffix="json"):
        self.counter += 1
        path = self.work / f"input-{self.counter}.{suffix}"
        path.write_bytes(raw)
        return path

    def event(self, kind="branch_created", branch="first", actor="author", payload=None):
        if payload is None:
            payload = {
                "parent_id": None, "statement": f"Synthetic {branch} question",
                "assumptions": [], "evidence_sought": [], "reopen_conditions": [],
                "downstream_refs": [f"draft:{branch}"],
            }
        return self.save(json.dumps({
            "recorded_at": "2026-10-21T00:00:00Z", "actor": actor,
            "kind": kind, "branch_id": branch, "payload": payload,
        }).encode())

    def init(self):
        return self.save(self.cli(
            "init", "--profile", self.profile, "--project-ref", PROJECT
        ).stdout)

    def append(self, ledger, event, **kwargs):
        return self.cli("append", ledger, "--event", event, "--profile", self.profile,
                        "--project-ref", PROJECT, **kwargs)

    def candidate(self):
        ledger = self.init()
        for branch in ("first", "second"):
            ledger = self.save(self.append(ledger, self.event(branch=branch)).stdout)
        return ledger

    def commit(self, candidate, **kwargs):
        return self.cli(
            "commit", "--passport", self.passport, "--workspace-root", self.workspace,
            "--ledger-path", self.target.name, "--ledger", candidate,
            "--profile", self.profile, "--project-ref", PROJECT, **kwargs,
        )

    def load(self, *extra, **kwargs):
        return self.cli(
            "load-bound", "--passport", self.passport, "--workspace-root", self.workspace,
            "--profile", self.profile, "--project-ref", PROJECT, *extra, **kwargs,
        )

    def sidecar(self, suffix):
        return self.workspace / f".{self.passport.name}.inquiry-ledger.{suffix}"

    def archives(self, suffix):
        return list(self.workspace.glob(self.sidecar(suffix).name + ".retained-*"))

    def updated_candidate(self):
        self.commit(self.candidate())
        return self.save(self.append(self.target, self.event(
            kind="branch_parked", payload={"reason": "Synthetic author decision"}
        )).stdout)

    def assert_binding(self, expected_count):
        loaded = json.loads(self.load().stdout)
        self.assertEqual(loaded["state"], "bound")
        self.assertEqual(loaded["projection"]["event_count"], expected_count)
        self.assertEqual(loaded["pointer"]["content_sha256"],
                         hashlib.sha256(self.target.read_bytes()).hexdigest())
        return loaded

    def test_init_append_commit_replay_checkpoint_and_exact_bytes(self):
        candidate = self.candidate()
        result = self.commit(candidate)
        self.assertEqual(self.target.read_bytes(), candidate.read_bytes())
        loaded = self.assert_binding(2)
        self.assertEqual(json.loads(result.stdout), loaded["pointer"])
        self.assertEqual(loaded["ledger"]["schema_version"], "inquiry-branch-ledger/1.0")
        replay = self.cli("replay", self.target, "--profile", self.profile,
                          "--project-ref", PROJECT)
        self.assertEqual(json.loads(replay.stdout), loaded["projection"])
        args = [self.target, "--profile", self.profile, "--project-ref", PROJECT,
                "--moment", "design_freeze"]
        self.assertEqual(self.cli("checkpoint", *args).stdout, b"")
        summary = self.cli("checkpoint", *args, "--force").stdout
        self.assertIn(b"Inquiry branches", summary)
        self.assertIn(b"Synthetic first question", summary)
        self.assertEqual(summary, self.cli("summary", *args, "--force").stdout)
        self.assertEqual(len(self.archives("transaction.json")), 1)
        journal = json.loads(self.archives("transaction.json")[0].read_bytes())
        self.assertEqual(journal["new_ledger_sha256"], loaded["pointer"]["content_sha256"])
        self.assertEqual(journal["new_passport_sha256"],
                         hashlib.sha256(self.passport.read_bytes()).hexdigest())
        self.assertEqual(journal["old_passport_sha256"],
                         hashlib.sha256(self.original_passport).hexdigest())
        self.assertIn(b"# Synthetic passport", self.passport.read_bytes())
        self.assertIn("'Keep quotes and comment \u6d4b\u8bd5'".encode(), self.passport.read_bytes())
        if os.name == "nt":
            self.assertIn(b"power-loss durability is not certified", result.stderr)

    def test_zero_and_one_branch_cannot_be_published(self):
        candidate = self.init()
        for count in (0, 1):
            with self.subTest(count=count):
                result = self.commit(candidate, expected=2)
                self.assertIn(b"at least two introduced branches", result.stderr)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.passport.read_bytes(), self.original_passport)
                if count == 0:
                    candidate = self.save(self.append(candidate, self.event()).stdout)

    def test_author_decisions_and_adoption_are_not_fabricated(self):
        empty = self.init()
        bad_actor = self.append(empty, self.event(actor="ai"), expected=2)
        self.assertIn(b"must equal author", bad_actor.stderr)
        surfaced = self.save(self.append(empty, self.event(
            kind="facet_surfaced", actor="ai",
            payload={"parent_id": None, "surfaced_text": "Synthetic AI suggestion"}
        )).stdout)
        rejected = self.append(surfaced, self.event(kind="branch_adopted", payload={
            "source_event_id": 1, "surfaced_text": "Synthetic AI suggestion",
            "author_formulation": "ok",
        }), expected=2)
        self.assertIn(b"not an adoption formulation", rejected.stderr)
        replay = self.cli("replay", surfaced, "--profile", self.profile, "--allow-in-memory")
        self.assertEqual(json.loads(replay.stdout)["branches"][0]["provenance"],
                         "ai_surfaced_facet")
        self.assertFalse(self.target.exists())

    def test_reopen_appends_stale_marks_and_requires_author_reconfirmation(self):
        candidate = self.candidate()
        parked = self.save(self.append(candidate, self.event(
            kind="branch_parked", payload={"reason": "Synthetic author decision"}
        )).stdout)
        reopened = self.save(self.append(parked, self.event(
            kind="branch_reopened", payload={"reason": "Synthetic author reopened"}
        )).stdout)
        events = json.loads(reopened.read_bytes())["events"]
        self.assertEqual([e["kind"] for e in events[-2:]],
                         ["branch_reopened", "artifact_marked_stale"])
        self.assertEqual(events[-1]["actor"], "system")
        payload = {"artifact_ref": "draft:first", "resolves_stale_event_id": 5,
                   "note": "Synthetic author inspected changed artifact"}
        self.append(reopened, self.event(kind="artifact_reconfirmed", branch=None,
                                        actor="ai", payload=payload), expected=2)
        confirmed = self.save(self.append(reopened, self.event(
            kind="artifact_reconfirmed", branch=None, payload=payload
        )).stdout)
        self.commit(confirmed)
        self.assert_binding(6)

    def test_append_only_and_project_binding_remain_enforced(self):
        candidate = self.candidate()
        self.commit(candidate)
        result = self.commit(candidate, expected=2)
        self.assertIn(b"must append at least one", result.stderr)
        result = self.load("--project-ref", "other-synthetic-project", expected=2)
        self.assertIn(b"LEDGER-BINDING-BROKEN", result.stderr)
        changed = json.loads(candidate.read_bytes())
        changed["events"][0]["payload"]["statement"] = "Rewritten history"
        changed = self.save(json.dumps(changed).encode())
        self.cli("replay", changed, "--profile", self.profile, expected=2)
        self.assert_binding(2)

    def test_process_crashes_at_every_transaction_boundary_recover(self):
        for phase in ("temps_durable", "journal_durable", "ledger_published",
                      "passport_published", "journal_cleared"):
            with self.subTest(phase=phase):
                self.setUp()
                candidate = self.updated_candidate()
                self.commit(candidate, fault="crash:" + phase, expected=73)
                if phase == "temps_durable":
                    self.assert_binding(2)
                    self.assertTrue(self.sidecar("ledger.tmp").exists())
                    self.commit(candidate)
                    self.assertTrue(self.archives("ledger.tmp"))
                    self.assertTrue(self.archives("passport.tmp"))
                elif phase != "journal_cleared":
                    failed = self.load("--no-recover", expected=2)
                    self.assertIn(b"recovery disabled", failed.stderr)
                self.assert_binding(3)
                self.assertFalse(self.sidecar("transaction.json").exists())
                self.assertEqual(len(self.archives("transaction.json")), 2)
                self.assert_binding(3)  # Recovery is idempotent.

    def test_initial_publication_can_recover_without_old_ledger(self):
        candidate = self.candidate()
        self.commit(candidate, fault="crash:journal_durable", expected=73)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.passport.read_bytes(), self.original_passport)
        self.assert_binding(2)

    def test_partial_scratch_writes_are_retained_and_retry_archives_them(self):
        for suffix in ("ledger.tmp", "passport.tmp", "transaction.tmp"):
            with self.subTest(suffix=suffix):
                self.setUp()
                candidate = self.candidate()
                result = self.commit(candidate, fault="partial:" + suffix, expected=2)
                self.assertIn(b"synthetic partial write failure", result.stderr)
                partial = self.sidecar(suffix).read_bytes()
                self.assertEqual(len(partial), 19)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.passport.read_bytes(), self.original_passport)
                self.commit(candidate, fault="no-deletion-guard")
                self.assertEqual(self.archives(suffix)[0].read_bytes(), partial)
                self.assert_binding(2)

    def test_retention_failure_is_reported_and_keeps_recovery_journal(self):
        candidate = self.candidate()
        result = self.commit(candidate, fault="retention-failure", expected=2)
        self.assertIn(b"synthetic retention failure", result.stderr)
        self.assertTrue(self.sidecar("transaction.json").exists())
        self.assert_binding(2)
        self.assertEqual(len(self.archives("transaction.json")), 1)

    def test_tampered_staging_is_rejected_before_either_file_changes(self):
        candidate = self.updated_candidate()
        old_pair = (self.target.read_bytes(), self.passport.read_bytes())
        self.commit(candidate, fault="crash:journal_durable", expected=73)
        staged = self.sidecar("ledger.tmp")
        staged.write_bytes(staged.read_bytes() + b" ")
        result = self.load(expected=2)
        self.assertIn(b"complete new byte image", result.stderr)
        self.assertEqual((self.target.read_bytes(), self.passport.read_bytes()), old_pair)
        self.assertTrue(self.sidecar("transaction.json").exists())
        self.assertTrue(staged.read_bytes().endswith(b" "))

    def test_full_passport_cas_rejects_unrelated_concurrent_edit(self):
        candidate = self.updated_candidate()
        before = self.target.read_bytes()
        self.commit(candidate, fault="crash:journal_durable", expected=73)
        edited = self.passport.read_bytes() + b"# Synthetic external edit\n"
        self.passport.write_bytes(edited)
        result = self.load(expected=2)
        self.assertIn(b"neither the recorded old nor new byte generation", result.stderr)
        self.assertEqual(self.passport.read_bytes(), edited)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertTrue(self.sidecar("transaction.json").exists())

    def test_cross_process_lock_contention_and_release(self):
        candidate = self.candidate()
        lock = self.workspace / f".{self.passport.name}.lock"
        holder = subprocess.Popen(
            [sys.executable, "-B", "-c", LOCK_HOLDER, str(SCRIPT.parent), str(lock)],
            cwd=self.work, env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            backend = holder.stdout.readline().strip()
            self.assertEqual(backend, b"msvcrt" if os.name == "nt" else b"fcntl")
            result = self.load("--lock-timeout", "0.1", expected=2)
            self.assertIn(b"passport locked by another session", result.stderr)
            self.assertFalse(self.target.exists())
        finally:
            try:
                _, err = holder.communicate(b"release\n", timeout=10)
            except subprocess.TimeoutExpired:
                holder.kill()
                _, err = holder.communicate(timeout=10)
            self.assertEqual(holder.returncode, 0, err.decode())
        self.commit(candidate)
        self.assert_binding(2)

    def test_invalid_lock_timeout_fails_without_mutating_passport(self):
        for value in ("nan", "inf", "-1", "61"):
            with self.subTest(value=value):
                result = self.load("--lock-timeout", value, expected=2)
                self.assertIn(b"must be a finite number", result.stderr)
        self.assertEqual(self.passport.read_bytes(), self.original_passport)

    @unittest.skipUnless(os.name == "nt", "Native Windows filesystem semantics")
    def test_windows_rename_sharing_failure_is_visible_and_recoverable(self):
        candidate = self.candidate()
        with self.passport.open("rb"):
            result = self.commit(candidate, expected=2)
        self.assertIn(b"[inquiry_branch_ledger ERROR]", result.stderr)
        self.assertTrue(self.sidecar("transaction.json").exists())
        self.assertEqual(self.passport.read_bytes(), self.original_passport)
        self.assert_binding(2)

    @unittest.skipUnless(os.name == "nt", "Windows explicit local roots and path aliases")
    def test_windows_unsafe_roots_names_and_hardlinks_are_refused(self):
        for root in ("C:/", "D:relative", "//server/share", "//?/D:/work"):
            with self.subTest(root=root):
                self.load("--workspace-root", root, expected=2)
        candidate = self.candidate()
        for name in ("NUL", "ledger:stream", "ledger.", "ledger ", "../escape.json",
                     self.passport.name, self.sidecar("transaction.json").name):
            with self.subTest(name=name):
                self.cli("commit", "--passport", self.passport,
                         "--workspace-root", self.workspace, "--ledger-path", name,
                         "--ledger", candidate, "--profile", self.profile,
                         "--project-ref", PROJECT, expected=2)
        alias = self.workspace / "hardlinked-passport.yaml"
        os.link(self.passport, alias)
        result = self.load(expected=2)
        self.assertIn(b"hard-linked", result.stderr)
        self.assertEqual(self.passport.read_bytes(), self.original_passport)
        self.assertFalse(self.target.exists())

    def test_orphan_is_ignored_not_adopted_or_overwritten(self):
        candidate = self.candidate()
        self.target.write_bytes(candidate.read_bytes())
        result = json.loads(self.load("--orphan-candidate", self.target.name).stdout)
        self.assertEqual(result["state"], "orphan_ignored")
        self.commit(candidate, expected=2)
        self.assertEqual(self.target.read_bytes(), candidate.read_bytes())
        self.assertEqual(self.passport.read_bytes(), self.original_passport)


if __name__ == "__main__":
    unittest.main()
