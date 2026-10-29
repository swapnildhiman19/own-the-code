# The code walk: show before you ask

Why this exists: Claude changes code the user has never seen. Then the user spots something wrong on screen,
and Claude asks "Where would you look first?" about files they have never been shown. Any answer is a coin
toss. In two real cases the user picked "Not sure, just fix it" both times, and said it left them feeling like
an outsider in their own project. Studies of learning point the same way: for code someone doesn't know yet,
seeing a worked example (how it runs, how it was fixed) teaches more than being asked to solve it first. Asking
first pays off once they know that code. Showing also has to tie together what's on screen, which code ran and
what the values were, step by step, because people don't connect those by themselves.

So: **show first, then ask.** The code walk is how Own shows.

## What the user sees

One picture, with every part tied to the same step numbers:

1. **The numbered flow.** 2-5 lanes, left to right: the user's screen first ("You: the screen"), then the
   parts the code runs through ("Web app: src/cart.js", "Server: app/cart.py", "Database: coupons"). One arrow
   per step, numbered.
2. **Each step**, when they click its arrow or number:
   - **On your screen**: what they see at this moment.
   - **The code that runs**: `file:line function()`, the real lines (at most about 12), the key line
     highlighted.
   - **The values at this moment**: the real values flowing through those lines, like Xcode's variables panel
     at a breakpoint.
   - **Who calls whom to get here**: the chain of calls from the starting point to this step's function,
     outermost first. It says how each one reaches the next: it *calls* it, *runs* it (a timer or a thread
     start), *wakes another thread* (a signal, not a call), makes an *HTTP request* to it, or *returns* to it.
3. **Marks**: steps that *will change* (amber), that *changed* (green, with a Before / After switch), or where
   it *broke* (red).

Two places code connects without a direct call are what people miss most, so always show them: a thread being
woken (a background check, a queue, a timer), and an HTTP hop between the page and the server. When two chains
never call each other but meet at one value (one writes it, the other reads it), say so in that step's `note`:
"The nightly job writes `coupon.active` here. The checkout reads it at step 5."

## When

| Moment | `moment` | What it shows |
|---|---|---|
| Starting a change (Own held back the first edit) | `before` | The code **as it is today**, only the part this change touches, with the steps that will change marked `will change`. If the user doesn't know this code yet, this picture is their introduction to it. |
| End of work, before any quiz card | `after` | The same steps with `after` filled in for the steps that changed, marked `changed`. The user flips Before / After. |
| A bug fixed in code the user hadn't seen | `bug` | The step where it broke marked `broken`, the bad value visible, and `after` showing the fix. |
| End of a walk ([WALK.md](WALK.md)) | `after` (or `before` if nothing changed) | The whole flow, to compare with their explain-back. |

The picture never waits for a click. Show it and carry on. What will change and why (before), what changed
(after), or what broke and why (bug) goes **inside the picture**, in the `note` of the steps it concerns, and is
repeated in 2-3 plain lines in **your last message of the turn**. Never only in text between tool calls: the
desktop app shrinks that to one line (SKILL.md rule 13). Plain words; compare to what the user already knows
(their `background`) and say where the comparison stops.

**Their real code only** (SKILL.md rule 14): the example is a real thing from their project or this
conversation ("you asked why <the screen> showed <what was wrong>", "your first edit to `<the real file>`"). The made-up shop
below only shows the shape of the JSON.

## How to make it

1. **Read the real code of every step now.** Copy the lines from the file; take `file:line` from the file as it
   is now. Never write code from memory.
2. **Values.** Use real values when they are cheap to get: test output, a log line, the app's own API, the
   database, a print while the tests run. Otherwise work them out from the code with one concrete example from
   their project and mark them: `"0.0 (worked out from the code)"`. Never show a made-up value as if it were
   real.
3. **Calls.** For each step, the chain from the entry point (a click handler, a route, a timer, `main`) to this
   step's function: at most 8 frames, each `[function, "file:line", how]`, where `how` is how it reaches the
   *next* frame: `calls`, `runs`, `wakes`, `http`, `returns` (empty for the last frame). Check each link in the
   code (who really calls this function: search for it).
4. Keep it small: 3-8 steps for most changes, never more than 12. A step that needs more than ~12 lines of code
   is two steps, or needs cutting with `...`.
5. Write the facts as JSON (shape below) to a temporary file, then run:

   ```bash
   python3 -I ~/code-guides/.bin/own-guide walk-page /path/to/walk.json
   ```

   It checks the facts (and says plainly what's wrong if anything is), saves the page in the guide as
   `walks/<flow>.html` (it opens in any browser, and the guide page links to it), and prints `chat`: a file
   with the picture for the chat. Add `--step N` to open the chat picture at step N (a walk does this at each
   stop).
6. **Show it in chat:** read the `chat` file and pass its whole text, unchanged, to the inline picture tool (in
   the desktop app: the tool that shows widgets or visuals inline). Don't retype or edit it. If this session has
   no inline picture tool, `open` the `page` path and send the file.
7. The flow page (`flows/<flow>.md`) uses the same step numbers and the same code and values in text
   ([FLOW-FORMAT.md](FLOW-FORMAT.md)), so the picture, the page and any later walk agree.

## The JSON

```json
{
  "flow": "checkout",
  "moment": "after",
  "title": "How a coupon is applied at checkout",
  "lanes": ["You: the screen", "Web app: src/cart.js", "Server: app/cart.py", "Database: coupons"],
  "steps": [
    {"from": 0, "to": 1, "label": "types SPRING10, clicks Pay",
     "title": "Mia types the coupon and clicks Pay",
     "screen": "The cart shows 42.00 and a coupon box with SPRING10 in it.",
     "file": "src/cart.js:40 pay()",
     "code": ["async function pay() {", "  const body = { items: cart.items, coupon: $('coupon').value };"],
     "hl": 1,
     "values": [["coupon", "\"SPRING10\""]],
     "calls": [["onclick (Pay button)", "src/cart.html:31", "calls"], ["pay()", "src/cart.js:40", ""]]},
    {"from": 2, "to": 3, "label": "look up SPRING10", "mark": "changed",
     "title": "The server looks up the coupon",
     "note": "This is the step that changed: expired coupons now get 24 more hours.",
     "screen": "Nothing new yet.",
     "file": "app/cart.py:52 apply_coupon()",
     "code": ["row = db.coupons.get(code)", "if row is None or row.expires < today:"],
     "hl": 1,
     "values": [["row.expires", "2026-10-25"], ["row.expires < today", "True, so it is refused"]],
     "calls": [["checkout()", "app/routes/checkout.py:12", "calls"], ["apply_coupon(code)", "app/cart.py:52", ""]],
     "after": {"code": ["row = db.coupons.get(code)", "grace = row.expires + timedelta(hours=24) if row else None"],
               "values": [["grace", "2026-10-26 23:59"], ["grace < now", "False, so it is accepted"]]}}
  ]
}
```

- `from` / `to`: lane numbers, starting at 0. The same lane twice is a step inside one part (a decision, a loop).
- `mark`: `will change`, `changed` or `broken` (or leave it out).
- `after`: only the fields that differ after the change. Leave it out for steps that didn't change.
- `hl`: which code line to highlight, counting from 0 (`-1` for none).
