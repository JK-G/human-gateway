---
name: import-source
description: Wrap an external export (notes-app export, transcript, PDF, URL) with raw frontmatter and bring it into vault/raw/ for /hg:ingest.
argument-hint: "<file|url> --project <slug> --kind meetings|interviews|sources|snapshots"
---

# /hg:import-source

The one sanctioned way for an outside file to enter `vault/raw/`. It records provenance once, hands the
file to `hg-tool raw-add` for its permanent dated home, and stops. It never ingests: `/hg:ingest` stays a separate step so a
dry run remains the default habit.

## Arguments

| Argument | Rule |
|---|---|
| `<file>` | Repo-relative path under `vault/inbox/` or `intake/`. `hg-tool raw-add` refuses any other place. |
| `<url>` | `http(s)` only. Downloaded with `curl -fsSL` into `vault/inbox/` first, no auth headers, no cookies. |
| `--project` | A slug from hg.json `projects` (`hg-tool registry projects --with-cross`) or `cross`. Missing: apply the project detection idiom (CWD in `vault/projects/<slug>/`, a slug named by the user, else list `vault/projects/` and ask). |
| `--kind` | `meetings`, `interviews`, `sources` or `snapshots` (`vault/raw/README.md`). Missing: propose one from the content and ask. |

## Steps

1. **Check inputs.** Unknown project or kind -> show the valid values and stop. The file must exist and
   sit inside the repo; never read from or write to paths outside it.
2. **Date and slug.** `captured` = the date the source was created (the meeting day, not the export
   day). Read it from the content or file name, else ask. Slug = short English kebab-case. Step 5 builds the
   destination from them: `vault/raw/<project>/<kind>/<YYYY-MM-DD>-<slug>.<ext>`. Raw files are never
   overwritten, so for a name that is taken pick a new slug or, for a changed source, a new capture
   date (a later snapshot).
3. **Scan.** Run `hg-tool scan <file>`. Exit 2 means the scan did not run: fix that first. Exit 0 means it
   found nothing it can recognise. Then still read text files for full names of people outside the team,
   which the scan cannot judge, and look through binary files such as a PDF, whose contents it does not
   read. Exit 1, or a name found by reading -> stop. Show the findings as printed: the values are masked,
   and you never write out the original. Offer two paths: anonymize the inbox copy now (replace people with
   roles, drop contact details, take out the secret) and scan again until it is clean, or keep the file out
   of git entirely. For a `filetype` finding the second path is the only one: `link only` means the repo
   gets a link to the file, `secret file` means it gets nothing.
4. **Wrap** (Markdown and plain-text sources only, edited in place while still in the inbox):
   - Normalize export noise only: tool-specific bullet nesting, inline metadata lines, broken line
     wraps. Never rewrite content.
   - Prepend the raw frontmatter; merge with existing frontmatter if present (existing keys win, except
     the four below). Step 5 gives a `.txt` file the suffix `.md`.

```yaml
---
source_type: meeting          # meeting | interview | source | snapshot (singular of --kind)
captured: 2026-01-15
origin: "meeting-notes app export"   # tool, export or URL; people by role, never by private name
project: acme-notes
---
```

   - Binary files (PDF, office documents, images) stay byte-identical with no frontmatter. Their
     metadata goes into the `source-summary` stub the ingest creates.
5. **Bring it in.** Run `hg-tool raw-add <file> --project <p> --kind <k> --date <captured> --slug <slug>`.
   It is the only writer of `vault/raw/`, creates the folders it needs and prints the destination. It scans
   the file again, because step 4 changed it. Any refusal (exit 1, or exit 2 for a wrong command line) stops
   the flow: the file has not moved. Show what it printed, masked values included, then go back to step 3
   for a finding or step 2 for a name that is taken. Do not get the file there any other way.
6. **Report** the final path and the next step:
   `/hg:ingest <destination> --dry-run`.

## Writing a source-specific adapter

Most teams have one or two recurring sources (a meeting-notes app, a transcription tool, a survey
export). Give each a thin adapter instead of baking the vendor into this command:

1. Create `.claude/skills/import-<source>/SKILL.md` with frontmatter `description` and `argument-hint`.
2. In its body, describe only what is specific to that source: how the user exports (menu path, format),
   which noise to strip (for a meeting-notes export: nested bullet syntax, node ids, inline tags), how to
   read the meeting date and the participants' roles, and which `--kind` it maps to.
3. End with: "Then follow `/hg:import-source` from step 2 with `--project <p> --kind <k>`."
4. Keep it vendor-neutral in the vault: `origin` may name the tool, but no account ids, workspace ids,
   internal URLs or API tokens in raw frontmatter or in the adapter. Credentials live in the environment,
   named by an env var, never in a tracked file.
5. No API access is needed. A file the user exported by hand is the simplest, most auditable adapter.

## Never

- Edit a file that is already in `vault/raw/`, or reuse a destination name.
- Run `/hg:ingest` automatically.
- Commit. The user or the orchestrating session commits the move together with the ingest result.
