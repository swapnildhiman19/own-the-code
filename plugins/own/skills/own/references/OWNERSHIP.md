# Your call, your line, find it yourself

Why this exists: pictures let the user *watch* the code. They don't make it *theirs*. Research on the feeling
"this is mine" (psychological ownership) finds it grows three ways: knowing something closely, steering it, and
putting yourself into it. In one study of employees, putting yourself in had the largest effect. The "IKEA
effect" study found the same: people value what they built themselves, but only when the work ends in success.
In Auto mode Claude makes every decision and writes every line, and the user presses Enter. So Own adds one
small piece of each, per change:

| Feeling | Card | Example |
|---|---|---|
| Knowing it | **Find it yourself**: one thing the user finds in their own editor | "Open app/cart.py and find who calls `apply_coupon()`." |
| Steering it | **Your call**: at a real fork, Claude stops, recommends, and the user decides | "Expired coupon: refuse it, or accept it for 24 more hours?" |
| Putting yourself in | **Your line**: the user writes the 1-3 lines that carry the change | `grace = row.expires + timedelta(hours=24) if row else None` |

**Every card can be handed back:** "Claude decides" / "Claude writes it" / "Just show me". And **busy today**
(below) skips all three for the day.

## Starting a change (Own held back your first code edit)

Own holds back the first code edit of each piece of work, once, with a note.

1. **A small fix** (one file, about 15 changed lines or fewer): make the edit again and carry on. Nothing else.
2. **Otherwise**, in one moment, before building:
   1. The "about to change" picture ([CODE-WALK.md](CODE-WALK.md), `moment: before`).
   2. **Your call**, if this change has a real fork. At most one.
   3. **Your line** offer.
3. Then make the held edit again and build. The only later interruption is handing over Your line, if they
   took it.

If status says `busy_today` (or the session note says "Busy today"): show the picture, skip the cards, decide and
write yourself, and record each one as Claude's (below).

## Your call

A **fork** is a point where the change could reasonably go two ways, both work, and the choice changes what
users see, what it costs, or what would be hard to undo later. Examples: "after how many failed payments do we
pause a store's checkout: 1 or 2?", "refuse an expired coupon, or give 24 more hours?". **Not forks**: names,
which file, the shape of a loop, anything the user wouldn't notice. Decide those yourself.

One AskUserQuestion, header "Your call":

- The question carries the setup: the fork in one line, then what each choice means for a real person, with the
  concrete example ("With 1: one declined card pauses checkout for everyone in the store. With 2: a broken
  payment link is caught a moment later, but one declined card can't stop the others.").
- Options: your recommendation first, labelled "(Recommended)", with the reason in its description; the other
  choice; **"Claude decides"**.
- Then record it, and add one line to the `## Inbox` of CODE-DECISIONS.md with who decided:

  ```bash
  python3 -I ~/code-guides/.bin/own-guide owned call --who you --what "Expired coupons get 24 more hours"
  python3 -I ~/code-guides/.bin/own-guide owned call --who claude --why skipped --what "..."   # "Claude decides"
  ```

## Your line

Pick the 1-3 lines **where the new behaviour lives**: the condition, the calculation, the query that the change
is about. Never boilerplate, imports or wiring.

One AskUserQuestion, header "Your line": "Write the line that decides <what> yourself (~3 min)?" with the line's
job in plain words. Options: **"I'll write it"** / **"Claude writes it"**.

- **"I'll write it"**: build everything around it. At that spot leave a clear stub, the only gap in the code:

  ```python
  # YOUR LINE: when does an expired coupon stop working?
  # You have: row.expires (a datetime, or row is None when the code doesn't exist), now (a datetime).
  # Coupons get 24 more hours after row.expires.
  grace = ...  # <- write this
  ```

  Tell them the `file:line`, show that step of the code walk with its values, run
  `python3 -I ~/code-guides/.bin/own-guide line-handed` (so this piece of work stays open while they write),
  and wait. When they say it's done:
  read it, run the tests. If a test fails, show the failing value and let them fix it: hints, not the answer, up
  to 2 rounds, then offer to show it. It must end in success (tests pass): that's what makes it theirs. Then one
  kind review: what works, and one thing to improve and why. Record it:

  ```bash
  python3 -I ~/code-guides/.bin/own-guide owned line --who you --file app/cart.py --what "the 24-hour grace check"
  ```

- **"Claude writes it"**: write it and record `owned line --who claude --why skipped --what "..."`.
- "Let me write this part" (the user asks for it): the same, with a 5-15 line gap.

## Find it yourself

Once per end-of-work picture or walk, when there's a good one: something the user finds in their own editor,
about the code they were just shown. "Who calls `apply_coupon()`?", "Where is `coupon.active` first set?". Tell
them how: their editor's "Find references" or "Go to definition" (in Xcode: Find Call Hierarchy, Jump to
Definition).

One AskUserQuestion, header "Find it": the question, then **"I'll look"** / **"Just show me"**. When they
answer, give a firm verdict with the `file:line` that proves it (SKILL.md rule 7), then record
`owned find --who you --what "who calls apply_coupon()"`.

## Busy today

When the user says they're short on time, or picks "Busy today":

```bash
python3 -I ~/code-guides/.bin/own-guide busy        # until the day ends
python3 -I ~/code-guides/.bin/own-guide busy --off  # back to normal
```

Until the day ends: no Your call, Your line or Find it cards. Claude decides and writes, and records each one
with `--who claude --why busy`. Pictures are still shown and saved. The guide page lists "Calls Claude made for
you", so the user can look at them later.

## Never

- More than one Your call and one Your line per piece of work.
- A card right after the user skipped or postponed one, or reported a problem (SKILL.md rule 11).
- A "your line" that is boilerplate, or a "fork" that only Claude would notice.
