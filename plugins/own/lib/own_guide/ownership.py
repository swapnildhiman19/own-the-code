"""What makes the code feel like the person's own: what they've seen, decided and written.

Three records, one per kind of ownership (knowing it, steering it, putting yourself into it):

- "find" - they found something in the code themselves ("who calls apply_coupon()?").
- "call" - they made a real decision at a fork ("expired coupon: reject it, or a 24-hour grace?").
- "line" - they wrote the 1-3 lines that carry a change.

Each record says who did it: "you" (the person) or "claude" (they chose "Claude handles it", or it
was a busy day). Claude-made calls are counted too, so the guide can list them for a later look.

`seen_files()` answers the question the debug-first card depends on: has the person been shown this
code? Mia reports that SPRING10 is refused at checkout. Claude's three likeliest places are
`shop/coupons.py`, `shop/cart.py` and `web/checkout.js`. Only if every one of them is on a flow page
she has walked, and none of them changed since that page was checked, is "Where would you look first?"
a fair question. Otherwise she'd be guessing about code she has never seen.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

KINDS = ("call", "line", "find")
WHO = ("you", "claude")
WHY = ("", "skipped", "busy")
MAX_WHAT = 200


def new_event(kind: str, who: str, what: str, day: str, why: str = "", file: str = "") -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if who not in WHO:
        raise ValueError(f"who must be one of {WHO}")
    if why not in WHY:
        raise ValueError(f"why must be one of {WHY[1:]} (or left out)")
    what = " ".join(str(what or "").split())[:MAX_WHAT]
    if not what:
        raise ValueError("say in one line what was decided, written or found")
    event = {"date": day, "kind": kind, "who": who, "what": what}
    if why:
        event["why"] = why
    if file:
        event["file"] = " ".join(str(file).split())[:MAX_WHAT]
    return event


def counts(events: list[dict[str, Any]]) -> dict[str, int]:
    """e.g. {"call_you": 2, "call_claude": 1, "line_you": 3, ...}: every kind/who pair, 0 when none."""
    out = {f"{k}_{w}": 0 for k in KINDS for w in WHO}
    for event in events:
        key = f"{event.get('kind')}_{event.get('who')}"
        if key in out:
            out[key] += 1
    return out


def busy_today(settings: dict[str, Any], today: dt.date) -> bool:
    """`own-guide busy` marks one day: Claude handles every ownership card by itself until it ends."""
    return settings.get("busy_day") == today.isoformat()


def repo_path(name: str, top: str) -> str:
    """A file as the guide's flow pages name it: repo-relative, forward slashes, no ':line' or ':function'.

    "shop/cart.py:42" and "/repo/shop/cart.py" (inside /repo) both become "shop/cart.py".
    """
    name = name.strip()
    match = re.match(r"^(.*?):[\w.]+$", name)
    if match and not re.match(r"^[A-Za-z]:[\\/]", name):  # keep Windows drive letters
        name = match.group(1)
    path = Path(name)
    if path.is_absolute():
        try:
            name = os.path.relpath(path, top)
        except ValueError:  # another drive on Windows
            return name.replace("\\", "/")
    return str(PurePosixPath(*Path(name).parts)) if name else name


def seen_files(files: list[str], pages: dict[str, list[str]], walked: set[str],
               stale: dict[str, set[str] | None]) -> dict[str, Any]:
    """Which of `files` the person has been shown, and whether a guess about them is fair.

    pages:  flow page name -> the repo files its header lists
    walked: flow pages the person has walked at least once
    stale:  flow page name -> the files that changed since it was checked (None = the whole page is out of date)
    """
    def unchanged(page: str, name: str) -> bool:
        if page not in stale:
            return True
        changed = stale[page]
        return changed is not None and name not in changed

    seen, unseen, via = [], [], {}
    for name in files:
        fresh_walked = [page for page, listed in sorted(pages.items())
                        if name in listed and page in walked and unchanged(page, name)]
        if fresh_walked:
            seen.append(name)
            via[name] = fresh_walked
        else:
            unseen.append(name)
    return {"ask_guess": bool(files) and not unseen, "seen": seen, "unseen": unseen, "via": via}
