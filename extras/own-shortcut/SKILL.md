---
name: own
description: Short form of /own:own (Own the code). Type /own, /own quiz, /own walk <flow>, /own progress, /own dashboard, /own map, /own tour, /own explain <flow>, /own profile, /own off [here], /own on [here].
argument-hint: "[quiz | walk <flow> | progress | dashboard | map | tour | explain <flow> | profile | off | on] [here]"
disable-model-invocation: true
---

The user typed `/own $ARGUMENTS`. This is only a shortcut for the Own plugin's skill.

Invoke the `own:own` skill with the Skill tool, passing `$ARGUMENTS` as its arguments, and follow it.

If no `own:own` skill is available (the Own plugin is turned off or removed), reply with one line and nothing else:
"Own is turned off in the plugins list, so /own does nothing right now."
