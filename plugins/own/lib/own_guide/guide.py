"""The guide files themselves: creating an empty guide, and counting what is in one.

Counting relies on the formats the `own` skill writes (see skills/own/references):
- FLOW.md lists flows as table rows whose last cell is a `flows/<name>.md` link or "not written yet".
- CODE-DECISIONS.md has an index table whose rows start with `| <number> |`.
- LEARNINGS.md has one `### ` heading per idea.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import state

_DECISION_ROW = re.compile(r"^\|\s*\d+\s*\|")
_FLOW_ROW = re.compile(r"^\|.*(flows/[\w.-]+\.md|not written yet).*\|\s*$", re.IGNORECASE)


def guide_dir(folder: str) -> Path:
    return state.project_dir(folder)


def exists(folder: str) -> bool:
    return (guide_dir(folder) / "FLOW.md").is_file()


def init(folder: str, project_name: str, today: str) -> list[str]:
    """Create the empty guide files that don't exist yet. Returns what was created."""
    base = guide_dir(folder)
    (base / "flows").mkdir(parents=True, exist_ok=True)
    files = {
        "FLOW.md": (
            f"# How {project_name} runs\n\n"
            "> Your private guide to this code, kept by Claude in plain words. It lives outside the repo.\n"
            f"> Started: {today}\n\n"
            "## The whole-project map\n\n"
            "_Not drawn yet._\n\n"
            "## The flows\n\n"
            "| Flow | What it does | Starts at | Page |\n"
            "|---|---|---|---|\n"
        ),
        "CODE-DECISIONS.md": (
            f"# Code decisions: why {project_name} is built this way\n\n"
            "| # | Decision | Who decided | Still true? |\n"
            "|---|---|---|---|\n\n"
            "## Inbox\n\n"
            "<!-- One line per choice made while building. Turned into full entries when the work is done. -->\n"
        ),
        "LEARNINGS.md": (
            f"# Learnings: new ideas met in {project_name}\n\n"
            "Each idea: how this project uses it, with a link to the full entry in your knowledge book "
            "(`~/code-guides/_knowledge/`).\n"
        ),
    }
    created = []
    for name, text in files.items():
        path = base / name
        if not path.exists():
            path.write_text(text, encoding="utf-8")
            created.append(str(path))
    book = state.guides_root() / "_knowledge"
    (book / "frameworks").mkdir(parents=True, exist_ok=True)
    index = book / "INDEX.md"
    if not index.exists():
        index.write_text(
            "# Your knowledge book\n\n"
            "One entry per idea, written once, shared by every project. Each entry has: the idea in general, "
            "one level deeper, like something you already know, and the projects where you met it.\n\n"
            "| Idea | Area | Met in |\n|---|---|---|\n",
            encoding="utf-8",
        )
        created.append(str(index))
    return created


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def flow_rows(flow_text: str) -> list[str]:
    """Rows of the flow list: only table rows under the `## The flows` heading count."""
    rows, inside = [], False
    for line in flow_text.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == "## the flows"
        elif inside and _FLOW_ROW.match(line.strip()):
            rows.append(line)
    return rows


def counts(folder: str) -> dict[str, Any]:
    base = guide_dir(folder)
    flow_text = _read(base / "FLOW.md")
    flow_rows_found = flow_rows(flow_text)
    pages = sorted(p.stem for p in (base / "flows").glob("*.md")) if (base / "flows").is_dir() else []
    decisions = sum(1 for line in _read(base / "CODE-DECISIONS.md").splitlines() if _DECISION_ROW.match(line.strip()))
    ideas = sum(1 for line in _read(base / "LEARNINGS.md").splitlines() if line.startswith("### "))
    return {
        "flows_listed": max(len(flow_rows_found), len(pages)),
        "flow_pages": pages,
        "decisions": decisions,
        "ideas": ideas,
    }
