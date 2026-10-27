# Contributing

Thanks for helping. Own is small on purpose: a Python tool with no dependencies, one skill, and two hooks.

## Run it from your clone

```bash
git clone https://github.com/swapnildhiman19/own-the-code.git
cd own-the-code
claude plugin marketplace add "$PWD"
claude plugin install own@own-the-code
```

Claude Code then runs the plugin straight from your clone, so an edit applies from the next session.

## Before you open a pull request

```bash
python3 -m unittest discover -s tests -t tests
```

```bash
claude plugin validate plugins/own
```

- Tests use only the Python standard library and run in a throwaway `~/code-guides` (set by `tests/support.py`),
  so they never touch your real guides.
- Keep the tool dependency-free: it runs inside every repo a person opens, so it must not import anything a
  project could shadow (that is why it runs as `python3 -I`).
- Keep the words plain. Everything a person sees (cards, quiz questions, guide pages) starts with a concrete
  example and defines every term the first time it appears.
- New behaviour in the skill (`plugins/own/skills/own/`) usually needs a matching line in the README.

## Where things are

| Path | What it is |
|---|---|
| `plugins/own/lib/own_guide/` | The `own-guide` tool: state, schedules, git checks, pictures, the guide page |
| `plugins/own/skills/own/` | The `/own` skill and its references (walks, quizzes, page formats) |
| `plugins/own/hooks/hooks.json` | The session-start note and the end-of-turn check |
| `extras/own-shortcut/` | Optional `/own` shortcut (plugin commands are otherwise `/own:own`) |
| `tests/` | `python3 -m unittest` tests |

## Reporting a problem

Open an issue with what you typed, what you expected, and what happened. If a guide page looks wrong, attach the
page (remove anything private first).
