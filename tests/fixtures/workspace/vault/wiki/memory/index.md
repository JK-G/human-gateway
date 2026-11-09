---
type: index
project: cross
---

# Shared memory index

Durable workspace knowledge every session should start with: decisions, stable facts, conventions.
Imported into every session by the root `CLAUDE.md`, so every byte here costs tokens on every turn.

- **Populated by** the wiki-heartbeat routine (journal -> `memory_distill`) and by hand whenever you learn
  something durable. Each entry points to a `type: memory` page in this folder.
- **HARD rule:** one line per page, at most `MAX_MEMORY_LINE_CHARS` (default 300) characters, format
  `- [Title](slug.md): hook`. Enforced by `.claude/tools/lint-context.sh`.
- **Updates edit the page, not the bullet.** Rewrite the hook only if the headline fact changed. Never
  append dated logs to a bullet; history goes in the page's `## History` section.
- **Coexists with host auto-memory** (personal, outside git). Each fact lives in one tier only; the other
  tier links to it. See `docs/MEMORY.md`.

## Memory pages

- [Acme Notes release train](example--acme-notes-release-train.md): EXAMPLE. Ships every two weeks; hotfixes bypass the train only with owner sign-off.
