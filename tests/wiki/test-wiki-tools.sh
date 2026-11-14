#!/usr/bin/env bash
# test-wiki-tools.sh - tests for the wiki machinery: registry, canonicalize, validate-frontmatter,
# validate-plan and the index generator.
#
# Copies the fixture vault (fictional Acme Notes) into a temp dir and runs every tool there with
# --root. Self-contained; exits nonzero when any assertion fails.
set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
FIX="$REPO_ROOT/tests/wiki/fixtures"
TMP="$(temp_dir hg-wiki)"
trap 'rm -rf "$TMP"' EXIT
export KIT_TODAY="2026-02-01"
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf 'ok    %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf 'FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/      /'; }
sha1_of() { $PY -c 'import hashlib,sys; print(hashlib.sha1(open(sys.argv[1],"rb").read()).hexdigest())' "$1" | tr -d '\r'; }

# --- sandbox --------------------------------------------------------------------
mkdir -p "$TMP/.claude"
cp -R "$REPO_ROOT/tests/fixtures/workspace/vault" "$TMP/vault"
cat > "$TMP/.claude/hg.json" <<'CONF'
{ "schemaVersion": 1, "projects": ["acme-notes"], "timezone": "UTC" }
CONF
rm -f "$TMP"/vault/log.jsonl

# --- registry and config ----------------------------------------------------------
types="$(hg registry --root "$TMP" types 2>&1)"
if printf '%s\n' "$types" | grep -qx concept && printf '%s\n' "$types" | grep -qx memory; then
  ok "registry lists types"
else bad "registry lists types" "$types"; fi
projs="$(hg registry --root "$TMP" projects --with-cross)"
printf '%s\n' "$projs" | grep -qx cross && ok "projects --with-cross" || bad "projects --with-cross" "$projs"
printf '%s\n' "$projs" | grep -qx acme-notes && ok "projects come from hg.json" || bad "projects come from hg.json" "$projs"
[ "$(hg registry --root "$TMP" conf VAULT_DIR)" = "vault" ] && ok "conf value has no stray CR" || bad "conf value has no stray CR"
out="$(hg registry --root "$TMP" conf --sh)"
printf '%s' "$out" | grep -q "^PROJECTS=acme-notes$" && ok "conf --sh prints shell assignments" || bad "conf --sh prints shell assignments" "$out"
printf '{ "schemaVersion": 1, "projectName": "$(touch pwned); `touch pwned2`" }' > "$TMP/evil.json"
mkdir -p "$TMP/evil/.claude"; cp "$TMP/evil.json" "$TMP/evil/.claude/hg.json"
( cd "$TMP/evil" && eval "$(hg registry --root "$TMP/evil" conf --sh)" )
[ ! -e "$TMP/evil/pwned" ] && [ ! -e "$TMP/evil/pwned2" ] && ok "config values are never executed" || bad "config values are never executed"
rm -rf "$TMP/evil" "$TMP/evil.json"
echo '{ broken' > "$TMP/broken.json"; mkdir -p "$TMP/b/.claude"; cp "$TMP/broken.json" "$TMP/b/.claude/hg.json"
hg registry --root "$TMP/b" conf VAULT_DIR >/dev/null 2>&1; [ $? -eq 1 ] && ok "broken hg.json is an error for the CLI" || bad "broken hg.json is an error for the CLI"
rm -rf "$TMP/b" "$TMP/broken.json"

# --- validate-frontmatter ---------------------------------------------------------------
out="$(hg validate-frontmatter --root "$TMP" 2>&1)"; rc=$?
if [ $rc -eq 0 ] && ! printf '%s\n' "$out" | grep -q '^ERROR'; then
  ok "shipped pages validate clean"
else bad "shipped pages validate clean (rc=$rc)" "$out"; fi

cp "$FIX/bad-page.md" "$TMP/vault/wiki/concepts/bad-page.md"
out="$(hg validate-frontmatter --root "$TMP" "$TMP/vault/wiki/concepts/bad-page.md" 2>&1)"; rc=$?
if [ $rc -eq 1 ] && printf '%s' "$out" | grep -q "missing_key: 'temporal'" \
   && printf '%s' "$out" | grep -q "missing_key: 'sources'" \
   && printf '%s' "$out" | grep -q "bad_enum: status='maybe'" \
   && printf '%s' "$out" | grep -q "missing_section: '## Definition'"; then
  ok "bad-page fails with ERROR findings"
else bad "bad-page fails with ERROR findings (rc=$rc)" "$out"; fi
printf '%s\n' "$out" | awk -F'\t' 'NF!=3 || $1 !~ /^(ERROR|WARN|INFO)$/ {exit 1}' \
  && ok "findings use LEVEL<TAB>path<TAB>message" || bad "findings use LEVEL<TAB>path<TAB>message" "$out"
rm -f "$TMP/vault/wiki/concepts/bad-page.md"

# A page filed back by /hg:wiki-query (log op file_back) must carry derived_from.
mkdir -p "$TMP/vault/wiki/research"
cat > "$TMP/vault/wiki/research/filed-answer.md" <<'EOF'
---
type: research
project: cross
temporal: living
status: active
last_verified: 2026-01-30
sources: []
aliases: []
summary: "A filed answer without provenance."
---
## Finding
x
## Evidence
y
## Q&A
### Q: what is x? (2026-01-30)
An answer with no citation line.
EOF
printf '{"ts":"2026-01-30T10:00:00Z","op":"file_back","agent":"wiki-librarian","project":"cross","inputs":[],"outputs":["wiki/research/filed-answer.md"],"status":"applied","note":""}\n' > "$TMP/vault/log.jsonl"
out="$(hg validate-frontmatter --root "$TMP" "$TMP/vault/wiki/research/filed-answer.md" 2>&1)"; rc=$?
n="$(printf '%s\n' "$out" | grep -c 'uncited_query_output')"
[ $rc -eq 1 ] && [ "$n" -eq 2 ] && ok "uncited query output rejected (page + Q&A entry)" \
  || bad "uncited query output rejected (rc=$rc, hits=$n)" "$out"
rm -f "$TMP/vault/wiki/research/filed-answer.md" "$TMP/vault/log.jsonl"

# --- validate-plan -----------------------------------------------------------------
SRC="vault/raw/acme-notes/meetings/2026-01-15-example-kickoff.md"
H="$(sha1_of "$TMP/$SRC")"
REF="$(cd "$TMP" && CLAUDE_PROJECT_DIR="$TMP" hg raw-ref "$SRC")"
case "$REF" in src:meetings:2026-01-15:????????) ok "the fixture source has a reference";; *) bad "the fixture source has a reference" "$REF";; esac
jedit "$FIX/valid-plan.json" "$TMP/plan.json" "d['source_hash']='sha1:$H'; d['edits'][0]['values']=['$REF']; d['new_pages'][0]['frontmatter']['sources']=['$REF']"
out="$(hg validate-plan --root "$TMP" --check-pages "$TMP/plan.json" 2>&1)"; rc=$?
[ $rc -eq 0 ] && [ ! -f "$TMP/plan.errors.json" ] && ok "valid plan passes" || bad "valid plan passes (rc=$rc)" "$out"
grep -rq "$REF" "$TMP/vault/wiki" && ok "the fixture pages cite the fixture's reference" || bad "the fixture pages cite the fixture's reference"

# --- raw files stay on one machine: plans and pages cite them by reference ------------------------
plan_rule() {  # plan_rule <label> <rule> <python statements on d>
  jedit "$TMP/plan.json" "$TMP/rule.json" "$3"
  local out rc; out="$(hg validate-plan --root "$TMP" "$TMP/rule.json" 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && printf '%s' "$out" | grep -q "\[$2\]"; } && ok "$1" || bad "$1 (rc=$rc)" "$out"
}
RAWP="raw/acme-notes/meetings/2026-01-15-example-kickoff.md"
plan_rule "a plan whose page names a raw path is rejected (page.private_path): in body" page.private_path \
  "d['new_pages'][0]['body']+='\nOriginal: \`$RAWP\`.\n'"
plan_rule "a plan whose page names a raw path is rejected (page.private_path): in content" page.private_path \
  "d['edits'].append(dict(op='append',page='vault/wiki/concepts/example--acme-notes-offline-sync.md',page_hash_expected='sha1:'+'0'*40,section='Related',content='- from vault/$RAWP',rationale='r',confidence=0.5))"
plan_rule "a plan whose page names a raw path is rejected (page.private_path): in sources" page.private_path \
  "d['new_pages'][0]['frontmatter']['sources']=['$RAWP']"
plan_rule "a plan whose page names an intake file is rejected" page.private_path \
  "d['new_pages'][0]['body']+='\nSee intake/cennik.xlsx for the numbers.\n'"
plan_rule "a raw path written with backslashes is rejected too" page.private_path \
  "d['new_pages'][0]['body']+='\nOriginal: '+chr(92).join(['vault','raw','acme-notes','meetings','2026-01-15-example-kickoff.md'])+'\n'"
plan_rule "a plan whose new page does not cite the source's reference is rejected (page.source_ref)" page.source_ref \
  "d['new_pages'][0]['frontmatter']['sources']=['wiki/concepts/example--acme-notes-offline-sync.md']"
jedit "$TMP/plan.json" "$TMP/rule.json" "d['new_pages'][0]['frontmatter']['sources']=[]"
out="$(hg validate-plan --root "$TMP" "$TMP/rule.json" 2>&1)"
printf '%s' "$out" | grep -qF "add $REF to sources" && ok "the message gives the reference" || bad "the message gives the reference" "$out"
jedit "$TMP/plan.json" "$TMP/rule.json" "d['edits'][0]['values']=['$REF','wiki/decisions/example--2026-01-20-acme-notes-local-first.md','journal/2026-01-15.md']"
out="$(hg validate-plan --root "$TMP" "$TMP/rule.json" 2>&1)"; rc=$?
plan_rule "add_source_ref rejects free text (page.source_entry)" page.source_entry "d['edits'][0]['values']=['the kickoff meeting']"
[ $rc -eq 0 ] && ok "add_source_ref takes a reference and a wiki path, and rejects free text (page.source_entry)" || bad "add_source_ref takes a reference and a wiki path, and rejects free text (page.source_entry) (rc=$rc)" "$out"

page_case() {  # page_case <name> <sources line> [extra frontmatter line]: writes a concept page, prints validate-frontmatter
  printf -- '---\ntype: concept\nproject: acme-notes\ntemporal: living\nstatus: active\nlast_verified: 2026-01-30\nsources: %s\naliases: []\nsummary: "A page."\n%b---\n## Definition\nx\n## Related\ny\n' "$2" "${3:-}" > "$TMP/vault/wiki/concepts/$1.md"
  hg validate-frontmatter --root "$TMP" "$TMP/vault/wiki/concepts/$1.md" 2>&1
}
out="$(page_case acme-notes--raw-cited "[\"$RAWP\"]")"; rc=$?
{ [ $rc -eq 1 ] && printf '%s' "$out" | grep -q "bad_source_entry: 'sources'"; } && ok "a page with a raw path in sources fails validate-frontmatter (bad_source_entry)" || bad "a page with a raw path in sources fails validate-frontmatter (bad_source_entry) (rc=$rc)" "$out"
printf '%s' "$out" | grep -q 'example-kickoff' && bad "the finding does not print the value" "$out" || ok "the finding does not print the value"
out="$(page_case acme-notes--well-cited "[\"$REF\", \"wiki/decisions/example--2026-01-20-acme-notes-local-first.md\", \"journal/2026-01-15.md\"]")"; rc=$?
printf '%s' "$out" | grep -q 'bad_source_entry' && bad "a page with a reference, a wiki path and a journal day passes" "$out" || ok "a page with a reference, a wiki path and a journal day passes"
printf '%s' "$out" | grep -q "WARN.*dead_source: 'journal/2026-01-15.md' is not in this repository" && ok "a wiki path that does not exist is a warning (dead_source)" || bad "a wiki path that does not exist is a warning (dead_source)" "$out"
{ [ $rc -eq 0 ] && ! printf '%s' "$out" | grep -q "dead_source: 'wiki/decisions"; } && ok "an existing wiki page is no dead source, and a warning does not fail" || bad "an existing wiki page is no dead source, and a warning does not fail (rc=$rc)" "$out"
out="$(page_case acme-notes--dead-wiki "[\"wiki/concepts/acme-notes--gone.md\"]")"; rc=$?
{ [ $rc -eq 0 ] && printf '%s' "$out" | grep -q "^WARN.*dead_source: 'wiki/concepts/acme-notes--gone.md'"; } && ok "a missing wiki page is a dead source too" || bad "a missing wiki page is a dead source too (rc=$rc)" "$out"
tok="tok""en=abcd1234efgh5678ijkl"
out="$(page_case acme-notes--bad-url "[\"$REF\"]" "source_url: \"https://app.clickup.example/t/86abc?$tok\"\n")"; rc=$?
{ [ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'bad_source_url'; } && ok "source_url must be one clean link (bad_source_url): a link with token= fails" || bad "source_url must be one clean link (bad_source_url): a link with token= fails (rc=$rc)" "$out"
printf '%s' "$out" | grep -q 'abcd1234' && bad "the link's token is not printed" "$out" || ok "the link's token is not printed"
out="$(page_case acme-notes--two-urls "[\"$REF\"]" "source_url: \"https://a.example/x https://b.example/y\"\n")"; rc=$?
[ $rc -eq 1 ] && ok "source_url with two links fails" || bad "source_url with two links fails (rc=$rc)" "$out"
mkdir -p "$TMP/vault/wiki/sources"
printf -- '---\ntype: source-summary\nproject: acme-notes\ntemporal: snapshot\nstatus: active\nlast_verified: 2026-01-30\nsource_raw: "%s"\nsource_url: "https://app.clickup.example/t/86abc"\nextraction: extracted\nsources: ["%s"]\naliases: []\nsummary: "A task summary."\n---\n# Summary\n' "$REF" "$REF" > "$TMP/vault/wiki/sources/acme-notes--2026-01-30-task.md"
out="$(hg validate-frontmatter --root "$TMP" "$TMP/vault/wiki/sources/acme-notes--2026-01-30-task.md" 2>&1)"; rc=$?
{ [ $rc -eq 0 ] && ! printf '%s' "$out" | grep -qE 'unknown_key|bad_source'; } && ok "a link summary is a source-summary page with source_url" || bad "a link summary is a source-summary page with source_url (rc=$rc)" "$out"
rm -f "$TMP"/vault/wiki/concepts/acme-notes--*.md "$TMP/vault/wiki/sources/acme-notes--2026-01-30-task.md"

jedit "$TMP/plan.json" "$TMP/tampered.json" "d['source_hash']='sha1:'+'0'*40"
out="$(hg validate-plan --root "$TMP" "$TMP/tampered.json" 2>&1)"; rc=$?
if [ $rc -eq 1 ] && jtrue 'any(x["rule"]=="source_hash.mismatch" for x in d)' < "$TMP/tampered.errors.json"; then
  ok "tampered source_hash fails and writes errors.json"
else bad "tampered source_hash fails and writes errors.json (rc=$rc)" "$out"; fi

jedit "$TMP/plan.json" "$TMP/scope.json" "d['new_pages'][0].update(type='memory',page='vault/wiki/memory/acme-notes--prototype-offline-dropout.md'); d['new_pages'][0]['frontmatter']['type']='memory'"
out="$(hg validate-plan --root "$TMP" "$TMP/scope.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q rejected_ingest_scope \
  && ok "ingest map rejects a memory page from a meeting" || bad "ingest map rejects a memory page from a meeting (rc=$rc)" "$out"

jedit "$TMP/plan.json" "$TMP/cross.json" "d['target_project']='cross'"
out="$(hg validate-plan --root "$TMP" "$TMP/cross.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'project.write_guard' \
  && ok "cross plan may not write project pages" || bad "cross plan may not write project pages (rc=$rc)" "$out"

jedit "$TMP/plan.json" "$TMP/prd.json" "d['edits'][0]['page']='vault/projects/acme-notes/PRD.md'"
out="$(hg validate-plan --root "$TMP" "$TMP/prd.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'dedup.scope_guard' \
  && ok "PRD is never an edit target" || bad "PRD is never an edit target (rc=$rc)" "$out"

jedit "$TMP/plan.json" "$TMP/badop.json" "d['edits'][0]['op']='rewrite_everything'"
out="$(hg validate-plan --root "$TMP" "$TMP/badop.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'edits.op' && ok "unknown edit op is rejected" || bad "unknown edit op is rejected (rc=$rc)" "$out"
printf 'not json' > "$TMP/garbage.json"
out="$(hg validate-plan --root "$TMP" "$TMP/garbage.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q 'not a JSON object' && ok "garbage plan is rejected" || bad "garbage plan is rejected (rc=$rc)" "$out"

P="vault/wiki/concepts/example--acme-notes-offline-sync.md"
PH="$(hg canonicalize --hash "$TMP/$P")"
jedit "$TMP/plan.json" "$TMP/stale.json" "d['edits'].append(dict(op='append',page='$P',page_hash_expected='$PH',section='Related',content='- x',rationale='r',confidence=0.5))"
hg validate-plan --root "$TMP" --check-pages "$TMP/stale.json" >/dev/null 2>&1 \
  && ok "fresh page hash passes --check-pages" || bad "fresh page hash passes --check-pages"
cp "$TMP/$P" "$TMP/page.bak"
printf '\nedited after planning\n' >> "$TMP/$P"
out="$(hg validate-plan --root "$TMP" --check-pages "$TMP/stale.json" 2>&1)"; rc=$?
[ $rc -eq 1 ] && printf '%s' "$out" | grep -q stale_plan \
  && ok "edited page makes the plan stale" || bad "edited page makes the plan stale (rc=$rc)" "$out"
cp "$TMP/page.bak" "$TMP/$P"

# --- canonicalize ---------------------------------------------------------------------
printf -- '---\ntype: concept\naliases: [a, b]\nproject: cross\n---\n\nBody line  \n' > "$TMP/lf.md"
printf -- '---\r\nproject: cross\r\naliases:\r\n  - a\r\n  - b\r\ntype: concept\r\n---\r\nBody line\r\n\r\n' > "$TMP/crlf.md"
h1="$(hg canonicalize --hash "$TMP/lf.md")"; h2="$(hg canonicalize --hash "$TMP/crlf.md")"
[ -n "$h1" ] && [ "$h1" = "$h2" ] && ok "canonical hash ignores CRLF, key order, list style, trailing space" \
  || bad "canonical hash ignores CRLF, key order, list style, trailing space" "$h1 vs $h2"
printf 'changed\n' >> "$TMP/lf.md"
[ "$(hg canonicalize --hash "$TMP/lf.md")" != "$h1" ] && ok "canonical hash changes with content" \
  || bad "canonical hash changes with content"

printf 'plan body' > "$TMP/draft.json"
expected="$(sha1_of "$TMP/draft.json")"
[ "$(hg sha1 "$TMP/draft.json")" = "$expected" ] && ok "sha1 of a file's bytes" || bad "sha1 of a file's bytes"
named="$(hg plan-name "$TMP/draft.json")"
[ "$named" = "$TMP/${expected:0:12}.json" ] && [ -f "$named" ] && [ ! -e "$TMP/draft.json" ]   && ok "plan-name renames a plan after its hash" || bad "plan-name renames a plan after its hash" "$named"

# --- index ----------------------------------------------------------------------------
hg index --root "$TMP" >/dev/null 2>&1 || bad "index generator runs"
sum1="$(cat "$TMP"/vault/index*.md | cksum)"
out="$(hg index --root "$TMP" 2>&1)"
sum2="$(cat "$TMP"/vault/index*.md | cksum)"
[ "$sum1" = "$sum2" ] && printf '%s' "$out" | grep -q 'no changes' \
  && ok "index generator is idempotent" || bad "index generator is idempotent" "$out"
hg index --root "$TMP" --check >/dev/null 2>&1 \
  && ok "index --check passes when fresh" || bad "index --check passes when fresh"
router="$(grep '^- `raw/`' "$TMP/vault/index.md")"
case "$router" in *"never in git"*) ok "the index router no longer calls raw a shared layer";; *) bad "the index router no longer calls raw a shared layer" "$router";; esac
for t in $(hg registry --root "$TMP" types); do
  [ -f "$TMP/vault/index-$t.md" ] || bad "sub-index for $t written"
done
printf -- '---\ntype: concept\nproject: cross\ntemporal: living\nstatus: active\nlast_verified: 2026-01-30\nsources: []\naliases: []\nsummary: "New."\n---\n## Definition\nx\n## Related\ny\n' \
  > "$TMP/vault/wiki/concepts/cross--new-page.md"
hg index --root "$TMP" --check >/dev/null 2>&1 \
  && bad "index --check detects a new page" || ok "index --check detects a new page"

echo
echo "wiki tools: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
