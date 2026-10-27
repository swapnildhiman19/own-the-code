# Existing projects: the first map, then the tour

## The first map (card answer "Build it now", or `/own map`)

Read-only on the repo: you only read code and write into `~/code-guides/<project>/`. Budget about 15 minutes of
work (up to ~30 for a very large project). Tell the user it's happening in one line, then do it.

**Big document sets** (more than ~10 plans or design docs): don't read them end to end. Read each one's title,
status or summary section, and any decision tables; read the newest first. When an older and a newer document
disagree, the newer one wins and the older decision is marked `Replaced by #n`.

1. `python3 -I ~/code-guides/.bin/own-guide init-guide` and `python3 -I ~/code-guides/.bin/own-guide first-map now`.
2. Read what already explains the project, before reading code: `README*`, `docs/`, `plans/`, files like
   `ARCHITECTURE*.md`, `DESIGN*.md`, `HOW*.md`, `CLAUDE.md` / `AGENTS.md`.
3. Find the entry points: app/server start files (`main.py`, `app.py`, `index.ts`, `AppDelegate`, `main.dart`),
   route registration (`include_router`, `app.get(...)`, `Router`), background jobs and schedulers, CLI commands,
   screens.
4. Draw **level 1** (whole-project map, at most ~15 boxes) from the real top-level folders - see FLOW-FORMAT.md.
5. Write **level 2**: one row per flow with its real entry point (`file:line` `function()`), Page = "not written
   yet". Do **not** write flow pages now.
6. Seed **CODE-DECISIONS.md** with one-line entries for decisions already written in the existing docs/plans:
   "Who decided: you, in planning" + the doc's absolute path and section; "Still true?" = `As written`, or
   `Yes, seen in code` where you checked, or `Replaced by #n`. Do not invent reasons that aren't written down.
7. `python3 -I ~/code-guides/.bin/own-guide diagrams`, `python3 -I ~/code-guides/.bin/own-guide synced`,
   `python3 -I ~/code-guides/.bin/own-guide render`. Finish by showing the **map as a picture** in chat (SKILL.md
   rule 6), then 3-4 plain lines: how many parts, how many flows, how many decisions found, and "pages get written
   as we touch each flow, or on a tour".

"Later" → `python3 -I ~/code-guides/.bin/own-guide first-map later` (offered again on another day). "Never in this project" →
`python3 -I ~/code-guides/.bin/own-guide first-map never` and `python3 -I ~/code-guides/.bin/own-guide pause --here`.

## The tour (card option "Walk one flow", or `/own tour`)

About 10 minutes, one flow, walked stop by stop. A tour is never "read a page, then a quiz": in the first trial
that left the user with right answers and no feel for how the code flows.

1. `python3 -I ~/code-guides/.bin/own-guide hotspots` - files changed most often in the last 90 days.
2. Pick the flow (from FLOW.md's list) that runs through the top hotspot files and is **not walked yet**
   (`flow_status` in `python3 -I ~/code-guides/.bin/own-guide status`), preferring one with a stale page or no
   page (`python3 -I ~/code-guides/.bin/own-guide stale`). Say which and why in one line ("Checkout - its files
   changed 23 times lately, and you haven't walked it yet").
3. Write (or fix) its page per FLOW-FORMAT.md, and its row link; `stamp` it, run `diagrams`, and fix the page if
   `diagrams` lists it under `numbering`. Don't show the picture yet.
4. Walk it: [WALK.md](WALK.md), a full walk. The walk records itself (`walked`) and turns the gaps from the
   explain-back into returning questions.
5. If the page was new or changed, end with the changed-guide note (SKILL.md).
