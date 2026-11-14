---
# kit:example <!-- kit:example -->
source_type: meeting
captured: 2026-01-15
origin: "meeting notes, summarized by the PM from a call recording"
project: acme-notes
---

> EXAMPLE (fictional, safe to delete: scripts/init.sh --remove-examples)

# Acme Notes v1 kickoff (2026-01-15)

Participants: PM, Eng lead, Designer. 45 minutes.

## Where we are

- PM: prototype round finished. Of 24 testers, 11 stopped within a week. The most common reason: "the app
  is useless on the train", the notes do not open without a connection.
- Designer: second complaint was silent overwrites. Two testers lost a paragraph after editing the same
  note on laptop and phone.
- Eng lead: the prototype is server-first. An offline cache would only cover recently opened notes.

## Storage approach

- Eng lead proposed local-first storage: the device copy is primary, the server only relays changes and
  keeps an encrypted backup. Costs about one extra quarter of engineering compared with a cache.
- PM: this also answers the privacy question from two pilot teams ("can you read our notes?").
- Agreed direction: local-first. PM to write it up as a decision after checking the web client impact.

## Offline sync (new concept for the team)

- Everyone can read and edit every note offline; sync runs when a connection returns.
- Conflict policy proposed by Eng lead: merge edits to different fields automatically; when the same
  paragraph is edited on two devices, keep both, with the earlier one as a flagged copy. No silent overwrite.
- Designer to sketch how a flagged copy looks in the note.

## Release cadence

- Until now we shipped monthly. PM: monthly is too slow for the sync work, bugs wait four weeks.
- New rule from today: a two-week release train. Hotfixes outside the train only with sign-off from the
  product owner (after the prototype hotfix that broke sync for all offline devices).

## Open question

- Shared team notebooks: do they need lock-while-editing instead of the conflict policy above? Eng lead
  thinks locks are fragile offline; Designer thinks teams expect them. Not decided, revisit at the next
  design review.

## Actions

- PM: decision write-up on local-first storage (due 2026-01-20).
- Designer: flagged-copy sketch.
- Eng lead: estimate for the browser local store.
