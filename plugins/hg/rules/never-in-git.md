# What never enters git

A file that reaches git history cannot be fully removed: every clone keeps a copy. These seven
kinds of content stay out, whatever the repository's visibility. A company may add to this list
under `neverInGit.extra` in `.claude/hg.json`. It cannot remove anything from it.

1. **Secrets:** passwords, tokens, keys and webhook URLs, including keys shared by a team. Only
   values public by design may be in a repo (publishable keys, analytics IDs, public addresses,
   list IDs). Shared keys go to a password manager and GitHub Secrets, with the variable name in
   the repo.
2. **Personal data of customers and end users:** anonymise it, or point to the source system.
3. **HR data about named people:** pay, reviews, health, employment contracts.
4. **Statistics per person:** per role and per gate only.
5. **Signed documents:** contracts, annexes, NDAs. A pointer and a description without data.
6. **A person's own source files:** conversations, notes, transcripts, recordings, exports. They stay in
   `vault/raw/` on that person's machine. The repository gets processed pages only.
7. **Files people work on together:** Figma, spreadsheets, Word. A link.

What stays in git: procedures, playbooks, skills, glossary, policies, PRDs, the decision log and
gate records.

How it is enforced: a scan before saving, the publish check before every commit (`hg-tool publish check`, which
runs the scan and checks for private files, names of source files, the department's word list, instruction-shaped
lines, hidden text and copied runs), and the scan in CI on the host (`hg-tool scan`). Nothing stops a commit made
with git directly; then only CI scans it, after the push. With
`--git` the scan also reports any tracked file in a private folder (`vault/raw/`, `vault/inbox/`, `vault/daily/`,
`intake/`, `.gateway/`). A company adds its own addresses and patterns under `scan.allow` and `scan.patterns` in
`.claude/hg.json`. The scan catches secrets, contact data and private files reliably. Neither the scan nor any
other check can judge points 3 to 5, or whether a page carries too much of a person's own file: the agent checks
that when it reads a source, and that check is not deterministic.
