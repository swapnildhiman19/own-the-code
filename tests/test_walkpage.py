"""The code-walk picture: checked facts in, the same picture out, in the chat and in the guide."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from support import GuideTestCase

from own_guide import state, viewer, walkpage

WALK = {
    "flow": "checkout",
    "moment": "after",
    "title": "How a coupon is applied at checkout",
    "lanes": ["You: the screen", "Web app: src/cart.js", "Server: app/cart.py"],
    "steps": [
        {"from": 0, "to": 1, "label": "clicks Pay", "title": "Mia clicks Pay", "screen": "The cart shows 42.00.",
         "file": "src/cart.js:40 pay()", "code": ["async function pay() {", "  const body = cart;"], "hl": 1,
         "values": [["coupon", "\"SPRING10\""]], "calls": [["pay()", "src/cart.js:40", ""]]},
        {"from": 2, "to": 2, "label": "checks the coupon", "title": "The server checks the coupon", "mark": "changed",
         "code": ["if row.expires < today:"], "hl": 0, "values": [["row.expires < today", "True"]],
         "calls": [["checkout()", "app/routes/checkout.py:12", "calls"], ["apply_coupon()", "app/cart.py:52", ""]],
         "after": {"code": ["if grace < now:"], "values": [["grace < now", "False"]]}},
    ],
}


class ValidateTest(unittest.TestCase):
    def broken(self, **changes) -> dict:
        data = copy.deepcopy(WALK)
        for path, value in changes.items():
            target = data
            *parents, last = path.split("__")
            for key in parents:
                target = target[int(key)] if key.isdigit() else target[key]
            target[last] = value
        return data

    def test_a_good_walk_comes_back_clean(self) -> None:
        clean = walkpage.validate({**WALK, "secret_extra": "dropped"})
        self.assertNotIn("secret_extra", clean)
        self.assertEqual(clean["steps"][1]["after"], {"code": ["if grace < now:"], "values": [["grace < now", "False"]]})
        self.assertEqual(clean["steps"][0]["code"][1], "  const body = cart;")  # indentation kept

    def test_mistakes_are_refused_in_plain_words(self) -> None:
        cases = {
            "flow": self.broken(flow="../etc"),
            "moment": self.broken(moment="later"),
            "lanes": self.broken(lanes=["only one"]),
            "lane numbers": self.broken(steps__0__to=7),
            "mark": self.broken(steps__1__mark="maybe"),
            "label": self.broken(steps__0__label=""),
            "code": self.broken(steps__0__code=["x"] * 13),
            "values": self.broken(steps__0__values=[["only a name"]]),
            "calls": self.broken(steps__1__calls=[["f()", "a.py:1", "teleports"]]),
            "steps": self.broken(steps=[]),
        }
        for name, data in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                walkpage.validate(data)

    def test_code_from_the_repo_cannot_break_out_of_the_page(self) -> None:
        data = copy.deepcopy(WALK)
        data["steps"][0]["code"] = ["html = '</script><script>alert(1)</script>'"]
        data["title"] = "<b>Checkout</b>"
        page = walkpage.page(data, "shop")
        self.assertNotIn("</script><script>alert(1)", page)
        self.assertIn("<\\/script>", page)
        self.assertIn("&lt;b&gt;Checkout&lt;/b&gt;", page)
        self.assertNotIn("http://", page.replace("http://www.w3.org/2000/svg", ""))
        self.assertNotIn("https://", page)

    def test_a_commented_out_script_tag_in_the_code_cannot_swallow_the_page(self) -> None:
        data = copy.deepcopy(WALK)
        data["steps"][0]["code"] = ['<!-- <script src="x"></script> -->']
        page = walkpage.page(data, "shop")
        script = page[page.index("<script>") + len("<script>"):]
        self.assertNotIn("<!--", script.split("</script>")[0])
        self.assertIn("<\\!-- <script src=\\\"x\\\"><\\/script> -->", page)

    def test_a_walk_can_open_the_chat_picture_at_its_current_stop(self) -> None:
        self.assertIn("Math.max(1,2))-1", walkpage.fragment(WALK, 2))
        self.assertIn("Math.max(1,1))-1", walkpage.fragment(WALK))
        for bad in (0, 3, "2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                walkpage.fragment(WALK, bad)

    def test_the_chat_picture_is_a_fragment_and_the_page_is_whole(self) -> None:
        fragment = walkpage.fragment(WALK)
        self.assertFalse(fragment.lstrip().lower().startswith("<!doctype"))
        self.assertIn("Who calls whom to get here", fragment)
        self.assertIn('"moment": "after"', fragment)
        page = walkpage.page(WALK, "shop")
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("flows/checkout.md", page)


class WalkPageCliTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", remote="git@github.com:me/shop.git")
        self.assertEqual(self.run_cli(self.repo, "init-guide").returncode, 0)
        self.base = self.guides / "shop"
        self.data = self.tmp / "walk.json"
        self.data.write_text(json.dumps(WALK), encoding="utf-8")

    def test_needs_the_flow_page_first(self) -> None:
        proc = self.run_cli(self.repo, "walk-page", str(self.data))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("write the page first", proc.stderr)

    def test_writes_the_page_and_the_chat_picture_and_the_guide_links_it(self) -> None:
        (self.base / "flows" / "checkout.md").write_text("---\nflow: checkout\nfiles: [app.py]\n---\n# Flow: Checkout\n",
                                                        encoding="utf-8")
        self.assertEqual(self.run_cli(self.repo, "dashboard").returncode, 0)  # the person has looked at the guide
        out = json.loads(self.run_cli(self.repo, "walk-page", str(self.data)).stdout)
        self.assertEqual(out["steps"], 2)
        self.assertTrue(out["page"].endswith("shop/walks/checkout.html"))
        self.assertIn("Who calls whom", Path(out["chat"]).read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.base / "walks" / "checkout.json").read_text(encoding="utf-8"))["flow"],
                         "checkout")
        self.run_cli(self.repo, "render")
        page = (self.base / "guide.html").read_text(encoding="utf-8")
        self.assertIn('href="walks/checkout.html">step-by-step walk</a>', page)
        self.assertIn("walks/checkout.html (new, step-by-step walk of flows/checkout.md)", page)
        self.assertEqual(viewer.page_of("walks/checkout.html"), "flows/checkout.md")

    def test_bad_json_fails_cleanly(self) -> None:
        self.data.write_text("{not json", encoding="utf-8")
        proc = self.run_cli(self.repo, "walk-page", str(self.data))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("can't read the walk's JSON", proc.stderr)


class AskTomorrowTest(GuideTestCase):
    def test_a_question_saved_after_a_bug_fix_comes_back_tomorrow_with_no_fake_answer(self) -> None:
        repo = self.make_repo("shop")
        proc = self.run_cli(repo, "add-question", "--kind", "debug", "--tests", "why SPRING10 was refused",
                            "--answer", "row.expires was compared, not the grace", "--ask-tomorrow")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["next_due"], "2026-10-27")
        question = state.load_state("shop")["questions"][0]
        self.assertEqual((question["status"], question["history"]), ("learning", []))
        both = self.run_cli(repo, "add-question", "--kind", "debug", "--tests", "x", "--answer", "y",
                            "--result", "miss", "--ask-tomorrow")
        self.assertEqual(both.returncode, 2)


if __name__ == "__main__":
    unittest.main()
