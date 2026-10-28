"""Where Own keeps its files, and safe reading and writing of its JSON files.

Everything lives under one personal folder, `~/code-guides/` (override with the
OWN_GUIDES_DIR environment variable, which the tests use). Writes are atomic - a
temp file renamed over the old one - and happen under a file lock, so two Claude
sessions open on the same project cannot corrupt each other's state.
"""

from __future__ import annotations

import contextlib
import copy
import datetime as dt
import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # Windows has no fcntl. Writes stay atomic; only the cross-session lock is skipped.
    fcntl = None  # type: ignore[assignment]

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    # The person's profile (`own-guide profile`): what Claude calls them, and what they already know
    # well, for "like something you already know" comparisons. Empty = "you", no comparisons assumed.
    "name": "",
    "background": "",
    # "Busy today" (`own-guide busy`): on this date Claude decides forks and writes lines itself,
    # without the ownership cards. Any other value (or "") = not busy.
    "busy_day": "",
    # A change counts as "a feature worth a quiz" when it is at least this big.
    "min_lines": 40,
    "min_files": 2,
    "min_lines_multi_file": 15,
    "new_file_min_lines": 10,
    "quiz_min": 3,
    "quiz_max": 5,
    "max_returns_per_sitting": 2,
    "tour_offer": True,
    # A repo with at least this many (non-ignored) tracked files gets the first-map card.
    "existing_repo_min_files": 15,
    # Paths that never count as code changes (matched against the path and the file name).
    "ignore": [
        "*.md", "*.txt", "*.rst", "*.csv", "*.log",
        "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
        "Pipfile.lock", "Podfile.lock", "pubspec.lock", "Cargo.lock", "go.sum",
        "*.min.js", "*.min.css", "*.map", "*.pyc",
        "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg", "*.ico", "*.pdf",
        "*.mp4", "*.mov", "*.mp3", "*.wav", "*.zip", "*.docx", "*.pptx", "*.xlsx",
        "*.g.dart", "*.freezed.dart", "*.generated.*",
        "dist/*", "*/dist/*", "build/*", "*/build/*", "node_modules/*", "*/node_modules/*",
        ".venv/*", "*/.venv/*", "venv/*", "__pycache__/*", "*/__pycache__/*",
        ".claude/*", "screenshots/*", "*/screenshots/*", ".dart_tool/*", "Pods/*",
    ],
}

DEFAULT_STATE: dict[str, Any] = {
    "schema": 1,
    "paused": False,
    "guide": {"synced_at": None, "synced_commit": None},
    # Per working copy (main folder or a worktree): what the tree looked like when the
    # session started or the guide was last updated. Keyed by the copy's top folder.
    "worktrees": {},
    "daily_card": {"last_shown": None},
    "weekly_line": {"last_week": None},
    "first_map": {"answer": None},  # None, "later" (with date) or "never"
    "level": 1,
    "all_correct_streak": 0,
    "next_question_id": 1,
    "questions": [],
    "quizzes": [],
    "pending_quiz": None,
    "progress_log": [],
    # Walks through a flow (see walks.py), and the last positions the right answer was put in.
    "walks": [],
    "answer_slots": [],
    # What the guide files looked like when the person was last shown them: "note" for the
    # "your guide changed" note in chat, "viewer" for the guide page. None = never shown yet.
    "guide_seen": {"note": None, "viewer": None},
    # Calls the person made, lines they wrote, things they found themselves - and the ones Claude
    # handled for them (see ownership.py).
    "ownership": [],
}


def guides_root() -> Path:
    """The personal folder that holds every project's guide."""
    override = os.environ.get("OWN_GUIDES_DIR")
    return Path(override).expanduser() if override else Path.home() / "code-guides"


def today() -> dt.date:
    """Today's date. OWN_TODAY=YYYY-MM-DD fakes it, for tests and 'days later' trials."""
    override = os.environ.get("OWN_TODAY")
    return dt.date.fromisoformat(override) if override else dt.date.today()


def _launcher() -> Path:
    """The own-guide launcher of the copy of the plugin that is running right now."""
    return Path(__file__).resolve().parents[2] / "bin" / "own-guide"


def tool_link() -> Path:
    """A stable address for the tool, kept pointing at the running copy (see ensure_tool_link)."""
    return guides_root() / ".bin" / "own-guide"


def ensure_tool_link() -> Path:
    """Point ~/code-guides/.bin/own-guide at the launcher of the copy that is running now.

    Each plugin version installs into its own folder, so the link is re-pointed on every run.
    Never raises: if the link can't be made, tool_command() falls back to the full launcher path.
    """
    target = _launcher()
    link = tool_link()
    try:
        if link.is_symlink() and Path(os.readlink(link)) == target:
            return link
        link.parent.mkdir(parents=True, exist_ok=True)
        tmp = link.with_name(f".own-guide.{os.getpid()}.tmp")
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        os.symlink(target, tmp)
        os.replace(tmp, link)
    except OSError:
        pass
    return link


def tool_command() -> str:
    """How Claude must run the tool.

    Always through python3: in the desktop app the plugin's bin folder is not on PATH, and
    lean-ctx's command allowlist refuses the bare `own-guide` name but allows `python3 -I <file>`.
    """
    link = tool_link()
    if link.is_file() and link.resolve() == _launcher():
        default = Path.home() / "code-guides" / ".bin" / "own-guide"
        shown = "~/code-guides/.bin/own-guide" if link == default else shlex.quote(str(link))
    else:  # no link, or it still points at another copy: name this copy directly
        shown = shlex.quote(str(_launcher()))
    return f"python3 -I {shown}"


DEFAULT_TOOL_COMMAND = "python3 -I ~/code-guides/.bin/own-guide"


@contextlib.contextmanager
def locked(path: Path) -> Iterator[None]:
    """Hold an exclusive lock on `path` (via a sibling .lock file) for the block (no lock where fcntl is missing)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    with open(path.with_name(path.name + ".lock"), "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read_json(path: Path, default: Any) -> Any:
    """Read JSON, or return `default` when the file is missing.

    A file that is not valid JSON is moved aside (never silently overwritten), so a
    bad write can't destroy someone's progress without a trace.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(default)
    except json.JSONDecodeError:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path.rename(path.with_name(f"{path.name}.corrupt-{stamp}"))
        return copy.deepcopy(default)


def write_json(path: Path, data: Any) -> None:
    """Write JSON atomically: a temp file in the same folder, renamed over the old one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def settings_path() -> Path:
    return guides_root() / "settings.json"


def load_settings() -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    merged.update(read_json(settings_path(), {}))
    return merged


def save_settings(changes: dict[str, Any]) -> None:
    path = settings_path()
    with locked(path):
        data = read_json(path, {})
        data.update(changes)
        write_json(path, data)


def project_dir(folder: str) -> Path:
    return guides_root() / folder


def state_path(folder: str) -> Path:
    return project_dir(folder) / "state.json"


def _fill_defaults(state: dict[str, Any]) -> dict[str, Any]:
    for key, value in DEFAULT_STATE.items():
        if key not in state:
            state[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(state[key], dict):
            for sub_key, sub_value in value.items():
                state[key].setdefault(sub_key, copy.deepcopy(sub_value))
    return state


def load_state(folder: str) -> dict[str, Any]:
    return _fill_defaults(read_json(state_path(folder), {}))


@contextlib.contextmanager
def edit_state(folder: str) -> Iterator[dict[str, Any]]:
    """Load a project's state under the lock, let the block change it, save it."""
    path = state_path(folder)
    with locked(path):
        state = load_state(folder)
        yield state
        write_json(path, state)
