<!-- kit:example -->
> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Acme Notes: product requirements

> **Authoritative.** Routines never edit this file; the wiki links TO it. Created 2026-01-10.

## Problem

Small teams take notes in meetings, on trains and at client sites. Cloud-first note apps fail exactly
there: no connection means no notes, and concurrent edits overwrite each other silently. Privacy-minded
teams also distrust servers that can read their content.

## Users and segments

| Segment | Job to be done | Signal |
|---|---|---|
| Consulting teams | capture and share client notes on site | 9 of 24 prototype testers |
| Field teams | write notes with poor connectivity | most offline complaints |
| Privacy-sensitive teams | keep notes unreadable to the vendor | 2 pilot teams asked directly |

## Goals and non-goals

**Goals**
- Every note readable and editable offline, on every device.
- No silent data loss on concurrent edits.
- Server never holds readable note content.

**Non-goals**
- Real-time co-editing of the same paragraph (v1).
- Server-side full-text search.

## Solution overview

Local-first storage ([[example--2026-01-20-acme-notes-local-first]]): the device copy is primary, an
encrypted relay syncs devices. Sync and conflict handling: [[example--acme-notes-offline-sync]].

## Requirements

| ID | Requirement (as an outcome) | Priority | Status |
|---|---|---|---|
| R1 | A user opens and edits any note with no connection | must | in progress |
| R2 | Concurrent edits never lose text; the user sees what conflicted | must | in progress |
| R3 | The server stores only encrypted blobs | must | planned |
| R4 | A new team member is set up in under 5 minutes | should | proposed |

## Metrics

| Metric | Definition | Baseline | Target |
|---|---|---|---|
| Week-1 retention | testers active in week 2 / testers onboarded | 54% | 80% |
| Sync tickets share | sync tickets / all support tickets per month | n/a | under 10% |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sync engine takes longer than a quarter | medium | high | ship read-only offline first |
| Flagged copies confuse users | medium | medium | design review with 5 testers |

## Open questions

- Shared team notebooks: lock-while-editing or the standard conflict policy? (Designer, next design review)

## Changelog

| Date | Change | Why |
|---|---|---|
| 2026-01-10 | Created | project start |
| 2026-01-20 | Local-first storage adopted | kickoff findings, see decision page |
