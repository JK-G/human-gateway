---
name: wiki-query
description: Ask the wiki a question, synthesize an answer, and offer to file novel answers back so knowledge compounds.
argument-hint: "\"<question>\" [--no-file]"
---

# /hg:wiki-query

Ask, synthesize, file back. An answer that combines several pages into something new is worth more than
a chat reply: filing it back means the next question starts from it instead of from scratch. That loop
is the point of the wiki.

## Usage

| Invocation | Effect |
|---|---|
| `/hg:wiki-query "<question>"` | Answer, then file back if the routing table says so and the person agrees. |
| `/hg:wiki-query "<question>" --no-file` | Chat-only answer. No wiki page is written. |

## Steps

1. **Search.** Detect the project (CWD inside `vault/projects/<slug>/`, else a slug named in the
   question, else all projects). Normalize the question's key terms (casefold, strip diacritics) and
   match them against page `aliases`, file stems, `summary` lines in `vault/index-*.md`, and
   `aliases-seed.yml` `entities:`. Read the best matches (at most about 8 pages), plus the canonical
   page of any fact they link.
2. **Synthesize.** Answer from those pages only, in the language of the question. Cite every claim
   with `[[page]]`. Say plainly what the wiki does not know; do not fill gaps from general knowledge
   without labelling it as such. The wiki only: no external systems.
3. **Route** (skip with `--no-file`):

| Answer shape | Where it goes | How |
|---|---|---|
| Adds new information about one existing page's subject | that page, `## Q&A` | `section_merge` |
| Novel synthesis across pages, no existing page owns it | new `concept` or `research` page | `new_pages` |
| Pure retrieval, nothing new | chat only | none |
| Ambiguous (two candidate pages, or unclear if new) | ask the user which | none until answered |

4. **Ask, then file back** (when routed to a write): wiki pages are shared and go out with the next push,
   so ask first with AskUserQuestion, naming the page that would change or be created. For the ambiguous
   row this is the same question. Without a yes, nothing is filed and the answer stays in chat.
   On yes, dispatch the `hg:wiki-librarian` subagent with the answer, the pages read, and the routing
   decision. It takes the lock, builds a plan with `op: file_back`, validates it, applies it, and
   regenerates the index.
5. **Log.** One `query` line for every answered question; one `file_back` line listing the written
   pages in `outputs` when something was filed. Both through `hg-tool log` (the
   librarian writes them when it is involved).

## Provenance (enforced)

- A new page filed from an answer carries `derived_from: [wiki/..., ...]` (vault-relative) listing every
  page the answer used. The frontmatter validator reads `file_back` lines in the log and reports
  `uncited_query_output` (ERROR) for a filed page without it.
- A `## Q&A` entry has this shape; the validator rejects an entry without the citation line:

```markdown
## Q&A

### Q: Does offline sync cover shared notebooks? (2026-01-22)

Not yet. Shared notebooks are an open point; the policy covers single-user devices only.

Derived from: [[example--acme-notes-offline-sync]], [[example--2026-01-15-kickoff-summary]]
```

- Entries accumulate oldest first. More than about 20 entries on one page is a sign the Q&A deserves its
  own page: suggest moving it to its own page.

## Never

- File back a pure retrieval answer (it duplicates the source page and creates drift).
- Dispatch the librarian before the person has agreed.
- Write without the librarian's lock and a validated plan.
- Touch `vault/raw/`, a `PRD.md`, `planning/` or `journal/` while answering.
- Translate page bodies: a new page keeps the language of the answer; add other-language `aliases`.
