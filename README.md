# Human Gateway

`hg` is a second brain for one person or for a department, as a Claude Code plugin. Claude works from your own context, kept as files you can read: a wiki it builds from your own files, such as conversations, notes and exports. Those files stay on your computer, outside git.

When you want to share, a page goes to the department's repository through `/hg:publish`. First an automatic check, then a private preview of exactly what goes out and what was left out, then your own yes. What the department approves is held by gates. A gate names the approved pages and the person who answers for them, and it reopens when a page or an outside source it rests on changes.

That route is a rule Claude is given, not a lock. Plain `git commit` and `git push` still work, for an agent and for a person. What the tools do guarantee is narrower, and [Known limits](#known-limits) says exactly what.

The repository holds only the department's content. Commands, hooks and tools come from the plugin. A gate's outside source can be a task or a board in another system. When an approved page changes, or a source is seen to have changed, the gate shows as `reopened` in `/hg:today`, in `DASHBOARD.md` and at the start of each session. Integrations are nodes you plug in: a messenger (Slack, Microsoft Teams or any JSON webhook), project platforms and a calendar. An agent that works between sessions and a backup of source files are listed as not available yet.

To install it, follow [QUICKSTART.md](QUICKSTART.md) (in Polish). You need Claude Code, git and Python 3.9 or newer, plus Git Bash on Windows. The GitHub CLI signs you in to GitHub. `/hg:setup` and `/hg:doctor` also use it for the messenger: to check that the secret exists, to send a test message and to read how the last run ended. `/hg:setup` offers to install what is missing with winget or Homebrew. It also asks for a git name and email when none is set, because a commit and an approval need them.

| Command | What it does |
|---|---|
| `/hg:setup` | Checks the computer and creates the workspace. Never overwrites a file. `--update` updates the plugin. `--nodes` lists the nodes and plugs in the ones you choose. |
| `/hg:init` | Reads `intake/` and pasted links, writes a context map, asks at most 5 questions, drafts wiki pages and gates, then hands over to `/hg:publish`. |
| `/hg:today`, `/hg:dayend` | Start and end of the day. `/hg:today` also refreshes the marks of the outside sources the session can read. |
| `/hg:import-source`, `/hg:ingest` | Bring a source into `vault/raw/` on this computer and turn it into wiki pages, also on this computer, through a validated change plan. |
| `/hg:wiki-query` | Asks the wiki a question. |
| `/hg:gate` | Creates, lists and approves gates, and adds or removes their outside sources. |
| `/hg:publish` | Checks what changed, writes a private preview of exactly what goes out and what was left out, and commits on your own yes. `withdraw <page>` takes a published page out. |
| `/hg:doctor` | Checks the workspace. |

## Your own files

Five folders stay on your computer and outside git: `intake/` (what you drop in for `/hg:init`), `vault/inbox/` (notes and files waiting to come in), `vault/raw/` (the sources brought in), `vault/daily/` (daily notes) and `.gateway/` (the tools' working files: previews, left-out reports, change plans). The template's `.gitignore` keeps them out. `hg-tool raw-add`, the only writer of `vault/raw/`, refuses when git does not ignore its destination, and `hg-tool scan --git`, on your computer and in CI, reports any tracked file in these folders as `private`.

A page cites a source by a reference such as `src:meetings:2026-01-15:3fa94c1e`: the kind, the date and 8 hex digits of the file's sha256. It is computed from the file, so no list of references is kept anywhere. On your computer, `hg-tool raw-ref --say <ref>` says where the file is. A colleague who asks where a page comes from is told that the source is private, with its kind and date. They also hear that the file stayed with the person who brought it in, and that the page's change history shows who published the page. No path is shown.

There is no backup and no history of these files. A lost disk loses them; the pages made from them stay.

## Publishing

Pages, gates and log lines are written on your computer first. They reach the department's repository through `/hg:publish`, or when you write "opublikuj". `/hg:init`, `/hg:ingest`, `/hg:gate`, `/hg:dayend` and filing an answer from `/hg:wiki-query` all end there.

1. `hg-tool publish check` stages what changed, or only the paths you name, and checks every added line and every new file name: secrets, contact data and file types (the scanner), files from the private folders, file names with invisible characters, text files not saved as UTF-8, names of your source files, the department's word list (`publish.words`, empty until the department fills it), mentions of pages that are not going out, lines shaped like instructions to an assistant, hidden text, and runs of 12 words copied from a file on this computer. Any finding stops the publication.
2. It writes a preview to `.gateway/outgoing/<id>.md`, a file that stays on your computer. It has one line per check saying whether it ran, then what the model left out of the pages, then the files that steer every colleague's assistant (`CLAUDE.md`, `.claude/`, `vault/cleaning.md` and the others), then the full text that goes out.
3. The checks take their settings from the published and the staged `.claude/hg.json`, the stricter of the two, so a publication cannot switch off its own checks. The folders they read (`paths`) must be the same on disk, in the published and in the staged copy, or nothing is checked or committed.
4. You are asked twice: the question in `/hg:publish`, then Claude Code's own prompt before `hg-tool publish commit` runs (a `permissions.ask` rule in `.claude/settings.json`).
5. `hg-tool publish commit <id>` makes the commit. It refuses when what is staged is not the bundle of that id, when the preview on disk is not the one the tool writes for it, when a check finds something on the second run inside the command, or when git has no `user.email`. The message is fixed: a subject, the paths, and the trailers `Hg-Publish`, `Hg-Bundle` and `Hg-Checks`. No text from an agent or a person goes into it.
6. The skill then sends the commit with `git push`. When the department has newer changes, it runs `git pull` and pushes again. When both sides changed the same place, Claude joins the two texts, shows you the result and asks once more; that joined text is committed with git and is not checked.

To correct a published page, change it and publish again. `hg-tool publish withdraw <page>` takes a published page out of the current version, and the deletion goes out the same way. Both leave the earlier text in the change history. The librarian follows the cleaning rules in the plugin's `rules/cleaning.md`; a department adds its own in `vault/cleaning.md` and its word list in `publish.words`.

## Nodes

A node is one optional integration. There are five: the messenger, project platforms, a calendar, an agent and a backup. `hg-tool nodes` prints one line for each, in the content language, and `hg-tool nodes --json` gives the same list as data. An empty node says what plugging it in would add. `/hg:setup --nodes` shows the list and walks through the nodes you pick, and `/hg:doctor` ends its report with it.

- The messenger is the department's channel, described below.
- Project platforms are the systems where tasks and boards live. `hg-tool nodes declare projects clickup,jira` records them. A table of nine platforms (ClickUp, Jira, Asana, Trello, Linear, GitHub, Notion, monday.com, Miro) names the field of an item that is proposed as its mark, and `hg-tool nodes watch <link>` prints it, so `/hg:gate` and `/hg:init` know which field to watch. hg never opens the link: only a session with its own tool for that platform reads it.
- The calendar has nothing to declare. `/hg:today` uses a calendar tool when the session has one.
- An agent that works between sessions and a backup of source files are listed as not available yet.

Declarations live under `nodes` in `.claude/hg.json`, which is tracked. Outside the repository the tool checks one thing: whether the messenger's secret exists, by name, through `gh`. Which tools a session has is something only the session knows: it reports that with a fixed sentence, and nothing stores it.

## The messenger node

The department's repository can post to one channel when a gate starts to wait for approval. The channel is `nodes.messenger.type` in `.claude/hg.json`: `slack`, `teams` (a Microsoft Teams webhook made with the Workflows app, sent as one Adaptive Card) or `webhook` (any https address that takes `{"text": ...}`). With no type declared nothing is sent. `/hg:setup` adds a second workflow, `hg-notify.yml`. It sends one message per gate when a push to the default branch turns it into a draft or reopens it. When more than five start to wait in one push, it sends one list instead. On workday mornings it sends one list, when something waits or has an outside source with no recent recorded check. It needs GitHub Actions and one repository secret, `HG_NOTIFY_WEBHOOK_URL`, which holds the channel's address, whichever channel it is. The plugin holds no address. `/hg:setup --nodes` walks the repository's owner through it. It ends with a test message, the only proof that messages arrive. `hg-tool nodes` calls the messenger plugged in when the declaration, the workflow and the notifier are in the department's repository as this computer last saw it and the secret exists. The messages are fixed sentences, the same on every channel, in Polish when the content language is Polish and in English otherwise. No model writes them, and a gate title loses its markup, its `@` signs and every prefix such as `https://` before it is sent.

## What it does not do

- It does not replace the systems a department already uses. Spreadsheets, Word files, slides and design files stay where they are, and the repository keeps a summary and a link.
- It builds no connectors. `/hg:init` reads a link only if the session already has a read tool for that system. Otherwise the link is kept and the context map records the gap.
- The tool never fetches an outside source. Only the person's own agent reads it, with a read tool the session already has, and records what it read with `hg-tool gate observe`.
- It does not prove that a person read what was approved. An agent may approve on a person's account, and that person answers for the content. No hook blocks approvals and there is no separate bot identity.
- It does not block a commit made with git. The session rule sends every commit through `/hg:publish`, and nothing enforces it (see the limits below).
- It keeps no copy and no history of your own source files.
- It does not guarantee that a page is clean. The checks match patterns, and the model's cleaning is help.

## Known limits

The route to the repository:

- Nothing enforces this route. An agent can commit and push with plain `git`. Of `git commit` and `git push`, the settings deny only the forms that skip hooks or force a push, and the Bash guard lets `git commit` through. "Check, preview, yes" is a rule Claude is given at session start and in the skills. It holds only while the agent keeps to it, and a commit made another way passes no check on that computer. CI then runs the scanner only, after the push.
- The yes in the chat is part of the same rule. The skill asks it with AskUserQuestion, and nothing proves that the person read the preview or could open it.
- What the tools do guarantee is narrower. `hg-tool publish commit <id>` commits only the bundle the preview showed, only with that preview on disk unchanged, only when every check passes again, and always with the fixed message. Claude Code asks the person before a command that matches `Bash(hg-tool publish commit *)` runs, while that `ask` rule is in `.claude/settings.json` (`/hg:doctor` warns when it is missing). The rule matches the command text: another spelling of the same command, with two spaces or quotes, matches only the allow rule `Bash(hg-tool *)` and runs with no prompt. How the prompt behaves in each of Claude Code's permission modes is up to Claude Code and was not tested here.
- An agent with a tool that writes to GitHub directly, such as a GitHub connector or `gh api`, can change the repository with no local commit and no check.

Gates:

- An agent can still run `hg-tool gate approve` directly. The rule that it approves only when the accountable person asked is written in the command and is not enforced.
- `via` (person or agent) is what the approver declares. `by` is the git identity set on that machine, which git does not verify. Git history and `/hg:today` show afterwards what happened.
- A gate covers files in one repository.
- The guards on `gates/` and `vault/raw/` stop honest mistakes. A script can still write there, they let a call through when its payload cannot be parsed, and `HG_GUARD_BYPASS=1` turns them off.

Outside sources on a gate:

- A mark (a source's last-modified time or version) is a statement, like `via`. The tool cannot check it, because it never fetches. An agent can record a wrong mark. The guards against that are the fixed field, the refusal of a date in the future, and git history. A wrong mark can reopen a gate and cannot close one.
- "A person stated it" is also only a declaration. A statement about a source is whatever a session ran with `--declare`; nothing proves a person made it. It cannot close a reopened gate, but it does keep a gate from showing as unchecked.
- The mark is text from an outside system and passes through a shell line the agent writes. The tool takes only letters, digits, spaces and `. , : + / _ = -`, and the Bash guard blocks any other shape of that line. The guard is a hook: it fails open when it cannot parse its input and is off under `HG_GUARD_BYPASS=1`. A mark with other characters cannot be recorded, and that source is then watched by a person's statement.
- The baseline is the first recorded reading, not the state the summary was written from. A change between writing the summary and the first reading is never seen, for example when a source is added to a gate days later.
- When an approval rests on a person's statement, the first tool reading after it becomes the baseline. A change between the statement and that reading is not seen.
- A change in an outside system is noticed only when someone's session reads that source: in `/hg:today` or before an approval. If nobody runs a session, nobody notices; after N days (`gates.sourceCheckDays`, default 7) the gate shows as unchecked.
- Every surface shows what is recorded in the clone it runs in. A check that was made and not published and sent is invisible to everyone else.
- A source with no reported time or version, or one no session can read, is watched only by a person's statement.
- A mark covers the whole item. A comment or a status change in a task moves it and reopens the gate even when the approved content did not change.
- A link with a key, a token or an address in it cannot be a source. The person uses a link without that part.
- Everyone has to update the plugin before the first gate gets a source. An older plugin ignores sources: it shows a gate as approved that the new one and the department's channel show as reopened or unchecked, and an approval made with it records no sources, so the gate reopens at once for everyone else.

Nodes and the messenger:

- A declared node is a statement in `.claude/hg.json`, not a check. For the messenger hg checks two things: that the declaration, the workflow and the notifier are in the department's repository as this computer last saw it, and that a repository secret with the right name exists, the second only where `gh` is signed in. "Plugged in" means both. It does not mean a message arrives: only the test message shows that.
- "This session reports a tool" is the session describing its own tools. It is not stored and not verified.
- "A reading is recorded" means some session read that platform with a tool on that date. It does not mean this computer can.
- The field proposed for a platform comes from its public API documentation. A connector may present the item differently; then the source is watched by a person's statement.
- Teams: only webhooks made with the Workflows app. A workflow belongs to the person who made it and stops when that person leaves, unless someone else is added as an owner (Microsoft's own limitation). The payload was built from Microsoft's sample and not run against a tenant.
- The generic webhook sends one key, `text`. A receiver that needs another shape needs its own small adapter, which hg does not provide.
- With no messenger declared nothing is sent, and that is a green run, as a missing secret is.
- Every limit below holds for all three channels.

The messages:

- GitHub only, with Slack, Microsoft Teams or a generic JSON webhook. It runs after a push, so a change that is not published and sent is not announced.
- The channel sees only what was pushed. The morning list says that the last check recorded in the repository is N days old also when people checked that morning and did not push.
- A missing secret is a green run: the workflow then sends nothing and does not fail. `hg-tool doctor` can say that the last run did not fail, not that a message arrived. Only the test message proves delivery.
- `hg-tool doctor` sees repository secrets only. With an organization secret it warns that none was found although messages are delivered.
- Anyone who may push to the repository can change the workflow and so reach the channel's address, which lets its holder post into that one channel.
- Nothing remembers what was sent: a run started again posts again. The morning list repeats every workday while something waits.
- Two pushes close together may be announced in either order.
- A failed post fails the `hg notify` run and nothing else. GitHub mails that failure to whoever pushed, or, for the morning run, to whoever last changed the workflow file.
- GitHub may start a scheduled run late. After a force push the per-gate messages are skipped and the next morning list covers them.
- The accountable person is named by the address in the gate, on the lines about gates that wait for approval, visible to everyone in the channel. No message mentions anyone, and a channel may show the address as a mail link.
- The cleaning of titles was tested on text only, not against Slack or Teams. Whether a channel turns a bare domain name in a title into a link is not known.

Your own files:

- They exist on one computer. There is no backup and no history. A lost disk loses them; the pages made from them stay.
- On a second computer, or after a restore, a source resolves again only if the same `vault/raw/` folder is copied back by hand.
- A reference shows the kind of source and its date to everyone who can read the repository. Its 8 hex digits come from the file's content, so someone who already holds the same file can confirm that it is the one.
- A colleague cannot read your private source. They are told so, and that the page's change history shows who published it. Git history names that person, as it does for every file; hg adds no other record of who holds what.
- The scan no longer keeps contact data out of `vault/raw/`: it only counts it. A secret is still refused there, and a file with a secret stays in `intake/`.
- The check that a private file is not in git runs in `hg-tool publish check` and in CI. A file committed and pushed with plain git, for example after `git add --force` in a person's own terminal, is reported by CI after the push, when it is already on the remote.
- `git clean -x` or `git stash --all` run by a person deletes their raw files from the folder. The guard stops an agent's Bash command, not a person.
- The guards on `gates/` and `vault/raw/`, and the rules against `git add --force`, `git clean`, `git stash --all` and `git update-index`, cover the Bash tool and the file tools. They do not cover the PowerShell tool: a PowerShell command that runs one of those git commands, or deletes or rewrites a file there, is not stopped.

Publishing:

- While a merge waits, `hg-tool publish check` refuses. A merge is finished with git, so text resolved by hand in a conflict is not checked. A merge git makes by itself during `git pull` is not checked either.
- The model's cleaning is help, never a guarantee, and the checks match patterns. Neither catches a judgment of a person written politely, a complaint or blame without a listed word, a fact that compromises someone, a name that is not on the department's list, the contents of images and PDF files, a quote put in other words, an instruction written as ordinary prose, or an instruction in a language other than Polish and English.
- The list of what was left out is written by the model that did the cutting. Nothing checks that it is complete. A file with no such list is named in the preview, without a reason: the tool cannot tell a page edited by hand from one whose list the model did not save.
- The quote check compares word-for-word runs (12 words by default, `publish.quoteWords`) with text files in `vault/raw/`, `vault/inbox/`, `vault/daily/` and `intake/` on the computer that publishes. Binary files, files over 5 MB and sources only a colleague holds are not compared; the preview gives the numbers. A person's own note copied word for word into a page is refused like any copy. A table is compared row by row, so a copied table of short rows passes.
- The word list is tracked, so everyone who can read the repository can read it. It ships empty, and with an empty list the check does nothing, as the preview says. Polish inflection needs stems with `*`, such as `zwolnien*`.
- The instruction check has false alarms and misses. Its test set has 17 planted lines, all caught, and 31 ordinary lines, none refused; 4 planted lines written as plain prose pass. A department can switch it off, and the hidden-text and quote checks too, under `publish.off`. The change is visible in git and named in every preview.
- A change to the check settings that loosens a check works from the next publication on. The publication that makes it is still checked with the stricter settings and shows the change among the control files. Nothing stops a person from publishing such a change: the department sees it in git.
- Control files (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.github/`, `vault/cleaning.md` and the others) steer every colleague's assistant. The preview shows a change to them first and says so. It does not judge the change: a hook added to `.claude/settings.json` goes out when the person says yes.
- The hidden-text check reads added lines only, so a line added inside a comment that was already published is not seen. It catches comments, invisible and format characters, line breaks a reader sees and git does not, runs of variation selectors, an element hidden by the `hidden` attribute or an inline `display:none` or `visibility:hidden`, a `<details>` block and a link definition's title. Text hidden by a class, by its colour or by a tiny font passes.
- A source file's name written without its folder is caught only while that file is on the computer that publishes. A raw file another person holds, or a file already moved out of `intake/` or the inbox, is caught only by its path.
- After a publication of chosen paths, the index, the log and the journal in git lag behind until the next full publication.
- A page that was drafted and deleted before it was published stays named, by its path, in the log line of the ingest that made it.
- A commit made by the tool names who made it by the git identity of that computer, which git does not verify.
- Sending is a separate step. A publication that was committed and not sent is invisible to everyone else; `/hg:today` counts it among the changes not published yet.
- A repository that tracks files under `vault/raw/` refuses every publication until they leave the index. `hg-tool setup` takes out the empty `.gitkeep` placeholders an earlier release made. Real raw files are left to whoever maintains the repository: `git rm -r --cached vault/raw` in their own terminal (the guards stop an agent from running it), then `/hg:publish` sends the deletion and the files stay on that computer.
- Git keeps everything. A withdrawn or corrected page stays in the history and in every clone made before. A secret that went out must be replaced.

Scanner (`hg-tool scan`):

- It matches patterns: known token formats, values assigned to names like `password`, email addresses, phone numbers, IBANs and long runs of digits. A secret in an unknown format passes. A company can add its own under `scan.patterns`.
- It does not find names of people. HR data, statistics per person, signed documents and recordings with names are left to the agent when it reads a source, and that check is not deterministic.
- It does not read the contents of binary files such as PDFs and images. They are listed as not read and do not change the exit code. Office and design files are recognised by extension only.
- The publish check before a commit, which runs the scanner, is a rule given to the agent at session start, and no git hook runs it. The workflow in the department's repository runs on GitHub on push and pull request, so it reports a finding after the content has reached the remote.

## Tests

You need bash, git and Python 3.9 or newer. The full run takes several minutes. `claude plugin validate` is included when `claude` is on the path.

```
bash tests/run-all.sh
bash tests/run-all.sh gates      # only tests whose path contains "gates"
bash tests/run-all.sh --verbose  # print each test's output
```

`tests/gates/test-gate-sources.sh` covers outside sources on a gate: the list, the recorded checks, approval, status and the Bash guard's rule for a mark.

`tests/raw/test-raw-ref.sh` covers source references: how one is computed, finding the file again, what a reader is told on this computer and on a colleague's, which sources pages cite, and the one definition of the private folders.

`tests/notify/test-notify.sh` covers the messenger: which gates started to wait in a push, the morning list, the templates and their cleaning, the three channels and their payloads, the secret, the copies CI uses and the workflow. It never touches the network.

`tests/nodes/test-nodes.sh` covers `hg-tool nodes`: the five nodes and their states, declaring them, what the department's repository holds (a bare remote in a temp folder), the secret through a stub of `gh`, recorded readings, the platform table and `watch`. It never touches the network.

`tests/publish/test-publish.sh` covers `hg-tool publish`: staging, the bundle and its id, every check and the settings they read, the preview word for word, left-out reports, the commit and its message, withdrawing a page, the rule copied into the skills, and the stated limit that nothing blocks `git commit`.

`.github/workflows/tests.yml` runs the same suites on `windows-latest` and `macos-latest`.

## License

MIT. See [LICENSE](LICENSE).
