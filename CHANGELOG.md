# Changelog

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
