---
name: own
description: Own the code - keeps the user's private, plain-language guide to the current project in ~/code-guides (flow map, code decisions, learnings), walks them through flows stop by stop, and runs their short quizzes. Use when they type /own (quiz, walk, progress, dashboard, map, tour, explain, profile, off, on), when a message from Own says code changed (run the end-of-work routine), or when today's card is due.
argument-hint: "[quiz | walk <flow> | progress | dashboard | map | tour | explain <flow> | profile | off [here] | on [here]]"
---

# Own the code

Own keeps the user the owner of the code Claude builds with them. Per project it keeps a private guide
**outside the repo** in `~/code-guides/<project>/`, walks them through how the code runs, and asks a short,
friendly quiz when a feature is done. The tool `own-guide` keeps every number, date and identity exact: never
hand-edit `state.json`, `PROGRESS.md`, `guide.html` or `dashboard.html`.

Own's session note says what to call the user (their `name`) and what they already know well (their
`background`). Use the name when talking to them; with no name, say "you". The examples below call them "the user".

**How to run the tool: the command in Own's session note wins.** It is normally
`python3 -I ~/code-guides/.bin/own-guide <command>`, which every example below uses. If the note's "Own's tool"
line shows a different command (another guides folder, or a full path because the shortcut couldn't be made),
run that one wherever an example below says `python3 -I ~/code-guides/.bin/own-guide`. Never use the bare name
`own-guide`: it is not on PATH in the desktop app, and some shell allowlists refuse it.

## Rules that apply to every routine

1. **Never slow delivery.** Nothing here may block building, pushing or deploying. Guide work happens after the
   work is done, and is proportionate (a few minutes, not a rewrite).
2. **Plain language.** Everything the user sees starts with a concrete case, defines every term at first use, and
   uses short sentences. If they have a preferred style for explanations, follow it. Never mention internal names
   (hook, state file, stop check, fingerprint): say "your guide", "your quiz", "questions coming back".
3. **One question at a time, with AskUserQuestion.** Cards and quiz questions always use AskUserQuestion, one
   question per call. Never answer a quiz question before the user does.
4. **Real code only.** Every file, function and line you name comes from reading the code now. Never invent.
5. **Guide files live in `~/code-guides/<project>/`, never in the repo.**
6. **Diagrams are shown as pictures, never as code.** The desktop app shows Mermaid as code, in chat and in the
   file pane. After you add or change any diagram in the guide, run
   `python3 -I ~/code-guides/.bin/own-guide diagrams`: it draws each one to `diagrams/<page>-<n>.png` and puts the
   picture above its code. In chat, show the picture: use a Mermaid-rendering tool if this session has one,
   otherwise send or link the PNG. If the tool reports the drawing program is missing, tell the user once,
   plainly, with the install command it gives; don't install anything yourself.
7. **Firm verdicts, with evidence.** Every "right" or "not quite" on a guess, quiz answer or explain-back comes
   with the `file:line` that proves it. If the user pushes back, re-read the code and change the verdict only when
   the code shows it, quoting the line. Never call a wrong answer right to be kind.
8. **The tool places the right answer.** Before writing the options of any card that has a right answer, run
   `python3 -I ~/code-guides/.bin/own-guide slot` and put the right answer at the position it gives. "Not sure,
   show me" is always last.
9. **Show the user what changed in their guide.** They should never have to dig through `~/code-guides` to find
   out. Whenever a routine changes the guide, end with the changed-guide note (below).

## Start of every routine

```bash
python3 -I ~/code-guides/.bin/own-guide where     # the guide folder for this repo
python3 -I ~/code-guides/.bin/own-guide status    # today's facts (JSON)
```

If `where` says this repo "may be the same project as" another guide: ask once with AskUserQuestion
("Same project as <folder>?" → "Same project" / "A different project"), then run `python3 -I ~/code-guides/.bin/own-guide link <folder>` or
`python3 -I ~/code-guides/.bin/own-guide register-new`. Outside a git repo, say Own only works inside git projects and stop.

## Routing

| They typed | Do |
|---|---|
| `/own` | Show the progress summary (`python3 -I ~/code-guides/.bin/own-guide render`, print its summary text), then one card: "Quiz me now" / "Walk one flow" / "Show my guide" / "Nothing now". |
| `/own quiz` | End-of-work quiz on the most recent work in this project, plus any due returns (see QUIZ). If nothing new was built, quiz due returns, else 2 questions from an existing flow page. |
| `/own walk <flow>` | Walk that flow stop by stop ([WALK.md](references/WALK.md)). Without a flow name, pick one as the tour does. |
| `/own progress` | `python3 -I ~/code-guides/.bin/own-guide render`, then show its summary text as is, in a short message. |
| `/own dashboard` | `python3 -I ~/code-guides/.bin/own-guide dashboard`, then `open` the path in its `open` field (this project's guide page: map, every flow page with its picture, decisions, learnings, "Changed" badges). Mention it is a local file, never published. |
| `/own map` | First-map routine ([FIRST-MAP-AND-TOUR.md](references/FIRST-MAP-AND-TOUR.md)). |
| `/own tour` | Tour routine (same file): pick a flow, then walk it. |
| `/own explain <flow>` | Write or fix the page if it is missing or stale, show its one-line summary, then one card: "Walk it with me (~10 min)" / "Just show me the page". The page: show its picture and send or link the file. |
| `/own profile` | Two cards, one at a time: "What should I call you?" and "What do you already know well? (used for comparisons, e.g. iOS and Swift, or React)", each with "Skip" and the typed answer (Other). Then `python3 -I ~/code-guides/.bin/own-guide profile --name "<name>" --background "<background>"` (leave out a skipped one) and confirm in one line. |
| `/own off here` / `/own on here` | `python3 -I ~/code-guides/.bin/own-guide pause --here` / `python3 -I ~/code-guides/.bin/own-guide resume --here`. Confirm in one line. |
| `/own off` / `/own on` | `python3 -I ~/code-guides/.bin/own-guide pause` / `python3 -I ~/code-guides/.bin/own-guide resume`. Confirm in one line; say "off" takes full effect from the next session and that turning the plugin off in the plugins list removes it completely. |
| "let me write this part" | Write-it-myself ([DEBUG-FIRST-AND-WRITE-IT.md](references/DEBUG-FIRST-AND-WRITE-IT.md)). |

## End-of-work routine (when Own says code changed, or after `/own quiz` with new work)

1. `python3 -I ~/code-guides/.bin/own-guide init-guide` (safe to run every time; creates only missing files), then
   `python3 -I ~/code-guides/.bin/own-guide changes --start` (remembers the guide as it is now, so the note at the
   end lists only what this routine changed).
2. `python3 -I ~/code-guides/.bin/own-guide stale` - any page you are about to rely on that is stale: re-read its code and fix the page first.
3. Find out what changed in this piece of work: `git status --short`, `git diff --stat`, recent commits from this
   session, and the conversation (what was asked, what was decided, why).
4. Update the guide, proportionately:
   - **Flows** - [FLOW-FORMAT.md](references/FLOW-FORMAT.md): add or update the flow page(s) this work touched
     (header `files` = the files the page describes; then `python3 -I ~/code-guides/.bin/own-guide stamp
     flows/<name>.md` for each page you wrote or fixed), its row in FLOW.md, and the map if a new part appeared.
     Then `python3 -I ~/code-guides/.bin/own-guide diagrams` (rule 6); fix any page it lists under `numbering`.
   - **Code decisions** - [DECISIONS-FORMAT.md](references/DECISIONS-FORMAT.md): turn every `## Inbox` line into
     a full entry (Claude-alone decisions) or a one-line entry with a plan link (the user's planning decisions);
     add any decision you made but forgot to jot down. Empty the Inbox.
   - **Learnings** - [LEARNINGS-FORMAT.md](references/LEARNINGS-FORMAT.md): new ideas met → layer 1 in
     LEARNINGS.md + the knowledge book entry (layers 2-4); framework page if a framework part was used.
5. `python3 -I ~/code-guides/.bin/own-guide synced` - records the code exactly as it is now, committed or not, so
   only later changes count as new work.
6. Show the changed-guide note (below).
7. Offer the quiz - [QUIZ-RULES.md](references/QUIZ-RULES.md). Start with the opener card; "Walk me through it
   first" runs the short walk of what changed ([WALK.md](references/WALK.md)) before the questions.
8. After the quiz (or Later / Skip): run the matching `python3 -I ~/code-guides/.bin/own-guide quiz-done | quiz-later | quiz-skip`, then
   `python3 -I ~/code-guides/.bin/own-guide render` quietly. End with one plain line, e.g. "Done. 1 question will come back on Thursday."

## The changed-guide note

Run `python3 -I ~/code-guides/.bin/own-guide changes`. It lists the guide files that are new or changed since the
last note (each with its full `path`), the new or changed pictures (`pictures`), and the guide page
(`guide_page`). Show the user, in a few lines:

```markdown
**Your guide changed:**
- [flows/checkout.md](/Users/you/code-guides/shop/flows/checkout.md) (changed): steps 4-5 now cover the coupon check
- [CODE-DECISIONS.md](/Users/you/code-guides/shop/CODE-DECISIONS.md) (changed): #7, why coupons are checked on the server
- Everything on one page: `/own dashboard`
```

Say in a few plain words what changed in each file (you just wrote it, so you know). Then show each picture in
`pictures` (rule 6). If the list is empty or says `first_look`, say nothing about it.

## Daily card (when status says `card_due_today`)

Show it at the end of your **first finished turn** of the session, never before handling the user's request. One
AskUserQuestion, header "Today", up to 4 options built from `python3 -I ~/code-guides/.bin/own-guide status`:

| Status says | Option |
|---|---|
| `first_map_offer` | This replaces the whole card: "This project has no guide yet. Build the first map now (~15 min)?" → "Build it now" / "Later" / "Never in this project". Record with `python3 -I ~/code-guides/.bin/own-guide first-map now|later|never` ("never" also runs `python3 -I ~/code-guides/.bin/own-guide pause --here`). |
| `due_now` > 0 | "N waiting questions (~1 min)" |
| `pending_quiz` | "The saved quiz on <feature> (~2 min)" |
| `tour_offer` | "Walk one flow (~10 min)" |
| always | "Not today" |

Put the `weekly_line` (if any) as the first sentence of the question text. Then `python3 -I ~/code-guides/.bin/own-guide card-shown`
(add `--weekly` if the weekly line was shown). Follow their pick: returns → QUIZ "returns"; saved quiz →
QUIZ on that feature; walk → tour routine (pick a flow, then walk it); "Not today" → one friendly line, nothing else.

## A bug the user reports

Debug-first card before investigating - see [DEBUG-FIRST-AND-WRITE-IT.md](references/DEBUG-FIRST-AND-WRITE-IT.md).
