# Cross-project digests

Landing zone for output that does not belong to a single project: agents created with
`scripts/new-agent.sh <name> --project cross` push to `vault/digests/<name>/`, and the
`weekly-intel-digest` routine writes cross-project reports to `vault/digests/intel/`.

The contract is identical to a project's digests folder, see
[projects/_template/digests/README.md](../projects/_template/digests/README.md):

- Agents overwrite only their own `vault/digests/<agent>/` files; humans do not hand-edit them.
- PII-free, aggregated content only; every file starts with the `> AUTO-SYNC: ...` banner line.
- Transient feedstock: the durable signal is extracted into wiki pages (via `/ingest` or change
  plans), after which `wiki-heartbeat` garbage-collects old reports.
- HITL proposals use the numbered `P-<n>` convention and are applied only on human approval.
- Read by `task-extractor` (when listed in a playbook's `approved_sources`) and by `/today`.
