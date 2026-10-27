"""The two automatic moments: session start, and the end-of-turn check."""

from __future__ import annotations

import json
import unittest

import os
import subprocess
import sys

from support import BIN, GuideTestCase

from own_guide import __version__, guide, hooks, state


class ToolLinkTest(GuideTestCase):
    """The tool is reached through a stable link, because its bare name isn't on PATH in the desktop app."""

    def test_note_gives_the_exact_command_and_the_link_runs(self) -> None:
        repo = self.make_repo("shop")
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        link = self.guides / ".bin" / "own-guide"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), BIN.resolve())
        self.assertIn(f"`python3 -I {link} <command>`", text)
        self.assertIn(f"`python3 -I {link} pause --here`", text)
        self.assertNotIn("run `own-guide", text)
        # A non-default guides folder: the note tells Claude to swap it into the skill's examples.
        self.assertIn(f"wherever the skill writes `{state.DEFAULT_TOOL_COMMAND} X`, run `python3 -I {link} X`", text)
        proc = subprocess.run([sys.executable, "-I", str(link), "--version"], capture_output=True, text=True)
        self.assertEqual(proc.stdout.strip(), f"own-guide {__version__}")

    def test_a_link_to_another_existing_copy_is_never_trusted(self) -> None:
        old = self.tmp / "old-version" / "bin" / "own-guide"
        old.parent.mkdir(parents=True)
        old.write_text("# an older copy still on disk\n", encoding="utf-8")
        link = self.guides / ".bin" / "own-guide"
        link.parent.mkdir(parents=True)
        os.symlink(old, link)
        self.assertEqual(state.tool_command(), f"python3 -I {BIN.resolve()}")

    def test_a_link_left_by_an_older_version_is_repointed(self) -> None:
        link = self.guides / ".bin" / "own-guide"
        link.parent.mkdir(parents=True)
        os.symlink("/nowhere/old-version/bin/own-guide", link)
        state.ensure_tool_link()
        self.assertEqual(link.resolve(), BIN.resolve())
        self.assertEqual(state.tool_command(), f"python3 -I {link}")

    def test_without_a_link_the_command_falls_back_to_the_launcher(self) -> None:
        self.assertEqual(state.tool_command(), f"python3 -I {BIN.resolve()}")


class SessionStartTest(GuideTestCase):
    def test_hands_claude_the_rules_and_the_guide_folder(self) -> None:
        repo = self.make_repo("shop", remote="git@github.com:me/shop.git")
        out = json.loads(hooks.session_start(self.payload(repo)))
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn(str(self.guides / "shop"), text)
        self.assertIn("## Inbox", text)
        self.assertIn("Where would you look first?", text)

    def test_silent_outside_git(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(hooks.session_start(self.payload(plain)), "")

    def test_switched_off_everywhere_means_nothing_at_all(self) -> None:
        repo = self.make_repo("shop")
        state.save_settings({"enabled": False})
        self.assertEqual(hooks.session_start(self.payload(repo)), "")
        self.assertEqual(hooks.stop_check(self.payload(repo)), "")

    def test_paused_here_is_one_line(self) -> None:
        repo = self.make_repo("shop")
        hooks.session_start(self.payload(repo))
        with state.edit_state("shop") as st:
            st["paused"] = True
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("paused", text)
        self.assertNotIn("## Inbox", text)

    def test_existing_project_without_a_guide_gets_the_first_map_offer(self) -> None:
        files = {f"src/m{i}.py": "x = 1\n" for i in range(20)}
        repo = self.make_repo("big", files=files)
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("first map", text)
        with state.edit_state("big") as st:
            st["first_map"] = {"answer": "never", "date": "2026-10-26"}
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("first map", text)

    def test_small_new_project_starts_empty_without_a_card(self) -> None:
        repo = self.make_repo("tiny")
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("starts with the first feature", text)
        self.assertNotIn("Today's card is due", text)

    def test_daily_card_only_once_a_day(self) -> None:
        repo = self.make_repo("shop")
        hooks.session_start(self.payload(repo))
        guide.init("shop", "shop", "2026-10-26")
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Today's card is due", text)  # tour offer once a guide exists
        with state.edit_state("shop") as st:
            st["daily_card"]["last_shown"] = "2026-10-26"
        text = json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Today's card is due", text)


class StopCheckTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", remote="git@github.com:me/shop.git")
        hooks.session_start(self.payload(self.repo))

    def stop(self, **extra: object) -> dict:
        out = hooks.stop_check(self.payload(self.repo, **extra))
        return json.loads(out) if out else {}

    def test_a_real_feature_asks_once_then_stays_quiet(self) -> None:
        self.write(self.repo, "report.py", self.lines(50))
        first = self.stop()
        self.assertEqual(first.get("decision"), "block")
        self.assertIn("report.py", first["reason"])
        self.assertIn("own", first["reason"])
        self.assertEqual(self.stop(), {})  # same changes: never nags

    def test_more_work_after_the_first_ask_asks_again(self) -> None:
        self.write(self.repo, "report.py", self.lines(50))
        self.stop()
        self.write(self.repo, "mailer.py", self.lines(45, "y"))
        self.assertEqual(self.stop().get("decision"), "block")

    def test_already_continuing_after_a_stop_message_is_left_alone(self) -> None:
        self.write(self.repo, "report.py", self.lines(50))
        self.assertEqual(self.stop(stop_hook_active=True), {})

    def test_tiny_change_never_triggers(self) -> None:
        self.write(self.repo, "app.py", "print('hello')\n")
        self.assertEqual(self.stop(), {})

    def test_docs_and_lockfiles_do_not_count(self) -> None:
        self.write(self.repo, "README.md", self.lines(200))
        self.write(self.repo, "package-lock.json", self.lines(500))
        self.write(self.repo, "dist/bundle.js", self.lines(500))
        self.assertEqual(self.stop(), {})

    def test_changes_left_over_from_before_the_session_do_not_count(self) -> None:
        other = self.make_repo("dirty")
        self.write(other, "old.py", self.lines(100))  # half-finished work from yesterday
        hooks.session_start(self.payload(other))
        self.assertEqual(hooks.stop_check(self.payload(other)), "")
        self.write(other, "new.py", self.lines(60, "n"))
        self.assertIn('"block"', hooks.stop_check(self.payload(other)))

    def test_committed_work_during_the_session_counts(self) -> None:
        self.write(self.repo, "report.py", self.lines(60))
        self.commit(self.repo, "add report")
        self.assertEqual(self.stop().get("decision"), "block")

    def test_plan_mode_and_paused_projects_are_left_alone(self) -> None:
        self.write(self.repo, "report.py", self.lines(60))
        self.assertEqual(self.stop(permission_mode="plan"), {})
        with state.edit_state("shop") as st:
            st["paused"] = True
        self.assertEqual(self.stop(), {})

    def test_after_the_guide_is_synced_nothing_is_pending(self) -> None:
        self.write(self.repo, "report.py", self.lines(60))
        hooks.mark_synced(str(self.repo), "shop", str(self.repo))
        self.assertEqual(self.stop(), {})

    def test_brand_new_repo_with_no_commits_still_works(self) -> None:
        fresh = self.make_repo("fresh", files={}, commit=False)
        hooks.session_start(self.payload(fresh))
        self.assertEqual(hooks.stop_check(self.payload(fresh)), "")
        self.write(fresh, "main.py", self.lines(30))
        self.assertIn('"block"', hooks.stop_check(self.payload(fresh)))

    def test_the_first_commit_of_unchanged_new_files_is_not_new_work(self) -> None:
        fresh = self.make_repo("fresh", files={}, commit=False)
        hooks.session_start(self.payload(fresh))
        self.write(fresh, "main.py", self.lines(60))
        self.write(fresh, "util.py", self.lines(30, "u"))
        hooks.mark_synced(str(fresh), "fresh", str(fresh))  # the guide was updated before any commit
        self.commit(fresh, "first commit")
        self.assertEqual(hooks.stop_check(self.payload(fresh)), "")

    def test_an_edit_after_the_first_commit_still_counts(self) -> None:
        fresh = self.make_repo("fresh", files={}, commit=False)
        hooks.session_start(self.payload(fresh))
        self.write(fresh, "main.py", self.lines(60))
        self.write(fresh, "util.py", self.lines(30, "u"))
        hooks.mark_synced(str(fresh), "fresh", str(fresh))
        self.commit(fresh, "first commit")
        self.write(fresh, "main.py", self.lines(60) + self.lines(50, "extra"))
        out = json.loads(hooks.stop_check(self.payload(fresh)))
        self.assertEqual(out["decision"], "block")
        self.assertIn("main.py", out["reason"])
        self.assertNotIn("util.py", out["reason"])

    def test_resumed_session_keeps_its_starting_picture(self) -> None:
        self.write(self.repo, "report.py", self.lines(60))
        hooks.session_start(self.payload(self.repo, source="compact"))  # same session id
        self.assertEqual(self.stop().get("decision"), "block")


if __name__ == "__main__":
    unittest.main()
