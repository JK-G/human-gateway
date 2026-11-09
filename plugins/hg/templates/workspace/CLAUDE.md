# {{PROJECT_NAME}} workspace

A department workspace built on the Human Gateway plugin `hg`. This repo holds the content; commands,
hooks and tools come from the plugin. Write to people in {{CONTENT_LANGUAGE}}.

## Map

| Path | Purpose |
|---|---|
| `vault/` | Knowledge: wiki by type, raw sources, journal, projects, daily notes. See [vault/CLAUDE.md](vault/CLAUDE.md). |
| `gates/` | Approval gates. Written only by `hg-tool gate`. |
| `DASHBOARD.md` | Your own view of gates, projects and activity. Generated, outside git. |
| `intake/` | Files and links waiting for a scan. Outside git. |
| `.claude/hg.json` | Workspace configuration. |

## Commands

| Command | Purpose |
|---|---|
| `/hg:init` | Build the context map from `intake/` and pasted links |
| `/hg:today`, `/hg:dayend` | Start and end of the day |
| `/hg:import-source` | Bring an outside file into `vault/raw/` |
| `/hg:ingest` | Turn a raw source into wiki pages through a validated change plan |
| `/hg:wiki-query` | Ask the wiki |
| `/hg:gate` | Create, list and approve gates |
| `/hg:doctor`, `/hg:setup` | Check or repair this workspace |

## Rules

- The boundaries and the list of what never enters git are printed at session start.
- Commit only when the person asks.
- Nobody hand-edits `vault/index*.md`, `vault/log.jsonl`, `vault/journal/` or `gates/`. The one exception: a person
  may add to the section for the next person in a gate, in an editor.

@vault/wiki/memory/index.md
