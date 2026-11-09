# Human Gateway

`hg` is a Claude Code plugin that gives a department a private git repository for its knowledge, with approvals that reopen when the files behind them change.

The repository holds only the department's content. Commands, hooks and tools come from the plugin. An approval is called a gate: it names the approved files and the person who answers for them. When one of those files changes, the gate shows as `reopened` in `/hg:today`, in `DASHBOARD.md` and at the start of each session.

To install it, follow [QUICKSTART.md](QUICKSTART.md) (in Polish). You need Claude Code, git and Python 3.9 or newer, plus Git Bash on Windows. The GitHub CLI is used only to sign in to GitHub. `/hg:setup` offers to install what is missing with winget or Homebrew.

| Command | What it does |
|---|---|
| `/hg:setup` | Checks the computer and creates the workspace. Never overwrites a file. `--update` updates the plugin. |
| `/hg:init` | Reads `intake/` and pasted links, writes a context map, asks at most 5 questions, drafts wiki pages and gates for approval. |
| `/hg:today`, `/hg:dayend` | Start and end of the day. |
| `/hg:import-source`, `/hg:ingest` | Bring a source into `vault/raw/` and turn it into wiki pages through a validated change plan. |
| `/hg:wiki-query` | Asks the wiki a question. |
| `/hg:gate` | Creates, lists and approves gates. |
| `/hg:doctor` | Checks the workspace. |

## What it does not do

- It does not replace the systems a department already uses. Spreadsheets, Word files, slides and design files stay where they are, and the repository keeps a summary and a link.
- It builds no connectors. `/hg:init` reads a link only if the session already has a read tool for that system. Otherwise the link is kept and the context map records the gap.
- It does not prove that a person read what was approved. An agent may approve on a person's account, and that person answers for the content. No hook blocks approvals and there is no separate bot identity.
- It does not commit or push by itself. The agent is told to commit only when the person asks.

## Known limits

Gates:

- An agent can still run `hg-tool gate approve` directly. The rule that it approves only when the accountable person asked is written in the command and is not enforced.
- `via` (person or agent) is what the approver declares. `by` is the git identity set on that machine, which git does not verify. Git history and `/hg:today` show afterwards what happened.
- A change in an outside system such as ClickUp or Miro does not reopen a gate until someone refreshes the summary in the repository.
- A gate covers files in one repository.
- The guards on `gates/` and `vault/raw/` stop honest mistakes. A script can still write there, they let a call through when its payload cannot be parsed, and `HG_GUARD_BYPASS=1` turns them off.

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

`.github/workflows/tests.yml` runs the same suites on `windows-latest` and `macos-latest`.

## License

MIT. See [LICENSE](LICENSE).
