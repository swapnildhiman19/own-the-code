"""The commands the skill runs, end to end through the real launcher, and the progress views."""

from __future__ import annotations

import datetime as dt
import json
import unittest

from support import GuideTestCase

from own_guide import guide, render, state


class CliFlowTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", remote="git@github.com:me/shop.git")

    def cli(self, *args: str, stdin: str = "") -> str:
        proc = self.run_cli(self.repo, *args, stdin=stdin)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_a_whole_quiz_round_trip(self) -> None:
        self.cli("init-guide")
        self.assertTrue((self.guides / "shop" / "FLOW.md").is_file())
        self.assertTrue((self.guides / "_knowledge" / "INDEX.md").is_file())

        missed = json.loads(self.cli("add-question", "--kind", "debug", "--tests", "where a grey button comes from",
                                     "--answer", "the cart check refuses an empty cart", "--link", "app/cart.py:can_checkout",
                                     "--source", "flow:who-am-i", "--feature", "who am i", "--result", "miss"))
        right = json.loads(self.cli("add-question", "--kind", "why", "--tests", "why the server decides",
                                    "--answer", "one place for the rule", "--result", "right"))
        self.assertEqual(missed["next_due"], "2026-10-27")
        self.assertEqual(right["next_due"], "2026-11-09")

        done = json.loads(self.cli("quiz-done", "--feature", "who am i", "--asked", "2", "--right", "1"))
        self.assertEqual(done["next_returns"][0]["date"], "2026-10-27")

        self.assertEqual(json.loads(self.cli("due")), [])
        tomorrow = self.run_cli(self.repo, "due", stdin="")
        self.env["OWN_TODAY"] = "2026-10-27"
        due = json.loads(self.run_cli(self.repo, "due").stdout)
        self.assertEqual([q["id"] for q in due], [missed["id"]])
        self.assertEqual(tomorrow.returncode, 0)
        recorded = json.loads(self.run_cli(self.repo, "record", missed["id"], "right").stdout)
        self.assertEqual(recorded["next_due"], "2026-10-30")

        summary = self.run_cli(self.repo, "render").stdout
        self.assertIn("shop: what you know", summary)
        self.assertTrue((self.guides / "shop" / "PROGRESS.md").is_file())
        self.assertTrue((self.guides / "dashboard.html").is_file())

    def test_later_then_done_clears_the_saved_quiz(self) -> None:
        self.cli("quiz-later", "--feature", "weekly report")
        self.assertEqual(state.load_state("shop")["pending_quiz"]["feature"], "weekly report")
        self.cli("quiz-done", "--feature", "weekly report", "--asked", "3", "--right", "3")
        self.assertIsNone(state.load_state("shop")["pending_quiz"])

    def test_two_perfect_quizzes_raise_the_level(self) -> None:
        for _ in range(2):
            self.cli("quiz-done", "--feature", "f", "--asked", "3", "--right", "3")
        self.assertEqual(state.load_state("shop")["level"], 2)
        self.cli("quiz-done", "--feature", "f", "--asked", "3", "--right", "2")
        self.assertEqual(state.load_state("shop")["level"], 1)

    def test_switches(self) -> None:
        self.cli("pause", "--here")
        self.assertTrue(state.load_state("shop")["paused"])
        self.cli("resume", "--here")
        self.assertFalse(state.load_state("shop")["paused"])
        self.cli("pause")
        self.assertFalse(state.load_settings()["enabled"])
        self.assertEqual(self.cli("session-start", stdin=self.payload(self.repo)), "")
        self.cli("resume")
        self.assertTrue(state.load_settings()["enabled"])

    def test_card_shown_marks_today_and_the_week(self) -> None:
        self.cli("card-shown", "--weekly")
        st = state.load_state("shop")
        self.assertEqual(st["daily_card"]["last_shown"], "2026-10-26")
        self.assertEqual(st["weekly_line"]["last_week"], "2026-W44")

    def test_hooks_never_fail_on_garbage_input(self) -> None:
        self.assertEqual(self.run_cli(self.repo, "session-start", stdin="not json").returncode, 0)
        self.assertEqual(self.run_cli(self.repo, "stop-check", stdin="{]").returncode, 0)

    def test_outside_git_commands_explain_themselves(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        proc = self.run_cli(plain, "where")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not inside a git repository", proc.stderr)


class RenderTest(GuideTestCase):
    def test_counts_follow_the_guide_formats(self) -> None:
        repo = self.make_repo("shop")
        from own_guide import identity
        identity.resolve(repo)
        guide.init("shop", "shop", "2026-10-26")
        base = self.guides / "shop"
        with open(base / "FLOW.md", "a", encoding="utf-8") as f:
            f.write("| Who am I? | says who is signed in | `routers/me.py:28` | [page](flows/who-am-i.md) |\n")
            f.write("| Ask a question | answers | `routers/ask.py:10` | not written yet |\n")
        (base / "flows" / "who-am-i.md").write_text("# page\n", encoding="utf-8")
        text = (base / "CODE-DECISIONS.md").read_text(encoding="utf-8").replace(
            "|---|---|---|---|\n", "|---|---|---|---|\n| 1 | Server decides | You | Yes |\n| 2 | Lazy import | Claude | Yes |\n", 1)
        (base / "CODE-DECISIONS.md").write_text(text, encoding="utf-8")
        with open(base / "LEARNINGS.md", "a", encoding="utf-8") as f:
            f.write("\n### FastAPI Depends\n\n### Circular import\n")
        n = render.summary("shop", state.load_state("shop"), dt.date(2026, 10, 26))
        self.assertEqual((n["flows_listed"], n["flow_pages"], n["decisions"], n["ideas"]), (2, 1, 2, 2))

    def test_weekly_line_shows_growth_once_a_week(self) -> None:
        st = state.load_state("p")
        today = dt.date(2026, 10, 26)
        st["progress_log"] = [
            {"date": "2026-10-18", "flows_listed": 0, "flow_pages": 1, "flows_got": 0, "ideas": 2, "decisions": 1,
             "got_it": 0},
            {"date": "2026-10-26", "flows_listed": 34, "flow_pages": 3, "flows_got": 1, "ideas": 7, "decisions": 4,
             "got_it": 2},
        ]
        line = render.weekly_line("shop", st, today)
        self.assertEqual(line, "This week in shop: +34 flows on the map, +2 flow pages written, +5 ideas, "
                               "+2 questions you've got for good")
        st["weekly_line"]["last_week"] = "2026-W44"
        self.assertIsNone(render.weekly_line("shop", st, today))

    def test_old_rows_without_a_metric_do_not_inflate_the_week(self) -> None:
        st = state.load_state("p")
        st["progress_log"] = [
            {"date": "2026-10-18", "flow_pages": 1, "flows_got": 0, "ideas": 2, "decisions": 1, "got_it": 0},
            {"date": "2026-10-26", "flows_listed": 34, "flow_pages": 1, "flows_got": 0, "ideas": 2, "decisions": 1,
             "got_it": 0},
        ]
        self.assertEqual(render.weekly_delta(st, dt.date(2026, 10, 26))["flows_listed"], 0)
        self.assertIsNone(render.weekly_line("p", st, dt.date(2026, 10, 26)))

    def test_only_rows_under_the_flows_heading_count_as_flows(self) -> None:
        text = (
            "# How x runs\n\n## The whole-project map\n\n| Part | Note |\n|---|---|\n"
            "| Payments | not written yet |\n\n## The flows\n\n### Version 2\n\n"
            "| Flow | What it does | Starts at | Page |\n|---|---|---|---|\n"
            "| Checkout | takes payment | `checkout.py:12` | not written yet |\n"
            "| Who am I? | says who | `routes/me.py:8` | [page](flows/who-am-i.md) |\n\n## Notes\n\n| x | not written yet |\n"
        )
        self.assertEqual(len(guide.flow_rows(text)), 2)

    def test_dashboard_is_self_contained(self) -> None:
        page = render.dashboard_html([{"folder": "shop"}], dt.date(2026, 10, 26))
        self.assertNotIn("http", page)
        self.assertNotIn("<script", page)
        self.assertIn("prefers-color-scheme: dark", page)
        self.assertIn("never published", page)


if __name__ == "__main__":
    unittest.main()
