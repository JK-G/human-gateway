---
name: setup
description: Set up this folder as a department workspace - check tools, sign in to GitHub, create the skeleton, set the git name and email. With --update, update the plugin.
argument-hint: "[--update | --nodes]"
disable-model-invocation: true
---

# /hg:setup

Talk to the person in plain words, in the language they write in or, once `.claude/hg.json` exists, in
`language.content`. Assume they are not technical. `$ARGUMENTS` containing `--update` means: go straight
to **Update** below. `$ARGUMENTS` containing `--nodes` means: go straight to step 8.

Before any commit in a department repository, run hg-tool publish check, show the person the preview it writes,
and commit only through the commit step of /hg:publish, after the person's own yes in this session. This skill
commits nothing itself.

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
`hg-tool setup`, which only fills in what is missing. It never overwrites a file. Report what it created and skipped in one sentence, not line by line. Do not commit: the new files go out through `/hg:publish` (step 7).

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

The `raw` lines are about a person's own source files, which stay in `vault/raw/` on this computer and outside
git. A `raw` `ERROR` comes before everything else:

- `... are tracked by git`: a file from a private folder is in git. Run `hg-tool setup` once: it takes out the
  empty `.gitkeep` placeholders an earlier release made and prints each as `untracked`, a change to publish. If
  the `ERROR` stays, change nothing yourself: the person tells whoever maintains the repository, who runs
  `git rm -r --cached vault/raw` in their own terminal and then publishes with `/hg:publish`.
- `vault/raw/ is not ignored by git here`: a raw file could be committed. Run `hg-tool setup`, which adds the
  missing lines to `.gitignore`, then `hg-tool doctor` again.
- The `OK` lines: how many source files are on this computer, with no backup, and how many references in pages
  point to sources that are on a colleague's computer. Both are normal. Mention the missing backup once.

Three lines are about the message in the department's channel that says a gate waits:

- `notify`: the workflow `.github/workflows/hg-notify.yml` and the copies in `.github/hg/` it runs. A warning
  means one is missing or differs from the plugin: `hg-tool setup --refresh-ci` puts them back. With no messenger
  declared and no workflow, the line is `OK` and says how to plug one in.
- `notify-secret`: whether GitHub has a repository secret named `HG_NOTIFY_WEBHOOK_URL`, which holds the
  channel's address. A warning is not proof that nothing is set: a secret the company set for the whole
  organization does not show up here.
- `notify-run`: the last run of that workflow. An `OK` is not proof that a message arrived: a run without the
  secret also ends green. Only the test message in **Messenger** below proves it.

The two `notify-` lines appear only when a messenger is declared, the repo is on GitHub and `gh` is installed.
The `node` lines are for you and are not copied: step 8 shows the person the list in their language.

Then tell the person what comes next:

1. Look at the new files and write `opublikuj` (or `/hg:publish`) when ready. The first preview lists the plugin's
   own files by name only and shows the files made for this department in full.
2. Put the repo in a private place on GitHub that only the intended readers can open, and add it as `origin`:
   `/hg:publish` sends the changes there.
3. Put the department's files in `intake/` and run `/hg:init`, which builds the context map from them
   and from any links they paste.
4. Run `/hg:today` to start the first day. Anyone joining later opens the repo and runs `/setup`.

## 8. Nodes

A node is one optional integration. Run `hg-tool nodes` and copy the third column of its five lines to the person,
one bullet each, as they are: each empty line says what plugging it in would add.

Then ask one AskUserQuestion with multiple choice: which of the nodes that are `available` and still `empty` (the
messenger, the project platforms) to plug in now, with **None now** as an answer. A messenger that is `declared`
but still lacks something is offered too, as "finish the messenger". The calendar, the agent and the backup are
not in the question: the calendar has nothing to declare, and the other two are not available yet. With nothing to
offer, skip the question. Walk the chosen ones in list order through **Nodes** below. On **None now**, say that
`/hg:setup --nodes` comes back to this list.

## Nodes

### Messenger

For the person who owns the department repo on GitHub. A plugged-in channel gets a message when a gate starts to
wait for approval, and every workday morning a list of what waits. It needs GitHub Actions and one secret; the
plugin holds no address. A colleague in a repo where this is already set up is not walked through it.

1. Ask which channel the department uses: **Slack**, **Microsoft Teams**, or **another tool that takes a JSON
   webhook**. Run `hg-tool nodes declare messenger slack|teams|webhook` with the answer. It writes
   `nodes.messenger.type` in `.claude/hg.json` and prints the messenger's new line.
2. The workflow `.github/workflows/hg-notify.yml`, the copies in `.github/hg/` and `.claude/hg.json` must be in the
   department's repository first: published and sent. Run `hg-tool nodes` again: its messenger line says which
   of them the repository still lacks. Say so and start `hg:publish` with the Skill tool: its question is the
   person's yes. Then run `hg-tool nodes` once more.
3. Ask the person to create the channel's address and to copy it:
   - Slack: an incoming webhook for the department's channel. This may need a Slack administrator.
   - Microsoft Teams: in the channel's menu choose **Workflows**, then the template
     **Send webhook alerts to a channel**, and copy the address it shows at the end. The workflow belongs to the
     person who makes it, and stops when that person leaves unless someone else is added as an owner.
   - Another tool: any https address that takes a POST with `{"text": ...}`.
4. Ask them to open the link from the `notify-secret` line of `hg-tool notify status`, enter the name
   `HG_NOTIFY_WEBHOOK_URL`, paste the address as the value and save. **The address is never pasted into the chat,
   a file or a command.** If it was, tell the person to delete that address in the channel's tool and create a new
   one, because the old address is no longer private.
5. Run `hg-tool notify status`. When the `notify-secret` line is `OK`, run `gh workflow run hg-notify.yml -f mode=test`,
   wait half a minute, run `hg-tool notify status` again and read `notify-run`. Without `gh`: the Actions tab on
   GitHub, "hg notify", "Run workflow", mode `test`.
6. Ask whether the test message arrived in the channel. That answer, not the green run and not the word
   "plugged in" in `hg-tool nodes`, is the check.
7. Tell the person that everyone in the department should set the channel to notify them on every new message, or
   nobody is pinged.

### Project platforms

1. Ask which systems the department keeps tasks and boards in. The keys are those of `hg-tool nodes watch`'s table:
   `clickup`, `jira`, `asana`, `trello`, `linear`, `github`, `notion`, `monday`, `miro`, and `other` for anything
   else. Run `hg-tool nodes declare projects <key>,<key>`.
2. For each declared platform, look at this session's own tools. If one reads that platform, copy the projects
   node's `session_yes` from `hg-tool nodes --json --offline` with the platform's name in place of `{platform}`;
   otherwise copy its `session_no` the same way. hg stores neither sentence.
3. Say that each person connects the platform in their own Claude, outside hg. hg itself fetches nothing.

### Calendar

Run `hg-tool nodes --json --offline` and copy the calendar node's `session_yes` when this session has a calendar
tool, else its `session_no`. There is nothing to declare.

## Update

1. Note the repo's version: `hg-tool conf SCHEMA_VERSION`.
2. Run `claude plugin update hg@human-gateway` and report whether it changed anything.
3. Ask the person to type `/reload-plugins` and to tell you when it is done.
4. Run `hg-tool setup --refresh-ci`, which replaces the copies of the tools that CI uses in `.github/hg/`,
   adds a missing workflow in `.github/workflows/` and replaces `hg-notify.yml` only when it is an earlier
   release's, adds missing `.gitignore` lines, and takes old empty placeholders under `vault/raw/` out of git.
   Report every file it printed as `updated`, `created` or `untracked` as a file to publish, and start `hg:publish` with the
   Skill tool when the person wants to send them now. Do not commit any other way.
5. Run `hg-tool doctor` and read the `config` line, which compares the repo's `schemaVersion` with the
   plugin's. If they match, say the update is finished. If they differ, say that this repo's configuration
   is older than the plugin and that the update must wait for a migration from whoever maintains the
   plugin. Do not edit `.claude/hg.json` to make the numbers agree.
