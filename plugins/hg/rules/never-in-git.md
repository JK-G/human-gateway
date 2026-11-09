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
6. **Raw recordings and transcripts with names:** anonymise before saving, because `vault/raw/`
   is immutable. Record roles, and let the person approve the transcript before it is saved.
7. **Files people work on together:** Figma, spreadsheets, Word. A link.

What stays in git: procedures, playbooks, skills, glossary, policies, PRDs, the decision log and
gate records.

How it is enforced: a scan before saving and before every commit, and in CI on the host (`hg-tool scan`). A company adds
its own addresses and patterns under `scan.allow` and `scan.patterns` in `.claude/hg.json`. The
scan catches secrets and contact data reliably. Points 3 to 6 need judgment, so the agent checks them when it reads a
source, and that check is not deterministic.
