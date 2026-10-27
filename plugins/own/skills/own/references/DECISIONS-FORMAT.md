# CODE-DECISIONS.md: why the code is built this way

Named CODE-DECISIONS (never plain DECISIONS) so it cannot be confused with any "decisions" feature a product has.

## What counts as a decision worth writing down

Anything a teammate might ask "why?" about:
- picking a library, service or API ("SendGrid, not plain SMTP")
- the shape of stored data (a new field, a new collection or table, denormalising)
- a tradeoff (fast vs cheap, simple vs flexible, now vs later)
- anything about permissions, security or privacy
- anything hard to undo (a migration, a public API shape)
- anything that differs from the plan

Not: names, formatting, obvious steps, things the framework forces. Expect 0-5 per feature, not 50.

## While building: the Inbox

The moment you make such a choice and the plan did not settle it, add one line under `## Inbox`:

```markdown
- 2026-10-26 - Loaded `payment_client()` inside `charge()`, not at the top of the file - because a top-level import creates a circular import with `app/orders.py` (app/payments.py `charge`)
```

If the choice **changes the plan** (switching database, dropping a requirement), ask the user first instead.

## At the end of the work: full entries

1. Add one row per decision to the index table at the top (the tool counts rows that start with `| <number> |`):

```markdown
| # | Decision | Who decided | Still true? |
|---|---|---|---|
| 1 | The server checks coupons; the web app only shows the result | You, in planning | Yes, seen in code |
| 2 | Payments load their client inside `charge()` | Claude, while building | Yes, seen in code |
```

   "Still true?" uses only these words:
   - `Yes, seen in code` - you checked the code and it still works this way.
   - `As written` - taken from a document (a plan, a README) and not checked against the code yet.
   - `Replaced by #n` - a later decision or the code changed it (see "When a decision changes later").

2. Add an entry below the table. **Claude-alone decisions get the full entry**:

```markdown
<a id="2"></a>
### 2. Payments load their client inside `charge()`
- **Who decided:** Claude, while building. The plan didn't cover it.
- **What we chose:** `charge()` in `app/payments.py` loads `payment_client()` inside the function.
- **Why:** `app/orders.py` already loads `app/payments.py`; loading it back at the top of the file would make
  each file need the other first, and Python gets stuck (a circular import).
- **What we didn't choose:** loading it at the top of the file - it creates the loop.
- **Where in the code:** `app/payments.py:40` `charge()`
- **New idea here:** circular import → [LEARNINGS](LEARNINGS.md#circular-import)
```

   **The user's own planning decisions get one line** plus where the plan lives. The guide sits outside the repo, so a
   relative link would point inside `~/code-guides/`: give the plan's absolute path instead (a plan in the repo:
   `<repo root>/plans/<file>.md`; a Claude plan: `~/.claude/plans/<file>.md`), plus the section name:

```markdown
<a id="1"></a>
### 1. The server checks coupons; the web app only shows the result
- **Who decided:** you, in planning → `/Users/<you>/<repo>/plans/<file>.md`, section "<the section>"
```

   **"Changed the plan"** decisions (asked first) get the full entry, with "Who decided: you, when I asked".

3. Empty the Inbox.

## When a decision changes later

Never delete the old entry. Set its index row to `Replaced by #7` and add one line at the top of its entry:
`> Replaced by #7 on <date>: <one-line reason>`.
