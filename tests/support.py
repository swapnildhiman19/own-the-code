"""Shared test helpers: throwaway git repos and a throwaway ~/code-guides."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "plugins" / "own" / "lib"
BIN = ROOT / "plugins" / "own" / "bin" / "own-guide"
sys.path.insert(0, str(LIB))

TODAY = "2026-10-26"


class GuideTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="own-test-")).resolve()
        self.guides = self.tmp / "guides"
        self.env = {
            "OWN_GUIDES_DIR": str(self.guides),
            "OWN_TODAY": TODAY,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self._saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- git helpers -------------------------------------------------------------
    def git(self, repo: Path, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return proc.stdout.strip()

    def write(self, repo: Path, rel: str, text: str) -> Path:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, repo: Path, message: str = "change") -> None:
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", message)

    def make_repo(self, name: str, remote: str | None = None, files: dict[str, str] | None = None,
                  commit: bool = True) -> Path:
        repo = self.tmp / name
        repo.mkdir(parents=True)
        self.git(repo, "init", "-q", "-b", "main")
        if remote:
            self.git(repo, "remote", "add", "origin", remote)
        for rel, text in (files if files is not None else {"app.py": "print('hi')\n"}).items():
            self.write(repo, rel, text)
        if commit:
            self.commit(repo, "initial")
        return repo

    @staticmethod
    def lines(n: int, prefix: str = "x") -> str:
        return "".join(f"{prefix}_{i} = {i}\n" for i in range(n))

    @staticmethod
    def payload(repo: Path, **extra: object) -> str:
        return json.dumps({"cwd": str(repo), "session_id": "session-1", **extra})

    def run_cli(self, repo: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        env = dict(os.environ, **self.env)
        return subprocess.run([sys.executable, "-I", str(BIN), *args], cwd=repo, input=stdin,
                              capture_output=True, text=True, env=env)
