---
name: dayend
description: End-of-day wrap-up for a department workspace. Session summary, proposed updates to shared knowledge, next workday's note.
argument-hint: "[optional notes about today]"
---

# /hg:dayend

Close the working day: summarize what happened, keep shared knowledge current, and prepare the next
workday. Shared files change only after the person confirms. Write to the person in `language.content`
from `.claude/hg.json`.

## A personal folder

`today-data` has a `mode` key. When it is `personal`, the folder is one person's own and nothing in it is sent:
run steps 1 to 5, and skip step 6, because `unpublished` is absent. Say nothing about shared files, about other
people seeing anything, or about sending. Name a page by its title, as a link to its file.

When `mode` is `none`, this folder is not set up: copy the sentence under `say` in the person's language
and stop.

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
   When something from the session was deliberately not recorded, write a left-out report with `op: "dayend"`
   to `.gateway/leftout/draft.json` and run `hg-tool leftout .gateway/leftout/draft.json`, as
   `${CLAUDE_PLUGIN_ROOT}/rules/cleaning.md` describes. With nothing left out, write none.
4. **Update today's note.** In `vault/daily/YYYY-MM-DD.md`: tick finished items and add Done, Context
   updated and Tomorrow under `## End of day`.
5. **Prepare the next workday's note** at `vault/daily/<next_workday>.md`: carry over the unchecked items
   and add the new tasks from this session.
6. **Changes not shared yet.** Run `hg-tool today-data` and copy `unpublished.line` word for word when it is not
   empty. Say that colleagues and the department's channel see an approval, a check of an outside source or a
   journal line only after it is published, and start `hg:publish` with the Skill tool. Its question is the one
   question; do not ask a second one. When `unpublished.line` is empty, or `unpublished` is absent, skip this step.

## Rules

- No autonomous writes to shared files: propose, confirm, then apply.
- Before any commit in a department repository, run hg-tool publish check, show the person the preview it
  writes, and commit only through the commit step of /hg:publish, after the person's own yes in this session.
- Personal data of customers or end users never goes into a note or memory page.
