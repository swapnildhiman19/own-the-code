"""Everything Own asks git: what changed, which guide pages went stale, the hotspots.

How "what changed during this session" works, in one example: when Mia opens a repo
that already has two half-edited files, `snapshot()` records how each file differs from
HEAD at that moment. At the end of a turn it takes the same picture again, and
`compare()` keeps only the files whose picture moved. Her old half-edits don't count;
the code Claude just wrote does.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import frontmatter

# The empty tree: lets a repo with no commits yet be diffed like any other.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
_MAX_COUNT_BYTES = 2_000_000


@dataclass
class GitResult:
    code: int
    out: str
    err: str


def git(args: list[str], cwd: str | Path, timeout: int = 15) -> GitResult:
    """Run one git command. Never raises: failures come back as a non-zero code."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GitResult(1, "", str(exc))
    return GitResult(proc.returncode, proc.stdout, proc.stderr)


def toplevel(cwd: str | Path) -> str | None:
    result = git(["rev-parse", "--show-toplevel"], cwd)
    return str(Path(result.out.strip()).resolve()) if result.code == 0 else None


def head(cwd: str | Path) -> str | None:
    result = git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd)
    return result.out.strip() if result.code == 0 and result.out.strip() else None


def short_head(cwd: str | Path) -> str | None:
    result = git(["rev-parse", "--short", "HEAD"], cwd)
    return result.out.strip() if result.code == 0 and result.out.strip() else None


def is_ignored(path: str, patterns: list[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(name, p) for p in patterns)


def tracked_file_count(cwd: str | Path, patterns: list[str]) -> int:
    result = git(["ls-files", "-z"], cwd)
    if result.code != 0:
        return 0
    return sum(1 for p in result.out.split("\0") if p and not is_ignored(p, patterns))


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as handle:
            data = handle.read(_MAX_COUNT_BYTES)
    except OSError:
        return 0
    if b"\0" in data[:8000]:  # binary
        return 0
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def snapshot(cwd: str | Path, base: str | None) -> dict[str, list[Any]]:
    """How every changed file differs from `base` right now.

    Tracked files: [added, deleted, status] from `git diff <base>` (staged, unstaged and
    committed-since-base all included). Untracked files: [lines, 0, "U", size, mtime_ns].
    """
    base = base or EMPTY_TREE
    top = toplevel(cwd) or str(cwd)
    snap: dict[str, list[Any]] = {}

    numstat = git(["diff", "--numstat", "--no-renames", base, "--"], top)
    if numstat.code == 0:
        for line in numstat.out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            added = int(parts[0]) if parts[0].isdigit() else 0
            deleted = int(parts[1]) if parts[1].isdigit() else 0
            snap[parts[2]] = [added, deleted, "M"]

    status = git(["diff", "--name-status", "--no-renames", base, "--"], top)
    if status.code == 0:
        for line in status.out.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[1] in snap:
                snap[parts[1]][2] = parts[0][:1] or "M"

    # A file that is new since `base` also records its size and modified time, like an untracked one, so
    # committing an untouched new file ("U" becomes "A") isn't mistaken for new work (see compare()).
    for rel, entry in snap.items():
        if entry[2] == "A":
            try:
                info = (Path(top) / rel).stat()
            except OSError:
                continue
            entry.extend([info.st_size, info.st_mtime_ns])

    untracked = git(["ls-files", "--others", "--exclude-standard", "-z"], top)
    if untracked.code == 0:
        for rel in untracked.out.split("\0"):
            if not rel:
                continue
            full = Path(top) / rel
            try:
                info = full.stat()
            except OSError:
                continue
            snap[rel] = [_count_lines(full), 0, "U", info.st_size, info.st_mtime_ns]
    return snap


def _same_new_file(before: list[Any] | None, now: list[Any]) -> bool:
    """A new file that was only staged or committed since: same lines, size and modified time, "U" now "A".

    Example: a repo with no commits yet, 46 files written. The guide is updated, then everything is committed
    unchanged. Each file's entry goes from [lines, 0, "U", size, mtime] to [lines, 0, "A", size, mtime]: the
    label moved, the file didn't.
    """
    return (before is not None and len(before) == 5 and len(now) == 5 and {before[2], now[2]} == {"U", "A"}
            and before[0] == now[0] and before[3:] == now[3:])


def compare(start: dict[str, list[Any]], current: dict[str, list[Any]]) -> dict[str, dict[str, Any]]:
    """Files whose difference-from-base moved between two snapshots."""
    changes: dict[str, dict[str, Any]] = {}
    for path, now in current.items():
        before = start.get(path)
        if before == now or _same_new_file(before, now):
            continue
        lines_now = now[0] + now[1]
        lines_before = (before[0] + before[1]) if before and before[2] == now[2] else 0
        changes[path] = {
            "lines": max(abs(lines_now - lines_before), 1),
            "new": now[2] in ("U", "A") and before is None,
        }
    return changes


def meaningful(changes: dict[str, dict[str, Any]], settings: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Is this change big enough to be 'a feature' (and so worth a guide update + quiz)?"""
    kept = {p: c for p, c in changes.items() if not is_ignored(p, settings["ignore"])}
    files = len(kept)
    lines = sum(c["lines"] for c in kept.values())
    big_new_file = any(c["new"] and c["lines"] >= settings["new_file_min_lines"] for c in kept.values())
    ok = (
        lines >= settings["min_lines"]
        or (files >= settings["min_files"] and lines >= settings["min_lines_multi_file"])
        or big_new_file
    )
    top = sorted(kept, key=lambda p: -kept[p]["lines"])[:5]
    return ok, {"files": files, "lines": lines, "top_files": top}


def fingerprint(changes: dict[str, dict[str, Any]], snap: dict[str, list[Any]]) -> str:
    material = json.dumps({p: snap.get(p) for p in sorted(changes)}, sort_keys=True)
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def commit_exists(cwd: str | Path, commit: str) -> bool:
    return git(["cat-file", "-e", f"{commit}^{{commit}}"], cwd).code == 0


def file_hashes(top: str | Path, files: list[str]) -> dict[str, str]:
    """Git's fingerprint of each file as it is on disk right now ("missing" if it's gone).

    Content-based, so it works for uncommitted work: a page checked against a half-finished
    file stays fresh until that file changes again, whatever is committed.
    """
    hashes = {f: "missing" for f in files}
    present = [f for f in files if (Path(top) / f).is_file()]
    if present:
        result = git(["hash-object", "--", *present], top)
        if result.code == 0:
            hashes.update(zip(present, result.out.split()))
    return hashes


def _stamped_hashes(meta: dict[str, Any]) -> dict[str, str]:
    pairs = (item.rpartition("=") for item in meta.get("hashes", []) if isinstance(item, str) and "=" in item)
    return {path: digest for path, _, digest in pairs}


def stale_pages(cwd: str | Path, guide_dir: Path) -> list[dict[str, Any]]:
    """Flow pages whose code changed since they were checked.

    Pages stamped with file fingerprints (`own-guide stamp`) are judged by content; older
    pages with only a `checked_commit` fall back to comparing against that commit.
    """
    top = toplevel(cwd)
    flows_dir = guide_dir / "flows"
    if not top or not flows_dir.is_dir():
        return []
    stale: list[dict[str, Any]] = []
    for page in sorted(flows_dir.glob("*.md")):
        meta = frontmatter.parse(page.read_text(encoding="utf-8"))
        files = [f for f in meta.get("files", []) if isinstance(f, str) and f.strip()]
        rel = f"flows/{page.name}"
        stamped = _stamped_hashes(meta)
        if files and stamped:
            now = file_hashes(top, files)
            # A file that is gone now always counts, even if it was already gone when stamped:
            # the page still describes code that doesn't exist.
            changed = [f for f in files if now.get(f) == "missing" or now.get(f) != stamped.get(f)]
            if changed:
                stale.append({"page": rel, "changed": changed, "reason": "code changed since the page was checked"})
            continue
        commit = str(meta.get("checked_commit") or "").strip()
        if not commit or not files:
            continue
        if not commit_exists(top, commit):
            stale.append({"page": rel, "changed": [], "reason": "checked against a code version this copy doesn't have"})
            continue
        diff = git(["diff", "--name-only", "--no-renames", commit, "--", *files], top)
        changed = [p for p in diff.out.splitlines() if p]
        missing = [f for f in files if not (Path(top) / f).exists()]
        changed += [f for f in missing if f not in changed]
        if changed:
            stale.append({"page": rel, "changed": changed, "reason": "code changed since the page was checked"})
    return stale


def hotspots(cwd: str | Path, patterns: list[str], days: int = 90, top_n: int = 10) -> list[dict[str, Any]]:
    """Files changed most often in the last `days` days (bots and ignored files left out)."""
    result = git(["log", f"--since={days}.days.ago", "--no-merges", "--format=@@%an", "--name-only"], cwd, timeout=30)
    if result.code != 0:
        return []
    counts: Counter[str] = Counter()
    skip = False
    for line in result.out.splitlines():
        if line.startswith("@@"):
            skip = "[bot]" in line.lower() or line.lower().endswith("bot")
            continue
        if line and not skip and not is_ignored(line, patterns):
            counts[line] += 1
    return [{"file": f, "changes": n} for f, n in counts.most_common(top_n)]
