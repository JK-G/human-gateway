# {{PROJECT_NAME}}

One person's own place for notes, decisions and what they know, built on the plugin `hg`. hg keeps everything in
this folder and sends nothing from it. Commands, hooks and tools come from the plugin. Write to the person
in {{CONTENT_LANGUAGE}}, in plain words.

## Map

| Path | Purpose |
|---|---|
| `vault/` | Knowledge: wiki pages by type, projects. See [vault/CLAUDE.md](vault/CLAUDE.md). |
| `vault/raw/`, `vault/inbox/`, `intake/` | The person's own source files, kept as they came in. |
| `DASHBOARD.md` | The person's own view: what waits, what was kept, the topics. Generated. |
| `CLAUDE.local.md` | The person's own rules for how Claude works with them. |
| `.claude/hg.json` | Settings of this folder. |

## What the person says

| They say | Command | What happens |
|---|---|---|
| "zapisz", "keep this" | `/hg:keep` | A note, a link or a file is kept and gets a page |
| "co wiemy o ...", "what do we know about ..." | `/hg:wiki-query` | An answer from the pages |
| "co mam dziś", "what is on today" | `/hg:today` | The start of the day |
| "kończę na dziś", "I am done for today" | `/hg:dayend` | The end of the day |
| "coś nie działa", "something is not working" | `/hg:doctor` | A check of this folder |

## Rules

- The boundaries are printed at session start.
- Nobody hand-edits `vault/index*.md`, `vault/log.jsonl` or `vault/journal/`: tools write them.

@vault/wiki/memory/index.md
@CLAUDE.local.md
