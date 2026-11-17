# Vault: knowledge

One knowledge base for every topic, organized by **type**. The topic (project) is a frontmatter value
(`project:`), never a folder inside `wiki/`. The contract for pages is [schema.md](schema.md): read it
before creating or editing a wiki page, and do not restate it elsewhere.

## Layout

```
vault/
  wiki/<type>/        pages by TYPE (concepts, entities, decisions, sources, research, memory)
  wiki/memory/index.md  one-line memory index, loaded every session
  wiki/TAGS.md        controlled tag vocabulary
  wiki/aliases-seed.yml entity and fact resolution seed
  raw/<project>/      the person's own sources: meetings/ interviews/ sources/ snapshots/. Never changed after
                      they are kept; pages cite them by reference (hg-tool raw-ref)
  inbox/              quick capture, and hg's own working files (keep-*.md)
  journal/            append-only session journal (SessionEnd hook), never hand-edited
  projects/<slug>/    CLAUDE.md, PRD.md, planning/ (drafts)
  daily/              YYYY-MM-DD.md notes from /hg:today and /hg:dayend
  index.md            generated router (hg-tool index)
  log.jsonl           machine op log (append through hg-tool log only)
  schema.md           constitution: frontmatter, type registry, ingest map, triage, log ops
  cleaning.md         the person's own additions to the plugin's cleaning rules
```

## Knowledge flow

1. A note, a link or a file the person wants kept -> `/hg:keep` -> `raw/<p>/...` -> the librarian writes the page
2. `raw/<p>/...` -> `/hg:ingest` -> change plan -> validated pages in `wiki/`
3. question -> `/hg:wiki-query` -> answer -> saved as a page when the person says yes (`derived_from`)

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, a pasted note, a link, a file | `raw/<p>/...` via `/hg:keep`, then a page |
| Decision | `wiki/decisions/`, through a change plan |
| Durable fact or convention for every session | `wiki/memory/` page + one line in `wiki/memory/index.md` |
| Requirements of a topic | `projects/<p>/PRD.md` (the wiki links to it) |
| Spec or plan in progress | `projects/<p>/planning/` |
| Personal focus for today | `daily/YYYY-MM-DD.md` |

## Intentionally not in the wiki

- Dated reports: extract the durable signal into a standing page. Never migrate them verbatim.
- `daily/` notes and `planning/` drafts.
- `PRD.md`: linked TO, never superseded by a wiki page.

## Boundaries

- `raw/` and `journal/` are write-protected: only hg's tools (raw) and the SessionEnd hook (journal) write
  there. A guard hook blocks other writes.
- Never auto-edit `snapshot` pages, PII stubs, `PRD.md`, `planning/`, `daily/`.
- No page names a file in `raw/`, `inbox/` or `daily/`. A page cites a raw file by its source reference, which
  shows only its kind and date.
- Full rules: the plugin's `boundaries.md`, whose path is printed at session start.

## Project detection

CWD inside `projects/<slug>/` -> that project. Else a project named in the request (`projects` in
`.claude/hg.json`). Else the only project. Else list `projects/` and ask.
