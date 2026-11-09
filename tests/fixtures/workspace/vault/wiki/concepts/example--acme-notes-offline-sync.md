---
# kit:example <!-- kit:example -->
type: concept
project: acme-notes
temporal: living
status: active
last_verified: 2026-01-20
sources: ["raw/acme-notes/meetings/example--2026-01-15-kickoff.md"]
aliases: ["offline sync", "offline mode", "sync engine", "local-first sync"]
summary: "How Acme Notes keeps notes editable without a connection and reconciles edits made on several devices."
canonical_for: [acme-notes-sync-conflict-policy]
tags: [performance, ux]
---

> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Acme Notes offline sync

## Definition

Offline sync is the mechanism that lets an Acme Notes user read and edit every note with no network
connection, then reconciles those edits with the server and with the user's other devices once a
connection returns. It follows from the local-first storage decision
([[example--2026-01-20-acme-notes-local-first]]): the device copy is the primary copy, the server is a
relay and a backup.

## Conflict policy

This page is canonical for the conflict policy (`acme-notes-sync-conflict-policy`). Other pages link here
instead of restating it.

- **Field-level merge first.** Edits to different fields of the same note (title, body blocks, tags) merge
  automatically.
- **Conflict copy for the same block.** When two devices edit the same body block while offline, both
  versions are kept: the later edit stays in place and the earlier one is saved as a conflict copy next to
  it, flagged for the user.
- **Never last writer wins silently.** Silent overwrites were the top complaint in the prototype round and
  are ruled out.

## Open points

- Whether shared team notebooks need a stricter policy (lock while editing) is still open; see the
  kickoff summary [[example--2026-01-15-kickoff-summary]].

## Related

- Decision: [[example--2026-01-20-acme-notes-local-first]]
- Source: [[example--2026-01-15-kickoff-summary]]
- Requirements: `projects/acme-notes/PRD.md` (authoritative)
