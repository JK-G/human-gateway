# journal/: the session action journal

One file per day, `YYYY-MM-DD.md`, with one line per session.

## Contract

- **Written only by the plugin's SessionEnd hook.** It fires under Claude Code only.
- **Append-only.** One line per session: time, short session id, how many pages changed. Never hand-edited,
  never rewritten, never validated as a wiki page.
- **Counts only, never transcripts.** No prompts, no answers, no personal data, no file names.
- **Non-blocking.** The hook always exits 0; a failure loses one line, never the session.

Example line:

```
- 14:32 session 3f9a1c2e: 3 paths (+3 new)
```

## Who reads it

`/hg:doctor` reads when the last line was written. The pages say what changed.

## Gaps are a signal

A day with no file usually means a broken hook or a machine without the plugin, not a quiet day.
`/hg:doctor` warns when no session has been recorded lately.
