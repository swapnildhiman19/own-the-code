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

0. **Start from what the user can see, before any code.** The picture's first step is what they type or click
   and what they see happen, in their own project ("On your screen" of step 1). No file names, no code, no
   internal words (settings file, hook) until that is clear. A walk through code for something they have never
   seen working loses them; in a trial the reply was "I have not seen anything and you are throwing all these
   things". If they say they're lost: stop the walk, say plainly in your last message what went wrong and what
   the thing does from their side (no code), ask nothing more that turn, and offer to continue later.
1. The flow page must exist and be fresh: run `python3 -I ~/code-guides/.bin/own-guide stale`; write or fix the
   page per [FLOW-FORMAT.md](FLOW-FORMAT.md), `stamp` it, then run `diagrams`. If `diagrams` lists this page under
   `numbering`, fix the page first: the walk uses the picture's arrow numbers.
2. Read the real code of every step now. Every line you show comes from this reading.
3. Pick **one concrete example from their real project or this conversation** (SKILL.md rule 14): a real thing
   they asked for or saw ("you asked why <the screen> showed <what was wrong>"), with the real files. Never the
   made-up shop.
   Every stop says what happens to this example.
4. Group the page's numbered steps into stops: 5-7 for a full walk, 3-4 for a short one. Each stop is a run of
   neighbouring arrows ("Stop 2: arrows 3-4"). Give each stop a 1-3 word name: Button, Door, Waiting room...
5. Write the walk's code walk (CODE-WALK.md) for the whole flow once, with every step's screen, real code,
   values and calls filled in. **The picture is the walk**: the user reads each stop in it.

## Each stop: show it, then ask about what is on screen

In the desktop app, text written in the middle of a turn is shrunk to one line (SKILL.md rule 13). So a stop is
never explained in chat text. It is explained by the picture:

1. Draw the picture opened at this stop's first arrow:
   `python3 -I ~/code-guides/.bin/own-guide walk-page <walk.json> --step <first arrow of the stop>`, then pass the
   `chat` file to the inline picture tool. Each step in it already shows the screen, the code, the values and who
   calls whom. Put what's special about this stop in the steps' `note`.
2. Then, unless it was the last stop, one **check card** (AskUserQuestion, header "Check"). It asks about what
   the picture shows *now*, never about a stop not shown yet (SKILL.md rule 10):
   - Question: start with the verdict on the previous card if there was one (below), then
     `Stop k of N: <name> (arrows a-b). <one line saying what to look at, e.g. "Look at step 3's code and values.">
     <the question>`. Answerable from the picture alone.
   - Good questions apply what's on screen to a new case from the same project: "Step 3's check lets an edit
     through when `agent_id` is set. Which of these edits from today's session is held?"
   - 3 believable options from the same flow, then "Not sure, show me" last.
   - Position: run `python3 -I ~/code-guides/.bin/own-guide slot` before writing the options and put the right
     answer where it says. Never choose the position yourself.

The first card of the walk also says, in its first line, how the walk works: "4 stops. Each picture opens at the
stop; the question is about what you see in it. No score."

## The verdict: firm, with evidence

The verdict goes **at the top of the next card's question** (or of the explain-back card after the last stop),
never in chat text between cards, where it would be shrunk to one line:

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

"Give me a fill-in start" → a new card with a sentence that has blanks over the key moves ("<Their example> makes __
trips to the server. First it checks __, then __, and only after __ does the screen change."), and the user
types it filled in.

Then grade it, firmly, as the **last message of your turn** (so it is shown in full, SKILL.md rule 13):

1. A one-line verdict ("The pieces are right, the order isn't yet").
2. A table: what they got right | where it is in the code (`file:line`).
3. What's wrong or missing, numbered, each with the line that shows it. Wrong order and missing steps matter most:
   they are the flow.
4. A full answer in at most 3 sentences.
5. Now show the whole flow as a code walk ([CODE-WALK.md](CODE-WALK.md)): every step with its screen, code,
   values and calls, to compare with their version. It is saved as `walks/<flow>.html`, so they can open it
   again any time.

## Record it

1. `python3 -I ~/code-guides/.bin/own-guide walked <page> --stops <N> --asked <check cards> --right <right>
   --explain full|partial|missed|skipped` (`full`: nothing important wrong or missing; `partial`: some gaps;
   `missed`: mostly wrong or missing; `skipped`: the user skipped the explain-back).
2. Each important gap from the explain-back (at most 2) becomes a returning question, so it comes back tomorrow
   (the command's shape below; the words come from their project):

   ```bash
   python3 -I ~/code-guides/.bin/own-guide add-question --kind trace \
     --tests "the order in checkout: the coupon is checked before the payment is taken" \
     --answer "app/cart.py:52 apply_coupon() runs before app/payments.py:40 charge()" \
     --source flow:checkout --feature "Walk: Checkout" --result miss
   ```

3. Check cards are not stored as questions: they test what was just on screen, not memory. If there's a good
   one, end with one "Find it yourself" card ([OWNERSHIP.md](OWNERSHIP.md)): something they look up in their own
   editor.
4. `python3 -I ~/code-guides/.bin/own-guide render` quietly. End your last message with one line: "Walked. 2 gaps
   come back tomorrow; this flow counts as yours once you answer right on a later day."

The flow now shows as "Walked" in the user's progress. It becomes "Got it" only after a right answer on a later
day: right answers on the day of the walk only show that they just saw it.

## Pace

- Full walk about 10 minutes, short walk about 3. A stop that needs more than about 12 lines of code or 2 new terms
  is two stops, or needs cutting.
- The user can say "faster" (fewer, bigger stops, shorter code) or "slower" (more stops) at any point. Follow it
  for the rest of the walk.

## Short walk of what changed (quiz opener "Walk me through it first")

- The example is the feature just built, with a real input from this conversation.
- 3-4 stops on the code that changed, in the order it runs: the Before/After code walk opened at each stop, and
  a check card about what it shows.
- Explain-back in 1-2 sentences: "What does the new code add to the flow?"
- Record `walked <page>` for each flow page the change belongs to, then go straight into the quiz questions
  ([QUIZ-RULES.md](QUIZ-RULES.md)) without asking the opener again.
