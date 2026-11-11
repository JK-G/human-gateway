---
name: setup
description: Set up this folder as a department workspace - check tools, sign in to GitHub, create the skeleton, set the git name and email. With --update, update the plugin.
argument-hint: "[--update | --slack]"
disable-model-invocation: true
---

# /hg:setup

Talk to the person in plain words, in the language they write in or, once `.claude/hg.json` exists, in
`language.content`. Assume they are not technical. `$ARGUMENTS` containing `--update` means: go straight
to **Update** below. `$ARGUMENTS` containing `--slack` means: go straight to **Slack** below.

## 1. Check the computer

Run `hg-tool doctor` and read the `python`, `git`, `gh` and `git-bash` lines. On a folder that is not set up
yet, `ERROR` lines for `config` are expected, so ignore them here.

If `hg-tool` itself says Python was not found, treat Python as missing. On Windows without Git there is no
Bash tool yet: use the PowerShell tool for step 2.

## 2. Install what is missing

Say in one sentence what is missing and what you will install, and ask once, with AskUserQuestion, whether
to go ahead. That one answer covers every install below. Nothing missing: skip this step.

| Program | Windows | macOS |
|---|---|---|
| git and Git Bash | `winget install --id Git.Git -e --source winget` | `brew install git` |
| gh | `winget install --id GitHub.cli -e --source winget` | `brew install gh` |
| Python | `winget install --id Python.Python.3.12 -e --source winget` | `brew install python` |

- No `winget` or no `brew`: tell the person what is needed and stop. Do not install a package manager yourself.
  If `gh` is the only thing missing, or only its install fails, carry on: step 3 has a way without it.
- A freshly installed program is often invisible until Claude Code restarts. If `hg-tool doctor` still
  reports it missing, ask the person to quit Claude Code (the whole app, if they use the desktop app),
  reopen it in this folder and run `/hg:setup` again.

## 3. Sign in to GitHub

1. If `gh` is installed, run `gh auth status`. If it reports a signed-in account, go to item 4.
2. Sign-in needs the person's own browser and keyboard. If `gh` is installed, ask them to type
   `! gh auth login` into the prompt, choose GitHub.com, HTTPS and the browser, and tell you when it is done.
   Run `gh auth status` again. If it reports an account, go to item 4.
3. If that failed, the prompt gave them no way to answer, or `gh` is missing, let git sign in by itself. Run
   `git ls-remote origin HEAD`. With no `origin`, use `https://github.com/<repo>` in its place, with `<repo>`
   from `extraKnownMarketplaces.human-gateway.source.repo` in `.claude/settings.json`. On Windows a browser
   window from Git may open: ask the person to sign in there.
   - If there is no `origin` and the settings name no repo, this folder needs no GitHub yet. Say that the
     sign-in waits until the repo is pushed, skip item 4 and go to step 4.
   - If the command prints a line with a commit, git can read GitHub. Skip item 4 and go to step 4.
   - If it fails and `gh` is installed, ask the person to open a terminal (in the desktop app: Ctrl and the
     backtick key), run `gh auth login` there, and tell you when it is done. Then go to item 4.
   - If that fails too, tell the person the sign-in did not finish, ask them to contact whoever set up this
     repo, and stop.
4. Run `gh auth setup-git`, so that git can read private repositories.

## 4. Ask three things

If `.claude/hg.json` already exists, skip this step: the file is never changed.

Use one AskUserQuestion call with three questions:

- **Name** of the workspace, usually the department. Propose the folder name.
- **Language** of the notes and pages. Propose `pl` first.
- **Timezone.** Propose `Europe/Warsaw` first, and `UTC`.

## 5. Create the workspace

Run `claude plugin marketplace list`. If the shell cannot find `claude` or the command fails, leave the flag
out and carry on: the desktop app does not need that command, so do not install it. If it shows
`human-gateway` coming from a GitHub repo, pass that `owner/repo` as `--marketplace`, so the next person can
install the plugin. Otherwise leave the flag out.

```
hg-tool setup --name "<name>" --language <code> --timezone <zone> [--marketplace owner/repo]
```

Add `--project <slug>` only if the person named a project. If `.claude/hg.json` already existed, run plain
`hg-tool setup`, which only fills in what is missing. It never overwrites a file. Report what it created and skipped in one sentence, not line by line. Do not commit.

## 6. Set the git identity

A commit and `hg-tool gate approve` both need a name and an email in git. Run `git config user.email` and
`git config user.name`. If either prints nothing, ask the person for the missing one, then set it for this
repo only, without `--global`:

```
git config user.name "<name>"
git config user.email "<email>"
```

Never guess either value. For the email, suggest the address the department's gates name them by: an approval
on their behalf is offered only when the two match.

## 7. Check again and say what is next

Run `hg-tool doctor` and explain anything marked `ERROR`, then the `marketplace`, `scanner` and `gitignore` warnings if there are any. A `gitignore` warning means notes or files in `intake/` could reach git: treat it as important and offer to add the lines it names.
A `journal` warning is normal on a new machine, so do not mention it.

Three lines are about the Slack message that says a gate waits:

- `notify`: the workflow `.github/workflows/hg-notify.yml` and the copies in `.github/hg/` it runs. A warning
  means one is missing or differs from the plugin: `hg-tool setup --refresh-ci` puts them back.
- `notify-secret`: whether GitHub has a repository secret named `HG_SLACK_WEBHOOK_URL`. A warning is not proof
  that nothing is set: a secret the company set for the whole organization does not show up here.
- `notify-run`: the last run of that workflow. An `OK` is not proof that a message arrived: a run without the
  secret also ends green. Only the test message in the **Slack** step proves it.

The two `notify-` lines appear only when the repo is on GitHub and `gh` is installed.

Then tell the person what comes next:

1. Look at the new files and ask you to commit them when ready.
2. Push the repo to a private place that only the intended readers can open.
3. Put the department's files in `intake/` and run `/hg:init`, which builds the context map from them
   and from any links they paste.
4. Run `/hg:today` to start the first day. Anyone joining later opens the repo and runs `/setup`.

If the `notify-secret` line is a `WARN`, ask one question with AskUserQuestion before you finish: is this person
the one who sets up the department's Slack messages, and are they not set up yet? On "yes", go on with
**Slack**. On "no", skip it: in a repo that uses an organization secret, a colleague is not walked through it.

## Slack

For the person who owns the department repo on GitHub. The message says in the department's channel when a gate
waits for approval, and lists every workday morning what waits. It needs GitHub Actions and one secret; the
plugin holds no address.

1. The workflow and the files in `.github/hg/` must be committed and pushed first. If `git status` shows them
   as new or changed, say so and ask whether to commit and push them. Commit only when the person asks.
2. Ask the person to create an incoming webhook for the department's channel in Slack and to copy its address.
   This may need a Slack administrator.
3. Ask them to open the link from the `notify-secret` line, enter the name `HG_SLACK_WEBHOOK_URL`, paste the
   address as the value and save. **The address is never pasted into the chat, a file or a command.** If it was,
   tell the person to delete that webhook in Slack and create a new one, because the old address is no longer
   private.
4. Run `hg-tool notify status`. When the `notify-secret` line is `OK`, run `gh workflow run hg-notify.yml -f mode=test`,
   wait half a minute, run `hg-tool notify status` again and read `notify-run`. Without `gh`: the Actions tab on
   GitHub, "hg notify", "Run workflow", mode `test`.
5. Ask whether the test message arrived in the channel. That answer, not the green run, is the check.
6. Tell the person that everyone in the department should set the channel in Slack to notify them on every new
   message, or nobody is pinged.

## Update

1. Note the repo's version: `hg-tool conf SCHEMA_VERSION`.
2. Run `claude plugin update hg@human-gateway` and report whether it changed anything.
3. Ask the person to type `/reload-plugins` and to tell you when it is done.
4. Run `hg-tool setup --refresh-ci`, which replaces the copies of the tools that CI uses in `.github/hg/` and
   adds a missing workflow in `.github/workflows/`. It never overwrites a workflow and touches nothing else.
   Report every file it printed as `updated` or `created` as a file that needs committing. Do not commit.
5. Run `hg-tool doctor` and read the `config` line, which compares the repo's `schemaVersion` with the
   plugin's. If they match, say the update is finished. If they differ, say that this repo's configuration
   is older than the plugin and that the update must wait for a migration from whoever maintains the
   plugin. Do not edit `.claude/hg.json` to make the numbers agree.
