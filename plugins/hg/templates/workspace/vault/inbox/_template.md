---
captured: YYYY-MM-DD
project: unknown        # a slug from projects in .claude/hg.json, "cross", or "unknown" (the ingest classifies it)
source: ""              # where this came from: meeting, chat, article URL, idea in the shower
---

# Title in a few words

What happened, what you learned, or what you think. Raw is fine: bullets, a pasted excerpt, a half idea.
If it contains a decision, say who decided (by role) and when.

<!--
How the inbox works:
- Copy this file to inbox/<anything>.md and fill it in. This _template.md itself is never ingested.
- /hg:ingest --inbox classifies each file, brings it into raw/<project>/... with /hg:import-source, ingests it and
  removes it from inbox/. You can also run /hg:ingest <file> yourself.
- Do not paste personal data of customers or other private individuals. Anonymize first.
-->
