---
name: dayend
description: End-of-day wrap-up for a department workspace. Session summary, proposed updates to shared knowledge, next workday's note.
argument-hint: "[optional notes about today]"
---

# /hg:dayend

Close the working day: summarize what happened, keep shared knowledge current, and prepare the next
workday. Shared files change only after the person confirms. Write to the person in `language.content`
from `.claude/hg.json`.

## Steps

1. **Date.** Run `hg-tool today-data` and use `date` and `next_workday`. Never trust your own idea of today.
2. **Session summary.** From this conversation and the person's notes, list:
   - **Done:** main actions and results, with file paths.
   - **Decisions:** what was decided and why, one line each.
   - **Open threads:** what is unfinished, and who owns it.
3. **Propose updates (do not apply yet).** Check each living file for concrete new information:

   | File | Update when |
   |---|---|
   | `vault/projects/<slug>/CLAUDE.md` | status, constraints or conventions of the project changed |
   | `vault/wiki/memory/<page>.md` + `vault/wiki/memory/index.md` | a durable fact every session should know |

   Only concrete new information. Keep each file's structure and change the minimum. A memory index entry
   is one line of at most `limits.maxMemoryLineChars` characters. Show each edit as before and after and
   ask for confirmation. Apply only what the person approves. Never edit `snapshot` pages, PRDs or
   `vault/journal/`.
4. **Update today's note.** In `vault/daily/YYYY-MM-DD.md`: tick finished items and add Done, Context
   updated and Tomorrow under `## End of day`.
5. **Prepare the next workday's note** at `vault/daily/<next_workday>.md`: carry over the unchecked items
   and add the new tasks from this session.
6. **Uncommitted changes.** Run `git status --short`. If anything is modified or untracked, list the
   paths and remind the person to commit. Never commit from here.

## Rules

- No autonomous writes to shared files: propose, confirm, then apply.
- Personal data of customers or end users never goes into a note or memory page.
