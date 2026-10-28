# The walk: follow one flow, stop by stop

Why this exists: a finished flow page plus a few quiz questions is not enough to "see the code flowing", because
Claude did all the tracing and the user only took the test. On a walk the user does the tracing: at every stop
they guess where the code goes next, and at the end they explain the whole flow back. The explain-back is what
finds the real gaps. In the first trial the user guessed 5 of 5 stops right and still put two steps in the wrong
order when explaining it back.

## When

| Moment | Walk |
|---|---|
| `/own walk <flow>` | That flow, a full walk (5-7 stops, about 10 minutes) |
| `/own tour`, or "Walk one flow" on a card | Pick the flow ([FIRST-MAP-AND-TOUR.md](FIRST-MAP-AND-TOUR.md)), then a full walk |
| `/own explain <flow>` | One card: "Walk it with me (~10 min)" / "Just show me the page" |
| Quiz opener "Walk me through it first" | A short walk of what just changed (3-4 stops, about 3 minutes), then the quiz |

## Before the first stop

0. **Start from what the user can see, before any code.** In 3-4 plain steps (a small picture is better): what
   they type or click, what they see happen, what changes for them. No file names, no code, no internal words
   (settings file, hook) until that picture is clear. A walk through code for something they have never seen
   working loses them; in a trial the reply was "I have not seen anything and you are throwing all these things".
   If they say they're lost, stop the walk, show that picture, and offer to continue later.
1. The flow page must exist and be fresh: run `python3 -I ~/code-guides/.bin/own-guide stale`; write or fix the
   page per [FLOW-FORMAT.md](FLOW-FORMAT.md), `stamp` it, then run `diagrams`. If `diagrams` lists this page under
   `numbering`, fix the page first: the walk uses the picture's arrow numbers.
2. Read the real code of every step now. Every line you show comes from this reading.
3. Pick **one concrete example**: a person and a real input ("Mia orders 2 mugs with the coupon SPRING10"). Use a
   name that already appears in the project when there is one. Every stop says what happens to this example.
4. Group the page's numbered steps into stops: 5-7 for a full walk, 3-4 for a short one. Each stop is a run of
   neighbouring arrows ("Stop 2: arrows 3-4"). Give each stop a 1-3 word name: Button, Door, Waiting room...
5. Don't show the flow's picture yet: it would give away every guess. It comes after the explain-back.
6. Say how it works in two lines: "6 stops. At each you see the real code, then you guess what happens next
   before I show it. No score."

## Each stop

Show, in this order:

- **Route line**: every stop's name, the current one in bold: `1 Button → **[2 Door]** → 3 Waiting room → 4 ...`
- **Heading**: `Stop 2 of 6: the door (arrows 3-4)`.
- **Code**: at most about 12 lines of the real code. The first line is a comment with `file:line`. Cut it with
  `...` to the lines that matter. Never rewrite code from memory.
- **What it does**: at most 3 bullets on what happens to the example here. At most 2 new terms per stop, each
  defined in brackets at first use. Use an analogy only when it is honest, and say where it stops; the user's
  `background` (Own's session note) says what they already know well.
- **Values and calls**: one line with the example's values at this stop (`coupon = "SPRING10"`,
  `row.expires = 2026-10-25`), and one line with how the code got here (`checkout() → apply_coupon()`, naming
  any HTTP hop or thread wake-up). These are what make the code feel connected, not just described.

Then, unless it was the last stop, one **prediction card** (AskUserQuestion, header "Predict"):

- Question: `Stop k → k+1. <the example, one line>. <What happens next? / Where does it go? / Which check
  comes first?>`
- 3 believable options, then "Not sure, show me" last. The best wrong options are real things from this same flow
  that happen at other stops (a check that comes later, a step that already happened): then even a wrong guess
  teaches the route.
- Position: run `python3 -I ~/code-guides/.bin/own-guide slot` before writing the options and put the right
  answer where it says. Never choose the position yourself.

## The verdict: firm, with evidence

Open the next stop with the verdict on the guess:

- Right: "**Your answer: X. That's right.**" Then the line(s) of code that prove it, with `file:line`.
- Wrong: "**Your answer: X. Not quite.**" Then where X actually happens (which stop, `file:line`), the right
  answer, and the line that proves it.
- A typed answer that is partly right: say which part is right and which isn't, each with its line.
- "Not sure, show me": no verdict. Show the stop and point at the line that answers the question.

Rules:

- **The code decides**, not the user's confidence and not yours. If they push back, re-read the code. Change the
  verdict only when the code shows you were wrong, and quote the line that does. Never turn a wrong answer into a
  right one to be kind, and never go vague ("both could be true") when the code is clear.
- When their answer is more precise than what you showed (it happens), say so plainly and correct yourself, with
  the line.

## The explain-back (the most important part)

After the last stop, one AskUserQuestion, header "Explain":
"Explain it back. In 2-3 sentences, in your own words: how does <the example> get from <start> to <end>? Pick
'Other' and type it. Rough is fine; I'll say plainly what's right and what's missing, with the code line for each."
Options: "Give me a fill-in start" / "Skip explaining back".

"Give me a fill-in start" → a new card with a sentence that has blanks over the key moves ("Mia's order makes __
trips to the server. First it checks __, then __, and only after __ is the order saved."), and the user types it
filled in.

Then grade it, firmly:

1. A one-line verdict ("The pieces are right, the order isn't yet").
2. A table: what they got right | where it is in the code (`file:line`).
3. What's wrong or missing, numbered, each with the line that shows it. Wrong order and missing steps matter most:
   they are the flow.
4. A full answer in at most 3 sentences.
5. Now show the whole flow as a code walk ([CODE-WALK.md](CODE-WALK.md)): every step with its screen, code,
   values and calls, to compare with their version. It is saved as `walks/<flow>.html`, so they can open it
   again any time.

## Record it

1. `python3 -I ~/code-guides/.bin/own-guide walked <page> --stops <N> --asked <predictions> --right <right>
   --explain full|partial|missed|skipped` (`full`: nothing important wrong or missing; `partial`: some gaps;
   `missed`: mostly wrong or missing; `skipped`: the user skipped the explain-back).
2. Each important gap from the explain-back (at most 2) becomes a returning question, so it comes back tomorrow:

   ```bash
   python3 -I ~/code-guides/.bin/own-guide add-question --kind trace \
     --tests "the order in checkout: the coupon is checked before the payment is taken" \
     --answer "app/cart.py:52 apply_coupon() runs before app/payments.py:40 charge()" \
     --source flow:checkout --feature "Walk: Checkout" --result miss
   ```

3. Predictions are not stored as questions: they test the next stop, not memory. If there's a good one, end
   with one "Find it yourself" card ([OWNERSHIP.md](OWNERSHIP.md)): something they look up in their own editor.
4. `python3 -I ~/code-guides/.bin/own-guide render` quietly. End with one line: "Walked. 2 gaps come back
   tomorrow; Checkout counts as yours once you answer right on a later day."

The flow now shows as "Walked" in the user's progress. It becomes "Got it" only after a right answer on a later
day: right answers on the day of the walk only show that they just saw it.

## Pace

- Full walk about 10 minutes, short walk about 3. A stop that needs more than about 12 lines of code or 2 new terms
  is two stops, or needs cutting.
- The user can say "faster" (fewer, bigger stops, shorter code) or "slower" (more stops) at any point. Follow it
  for the rest of the walk.

## Short walk of what changed (quiz opener "Walk me through it first")

- The example is the feature just built, with a concrete input.
- 3-4 stops on the code that changed, in the order it runs: same route line, code, bullets and prediction cards.
- Explain-back in 1-2 sentences: "What does the new code add to the flow?"
- Record `walked <page>` for each flow page the change belongs to, then go straight into the quiz questions
  ([QUIZ-RULES.md](QUIZ-RULES.md)) without asking the opener again.
