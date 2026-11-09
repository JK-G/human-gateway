# journal/: the session action journal

One file per day, `YYYY-MM-DD.md`, showing which files each session touched.

## Contract

- **Written only by the plugin's SessionEnd hook.** It fires under Claude Code only.
- **Append-only.** One line per session: time, short session id, touched paths. Never hand-edited, never
  rewritten, never validated as a wiki page.
- **Paths only, never transcripts.** No prompts, no answers, no personal data.
- **Non-blocking.** The hook always exits 0; a failure loses one line, never the session.

Example line:

```
- 14:32 · session 3f9a1c2e · touched: vault/wiki/concepts/my-project--offline-sync.md
```

## Who reads it

`/hg:today` and `/hg:dayend` show recent sessions from it. The journal says *where* to look; git says
*what* changed.

## Gaps are a signal

A day with no file usually means a broken hook or a machine without the plugin, not a quiet day.
`/hg:doctor` warns when no session has been recorded lately.
