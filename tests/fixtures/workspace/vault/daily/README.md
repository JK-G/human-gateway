# daily/: personal daily notes

One note per working day, `YYYY-MM-DD.md`, written by `/today` (morning) and `/dayend` (evening).

## Contract

- **Not wiki pages.** No schema frontmatter, not indexed, not linted, not ingested.
- **Never auto-edited by routines.** Only `/today`, `/dayend` and you touch these files.
- **Safe to prune.** Anything durable from a daily note should already have moved to the wiki (via
  `inbox/` or `/decision-log`) or to the playbook (via `/capture-task`). Delete old notes freely.
- Weekends are skipped by default (kit.conf `WORKDAYS="1-5"`): Friday's `/dayend` prepares Monday.

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
- Context updated (wiki, memory, playbook):
- Tomorrow:
```
