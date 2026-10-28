"""Show before you ask, and what makes the code the person's own: seen code, their calls, their lines."""

from __future__ import annotations

import datetime as dt
import json
import unittest

from support import ROOT, GuideTestCase

from own_guide import hooks, ownership, state

FLOW_PAGE = """---
flow: checkout
files: [shop/cart.py, shop/coupons.py]
---

# Flow: "Checkout"

1. `shop/cart.py:3` `total()`: adds up the cart.
"""


class OwnershipRecordsTest(unittest.TestCase):
    def test_a_record_is_one_clean_line(self) -> None:
        event = ownership.new_event("call", "you", "  Expired coupons:\n24-hour grace ", "2026-10-26")
        self.assertEqual(event, {"date": "2026-10-26", "kind": "call", "who": "you",
                                 "what": "Expired coupons: 24-hour grace"})
        self.assertEqual(len(ownership.new_event("line", "you", "x" * 500, "2026-10-26")["what"]), ownership.MAX_WHAT)

    def test_bad_records_are_refused(self) -> None:
        for args in (("vote", "you", "x"), ("call", "mia", "x"), ("call", "you", "  "), ("call", "claude", "x", "lazy")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                ownership.new_event(*args[:3], "2026-10-26", *args[3:])

    def test_counts_cover_every_kind_and_who(self) -> None:
        events = [ownership.new_event("call", "you", "a", "d"), ownership.new_event("call", "claude", "b", "d", "busy"),
                  ownership.new_event("line", "you", "c", "d"), {"kind": "junk", "who": "you"}]
        self.assertEqual(ownership.counts(events), {"call_you": 1, "call_claude": 1, "line_you": 1, "line_claude": 0,
                                                    "find_you": 0, "find_claude": 0})

    def test_busy_is_one_day_only(self) -> None:
        day = dt.date(2026, 10, 26)
        self.assertTrue(ownership.busy_today({"busy_day": "2026-10-26"}, day))
        self.assertFalse(ownership.busy_today({"busy_day": "2026-10-25"}, day))
        self.assertFalse(ownership.busy_today({"busy_day": ""}, day))


class SeenTest(unittest.TestCase):
    """The 'Where would you look first?' card is fair only for code the person has walked, unchanged since."""

    PAGES = {"checkout": ["shop/cart.py", "shop/coupons.py"], "login": ["shop/auth.py"]}

    def test_files_are_named_the_way_flow_pages_name_them(self) -> None:
        self.assertEqual(ownership.repo_path("shop/cart.py:42", "/repo"), "shop/cart.py")
        self.assertEqual(ownership.repo_path("shop/cart.py:apply_coupon", "/repo"), "shop/cart.py")
        self.assertEqual(ownership.repo_path("/repo/shop/cart.py", "/repo"), "shop/cart.py")
        self.assertEqual(ownership.repo_path("./shop/cart.py", "/repo"), "shop/cart.py")

    def test_walked_and_unchanged_is_fair(self) -> None:
        out = ownership.seen_files(["shop/cart.py", "shop/coupons.py"], self.PAGES, {"checkout"}, {})
        self.assertTrue(out["ask_guess"])
        self.assertEqual(out["via"], {"shop/cart.py": ["checkout"], "shop/coupons.py": ["checkout"]})

    def test_one_file_never_walked_makes_the_guess_unfair(self) -> None:
        out = ownership.seen_files(["shop/cart.py", "shop/auth.py"], self.PAGES, {"checkout"}, {})
        self.assertFalse(out["ask_guess"])
        self.assertEqual(out["unseen"], ["shop/auth.py"])

    def test_code_claude_changed_since_the_walk_is_not_seen(self) -> None:
        out = ownership.seen_files(["shop/cart.py", "shop/coupons.py"], self.PAGES, {"checkout"},
                                   {"checkout": {"shop/coupons.py"}})
        self.assertEqual((out["seen"], out["unseen"]), (["shop/cart.py"], ["shop/coupons.py"]))
        whole_page_old = ownership.seen_files(["shop/cart.py"], self.PAGES, {"checkout"}, {"checkout": None})
        self.assertFalse(whole_page_old["ask_guess"])

    def test_no_files_means_no_guess(self) -> None:
        self.assertFalse(ownership.seen_files([], self.PAGES, {"checkout"}, {})["ask_guess"])


class EditCheckTest(GuideTestCase):
    """Claude's first code edit of a piece of work is held back once, so the person sees what's about to change."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", files={"shop/cart.py": "def total():\n    return 0\n",
                                                  ".gitignore": "data/\n"})
        hooks.session_start(self.payload(self.repo))

    def edit(self, rel: str, **extra: object) -> str:
        target = rel if rel.startswith("/") else str(self.repo / rel)
        return hooks.edit_check(self.payload(self.repo, tool_name="Edit", hook_event_name="PreToolUse",
                                             tool_input={"file_path": target}, **extra))

    def test_the_first_code_edit_is_held_once_then_edits_flow(self) -> None:
        out = json.loads(self.edit("shop/cart.py"))["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("Starting a change", out["permissionDecisionReason"])
        self.assertIn("Your call", out["permissionDecisionReason"])
        self.assertEqual(self.edit("shop/cart.py"), "")
        self.assertEqual(self.edit("shop/new_file.py"), "")

    def test_helper_agents_and_plan_mode_are_left_alone(self) -> None:
        self.assertEqual(self.edit("shop/cart.py", agent_id="agent-7", agent_type="Explore"), "")
        self.assertEqual(self.edit("shop/cart.py", permission_mode="plan"), "")
        self.assertIn("deny", self.edit("shop/cart.py"))  # the hold wasn't used up by them

    def test_files_that_are_not_the_projects_code_are_left_alone(self) -> None:
        for target in ("README.md", "data/run.json", str(self.tmp / "elsewhere.py"),
                       str(self.guides / "shop" / "FLOW.md")):
            with self.subTest(target=target):
                self.assertEqual(self.edit(target), "")
        reads = hooks.edit_check(self.payload(self.repo, tool_name="Read",
                                              tool_input={"file_path": str(self.repo / "shop/cart.py")}))
        self.assertEqual(reads, "")

    def test_busy_paused_or_off_means_no_hold(self) -> None:
        state.save_settings({"busy_day": "2026-10-26"})
        self.assertEqual(self.edit("shop/cart.py"), "")
        state.save_settings({"busy_day": "2026-10-25"})  # yesterday's busy day is over
        with state.edit_state("shop") as st:
            st["paused"] = True
        self.assertEqual(self.edit("shop/cart.py"), "")
        with state.edit_state("shop") as st:
            st["paused"] = False
        state.save_settings({"enabled": False})
        self.assertEqual(self.edit("shop/cart.py"), "")
        state.save_settings({"enabled": True})
        self.assertIn("deny", self.edit("shop/cart.py"))

    def test_a_new_piece_of_work_is_held_again(self) -> None:
        self.assertIn("deny", self.edit("shop/cart.py"))
        hooks.mark_synced(str(self.repo), "shop", str(self.repo))  # the guide was updated: that work is done
        self.assertIn("deny", self.edit("shop/cart.py"))
        # A small fix ends a turn without much code changed: the next request is new work too.
        self.write(self.repo, "shop/cart.py", "def total():\n    return 1\n")
        self.assertEqual(hooks.stop_check(self.payload(self.repo)), "")
        self.assertIn("deny", self.edit("shop/cart.py"))

    def test_while_their_line_is_with_them_the_work_stays_open(self) -> None:
        self.assertIn("deny", self.edit("shop/cart.py"))
        hooks.mark_line_pending(str(self.repo), "shop", str(self.repo), True)  # `own-guide line-handed`
        self.write(self.repo, "shop/cart.py", "def total():\n    return ...  # YOUR LINE\n")
        self.assertEqual(hooks.stop_check(self.payload(self.repo)), "")  # the turn ends to wait for them
        self.assertEqual(self.edit("shop/cart.py"), "")  # finishing the same work: no second hold
        hooks.mark_line_pending(str(self.repo), "shop", str(self.repo), False)  # `owned line ...`
        self.assertEqual(hooks.stop_check(self.payload(self.repo)), "")
        self.assertIn("deny", self.edit("shop/cart.py"))  # the next request is new work again

    def test_the_plugin_runs_the_check_before_file_edits(self) -> None:
        config = json.loads((ROOT / "plugins/own/hooks/hooks.json").read_text(encoding="utf-8"))
        entry = config["hooks"]["PreToolUse"][0]
        self.assertEqual(set(entry["matcher"].split("|")), set(hooks.EDIT_TOOLS))
        self.assertTrue(entry["hooks"][0]["command"].endswith("edit-check"))

    def test_the_cli_hook_prints_the_hold_and_never_fails(self) -> None:
        payload = self.payload(self.repo, tool_name="Write", tool_input={"file_path": str(self.repo / "shop/x.py")})
        proc = self.run_cli(self.repo, "edit-check", stdin=payload)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        broken = self.run_cli(self.repo, "edit-check", stdin="{not json")
        self.assertEqual((broken.returncode, broken.stdout), (0, ""))


class NoteAndCardsTest(GuideTestCase):
    def note(self, repo) -> str:
        return json.loads(hooks.session_start(self.payload(repo)))["hookSpecificOutput"]["additionalContext"]

    def test_the_note_says_show_before_you_ask(self) -> None:
        repo = self.make_repo("shop")
        text = self.note(repo)
        self.assertIn("Show before you ask", text)
        self.assertIn("seen <the 3 likeliest files>", text)
        self.assertNotIn("Busy today:", text)

    def test_a_busy_day_is_in_the_note(self) -> None:
        repo = self.make_repo("shop")
        state.save_settings({"busy_day": "2026-10-26"})
        self.assertIn("- Busy today:", self.note(repo))

    def test_the_end_of_work_message_asks_for_the_before_after_walk(self) -> None:
        repo = self.make_repo("shop")
        hooks.session_start(self.payload(repo))
        self.write(repo, "shop/big.py", self.lines(60))
        reason = json.loads(hooks.stop_check(self.payload(repo)))["reason"]
        self.assertIn("Before/After code walk", reason)


class OwnershipCliTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", remote="git@github.com:me/shop.git",
                                   files={"shop/cart.py": "def total():\n    return 0\n",
                                          "shop/coupons.py": "CODES = {}\n", "shop/auth.py": "x = 1\n"})
        self.cli("init-guide")
        self.base = self.guides / "shop"
        (self.base / "flows" / "checkout.md").write_text(FLOW_PAGE, encoding="utf-8")
        self.cli("stamp", "flows/checkout.md")

    def cli(self, *args: str) -> str:
        proc = self.run_cli(self.repo, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def seen(self, *files: str) -> dict:
        return json.loads(self.cli("seen", *files))

    def test_seen_follows_walks_and_changes(self) -> None:
        self.assertFalse(self.seen("shop/cart.py:2")["ask_guess"])  # page written, never walked
        self.cli("walked", "checkout", "--stops", "5", "--asked", "4", "--right", "4", "--explain", "full")
        out = self.seen("shop/cart.py:2", str(self.repo / "shop/coupons.py"))
        self.assertTrue(out["ask_guess"], out)
        self.assertFalse(self.seen("shop/cart.py", "shop/auth.py")["ask_guess"])  # auth was never shown
        self.write(self.repo, "shop/coupons.py", "CODES = {'SPRING10': 10}\n")  # Claude changed it since
        out = self.seen("shop/cart.py", "shop/coupons.py")
        self.assertEqual((out["ask_guess"], out["unseen"]), (False, ["shop/coupons.py"]))
        self.assertIn("fix it first", out["say"])

    def test_busy_today_and_back(self) -> None:
        self.assertTrue(json.loads(self.cli("busy"))["busy_today"])
        self.assertEqual(state.load_settings()["busy_day"], "2026-10-26")
        self.assertTrue(json.loads(self.cli("status"))["busy_today"])
        self.assertFalse(json.loads(self.cli("busy", "--off"))["busy_today"])
        self.assertFalse(json.loads(self.cli("status"))["busy_today"])

    def test_owned_records_show_in_progress_and_on_the_guide_page(self) -> None:
        self.cli("owned", "call", "--who", "you", "--what", "Expired coupons get a 24-hour grace")
        self.cli("owned", "line", "--who", "you", "--what", "the grace check in apply_coupon()",
                 "--file", "shop/coupons.py")
        out = json.loads(self.cli("owned", "call", "--who", "claude", "--why", "busy",
                                  "--what", "Two failed checks before 'store offline'"))
        self.assertEqual(out["totals"]["call_you"], 1)
        self.assertEqual(out["totals"]["call_claude"], 1)
        summary = self.cli("render")
        self.assertIn("Yours: 1 calls you made, 1 pieces of code you wrote, 0 things you found yourself", summary)
        self.assertIn("Calls Claude made for you (to look at later): 1", summary)
        page = (self.base / "guide.html").read_text(encoding="utf-8")
        self.assertIn("Calls Claude made for you", page)
        self.assertIn("Two failed checks before &#x27;store offline&#x27;", page)
        self.assertIn("(you were busy)", page)
        self.assertIn("| Calls you made | 1 |", (self.base / "PROGRESS.md").read_text(encoding="utf-8"))

    def test_line_handed_then_owned_closes_the_wait(self) -> None:
        self.cli("line-handed")
        top = str(self.repo)
        self.assertTrue(state.load_state("shop")["worktrees"][top]["line_pending"])
        self.cli("owned", "line", "--who", "you", "--what", "the grace check")
        self.assertFalse(state.load_state("shop")["worktrees"][top]["line_pending"])

    def test_bad_owned_records_fail_cleanly(self) -> None:
        self.assertEqual(self.run_cli(self.repo, "owned", "call", "--who", "you", "--what", " ").returncode, 1)
        self.assertEqual(self.run_cli(self.repo, "owned", "vote", "--who", "you", "--what", "x").returncode, 2)


if __name__ == "__main__":
    unittest.main()
