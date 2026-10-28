"""The three automatic moments: a session starting, Claude's first code edit, and Claude's turn ending.

session_start() - hands Claude the short standing instructions plus today's facts for this
    project (or nothing at all when Own is switched off everywhere). It also records what
    the working copy looks like now, so later only *this session's* code changes count.
edit_check()    - holds back Claude's first code edit of each piece of work, once, so the person
    sees what is about to change before it changes (and gets their call and their line).
stop_check()    - when a turn ends after enough code changed, tells Claude (once per set of
    changes) to update the guide, show what changed and offer the quiz. Otherwise stays silent.

All read the hook's JSON from stdin and must never break a session: every failure ends
in silence, not an error.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from . import gitinfo, guide, identity, ownership, render, schedule, state

RULES = """\
{Person} asked for the following while Own is on. None of it may slow building, pushing or deploying beyond \
what they choose.
1. Show before you ask: never ask {person} to predict, guess or answer anything about code they haven't been \
shown in a picture or walk.
2. While building: when you make a choice the plan or {person} did not settle (a library or service, the shape \
of stored data, a tradeoff, permissions or security, something hard to undo, anything that differs from the plan), \
add one plain line right away under "## Inbox" in {guide}/CODE-DECISIONS.md: what you chose and why. If the \
choice changes the plan, ask them first instead.
3. Changing code: Own holds back your first code edit of each piece of work, once. Then, unless it's a small fix, \
load the `own` skill and follow "Starting a change": show the "about to change" picture, ask "Your call" if the \
change has a real fork, offer "Your line"; then make the edit again and keep building.
4. Plans you write end with "## After this ships, you'll be able to answer:" and 3 plain questions (how it runs, \
why it is built that way, where to look first if it breaks).
5. When {person} reports a bug (not errors you hit yourself while building): if they say it's urgent, just fix it. \
Otherwise run `{tool} seen <the 3 likeliest files>`. Only if it says "ask_guess": true, ask one AskUserQuestion \
"Where would you look first?" with those 3 places plus "Not sure, just fix it", and after the fix say how close \
the guess was. Otherwise don't ask: fix it, then show the code walk with the broken step marked (the `own` \
skill's "Bug reported by them").
6. When {person} says "let me write this part": run "Your line" from the `own` skill, with a 5-15 line gap.
7. When a message from Own says code changed: load the `own` skill and run its end-of-work routine (update the \
guide, show the Before/After code walk, then offer the quiz card). Never ask quiz questions in the middle of \
building.
8. After {person} skips or postpones a card, or reports a problem while answering one, show no other learning \
card in that turn.
9. Busy: when {person} says they're short on time or picks "Busy today", run `{tool} busy`. Until the day ends, \
decide forks and write lines yourself without asking, and record each with `{tool} owned call|line ... --who \
claude --why busy`. Pictures are still shown and saved.
10. Talk about all of this in plain words; never mention internal names (hooks, state files, stop checks).
11. "/own off here" or "/own off": run `{tool} pause --here` or `{tool} pause` at once, then stop all of the \
above.
"""

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

MAX_NAME, MAX_BACKGROUND = 60, 200


def clean_profile_value(value: Any, limit: int) -> str:
    """One short line of plain text: profile values are read out to Claude, so no line breaks, bounded length."""
    return " ".join(str(value or "").split())[:limit]


def person(settings: dict[str, Any]) -> str:
    """What to call the person in Own's notes: their name from settings, or "the user"."""
    return clean_profile_value(settings.get("name"), MAX_NAME) or "the user"


def profile_line(settings: dict[str, Any]) -> str:
    """One line about the person, from their profile (`own-guide profile`)."""
    name = clean_profile_value(settings.get("name"), MAX_NAME)
    background = clean_profile_value(settings.get("background"), MAX_BACKGROUND)
    who = f"- The person you're working with is {name}." if name else (
        "- No name is set (`/own profile` sets one): speak to them as \"you\".")
    if background:
        who += (f" They already know {background} well: when explaining a new idea, compare it to that, and say "
                "where the comparison stops.")
    return who

TOOL_LINE = (
    "- Own's tool, for every Own step: `{tool} <command>`. Run it exactly like that with the shell: the bare "
    "name `own-guide` is not found here."
)
TOOL_SWAP = (
    " On this machine it differs from the `own` skill's examples: wherever the skill writes "
    "`" + state.DEFAULT_TOOL_COMMAND + " X`, run `{tool} X` instead."
)


def _read_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def project_status(cwd: str, entry: dict[str, Any], st: dict[str, Any], settings: dict[str, Any],
                   today: dt.date) -> dict[str, Any]:
    """Today's facts for one project: what's due, what the daily card should offer."""
    folder = entry["folder"]
    exists = guide.exists(folder)
    tracked = gitinfo.tracked_file_count(cwd, settings["ignore"])
    existing_code = tracked >= settings["existing_repo_min_files"]
    answer = st["first_map"].get("answer")
    later_today = answer == "later" and st["first_map"].get("date") == today.isoformat()
    first_map = (not exists) and existing_code and answer != "never" and not later_today
    due_total = schedule.due_count(st["questions"], today)
    weekly = render.weekly_line(folder, st, today)
    tour = bool(settings["tour_offer"]) and exists
    shown_today = st["daily_card"].get("last_shown") == today.isoformat()
    card_due = (not shown_today) and bool(first_map or due_total or st["pending_quiz"] or tour or weekly)
    return {
        "project": folder,
        "guide_dir": str(guide.guide_dir(folder)),
        "guide_exists": exists,
        "tracked_files": tracked,
        "first_map_offer": first_map,
        "due_now": due_total,
        "due_this_sitting": [q["id"] for q in schedule.due(st["questions"], today, settings["max_returns_per_sitting"])],
        "pending_quiz": st["pending_quiz"],
        "tour_offer": tour,
        "weekly_line": weekly,
        "card_due_today": card_due,
        "card_shown_today": shown_today,
        "paused": bool(st.get("paused")),
        "busy_today": ownership.busy_today(settings, today),
        "level": st["level"],
    }


def _status_lines(status: dict[str, Any], stale: list[dict[str, Any]], tool: str) -> list[str]:
    tool_line = TOOL_LINE.format(tool=tool)
    if tool != state.DEFAULT_TOOL_COMMAND:
        tool_line += TOOL_SWAP.format(tool=tool)
    lines = [
        tool_line,
        f"- This project's guide: {status['guide_dir']}/ (outside the repo; guide files never go into the repo).",
    ]
    if status["guide_exists"]:
        lines.append("- The guide exists.")
    elif status["first_map_offer"]:
        lines.append(f"- No guide yet, and this is an existing project ({status['tracked_files']} files): "
                     "today's card offers to build the first map.")
    else:
        lines.append("- No guide yet: it starts with the first feature built here.")
    if status["due_now"]:
        lines.append(f"- Questions waiting to come back: {status['due_now']} (up to "
                     f"{len(status['due_this_sitting'])} per sitting; `{tool} due` lists them).")
    if status["pending_quiz"]:
        lines.append(f"- A quiz was saved for later: \"{status['pending_quiz'].get('feature', '')}\".")
    if stale:
        lines.append(f"- Guide pages that may be out of date: {len(stale)} (`{tool} stale`).")
    if status["busy_today"]:
        lines.append("- Busy today: decide forks and write lines yourself, without the Your call / Your line / "
                     "Find it yourself cards; record each one as Claude's. Pictures are still shown and saved.")
    if status["weekly_line"]:
        lines.append(f"- Weekly line for today's card: \"{status['weekly_line']}\"")
    if status["card_due_today"]:
        lines.append("- Today's card is due: show it at the end of your first finished turn in this session "
                     "(never before handling their request), using the `own` skill's daily card routine.")
    return lines


def _hook_json(event: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def _record_baseline(st: dict[str, Any], top: str, session_id: str, cwd: str, today: dt.date) -> None:
    current = st["worktrees"].get(top)
    if current and session_id and current.get("session_id") == session_id:
        return  # resumed or compacted: keep this session's starting picture
    base = gitinfo.head(cwd)
    st["worktrees"][top] = {
        "session_id": session_id,
        "base": base,
        "snap": gitinfo.snapshot(cwd, base),
        "started": today.isoformat(),
        "handled": [],
    }


def session_start(raw_stdin: str) -> str:
    payload = _read_payload(raw_stdin)
    state.ensure_tool_link()
    tool = state.tool_command()
    settings = state.load_settings()
    if not settings.get("enabled", True):
        return ""
    cwd = payload.get("cwd") or "."
    resolved = identity.resolve(cwd, create=True)
    if resolved is None:
        return ""
    if resolved["status"] == "ambiguous":
        cand = resolved["candidate"]["folder"]
        name = identity.slug(Path(resolved["info"]["main_root"]).name)
        return _hook_json("SessionStart", (
            f"Own (a learning plugin {person(settings)} installed): this repo ({name}) might be the same project as "
            f"the existing guide '{cand}' in ~/code-guides/. At the end of your first finished turn, ask once with "
            f"AskUserQuestion: same project, or a new one? Then run `{tool} link {cand}` or `{tool} register-new`. "
            "Until then, do nothing else for Own here."
        ))
    entry = resolved["entry"]
    today = state.today()
    top = resolved["info"]["toplevel"]
    with state.edit_state(entry["folder"]) as st:
        if st.get("paused"):
            return _hook_json("SessionStart", (
                f"Own (a learning plugin {person(settings)} installed) is paused in this project. Do nothing for it "
                f"unless they type /own on here (then run `{tool} resume --here`)."
            ))
        _record_baseline(st, top, str(payload.get("session_id") or ""), cwd, today)
        status = project_status(cwd, entry, st, settings, today)
    stale = gitinfo.stale_pages(cwd, guide.guide_dir(entry["folder"])) if status["guide_exists"] else []
    who = person(settings)
    text = (
        f"Own (\"own the code\", a learning plugin {who} installed) is on in this project. Facts for this session:\n"
        + "\n".join([profile_line(settings), *_status_lines(status, stale, tool)])
        + "\n\n"
        + RULES.format(guide=status["guide_dir"], tool=tool, person=who, Person=who[:1].upper() + who[1:])
    )
    return _hook_json("SessionStart", text)


def _code_file(target: str, cwd: str, top: str, settings: dict[str, Any]) -> bool:
    """Is this a file of the project's code (inside the repo, not ignored, not a guide)?"""
    path = Path(target)
    if not path.is_absolute():
        path = Path(cwd) / path
    path = path.resolve()
    try:
        rel = path.relative_to(Path(top)).as_posix()
    except ValueError:
        return False  # outside the repo: plans, memory, scratch files
    guides = state.guides_root().expanduser().resolve()
    if path == guides or guides in path.parents:
        return False
    if gitinfo.is_ignored(rel, settings["ignore"]):
        return False
    return gitinfo.git(["check-ignore", "-q", "--", rel], top).code != 0


def edit_check(raw_stdin: str) -> str:
    """Hold back Claude's first code edit of a piece of work, once, with a note only Claude sees.

    Mia asks for a 24-hour grace period on expired coupons. Before Claude's first edit to
    `shop/coupons.py` lands, Own stops it once: Claude first shows her what is about to change, asks her
    call on the fork it found, offers her the line that carries the change, then makes the same edit
    again. Every later edit goes through until the guide is updated (`synced`), which starts a new piece
    of work. Silent for helper agents, plan mode, busy days, paused projects and non-code files.
    """
    payload = _read_payload(raw_stdin)
    if payload.get("agent_id") or payload.get("permission_mode") == "plan":
        return ""
    if payload.get("tool_name") not in EDIT_TOOLS:
        return ""
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(target, str) or not target.strip():
        return ""
    settings = state.load_settings()
    today = state.today()
    if not settings.get("enabled", True) or ownership.busy_today(settings, today):
        return ""
    cwd = payload.get("cwd") or "."
    resolved = identity.resolve(cwd, create=False)
    if resolved is None or resolved["status"] not in ("known", "new"):
        return ""
    top = resolved["info"]["toplevel"]
    if not _code_file(target, cwd, top, settings):
        return ""
    with state.edit_state(resolved["entry"]["folder"]) as st:
        if st.get("paused"):
            return ""
        if top not in st["worktrees"]:
            _record_baseline(st, top, str(payload.get("session_id") or ""), cwd, today)
        record = st["worktrees"][top]
        if record.get("edit_gate"):
            return ""
        record["edit_gate"] = True
    reason = (
        f"Own held back this first code change of the current piece of work (only this once). Before making it: "
        f"unless this is a small fix (one file, about 15 changed lines or fewer), load the `own` skill and follow "
        f"\"Starting a change\": show {person(settings)} the \"about to change\" picture (the flow, the code walk "
        "and who calls whom for the part you're changing, with the steps that will change marked), ask \"Your "
        "call\" if the change has a real fork, and offer \"Your line\". Then make this same edit again and keep "
        "building: Own won't hold back another edit until this work is wrapped up."
    )
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}})


def stop_check(raw_stdin: str) -> str:
    payload = _read_payload(raw_stdin)
    if payload.get("stop_hook_active") or payload.get("permission_mode") == "plan":
        return ""
    settings = state.load_settings()
    if not settings.get("enabled", True):
        return ""
    cwd = payload.get("cwd") or "."
    resolved = identity.resolve(cwd, create=False)
    if resolved is None or resolved["status"] not in ("known", "new"):
        return ""
    entry = resolved["entry"]
    top = resolved["info"]["toplevel"]
    today = state.today()
    with state.edit_state(entry["folder"]) as st:
        if st.get("paused"):
            return ""
        record = st["worktrees"].get(top)
        if not record:
            _record_baseline(st, top, str(payload.get("session_id") or ""), cwd, today)
            return ""
        current = gitinfo.snapshot(cwd, record.get("base"))
        changes = gitinfo.compare(record.get("snap") or {}, current)
        ok, info = gitinfo.meaningful(changes, settings)
        if not ok:
            # A small fix ended here: the next request is a new piece of work, so its first edit is held once.
            # Not while the person is writing their line: the turn ended to wait for them, the work goes on.
            if not record.get("line_pending"):
                record["edit_gate"] = False
            return ""
        mark = gitinfo.fingerprint(changes, current)
        if mark in record.setdefault("handled", []):
            return ""
        record["handled"] = (record["handled"] + [mark])[-20:]
    files = ", ".join(info["top_files"])
    reason = (
        f"Own: this turn changed code ({info['files']} files, about {info['lines']} lines: {files}). "
        f"Before you finish, load the `own` skill and run its end-of-work routine: update the guide in "
        f"{guide.guide_dir(entry['folder'])}/, show {person(settings)} the Before/After code walk of what changed "
        "(flow, code walk and who calls whom), then offer the quiz card "
        "(Walk me through it first / Start / Later / Skip this one). "
        "Keep it short and don't redo any of the work."
    )
    return json.dumps({"decision": "block", "reason": reason})


def mark_line_pending(cwd: str, folder: str, top: str, pending: bool) -> None:
    """'Your line' was handed to the person (or came back): keep this piece of work open while they write it."""
    with state.edit_state(folder) as st:
        if top not in st["worktrees"]:
            _record_baseline(st, top, "", cwd, state.today())
        st["worktrees"][top]["line_pending"] = pending


def mark_synced(cwd: str, folder: str, top: str) -> dict[str, Any]:
    """The guide now matches the code: measure future changes from here."""
    today = state.today()
    base = gitinfo.head(cwd)
    with state.edit_state(folder) as st:
        record = st["worktrees"].setdefault(top, {"session_id": "", "handled": []})
        # A new piece of work starts here, so its first code edit is held back once again (edit_check).
        record.update(base=base, snap=gitinfo.snapshot(cwd, base), handled=[], edit_gate=False, line_pending=False)
        st["guide"].update(synced_at=today.isoformat(), synced_commit=base)
    return {"synced_commit": base, "synced_at": today.isoformat()}
