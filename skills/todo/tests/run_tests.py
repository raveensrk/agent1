#!/usr/bin/env python3
"""Tests for the todo skill: the helper script, and the org behaviors it documents.

Run with:

    python3 tests/run_tests.py

Integration tests skip when the org CLI is missing; the linter tests skip when
Main_Quest's lint_board.sh is missing. The org-behavior tests pin the facts the
skill states, so a change in org fails loudly and the skill text gets revisited.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "todo_agent.py"
LINTER = Path.home() / "repos" / "Main_Quest" / "scripts" / "lint_board.sh"
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))

import todo_agent as agent  # noqa: E402

try:
    ORG = agent.org_bin()
except Exception:  # noqa: BLE001 - any failure means no CLI to test against
    ORG = None

SCAFFOLD = (
    "#+TITLE: TODO\n"
    "#+TODO: TODO IN_PROGRESS OPTIONAL LATER | DONE OBSOLETE\n"
    "#+STARTUP: logdone\n\n* Tasks\n"
)


def make_config(directory: Path, *, review_actor: str | None = "reviewer") -> Path:
    lines = [f'default_dirs = ["{directory}"]', 'ignore = ["node_modules"]']
    if review_actor:
        lines.append(f'review_actor = "{review_actor}"')
    path = directory / "todo_skill.toml"
    path.write_text("\n".join(lines) + "\n")
    return path


def board(directory: Path, body: str = "") -> Path:
    path = directory / "todo.org"
    path.write_text(SCAFFOLD + body)
    return path


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class Harness(unittest.TestCase):
    """A temp dir, a temp config, and helpers to run the script and org."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="todo-skill-test-")
        self.tmp = Path(self.tmpdir.name)
        self.addCleanup(self.tmpdir.cleanup)
        self.config = make_config(self.tmp)
        self.env = os.environ.copy()
        self.env.update(
            TODO_SKILL_CONFIG=str(self.config),
            ORG_BIN=ORG or "",
            ORG_ACTOR="tester",
        )

    def agent(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd or self.tmp,
            capture_output=True,
            text=True,
            env=self.env,
        )

    def agent_json(self, *args: str, cwd: Path | None = None):
        done = self.agent("--json", *args, cwd=cwd)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def org(self, directory: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [ORG, "-d", str(directory), "-f", "json", *args],
            capture_output=True,
            text=True,
        )


class TestPureHelpers(unittest.TestCase):
    def test_first_state_reads_the_files_own_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "todo.org"
            path.write_text("#+TODO: OPEN DOING | CLOSED\n")
            self.assertEqual(agent.first_state(path), "OPEN")
            path.write_text(SCAFFOLD)
            self.assertEqual(agent.first_state(path), "TODO")
            path.write_text("#+TITLE: none\n")
            with self.assertRaises(agent.Fail):
                agent.first_state(path)

    def test_is_ignored_matches_the_config_semantics(self) -> None:
        self.assertTrue(agent.is_ignored(Path("/a/node_modules/x.org"), ["node_modules"]))
        self.assertTrue(agent.is_ignored(Path("/a/repos/notes/z.org"), ["repos/notes"]))
        self.assertTrue(agent.is_ignored(Path("/a/b/statement_tracker.md"), ["**/statement_tracker.md"]))
        self.assertTrue(agent.is_ignored(Path("/private/tmp/keep/x.org"), ["/private/tmp/keep"]))
        self.assertFalse(agent.is_ignored(Path("/a/b/c.org"), ["node_modules", "repos/notes"]))

    def test_board_for_prefers_the_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            nested = root / "src" / "deep"
            nested.mkdir(parents=True)
            self.assertEqual(agent.board_for(nested).resolve(), (root / "todo.org").resolve())

    def test_board_for_walks_up_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "todo.org").write_text(SCAFFOLD)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(agent.board_for(nested), root / "todo.org")

    def test_board_for_falls_back_to_the_start_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            start = Path(tmp) / "nowhere"
            start.mkdir()
            self.assertEqual(agent.board_for(start), start / "todo.org")

    def test_split_and_join_heading(self) -> None:
        states = ["TODO", "DONE"]
        self.assertEqual(
            agent.split_heading("** TODO [#A] Pay rent :finance:home:\n", states),
            ("**", "TODO", "[#A]", "Pay rent", ":finance:home:"),
        )
        self.assertEqual(
            agent.split_heading("*** DONE Ship it\n", states),
            ("***", "DONE", "", "Ship it", ""),
        )
        self.assertEqual(
            agent.join_heading("**", "TODO", "[#B]", "Pay rent", ":home:"),
            "** TODO [#B] Pay rent :home:",
        )
        with self.assertRaises(agent.Fail):
            agent.split_heading("* Tasks\n", states)

    def test_load_config_expands_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            old = os.environ.get("TODO_SKILL_CONFIG")
            os.environ["TODO_SKILL_CONFIG"] = str(config)
            try:
                loaded = agent.load_config()
            finally:
                if old is None:
                    os.environ.pop("TODO_SKILL_CONFIG", None)
                else:
                    os.environ["TODO_SKILL_CONFIG"] = old
            self.assertEqual(loaded["review_actor"], "reviewer")
            self.assertEqual(loaded["ignore"], ["node_modules"])
            self.assertEqual(loaded["default_dirs"], [Path(tmp)])


@unittest.skipUnless(ORG, "org CLI not found")
class TestVerbs(Harness):
    def test_create_writes_a_valid_task(self) -> None:
        result = self.agent_json(
            "create", "Pay rent", "--deadline", "2026-11-05", "--tag", "finance", "--priority", "A"
        )
        text = Path(result["file"]).read_text()
        self.assertIn("** TODO [#A] Pay rent :finance:", text)
        self.assertIn("DEADLINE: <2026-11-05 Thu>", text)
        self.assertRegex(text, r":ID: [0-9a-f-]{36}")
        self.assertIn(":CREATED: ", text)
        self.assertEqual(result["state"], "TODO")

    def test_create_scaffolds_a_missing_board(self) -> None:
        target = self.tmp / "fresh" / "todo.org"
        result = self.agent_json("create", "First", "--file", str(target))
        text = Path(result["file"]).read_text()
        self.assertTrue(text.startswith("#+TITLE: TODO"))
        self.assertIn("* Tasks", text)
        self.assertIn("** TODO First", text)

    def test_create_refuses_a_file_with_no_states(self) -> None:
        path = self.tmp / "weird.org"
        path.write_text("#+TITLE: nope\n")
        done = self.agent("create", "X", "--file", str(path))
        self.assertEqual(done.returncode, 1)
        self.assertIn("no #+TODO:", done.stderr)

    def test_read_returns_tasks_and_drops_ignored_paths(self) -> None:
        self.agent_json("create", "Visible")
        write_file(self.tmp / "node_modules" / "hidden.org", SCAFFOLD + "** TODO Hidden\n")
        titles = [item["title"] for item in self.agent_json("read")]
        self.assertIn("Visible", titles)
        self.assertNotIn("Hidden", titles)

    def test_read_sees_the_board_the_cwd_is_on(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        self.config.write_text(f'default_dirs = ["{elsewhere}"]\nignore = []\n')
        self.agent_json("create", "On my board")
        titles = [item["title"] for item in self.agent_json("read")]
        self.assertEqual(titles, ["On my board"])

    def test_read_does_not_double_count_the_cwd_board(self) -> None:
        self.agent_json("create", "Once only")
        titles = [item["title"] for item in self.agent_json("read")]
        self.assertEqual(titles.count("Once only"), 1)

    def test_update_by_id(self) -> None:
        created = self.agent_json("create", "Edit me")
        ref = f"id:{created['id']}"
        self.agent_json("set-state", ref, "IN_PROGRESS")
        self.agent_json("set-deadline", ref, "2026-12-01")
        self.agent_json("add-tag", ref, "home")
        self.agent_json("append", ref, "note from the agent")
        text = Path(created["file"]).read_text()
        self.assertIn("** IN_PROGRESS Edit me :home:", text)
        self.assertIn("DEADLINE: <2026-12-01 Tue>", text)
        self.assertIn("note from the agent", text)
        self.agent_json("remove-tag", ref, "home")
        self.assertNotIn(":home:", Path(created["file"]).read_text())

    def test_obsolete_and_archive(self) -> None:
        created = self.agent_json("create", "Old work")
        ref = f"id:{created['id']}"
        self.agent_json("obsolete", ref)
        self.assertIn("** OBSOLETE Old work", Path(created["file"]).read_text())
        self.agent_json("archive", ref)
        board_text = Path(created["file"]).read_text()
        archive = Path(created["file"] + "_archive")
        self.assertNotIn("Old work", board_text)
        self.assertTrue(archive.is_file())
        self.assertIn("Old work", archive.read_text())

    def test_rename_changes_only_the_title(self) -> None:
        self.agent_json("create", "First task")
        second = self.agent_json("create", "Second task", "--priority", "B", "--tag", "keep")
        board_path = Path(second["file"])
        before = board_path.read_text()
        result = self.agent_json("rename", f"id:{second['id']}", "Second task renamed")
        after = board_path.read_text()
        self.assertEqual(result["title"], "Second task renamed")
        self.assertIn("** TODO [#B] Second task renamed :keep:", after)
        self.assertIn(f":ID: {second['id']}", after)
        self.assertIn("** TODO First task", after)
        changed = [line for line in before.splitlines() if line not in after.splitlines()]
        self.assertEqual(changed, ["** TODO [#B] Second task :keep:"])

    def test_rename_refuses_an_unknown_task(self) -> None:
        self.agent_json("create", "Real task")
        done = self.agent("rename", "id:00000000-0000-4000-8000-000000000000", "Nope")
        self.assertEqual(done.returncode, 1)
        self.assertIn("not on", done.stderr)

    def test_capture_appends_a_plain_heading(self) -> None:
        self.agent_json("capture", "Look into routing")
        inbox = self.tmp / "inbox.org"
        text = inbox.read_text()
        self.assertEqual(text, "#+TITLE: INBOX\n* Look into routing\n")

    def test_resolve_reports_the_git_root_board(self) -> None:
        subprocess.run(["git", "-C", str(self.tmp), "init", "-q"], check=True)
        nested = self.tmp / "src"
        nested.mkdir()
        resolved = self.agent_json("resolve", "--dir", str(nested))
        self.assertEqual(resolved["file"], str((self.tmp / "todo.org").resolve()))
        self.assertFalse(resolved["exists"])
        self.agent_json("create", "Made it")
        self.assertTrue(self.agent_json("resolve", "--dir", str(nested))["exists"])


@unittest.skipUnless(ORG, "org CLI not found")
class TestLoop(Harness):
    def submitted(self) -> dict:
        created = self.agent_json("create", "Loop task")
        ref = f"id:{created['id']}"
        claim = self.agent_json("claim", ref)
        self.agent_json(
            "submit", ref, "--claim-id", claim["claim_id"], "--evidence", "did the work"
        )
        return {"ref": ref, "claim": claim, "created": created}

    def test_claim_submit_approve(self) -> None:
        state = self.submitted()
        awaiting = self.agent_json("review")
        self.assertEqual([t["title"] for t in awaiting], ["Loop task"])
        result = self.agent_json("approve", state["ref"], "--evidence", "looks right")
        self.assertEqual(result["state"], "DONE")
        self.assertEqual(result["reviewed_by"], "reviewer")
        text = Path(state["created"]["file"]).read_text()
        self.assertIn("** DONE Loop task", text)
        self.assertIn("CLOSED: [", text)
        self.assertIn(":TASK_REVIEWED_BY: reviewer", text)

    def test_reviewer_may_not_be_the_agent(self) -> None:
        state = self.submitted()
        done = self.agent(
            "approve", state["ref"], "--evidence", "self", "--actor", "tester"
        )
        self.assertEqual(done.returncode, 1)
        self.assertIn("must differ", done.stderr)

    def test_approve_requires_a_configured_reviewer(self) -> None:
        state = self.submitted()
        self.config.write_text(f'default_dirs = ["{self.tmp}"]\n')
        done = self.agent("approve", state["ref"], "--evidence", "x")
        self.assertEqual(done.returncode, 1)
        self.assertIn("review_actor", done.stderr)

    def test_claim_requires_an_actor(self) -> None:
        created = self.agent_json("create", "Need actor")
        env = dict(self.env)
        env.pop("ORG_ACTOR", None)
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "claim", f"id:{created['id']}"],
            cwd=self.tmp,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(done.returncode, 1)
        self.assertIn("ORG_ACTOR", done.stderr)


@unittest.skipUnless(ORG, "org CLI not found")
class TestOrgBehavior(Harness):
    """Pin the org facts the skill states. A failure here means the skill text
    is stale, not that the code is broken."""

    def test_bare_add_lands_at_the_root(self) -> None:
        path = board(self.tmp)
        self.org(self.tmp, "add", str(path), "Bare")
        self.assertIn("\n* Bare\n", path.read_text())

    def test_dates_take_a_bare_date_only(self) -> None:
        path = board(self.tmp)
        for value in ("<2026-11-05 Thu>", "2026-11-05 09:00", "2026-11-05 +1m"):
            done = self.org(self.tmp, "add", str(path), "Date probe", "--deadline", value)
            payload = json.loads(done.stdout) if done.stdout.strip().startswith("{") else {}
            self.assertFalse(done.returncode == 0 and payload.get("ok"), value)

    def test_deadline_deletes_a_repeater(self) -> None:
        path = board(
            self.tmp,
            "** TODO Rent\nDEADLINE: <2026-11-05 Thu +1m>\n"
            ":PROPERTIES:\n:ID: aaaa1111-2222-4333-8444-555566667777\n:END:\n",
        )
        self.org(self.tmp, "deadline", str(path), "id:aaaa1111-2222-4333-8444-555566667777", "2026-12-05")
        self.assertIn("DEADLINE: <2026-12-05 Sat>", path.read_text())
        self.assertNotIn("+1m", path.read_text())

    def test_plain_verbs_ignore_a_wrong_revision(self) -> None:
        board(self.tmp)
        created = self.agent_json("create", "Ignore hash")
        done = self.org(
            self.tmp,
            "todo",
            "set",
            created["file"],
            f"id:{created['id']}",
            "IN_PROGRESS",
            "--expected-revision",
            "WRONG",
        )
        self.assertEqual(done.returncode, 0)
        self.assertIn("** IN_PROGRESS Ignore hash", (self.tmp / "todo.org").read_text())

    def test_claim_rejects_a_wrong_revision(self) -> None:
        board(self.tmp)
        created = self.agent_json("create", "Hash guard")
        done = self.org(
            self.tmp,
            "task",
            "claim",
            f"id:{created['id']}",
            "--actor",
            "tester",
            "--claim-id",
            "11111111-1111-4111-8111-111111111111",
            "--expected-revision",
            "WRONG",
        )
        payload = json.loads(done.stdout)
        self.assertFalse(payload["ok"])

    def test_task_create_writes_tasks_org(self) -> None:
        self.org(self.tmp, "task", "create", "Coordination probe", "--actor", "tester")
        self.assertTrue((self.tmp / "tasks.org").is_file())
        self.assertFalse((self.tmp / "todo.org").exists())

    def test_unclaimed_task_cannot_be_shown(self) -> None:
        board(self.tmp, "** TODO No id\nplain text\n")
        done = self.org(self.tmp, "task", "claim", "No id", "--actor", "tester", "--claim-id", "x")
        self.assertNotEqual(done.returncode, 0)


@unittest.skipUnless(LINTER.is_file(), "lint_board.sh not found")
class TestLinter(unittest.TestCase):
    """Pin what the shipped linter catches, which is less than the format
    forbids. The skill must not claim more than the tool does."""

    def lint(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "todo.org"
            path.write_text(text)
            done = subprocess.run([str(LINTER), str(path)], capture_output=True, text=True)
            return done.stdout + done.stderr

    def test_missing_id_is_caught(self) -> None:
        self.assertIn("missing_id", self.lint(SCAFFOLD + "** TODO No id\n"))

    def test_empty_title_is_caught(self) -> None:
        report = self.lint(
            SCAFFOLD + "** TODO \n:PROPERTIES:\n:ID: bbbb1111-2222-4333-8444-555566667777\n:END:\n"
        )
        self.assertIn("unknown_state", report)

    def test_bad_tags_are_tolerated(self) -> None:
        report = self.lint(
            SCAFFOLD + "** TODO Tagged :Bad-Tag:UPPER:\n"
            ":PROPERTIES:\n:ID: cccc1111-2222-4333-8444-555566667777\n:END:\n"
        )
        self.assertIn("clean", report)

    def test_near_miss_state_container_is_tolerated(self) -> None:
        report = self.lint(
            SCAFFOLD + "* done x\n"
            "** TODO Real\n:PROPERTIES:\n:ID: ffff1111-2222-4333-8444-555566667777\n:END:\n"
        )
        self.assertIn("clean", report)

    def test_todo_colon_container_is_tolerated(self) -> None:
        report = self.lint(
            SCAFFOLD + "* TODO: To read\n"
            "** TODO Real\n:PROPERTIES:\n:ID: eeee1111-2222-4333-8444-555566667777\n:END:\n"
        )
        self.assertIn("clean", report)

    def test_a_task_title_may_start_with_todo_colon(self) -> None:
        report = self.lint(
            SCAFFOLD + "** TODO TODO: probe\n"
            ":PROPERTIES:\n:ID: aaaa1111-2222-4333-8444-555566667777\n:END:\n"
        )
        self.assertIn("clean", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
