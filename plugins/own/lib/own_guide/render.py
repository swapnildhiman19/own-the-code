"""Progress, in words and in pictures.

`summary()` is the numbers. `progress_markdown()` writes them as each project's
PROGRESS.md; `dashboard_html()` draws all projects on one local page. The page is a
single self-contained file - no scripts, no fonts, no links to the internet - so it opens
offline and nothing about the code ever leaves the Mac.
"""

from __future__ import annotations

import datetime as dt
import html
from typing import Any
from urllib.parse import quote

from . import guide, ownership, schedule, state, walks


def _week_key(day: dt.date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def summary(folder: str, st: dict[str, Any], today: dt.date) -> dict[str, Any]:
    c = guide.counts(folder)
    questions = st["questions"]
    # Right answers alone never make a flow "got": it must be walked first (walks.flow_status).
    flow_status = {page: walks.flow_status(page, st["walks"], questions) for page in c["flow_pages"]}
    quizzed_decisions = {q["source"] for q in questions if str(q.get("source", "")).startswith("decision:")}
    month_ago = (today - dt.timedelta(days=30)).isoformat()
    events = st.get("ownership", [])
    owned = ownership.counts(events)
    return {
        "calls_you": owned["call_you"],
        "lines_you": owned["line_you"],
        "finds_you": owned["find_you"],
        "handled_by_claude": owned["call_claude"] + owned["line_claude"],
        # Decisions Claude made because the person was busy or chose "Claude decides": listed for a later look.
        "claude_calls": [{"date": e["date"], "what": e["what"], "why": e.get("why", "")}
                         for e in events if e.get("kind") == "call" and e.get("who") == "claude"][-20:],
        "flows_listed": c["flows_listed"],
        "flow_pages": len(c["flow_pages"]),
        "flows_walked": sum(1 for s in flow_status.values() if s != walks.NOT_WALKED),
        "flows_got": sum(1 for s in flow_status.values() if s == walks.GOT),
        "flow_status": flow_status,
        "decisions": c["decisions"],
        "decisions_quizzed": len(quizzed_decisions),
        "ideas": c["ideas"],
        "questions": len(questions),
        "got_it": sum(1 for q in questions if q["status"] == "done"),
        "coming_back": sum(1 for q in questions if q["status"] in ("learning", "check")),
        "due_now": schedule.due_count(questions, today),
        "upcoming": [{"date": q["next_due"], "tests": q["tests"]} for q in schedule.upcoming(questions, today)],
        "quizzes_30d": sum(1 for z in st["quizzes"] if z.get("date", "") >= month_ago and z.get("outcome") == "done"),
    }


def record_snapshot(st: dict[str, Any], numbers: dict[str, Any], today: dt.date) -> None:
    """Keep one row of numbers per day, so 'this week: +2 flows' can be worked out."""
    row = {
        "date": today.isoformat(),
        "flows_listed": numbers["flows_listed"],
        "flow_pages": numbers["flow_pages"],
        "flows_walked": numbers["flows_walked"],
        "flows_got": numbers["flows_got"],
        "ideas": numbers["ideas"],
        "decisions": numbers["decisions"],
        "got_it": numbers["got_it"],
        "calls_you": numbers["calls_you"],
        "lines_you": numbers["lines_you"],
    }
    log = [r for r in st["progress_log"] if r["date"] != row["date"]]
    log.append(row)
    st["progress_log"] = log[-400:]


def weekly_delta(st: dict[str, Any], today: dt.date) -> dict[str, int] | None:
    log = st["progress_log"]
    if not log:
        return None
    week_ago = (today - dt.timedelta(days=7)).isoformat()
    older = [r for r in log if r["date"] <= week_ago]
    before = older[-1] if older else {}
    now = log[-1]
    keys = ("flows_listed", "flow_pages", "flows_walked", "flows_got", "ideas", "decisions", "got_it",
            "calls_you", "lines_you")
    # A key the older row never recorded (rows saved before a metric existed) has no honest
    # "before", so its change is reported as 0 rather than as everything counted so far.
    return {k: (now.get(k, 0) - before.get(k, 0)) if (k in before or not older) else 0 for k in keys}


def _plural(n: int, one: str, many: str) -> str:
    return f"+{n} {one if n == 1 else many}"


def weekly_line(project_name: str, st: dict[str, Any], today: dt.date) -> str | None:
    """'This week in X: +2 flows, +5 ideas' - or None if nothing grew or it was shown this week."""
    if st["weekly_line"].get("last_week") == _week_key(today):
        return None
    delta = weekly_delta(st, today)
    if not delta:
        return None
    parts = []
    if delta["flows_listed"] > 0:
        parts.append(_plural(delta["flows_listed"], "flow on the map", "flows on the map"))
    if delta["flow_pages"] > 0:
        parts.append(_plural(delta["flow_pages"], "flow page written", "flow pages written"))
    if delta["flows_walked"] > 0:
        parts.append(_plural(delta["flows_walked"], "flow walked with you", "flows walked with you"))
    if delta["calls_you"] > 0:
        parts.append(_plural(delta["calls_you"], "call you made", "calls you made"))
    if delta["lines_you"] > 0:
        parts.append(_plural(delta["lines_you"], "piece of code you wrote", "pieces of code you wrote"))
    if delta["ideas"] > 0:
        parts.append(_plural(delta["ideas"], "idea", "ideas"))
    if delta["got_it"] > 0:
        parts.append(_plural(delta["got_it"], "question you've got for good", "questions you've got for good"))
    return f"This week in {project_name}: " + ", ".join(parts) if parts else None


def summary_text(project_name: str, n: dict[str, Any]) -> str:
    lines = [
        f"{project_name}: what you know",
        f"- Flows: {n['flow_pages']} of {n['flows_listed']} have pages, {n['flows_walked']} walked with you, "
        f"{n['flows_got']} you've got (walked, then answered right on a later day)",
        f"- Code decisions: {n['decisions']} written down, {n['decisions_quizzed']} you've been asked about",
        f"- Yours: {n['calls_you']} calls you made, {n['lines_you']} pieces of code you wrote, "
        f"{n['finds_you']} things you found yourself",
        f"- Ideas met: {n['ideas']}",
        f"- Questions: {n['got_it']} got for good, {n['coming_back']} coming back ({n['due_now']} due now)",
    ]
    if n["claude_calls"]:
        lines.append(f"- Calls Claude made for you (to look at later): {len(n['claude_calls'])}, listed on the guide page")
    if n["upcoming"]:
        lines.append("- Next returns: " + ", ".join(f"{u['date']}" for u in n["upcoming"]))
    lines.append(f"- Quizzes in the last 30 days: {n['quizzes_30d']}")
    return "\n".join(lines)


def progress_markdown(project_name: str, n: dict[str, Any], st: dict[str, Any], today: dt.date) -> str:
    delta = weekly_delta(st, today) or {}
    out = [
        f"# Progress: {project_name}",
        "",
        f"> Updated by Own on {today.isoformat()}. Generated file: edits are overwritten.",
        "",
        "| What | Now |",
        "|---|---|",
        f"| Flows with a page | {n['flow_pages']} of {n['flows_listed']} |",
        f"| Flows walked with you | {n['flows_walked']} |",
        f"| Flows you've got (walked, then answered right on a later day) | {n['flows_got']} |",
        f"| Code decisions written down | {n['decisions']} ({n['decisions_quizzed']} asked about) |",
        f"| Calls you made | {n['calls_you']} |",
        f"| Pieces of code you wrote | {n['lines_you']} |",
        f"| Things you found in the code yourself | {n['finds_you']} |",
        f"| Ideas met | {n['ideas']} |",
        f"| Questions got for good | {n['got_it']} |",
        f"| Questions coming back | {n['coming_back']} ({n['due_now']} due now) |",
        f"| Quizzes in the last 30 days | {n['quizzes_30d']} |",
        "",
        "## The last 7 days",
        "",
        f"- Flows on the map: {delta.get('flows_listed', 0):+d}",
        f"- Flow pages written: {delta.get('flow_pages', 0):+d}",
        f"- Flows walked with you: {delta.get('flows_walked', 0):+d}",
        f"- Calls you made: {delta.get('calls_you', 0):+d}",
        f"- Pieces of code you wrote: {delta.get('lines_you', 0):+d}",
        f"- Ideas met: {delta.get('ideas', 0):+d}",
        f"- Questions got for good: {delta.get('got_it', 0):+d}",
        "",
        "## Coming back next",
        "",
    ]
    if n["upcoming"]:
        out += [f"- {u['date']}: {u['tests']}" for u in n["upcoming"]]
    else:
        out.append("- Nothing scheduled.")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- dashboard

_CSS = """
:root{--bg:#f7f6f2;--card:#ffffff;--ink:#1f1f1c;--muted:#6b6a63;--line:#e4e2da;--bar:#3d6fb6;--good:#2f8a5b}
@media (prefers-color-scheme: dark){:root{--bg:#141413;--card:#1e1e1c;--ink:#ecebe6;--muted:#a3a29b;--line:#33322e;--bar:#7aa7e8;--good:#5cc28b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);margin:0 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h2{font-size:17px;margin:0 0 10px}.row{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:6px 0}
.row:first-of-type{border-top:0}.num{font-variant-numeric:tabular-nums;font-weight:600}.muted{color:var(--muted);font-size:13px}
svg text{fill:var(--muted);font-size:10px}.empty{color:var(--muted)}
"""


def _bars(weeks: list[tuple[str, int]]) -> str:
    width, height, pad = 260, 70, 14
    top = max([v for _, v in weeks] + [1])
    step = width / max(len(weeks), 1)
    parts = [f'<svg viewBox="0 0 {width} {height + pad}" width="100%" role="img" aria-label="Quizzes per week">']
    for i, (label, value) in enumerate(weeks):
        h = 0 if top == 0 else (value / top) * (height - 6)
        x = i * step + 4
        parts.append(
            f'<rect x="{x:.1f}" y="{height - h:.1f}" width="{step - 8:.1f}" height="{h:.1f}" rx="3" fill="var(--bar)">'
            f"<title>{html.escape(label)}: {value}</title></rect>"
        )
        parts.append(f'<text x="{x:.1f}" y="{height + 11}">{html.escape(label[-3:])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _weeks(st: dict[str, Any], today: dt.date, count: int = 8) -> list[tuple[str, int]]:
    keys = [_week_key(today - dt.timedelta(weeks=i)) for i in reversed(range(count))]
    tally = {k: 0 for k in keys}
    for quiz in st["quizzes"]:
        if quiz.get("outcome") != "done" or not quiz.get("date"):
            continue
        key = _week_key(dt.date.fromisoformat(quiz["date"]))
        if key in tally:
            tally[key] += 1
    return [(k, tally[k]) for k in keys]


def dashboard_html(projects: list[dict[str, Any]], today: dt.date) -> str:
    cards = []
    for project in projects:
        st = state.load_state(project["folder"])
        n = summary(project["folder"], st, today)
        e = html.escape
        cards.append(
            '<section class="card">'
            f"<h2>{e(project['folder'])}</h2>"
            f'<div class="row"><span>Flows with a page</span><span class="num">{n["flow_pages"]} / {n["flows_listed"]}</span></div>'
            f'<div class="row"><span>Flows walked with you</span><span class="num">{n["flows_walked"]}</span></div>'
            f'<div class="row"><span>Flows you\'ve got</span><span class="num">{n["flows_got"]}</span></div>'
            f'<div class="row"><span>Code decisions</span><span class="num">{n["decisions"]}</span></div>'
            f'<div class="row"><span>Calls you made / code you wrote</span>'
            f'<span class="num">{n["calls_you"]} / {n["lines_you"]}</span></div>'
            f'<div class="row"><span>Ideas met</span><span class="num">{n["ideas"]}</span></div>'
            f'<div class="row"><span>Got for good</span><span class="num" style="color:var(--good)">{n["got_it"]}</span></div>'
            f'<div class="row"><span>Coming back</span><span class="num">{n["coming_back"]} ({n["due_now"]} due)</span></div>'
            '<p class="muted">Quizzes per week</p>'
            f"{_bars(_weeks(st, today))}"
            + (f'<p><a href="{e(quote(project["folder"]))}/guide.html">Open the guide</a></p>'
               if (state.project_dir(project["folder"]) / "guide.html").is_file() else "")
            + (f'<p class="muted">Paused in this project</p>' if st.get("paused") else "")
            + "</section>"
        )
    book = state.guides_root() / "_knowledge"
    ideas = len([p for p in book.rglob("*.md") if p.name != "INDEX.md" and p.parent.name != "frameworks"]) if book.is_dir() else 0
    frameworks = len(list((book / "frameworks").glob("*.md"))) if (book / "frameworks").is_dir() else 0
    body = "".join(cards) or '<p class="empty">No projects yet. Open a git project with the plugin on.</p>'
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Own the Code</title>"
        f"<style>{_CSS}</style></head><body><main>"
        "<h1>Own the Code</h1>"
        f'<p class="sub">Updated {today.isoformat()} · knowledge book: {ideas} ideas, {frameworks} framework pages · '
        "local file, never published</p>"
        f'<div class="grid">{body}</div></main></body></html>\n'
    )
