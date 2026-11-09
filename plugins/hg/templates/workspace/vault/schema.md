---
type: schema
title: Wiki schema (constitution)
version: 1.0
---

# Wiki schema: the single source of truth

Every agent, validator and index generator reads this file. One wiki under `vault/wiki/`, organized by
**type**; the owning project is a frontmatter value, never a folder.

- Machine contract: the `kit:type-registry` block below, parsed only by the plugin's registry reader
  (`hg-tool registry`). Never hand-mirror it into another file.
- Paths in frontmatter (`sources`, `source_raw`, `derived_from`, `canonical_page`) are relative to the
  vault root, for example `raw/my-project/meetings/2026-01-15-kickoff.md`.

## Universal frontmatter

| Key | Values | Meaning |
|---|---|---|
| `type` | a registry type | Page type. Decides the folder and the required keys and sections. |
| `project` | a slug from `projects` in `.claude/hg.json`, or `cross` | Owning project. `cross` = spans projects. |
| `temporal` | `living` \| `snapshot` | `living` = current truth, refreshed when stale. `snapshot` = frozen record, never auto-edited or auto-deleted. |
| `status` | `active` \| `superseded` \| `retracted` | Lifecycle. Cleanup by an agent only ever sets `superseded`. |
| `last_verified` | `YYYY-MM-DD` | When a human or agent last confirmed the page is current. Drives staleness. |
| `sources` | `[path, ...]` | Provenance into `raw/`, `journal/` or another page. Empty only for hand-written pages. |
| `aliases` | `[string, ...]` | Other names for the subject (synonyms, abbreviations, other-language forms). Entity resolution. |
| `summary` | one sentence | Required by every default type. Used by the index generator and `/hg:wiki-query`. |
| `canonical_for` | `[fact-slug, ...]` (optional) | Fact-slugs this page owns. Other pages link or transclude, never restate. |
| `tags` | `[kebab-case, ...]` (optional) | Discovery tags from `wiki/TAGS.md`. Soft-enforced (validator INFO). |
| `derived_from` | `[path, ...]` (optional) | Set on pages filed back from a `/hg:wiki-query` answer: the pages the answer was built from. |
| `superseded_by` | path (optional) | Set together with `status: superseded`: the page or source that replaced this one. |

Rules: do not invent keys. A key not in this table or in the type's `required` list is a validator WARN.
The slug is the filename stem; there is no `slug:` key.

## Type registry

```yaml
# kit:type-registry
# Parsed by the plugin's registry reader. Edit here only; validators and the index generator import it.
# dir is relative to the vault root. stale_days: 0 = never stale.
universal_required: [type, project, temporal, status, last_verified, sources, aliases]
types:
  concept:
    dir: wiki/concepts
    required: [summary]
    sections: [Definition, Related]
    stale_days: 180
  entity:
    dir: wiki/entities
    required: [summary, kind]
    sections: [Overview, Related]
    stale_days: 180
  decision:
    dir: wiki/decisions
    required: [summary, decided]
    sections: [Context, Options, Decision, Consequences, Review date]
    stale_days: 365
  source-summary:
    dir: wiki/sources
    required: [summary, source_raw, extraction]
    sections: []
    stale_days: 0
  research:
    dir: wiki/research
    required: [summary]
    sections: [Finding, Evidence]
    stale_days: 90
  memory:
    dir: wiki/memory
    required: [summary]
    sections: [Memory]
    stale_days: 180
  # Optional add-ons. Uncomment to enable, then add a folder and an ingest-map row.
  # hypothesis:
  #   dir: wiki/hypotheses
  #   required: [summary, test_status]
  #   sections: [Hypothesis, Test, Status]
  #   stale_days: 90
  # open-question:
  #   dir: wiki/questions
  #   required: [summary]
  #   sections: [Question, Why it matters, Leads]
  #   stale_days: 90
  # glossary-term:
  #   dir: wiki/glossary
  #   required: [summary]
  #   sections: [Definition]
  #   stale_days: 365
```

### Type notes

| Type | Use it for | Default `temporal` | Type-specific keys |
|---|---|---|---|
| `concept` | An idea, feature, mechanism, policy or pattern. The workhorse type. | living | none |
| `entity` | A named thing: competitor, organization, tool, team role, segment. People appear by role only. | living | `kind`: `organization`, `competitor`, `tool`, `role`, `segment`, `other` |
| `decision` | One decision with context, options, rationale and a review date. | **snapshot** | `decided`: `YYYY-MM-DD` |
| `source-summary` | A lightweight stub per raw source (binary, large or PII-bearing). | snapshot | `source_raw` (path), `extraction`: `unextracted`, `partial`, `extracted`, `obsolete`; optional `source_hash`, `extracted_to: []` |
| `research` | A discrete finding with evidence (analysis, benchmark, survey result). | living | none |
| `memory` | A durable workspace fact, convention or decision every session should know. | living | none |

- A decision is a snapshot by default: when a later decision replaces it, set `status: superseded` and
  `superseded_by`, and never rewrite its body.
- `extraction` is deliberately separate from `status` (lifecycle).
- `source-summary` has no required sections: it is a stub by design. `stale_days: 0` because a summary
  of a frozen source cannot go stale.
- `memory` pages are indexed one line each in `wiki/memory/index.md`.

## Slug rules

- The filename stem is the slug. English kebab-case: `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$`, at most 80 chars.
- Project-scoped pages: `<project>--<slug>` (for example `my-project--offline-sync`).
- Cross-project pages: `cross--<slug>`.
- Decisions and dated sources lead with the date: `<project>--YYYY-MM-DD-<slug>`.
- Collisions are allowed across types, never within one type folder. Link by slug: `[[my-project--offline-sync]]`.

## Ingest map

`raw/` is partitioned per project: `raw/<project>/{meetings,interviews,sources,snapshots}/`.
A change plan that proposes a page type outside its source's row is rejected and logged as
`rejected_ingest_scope`.

| Raw source type | Path glob | May create or update |
|---|---|---|
| `meeting` | `raw/<p>/meetings/*.md` | `concept`, `entity`, `decision`, `research`, `source-summary` |
| `interview` | `raw/<p>/interviews/*.md` | `concept`, `entity`, `research`, `source-summary` |
| `snapshot` | `raw/<p>/snapshots/*.md` | `entity`, `research`, `concept` |
| `source` | `raw/<p>/sources/*` | `source-summary` first; then `concept`, `entity`, `research`, `decision` by extraction |
| `journal` | `journal/YYYY-MM-DD.md` | `memory` only |
| `inbox` | `inbox/*.md` | nothing directly: classify as one of the rows above, `/hg:import-source` into `raw/<p>/...`, then ingest |
| `query` | a `/hg:wiki-query` answer | `concept`, `research` (requires `derived_from`) |

Not raw sources, and never ingested: `projects/<p>/PRD.md`, `planning/`, `daily/`.
The wiki links TO a PRD; it never restates or supersedes it.

### Binary, large and PII-bearing sources

- Binary (pdf, docx, xlsx, images) or over ~1 MB: create a `source-summary` stub only, with
  `extraction: unextracted`. Extraction into typed pages is a later, explicit step.
- PII-bearing (contracts, customer exports, legal text with personal data): the stub stays
  `unextracted` for good. Only anonymized patterns may reach a wiki body; raw PII never enters git.

## One fact, one page

Structured facts (tables, prices, KPIs, limits) live on one canonical page and are referenced with
`![[page#section]]` or `[[page]]`. Fact-slug format: same regex as page slugs, at most 60 chars.

## Cleanup triage

The guiding rule: **supersession with evidence may be done by an agent; suspicion without evidence goes to
a human.** This keeps the human queue small.

1. **With evidence.** New information supersedes a `living` fact **and has a citable source**: set the old
   page `status: superseded` with `superseded_by`, fix links, merge exact duplicates, log `supersede` or
   `dedup`. Git-reversible.
2. **Human queue.** Only an unresolvable contradiction, or a `living` page past `stale_days` with no
   superseding source. Log `conflict` with `status: queued`. Ask one low-effort question
   ("still true?"), not an essay.
3. **Never auto-touch.** `snapshot` pages, PII stubs, `PRD.md`, `planning/`, `daily/`, `journal/`, `raw/`.

## Languages

Set in `.claude/hg.json` under `language`:

| Setting | Default | Effect |
|---|---|---|
| `infra` | `en` | Language of schema, commands and agent prompts. Keep `en`. |
| `content` | set by `/hg:setup` | Language of page bodies. A source in another language keeps its language (no auto-translation). |

Always English regardless of settings: frontmatter keys, controlled values, slugs, tags, log ops.
With a second content language, `aliases` carry both languages plus diacritic-stripped forms.

## Log schema

`vault/log.jsonl` (`paths.log` in `.claude/hg.json`) is the append-only machine log of wiki operations.
Write it only through `hg-tool log`, never by hand. One JSON object per line:

```json
{"ts":"2026-01-20T09:12:00Z","op":"ingest","agent":"wiki-librarian","project":"my-project","inputs":["raw/my-project/meetings/2026-01-15-kickoff.md"],"outputs":["wiki/decisions/my-project--2026-01-20-local-first.md"],"status":"applied","note":""}
```

`status`: `applied`, `queued`, `skipped`, `failed`, `blocked`. `project` defaults to `cross`.

### Op vocabulary (fixed)

| Op | Meaning |
|---|---|
| `ingest` | Source turned into page changes. |
| `rejected_ingest_scope` | Change plan proposed a page type outside the ingest map. |
| `lint` | Vocabulary changes, e.g. `note: "tag_added: offline"`. |
| `query` | `/hg:wiki-query` answered a question. |
| `file_back` | A query answer was filed back as a page. |
| `dedup` | Duplicate merged or a monolith split. |
| `supersede` | A living fact was marked superseded. |
| `archive` | A page was archived, or the log was rotated. |
| `conflict` | Unresolvable contradiction or ambiguous entity, queued for a human. |
| `init` | Workspace or project scaffolded. |
| `gate_new` | A gate was created. No names of people. |
| `gate_approve` | A gate was approved. `note` holds `via` and the inputs that changed since the last approval. No names of people. |
| `gate_new` | A gate was created. No names of people. |
| `gate_approve` | A gate was approved. `note` holds `via` and the inputs that changed since the last approval. No names of people. |

The vocabulary belongs to the plugin; `hg-tool log` rejects an op it does not know.

### Rotation

`hg-tool log` rotates the file when it exceeds `limits.logRotateBytes` (default 512000): the current file
moves to `vault/log/YYYY.jsonl`, or `YYYY-N.jsonl` if that name exists, and a fresh `log.jsonl` starts.
Readers that need history glob `vault/log/*.jsonl` plus `vault/log.jsonl`.

The **journal** (`vault/journal/YYYY-MM-DD.md`) is a separate, human-readable capture of touched paths per
session.
