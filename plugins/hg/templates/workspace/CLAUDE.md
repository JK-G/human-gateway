# {{PROJECT_NAME}} workspace

A department workspace built on the Human Gateway plugin `hg`. This repo holds the content; commands,
hooks and tools come from the plugin. Write to people in {{CONTENT_LANGUAGE}}.

## Map

| Path | Purpose |
|---|---|
| `vault/` | Knowledge: wiki by type, journal, projects. See [vault/CLAUDE.md](vault/CLAUDE.md). |
| `vault/cleaning.md` | This department's own rules for what a page may carry out of a person's files. |
| `vault/raw/`, `vault/inbox/`, `intake/` | Your own source files. On this computer only, never in git. |
| `gates/` | Approval gates and observations of outside sources. Written only by `hg-tool gate`. |
| `DASHBOARD.md` | Your own view of gates, projects and activity. Generated, outside git. |
| `.claude/hg.json` | Workspace configuration. |

## Commands

| Command | Purpose |
|---|---|
| `/hg:init` | Build the context map from `intake/` and pasted links |
| say "zapisz", or `/hg:keep` | Keep a note, a link or a file in one step |
| `/hg:today`, `/hg:dayend` | Start and end of the day |
| `/hg:import-source` | Bring an outside file into `vault/raw/` on this computer |
| `/hg:ingest` | Turn a raw source into wiki pages through a validated change plan |
| `/hg:wiki-query` | Ask the wiki |
| `/hg:gate` | Create, list and approve gates |
| `/hg:publish` | Check, show and send what changed |
| `/hg:doctor`, `/hg:setup` | Check or repair this workspace |

## Rules

- The boundaries and the list of what never enters git are printed at session start.
- Nothing is committed except through `/hg:publish`. Before any commit in a department repository, run hg-tool
  publish check, show the person the preview it writes, and commit only through the commit step of /hg:publish,
  after the person's own yes in this session. Nothing enforces this: git still commits, so everyone keeps to it.
- Nobody hand-edits `vault/index*.md`, `vault/log.jsonl`, `vault/journal/` or `gates/`. The one exception: a person
  may add to the section for the next person in a gate, in an editor.

@vault/wiki/memory/index.md
