"""A guide page knows when the code under it has changed."""

from __future__ import annotations

import unittest

from support import GuideTestCase

from own_guide import frontmatter, gitinfo, identity


class FrontmatterTest(unittest.TestCase):
    def test_inline_and_block_lists(self) -> None:
        inline = "---\nflow: who-am-i\nchecked_commit: 'abc123'\nfiles: [a.py, b/c.py]\n---\n# body"
        block = "---\nflow: x\nfiles:\n  - a.py\n  - b.py\n---\n"
        self.assertEqual(frontmatter.parse(inline),
                         {"flow": "who-am-i", "checked_commit": "abc123", "files": ["a.py", "b/c.py"]})
        self.assertEqual(frontmatter.parse(block)["files"], ["a.py", "b.py"])

    def test_no_header_or_unclosed_header(self) -> None:
        self.assertEqual(frontmatter.parse("# just a page"), {})
        self.assertEqual(frontmatter.parse("---\nflow: x\n"), {})

    def test_update_keeps_the_body_and_key_order(self) -> None:
        text = "---\nflow: x\nfiles: [a.py]\n---\n# Body\nline\n"
        out = frontmatter.update(text, {"checked_commit": "abc", "files": ["a.py", "b.py"]})
        self.assertEqual(out, "---\nflow: x\nfiles: [a.py, b.py]\nchecked_commit: abc\n---\n# Body\nline\n")


class StalePagesTest(GuideTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo("shop", files={"api.py": "a = 1\n", "auth.py": "b = 1\n", "other.py": "c\n"})
        self.head = self.git(self.repo, "rev-parse", "--short", "HEAD")
        folder = identity.resolve(self.repo)["entry"]["folder"]  # register first, as a session would
        self.guide_dir = self.guides / folder
        (self.guide_dir / "flows").mkdir(parents=True)

    def page(self, name: str, commit: str, files: list[str]) -> None:
        (self.guide_dir / "flows" / f"{name}.md").write_text(
            f"---\nflow: {name}\nchecked_commit: {commit}\nfiles: [{', '.join(files)}]\n---\n# {name}\n",
            encoding="utf-8",
        )

    def test_fresh_page_is_not_stale(self) -> None:
        self.page("login", self.head, ["api.py", "auth.py"])
        self.assertEqual(gitinfo.stale_pages(self.repo, self.guide_dir), [])

    def test_changed_file_makes_its_page_stale_but_not_others(self) -> None:
        self.page("login", self.head, ["api.py", "auth.py"])
        self.page("misc", self.head, ["other.py"])
        self.write(self.repo, "auth.py", "b = 2\n")
        self.commit(self.repo, "teammate change")
        stale = gitinfo.stale_pages(self.repo, self.guide_dir)
        self.assertEqual([s["page"] for s in stale], ["flows/login.md"])
        self.assertEqual(stale[0]["changed"], ["auth.py"])

    def test_uncommitted_and_deleted_files_count(self) -> None:
        self.page("login", self.head, ["api.py", "auth.py"])
        (self.repo / "api.py").unlink()
        stale = gitinfo.stale_pages(self.repo, self.guide_dir)
        self.assertIn("api.py", stale[0]["changed"])

    def test_stamped_page_describing_uncommitted_work_stays_fresh_until_the_file_changes(self) -> None:
        self.write(self.repo, "auth.py", "b = 1\nhalf_finished = True\n")  # uncommitted work
        (self.guide_dir / "flows" / "login.md").write_text(
            "---\nflow: login\nfiles: [api.py, auth.py]\n---\n# login\n", encoding="utf-8")
        proc = self.run_cli(self.repo, "stamp", "flows/login.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        header = frontmatter.parse((self.guide_dir / "flows" / "login.md").read_text(encoding="utf-8"))
        self.assertEqual(header["checked_commit"], self.head)
        self.assertEqual(len(header["hashes"]), 2)
        self.assertEqual(gitinfo.stale_pages(self.repo, self.guide_dir), [])  # dirty, but as checked
        self.write(self.repo, "auth.py", "b = 1\nhalf_finished = False\n")
        stale = gitinfo.stale_pages(self.repo, self.guide_dir)
        self.assertEqual(stale[0]["changed"], ["auth.py"])
        self.write(self.repo, "auth.py", "b = 1\nhalf_finished = True\n")  # back to what was checked
        self.assertEqual(gitinfo.stale_pages(self.repo, self.guide_dir), [])

    def test_a_file_missing_at_stamp_time_still_counts_as_stale(self) -> None:
        (self.guide_dir / "flows" / "gone.md").write_text(
            "---\nflow: gone\nfiles: [api.py, removed.py]\n---\n# gone\n", encoding="utf-8")
        self.assertEqual(self.run_cli(self.repo, "stamp", "flows/gone.md").returncode, 0)
        stale = gitinfo.stale_pages(self.repo, self.guide_dir)
        self.assertEqual(stale[0]["changed"], ["removed.py"])

    def test_stamp_needs_a_files_list(self) -> None:
        (self.guide_dir / "flows" / "x.md").write_text("---\nflow: x\n---\n# x\n", encoding="utf-8")
        proc = self.run_cli(self.repo, "stamp", "flows/x.md")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("files", proc.stderr)

    def test_unknown_version_is_flagged(self) -> None:
        self.page("login", "deadbeef", ["api.py"])
        stale = gitinfo.stale_pages(self.repo, self.guide_dir)
        self.assertIn("doesn't have", stale[0]["reason"])


if __name__ == "__main__":
    unittest.main()
