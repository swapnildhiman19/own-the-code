# FLOW.md and flow pages: how the code runs

Three zoom levels, like a map app: the whole country, the list of cities, then the streets of one city.
One giant diagram of a whole project is never drawn: past ~15 boxes nobody can read it.

## Level 1: the whole-project map (top of `FLOW.md`)

- One Mermaid `flowchart`, **at most ~15 boxes**: the main parts and how a request moves between them.
- Box labels use the project's real folder or module names plus a 2-4 word plain description,
  e.g. `Auth["Sign-in check (auth/)"]`.
- Things that live outside the repo (a database, a separate service) are drawn as such:
  `DB[("Postgres")]`, `Pay["Payment provider (outside)"]`.
- Under the diagram, one plain sentence per box ("Sign-in check: works out who is calling and what they may do").
- Redraw only when a new part appears or a part goes away.

## Pictures of the diagrams

The app shows Mermaid as code, so every diagram also gets a picture. After adding or changing any diagram, run
`python3 -I ~/code-guides/.bin/own-guide diagrams`. It adds two lines right above each ```mermaid block:

```markdown
<!-- own:diagram flow-1 sha=3f2a9c1e -->
![flow-1: picture of the diagram below](diagrams/flow-1.png)
```

Never write or edit those two lines by hand; the tool keeps them in step with the diagram. Edit only the Mermaid
code, then run `diagrams` again. Prefer `flowchart TD` (top to bottom) for the map: left-to-right squeezes 15
boxes into a thin strip.

## Level 2: the list of flows (in `FLOW.md`, section `## The flows`)

One row per thing the app does. Keep this exact table shape (the tool counts the rows):

```markdown
| Flow | What it does | Starts at | Page |
|---|---|---|---|
| Checkout | Takes payment for a cart and creates the order | `app/routes/checkout.py:12` `checkout()` | [page](flows/checkout.md) |
| Nightly export | Sends yesterday's orders to the warehouse | `app/jobs/export.py:20` `run_export()` | not written yet |
```

A flow is: an API route or route group, a background job, a screen or user action, a CLI command, a
scheduled task. Name it the way a person would ask about it ("Nightly export", not `run_export`).

## Level 3: one page per flow (`flows/<flow-name>.md`)

Every flow page is its own file in `flows/` (also in small projects), and starts with this header. The tool
uses it to notice when the code under the page changes:

```markdown
---
flow: checkout
checked_commit: 3f2a9c1
checked_on: 2026-10-26
files: [src/cart.js, app/routes/checkout.py, app/cart.py, app/payments.py]
---
```

- `files`: repo-relative paths of every file the steps below mention. You write this list.
- `checked_commit`, `checked_on` and `hashes`: **never write these by hand.** After writing or fixing a page, run
  `python3 -I ~/code-guides/.bin/own-guide stamp flows/<flow-name>.md`. It records the current commit and a
  fingerprint of each listed file *as it is on disk*, so a page describing uncommitted work stays fresh until
  that file really changes.

Then these sections, in this order:

```markdown
# Flow: "Checkout" (POST /checkout)

**In one line:** Mia clicks Pay; the server checks her sign-in and her cart, applies her coupon, charges her card
through the payment provider, and answers with the order number.

<Mermaid sequenceDiagram starting with `autonumber`: participants are files or parts, labelled in plain words;
one arrow per step below, in the same order; at most ~12.>

## Step by step
1. `src/cart.js:40` `pay()`: the Pay button sends the cart to `POST /checkout`.
   - On your screen: the cart shows 42.00, SPRING10 in the coupon box.
   - Code: `const body = { items: cart.items, coupon: $('coupon').value };`
   - Values: `coupon = "SPRING10"`
2. `app/routes/checkout.py:12` `checkout()`: before it runs, FastAPI runs the sign-in check it asks for.
3. ...

## Who calls whom
- Pay button `onclick` (`src/cart.html:31`) → `pay()` (`src/cart.js:40`) → HTTP `POST /checkout` →
  `checkout()` (`app/routes/checkout.py:12`) → `apply_coupon()` (`app/cart.py:52`)
- The nightly job `expire_coupons()` (`app/jobs.py:20`, its own timer) never calls checkout: it writes
  `coupon.active`, which step 4 reads.
- Walk with pictures: [walks/checkout.html](../walks/checkout.html) (made by `own-guide walk-page`)

## If it breaks, look here first
- Everyone gets "not signed in" errors → step 2, the sign-in check.
- One person's coupon is ignored → step 4, the coupon check.

## What if it grows?
- Every checkout re-reads the whole coupon table (`app/cart.py:52`, no cache). At 100x orders that is 100x
  reads; a short-lived cache of active coupons would cut it.

## Why it's built this way
- The server checks coupons, the web app only shows the result → [CODE-DECISIONS #1](../CODE-DECISIONS.md#1)
- New idea here: FastAPI `Depends` → [LEARNINGS](../LEARNINGS.md#fastapi-depends)
```

Rules:
- **Numbered arrows = numbered steps.** The sequence diagram's line after `sequenceDiagram` is `autonumber`, so
  the picture prints 1, 2, 3... on its arrows. Arrow N is step N: exactly one arrow per step, in the same order
  (an answer arrow `-->>` is a step too). At most ~12 steps; extra detail goes into indented bullets under a step,
  never into more numbered steps. Walks group these numbers into stops ("Stop 2: arrows 3-4"), so the picture,
  the page and the walk all share one set of numbers. `diagrams` lists any flow page whose numbers don't match
  under `numbering`; fix it before walking or quizzing from that page. A small example:

  ```text
  sequenceDiagram
      autonumber
      actor Mia
      participant Web as Web app (src/cart.js)
      participant API as Checkout door (app/routes/checkout.py)
      Mia->>Web: clicks Pay
      Web->>API: POST /checkout with her cart
      API-->>Web: the order number
  ```

  with `## Step by step` items 1 (`src/cart.js:40` `pay()`), 2 (`app/routes/checkout.py:12` `checkout()`) and 3
  (`checkout.py:31`, the reply).
- Mermaid ends a message at a `;`, so never put a semicolon in an arrow's text (use a comma or "then").
- Each step names **file:line and the function**, so it still makes sense after lines move. Refresh the line
  numbers every time you touch the page, then run `stamp` again.
- One plain sentence per step: what happens, in words a newcomer understands. Steps that changed recently, or
  that are hard to follow, get the three sub-bullets of the code walk ([CODE-WALK.md](CODE-WALK.md)): what's on
  your screen, the key code line, and the real values (examples marked "(example)").
- "Who calls whom": the call chains from each entry point (a click, a route, a timer, a thread) to the functions
  in the steps, with every HTTP hop and every thread wake-up named, and any value two chains meet at. Check each
  link in the code.
- "If it breaks": 2-3 symptom → step pairs. These feed debug questions.
- "What if it grows?": 1-2 lines, from the real code (read it), about the first thing that breaks at 10x or
  100x (load, cost, data size, concurrency). Never generic advice.
- After writing or fixing a page: update its row in FLOW.md (link instead of "not written yet").
