"""Pictures of the guide's diagrams, because the desktop app shows Mermaid as code.

Example: FLOW.md holds the whole-project map as a ```mermaid block. In the app's file pane
that appears as 40 lines of `flowchart TD ...` text, not a map. `render_page()` draws each
block to `diagrams/<page>-<n>.png` with the Mermaid command-line tool (mmdc) and puts the
picture right above the block:

    <!-- own:diagram flow-1 sha=3f2a9c1e -->
    ![flow-1: picture of the diagram below](diagrams/flow-1.png)
    ```mermaid
    flowchart TD ...

The sha is a fingerprint of the block's text: an unchanged block is never drawn twice.
mmdc runs as a child process of this tool, so shell allowlists that gate Claude's own
commands (lean-ctx) don't block it.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_BLOCK = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
_MARKER = re.compile(r"^<!-- own:diagram (\S+) sha=([0-9a-f]+) -->\n!\[[^\]]*\]\([^)]*\)\n", re.MULTILINE)

# Lines of a sequence diagram that are not messages (arrows).
_NOT_A_MESSAGE = re.compile(
    r"^(?:sequenceDiagram|autonumber|note|participant|actor|loop|alt|else|end|opt|par|and|rect|activate|"
    r"deactivate|critical|break|box|title|create|destroy|%%)\b",
    re.IGNORECASE,
)
_ARROW = re.compile(r"(?:<<)?-{1,2}(?:>>|>|x|\))")
_STEP = re.compile(r"^\d+\.\s")


def count_arrows(code: str) -> int:
    """Messages in a Mermaid sequence diagram: `Mia->>Web: clicks Pay` is one, a Note is none."""
    count = 0
    for line in code.splitlines():
        line = line.strip()
        if not line or _NOT_A_MESSAGE.match(line) or ":" not in line:
            continue
        if _ARROW.search(line.split(":", 1)[0]):
            count += 1
    return count


def count_steps(text: str) -> int:
    """Top-level numbered items under the page's `## Step by step` heading."""
    steps, inside = 0, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip().lower() == "## step by step"
        elif inside and _STEP.match(line):
            steps += 1
    return steps


def check_numbering(text: str) -> list[str]:
    """Why a flow page's picture numbers wouldn't match its numbered steps (empty list = they match).

    Example: the picture's arrow 6 must be step 6 on the page and stop 6 on a walk. That needs
    `autonumber` in the sequence diagram (Mermaid then prints 1, 2, 3... on the arrows) and exactly
    one arrow per step. Pages without a sequence diagram have nothing to check.
    """
    code = next((m.group(1) for m in _BLOCK.finditer(text) if m.group(1).lstrip().startswith("sequenceDiagram")), None)
    if code is None:
        return []
    problems = []
    if not any(line.strip().lower().split(" ")[0] == "autonumber" for line in code.splitlines()):
        problems.append("the sequence diagram has no `autonumber` line, so its arrows carry no numbers")
    arrows, steps = count_arrows(code), count_steps(text)
    if not steps:
        problems.append("there is no numbered list under `## Step by step` for the arrow numbers to match")
    elif arrows != steps:
        problems.append(f"the picture has {arrows} arrows but `## Step by step` has {steps} steps; "
                        "make it exactly one arrow per step, in the same order")
    return problems


def numbering_report(guide_dir: Path) -> list[dict[str, Any]]:
    """Every flow page whose picture numbers don't match its steps, with the reasons."""
    report = []
    for page in sorted((guide_dir / "flows").glob("*.md")) if (guide_dir / "flows").is_dir() else []:
        problems = check_numbering(page.read_text(encoding="utf-8"))
        if problems:
            report.append({"page": f"flows/{page.name}", "problems": problems})
    return report

_CANDIDATES = (
    "~/.npm-global/bin/mmdc",
    "~/.npm-global/lib/node_modules/claude-mermaid/node_modules/.bin/mmdc",
    "/opt/homebrew/bin/mmdc",
    "/usr/local/bin/mmdc",
)


def find_mmdc() -> str | None:
    """The Mermaid drawing tool: $OWN_MMDC, then PATH, then the usual install places."""
    override = os.environ.get("OWN_MMDC")
    if override:
        # Return the expanded path: a child process gets no shell, so a literal "~" would not be found.
        expanded = Path(override).expanduser()
        return str(expanded) if expanded.is_file() else None
    on_path = shutil.which("mmdc")
    if on_path:
        return on_path
    for candidate in _CANDIDATES:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def _draw(mmdc: str, code: str, out: Path) -> str | None:
    """Draw one diagram to `out` (PNG). Returns an error message, or None on success."""
    out.parent.mkdir(parents=True, exist_ok=True)
    # Work next to the final picture, so the closing os.replace never crosses disks.
    with tempfile.TemporaryDirectory(prefix=".own-diagram-", dir=out.parent) as tmp:
        source = Path(tmp) / "diagram.mmd"
        source.write_text(code, encoding="utf-8")
        drawn = Path(tmp) / "diagram.png"
        env = dict(os.environ)
        # mmdc is a node script; make sure the usual node locations are searched.
        env["PATH"] = os.pathsep.join([env.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"])
        try:
            proc = subprocess.run(
                [mmdc, "-i", str(source), "-o", str(drawn), "-b", "white", "-s", "2"],
                capture_output=True, text=True, timeout=120, env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return str(exc)
        if proc.returncode != 0 or not drawn.is_file():
            lines = (proc.stderr or proc.stdout).strip().splitlines()
            return lines[-1] if lines else f"mmdc exited with {proc.returncode}"
        os.replace(drawn, out)
    return None


def _prefix(page: Path, diagrams_dir: Path) -> str:
    """A picture-name prefix unique per page: FLOW.md → "flow", flows/who-am-i.md → "flows-who-am-i"."""
    try:
        rel = page.relative_to(diagrams_dir.parent).with_suffix("")
    except ValueError:
        rel = Path(page.stem)
    return re.sub(r"[^a-z0-9]+", "-", rel.as_posix().lower()).strip("-") or "page"


def render_page(page: Path, diagrams_dir: Path, mmdc: str) -> dict[str, Any]:
    """Draw every Mermaid block in `page` and keep a picture line above each one."""
    text = page.read_text(encoding="utf-8")
    prefix = _prefix(page, diagrams_dir)
    old_sha = {m.group(1): m.group(2) for m in _MARKER.finditer(text)}
    body = _MARKER.sub("", text)  # markers are re-written below, so they never pile up
    pieces: list[str] = []
    cursor = 0
    report: dict[str, Any] = {"page": str(page), "drawn": [], "unchanged": [], "failed": []}
    for index, block in enumerate(_BLOCK.finditer(body), start=1):
        name = f"{prefix}-{index}"
        code = block.group(1)
        sha = _sha(code)
        picture = diagrams_dir / f"{name}.png"
        if old_sha.get(name) == sha and picture.is_file():
            report["unchanged"].append(name)
            marker_sha: str | None = sha
        else:
            error = _draw(mmdc, code, picture)
            if error is None:
                report["drawn"].append(name)
                marker_sha = sha
            else:
                report["failed"].append({"diagram": name, "error": error})
                # Keep showing the previous picture, under its old fingerprint, so the next run retries.
                marker_sha = old_sha.get(name) if picture.is_file() else None
        pieces.append(body[cursor:block.start()])
        if marker_sha:
            rel = os.path.relpath(picture, page.parent)
            pieces.append(f"<!-- own:diagram {name} sha={marker_sha} -->\n![{name}: picture of the diagram below]({rel})\n")
        cursor = block.start()
    pieces.append(body[cursor:])
    new_text = "".join(pieces)
    if new_text != text:
        page.write_text(new_text, encoding="utf-8")
    return report


def render_guide(guide_dir: Path, book_dir: Path | None = None) -> dict[str, Any]:
    """Draw the diagrams of FLOW.md and every flow page (and framework pages in the book).

    `numbering` lists flow pages whose arrow numbers don't match their steps; it is checked even
    when the drawing tool is missing, because it is about the page, not the picture.
    """
    numbering = numbering_report(guide_dir)
    mmdc = find_mmdc()
    if mmdc is None:
        return {"mmdc": None, "pages": [], "numbering": numbering, "note": (
            "The Mermaid drawing tool (mmdc) isn't installed, so diagrams stay as code. It is free: "
            "`npm install -g @mermaid-js/mermaid-cli`. Nothing was changed."
        )}
    pages = [guide_dir / "FLOW.md", *sorted((guide_dir / "flows").glob("*.md"))]
    reports = [render_page(p, guide_dir / "diagrams", mmdc) for p in pages if p.is_file()]
    if book_dir is not None and (book_dir / "frameworks").is_dir():
        reports += [render_page(p, book_dir / "diagrams", mmdc) for p in sorted((book_dir / "frameworks").glob("*.md"))]
    return {"mmdc": mmdc, "pages": [r for r in reports if r["drawn"] or r["unchanged"] or r["failed"]],
            "numbering": numbering}
