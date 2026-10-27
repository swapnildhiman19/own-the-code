"""Walks, the right answer's position, honest flow counts, numbered pictures, and the guide page."""

from __future__ import annotations

import json
import random
import unittest
from pathlib import Path

from support import GuideTestCase

from own_guide import diagrams, state, viewer, walks

FLOW_PAGE = """---
flow: checkout
files: [app/cart.py]
---

# Flow: "Checkout" (POST /checkout)

**In one line:** Mia pays for her cart.

<!-- own:diagram flows-checkout-1 sha=0a1b2c3d -->
![flows-checkout-1: picture of the diagram below](../diagrams/flows-checkout-1.png)
```mermaid
sequenceDiagram
    autonumber
    actor Mia
    participant Web as Web app
    participant API as Checkout door
    Note over API: checks the cart first
    Mia->>Web: clicks Pay
    Web->>API: POST /checkout
    API-->>Web: the order number
```

## Step by step

1. `src/cart.js:40` `pay()`: the button.
   - sends the cart
2. `app/routes/checkout.py:12` `checkout()`: the door.
3. `checkout.py:31`: the reply.

## Why it's built this way

- Coupons are checked on the server → [CODE-DECISIONS #7](../CODE-DECISIONS.md#7)
"""


def answer(day: str, result: str) -> dict:
    return {"date": day, "result": result}


class SlotTest(unittest.TestCase):
    def picks(self, choices: int, count: int, seed: int = 7) -> list[int]:
        rng, recent = random.Random(seed), []
        for _ in range(count):
            recent.append(walks.pick_slot(recent, choices, rng))
        return recent

    def test_every_pick_is_a_real_position(self) -> None:
        for choices in (2, 3, 4):
            self.assertTrue(set(self.picks(choices, 300)) <= set(range(1, choices + 1)))

    def test_the_same_position_never_comes_three_times_in_a_row(self) -> None:
        for choices in (2, 3, 4):
            seq = self.picks(choices, 2000)
            runs = [i for i in range(2, len(seq)) if seq[i] == seq[i - 1] == seq[i - 2]]
            self.assertEqual(runs, [], f"three in a row with {choices} choices")

    def test_every_position_gets_used_about_equally(self) -> None:
        seq = self.picks(3, 3000)
        for slot in (1, 2, 3):
            self.assertGreater(seq.count(slot), 800)


class FlowStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.walk = [walks.new_walk("checkout", "2026-10-27", 6, 5, 5, "partial")]

    def q(self, *history: dict, source: str = "flow:checkout") -> dict:
        return {"source": source, "history": list(history)}

    def test_right_answers_without_a_walk_are_not_got(self) -> None:
        questions = [self.q(answer("2026-10-27", "right"), answer("2026-11-10", "right"))]
        self.assertEqual(walks.flow_status("checkout", [], questions), walks.NOT_WALKED)

    def test_right_answers_on_the_day_of_the_walk_do_not_count(self) -> None:
        questions = [self.q(answer("2026-10-27", "right"))]
        self.assertEqual(walks.flow_status("checkout", self.walk, questions), walks.WALKED)

    def test_a_right_answer_on_a_later_day_makes_it_got(self) -> None:
        questions = [self.q(answer("2026-10-27", "miss"), answer("2026-10-28", "right"))]
        self.assertEqual(walks.flow_status("checkout", self.walk, questions), walks.GOT)

    def test_a_later_miss_takes_it_back_to_walked_until_right_again(self) -> None:
        q = self.q(answer("2026-10-28", "right"), answer("2026-10-31", "miss"))
        self.assertEqual(walks.flow_status("checkout", self.walk, [q]), walks.WALKED)
        q["history"].append(answer("2026-11-03", "right"))
        self.assertEqual(walks.flow_status("checkout", self.walk, [q]), walks.GOT)

    def test_a_miss_on_the_latest_day_outweighs_a_right_answer_that_day(self) -> None:
        questions = [self.q(answer("2026-10-28", "right")), self.q(answer("2026-10-28", "not-sure"))]
        self.assertEqual(walks.flow_status("checkout", self.walk, questions), walks.WALKED)

    def test_answers_about_other_flows_do_not_count(self) -> None:
        questions = [self.q(answer("2026-10-28", "right"), source="flow:login")]
        self.assertEqual(walks.flow_status("checkout", self.walk, questions), walks.WALKED)

    def test_a_walk_record_refuses_impossible_numbers(self) -> None:
        with self.assertRaises(ValueError):
            walks.new_walk("checkout", "2026-10-27", 6, 3, 4, "full")
        with self.assertRaises(ValueError):
            walks.new_walk("checkout", "2026-10-27", 6, 5, 5, "great")


class NumberingTest(unittest.TestCase):
    def test_arrows_are_counted_and_other_lines_are_not(self) -> None:
        code = (
            "sequenceDiagram\n    autonumber\n    participant A as Web app: the screen\n"
            "    Note over A: not an arrow\n    A->>B: one\n    B-->>A: two\n    A-xB: three\n"
            "    A-)B: four\n    A->B: five\n    A-->B: six\n    loop every minute\n    end\n"
        )
        self.assertEqual(diagrams.count_arrows(code), 6)

    def test_a_matching_page_has_no_problems(self) -> None:
        self.assertEqual(diagrams.check_numbering(FLOW_PAGE), [])

    def test_a_missing_autonumber_is_reported(self) -> None:
        problems = diagrams.check_numbering(FLOW_PAGE.replace("    autonumber\n", ""))
        self.assertEqual(len(problems), 1)
        self.assertIn("autonumber", problems[0])

    def test_more_steps_than_arrows_is_reported_with_both_counts(self) -> None:
        page = FLOW_PAGE.replace("3. `checkout.py:31`: the reply.\n", "3. `checkout.py:31`: the reply.\n4. extra\n")
        self.assertIn("3 arrows but `## Step by step` has 4 steps", diagrams.check_numbering(page)[0])

    def test_only_top_level_steps_under_the_heading_count(self) -> None:
        self.assertEqual(diagrams.count_steps(FLOW_PAGE + "\n## Notes\n\n1. not a step\n"), 3)

    def test_pages_without_a_sequence_diagram_are_not_checked(self) -> None:
        self.assertEqual(diagrams.check_numbering("# Map\n\n```mermaid\nflowchart TD\n  A --> B\n```\n"), [])


class MarkdownTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base = self.tmp / "g"
        (self.base / "flows").mkdir(parents=True)
        docs = {self.base / "CODE-DECISIONS.md": "decisions", self.base / "flows" / "checkout.md": "flow-checkout"}
        self.md = viewer.Markdown("flow-checkout", self.base / "flows", self.base, docs)

    def html(self, text: str) -> str:
        return self.md.render(text)

    def test_the_picture_is_shown_and_its_mermaid_code_is_not(self) -> None:
        out = self.html(FLOW_PAGE)
        self.assertIn('src="diagrams/flows-checkout-1.png"', out)
        self.assertNotIn("sequenceDiagram", out)
        self.assertNotIn("flow: checkout", out)  # the header is not shown

    def test_a_diagram_without_a_picture_stays_available_as_code(self) -> None:
        out = self.html("```mermaid\nflowchart TD\n  A --> B\n```\n")
        self.assertIn("<details>", out)
        self.assertIn("flowchart TD", out)

    def test_numbered_steps_keep_their_wrapped_lines_and_sub_bullets(self) -> None:
        out = self.html("1. first line\n   continues here\n   - a detail\n2. second\n")
        self.assertIn("<ol><li>first line continues here<ul><li>a detail</li></ul></li><li>second</li></ol>", out)

    def test_an_ordered_list_can_start_later(self) -> None:
        self.assertIn('<ol start="4">', self.html("4. four\n5. five\n"))

    def test_tables_keep_a_pipe_inside_code(self) -> None:
        out = self.html("| Key | Meaning |\n|---|---|\n| `a|b` | split |\n")
        self.assertIn("<td><code>a|b</code></td><td>split</td>", out)

    def test_links_between_guide_pages_become_jumps_within_the_page(self) -> None:
        out = self.html("See [#7](../CODE-DECISIONS.md#7) and [steps](#step-by-step).\n\n<a id=\"7\"></a>\n")
        self.assertIn('href="#decisions-7"', out)
        self.assertIn('href="#flow-checkout-step-by-step"', out)
        self.assertIn('<a id="flow-checkout-7"></a>', out)

    def test_nothing_from_a_page_can_run_or_load_from_the_internet(self) -> None:
        out = self.html(
            "<script>alert(1)</script>\n\n[x](javascript:alert(1)) ![y](https://example.com/p.png) "
            "[docs](https://example.com)\n"
        )
        self.assertNotIn("<script", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("javascript:", out)
        self.assertNotIn('src="https', out)
        self.assertIn('href="https://example.com"', out)

    def test_code_blocks_are_escaped(self) -> None:
        self.assertIn("&lt;b&gt;", self.html("```python\nx = '<b>'\n```\n"))


class GuideCliTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", remote="git@github.com:me/shop.git")
        self.cli("init-guide")
        self.base = self.guides / "shop"
        (self.base / "flows" / "checkout.md").write_text(FLOW_PAGE, encoding="utf-8")
        (self.base / "diagrams").mkdir(exist_ok=True)
        (self.base / "diagrams" / "flows-checkout-1.png").write_bytes(b"\x89PNG one")

    def cli(self, *args: str) -> str:
        proc = self.run_cli(self.repo, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_slot_gives_a_position_and_remembers_it(self) -> None:
        out = json.loads(self.cli("slot"))
        self.assertIn(out["slot"], (1, 2, 3))
        self.assertEqual(state.load_state("shop")["answer_slots"], [out["slot"]])
        self.assertEqual(self.run_cli(self.repo, "slot", "--choices", "5").returncode, 1)

    def test_a_flow_is_walked_then_got_only_after_a_later_right_answer(self) -> None:
        self.assertEqual(json.loads(self.cli("status"))["flow_status"], {"checkout": "not walked"})
        out = json.loads(self.cli("walked", "checkout", "--stops", "6", "--asked", "5", "--right", "4",
                                  "--explain", "partial"))
        self.assertEqual(out["status"], "walked")
        self.cli("add-question", "--kind", "trace", "--tests", "order", "--answer", "a then b",
                 "--source", "flow:checkout", "--result", "right")
        self.assertIn("1 walked with you, 0 you've got", self.cli("render"))
        self.env["OWN_TODAY"] = "2026-10-27"
        self.cli("add-question", "--kind", "why", "--tests", "why", "--answer", "because",
                 "--source", "flow:checkout", "--result", "right")
        self.assertIn("1 walked with you, 1 you've got", self.cli("render"))

    def test_walked_refuses_a_page_that_does_not_exist_or_a_strange_name(self) -> None:
        for name in ("login", "../state", ".hidden"):
            proc = self.run_cli(self.repo, "walked", name, "--stops", "1", "--asked", "0", "--right", "0",
                                "--explain", "skipped")
            self.assertEqual(proc.returncode, 1, name)
        self.assertEqual(state.load_state("shop")["walks"], [])

    def test_changes_lists_what_changed_since_the_last_note(self) -> None:
        self.assertTrue(json.loads(self.cli("changes"))["first_look"])
        self.assertEqual(json.loads(self.cli("changes"))["changed"], [])
        page = self.base / "flows" / "checkout.md"
        page.write_text(FLOW_PAGE.replace("Mia pays", "Mia pays quickly"), encoding="utf-8")
        (self.base / "diagrams" / "flows-checkout-1.png").write_bytes(b"\x89PNG two")
        (self.base / "diagrams" / "flow-1.png").write_bytes(b"\x89PNG map")
        peek = json.loads(self.cli("changes", "--peek"))
        self.assertEqual([(c["file"], c["kind"]) for c in peek["changed"]], [
            ("diagrams/flow-1.png", "new"), ("diagrams/flows-checkout-1.png", "changed"),
            ("flows/checkout.md", "changed"),
        ])
        self.assertEqual(peek["pictures"][1], str(self.base / "diagrams" / "flows-checkout-1.png"))
        self.assertEqual(len(json.loads(self.cli("changes"))["changed"]), 3)  # --peek remembered nothing
        self.assertEqual(json.loads(self.cli("changes"))["changed"], [])
        page.unlink()
        self.assertEqual(json.loads(self.cli("changes"))["removed"], ["flows/checkout.md"])

    def test_changes_start_only_remembers(self) -> None:
        # FLOW.md, CODE-DECISIONS.md, LEARNINGS.md, flows/checkout.md and its picture
        self.assertEqual(json.loads(self.cli("changes", "--start")), {"marked": 5})

    def test_the_guide_page_badges_changes_until_it_is_opened(self) -> None:
        out = json.loads(self.cli("dashboard"))
        page = Path(out["guide_page"])
        self.assertEqual(out["open"], str(page))
        first = page.read_text(encoding="utf-8")
        self.assertIn("First look at this page", first)
        self.assertIn('<span class="chip not-walked">Not walked yet</span>', first)
        self.assertNotIn("<script", first)
        self.assertNotIn('src="http', first)
        self.assertIn("shop/guide.html", (self.guides / "dashboard.html").read_text(encoding="utf-8"))

        (self.base / "diagrams" / "flows-checkout-1.png").write_bytes(b"\x89PNG two")
        self.cli("render")  # refreshes the page without counting as "looked"
        self.assertIn('class="chip changed"', page.read_text(encoding="utf-8"))
        self.cli("dashboard")  # opening it: the badge shows this time...
        self.assertIn("picture of flows/checkout.md", page.read_text(encoding="utf-8"))
        self.cli("dashboard")  # ...and is gone the next time
        self.assertIn("Nothing changed since you last looked", page.read_text(encoding="utf-8"))

    def test_dashboard_outside_a_project_opens_the_all_projects_page(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        proc = self.run_cli(plain, "dashboard")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIsNone(out["guide_page"])
        self.assertEqual(out["open"], out["dashboard"])

    def test_diagrams_reports_pages_whose_numbers_do_not_match(self) -> None:
        (self.base / "flows" / "checkout.md").write_text(FLOW_PAGE.replace("    autonumber\n", ""), encoding="utf-8")
        self.env["OWN_MMDC"] = str(self.tmp / "no-such-mmdc")
        out = json.loads(self.cli("diagrams"))
        self.assertEqual(out["numbering"][0]["page"], "flows/checkout.md")


if __name__ == "__main__":
    unittest.main()
