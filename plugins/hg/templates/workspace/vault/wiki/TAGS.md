---
title: Tag vocabulary
type: index
project: cross
---

# Tag vocabulary (`tags:`)

The single source of truth for the optional `tags:` frontmatter on wiki pages. Tags are a discovery layer
(Obsidian tag pane, `tag:` search, Dataview). They never replace `type` or `project`.

- **Model:** one flat list per page, lowercase kebab-case (`^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$`).
- **How many:** 1-5 per page. Prefer one precise tag over three vague ones.
- **Soft-enforced:** a missing tag or a tag not listed here is a validator INFO, never a blocker.

## Starter vocabulary

- `pricing` - plans, prices, packaging, discounts, willingness to pay.
- `onboarding` - first-run experience, setup, time to first value, activation.
- `retention` - why users stay or leave: churn, renewals, habit, stickiness.
- `integrations` - connections to external systems: APIs, webhooks, imports, exports.
- `privacy` - personal data, consent, retention periods, compliance, security posture.
- `performance` - speed, reliability, scalability, resource cost.
- `ux` - interaction design, usability, accessibility, copy in the product.
- `analytics` - metrics, instrumentation, dashboards, experiments.
- `competition` - competitors, alternatives, positioning, market moves.
- `pipeline` - sales or lead pipeline: acquisition, qualification, conversion.

Replace or extend this list for your domain. Keep it lean (hard cap around 30): a sprawling vocabulary
defeats findability.

## Governance: adding a tag

1. **Reuse first.** Scan this file. Never coin a near-synonym of an existing tag (`speed` when
   `performance` exists, `gdpr` when `privacy` exists).
2. **Add only for a genuinely new area** that no tag covers. Add a line above in the same format
   (`` - `tag` - one-line definition. ``), in the same commit as the first page that uses it.
3. **Log it:** `hg-tool log --op lint --agent <you> --note "tag_added: <tag>"`.
4. **Retiring a tag:** remove it here, then fix pages in the same commit; `hg-tool validate-frontmatter`
   lists stragglers.
