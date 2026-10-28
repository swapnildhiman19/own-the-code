# The quiz: a friendly thinking prompt, not an exam

## 1. The opener card

Only after the user has seen the Before/After code walk of this work ([CODE-WALK.md](CODE-WALK.md)): never quiz
code they haven't been shown (SKILL.md rule 10). Every question is about something in that picture or in a walk
they did. Not after they skipped a card or reported a problem in this turn (SKILL.md rule 11).

One AskUserQuestion, header "Quiz":
- Question: `Quiz on <feature, in their words>: <N> questions, about <M> minutes.` (M ≈ N × 40 seconds, rounded up)
- Options: **Walk me through it first (~3 min)** · **Start** · **Later** (saved; asked again on a later day in
  this project) · **Skip this one** (not saved)

Walk first → the short walk of what changed ([WALK.md](WALK.md)), then straight into the questions.
Later → `python3 -I ~/code-guides/.bin/own-guide quiz-later --feature "<feature>"`. Skip → `python3 -I ~/code-guides/.bin/own-guide quiz-skip --feature "<feature>"`.

## 2. How many and which

- **3 questions** for a normal feature; +1 for each extra Claude-alone decision or new idea beyond the first;
  **at most 5**. Plus up to 2 due returns (`python3 -I ~/code-guides/.bin/own-guide due`), asked after the new ones.
- Slots: always **1 trace-or-debug** and **1 why**, plus rotating: **what-if-it-grows**, **a new idea**, or
  **the same idea in a different setting** (transfer: "In a Flask app, where would this check go?").
- Source priority: decisions Claude made alone → new ideas → the plan's "After this ships, you'll be able to
  answer:" questions → flow steps.
- Never ask from a stale page: check `python3 -I ~/code-guides/.bin/own-guide stale` first and fix the page.
- Difficulty follows `level` in `python3 -I ~/code-guides/.bin/own-guide status`: level 1 = concrete (which file, which step); level 2+ = more
  what-if, transfer and "why not the other way".

## 3. Writing one question

- One AskUserQuestion per question, header = the kind ("Trace", "Why", "Debug", "What if", "New idea").
- Question text: a short real situation first ("Mia can sign in but her Checkout button is grey."), then the
  question. Plain words. No trivia (no line numbers), no trick wording.
- Options: **3 believable choices + "Not sure, show me"**. Wrong choices are real files, real functions, real
  alternatives that a reasonable person might pick - never silly. The "type your own answer" box is added
  automatically.
- **Position:** run `python3 -I ~/code-guides/.bin/own-guide slot` before writing each question's options and put
  the right answer where it says. Never choose it yourself: left to habit, it lands first again and again, and
  the card highlights the first option.
- When the question is about code, use the option `preview` to show the short code snippet each choice refers to.
- Never reveal or hint the answer in the question, and never answer before they do.

## 4. After each answer (immediately)

2-4 friendly but firm lines, always with evidence:
- Right: "Right." + one sentence on why + the `file:line` that shows it.
- Wrong: "Not quite." + what their choice would actually mean (where that thing really happens, `file:line`) + the
  right answer + the `file:line` that proves it.
- Typed answer: say which part is right and which isn't, each with its line.
- Not sure: explain simply with a fresh concrete example (the repair rule), then the `file:line` to open.
- If they push back: re-read the code. Change the verdict only when the code shows you were wrong, and quote that
  line. Never turn a wrong answer into a right one to be kind, and never go vague when the code is clear.
Never "Wrong!", never a score.

Record each new question right away (store what it tests and the correct gist, not the wording):

```bash
python3 -I ~/code-guides/.bin/own-guide add-question --kind debug --tests "where a grey Checkout button comes from" \
  --answer "the cart check refuses an empty cart (cart.py:52 can_checkout)" \
  --link "app/cart.py:can_checkout" --source "flow:checkout" --feature "Checkout" --result miss
```

`--source`: `flow:<page-name>` | `decision:<number>` | `idea:<slug>` | `plan`. `--result`: `right` | `miss` | `not-sure`.
If they miss an idea question, add or update its LEARNINGS / knowledge-book entry.
If they type "I know this" about an idea, level it up (LEARNINGS-FORMAT.md) and record the answer as `right`.

## 5. Returning questions

`python3 -I ~/code-guides/.bin/own-guide due` lists them (max 2 per sitting, oldest and most-missed first). For each: **write a new wording**
of what it `tests` (new situation, new choices, the position from `slot`), ask it, give feedback, then
`python3 -I ~/code-guides/.bin/own-guide record <id> right|miss|not-sure`.

## 6. Ending

`python3 -I ~/code-guides/.bin/own-guide quiz-done --feature "<feature>" --asked <N> --right <M>` → its `next_returns` gives the dates.
Then `python3 -I ~/code-guides/.bin/own-guide render` quietly. Say one line: "Done. 1 question will come back on Thursday." (or "Done -
nothing coming back for this one."). No score, no percentages.
