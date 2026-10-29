# Changelog

## 0.3.1

- **Walk explanations are always visible.** The desktop app shrinks text written just before a card to one line,
  so a walk could ask about an explanation you never saw. Each stop now shows the code walk opened at that stop
  (`own-guide walk-page --step N`), and the question is about what the picture shows. Verdicts go inside the next
  card.
- **Your real code only.** Walks, pictures, pages and quizzes use your project and your conversation, never the
  made-up examples from these docs.
- No question about a step before it's shown.

## 0.3.0

- **Show before you ask.** Own never asks you to guess about code you haven't been shown. "Where would you look
  first?" now appears only for code you've walked and that hasn't changed since (`own-guide seen`). Otherwise
  Claude fixes the bug first, then shows you what broke.
- **Code walks.** One picture, shown in the chat and saved as `walks/<flow>.html` in your guide. It has numbered
  arrows, and for each step what's on your screen, the real code with the key line highlighted, the real values,
  and who calls whom to get there (calls, HTTP hops, threads woken). It appears when Claude starts a change (what
  will change), when it finishes (Before / After, before any quiz), and after a bug fix (the step that broke).
- **The first code edit waits, once.** Before Claude's first code edit of a piece of work, Own holds it back once
  so the "about to change" picture comes first. Small fixes just go ahead.
- **Your call, your line, find it yourself.** At a real fork, you make the call. You can write the 1-3 lines that
  carry a change, with Claude's help until the tests pass. And you find one thing in your own editor. Every card
  can be handed back to Claude, and `/own busy` hands them all back for the day.
- **Progress counts what's yours:** calls you made, code you wrote, things you found. Calls Claude made for you
  are listed on the guide page, to look at later.
- One learning card at a time, and none right after you skip one or report a problem.

## 0.2.0

- **Walks.** `/own walk <flow>`, the tour and a new "Walk me through it first" quiz option go through a flow stop
  by stop: real code at each stop, you guess the next stop, then you explain the whole flow back.
- **Firm, evidenced verdicts.** Every "right" or "not quite" comes with the file and line that prove it.
- **Fair answer positions.** `own-guide slot` decides where the right answer goes; it never sits in the same
  place three times in a row.
- **Numbered pictures.** A flow's picture numbers its arrows, and arrow N is step N on the page. `diagrams`
  reports pages whose numbers don't match.
- **Your guide on one page.** `/own dashboard` opens `guide.html`: the map, every flow page with its picture, the
  code decisions and the learnings, with "Changed" badges. After each update Claude lists what changed.
- **Honest progress.** A flow counts as *walked* after a walk, and as *got* only after a right answer on a later day.
- **Profile.** `/own profile` sets what Claude calls you and what you already know well (for comparisons).

## 0.1.4

- Pictures of every Mermaid diagram in the guide (the desktop app shows Mermaid as code).

## 0.1.0 - 0.1.3

- First version: the private guide (map, flow pages, code decisions, learnings), the end-of-work quiz with spaced
  returns, the first map for existing projects, progress and a local dashboard, and the on/off switches.
