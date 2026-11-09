#!/usr/bin/env bash
# routine-lock.sh - real mutual exclusion for routines and the wiki.
#
# Usage:
#   routine-lock.sh acquire <name> [--ttl-min N] [--no-steal]
#   routine-lock.sh release <name>
#   routine-lock.sh status  <name>
#
# Lock = directory .claude/state/locks/<name>.lock (mkdir is atomic) holding owner.json,
# written to a temp file first and renamed into place so readers never see a half file.
#
# Exit codes:
#   acquire: 0 acquired, 1 held by someone else, 2 usage
#   release: 0 released (or was not held), 2 usage
#   status : 0 free, 1 held (fresh), 3 held but stale, 2 usage
#
# Staleness: a lock is stale when it is older than its TTL AND, if it was taken on this host,
# its owner pid is no longer alive. A different host cannot check the pid, so age alone decides.
# A stale lock is stolen on acquire unless --no-steal is given.
#
# Owner pid: ROUTINE_LOCK_PID if set (scripts/schedule/run-routine.sh exports its own pid, which
# lives for the whole run), else the parent pid of this script.
# Note: this is not a hook. Hook exit-code contract (PreToolUse): only exit 2 blocks; other nonzero exits warn.

set -u

KIT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOCK_BASE="${ROUTINE_LOCK_DIR:-$KIT_ROOT/.claude/state/locks}"
DEFAULT_TTL_MIN=90

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

now_epoch() { date +%s; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
host_name() { hostname 2>/dev/null || uname -n; }

mtime_epoch() {
  # portable mtime: GNU stat first (GNU "stat -f" means filesystem info), then BSD stat
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0
}

json_field() {
  # json_field <file> <key> : read a scalar from the flat owner.json this script writes
  sed -n "s/^[[:space:]]*\"$2\":[[:space:]]*\"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}[[:space:]]*$/\1/p" "$1" | head -n 1
}

pid_alive() {
  [ -n "$1" ] && [ "$1" -gt 0 ] 2>/dev/null && kill -0 "$1" 2>/dev/null
}

# lock_state <dir> -> prints "free" | "fresh" | "stale"
lock_state() {
  local dir="$1" owner="$1/owner.json"
  [ -d "$dir" ] || { echo free; return; }
  local now; now=$(now_epoch)
  if [ ! -f "$owner" ]; then
    # mkdir succeeded but owner.json not yet renamed in: treat as fresh for 60 s
    local age=$(( now - $(mtime_epoch "$dir") ))
    if [ "$age" -gt 60 ]; then echo stale; else echo fresh; fi
    return
  fi
  local started ttl host pid
  started=$(json_field "$owner" started_epoch); started=${started:-0}
  ttl=$(json_field "$owner" ttl_min); ttl=${ttl:-$DEFAULT_TTL_MIN}
  host=$(json_field "$owner" host)
  pid=$(json_field "$owner" pid)
  local age_min=$(( (now - started) / 60 ))
  if [ "$age_min" -lt "$ttl" ]; then echo fresh; return; fi
  if [ "$host" = "$(host_name)" ] && pid_alive "$pid"; then echo fresh; return; fi
  echo stale
}

describe_owner() {
  local owner="$1/owner.json"
  if [ -f "$owner" ]; then
    local started; started=$(json_field "$owner" started_epoch); started=${started:-0}
    printf 'owner pid=%s host=%s session=%s started=%s age=%smin ttl=%smin\n' \
      "$(json_field "$owner" pid)" "$(json_field "$owner" host)" "$(json_field "$owner" session)" \
      "$(json_field "$owner" started_at)" "$(( ($(now_epoch) - started) / 60 ))" "$(json_field "$owner" ttl_min)"
  else
    echo "owner unknown (lock directory has no owner.json yet)"
  fi
}

write_owner() {
  local dir="$1" ttl="$2" tmp
  tmp="$LOCK_BASE/.owner.$$.$(now_epoch).tmp"
  cat > "$tmp" <<EOF
{
  "pid": ${ROUTINE_LOCK_PID:-$PPID},
  "host": "$(host_name)",
  "session": "${CLAUDE_SESSION_ID:-${KIT_ROUTINE_NAME:--}}",
  "started_at": "$(now_iso)",
  "started_epoch": $(now_epoch),
  "ttl_min": $ttl
}
EOF
  mv -f "$tmp" "$dir/owner.json"
}

valid_name() {
  case "$1" in
    ''|*/*|.*|*' '*) return 1 ;;
    *) return 0 ;;
  esac
}

cmd="${1:-}"; name="${2:-}"
[ -n "$cmd" ] && [ -n "$name" ] || usage
valid_name "$name" || { echo "routine-lock: invalid lock name '$name'" >&2; exit 2; }
shift 2

ttl="$DEFAULT_TTL_MIN"; steal=1
while [ $# -gt 0 ]; do
  case "$1" in
    --ttl-min) [ $# -ge 2 ] || usage; ttl="$2"; shift 2 ;;
    --no-steal) steal=0; shift ;;
    *) usage ;;
  esac
done
case "$ttl" in ''|*[!0-9]*) echo "routine-lock: --ttl-min needs a positive integer" >&2; exit 2 ;; esac

mkdir -p "$LOCK_BASE" || { echo "routine-lock: cannot create $LOCK_BASE" >&2; exit 2; }
dir="$LOCK_BASE/$name.lock"

case "$cmd" in
  acquire)
    if mkdir "$dir" 2>/dev/null; then
      write_owner "$dir" "$ttl"; echo "acquired $name"; exit 0
    fi
    state=$(lock_state "$dir")
    if [ "$state" = stale ] && [ "$steal" -eq 1 ]; then
      echo "routine-lock: stealing stale lock $name ($(describe_owner "$dir"))" >&2
      judged=$(json_field "$dir/owner.json" started_epoch 2>/dev/null)
      graveyard="$dir.stale.$$.$(now_epoch)"
      # Rename aside (atomic), then confirm we moved the lock we judged stale. If a concurrent stealer
      # already replaced it with a fresh lock, put that one back and report "held".
      if mv "$dir" "$graveyard" 2>/dev/null; then
        moved=$(json_field "$graveyard/owner.json" started_epoch 2>/dev/null)
        if [ "$moved" != "$judged" ]; then
          if mkdir "$dir" 2>/dev/null; then mv -f "$graveyard/owner.json" "$dir/owner.json" 2>/dev/null; fi
          rm -rf "$graveyard"
          echo "held $name: $(describe_owner "$dir")"; exit 1
        fi
        rm -rf "$graveyard"
      fi
      if mkdir "$dir" 2>/dev/null; then
        write_owner "$dir" "$ttl"; echo "acquired $name (stale lock stolen)"; exit 0
      fi
    fi
    echo "held $name: $(describe_owner "$dir")$( [ "$state" = stale ] && echo ' [stale, not stolen]')"
    exit 1
    ;;
  release)
    if [ -d "$dir" ]; then
      rm -f "$dir/owner.json"; rmdir "$dir" 2>/dev/null || rm -rf "$dir"
      echo "released $name"
    else
      echo "not held $name"
    fi
    exit 0
    ;;
  status)
    state=$(lock_state "$dir")
    case "$state" in
      free) echo "free $name"; exit 0 ;;
      fresh) echo "held $name: $(describe_owner "$dir")"; exit 1 ;;
      stale) echo "stale $name: $(describe_owner "$dir")"; exit 3 ;;
    esac
    ;;
  *) usage ;;
esac
