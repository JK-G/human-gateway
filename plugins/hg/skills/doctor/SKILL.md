---
name: doctor
description: Check that this department workspace and the tools it needs are set up correctly. Use when a hg command fails or looks wrong.
---

# /hg:doctor

Run `hg-tool doctor`. It prints one finding per line as `LEVEL<TAB>check<TAB>message`, with level `OK`,
`WARN` or `ERROR`, and exits 1 when any check is an `ERROR`.

Explain the result to the person in plain words, in `language.content` from `.claude/hg.json` when it is
readable. Lead with what is broken and the one thing to do about it. Do not list the checks that passed
unless asked. If a tool is missing, offer `/hg:setup`.
