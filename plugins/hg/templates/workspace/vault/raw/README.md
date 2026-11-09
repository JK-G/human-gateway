# raw/: immutable source captures

Raw sources are the evidence the wiki is built from. They are captured once and never edited again.

## Layout

```
raw/<project>/
  meetings/     meeting notes, call summaries, transcripts (.md)
  interviews/   user or stakeholder interviews (.md)
  sources/      exported documents, PDFs, spreadsheets, decks, web captures (any format)
  snapshots/    point-in-time captures of something that changes (a competitor page, a pricing table)
```

`<project>` is a slug from `projects` in `.claude/hg.json`, or `cross`. `hg-tool setup --project <slug>`
creates the four folders for a new project.

## Who writes here

- **Only** `hg-tool raw-add`, which `/hg:import-source` runs after recording provenance. It scans the file
  first and never overwrites. A tracked file keeps its history; files are never copied and retyped.
- Everything else is blocked (`forbiddenWritePaths` in `.claude/hg.json` and `permissions.deny` in
  `.claude/settings.json`).
- **Never edited after capture.** A correction is a new source (a later snapshot, a follow-up meeting),
  and the wiki records the supersession. That is what keeps the wiki auditable.

## Minimal frontmatter (Markdown sources)

```yaml
---
source_type: meeting        # meeting | interview | source | snapshot
captured: 2026-01-15        # date the source was created or captured
origin: "call notes"        # where it came from: tool, export, URL, person's role (never a private name)
project: my-project         # optional; the folder already says it
---
```

Binary sources carry no frontmatter; their `source-summary` stub in `wiki/sources/` holds the metadata.

## Binary, large and PII-bearing files

- Binary or large files get a stub-only `source-summary` page (`extraction: unextracted`) until someone
  extracts them explicitly.
- Files with personal data stay stubbed for good. Only anonymized patterns may reach a wiki page body,
  and raw personal data should not be committed at all: keep it in the system of record and capture an
  anonymized version here.
