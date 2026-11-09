# daily/: personal daily notes

One note per working day, `YYYY-MM-DD.md`, written by `/hg:today` (morning) and `/hg:dayend` (evening).

## Contract

- **Personal and local.** This folder stays out of git, so nobody's day becomes a record of their activity.
- **Not wiki pages.** No schema frontmatter, not indexed, not validated, not ingested.
- **Safe to prune.** Anything durable from a daily note should already have moved to `inbox/` or the wiki.
  Delete old notes freely.
- Weekends are skipped by default (`workdays` in `.claude/hg.json`): Friday's `/hg:dayend` prepares Monday.

## Expected skeleton

```markdown
# YYYY-MM-DD (Weekday)

## Focus
- [ ] The one or two outcomes that would make today a good day

## Calendar
| Time | Event | Notes |
|---|---|---|

## Tasks
- [ ] Carried over from yesterday
- [ ] New today

## Notes
- Anything worth remembering; move durable items to inbox/ before end of day

## End of day
- Done:
- Context updated (wiki, memory):
- Tomorrow:
```
