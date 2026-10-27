# Security and privacy

## What Own does with your code

- Own runs on your computer only. It has no server and sends nothing anywhere.
- It reads your repo with `git` and writes only inside `~/code-guides/` (or the folder in `OWN_GUIDES_DIR`). It
  never writes into your repos.
- The guide pages it keeps (`~/code-guides/<project>/`) can contain file names and short code excerpts from your
  projects. Treat that folder like the code itself: if you back it up to a git host, use a private repository.
- `guide.html` and `dashboard.html` are local files with no scripts and nothing loaded from the internet.
- Claude, working in your session, reads and writes the guide like any other file. What Claude sends to Anthropic
  is governed by your Claude Code settings, exactly as without Own.

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's private reporting instead: on the repository page, go to
**Security → Report a vulnerability**. Include what you found and how to reproduce it.
