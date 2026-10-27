# Learnings and the knowledge book: growing the user's knowledge, not just this project

Two places, so each idea is written once:
- `~/code-guides/<project>/LEARNINGS.md` - layer 1 only: **how this project uses the idea**, with a link.
- `~/code-guides/_knowledge/` - the knowledge book, shared by all projects: layers 2-4 of each idea, and
  framework pages.

## What counts as a new idea

- A language or framework mechanism used in this work (FastAPI `Depends`, Swift actors, database transactions).
- A pattern (dependency injection, idempotent jobs, optimistic UI, retries with backoff).
- A library or service feature used for the first time here.
- Anything the user asked "what is X?" about, and anything they missed in a quiz.

Before adding, look in `_knowledge/INDEX.md`: if the idea already has a book entry, only add this project to its
"Met in" list and add the layer-1 entry here.

## Layer 1, in `LEARNINGS.md` (one `### ` heading per idea; the tool counts them)

```markdown
### FastAPI Depends
- **In this project:** `app/routes/checkout.py:12` - `checkout(user = Depends(current_user))`:
  the sign-in check runs first, so `checkout` only ever sees a signed-in person.
- **Met:** 2026-10-26, while building "Checkout"
- **Full entry:** [knowledge book](../_knowledge/python-web/fastapi-depends.md)
```

## Layers 2-4, in the knowledge book: `_knowledge/<area>/<idea-slug>.md`

Areas (create as needed): `python`, `python-web`, `javascript`, `swift-ios`, `android`, `cloud`, `data`,
`ai-agents`, `system-design`, `security`, `testing`, `tooling`.

```markdown
# FastAPI Depends
**Level:** first met   <!-- "first met" | "knows the basics" | "knows it well" -->

## The idea in general
"Don't build what you need: ask for it, and let the framework hand it to you." This is dependency injection.
Use it for anything many routes need: the signed-in user, a database connection, settings.

## One level deeper
- A dependency can have dependencies of its own.
- Within one request, FastAPI runs each dependency once and reuses the answer.
- Common mistake: slow work inside a dependency every route uses - every request pays for it.

## Like something you already know
(For someone whose background is iOS.) In iOS you pass a service into a view model's initializer instead of
letting the view model create it. `Depends` is the same idea, except FastAPI does the passing for you, on every
request.
**Where the comparison stops:** in iOS you wire it once yourself; FastAPI re-runs it per request.

## Met in
- shop - `app/routes/checkout.py:12` (sign-in check)
```

Rules:
- Layer 4 compares to what the user already knows well: their `background` in Own's session note (set with
  `/own profile`). Always say where the comparison stops. With no background set, or no honest comparison,
  write "No close match" rather than forcing one.
- Add a row to `_knowledge/INDEX.md`: `| [FastAPI Depends](python-web/fastapi-depends.md) | python-web | shop |`.
- **"I know this"**: when the user says it about an idea, raise its Level one step and, next time the idea comes
  up, add only a deeper part (a new "One level deeper" bullet: edge cases, internals, performance) instead of
  repeating the basics. Questions about that idea move to the deeper part too.

## Framework pages: `_knowledge/frameworks/<name>.md`

When the work uses a part of a framework (FastAPI, Django, React, SwiftUI, an agent SDK…), grow its page:

```markdown
# FastAPI: the map
<Mermaid flowchart, at most ~12 boxes: the framework's main pieces and how a request moves through them.
Only pieces actually used so far.>

| Piece | What it does, plainly | Where you used it |
|---|---|---|
| ... | ... | shop `app/routes/checkout.py` |
```

Read the framework's real docs or source for anything you are not sure of - never guess internals.
