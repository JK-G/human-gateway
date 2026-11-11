# gates/: approvals that reopen when their inputs change

Each gate has a readable summary, `<id>.md`, and a record of approvals, `<id>.lock.json`. A gate that
names outside sources also has a folder `<id>.obs/` with one small file per recorded check of a source.
Use `/hg:gate`.

A gate is a draft until someone approves it. It stays approved while its inputs stay the same. It
reopens when an input changes, disappears, or is added to or removed from the list, and when the
accountable person changes. Saving a text file with other line endings does not reopen it.
`/hg:today`, `DASHBOARD.md` and the start of each session show reopened gates.

## Outside sources

A gate may also name outside sources: a link to a task, a board or a sheet, and optionally the field that
reports its last-modified time or version (its mark). The gate still needs at least one file input: what
is approved is the summary in this repo, and a source tells when that summary may be out of date.

- The tool never fetches a source. The mark is what the outside system reports, read by the person's own
  agent with a read tool the session already has, and recorded with `hg-tool gate observe`. A person can
  also state that a source is unchanged or changed; the session records their words.
- It reopens when a source is added or removed, when a source gets another link or field, and when a
  recorded check after the approval shows another mark or a person states it changed. It stays reopened
  until the next approval.
- It is **unchecked** when the approval holds but the newest recorded check of a source is more than N days
  old. N is `gates.sourceCheckDays` in `.claude/hg.json`, default 7.
- Observation files hold no person. Commit them with the rest, so others and the department's channel see a
  change.
- After a source got another link or field, the files of the old one stay in `<id>.obs/` and no longer count.

## Rules

- Only `hg-tool gate` writes here. The one exception: a person may add to the section for the next
  person in an editor. That section never changes the status.
- The status is computed from the current inputs, sources and recorded checks, and never stored.
- A gate names the person accountable for what is approved and says when an agent made the approval.
  That person answers for the content even if they did not read it.
- An approval made by an agent appears in that person's `/hg:today` for as long as it is the gate's
  latest approval, however old it is. Once a later approval replaces it, it stays listed for 14 days.
- Every input and the gate file itself must be committed before approval, because nobody else could
  check an uncommitted file. Commit the `.lock.json` afterwards so others see the approval.

## Known limits

- An agent can still run `hg-tool gate approve` directly, and `via` is what it declares about itself.
  The rule that an agent approves only when the accountable person asked is written in the command and
  is not enforced. Git history and `/hg:today` show afterwards what happened.
- `by` is the git identity set on the machine that ran the approval. Git does not verify it, so like
  `via` it is a declaration.
- The guards stop honest mistakes. They are not a wall: a script can still write here. Git history is
  the audit of who changed a record, and the guards are not.
- A gate covers files in this repo. Inputs from another repo are not supported yet.
- A mark is a statement, like `via`. The tool cannot check it, because it never fetches. An agent can
  record a wrong mark. The guards against that are the fixed field, the refusal of a date in the future,
  and git history. A wrong mark can reopen a gate and cannot close one.
- "A person stated it" is also only a declaration: a statement about a source is whatever a session ran
  with `--declare`, and nothing proves a person made it. It cannot close a reopened gate, but it does keep
  a gate from showing as unchecked.
- The mark is text from an outside system and passes through a shell line the agent writes. The tool
  takes only letters, digits, spaces and `. , : + / _ = -`, and the Bash guard blocks any other shape of
  that line. The guard is a hook: it fails open when it cannot parse its input and is off under
  `HG_GUARD_BYPASS=1`. A mark with other characters cannot be recorded, and that source is then watched
  by a person's statement.
- The baseline is the first recorded reading, not the state the summary was written from. A change
  between writing the summary and the first reading is never seen, for example when a source is added
  to a gate days later.
- When an approval rests on a person's statement, the first tool reading after it becomes the baseline.
  A change between the statement and that reading is not seen.
- A change in an outside system is noticed only when someone's session reads that source: in `/hg:today`
  or before an approval. If nobody runs a session, nobody notices; after N days the gate shows as
  unchecked.
- Every surface shows what is recorded in the clone it runs in. A check that was made and not committed
  and pushed is invisible to everyone else.
- A source with no reported time or version, or one no session can read, is watched only by a person's
  statement.
- A mark covers the whole item. A comment or a status change in a task moves it and reopens the gate even
  when the approved content did not change.
- A link with a key, a token or an address in it cannot be a source. Use a link without that part.
- Everyone has to update the plugin before the first gate gets a source. An older plugin ignores sources:
  it shows a gate as approved that the new one shows as reopened or unchecked, and an approval made with
  it records no sources, so the gate reopens at once for everyone else.
