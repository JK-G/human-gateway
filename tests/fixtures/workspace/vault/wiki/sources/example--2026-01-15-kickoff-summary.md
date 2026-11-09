---
# kit:example <!-- kit:example -->
type: source-summary
project: acme-notes
temporal: snapshot
status: active
last_verified: 2026-01-20
source_raw: "raw/acme-notes/meetings/example--2026-01-15-kickoff.md"
source_hash: "sha1: <computed on ingest>"
extraction: extracted
extracted_to: ["wiki/decisions/example--2026-01-20-acme-notes-local-first.md", "wiki/concepts/example--acme-notes-offline-sync.md", "wiki/memory/example--acme-notes-release-train.md"]
sources: ["raw/acme-notes/meetings/example--2026-01-15-kickoff.md"]
aliases: ["acme notes kickoff", "kickoff 2026-01-15"]
summary: "Kickoff for Acme Notes v1: local-first storage proposed, offline sync scoped, release cadence moved to two weeks, one open question on shared notebooks."
---

> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Source: Acme Notes kickoff (2026-01-15)

Original: `raw/acme-notes/meetings/example--2026-01-15-kickoff.md`. Participants by role only: PM, Eng lead,
Designer.

## Key points

- Testers abandon the prototype when offline; local-first storage proposed and later decided
  ([[example--2026-01-20-acme-notes-local-first]]).
- Offline sync scoped as the v1 core, with an explicit conflict policy
  ([[example--acme-notes-offline-sync]]).
- Release cadence changes from monthly to a two-week train; hotfixes need owner sign-off
  ([[example--acme-notes-release-train]]). This superseded the earlier monthly cadence.
- Open question: lock-while-editing for shared team notebooks. Not decided; left for the next design review.

## Pages touched

| Page | Op |
|---|---|
| [[example--2026-01-20-acme-notes-local-first]] | created (decision) |
| [[example--acme-notes-offline-sync]] | created (concept) |
| [[example--acme-notes-release-train]] | created (memory), older cadence recorded as superseded in its history |

## Entities resolved

`acme notes` -> `acme-notes` (project PRD); `offline mode` -> `acme-notes-offline-sync` (via `wiki/aliases-seed.yml`).
