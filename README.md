# Human Gateway

`hg` is a Claude Code plugin that gives a department a private git repository for its knowledge, with approvals that reopen when the files behind them change.

The repository holds only the department's content. Commands, hooks and tools come from the plugin. An approval is called a gate: it names the approved files and the person who answers for them. A gate may also name outside sources, such as a task or a board in another system. When one of those files changes, or a source is seen to have changed, the gate shows as `reopened` in `/hg:today`, in `DASHBOARD.md` and at the start of each session.

To install it, follow [QUICKSTART.md](QUICKSTART.md) (in Polish). You need Claude Code, git and Python 3.9 or newer, plus Git Bash on Windows. The GitHub CLI signs you in to GitHub. `/hg:setup` and `/hg:doctor` also use it for the Slack message: to check that the secret exists, to send a test message and to read how the last run ended. `/hg:setup` offers to install what is missing with winget or Homebrew. It also asks for a git name and email when none is set, because a commit and an approval need them.

| Command | What it does |
|---|---|
| `/hg:setup` | Checks the computer and creates the workspace. Never overwrites a file. `--update` updates the plugin. `--slack` sets up the Slack message. |
| `/hg:init` | Reads `intake/` and pasted links, writes a context map, asks at most 5 questions, drafts wiki pages and gates for approval. |
| `/hg:today`, `/hg:dayend` | Start and end of the day. `/hg:today` also refreshes the marks of the outside sources the session can read. |
| `/hg:import-source`, `/hg:ingest` | Bring a source into `vault/raw/` and turn it into wiki pages through a validated change plan. |
| `/hg:wiki-query` | Asks the wiki a question. |
| `/hg:gate` | Creates, lists and approves gates, and adds or removes their outside sources. |
| `/hg:doctor` | Checks the workspace. |

## The Slack message

The department's repository can post to one Slack channel when a gate starts to wait for approval. `/hg:setup` adds a second workflow, `hg-notify.yml`. It sends one message per gate when a push to the default branch turns it into a draft or reopens it. When more than five start to wait in one push, it sends one list instead. On workday mornings it sends one list, when something waits or has an outside source with no recent recorded check. It needs GitHub Actions and one repository secret, `HG_SLACK_WEBHOOK_URL`, which holds the channel's incoming webhook address. The plugin holds no address. `/hg:setup --slack` walks the repository's owner through it and ends with a test message. The messages are fixed sentences, in Polish when the content language is Polish and in English otherwise. No model writes them, and a gate title loses its markup, its `@` signs and every prefix such as `https://` before it is sent.

## What it does not do

- It does not replace the systems a department already uses. Spreadsheets, Word files, slides and design files stay where they are, and the repository keeps a summary and a link.
- It builds no connectors. `/hg:init` reads a link only if the session already has a read tool for that system. Otherwise the link is kept and the context map records the gap.
- The tool never fetches an outside source. Only the person's own agent reads it, with a read tool the session already has, and records what it read with `hg-tool gate observe`.
- It does not prove that a person read what was approved. An agent may approve on a person's account, and that person answers for the content. No hook blocks approvals and there is no separate bot identity.
- It does not commit or push by itself. The agent is told to commit only when the person asks.

## Known limits

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
- Every surface shows what is recorded in the clone it runs in. A check that was made and not committed and pushed is invisible to everyone else.
- A source with no reported time or version, or one no session can read, is watched only by a person's statement.
- A mark covers the whole item. A comment or a status change in a task moves it and reopens the gate even when the approved content did not change.
- A link with a key, a token or an address in it cannot be a source. The person uses a link without that part.
- Everyone has to update the plugin before the first gate gets a source. An older plugin ignores sources: it shows a gate as approved that the new one and Slack show as reopened or unchecked, and an approval made with it records no sources, so the gate reopens at once for everyone else.

Slack message:

- GitHub and Slack only. It runs after a push, so a change that is not committed and pushed is not announced.
- The channel sees only what was pushed. The morning list says that the last check recorded in the repository is N days old also when people checked that morning and did not push.
- A missing secret is a green run: the workflow then sends nothing and does not fail. `hg-tool doctor` can say that the last run did not fail, not that a message arrived. Only the test message proves delivery.
- `hg-tool doctor` sees repository secrets only. With an organization secret it warns that none was found although messages are delivered.
- Anyone who may push to the repository can change the workflow and so reach the webhook address, which lets its holder post into that one channel.
- Nothing remembers what was sent: a run started again posts again. The morning list repeats every workday while something waits.
- Two pushes close together may be announced in either order.
- A failed post fails the `hg notify` run and nothing else. GitHub mails that failure to whoever pushed, or, for the morning run, to whoever last changed the workflow file.
- GitHub may start a scheduled run late. After a force push the per-gate messages are skipped and the next morning list covers them.
- The accountable person is named by the address in the gate, on the lines about gates that wait for approval, visible to everyone in the channel. Slack notifies nobody by name, and may show the address as a mail link.
- The cleaning of titles was tested on text only, not against Slack. Whether Slack turns a bare domain name in a title into a link is not known.

Scanner (`hg-tool scan`):

- It matches patterns: known token formats, values assigned to names like `password`, email addresses, phone numbers, IBANs and long runs of digits. A secret in an unknown format passes. A company can add its own under `scan.patterns`.
- It does not find names of people. HR data, statistics per person, signed documents and recordings with names are left to the agent when it reads a source, and that check is not deterministic.
- It does not read the contents of binary files such as PDFs and images. They are listed as not read and do not change the exit code. Office and design files are recognised by extension only.
- The scan before a commit is a rule given to the agent at session start, and no git hook runs it. The workflow in the department's repository runs on GitHub on push and pull request, so it reports a finding after the content has reached the remote.

## Tests

You need bash, git and Python 3.9 or newer. The full run takes several minutes. `claude plugin validate` is included when `claude` is on the path.

```
bash tests/run-all.sh
bash tests/run-all.sh gates      # only tests whose path contains "gates"
bash tests/run-all.sh --verbose  # print each test's output
```

`tests/gates/test-gate-sources.sh` covers outside sources on a gate: the list, the recorded checks, approval, status and the Bash guard's rule for a mark.

`tests/notify/test-notify.sh` covers the Slack message: which gates started to wait in a push, the morning list, the templates and their cleaning, the secret, the copies CI uses and the workflow. It never touches the network.

`.github/workflows/tests.yml` runs the same suites on `windows-latest` and `macos-latest`.

## License

MIT. See [LICENSE](LICENSE).
