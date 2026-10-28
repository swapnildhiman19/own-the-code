"""The guide as one local web page, and "what changed in your guide" since it was last shown.

Example: after a feature, Claude rewrites flows/checkout.md and its picture. Mia types /own dashboard and
gets `~/code-guides/shop/guide.html`: the map picture, every flow page with its picture and a "Not walked yet /
Walked / Got it" chip, the code decisions, the learnings, and a "Changed" badge on checkout. She never has to dig
through the folder or read Mermaid code.

The page is one self-contained file: no scripts, no web fonts, nothing loaded from the internet. Markdown is
turned into HTML by the small renderer below (standard library only); everything from the guide is escaped,
so a stray `<script>` in a page shows as text.

Two "last shown" pictures of the guide are kept in state.json `guide_seen`: "note" for the changed-files note
Claude shows in chat, "viewer" for the badges on this page.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from . import frontmatter, walks

DOCS = {"FLOW.md": "map", "CODE-DECISIONS.md": "decisions", "LEARNINGS.md": "learnings"}


# ---------------------------------------------------------------- what changed

def _sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def guide_files(base: Path) -> dict[str, str]:
    """A fingerprint of every file the person reads in the guide (generated files like PROGRESS.md left out)."""
    files = {name: _sha(base / name) for name in DOCS if (base / name).is_file()}
    for sub, pattern in (("flows", "*.md"), ("diagrams", "*.png"), ("walks", "*.html")):
        if (base / sub).is_dir():
            files.update({f"{sub}/{p.name}": _sha(p) for p in sorted((base / sub).glob(pattern))})
    return files


def compare(before: dict[str, str] | None, now: dict[str, str]) -> dict[str, Any]:
    """New, changed and removed files since `before`. No `before` yet = a first look, nothing to list."""
    if before is None:
        return {"first_look": True, "changed": [], "removed": []}
    changed = [{"file": f, "kind": "new" if f not in before else "changed"} for f in sorted(now) if before.get(f) != now[f]]
    return {"first_look": False, "changed": changed, "removed": sorted(f for f in before if f not in now)}


def page_of_picture(name: str) -> str | None:
    """Which page a picture belongs to: diagrams/flows-checkout-1.png -> flows/checkout.md."""
    match = re.fullmatch(r"diagrams/(flows-(.+)|flow)-\d+\.png", name)
    if not match:
        return None
    return f"flows/{match.group(2)}.md" if match.group(2) else "FLOW.md"


def page_of(name: str) -> str | None:
    """The page a guide file belongs to: a picture or a walk belongs to its flow page; a page to itself.

    walks/checkout.html -> flows/checkout.md.
    """
    if name.startswith("diagrams/"):
        return page_of_picture(name)
    match = re.fullmatch(r"walks/(.+)\.html", name)
    return f"flows/{match.group(1)}.md" if match else name


def changed_pages(report: dict[str, Any]) -> set[str]:
    """The pages to badge: changed pages, plus pages whose picture or walk changed."""
    pages = set()
    for item in report["changed"]:
        name = item["file"]
        page = page_of(name)
        if page and page.endswith(".md"):
            pages.add(page)
    return pages


# ---------------------------------------------------------------- markdown

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_ANCHOR = re.compile(r'^<a id="([\w.-]+)"></a>$')
_PICTURE_MARK = re.compile(r"^<!-- own:diagram \S+ sha=[0-9a-f]+ -->$")
_HR = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")
_INLINE = re.compile(
    r"(?P<tick>`+)(?P<code>.+?)(?P=tick)"
    r"|!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)"
    r"|\[(?P<label>[^\]]+)\]\((?P<href>[^)\s]+)\)"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|(?<![\w*])\*(?P<em>[^*\s][^*]*?)\*(?![\w*])"
    r"|(?<![\w_])_(?P<em2>[^_\s][^_]*?)_(?![\w_])"
)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.replace("`", "").lower()).strip("-") or "section"


def _cells(row: str) -> list[str]:
    """Split a table row on `|`, but not on a `|` inside `code` or written as `\\|`."""
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    cells, current, in_code, i = [], [], False, 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current).strip())
    return cells


class Markdown:
    """Markdown from one guide file, as HTML for the guide page.

    `doc_id` prefixes every anchor so pages can't clash; `docs` maps each guide file to its section id,
    so `[#15](../CODE-DECISIONS.md#15)` becomes a jump within the page (`#decisions-15`).
    """

    def __init__(self, doc_id: str, src_dir: Path, out_dir: Path, docs: dict[Path, str]) -> None:
        self.doc_id, self.src_dir, self.out_dir, self.docs = doc_id, src_dir, out_dir, docs

    # -- links ------------------------------------------------------------------
    def url(self, href: str, image: bool = False) -> str | None:
        if href.startswith("#"):
            return None if image else f"#{self.doc_id}-{slug(unquote(href[1:]))}"
        scheme = _SCHEME.match(href)
        if scheme:  # web links open; pictures never load from the internet; other schemes are dropped
            return href if (not image and scheme.group(1).lower() in ("http", "https", "mailto")) else None
        path_part, _, fragment = href.partition("#")
        if not path_part:
            return None
        target = Path(os.path.normpath(self.src_dir / unquote(path_part)))
        if not image and target in self.docs:
            doc = self.docs[target]
            return f"#{doc}-{slug(unquote(fragment))}" if fragment else f"#{doc}"
        rel = Path(os.path.relpath(target, self.out_dir)).as_posix()
        return quote(rel) + (f"#{quote(fragment)}" if fragment and not image else "")

    # -- inline -----------------------------------------------------------------
    def inline(self, text: str) -> str:
        out, pos = [], 0
        for m in _INLINE.finditer(text):
            out.append(html.escape(text[pos:m.start()]))
            pos = m.end()
            if m.group("tick"):
                out.append(f"<code>{html.escape(m.group('code').strip())}</code>")
            elif m.group("src") is not None:
                src = self.url(m.group("src"), image=True)
                alt = html.escape(m.group("alt"))
                # A click opens the picture full size: wide sequence diagrams are small inside the page.
                out.append(f'<a href="{html.escape(src)}"><img src="{html.escape(src)}" alt="{alt}" loading="lazy"></a>'
                           if src else alt)
            elif m.group("href") is not None:
                href = self.url(m.group("href"))
                label = self.inline(m.group("label"))
                out.append(f'<a href="{html.escape(href)}">{label}</a>' if href else label)
            elif m.group("bold") is not None:
                out.append(f"<strong>{self.inline(m.group('bold'))}</strong>")
            else:
                out.append(f"<em>{self.inline(m.group('em') or m.group('em2'))}</em>")
        out.append(html.escape(text[pos:]))
        return "".join(out)

    # -- blocks -----------------------------------------------------------------
    def _list(self, items: list[list[Any]]) -> str:
        out: list[str] = []
        stack: list[tuple[int, str]] = []
        for indent, ordered, start, text in items:
            tag = "ol" if ordered else "ul"
            while stack and indent < stack[-1][0]:
                out.append(f"</li></{stack.pop()[1]}>")
            if stack and indent == stack[-1][0] and tag != stack[-1][1]:
                out.append(f"</li></{stack.pop()[1]}>")
            if not stack or indent > stack[-1][0]:
                attr = f' start="{start}"' if ordered and start != 1 else ""
                out.append(f"<{tag}{attr}><li>")
                stack.append((indent, tag))
            else:
                out.append("</li><li>")
            out.append(self.inline(text))
        while stack:
            out.append(f"</li></{stack.pop()[1]}>")
        return "".join(out)

    def blocks(self, lines: list[str]) -> str:
        out: list[str] = []
        para: list[str] = []
        picture_above = False  # the next ```mermaid block already has its picture: show only the picture

        def flush() -> None:
            if para:
                out.append(f"<p>{self.inline(' '.join(para))}</p>")
                para.clear()

        i = 0
        while i < len(lines):
            line = lines[i]
            s = line.strip()
            if not s:
                flush()
                i += 1
                continue
            if _PICTURE_MARK.match(s):
                flush()
                picture_above = True
                i += 1
                continue
            if s.startswith("<!--"):
                flush()
                while i < len(lines) and "-->" not in lines[i]:
                    i += 1
                i += 1
                continue
            anchor = _ANCHOR.match(s)
            if anchor:
                flush()
                out.append(f'<a id="{self.doc_id}-{slug(anchor.group(1))}"></a>')
                i += 1
                continue
            fence = _FENCE.match(line)
            if fence:
                flush()
                marker, lang = fence.group(1), fence.group(2).lower()
                code: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith(marker):
                    code.append(lines[i])
                    i += 1
                i += 1
                body = html.escape("\n".join(code))
                if lang == "mermaid" and picture_above:
                    picture_above = False
                elif lang == "mermaid":
                    out.append(f"<details><summary>Diagram (no picture drawn yet)</summary><pre><code>{body}</code></pre></details>")
                else:
                    out.append(f"<pre><code>{body}</code></pre>")
                continue
            heading = _HEADING.match(s)
            if heading:
                flush()
                level = min(len(heading.group(1)) + 1, 6)  # the page's own <h1> is the project title
                text = heading.group(2)
                out.append(f'<h{level} id="{self.doc_id}-{slug(text)}">{self.inline(text)}</h{level}>')
                i += 1
                continue
            if s.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
                flush()
                head = "".join(f"<th>{self.inline(c)}</th>" for c in _cells(s))
                i += 2
                rows = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    rows.append("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in _cells(lines[i])) + "</tr>")
                    i += 1
                out.append(f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
                continue
            if s.startswith(">"):
                flush()
                inner = []
                while i < len(lines) and lines[i].strip().startswith(">"):
                    inner.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                out.append(f"<blockquote>{self.blocks(inner)}</blockquote>")
                continue
            if _HR.match(s) and not para:
                out.append("<hr>")
                i += 1
                continue
            item = _LIST.match(line)
            if item:
                flush()
                items: list[list[Any]] = []
                while i < len(lines):
                    current = lines[i]
                    m = _LIST.match(current)
                    if m:
                        marker = m.group(2)
                        ordered = marker[0].isdigit()
                        items.append([len(m.group(1).expandtabs(4)), ordered, int(marker[:-1]) if ordered else 1, m.group(3)])
                        i += 1
                    elif not current.strip():
                        j = i + 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        if j < len(lines) and (_LIST.match(lines[j]) or lines[j].startswith((" ", "\t"))):
                            i = j
                        else:
                            break
                    elif current.startswith((" ", "\t")):
                        items[-1][3] += " " + current.strip()
                        i += 1
                    else:
                        break
                out.append(self._list(items))
                continue
            para.append(s)
            i += 1
        flush()
        return "".join(out)

    def render(self, text: str) -> str:
        _meta, body, _found = frontmatter.split(text)
        return self.blocks(body.splitlines())


# ---------------------------------------------------------------- the page

_CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1f1f1c;--muted:#6b6a63;--line:#e4e2da;--accent:#3d6fb6;--good:#2f8a5b;--warn:#b7791f;--code:#f1efe8}
@media (prefers-color-scheme: dark){:root{--bg:#141413;--card:#1e1e1c;--ink:#ecebe6;--muted:#a3a29b;--line:#33322e;--accent:#7aa7e8;--good:#5cc28b;--warn:#e0b25c;--code:#262624}}
*{box-sizing:border-box}html{scroll-behavior:smooth}[id]{scroll-margin-top:52px}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:16px 16px 64px}
header h1{font-size:24px;margin:8px 0 2px}.sub{color:var(--muted);margin:0 0 12px;font-size:14px}
nav{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 0;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:14px}
a{color:var(--accent)}section.doc,section.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 20px 16px;margin:0 0 20px;overflow-wrap:anywhere}
h2{font-size:20px;margin:18px 0 8px}h3{font-size:17px;margin:16px 0 6px}h4,h5,h6{font-size:15px;margin:14px 0 4px}
img{max-width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px}
code{background:var(--code);border-radius:4px;padding:1px 4px;font-size:.9em}
pre{background:var(--code);border-radius:8px;padding:10px 12px;overflow-x:auto}pre code{padding:0;background:none}
.table{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:var(--code)}
blockquote{margin:8px 0;padding:2px 14px;border-left:3px solid var(--line);color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin:8px 0}
.stat{border:1px solid var(--line);border-radius:10px;padding:8px 12px}.stat b{display:block;font-size:22px}
.chip{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 9px;margin-right:6px;border:1px solid currentColor}
.chip.got{color:var(--good)}.chip.walked{color:var(--accent)}.chip.not-walked{color:var(--muted)}.chip.changed{color:var(--warn)}
.muted{color:var(--muted);font-size:14px}ul.flows{list-style:none;padding:0}ul.flows li{padding:6px 0;border-top:1px solid var(--line)}
"""

_CHIP = {walks.NOT_WALKED: ("not-walked", "Not walked yet"), walks.WALKED: ("walked", "Walked"), walks.GOT: ("got", "Got it")}


def _title(text: str, fallback: str) -> str:
    _meta, body, _found = frontmatter.split(text)
    for line in body.splitlines():
        m = _HEADING.match(line.strip())
        if m and len(m.group(1)) == 1:
            return re.sub(r"^Flow:\s*", "", m.group(2))
    return fallback


def guide_html(project: str, base: Path, numbers: dict[str, Any], report: dict[str, Any], today: dt.date) -> str:
    """The whole guide of one project as one page, written to `<base>/guide.html`."""
    e = html.escape
    flow_pages = sorted((base / "flows").glob("*.md")) if (base / "flows").is_dir() else []
    docs: dict[Path, str] = {Path(os.path.normpath(base / name)): doc for name, doc in DOCS.items()}
    docs.update({Path(os.path.normpath(p)): f"flow-{slug(p.stem)}" for p in flow_pages})
    badged = changed_pages(report)
    changed_chip = '<span class="chip changed">Changed</span>'

    def doc_section(path: Path, doc_id: str, rel: str, chips: str = "") -> str:
        text = path.read_text(encoding="utf-8")
        md = Markdown(doc_id, path.parent, base, docs)
        badge = changed_chip if rel in badged else ""
        return f'<section class="doc" id="{doc_id}"><p>{chips}{badge}</p>{md.render(text)}</section>'

    n = numbers
    stats = [
        ("Flows with a page", f"{n['flow_pages']} / {n['flows_listed']}"),
        ("Walked with you", n["flows_walked"]), ("You've got", n["flows_got"]),
        ("Code decisions", n["decisions"]), ("Ideas met", n["ideas"]),
        ("Questions coming back", f"{n['coming_back']} ({n['due_now']} due now)"),
        ("Calls you made", n["calls_you"]), ("Code you wrote", n["lines_you"]), ("Found yourself", n["finds_you"]),
    ]
    parts = [
        '<section class="box" id="progress"><h2>Where you are</h2><div class="grid">'
        + "".join(f'<div class="stat"><span class="muted">{e(k)}</span><b>{e(str(v))}</b></div>' for k, v in stats)
        + '</div><p class="muted">Walked: you went through the flow stop by stop with Claude. Got it: walked, then '
          "answered a question on it right on a later day. Calls, code and finds: the decisions you made, the "
          "pieces of code you wrote and the things you found in the code yourself.</p></section>"
    ]
    if n.get("claude_calls"):
        why = {"busy": "you were busy", "skipped": "you chose “Claude decides”"}
        rows = "".join(
            f"<li>{e(c['date'])}: {e(c['what'])}"
            + (f' <span class="muted">({e(why[c["why"]])})</span>' if c.get("why") in why else "") + "</li>"
            for c in reversed(n["claude_calls"])
        )
        parts.append('<section class="box" id="claude-calls"><h2>Calls Claude made for you</h2>'
                     '<p class="muted">Decisions at a fork that Claude made alone. Worth a look when you have a minute; '
                     "the reasons are in Code decisions.</p>"
                     f"<ul>{rows}</ul></section>")

    if report["first_look"]:
        news = "<p>First look at this page. From now on, pages that change get a <b>Changed</b> badge.</p>"
    elif report["changed"] or report["removed"]:
        rows = []
        for item in report["changed"]:
            name = item["file"]
            page = page_of(name)
            doc = docs.get(Path(os.path.normpath(base / page))) if page else None
            what = "new" if item["kind"] == "new" else "changed"
            kind = "step-by-step walk of " if name.startswith("walks/") else "picture of "
            label = f"{name} ({what}{', ' + kind + page if page and page != name else ''})"
            rows.append(f'<li><a href="#{doc}">{e(label)}</a></li>' if doc else f"<li>{e(label)}</li>")
        rows += [f"<li>{e(name)} (removed)</li>" for name in report["removed"]]
        news = f"<ul>{''.join(rows)}</ul>"
    else:
        news = '<p class="muted">Nothing changed since you last looked.</p>'
    parts.append(f'<section class="box" id="changed"><h2>Changed since you last looked</h2>{news}</section>')

    if (base / "FLOW.md").is_file():
        parts.append(doc_section(base / "FLOW.md", "map", "FLOW.md"))

    status = n.get("flow_status", {})
    listing = []
    for p in flow_pages:
        css, label = _CHIP[status.get(p.stem, walks.NOT_WALKED)]
        badge = changed_chip if f"flows/{p.name}" in badged else ""
        title = _title(p.read_text(encoding="utf-8"), p.stem)
        walk = (f' <a class="muted" href="walks/{e(quote(p.stem))}.html">step-by-step walk</a>'
                if (base / "walks" / f"{p.stem}.html").is_file() else "")
        listing.append(f'<li><span class="chip {css}">{label}</span>{badge}<a href="#flow-{slug(p.stem)}">{e(title)}</a>'
                       f"{walk}</li>")
    parts.append(
        '<section class="box" id="flows"><h2>Flow pages</h2>'
        + (f'<ul class="flows">{"".join(listing)}</ul>' if listing else '<p class="muted">No flow pages written yet.</p>')
        + "</section>"
    )
    for p in flow_pages:
        css, label = _CHIP[status.get(p.stem, walks.NOT_WALKED)]
        parts.append(doc_section(p, f"flow-{slug(p.stem)}", f"flows/{p.name}", f'<span class="chip {css}">{label}</span>'))
    for name in ("CODE-DECISIONS.md", "LEARNINGS.md"):
        if (base / name).is_file():
            parts.append(doc_section(base / name, DOCS[name], name))

    nav = ['<a href="#progress">Where you are</a>', '<a href="#changed">Changed</a>']
    nav += ['<a href="#map">Map</a>'] if (base / "FLOW.md").is_file() else []
    nav += [f'<a href="#flows">Flows ({len(flow_pages)})</a>']
    nav += [f'<a href="#{DOCS[name]}">{label}</a>' for name, label in (("CODE-DECISIONS.md", "Code decisions"),
                                                                     ("LEARNINGS.md", "Learnings")) if (base / name).is_file()]
    nav.append('<a href="../dashboard.html">All projects</a>')
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{e(project)} guide</title><style>{_CSS}</style></head><body><main>"
        f"<header><h1>{e(project)}: your guide</h1>"
        f'<p class="sub">Updated {today.isoformat()} · local file, never published</p></header>'
        f"<nav>{''.join(nav)}</nav>{''.join(parts)}</main></body></html>\n"
    )


def picture_paths(base: Path, report: dict[str, Any]) -> list[str]:
    """Absolute paths of pictures that are new or changed, to show in chat."""
    return [str(base / item["file"]) for item in report["changed"] if item["file"].endswith(".png")]
