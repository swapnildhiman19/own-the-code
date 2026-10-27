"""One repo = exactly one guide."""

from __future__ import annotations

import unittest

from support import GuideTestCase

from own_guide import identity


class NormalizeRemoteTest(unittest.TestCase):
    def test_ssh_https_and_case_collapse_to_one_form(self) -> None:
        expected = "github.com/acme/api"
        for url in (
            "git@github.com:Acme/API.git",
            "https://github.com/acme/api",
            "https://token@github.com/acme/api.git/",
            "ssh://git@github.com:22/acme/api.git",
            "github.com:acme/api",
        ):
            with self.subTest(url=url):
                self.assertEqual(identity.normalize_remote(url), expected)

    def test_local_paths_are_not_addresses(self) -> None:
        for url in ("/Users/me/repo", "../repo", "file:///tmp/repo", "", "   "):
            with self.subTest(url=url):
                self.assertIsNone(identity.normalize_remote(url))


class ResolveTest(GuideTestCase):
    def test_ssh_and_https_clones_share_one_guide(self) -> None:
        a = self.make_repo("a/api", remote="git@github.com:Acme/Api.git")
        b = self.make_repo("b/api", remote="https://github.com/acme/api")
        first = identity.resolve(a)
        second = identity.resolve(b)
        self.assertEqual(first["status"], "new")
        self.assertEqual(second["status"], "known")
        self.assertEqual(first["entry"]["folder"], "api")
        self.assertEqual(second["entry"]["folder"], "api")
        self.assertEqual(len(identity.all_projects()), 1)

    def test_worktree_shares_the_main_folders_guide(self) -> None:
        repo = self.make_repo("store", remote="git@github.com:acme/online-store.git")
        self.git(repo, "worktree", "add", "-q", str(self.tmp / "store-wt"), "-b", "feature")
        main = identity.resolve(repo)
        worktree = identity.resolve(self.tmp / "store-wt")
        self.assertEqual(main["entry"]["folder"], "online-store")
        self.assertEqual(worktree["status"], "known")
        self.assertEqual(worktree["entry"]["folder"], "online-store")

    def test_repo_without_remote_uses_its_main_folder_even_from_a_worktree(self) -> None:
        repo = self.make_repo("solo")
        self.git(repo, "worktree", "add", "-q", str(self.tmp / "solo-wt"), "-b", "x")
        first = identity.resolve(repo)
        second = identity.resolve(self.tmp / "solo-wt")
        self.assertTrue(first["entry"]["id"].startswith("root:"))
        self.assertEqual(second["entry"]["folder"], first["entry"]["folder"])

    def test_remote_added_later_keeps_the_same_guide(self) -> None:
        repo = self.make_repo("later")
        before = identity.resolve(repo)
        self.git(repo, "remote", "add", "origin", "git@github.com:me/later.git")
        after = identity.resolve(repo)
        self.assertEqual(after["status"], "known")
        self.assertEqual(after["entry"]["folder"], before["entry"]["folder"])
        self.assertIn("github.com/me/later", after["entry"]["remotes"])

    def test_two_different_repos_with_the_same_name_get_two_clear_folders(self) -> None:
        a = self.make_repo("x/api", remote="git@github.com:acme/api.git")
        b = self.make_repo("y/api", remote="git@github.com:other/api.git")
        self.assertEqual(identity.resolve(a)["entry"]["folder"], "api")
        self.assertEqual(identity.resolve(b)["entry"]["folder"], "other-api")

    def test_unclear_match_is_asked_never_silently_duplicated(self) -> None:
        known = self.make_repo("one/api", remote="git@github.com:acme/api.git")
        identity.resolve(known)
        copy = self.make_repo("two/api")  # same name, no address: can't tell
        result = identity.resolve(copy)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["candidate"]["folder"], "api")
        self.assertEqual(len(identity.all_projects()), 1)
        identity.link(copy, "api")
        self.assertEqual(identity.resolve(copy)["status"], "known")
        self.assertEqual(len(identity.all_projects()), 1)

    def test_register_new_gives_an_unclear_repo_its_own_guide(self) -> None:
        identity.resolve(self.make_repo("one/api", remote="git@github.com:acme/api.git"))
        copy = self.make_repo("two/api")
        entry = identity.register_new(copy)
        self.assertEqual(entry["folder"], "api-2")
        self.assertEqual(identity.resolve(copy)["entry"]["folder"], "api-2")

    def test_outside_git_there_is_no_project(self) -> None:
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertIsNone(identity.resolve(plain))


if __name__ == "__main__":
    unittest.main()
