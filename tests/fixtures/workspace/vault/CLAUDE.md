# Vault layer: knowledge

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
  inbox/              quick capture, drained by the heartbeat via /ingest
  journal/            append-only session journal (SessionEnd hook), never hand-edited
  projects/<slug>/    CLAUDE.md, PRD.md (authoritative), planning/ (drafts), digests/ (agent output)
  digests/<agent>/    cross-project agent and intel output (same contract as project digests)
  daily/              YYYY-MM-DD.md notes from /today and /dayend
  index.md            generated router (python3 .claude/tools/regenerate-wiki-index.py)
  log.jsonl           machine op log (append via .claude/tools/log-append.sh only)
  schema.md           constitution: frontmatter, type registry, ingest map, triage, log ops
```

## Knowledge flow

1. `raw/<p>/...` -> `/ingest` -> change plan -> validated pages in `wiki/`
2. `inbox/` -> wiki-heartbeat -> `git mv` to `raw/<p>/...` -> `/ingest`
3. `journal/` -> wiki-heartbeat -> `wiki/memory/` pages + one index line
4. question -> `/wiki-query` -> answer -> file back as a page when novel (`derived_from`)

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, transcript, interview | `raw/<p>/meetings/` or `raw/<p>/interviews/`, then `/ingest` |
| Exported doc, PDF, spreadsheet | `raw/<p>/sources/` via `/import-source`, then `/ingest` (stub first) |
| Decision | `wiki/decisions/` via `/decision-log` |
| Durable fact or convention for every session | `wiki/memory/` page + one line in `wiki/memory/index.md` |
| Product requirements | `projects/<p>/PRD.md` (authoritative; the wiki links to it) |
| Spec or plan in progress | `projects/<p>/planning/` |
| Quick idea, unsorted note | `inbox/` (from `inbox/_template.md`) |
| Personal focus for today | `daily/YYYY-MM-DD.md` |
| Deferrable action for the autonomous routine | `tasks/playbooks/<name>.md` via `/capture-task` |

## Intentionally not in the wiki

- Transient digests and dated reports (research sweeps, agent digests): extract the durable signal into a
  standing page, then let the heartbeat garbage-collect the report. Never migrate them verbatim.
- `daily/` notes, `planning/` drafts, `projects/<p>/digests/`.
- `PRD.md`: authoritative monolith, linked TO, never superseded by a wiki page.

## Boundaries

- `raw/` and `journal/` are write-protected: only `/ingest`, `/import-source` (raw) and the SessionEnd
  hook (journal) write there. A guard hook blocks other writes (exit 2 blocks in PreToolUse; any other
  nonzero exit only warns).
- Never auto-edit `snapshot` pages, PII stubs, `PRD.md`, `planning/`, `daily/`. Raw PII never enters git.
- Never modify code under `code/` from this layer. Full rules: [.claude/rules/vault-boundaries.md](../.claude/rules/vault-boundaries.md).

## Project detection

CWD inside `projects/<slug>/` -> that project. Else a project named in the request (kit.conf `PROJECTS`).
Else list `projects/` and ask. Unattended runs default to `cross`.
