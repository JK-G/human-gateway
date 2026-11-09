#!/usr/bin/env bash
# test-guards.sh - regression tests for the hooks and the event log:
# guard-bash, guard-write, journal, log, and the rule that hooks stay silent outside a department repo.
#
# Self-contained: builds a throwaway workspace and points the tools at it through CLAUDE_PROJECT_DIR.
# Exit 0 when every assertion holds, 1 otherwise. The hook contract under test: only exit 2 blocks.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"

T="$(temp_dir hg-guards)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/.claude" "$T/vault/raw/acme-notes" "$T/vault/wiki/concepts" "$T/vault/inbox" "$T/code/repo"
cat > "$T/.claude/hg.json" <<'CONF'
{
  "schemaVersion": 1,
  "paths": { "vault": "vault", "journal": "vault/journal", "log": "vault/log.jsonl" },
  "forbiddenWritePaths": ["code/", "vault/raw/", ".obsidian/", "agents/*/raw/"],
  "timezone": "UTC",
  "limits": { "logRotateBytes": 600 }
}
CONF
echo "original" > "$T/vault/raw/x.md"

FAILS=0; N=0
ok()   { N=$((N + 1)); }
bad()  { N=$((N + 1)); FAILS=$((FAILS + 1)); echo "FAIL: $*"; }

bash_payload() { printf '{"tool_name":"Bash","tool_input":{"command":%s},"cwd":%s}' "$(json_str "$1")" "$(json_str "$2")"; }
write_payload() { printf '{"tool_name":%s,"tool_input":{"file_path":%s,"notebook_path":%s},"cwd":%s}' "$(json_str "$1")" "$(json_str "$2")" "$(json_str "$2")" "$(json_str "$3")"; }

bash_case() {  # bash_case <expected-exit> <command> [cwd] [project-dir]
  local want="$1" cmd="$2" cwd="${3:-$T}" dir="${4:-$T}" got
  bash_payload "$cmd" "$cwd" | CLAUDE_PROJECT_DIR="$dir" HG_GUARD_BYPASS=0 hg guard-bash >/dev/null 2>&1
  got=$?
  [ "$got" = "$want" ] && ok || bad "guard-bash want $want got $got: $cmd"
}
write_case() {  # write_case <expected-exit> <tool> <path> [cwd] [project-dir]
  local want="$1" tool="$2" path="$3" cwd="${4:-$T}" dir="${5:-$T}" got
  write_payload "$tool" "$path" "$cwd" | CLAUDE_PROJECT_DIR="$dir" HG_GUARD_BYPASS=0 HG_ALLOW_JOURNAL_WRITE=0 hg guard-write >/dev/null 2>&1
  got=$?
  [ "$got" = "$want" ] && ok || bad "guard-write want $want got $got: $tool $path"
}

# --- guard-bash: must block (exit 2) ----------------------------------------------------
bash_case 2 'echo x > code/repo/a'
bash_case 2 'rm -rf vault/raw/acme-notes'
bash_case 2 'sed -i s/a/b/ vault/raw/x.md'
bash_case 2 "sed -i '' 's/a/b/' vault/raw/x.md"
bash_case 2 'cp a.md code/repo/'
bash_case 2 'git -C code/repo commit -m x'
bash_case 2 'cd code/repo && git commit -m x'
bash_case 2 'echo x | tee -a code/repo/a'
bash_case 2 'mv code/repo/a /tmp/'
bash_case 2 'find code -name "*.tmp" -delete'
bash_case 2 'bash -c "rm -rf code/repo"'
bash_case 2 "python3 -c \"open('code/repo/x','w').write('a')\""
bash_case 2 'echo x > "$CLAUDE_PROJECT_DIR/code/a"'
bash_case 2 'echo a > vault/raw/x.md'
bash_case 2 'touch vault/.obsidian/a'
bash_case 2 'echo > agents/foo/raw/a.txt'
bash_case 2 'cp README.md ./code/../code/z'
bash_case 2 "rm $T/code/../code/repo/x"
bash_case 2 'git checkout HEAD~1 -- vault/raw/x.md'
bash_case 2 'git checkout HEAD~1 vault/raw/x.md'
bash_case 2 'git restore --source=HEAD~1 vault/raw/x.md'
bash_case 2 'git restore code/repo/a'
bash_case 2 'git restore --staged --worktree vault/raw/x.md'
bash_case 2 "cat > code/x <<'EOF'
hello
EOF"

# --- guard-bash: must allow (exit 0) ----------------------------------------------------
bash_case 0 "find . -not -path '*/code/*' 2>/dev/null"
bash_case 0 'ls code/'
bash_case 0 'cat vault/raw/x.md'
bash_case 0 'git status'
bash_case 0 'grep -r foo code/ > /tmp/out.txt'
bash_case 0 'echo hi 2>&1'
bash_case 0 'echo hi >&2'
bash_case 0 'git -C code/repo log --oneline'
bash_case 0 'cd code/repo && git diff | head'
bash_case 0 'git mv vault/inbox/n.md vault/raw/acme-notes/n.md'
bash_case 0 'git checkout main'
bash_case 0 'git checkout -- vault/wiki/concepts/a.md'
bash_case 0 'git restore vault/wiki/concepts/a.md'
bash_case 0 'git restore --staged vault/raw/x.md'
bash_case 0 'mkdir -p vault/raw/acme-notes/meetings'
bash_case 0 'echo "a > code/b"'
bash_case 0 'cp code/repo/a.md vault/wiki/concepts/'
bash_case 0 "python3 -c \"print(open('code/repo/x').read())\""
bash_case 0 "cat <<EOF > /tmp/kit-guard-test
rm -rf code/repo
EOF"

# fail open on garbage, and the human bypass works
printf '{garbage' | CLAUDE_PROJECT_DIR="$T" hg guard-bash >/dev/null 2>&1 && ok || bad "guard-bash must fail open on garbage"
bash_payload 'rm -rf code/repo' "$T" | CLAUDE_PROJECT_DIR="$T" HG_GUARD_BYPASS=1 hg guard-bash >/dev/null 2>&1 && ok || bad "HG_GUARD_BYPASS=1 must allow"

# --- guard-write ------------------------------------------------------------------------
write_case 2 Write "$T/code/repo/a.py"
write_case 2 Edit "$T/code/repo/a.py"
write_case 2 MultiEdit "code/repo/a.py"
write_case 2 NotebookEdit "$T/code/repo/n.ipynb"
write_case 2 Edit "$T/vault/raw/x.md"
write_case 2 Write "$T/vault/raw/x.md"
write_case 2 Write "$T/vault/journal/2026-01-20.md"
write_case 2 Edit "$T/.claude/settings.local.json"
write_case 2 Write "$T/.claude/state/x"
write_case 2 Write "$T/vault/.obsidian/app.json"
write_case 2 Write "$T/vault/wiki/../raw/x.md"
write_case 2 Write "$T/.claude/state/locks/x"
write_case 2 Write "$T/.claude/state/plans/abc123.json"
write_case 0 Write "$T/.gateway/plans/abc123.json"
write_case 0 Write "$T/vault/wiki/concepts/new-page.md"
write_case 0 Edit "$T/vault/wiki/concepts/new-page.md"
write_case 0 Write "$T/vault/raw/acme-notes/new-source.md"
write_case 0 Write "$T/vault/journal/README.md"
write_case 0 Write "/tmp/elsewhere.md"
printf 'not json' | CLAUDE_PROJECT_DIR="$T" hg guard-write >/dev/null 2>&1 && ok || bad "guard-write must fail open on garbage"
write_payload Write "$T/vault/journal/2026-01-20.md" "$T" | CLAUDE_PROJECT_DIR="$T" HG_ALLOW_JOURNAL_WRITE=1 hg guard-write >/dev/null 2>&1 && ok || bad "HG_ALLOW_JOURNAL_WRITE=1 must allow"

# --- Windows path shapes: the case the original guards let through ----------------------
if command -v cygpath >/dev/null 2>&1; then
  W="$(cygpath -w "$T")"; D="${T:0:1}"; U="/${D,,}${T:2}"   # D:\x and /d/x
  UPPER="$(printf '%s' "$W" | tr '[:lower:]' '[:upper:]')"
  write_case 2 Edit "$W\\vault\\raw\\x.md" "$W" "$W"
  write_case 2 Edit "$T/vault/raw/x.md" "$W" "$W"
  write_case 2 Edit "$U/vault/raw/x.md" "$W" "$W"
  write_case 2 Edit "vault\\raw\\x.md" "$W" "$W"
  write_case 2 Edit "$UPPER\\VAULT\\RAW\\X.MD" "$W" "$W"
  write_case 0 Edit "$W\\vault\\wiki\\concepts\\ok.md" "$W" "$W"
  write_case 0 Write "$W\\vault\\raw\\acme-notes\\new.md" "$W" "$W"
  write_case 0 Edit "C:\\elsewhere\\x.md" "$W" "$W"
  bash_case 2 'rm vault/raw/x.md' "$W" "$W"
  bash_case 2 "rm $T/vault/raw/x.md" "$W" "$W"
  bash_case 2 "rm $U/vault/raw/x.md" "$W" "$W"
  bash_case 2 "rm \"$W\\vault\\raw\\x.md\"" "$W" "$W"
  bash_case 2 "cd $T/code/repo && git commit -m x" "$W" "$W"
  bash_case 2 'echo x > VAULT/RAW/x.md' "$W" "$W"
  bash_case 0 'cat vault/raw/x.md' "$W" "$W"
  bash_case 0 'echo x > vault/wiki/concepts/ok.md' "$W" "$W"
fi

# --- silent outside a department repo ---------------------------------------------------
P="$(temp_dir hg-plain)"
mkdir -p "$P/vault/raw"; echo x > "$P/vault/raw/x.md"
write_payload Edit "$P/vault/raw/x.md" "$P" | CLAUDE_PROJECT_DIR="$P" hg guard-write >/dev/null 2>&1 && ok || bad "guard-write must pass without hg.json"
bash_payload 'rm vault/raw/x.md' "$P" | CLAUDE_PROJECT_DIR="$P" hg guard-bash >/dev/null 2>&1 && ok || bad "guard-bash must pass without hg.json"
printf '{}' | CLAUDE_PROJECT_DIR="$P" hg journal >/dev/null 2>&1 && ok || bad "journal must pass without hg.json"
[ ! -e "$P/vault/journal" ] && ok || bad "journal must not write without hg.json"
rm -rf "$P"

# --- broken config keeps the default protection -----------------------------------------
B="$(temp_dir hg-broken)"
mkdir -p "$B/.claude" "$B/vault/raw"; echo x > "$B/vault/raw/x.md"; echo '{ not json' > "$B/.claude/hg.json"
write_payload Edit "$B/vault/raw/x.md" "$B" | CLAUDE_PROJECT_DIR="$B" hg guard-write >/dev/null 2>&1; [ $? = 2 ] && ok || bad "broken hg.json must keep protecting vault/raw"
rm -rf "$B"

# --- a config with no forbiddenWritePaths still protects gates/ --------------------------
G="$(temp_dir hg-default)"
mkdir -p "$G/.claude" "$G/gates"
printf '{ "schemaVersion": 1, "projects": [], "timezone": "UTC" }\n' > "$G/.claude/hg.json"
write_case 2 Write "$G/gates/a.lock.json" "$G" "$G"
write_case 2 Edit "gates/a.md" "$G" "$G"
bash_case 2 'printf x > gates/a.lock.json' "$G" "$G"
bash_case 2 'git checkout HEAD~1 -- gates/a.lock.json' "$G" "$G"
bash_case 0 "hg-tool gate approve a --via person --request 'ok gates/'" "$G" "$G"
rm -rf "$G"

# --- journal ----------------------------------------------------------------------------
J="$T/journal-repo"; mkdir -p "$J/.claude" "$J/vault"
cp "$T/.claude/hg.json" "$J/.claude/hg.json"
( cd "$J" && git init -q && echo a > vault/a.md )
printf 'garbage {{{' | CLAUDE_PROJECT_DIR="$J" hg journal; rc=$?
[ "$rc" = 0 ] && ok || bad "journal must exit 0 on garbage (got $rc)"
DAY="$(TZ=UTC date +%Y-%m-%d)"
JF="$J/vault/journal/$DAY.md"
[ -f "$JF" ] && ok || bad "journal did not create $JF"
grep -q "^# Journal $DAY" "$JF" 2>/dev/null && ok || bad "journal day header missing"
grep -q 'session unknown: [0-9]* paths: .*vault/a.md' "$JF" 2>/dev/null && ok || bad "journal line missing vault/a.md"
printf '{"session_id":"abcdef123456"}' | CLAUDE_PROJECT_DIR="$J" hg journal
grep -q 'session abcdef12:' "$JF" && ok || bad "journal session id not parsed"
[ "$(grep -c '^- ' "$JF")" = 2 ] && ok || bad "journal should have exactly 2 entries"
[ -f "$J/.claude/state/journal-last-run" ] && ok || bad "journal-last-run marker missing"
grep -q $'\r' "$JF" && bad "journal must use LF" || ok
CLAUDE_PROJECT_DIR="$T/does-not-exist" hg journal </dev/null; [ $? = 0 ] && ok || bad "journal must exit 0 with a bad root"

# --- event log --------------------------------------------------------------------------
CLAUDE_PROJECT_DIR="$T" hg log --op ingest --agent test --project acme-notes --inputs a,b --note 'quote " and \ ok /hg:today' && ok || bad "log basic"
tail -n 1 "$T/vault/log.jsonl" | jtrue 'd["op"]=="ingest" and d["project"]=="acme-notes" and len(d["inputs"])==2 and d["status"]=="applied"' && ok || bad "log line shape"
tail -n 1 "$T/vault/log.jsonl" | jtrue 'd["note"]==r"""quote " and \ ok /hg:today"""' && ok || bad "log note must reach the file unchanged"
CLAUDE_PROJECT_DIR="$T" hg log --op not_an_op --agent test 2>/dev/null; [ $? = 2 ] && ok || bad "unknown op must be rejected"
CLAUDE_PROJECT_DIR="$T" hg log --op not_an_op --agent test --allow-custom-op && ok || bad "--allow-custom-op"
CLAUDE_PROJECT_DIR="$T" hg log --op lint --agent test --status bogus 2>/dev/null; [ $? = 2 ] && ok || bad "bad status must be rejected"
for i in 1 2 3 4 5 6 7 8; do CLAUDE_PROJECT_DIR="$T" hg log --op lint --agent test --note "fill $i" || bad "log fill $i"; done
ls "$T/vault/log/"*.jsonl >/dev/null 2>&1 && ok || bad "log rotation did not create vault/log/YYYY.jsonl"
head -n 1 "$T/vault/log.jsonl" | jtrue 'd["op"]=="archive"' && ok || bad "fresh log must start with an archive line"
while IFS= read -r line; do printf '%s' "$line" | jtrue 'True' || bad "invalid JSON line in log"; done < "$T/vault/log.jsonl"
grep -q $'\r' "$T/vault/log.jsonl" && bad "log must use LF" || ok

echo "$((N - FAILS))/$N assertions passed"
[ "$FAILS" -eq 0 ]
