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

A `raw` `ERROR` is the first thing to report, before any other finding. It means a person's own file is tracked
by git, or `vault/raw/` is not ignored and a raw file could be committed. For a tracked file, change nothing
yourself: the person tells whoever maintains the repository before anything else is published. For a
folder that is not ignored, offer `/hg:setup`. The `raw` `OK` lines are normal: source files stay on the computer
of whoever brought them in, outside git and with no backup.

A `notify-secret` or `notify-run` warning is for the person who set up the repo on GitHub. Anyone else is told to
pass it on to that person. They appear only when a messenger is declared. A `node` warning means `.claude/hg.json`
names a platform or a messenger type this plugin does not know: nothing is sent for it, and `/hg:setup --nodes`
declares it again.

The `node` lines of `hg-tool doctor` are English and for you: do not copy them.

A `permissions` warning that names an `ask` rule means Claude Code no longer asks the person before
`/hg:publish` commits: offer `hg-tool setup`, which adds the rule back. Never fix anything here with a commit of
your own. Before any commit in a department repository, run hg-tool publish check, show the person the preview it
writes, and commit only through the commit step of /hg:publish, after the person's own yes in this session.

The report always ends with the node list, also when nothing is broken. Run `hg-tool nodes` and copy the third
column of its five lines, one bullet each, in order, in the person's language: the messenger, the project platforms,
the calendar, the agent and the backup. Copy them as they are; do not add a sentence about a session's tools.
