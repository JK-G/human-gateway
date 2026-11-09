# Vault: knowledge

One knowledge base for every project, organized by **type**. The project is a frontmatter value
(`project:`), never a folder inside `wiki/`. The contract for pages is [schema.md](schema.md): read it
before creating or editing a wiki page, and do not restate it elsewhere.

## Layout

```
vault/
  wiki/<type>/        curated pages by TYPE (concepts, entities, decisions, sources, research, memory)
  wiki/memory/index.md  one-line shared memory index, loaded every session
  wiki/TAGS.md        controlled tag vocabulary
  wiki/aliases-seed.yml entity and fact resolution seed
  raw/<project>/      immutable sources: meetings/ interviews/ sources/ snapshots/ (ingest-only)
  inbox/              quick capture, drained by /hg:ingest --inbox
  journal/            append-only session journal (SessionEnd hook), never hand-edited
  projects/<slug>/    CLAUDE.md, PRD.md (authoritative), planning/ (drafts)
  daily/              YYYY-MM-DD.md notes from /hg:today and /hg:dayend, personal and outside git
  index.md            generated router (hg-tool index)
  log.jsonl           machine op log (append through hg-tool log only)
  schema.md           constitution: frontmatter, type registry, ingest map, triage, log ops
```

## Knowledge flow

1. `raw/<p>/...` -> `/hg:ingest` -> change plan -> validated pages in `wiki/`
2. `inbox/` -> `/hg:ingest --inbox` -> `/hg:import-source` into `raw/<p>/...` -> `/hg:ingest`
3. question -> `/hg:wiki-query` -> answer -> file back as a page when novel (`derived_from`)

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, transcript, interview | `raw/<p>/meetings/` or `raw/<p>/interviews/` via `/hg:import-source`, then `/hg:ingest` |
| Exported doc, PDF, spreadsheet | `raw/<p>/sources/` via `/hg:import-source`, then `/hg:ingest` (stub first) |
| Decision | `wiki/decisions/`, through a change plan |
| Durable fact or convention for every session | `wiki/memory/` page + one line in `wiki/memory/index.md` |
| Product requirements | `projects/<p>/PRD.md` (authoritative; the wiki links to it) |
| Spec or plan in progress | `projects/<p>/planning/` |
| Quick idea, unsorted note | `inbox/` (from `inbox/_template.md`) |
| Personal focus for today | `daily/YYYY-MM-DD.md` |

## Intentionally not in the wiki

- Dated reports: extract the durable signal into a standing page. Never migrate them verbatim.
- `daily/` notes and `planning/` drafts.
- `PRD.md`: authoritative monolith, linked TO, never superseded by a wiki page.

## Boundaries

- `raw/` and `journal/` are write-protected: only `/hg:ingest`, `/hg:import-source` (raw) and the
  SessionEnd hook (journal) write there. A guard hook blocks other writes.
- Never auto-edit `snapshot` pages, PII stubs, `PRD.md`, `planning/`, `daily/`. Raw PII never enters git.
- Full rules: the plugin's `boundaries.md`, whose path is printed at session start.

## Project detection

CWD inside `projects/<slug>/` -> that project. Else a project named in the request (`projects` in
`.claude/hg.json`). Else list `projects/` and ask.
