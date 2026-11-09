---
name: setup
description: Prepare this computer for this department workspace - install git, gh and Python, sign in to GitHub, install the hg plugin, then hand over to /hg:setup.
disable-model-invocation: true
---

# /setup

This skill lives in the department repo, so it works before the `hg` plugin is installed. It prepares the
computer and ends by handing over to `/hg:setup`. Talk to the person in the language they write in, in
plain words. Assume they are not technical.

On Windows without Git there is no Bash tool yet: use the PowerShell tool until Git is installed.

## 1. Check what is missing

Run each and note what fails:

- `git --version`
- `gh --version`
- Python 3.9 or newer: `python3 --version`, `python --version`, and on Windows `py -3 --version`. Any one
  of them is enough. A command that prints no version is the Microsoft Store placeholder and does not count.

## 2. Install what is missing

Say in one sentence what is missing and what you will install, and ask once, with AskUserQuestion, whether
to go ahead. That one answer covers every install below.

| Program | Windows | macOS |
|---|---|---|
| git | `winget install --id Git.Git -e --source winget` | `brew install git` |
| gh | `winget install --id GitHub.cli -e --source winget` | `brew install gh` |
| Python | `winget install --id Python.Python.3.12 -e --source winget` | `brew install python` |

- No `winget` or no `brew`: tell the person what is needed and stop. Do not install a package manager yourself.
  If `gh` is the only thing missing, or only its install fails, carry on: step 3 has a way without it.
- A freshly installed program is often invisible until Claude Code restarts. If a check still fails after
  a successful install, ask the person to quit Claude Code (the whole app, if they use the desktop app),
  reopen it in this folder and run `/setup` again.

## 3. Sign in to GitHub

1. If `gh` is installed, run `gh auth status`. If it reports a signed-in account, go to item 4.
2. Sign-in needs the person's own browser and keyboard. If `gh` is installed, ask them to type
   `! gh auth login` into the prompt, choose GitHub.com, HTTPS and the browser, and tell you when it is done.
   Run `gh auth status` again. If it reports an account, go to item 4.
3. If that failed, the prompt gave them no way to answer, or `gh` is missing, let git sign in by itself. Run
   `git ls-remote origin HEAD`. With no `origin`, use `https://github.com/<repo>` in its place, with `<repo>`
   from `extraKnownMarketplaces.human-gateway.source.repo` in `.claude/settings.json`. On Windows a browser
   window from Git may open: ask the person to sign in there.
   - If the command prints a line with a commit, git can read GitHub. Skip item 4 and go to step 4.
   - If it fails and `gh` is installed, ask the person to open a terminal (in the desktop app: Ctrl and the
     backtick key), run `gh auth login` there, and tell you when it is done. Then go to item 4.
   - If that fails too, tell the person the sign-in did not finish, ask them to contact whoever set up this
     repo, and stop.
4. Run `gh auth setup-git`, so that git can read private repositories.

## 4. Install the plugin

Run:

```
claude plugin install hg@human-gateway --scope project
```

Automatic loading from the repo settings is not reliable enough to skip this, so always run it. If it says
the plugin is already installed, carry on.

If it says the marketplace is unknown, read `extraKnownMarketplaces.human-gateway.source.repo` from
`.claude/settings.json`, run `claude plugin marketplace add <that repo>`, and run the install again. If the
settings name no marketplace, ask the person who set up this repo where the plugin comes from, and stop.

If the shell cannot find `claude`, the person is probably in the desktop app, which does not need that
command. Do not install it. Ask them to do this in the app and to tell you when it is done:

1. Click **+** next to the prompt box and choose **Add plugins**. If the menu shows **Plugins** instead, choose
   it, then **Browse plugins**.
2. Find `hg` from `human-gateway`, install it and choose the project scope.

If `hg` is not in the list, read `extraKnownMarketplaces.human-gateway.source.repo` from
`.claude/settings.json`, ask the person to type `/plugin marketplace add <that repo>`, and look again. If that
fails or the settings name no marketplace, ask them to contact whoever set up this repo, and stop.

## 5. Hand over

Ask the person to type `/reload-plugins`, and then `/hg:setup`. They have to type both themselves: you
cannot start them.

If the app says `/reload-plugins` is not available, or `/hg:setup` is not in the list when they type `/`, ask
them to quit and reopen Claude Code in this folder and type `/hg:setup` in the new session. If it is still not
there, ask them to install `hg` again as in step 4 with the scope for their user account, reopen, and try once
more. If it is still missing, ask them to contact whoever set up this repo.
