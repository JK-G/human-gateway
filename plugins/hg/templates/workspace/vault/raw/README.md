# raw/: a person's own source files

Raw sources are a person's own files. They stay on the computer of whoever brought them in and are never in
git. There is no backup and no history of them. The wiki pages made from them are what the department shares.

## Layout

```
raw/<project>/
  meetings/     meeting notes, call summaries, transcripts (.md)
  interviews/   user or stakeholder interviews (.md)
  sources/      exported documents, PDFs, spreadsheets, decks, web captures (any format)
  snapshots/    point-in-time captures of something that changes (a competitor page, a pricing table)
```

`<project>` is a slug from `projects` in `.claude/hg.json`, or `cross`. `hg-tool raw-add` creates the folders
it needs.

## Who writes here

- **Only** `hg-tool raw-add`, which `/hg:import-source` runs after recording provenance. It scans the file
  first, refuses a file with a secret, and never overwrites. It refuses when git does not ignore this folder.
- Everything else is blocked for the Bash tool and the file tools (`forbiddenWritePaths` in `.claude/hg.json`
  and `permissions.deny` in `.claude/settings.json`). The PowerShell tool has a
  coarser guard: it stops a command that names this folder, a read included.
- **Never edited after capture.** A correction is a new source (a later snapshot, a follow-up meeting),
  and the wiki records the supersession.

## How a page cites a raw file

A tracked file never names a raw file: its path and its name stay on this computer. A page cites it by its
source reference, `src:<kind>:<YYYY-MM-DD>:<8 hex digits>`: the folder's kind, the date in the file's name and
the start of the sha256 of its bytes. `hg-tool raw-ref <path>` prints it. A reader who asks where a page comes
from is told that the source is private, its kind and its date (`hg-tool raw-ref --say <ref>`).

`hg-tool raw-ref --list` lists the raw files on this computer with their references and whether a page cites
them. Its output holds paths, so it is for your own session only.

## A second computer, or a lost disk

The reference is computed from the file and never stored. Copy this folder by hand to a new computer and every
reference resolves again. A lost disk loses the raw files; the pages made from them stay. On a colleague's
computer your raw files are not there, and the pages say so.

## Minimal frontmatter (Markdown sources)

```yaml
---
source_type: meeting        # meeting | interview | source | snapshot
captured: 2026-01-15        # date the source was created or captured
origin: "call notes"        # where it came from: tool, export, URL, person's role (never a private name)
project: my-project         # optional; the folder already says it
---
```

Binary sources carry no frontmatter; their `source-summary` page in `wiki/sources/` holds the metadata.

## Binary, large and PII-bearing files

- Binary or large files get a stub-only `source-summary` page (`extraction: unextracted`) until someone
  extracts them explicitly.
- A file with contact data of people stays here, on this computer. What reaches a page is written with roles,
  never with the people's names or contact details.
