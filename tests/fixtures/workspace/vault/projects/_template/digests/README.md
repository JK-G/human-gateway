> AUTO-SYNC: files under digests/<agent>/ are overwritten by agents. Do not hand-edit.

# __NAME__ digests: the read surface for agent output

Autonomous agents in `agents/` (each its own gitignored repo) push **PII-free, aggregated** digests here as
the last step of their run. This folder is the only part of an agent's output that the main workspace reads.

## Rules

- **Agents overwrite their own files only**, under `digests/<agent>/`. One agent never writes another's folder.
- **Do not hand-edit.** The next sync overwrites any edit. Fix the agent instead.
- **The source of truth lives in the agent's own repo** (state, watermarks, raw inputs, trend history).
  A digest is a projection of it, safe to delete and regenerate.
- **No PII, no raw records.** Counts, patterns and anonymized examples only. The agent runs its PII lint
  before pushing.
- **Every file starts with the auto-sync banner line** (`> AUTO-SYNC: ...`) naming the agent and the run date.
- Durable findings graduate through the normal loop: `/ingest` into the wiki, decisions via
  `/decision-log`, scope changes into `PRD.md` by a human.

## Typed queues

Each file is a queue with exactly one consumer, so nothing is read "just in case".

| File | Written by | Consumer | Content |
|---|---|---|---|
| `<agent>/latest-digest.md` | the agent | everyone | Dated run header, TL;DR, source-failure flags |
| `<agent>/<topic>.md` | the agent | named role or agent | One typed stream (e.g. feature requests, drift, bugs) |
| `<agent>/proposals.md` | the agent | human (in a session) | Numbered HITL proposals, see below |

Fill in the real table when an agent starts pushing here.

## HITL proposals convention

Agents never change trackers, boards, PRDs or planning docs themselves. Fixes wait as numbered proposals:

```markdown
### P-7: Close duplicate roadmap item
- **Rationale:** two items describe the same outcome; the older one has no linked tasks.
- **Evidence:** item ids, dates, links (traceable identifiers, never personal data).
- **Exact operation:** set item <id> status to "duplicate", link it to <id>.
- **Status:** open
```

- IDs are stable and never reused (`P-1`, `P-2`, ...).
- The human approves by id in an interactive session ("apply P-7"); the main agent applies exactly the
  stated operation, marks the proposal `applied`, and logs it.
- Proposals that are rejected are marked `rejected` with a one-line reason, not deleted, so the agent
  does not propose them again.
