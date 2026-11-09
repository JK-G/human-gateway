# The vault

The vault is the knowledge layer of the workspace: plain Markdown with YAML frontmatter, tracked in git,
written by agents through a validated pipeline and readable by any human or tool.

## Open it in Obsidian (optional)

Point Obsidian at the `vault/` folder ("Open folder as vault"). Nothing depends on Obsidian, but it works
well with the conventions here:

- `[[slug]]` wiki-links are location-independent, so pages can move between folders without breaking.
- Frontmatter is plain YAML, so Dataview queries can filter by `type`, `project`, `status` or `tags`.
- The tag pane reads the `tags:` values from the controlled vocabulary in `wiki/TAGS.md`.

Obsidian keeps its settings in `vault/.obsidian/`, which stays out of git because they differ per device.
Agents never write there (the guard hooks block it).

## Why it is organized by type

Pages live in `wiki/<type>/`, not `wiki/<project>/`:

- Cross-project knowledge has a natural home (`project: cross`) instead of being duplicated.
- One structure to validate and index, instead of one per project.
- Per-project views are still one filter away: every page carries `project:`, and the generated
  `index-<type>.md` files group by project.

Raw sources are the exception: they are partitioned per project under `raw/<project>/`, because sources are
naturally project-scoped and heavy.

## Living vs snapshot

Every page declares `temporal:`.

| | `living` | `snapshot` |
|---|---|---|
| Means | Current truth about something that changes | A frozen record of a moment (a decision, a source) |
| When stale | Past `stale_days` from `last_verified`, `hg-tool validate-frontmatter` reports it | Never stale |
| Cleanup | May be marked `superseded` when newer, sourced information arrives | Never auto-edited or auto-deleted |

Supersession never deletes. The old page gets `status: superseded` plus `superseded_by:`, so history stays
readable and every change is reversible in git.

## How pages get written

- **Agents** write through change plans: `/hg:ingest` classifies a source, proposes a JSON change plan,
  validates it against the schema and the ingest map, and only then applies it. Every operation is logged
  to `log.jsonl`.
- **Humans** may edit any page directly. Keep the frontmatter valid (see [schema.md](schema.md)) and run
  `hg-tool validate-frontmatter` afterwards.
- **Nobody** hand-edits `journal/`, `raw/` after capture, `log.jsonl` or the generated `index*.md` files.

## Start here

1. Drop a file into `inbox/` (copy `inbox/_template.md`) or bring a source in with `/hg:import-source`.
2. Run `/hg:ingest <path>`, or `/hg:ingest --inbox` for everything in `inbox/`.
3. Ask questions with `/hg:wiki-query "..."`; useful answers are filed back as pages.
4. Create a new project space with `hg-tool setup --project <slug>`.
