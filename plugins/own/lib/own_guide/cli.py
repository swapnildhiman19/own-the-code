"""`own-guide <command>`: what the `own` skill (and the two hooks) call.

Every command prints JSON or short plain text and exits 0 on success. Commands that need
a project resolve it from the current folder, the same way the hooks do.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

from . import (__version__, diagrams, frontmatter, gitinfo, guide, hooks, identity, ownership, render, schedule, state,
               viewer, walkpage, walks)


def _out(data: Any) -> int:
    print(json.dumps(data, indent=2) if not isinstance(data, str) else data)
    return 0


def _fail(message: str) -> int:
    print(json.dumps({"error": message}), file=sys.stderr)
    return 1


def _project(cwd: str = ".") -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = identity.resolve(cwd, create=True)
    if resolved is None:
        raise SystemExit(_fail("not inside a git repository"))
    if resolved["status"] == "ambiguous":
        raise SystemExit(_fail(
            f"this repo may be the same project as '{resolved['candidate']['folder']}': "
            f"run `{state.tool_command()} link <folder>` or `{state.tool_command()} register-new` first"
        ))
    return resolved["entry"], resolved["info"]


def cmd_session_start(_: argparse.Namespace) -> int:
    try:
        text = hooks.session_start(sys.stdin.read())
    except Exception:  # a hook must never break the session
        return 0
    if text:
        print(text)
    return 0


def cmd_stop_check(_: argparse.Namespace) -> int:
    try:
        text = hooks.stop_check(sys.stdin.read())
    except Exception:
        return 0
    if text:
        print(text)
    return 0


def cmd_edit_check(_: argparse.Namespace) -> int:
    try:
        text = hooks.edit_check(sys.stdin.read())
    except Exception:
        return 0
    if text:
        print(text)
    return 0


def cmd_identify(_: argparse.Namespace) -> int:
    resolved = identity.resolve(".", create=False)
    return _out(resolved or {"status": "not-a-git-repo"})


def cmd_where(_: argparse.Namespace) -> int:
    entry, _info = _project()
    return _out(str(guide.guide_dir(entry["folder"])))


def cmd_status(_: argparse.Namespace) -> int:
    entry, _info = _project()
    st = state.load_state(entry["folder"])
    status = hooks.project_status(".", entry, st, state.load_settings(), state.today())
    # Per flow page: "not walked", "walked" or "got", so a tour can pick a flow the person hasn't walked yet.
    status["flow_status"] = render.summary(entry["folder"], st, state.today())["flow_status"]
    return _out(status)


def cmd_init_guide(_: argparse.Namespace) -> int:
    entry, _info = _project()
    created = guide.init(entry["folder"], entry["folder"], state.today().isoformat())
    return _out({"guide_dir": str(guide.guide_dir(entry["folder"])), "created": created})


def cmd_due(args: argparse.Namespace) -> int:
    entry, _info = _project()
    st = state.load_state(entry["folder"])
    limit = args.limit or state.load_settings()["max_returns_per_sitting"]
    return _out(schedule.due(st["questions"], state.today(), limit))


def cmd_add_question(args: argparse.Namespace) -> int:
    entry, _info = _project()
    today = state.today()
    with state.edit_state(entry["folder"]) as st:
        question = schedule.new_question(
            st["next_question_id"], today, kind=args.kind, tests=args.tests, answer=args.answer,
            links=args.link, source=args.source, feature=args.feature,
        )
        st["next_question_id"] += 1
        if args.result:
            schedule.apply_result(question, args.result, today)
        elif args.ask_tomorrow:
            schedule.ask_later(question, today)
        st["questions"].append(question)
    return _out({"id": question["id"], "status": question["status"], "next_due": question["next_due"]})


def cmd_record(args: argparse.Namespace) -> int:
    entry, _info = _project()
    today = state.today()
    with state.edit_state(entry["folder"]) as st:
        question = next((q for q in st["questions"] if q["id"] == args.id), None)
        if question is None:
            return _fail(f"no question {args.id}")
        schedule.apply_result(question, args.result, today)
    return _out({"id": question["id"], "status": question["status"], "next_due": question["next_due"]})


def _quiz_log(args: argparse.Namespace, outcome: str) -> int:
    entry, _info = _project()
    today = state.today()
    with state.edit_state(entry["folder"]) as st:
        st["quizzes"].append({
            "date": today.isoformat(), "feature": args.feature, "outcome": outcome,
            "asked": getattr(args, "asked", None), "right": getattr(args, "right", None),
        })
        if outcome == "later":
            st["pending_quiz"] = {"feature": args.feature, "since": today.isoformat()}
        elif st["pending_quiz"] and st["pending_quiz"].get("feature") == args.feature:
            st["pending_quiz"] = None
        if outcome == "done" and args.asked:
            perfect = args.right == args.asked
            st["all_correct_streak"] = st["all_correct_streak"] + 1 if perfect else 0
            if st["all_correct_streak"] >= 2:
                st["level"] += 1
                st["all_correct_streak"] = 0
            elif not perfect and st["level"] > 1:
                st["level"] -= 1
        level = st["level"]
        returns = schedule.upcoming(st["questions"], today)
    return _out({"outcome": outcome, "level": level,
                 "next_returns": [{"date": q["next_due"], "id": q["id"]} for q in returns]})


def cmd_quiz_done(args: argparse.Namespace) -> int:
    return _quiz_log(args, "done")


def cmd_quiz_later(args: argparse.Namespace) -> int:
    return _quiz_log(args, "later")


def cmd_quiz_skip(args: argparse.Namespace) -> int:
    return _quiz_log(args, "skipped")


def cmd_synced(_: argparse.Namespace) -> int:
    entry, info = _project()
    return _out(hooks.mark_synced(".", entry["folder"], info["toplevel"]))


def cmd_stamp(args: argparse.Namespace) -> int:
    """Record which code a flow page was checked against: the commit, and each listed file's fingerprint."""
    entry, info = _project()
    page = Path(args.page)
    if not page.is_absolute():
        page = guide.guide_dir(entry["folder"]) / page
    if not page.is_file():
        return _fail(f"no flow page at {page}")
    text = page.read_text(encoding="utf-8")
    files = [f for f in frontmatter.parse(text).get("files", []) if isinstance(f, str) and f.strip()]
    if not files:
        return _fail("the page header has no `files: [...]` list; add the repo-relative files the page describes")
    hashes = gitinfo.file_hashes(info["toplevel"], files)
    page.write_text(frontmatter.update(text, {
        "checked_commit": gitinfo.short_head(info["toplevel"]) or "none",
        "checked_on": state.today().isoformat(),
        "hashes": [f"{f}={hashes[f]}" for f in files],
    }), encoding="utf-8")
    missing = [f for f, h in hashes.items() if h == "missing"]
    return _out({"page": str(page), "files": len(files), "missing_files": missing})


def cmd_diagrams(_: argparse.Namespace) -> int:
    """Draw pictures of the guide's Mermaid diagrams (the app shows Mermaid as code)."""
    entry, _info = _project()
    return _out(diagrams.render_guide(guide.guide_dir(entry["folder"]), state.guides_root() / "_knowledge"))


def cmd_stale(_: argparse.Namespace) -> int:
    entry, _info = _project()
    return _out(gitinfo.stale_pages(".", guide.guide_dir(entry["folder"])))


def cmd_hotspots(args: argparse.Namespace) -> int:
    return _out(gitinfo.hotspots(".", state.load_settings()["ignore"], days=args.days, top_n=args.top))


def cmd_card_shown(args: argparse.Namespace) -> int:
    entry, _info = _project()
    today = state.today()
    with state.edit_state(entry["folder"]) as st:
        st["daily_card"]["last_shown"] = today.isoformat()
        if args.weekly:
            year, week, _ = today.isocalendar()
            st["weekly_line"]["last_week"] = f"{year}-W{week:02d}"
    return _out({"card_shown": today.isoformat(), "weekly": bool(args.weekly)})


def cmd_first_map(args: argparse.Namespace) -> int:
    entry, _info = _project()
    with state.edit_state(entry["folder"]) as st:
        st["first_map"] = {"answer": args.answer, "date": state.today().isoformat()}
    return _out(st["first_map"])


def _pause(here: bool, paused: bool) -> int:
    if here:
        entry, _info = _project()
        with state.edit_state(entry["folder"]) as st:
            st["paused"] = paused
        return _out({"project": entry["folder"], "paused": paused})
    state.save_settings({"enabled": not paused})
    return _out({"everywhere": True, "on": not paused})


def cmd_pause(args: argparse.Namespace) -> int:
    return _pause(args.here, True)


def cmd_resume(args: argparse.Namespace) -> int:
    return _pause(args.here, False)


def cmd_profile(args: argparse.Namespace) -> int:
    """Show or set what Claude calls the person and what they already know well."""
    changes = {}
    for key, limit in (("name", hooks.MAX_NAME), ("background", hooks.MAX_BACKGROUND)):
        value = getattr(args, key)
        if value is None:
            continue
        cleaned = hooks.clean_profile_value(value, limit + 1)
        if len(cleaned) > limit:
            return _fail(f"{key} is too long: at most {limit} characters")
        changes[key] = cleaned
    if changes:
        state.save_settings(changes)
    settings = state.load_settings()
    return _out({"name": settings["name"], "background": settings["background"]})


def _render_project(folder: str, mark_seen: bool = False) -> tuple[str, dict[str, Any]]:
    """Write PROGRESS.md and guide.html for one project and return the summary text."""
    today = state.today()
    base = guide.guide_dir(folder)
    with state.edit_state(folder) as st:
        numbers = render.summary(folder, st, today)
        render.record_snapshot(st, numbers, today)
        markdown = render.progress_markdown(folder, numbers, st, today)
        # Badges on the guide page = changes since the person last opened it; opening it (mark_seen) resets them.
        files = viewer.guide_files(base)
        report = viewer.compare(st["guide_seen"].get("viewer"), files)
        if mark_seen:
            st["guide_seen"]["viewer"] = files
    (base / "PROGRESS.md").write_text(markdown, encoding="utf-8")
    (base / "guide.html").write_text(viewer.guide_html(folder, base, numbers, report, today), encoding="utf-8")
    return render.summary_text(folder, numbers), numbers


def _write_dashboard() -> str:
    path = state.guides_root() / "dashboard.html"
    path.write_text(render.dashboard_html(identity.all_projects(), state.today()), encoding="utf-8")
    return str(path)


def cmd_render(_: argparse.Namespace) -> int:
    entry, _info = _project()
    text, _numbers = _render_project(entry["folder"])
    dashboard = _write_dashboard()
    base = guide.guide_dir(entry["folder"])
    return _out(f"{text}\n\nProgress file: {base}/PROGRESS.md\nGuide page: {base}/guide.html\nDashboard: {dashboard}")


def cmd_dashboard(_: argparse.Namespace) -> int:
    """Refresh every project's pages; the current project's guide page is the one to open."""
    resolved = identity.resolve(".", create=False)
    here = resolved["entry"]["folder"] if resolved and resolved["status"] in ("known", "new") else None
    for project in identity.all_projects():
        if guide.exists(project["folder"]):
            _render_project(project["folder"], mark_seen=project["folder"] == here)
    dashboard = _write_dashboard()
    page = guide.guide_dir(here) / "guide.html" if here and guide.exists(here) else None
    return _out({"dashboard": dashboard, "guide_page": str(page) if page else None,
                 "open": str(page) if page else dashboard})


def cmd_slot(args: argparse.Namespace) -> int:
    """Where to put the right answer of the next question (Claude must not choose it by habit)."""
    if not 2 <= args.choices <= 4:
        return _fail("--choices must be 2, 3 or 4")
    entry, _info = _project()
    with state.edit_state(entry["folder"]) as st:
        slot = walks.pick_slot(st["answer_slots"], args.choices, random.SystemRandom())
        st["answer_slots"] = (st["answer_slots"] + [slot])[-10:]
    return _out({"slot": slot, "of": args.choices,
                 "say": f"Put the right answer as option {slot} of {args.choices}; \"Not sure, show me\" stays last."})


def cmd_walked(args: argparse.Namespace) -> int:
    """Record a walk through one flow page."""
    page = re.sub(r"\.md$", "", re.sub(r"^flows/", "", args.flow))
    if not re.fullmatch(r"[\w.-]+", page) or page.startswith("."):
        return _fail(f"not a flow page name: {args.flow!r} (use the page's file name, e.g. checkout)")
    entry, _info = _project()
    if not (guide.guide_dir(entry["folder"]) / "flows" / f"{page}.md").is_file():
        return _fail(f"no flow page flows/{page}.md: write the page before walking it")
    try:
        walk = walks.new_walk(page, state.today().isoformat(), args.stops, args.asked, args.right, args.explain)
    except ValueError as exc:
        return _fail(str(exc))
    with state.edit_state(entry["folder"]) as st:
        st["walks"].append(walk)
        status = walks.flow_status(page, st["walks"], st["questions"])
        count = sum(1 for w in st["walks"] if w.get("flow") == page)
    return _out({"flow": page, "status": status, "walks_of_this_flow": count})


def cmd_changes(args: argparse.Namespace) -> int:
    """Guide files new or changed since the last 'your guide changed' note (then remembers this moment)."""
    entry, _info = _project()
    base = guide.guide_dir(entry["folder"])
    files = viewer.guide_files(base)
    with state.edit_state(entry["folder"]) as st:
        report = viewer.compare(st["guide_seen"].get("note"), files)
        if not args.peek:
            st["guide_seen"]["note"] = files
    if args.start:
        return _out({"marked": len(files)})
    for item in report["changed"]:
        item["path"] = str(base / item["file"])
    report.update(guide_dir=str(base), guide_page=str(base / "guide.html"), pictures=viewer.picture_paths(base, report))
    return _out(report)


def cmd_seen(args: argparse.Namespace) -> int:
    """Has the person been shown these files (on a walked flow page that is still up to date)?"""
    entry, info = _project()
    top = info["toplevel"]
    base = guide.guide_dir(entry["folder"])
    pages: dict[str, list[str]] = {}
    flow_pages = sorted((base / "flows").glob("*.md")) if (base / "flows").is_dir() else []
    for page in flow_pages:
        listed = frontmatter.parse(page.read_text(encoding="utf-8")).get("files", [])
        pages[page.stem] = [ownership.repo_path(f, top) for f in listed if isinstance(f, str) and f.strip()]
    st = state.load_state(entry["folder"])
    walked = {w.get("flow") for w in st["walks"] if w.get("flow")}
    # A page checked against code this copy doesn't have has no list of changed files: all of it counts as old.
    stale = {Path(s["page"]).stem: ({ownership.repo_path(f, top) for f in s["changed"]} if s["changed"] else None)
             for s in gitinfo.stale_pages(".", base)}
    files = [ownership.repo_path(f, top) for f in args.files]
    result = ownership.seen_files(files, pages, walked, stale)
    result["say"] = ("Fair to ask \"Where would you look first?\" with these places." if result["ask_guess"] else
                     "Don't ask a guess: fix it first, then show the code walk with the broken step marked.")
    return _out(result)


def cmd_busy(args: argparse.Namespace) -> int:
    """'Busy today': Claude handles the ownership cards by itself until the day ends (or --off)."""
    today = state.today()
    state.save_settings({"busy_day": "" if args.off else today.isoformat()})
    busy = ownership.busy_today(state.load_settings(), today)
    return _out({"busy_today": busy, "say": (
        f"Busy until the end of {today.isoformat()}: decide forks and write lines yourself, and record each one."
        if busy else "Not busy: the Your call / Your line / Find it yourself cards are back.")})


def cmd_owned(args: argparse.Namespace) -> int:
    """Record a call the person made, a line they wrote, or something they found - or Claude's, when skipped."""
    entry, info = _project()
    try:
        event = ownership.new_event(args.kind, args.who, args.what, state.today().isoformat(), args.why or "",
                                    args.file or "")
    except ValueError as exc:
        return _fail(str(exc))
    with state.edit_state(entry["folder"]) as st:
        st["ownership"].append(event)
        totals = ownership.counts(st["ownership"])
    if args.kind == "line":  # the line is written (by them or by Claude): the work is no longer waiting on it
        hooks.mark_line_pending(".", entry["folder"], info["toplevel"], False)
    return _out({"recorded": event, "totals": totals})


def cmd_line_handed(_: argparse.Namespace) -> int:
    """'Your line' is with the person now: while they write it, this piece of work stays open."""
    entry, info = _project()
    hooks.mark_line_pending(".", entry["folder"], info["toplevel"], True)
    return _out({"line_pending": True, "say": "Wait for them. When the line is in and the tests pass, run "
                                               "`owned line --who you ...`."})


def cmd_walk_page(args: argparse.Namespace) -> int:
    """Turn a walk's facts (JSON) into the picture for the chat and a page kept in the guide."""
    entry, _info = _project()
    try:
        data = walkpage.validate(json.loads(Path(args.data).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(f"can't read the walk's JSON: {exc}")
    except ValueError as exc:
        return _fail(str(exc))
    base = guide.guide_dir(entry["folder"])
    if not (base / "flows" / f"{data['flow']}.md").is_file():
        return _fail(f"no flow page flows/{data['flow']}.md: write the page first, then its walk")
    walks_dir = base / "walks"
    walks_dir.mkdir(parents=True, exist_ok=True)
    page_path = walks_dir / f"{data['flow']}.html"
    page_path.write_text(walkpage.page(data, entry["folder"]), encoding="utf-8")
    (walks_dir / f"{data['flow']}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                    encoding="utf-8")
    chat_dir = state.guides_root() / ".chat"
    chat_dir.mkdir(parents=True, exist_ok=True)
    chat_path = chat_dir / f"{entry['folder']}--{data['flow']}.html"
    chat_path.write_text(walkpage.fragment(data), encoding="utf-8")
    return _out({"page": str(page_path), "chat": str(chat_path), "steps": len(data["steps"]),
                 "say": "Show the picture in chat: read the `chat` file and pass its whole text to the inline "
                        "picture tool. If this session has none, open `page` in the browser and send the file."})


def cmd_link(args: argparse.Namespace) -> int:
    try:
        return _out(identity.link(".", args.folder))
    except ValueError as exc:
        return _fail(str(exc))


def cmd_register_new(_: argparse.Namespace) -> int:
    try:
        return _out(identity.register_new("."))
    except ValueError as exc:
        return _fail(str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="own-guide", description="The tool behind the `own` plugin.")
    parser.add_argument("--version", action="version", version=f"own-guide {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        return p

    add("session-start", cmd_session_start, "hook: print today's instructions and facts")
    add("stop-check", cmd_stop_check, "hook: ask for a guide update + quiz after enough code changed")
    add("edit-check", cmd_edit_check, "hook: hold back the first code edit of a piece of work, once")
    add("identify", cmd_identify, "show how this folder is recognised")
    add("where", cmd_where, "print this project's guide folder")
    add("status", cmd_status, "today's facts for this project (JSON)")
    add("init-guide", cmd_init_guide, "create the empty guide files if missing")
    p = add("due", cmd_due, "questions due to come back now")
    p.add_argument("--limit", type=int, default=None)
    p = add("add-question", cmd_add_question, "store a new question (what it tests + correct answer)")
    p.add_argument("--kind", required=True, choices=["trace", "why", "debug", "what-if", "idea", "transfer"])
    p.add_argument("--tests", required=True, help="what the question checks, in one plain line")
    p.add_argument("--answer", required=True, help="the correct answer, in one plain line")
    p.add_argument("--link", action="append", default=[], help="file:function to open (repeatable)")
    p.add_argument("--source", default="", help="flow:<page> | decision:<n> | idea:<name> | plan")
    p.add_argument("--feature", default="")
    when = p.add_mutually_exclusive_group()
    when.add_argument("--result", choices=list(schedule.RESULTS), default=None)
    when.add_argument("--ask-tomorrow", action="store_true",
                      help="not asked yet: ask it first tomorrow (e.g. after a bug Claude fixed and showed)")
    p = add("record", cmd_record, "record an answer to a returning question")
    p.add_argument("id")
    p.add_argument("result", choices=list(schedule.RESULTS))
    for name, func, text in (("quiz-done", cmd_quiz_done, "log a finished quiz"),
                             ("quiz-later", cmd_quiz_later, "save a quiz for later"),
                             ("quiz-skip", cmd_quiz_skip, "skip a quiz")):
        p = add(name, func, text)
        p.add_argument("--feature", required=True)
        if name == "quiz-done":
            p.add_argument("--asked", type=int, required=True)
            p.add_argument("--right", type=int, required=True)
    add("synced", cmd_synced, "mark the guide as matching the code now")
    p = add("stamp", cmd_stamp, "record the code a flow page was just checked against")
    p.add_argument("page", help="flows/<name>.md (relative to the guide folder) or an absolute path")
    add("stale", cmd_stale, "guide pages whose code changed since they were checked")
    add("diagrams", cmd_diagrams, "draw pictures of the guide's diagrams and show them above the code")
    p = add("hotspots", cmd_hotspots, "files changed most often recently")
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--top", type=int, default=10)
    p = add("card-shown", cmd_card_shown, "mark today's daily card as shown")
    p.add_argument("--weekly", action="store_true", help="the weekly line was shown too")
    p = add("first-map", cmd_first_map, "record the answer to the first-map card")
    p.add_argument("answer", choices=["now", "later", "never"])
    for name, func, text in (("pause", cmd_pause, "switch Own off (everywhere, or --here)"),
                             ("resume", cmd_resume, "switch Own back on (everywhere, or --here)")):
        p = add(name, func, text)
        p.add_argument("--here", action="store_true")
    p = add("profile", cmd_profile, "show or set your name and what you already know well")
    p.add_argument("--name", default=None, help="what Claude calls you (empty string clears it)")
    p.add_argument("--background", default=None, help='what you already know well, e.g. "iOS and Swift"')
    add("render", cmd_render, "update PROGRESS.md, the guide page and the dashboard, and print the summary")
    add("dashboard", cmd_dashboard, "rebuild every guide page and the dashboard; prints which page to open")
    p = add("slot", cmd_slot, "where to put the right answer of the next question")
    p.add_argument("--choices", type=int, default=3, help="believable choices, not counting 'Not sure' (2-4)")
    p = add("walked", cmd_walked, "record a walk through one flow page")
    p.add_argument("flow", help="the flow page's name, e.g. checkout for flows/checkout.md")
    p.add_argument("--stops", type=int, required=True)
    p.add_argument("--asked", type=int, required=True, help="predictions asked")
    p.add_argument("--right", type=int, required=True, help="predictions right")
    p.add_argument("--explain", required=True, choices=list(walks.EXPLAIN_RESULTS),
                   help="how the explain-back went")
    p = add("changes", cmd_changes, "guide files new or changed since the last 'your guide changed' note")
    p.add_argument("--start", action="store_true", help="only remember this moment (run before updating the guide)")
    p.add_argument("--peek", action="store_true", help="list without remembering")
    p = add("walk-page", cmd_walk_page, "draw a code walk (chat picture + a page in the guide's walks/ folder)")
    p.add_argument("data", help="the walk's facts as a JSON file (shape: the own skill's CODE-WALK.md)")
    p = add("seen", cmd_seen, "has the person been shown these files? (decides the 'where would you look' card)")
    p.add_argument("files", nargs="+", help="repo files, e.g. shop/cart.py or shop/cart.py:42")
    p = add("busy", cmd_busy, "busy today: Claude handles the ownership cards by itself until the day ends")
    p.add_argument("--off", action="store_true", help="not busy any more")
    p = add("owned", cmd_owned, "record a call made, a line written or something found")
    p.add_argument("kind", choices=list(ownership.KINDS))
    p.add_argument("--who", required=True, choices=list(ownership.WHO))
    p.add_argument("--what", required=True, help="one plain line: the decision, the line, or what was found")
    p.add_argument("--why", choices=[w for w in ownership.WHY if w], default=None,
                   help="for --who claude: skipped (they chose 'Claude handles it') or busy")
    p.add_argument("--file", default=None, help="the repo file it was in")
    add("line-handed", cmd_line_handed, "'your line' was handed to the person: keep this piece of work open")
    p = add("link", cmd_link, "this repo is the same project as an existing guide")
    p.add_argument("folder")
    add("register-new", cmd_register_new, "this repo is a new project: give it its own guide")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state.ensure_tool_link()
    return args.func(args)
