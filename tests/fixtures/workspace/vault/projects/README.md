# projects/: one folder per project

Each project in kit.conf `PROJECTS` has a folder here, named by its slug. This is where the authoritative,
non-wiki documents of a project live.

## Folder contract

```
projects/<slug>/
  CLAUDE.md      project context: what it is, status, where things go (keep it under ~60 lines)
  PRD.md         requirements: authoritative source of truth, never auto-edited by routines
  planning/      specs and plans in progress (drafts; promoted to the wiki when they settle)
  digests/       agent outputs, overwritten by agents only (see digests/README.md)
```

- **PRD.md is authoritative.** Wiki pages link TO it and never supersede it. Routines read it, never
  write it. Edit it yourself, or let an agent edit it in an interactive session at your request.
- **planning/** is outside the wiki on purpose: drafts change daily. When a plan settles, its durable
  parts become wiki pages (decision, concept) that link back.
- **digests/** belongs to the agents in `agents/`. Do not hand-edit; their source of truth lives in the
  agent's own repo.

Durable knowledge about the project does NOT live here: it lives in `vault/wiki/<type>/` with
`project: <slug>`. Raw sources live in `vault/raw/<slug>/`.

## Create a project

```bash
scripts/new-project.sh my-app "My App"
```

This copies `_template/`, fills `__SLUG__`, `__NAME__` and `__DATE__`, creates
`vault/raw/my-app/{meetings,interviews,sources,snapshots}/`, adds the slug to kit.conf `PROJECTS`, and logs
an `init` op. It never overwrites an existing project.

## Project auto-detection

Commands and agents that need a project resolve it the same way:

1. The CWD is inside `vault/projects/<slug>/`: use that project.
2. Else the request names a project listed in kit.conf `PROJECTS`: use that.
3. Else list `vault/projects/` and ask. In an unattended run there is no one to ask, so the documented
   default is `cross`.

`acme-notes/` is a fictional example; `scripts/init.sh --remove-examples` deletes it.
