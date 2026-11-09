#!/usr/bin/env bash
# run-all.sh - run every tests/**/test-*.sh and report PASS/FAIL per file.
#
# Usage: tests/run-all.sh [--verbose] [filter]
#   filter  only run test files whose path contains this string (for example "hooks")
#   --verbose  print each test's output, not only failures
#
# Each test runs in its own subshell with KIT_ROOT and CLAUDE_PROJECT_DIR set to the repo root.
# Exit: 0 when every test passed, 1 when any failed, 2 usage error.

set -u
VERBOSE=0; FILTER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --verbose|-v) VERBOSE=1; shift;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    -*) echo "run-all: unknown option '$1'" >&2; exit 2;;
    *) FILTER="$1"; shift;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PASS=0; FAIL=0; FAILED=""
LOGDIR="$(mktemp -d "${TMPDIR:-/tmp}/kit-tests.XXXXXX")"
trap 'rm -rf "$LOGDIR"' EXIT

TESTS="$(find "$HERE" -type f -name 'test-*.sh' | sort)"
[ -n "$TESTS" ] || { echo "run-all: no tests found under $HERE"; exit 0; }

while IFS= read -r t; do
  rel="${t#"$ROOT"/}"
  [ -n "$FILTER" ] && case "$rel" in *"$FILTER"*) ;; *) continue;; esac
  log="$LOGDIR/$(printf '%s' "$rel" | tr '/' '_').log"
  ( cd "$ROOT" && KIT_ROOT="$ROOT" CLAUDE_PROJECT_DIR="$ROOT" bash "$t" ) > "$log" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    PASS=$((PASS + 1)); echo "PASS  $rel"
    [ "$VERBOSE" = 1 ] && sed 's/^/      /' "$log"
  else
    FAIL=$((FAIL + 1)); FAILED="$FAILED $rel"; echo "FAIL  $rel (exit $rc)"
    sed 's/^/      /' "$log" | tail -n 40
  fi
done <<< "$TESTS"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || { echo "failed:$FAILED"; exit 1; }
exit 0
