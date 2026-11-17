# __NAME__: project context

> **Slug:** `__SLUG__` · **Created:** __DATE__
> **Knowledge:** durable knowledge lives in `vault/wiki/<type>/` with `project: __SLUG__` (contract:
> `vault/schema.md`). Raw sources live in `vault/raw/__SLUG__/` in this folder.

## Project

One paragraph: what __NAME__ is, who it serves, and the problem it solves. Replace this text.

## Status

| Field | Value |
|---|---|
| Stage | idea / discovery / building / pre-launch / live / sunset |
| Current focus | the one thing that matters this month |

## Sources of truth

- **[PRD.md](PRD.md)**: requirements. Read it before any product decision. The wiki links to it.
- Decisions: `vault/wiki/decisions/` filtered by `project: __SLUG__`.

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, interviews, a pasted note | say "zapisz": kept under `vault/raw/__SLUG__/`, then a page (`/hg:import-source` and `/hg:ingest` do the same in two steps) |
| Spec or plan in progress | `planning/` |
| Settled knowledge | `vault/wiki/<type>/` with `project: __SLUG__` |

## Glossary

Domain terms live as wiki pages (`concept`, or the optional `glossary-term` add-on). Name variants go in
`vault/wiki/aliases-seed.yml`.
