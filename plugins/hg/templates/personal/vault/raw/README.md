# raw/: your own source files

These are your own files: notes you pasted, links you kept, files you gave. They stay in this folder as they came
in. hg makes no copy of them and keeps no earlier versions. The pages made from them are the knowledge you ask.

## Layout

```
raw/<project>/
  meetings/     meeting notes, call summaries, transcripts (.md)
  interviews/   interviews (.md)
  sources/      notes, documents, PDFs, spreadsheets, decks, web captures (any format)
  snapshots/    point-in-time captures of something that changes (a page, a price table)
```

`<project>` is a slug from `projects` in `.claude/hg.json`, or `cross`.

## Who writes here

- **Only** hg's tools. They scan a file first, keep a secret out, and never overwrite.
- Everything else is blocked for the Bash tool and the file tools. The PowerShell tool is not covered.
- **Never edited after capture.** A correction is a new source (a later note, a follow-up meeting), and the wiki
  records the supersession.

## How a page cites a raw file

A page never names a raw file. It cites it by its source reference, `src:<kind>:<YYYY-MM-DD>:<8 hex digits>`:
the folder's kind, the date in the file's name and the start of the sha256 of its bytes. `hg-tool raw-ref <path>`
prints it, and `hg-tool raw-ref --say <ref>` says where the file is.

## A second computer, or a lost disk

The reference is computed from the file and never stored. Copy this folder by hand to a new computer and every
reference resolves again. A lost disk loses the raw files; the pages made from them stay only if they are on
another disk too.

## Binary and large files

Binary or large files get a short `source-summary` page (`extraction: unextracted`) until someone extracts them
explicitly.
