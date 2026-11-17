# The vault

The vault is the knowledge layer of this folder: plain Markdown with YAML frontmatter, written by agents through a
validated pipeline and readable by any person or tool. Three folders hold your own files as they came in:
`raw/`, `inbox/` and `daily/`.

## Open it in Obsidian (optional)

Point Obsidian at the `vault/` folder ("Open folder as vault"). Nothing depends on Obsidian, but it works
well with the conventions here:

- `[[slug]]` wiki-links are location-independent, so pages can move between folders without breaking.
- Frontmatter is plain YAML, so Dataview queries can filter by `type`, `project`, `status` or `tags`.
- The tag pane reads the `tags:` values from the controlled vocabulary in `wiki/TAGS.md`.

Obsidian keeps its settings in `vault/.obsidian/`. Agents never write there (the guard hooks block it).

## Why it is organized by type

Pages live in `wiki/<type>/`, not `wiki/<project>/`:

- Knowledge across topics has a natural home (`project: cross`) instead of being duplicated.
- One structure to validate and index, instead of one per topic.
- Per-topic views are still one filter away: every page carries `project:`, and the generated
  `index-<type>.md` files group by project.

Raw sources are the exception: they are kept per topic under `raw/<project>/`. A page cites one by its source
reference (`src:<kind>:<date>:<hash>`), never by its path or name.

## Living vs snapshot

Every page declares `temporal:`.

| | `living` | `snapshot` |
|---|---|---|
| Means | Current truth about something that changes | A frozen record of a moment (a decision, a source) |
| When stale | Past `stale_days` from `last_verified`, `hg-tool validate-frontmatter` reports it | Never stale |
| Cleanup | May be marked `superseded` when newer, sourced information arrives | Never auto-edited or auto-deleted |

Supersession never deletes. The old page gets `status: superseded` plus `superseded_by:`, so earlier text stays
readable.

## How pages get written

- **Agents** write through change plans: a source is classified, a JSON change plan is proposed, validated against
  the schema and the ingest map, and only then applied. Every operation is logged to `log.jsonl`.
- **You** may edit any page directly. Keep the frontmatter valid (see [schema.md](schema.md)).
- **Nobody** hand-edits `journal/`, `raw/` after capture, `log.jsonl` or the generated `index*.md` files.

## Start here

1. Paste a note or a link in the chat and say "zapisz" (or "keep this").
2. Ask questions with `/hg:wiki-query "..."`, or just ask; a useful answer is saved as a page when you say yes.
3. Say "co mam dziś" (or "what is on today") in the morning.
