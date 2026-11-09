<!-- kit:example -->
> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Acme Notes: project context

> **Slug:** `acme-notes` · **Created:** 2026-01-10
> **Knowledge:** durable knowledge lives in `vault/wiki/<type>/` with `project: acme-notes` (contract:
> `vault/schema.md`). Sources go to `vault/raw/acme-notes/`.

## Project

Acme Notes is a privacy-first note-taking app for small teams (3-30 people). Notes live on each device
first and sync through an encrypted relay, so the app works offline and the server cannot read content.
It competes on reliability offline and on trust, not on feature count.

## Status

| Field | Value |
|---|---|
| Stage | building (v1) |
| Owner role | product owner |
| Current focus | offline sync and its conflict policy |

## Sources of truth

- **[PRD.md](PRD.md)**: authoritative requirements. Never auto-edited by routines.
- Key decision: [[example--2026-01-20-acme-notes-local-first]].
- Core mechanism: [[example--acme-notes-offline-sync]].
- Shared memory: [[example--acme-notes-release-train]].

## Where things go

| Input | Destination |
|---|---|
| Meeting notes, interviews | `vault/raw/acme-notes/meetings/` or `interviews/`, then `/ingest` |
| Spec or plan in progress | `planning/` |
| Settled knowledge | `vault/wiki/<type>/` with `project: acme-notes` |
| Agent output | `digests/<agent>/` (agents only) |
| Deferrable action | `tasks/playbooks/` via `/capture-task` |

## Team roles

| Role | Responsibility |
|---|---|
| Product owner | priorities, sign-off, hotfix approval |
| PM | discovery, PRD, release notes |
| Eng lead | sync engine, estimates |
| Designer | conflict UX, onboarding |

## Glossary

- **Flagged copy**: the earlier version of a block kept beside the later one after a sync conflict.
- **Release train**: the fixed two-week release cadence.

Name variants are seeded in `vault/wiki/aliases-seed.yml`.

## Digests

| Agent | Folder | Cadence |
|---|---|---|
| (none yet; a support-observer agent would push feature requests here) | `digests/` | |

## Boundaries

Documentation only. Code lives under `code/` and is changed only from that layer.
