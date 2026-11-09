---
# kit:example <!-- kit:example -->
type: decision
project: acme-notes
temporal: snapshot
status: active
last_verified: 2026-01-20
decided: 2026-01-20
sources: ["raw/acme-notes/meetings/example--2026-01-15-kickoff.md"]
aliases: ["local-first decision", "local-first storage"]
summary: "Acme Notes stores notes on the device first and uses the server as relay and backup, not as the primary copy."
tags: [performance, privacy]
---

> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Decision: local-first storage for Acme Notes

**Decided:** 2026-01-20 · **Decider role:** product owner, after the kickoff (2026-01-15) · **Status:** active

## Context

Early testers work on trains and in client offices with poor connectivity. The prototype stored notes on
the server and showed a spinner without a connection; half of the testers stopped using it within a week.
Privacy-minded teams also asked whether the server could read their notes.

## Options

1. **Server-first with an offline cache.** Simplest to build; offline editing limited to recently opened
   notes; conflicts frequent and hard to explain.
2. **Local-first, server as relay and backup.** Every note lives on the device; the server syncs and backs
   up encrypted blobs. More engineering up front; strongest offline and privacy story.
3. **Fully peer-to-peer.** No server copy at all. Best privacy, but no backup and no web access.

## Decision

Option 2: local-first storage. The device copy is primary; the server relays changes between devices and
keeps an encrypted backup. Conflict handling is defined on the canonical page
[[example--acme-notes-offline-sync]].

## Consequences

- Sync becomes the core engineering investment for the first two quarters.
- The web client needs its own local store (browser storage) instead of being a thin client.
- Server-side search is off the table; search runs on the device.
- Positioning can lead with "works offline, private by design".

## Review date

2026-07-20, or earlier if sync-related support tickets exceed 10% of all tickets in a month.
