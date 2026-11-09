#!/usr/bin/env bash
# test-routine-tools.sh - tests for the named lock the wiki librarian takes.
# Self-contained: works in a temp dir, never touches real state. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"

TMP="$(temp_dir hg-lock)"
trap 'rm -rf "$TMP"' EXIT
export ROUTINE_LOCK_DIR="$TMP/locks"
unset CLAUDE_PROJECT_DIR

PASS=0; FAIL=0
ok()   { PASS=$((PASS + 1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL + 1)); echo "FAIL - $1"; }
check() { if [ "$1" -eq "$2" ]; then ok "$3"; else bad "$3 (expected exit $2, got $1)"; fi; }

hg lock acquire demo >/dev/null; check $? 0 "first acquire succeeds"
hg lock acquire demo >/dev/null; check $? 1 "second acquire fails while held"
hg lock status demo >/dev/null; check $? 1 "status reports held"
hg lock release demo >/dev/null; check $? 0 "release succeeds"
hg lock status demo >/dev/null; check $? 0 "status reports free after release"
hg lock acquire demo >/dev/null; check $? 0 "acquire works again after release"
hg lock release demo >/dev/null
hg lock acquire >/dev/null 2>&1; check $? 2 "missing name is a usage error"

# Craft a stale lock: started long ago, TTL 1 minute, dead pid on this host.
make_stale() {
  mkdir -p "$ROUTINE_LOCK_DIR/$1.lock"
  cat > "$ROUTINE_LOCK_DIR/$1.lock/owner.json" <<EOF
{
  "pid": 999999,
  "host": "$(hostname 2>/dev/null || uname -n)",
  "session": "test",
  "started_at": "2000-01-01T00:00:00Z",
  "started_epoch": 946684800,
  "ttl_min": 1
}
EOF
}
make_stale old
hg lock status old >/dev/null; check $? 3 "status reports stale lock"
hg lock acquire old --no-steal >/dev/null 2>&1; check $? 1 "--no-steal keeps a stale lock"
[ -f "$ROUTINE_LOCK_DIR/old.lock/owner.json" ] && grep -q '"pid": 999999' "$ROUTINE_LOCK_DIR/old.lock/owner.json" \
  && ok "stale owner untouched with --no-steal" || bad "stale owner untouched with --no-steal"
hg lock acquire old >/dev/null 2>&1; check $? 0 "stale lock is stolen without --no-steal"
grep -q '"pid": 999999' "$ROUTINE_LOCK_DIR/old.lock/owner.json" && bad "owner rewritten after steal" || ok "owner rewritten after steal"
hg lock release old >/dev/null

# A lock within its TTL is never stolen, even with a dead pid.
hg lock acquire fresh --ttl-min 60 >/dev/null
hg lock acquire fresh >/dev/null 2>&1; check $? 1 "fresh lock is not stolen"
hg lock release fresh >/dev/null

echo "lock tool: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
