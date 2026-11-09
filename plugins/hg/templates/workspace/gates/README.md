# gates/: approvals that reopen when their inputs change

Each gate has a readable summary, `<id>.md`, and a record of approvals, `<id>.lock.json`. Use `/hg:gate`.

A gate is a draft until someone approves it. It stays approved while its inputs stay the same. It
reopens when an input changes, disappears, or is added to or removed from the list, and when the
accountable person changes. Saving a text file with other line endings does not reopen it. `/hg:today`, `DASHBOARD.md` and the start of each session
show reopened gates.

- Only `hg-tool gate` writes here. The one exception: a person may add to the section for the next
  person in an editor. That section never changes the status.
- The status is computed from the current inputs and never stored.
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
- A change in ClickUp or Miro does not reopen a gate until someone refreshes the summary in this repo.
- A gate covers files in this repo. Inputs from another repo are not supported yet.
