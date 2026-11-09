---
name: ingest
description: Absorb a raw source (or the inbox) into the wiki through a validated change plan.
argument-hint: "<path|--inbox> [--dry-run|--apply <hash>|--force|--list-plans]"
---

# /hg:ingest

Turn a raw source into wiki changes: classify, plan, validate, apply, log. All writes are done by the
**wiki-librarian** subagent (`hg:wiki-librarian`); this command only parses the flags
and dispatches it.

## Usage

| Invocation | Effect |
|---|---|
| `/hg:ingest vault/raw/<p>/<kind>/<file>` | Dry run and apply in one go. |
| `/hg:ingest <path> --dry-run` | Build and validate the plan, print it, cache it for 24 hours. No page writes. |
| `/hg:ingest --apply <hash>` | Apply a cached plan after re-checking every page hash. |
| `/hg:ingest --apply <hash> --force` | Same, but on a hash mismatch show the diff and ask before applying (interactive only). |
| `/hg:ingest --list-plans` | List cached plans in `.gateway/plans/` with source, age and hours left. |
| `/hg:ingest --inbox` | Batch mode over `vault/inbox/` (below). |

Use repo-relative paths only (`vault/raw/...`), never absolute ones.

## Steps

1. Parse the arguments. Reject an unknown flag, or `--apply` without a hash, with the usage table.
2. For `--list-plans`: list `.gateway/plans/*.json` (skip `*.errors.json`) with their `source`,
   age and remaining TTL; delete plans older than 24 hours and say so. Stop.
3. Dispatch the `hg:wiki-librarian` subagent. Start its prompt with:
   "First action: read ${CLAUDE_PLUGIN_ROOT}/rules/boundaries.md and vault/schema.md." Then pass the operation
   (`ingest`), the path or plan hash, and the flags verbatim.
4. Show the librarian's result to the user: the summary table, the plan hash, and the log line it
   appended (or the reason it stopped).

## Inbox mode (`--inbox`)

1. List `vault/inbox/` (skip `_template.md` and dotfiles). Empty -> say so and stop.
2. For each file the librarian proposes a routing row: target project (hg.json `projects` or
   `cross`), raw kind (meetings, interviews, snapshots, sources), dated slug, confidence, one-line
   reason. Present all rows as one table and ask for one approval.
3. On approval, run `/hg:import-source <file> --project <p> --kind <kind>` per approved row (it wraps the
   frontmatter and moves the file into `vault/raw/`), then ingest each moved file.
4. Rows below 0.6 confidence stay in the inbox and are listed as "needs a human".

## Binary, large and PII-bearing sources

PDF, office files, images, anything over 1 MB, and any source carrying personal data become a
`source-summary` stub only (`extraction: unextracted`), never extracted pages. Extraction of a binary
source is a later, explicit step; a PII stub stays unextracted for good.

## Plan cache

- Plans live in `.gateway/plans/<hash>.json` (gitignored) with a 24-hour TTL.
- A plan is bound to page hashes: if a page changed since the dry run, that edit is skipped and logged
  as a stale plan rather than overwriting someone's change.

## Output

- The ops summary: one row per edit or new page (op, page, section, confidence).
- The log line appended to `vault/log.jsonl` (op `ingest`, or `rejected_ingest_scope` / `conflict`).

## Notes

- The librarian takes the `wiki-<project>` lock with `--no-steal`. If it is held, it stops and names
  the holder; release it yourself only after confirming no other session is writing.
- Hooks: `vault/raw/` is in `FORBIDDEN_WRITE_PATHS`. Guard hooks block a forbidden write by exiting 2
  (in PreToolUse only exit 2 blocks; any other nonzero exit just warns). The librarian never edits raw
  files, so a block there means a bug in the plan, not a reason to bypass the guard.
