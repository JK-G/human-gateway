# journal/: the session action journal

The journal is the cheap, complete capture layer of the memory loop. One file per day, `YYYY-MM-DD.md`.

## Contract

- **Written only by the SessionEnd hook** (`.claude/tools/journal-append.sh`, wired in
  `.claude/settings.json` as `"$CLAUDE_PROJECT_DIR"/.claude/tools/journal-append.sh`).
- **Append-only.** One line per session: time, short session id, touched paths. Never hand-edited, never
  rewritten, never linted as a wiki page.
- **Paths only, never transcripts.** The line records which files changed (from `git status`), capped to a
  short list, excluding the journal itself and code checkouts. No prompts, no answers, no personal data.
- **Non-blocking.** The hook always exits 0; a failure loses one line, never the session. (Exit codes:
  only exit 2 blocks, and only in PreToolUse; a SessionEnd hook can never block.)

Example line:

```
- 14:32 · session 3f9a1c2e · touched: vault/wiki/concepts/acme-notes--offline-sync.md tasks/playbooks/main.md
```

## Who reads it

The **wiki-heartbeat** routine reads entries newer than its watermark (the last `memory_distill`), pairs
them with `git log` for the same window to see what actually changed, and distills durable facts into
`wiki/memory/`. The journal says *where* to look; git says *what* changed.

## Gaps are a signal

A day with no file usually means a broken hook, not a quiet day. A hook command that is not
`$CLAUDE_PROJECT_DIR`-absolute, not quoted (paths with spaces), or not executable fails on every session
and leaves silent holes. `scripts/doctor.sh` checks that the newest journal file is fresh relative to the
latest commit. Do not read a gap as "no activity".
