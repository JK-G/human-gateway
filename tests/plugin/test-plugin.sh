#!/usr/bin/env bash
# test-plugin.sh - the plugin's shape: no leftovers from the kit, session-start, today-data, doctor.
# Self-contained. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TMP="$(temp_dir hg-plugin)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }

# --- leftovers from the kit -----------------------------------------------------------
stale='\.claude/(tools|adapters|routines|commands|agents/|rules/boundaries)|kit\.conf|\bjq\b|/(wiki-lint|wiki-dedup|capture-task|decision-log|doc-task|teachme|run-routine)\b|scripts/(init|doctor)\.sh|heartbeat|playbook-executor'
out="$(grep -rnE "$stale" "$PLUGIN/skills" "$PLUGIN/agents" "$PLUGIN/rules" "$PLUGIN/templates" 2>/dev/null)"
[ -z "$out" ] && ok "no references to the kit's old paths or dropped commands" || bad "no references to the kit's old paths or dropped commands" "$out"
out="$(grep -rnE '(^|[^/])/(today|dayend|ingest|import-source|wiki-query)\b' "$PLUGIN/skills" "$PLUGIN/agents" "$PLUGIN/templates" 2>/dev/null | grep -vE 'vault/|raw/')"
[ -z "$out" ] && ok "commands carry the hg: prefix" || bad "commands carry the hg: prefix" "$out"
for s in today dayend ingest import-source wiki-query doctor setup; do
  [ -f "$PLUGIN/skills/$s/SKILL.md" ] && grep -q "^name: $s$" "$PLUGIN/skills/$s/SKILL.md" && ok "skill $s" || bad "skill $s"
done

if command -v claude >/dev/null 2>&1; then
  out="$(claude plugin validate "$REPO_ROOT" 2>&1)"; [ $? -eq 0 ] && ok "marketplace validates" || bad "marketplace validates" "$out"
  out="$(claude plugin validate "$PLUGIN" 2>&1)"; [ $? -eq 0 ] && ok "plugin validates" || bad "plugin validates" "$out"
else
  echo "n/a  - claude is not installed here, plugin validation not run"
fi

# --- a small department workspace ------------------------------------------------------
W="$TMP/dept"
mkdir -p "$W/.claude" "$W/vault/daily" "$W/vault/inbox" "$W/vault/journal" "$W/vault/wiki" "$W/vault/raw"
cp "$REPO_ROOT/tests/fixtures/workspace/vault/schema.md" "$W/vault/schema.md"
cat > "$W/.claude/hg.json" <<'CONF'
{ "schemaVersion": 1, "projects": ["acme-notes"], "timezone": "UTC", "language": { "content": "pl" },
  "neverInGit": { "extra": ["pricing drafts"] } }
CONF
printf '# old\n- [ ] carry me\n- [x] done\n' > "$W/vault/daily/2026-01-30.md"
printf 'an idea\n' > "$W/vault/inbox/idea.md"
printf '{"ts":"2026-01-31T10:00:00Z","op":"ingest","agent":"t","project":"cross","inputs":[],"outputs":[],"status":"applied","note":""}\n{"ts":"2026-01-31T11:00:00Z","op":"conflict","agent":"t","project":"cross","inputs":[],"outputs":[],"status":"queued","note":"two prices"}\n' > "$W/vault/log.jsonl"

out="$(CLAUDE_PROJECT_DIR="$W" hg session-start)"
printf '%s' "$out" | grep -q 'Human Gateway department workspace' && ok "session-start prints the rules" || bad "session-start prints the rules" "$out"
printf '%s' "$out" | grep -q 'pricing drafts' && ok "session-start adds the company's extra terms" || bad "session-start adds the company's extra terms" "$out"
printf '%s' "$out" | grep -q 'schemaVersion' && bad "no schema warning when versions match" "$out" || ok "no schema warning when versions match"

# --- routing: people say what they want, the model starts the skill or names the command ----------
route="$(printf '%s\n' "$out" | grep 'any language')"
[ "$(printf '%s\n' "$out" | grep -c 'any language')" = 1 ] && ok "routing is one line" || bad "routing is one line" "$out"
for needle in hg:today hg:dayend hg:wiki-query hg:doctor 'put it in intake/' 'intake/links.md' 'type /hg:init' 'type /hg:gate' 'You cannot start /hg:init or /hg:gate'; do
  case "$route" in *"$needle"*) ok "routing names: $needle";; *) bad "routing names: $needle" "$route";; esac
done
case "$route" in *import-source*|*hg:ingest*) bad "routing sends no file straight to import or ingest" "$route";; *) ok "routing sends no file straight to import or ingest";; esac
for s in today dayend wiki-query doctor; do
  grep -q '^disable-model-invocation: true' "$PLUGIN/skills/$s/SKILL.md" && bad "the model can start $s" || ok "the model can start $s"
done
for s in init gate; do
  grep -q '^disable-model-invocation: true' "$PLUGIN/skills/$s/SKILL.md" && ok "only a person can start $s" || bad "only a person can start $s"
done

# --- a question routed to the wiki never changes shared pages without a yes -----------------------
WQ="$PLUGIN/skills/wiki-query/SKILL.md"
ask="$(grep -n 'ask first with AskUserQuestion' "$WQ" | cut -d: -f1)"
send="$(grep -n 'dispatch the `hg:wiki-librarian`' "$WQ" | cut -d: -f1)"
[ -n "$ask" ] && [ -n "$send" ] && [ "$ask" -lt "$send" ] && ok "/hg:wiki-query asks before it dispatches the librarian" || bad "/hg:wiki-query asks before it dispatches the librarian" "ask=$ask send=$send"
grep -qF 'Without a yes, nothing is filed' "$WQ" && ok "/hg:wiki-query files nothing without a yes" || bad "/hg:wiki-query files nothing without a yes"
for guide in QUICKSTART.md QUICKSTART-druga-osoba.md; do
  grep -qF 'zapyta, czy zapisać ją w wiki' "$REPO_ROOT/$guide" && ok "$guide says an answer is saved only on a yes" || bad "$guide says an answer is saved only on a yes"
done

sed -i.bak 's/"schemaVersion": 1/"schemaVersion": 99/' "$W/.claude/hg.json"
out="$(CLAUDE_PROJECT_DIR="$W" hg session-start)"
printf '%s' "$out" | grep -q 'schemaVersion 99' && ok "session-start warns on a schema mismatch" || bad "session-start warns on a schema mismatch" "$out"
CLAUDE_PROJECT_DIR="$W" hg doctor >/dev/null; [ $? -eq 1 ] && ok "doctor fails on a schema mismatch" || bad "doctor fails on a schema mismatch"
mv "$W/.claude/hg.json.bak" "$W/.claude/hg.json"

P="$TMP/plain"; mkdir -p "$P"
out="$(CLAUDE_PROJECT_DIR="$P" hg session-start)"
[ -z "$out" ] && ok "session-start is silent outside a department repo" || bad "session-start is silent outside a department repo" "$out"

data="$(CLAUDE_PROJECT_DIR="$W" KIT_TODAY=2026-02-02 hg today-data)"
check() { printf '%s' "$data" | jtrue "$1" && ok "$2" || bad "$2" "$data"; }
check 'd["date"]=="2026-02-02" and d["weekday_number"]==1 and d["is_workday"]' "today-data reads the pinned date"
check 'd["next_workday"]=="2026-02-03"' "today-data finds the next workday"
check 'd["last_note"]["unchecked"]==["- [ ] carry me"]' "today-data carries over open items"
check 'd["log"]["counts_7d"]["ingest"]==1 and d["log"]["conflicts_queued"]==["two prices"]' "today-data summarizes the log"
check 'd["inbox_recent"][0]["first_line"]=="an idea"' "today-data lists recent inbox files"
data="$(CLAUDE_PROJECT_DIR="$W" KIT_TODAY=2026-02-06 hg today-data)"
check 'd["next_workday"]=="2026-02-09"' "Friday's next workday is Monday"

printf '%s\n' 'vault/daily/' 'intake/' 'DASHBOARD.md' '.gateway/' '.claude/state/' '.claude/settings.local.json' > "$W/.gitignore"
out="$(CLAUDE_PROJECT_DIR="$W" hg doctor)"; rc=$?
if printf '%s' "$out" | grep -q '^ERROR.*\(git\|gh\)'; then
  echo "n/a  - doctor pass not asserted: git or gh missing on this machine"
else
  [ $rc -eq 0 ] && ok "doctor passes on a good workspace" || bad "doctor passes on a good workspace (rc=$rc)" "$out"
fi

# --- called by an absolute /d/x path with Git Bash's rewriting already off -------------------------
abs_tool="$HG_TOOL"
command -v cygpath >/dev/null 2>&1 && abs_tool="$(cygpath -u "$HG_TOOL")"
out="$(CLAUDE_PROJECT_DIR="$W" MSYS2_ARG_CONV_EXCL='*' bash "$abs_tool" doctor 2>&1)"
printf '%s' "$out" | grep -q $'^OK\tconfig\t' && ok "doctor through an absolute path" || bad "doctor through an absolute path" "$out"
data="$(CLAUDE_PROJECT_DIR="$W" MSYS2_ARG_CONV_EXCL='*' KIT_TODAY=2026-02-02 bash "$abs_tool" today-data 2>&1)"
check 'd["date"]=="2026-02-02"' "today-data through an absolute path"
n="$(grep -c 'pwd -W' "$HG_TOOL")"
[ "$n" = 1 ] && ok "the native path is computed in one place" || bad "the native path is computed in one place" "$n"
grep -B1 'pwd -W' "$HG_TOOL" | grep -qF 'if [ "$is_hook" = 0 ]; then' && ok "hooks skip that subshell" || bad "hooks skip that subshell"

# --- /hg:init is on the map ------------------------------------------------------------------------
grep -qF '| `/hg:init` |' "$PLUGIN/templates/workspace/CLAUDE.md" && ok "the workspace command table lists /hg:init" || bad "the workspace command table lists /hg:init"
grep -qF '`/hg:init`' "$PLUGIN/skills/setup/SKILL.md" && ok "setup's next steps name /hg:init" || bad "setup's next steps name /hg:init"

rm "$W/.claude/hg.json"
CLAUDE_PROJECT_DIR="$W" hg doctor >/dev/null; [ $? -eq 1 ] && ok "doctor fails without hg.json" || bad "doctor fails without hg.json"

echo "plugin: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
