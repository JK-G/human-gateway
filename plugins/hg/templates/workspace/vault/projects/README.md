# projects/: one folder per project

Each project in `projects` of `.claude/hg.json` has a folder here, named by its slug. This is where the
authoritative, non-wiki documents of a project live.

## Folder contract

```
projects/<slug>/
  CLAUDE.md      project context: what it is, status, where things go (keep it under ~60 lines)
  PRD.md         requirements: authoritative source of truth
  planning/      specs and plans in progress (drafts; promoted to the wiki when they settle)
```

- **PRD.md is authoritative.** Wiki pages link TO it and never supersede it. Agents read it and change it
  only at a person's request in a session.
- **planning/** is outside the wiki on purpose: drafts change daily. When a plan settles, its durable
  parts become wiki pages (decision, concept) that link back.

Durable knowledge about the project does NOT live here: it lives in `vault/wiki/<type>/` with
`project: <slug>`. Raw sources live in `vault/raw/<slug>/`.

## Create a project

```bash
hg-tool setup --project my-app
```

This copies `_template/`, fills `__SLUG__`, `__NAME__` and `__DATE__`, and creates
`vault/raw/my-app/{meetings,interviews,sources,snapshots}/`. It never overwrites a file. In an existing
workspace, then run `hg-tool conf-set project my-app`; the command reminds you.

## Project detection

Commands and agents that need a project resolve it the same way:

1. The CWD is inside `vault/projects/<slug>/`: use that project.
2. Else the request names a project listed in `.claude/hg.json`: use that.
3. Else list `vault/projects/` and ask.
