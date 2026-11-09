---
# kit:example <!-- kit:example -->
type: memory
project: acme-notes
temporal: living
status: active
last_verified: 2026-01-20
sources: ["wiki/decisions/example--2026-01-20-acme-notes-local-first.md", "raw/acme-notes/meetings/example--2026-01-15-kickoff.md"]
aliases: ["release train", "release cadence", "hotfix policy"]
summary: "Acme Notes ships on a two-week release train; hotfixes bypass it only with owner sign-off."
---

> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Memory: Acme Notes release train

## Memory

Acme Notes ships on a **two-week release train**. Whatever is merged and verified by the cut-off goes out;
nothing waits for a late feature.

- **Hotfixes** bypass the train only with explicit sign-off from the product owner. Why: an unreviewed
  hotfix during the prototype broke sync for every offline device at once.
- **How to apply:** when planning or writing release notes, assume the next train date, not a feature date.
  When something "must ship now", ask for owner sign-off instead of assuming a hotfix lane.

## History

- 2026-01-15: superseded the earlier fact "Acme Notes releases monthly". The new fact had a citable
  source (the kickoff, [[example--2026-01-15-kickoff-summary]]), so this was the autonomous tier: the
  `## Memory` section was rewritten, this history line was added, `last_verified` was bumped, the index
  line was rewritten (not appended to), and the change was logged as `supersede`.
- Use a separate superseded page (with `superseded_by`) instead of a history line when the old fact is
  itself worth keeping as a record, for example a decision.
