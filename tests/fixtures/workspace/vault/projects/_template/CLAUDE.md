# __NAME__: project context

> **Slug:** `__SLUG__` · **Created:** __DATE__
> **Knowledge:** durable knowledge lives in `vault/wiki/<type>/` with `project: __SLUG__` (contract:
> `vault/schema.md`). Sources go to `vault/raw/__SLUG__/`.

## Project

One paragraph: what __NAME__ is, who it serves, and the problem it solves. Replace this text.

## Status

| Field | Value |
|---|---|
| Stage | idea / discovery / building / pre-launch / live / sunset |
| Owner role | e.g. product owner |
| Current focus | the one thing that matters this month |

## Sources of truth

- **[PRD.md](PRD.md)**: authoritative requirements. Read it before any product decision. Never
  auto-edited by routines; the wiki links to it.
- Decisions: `vault/wiki/decisions/` filtered by `project: __SLUG__` (or `/decision-log`).

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, interviews | `vault/raw/__SLUG__/meetings/` or `interviews/`, then `/ingest` |
| Spec or plan in progress | `planning/` |
| Settled knowledge | `vault/wiki/<type>/` with `project: __SLUG__` |
| Agent output | `digests/<agent>/` (agents only) |
| Deferrable action | `tasks/playbooks/` via `/capture-task` |

## Team roles

Roles, never names (names change, and subagents should not need them).

| Role | Responsibility |
|---|---|
| Product owner | priorities, sign-off |
| Engineering lead | implementation, estimates |

## Glossary

Domain terms live as wiki pages (`concept`, or the optional `glossary-term` add-on). Name variants go in
`vault/wiki/aliases-seed.yml`.

## Digests

Which agents push into `digests/`, and who reads them. See [digests/README.md](digests/README.md).

| Agent | Folder | Cadence |
|---|---|---|
| (none yet) | | |

## Boundaries

Documentation only. Code lives under `code/` and is changed only from that layer.
