# tests/lib.sh - shared helpers for the test scripts. Source it first.
#
# Git Bash rewrites path-like arguments for native programs. Tests use forward-slash Windows
# paths (C:/x) on Windows, so that rewriting is switched off and every path is passed as it is.

export MSYS2_ARG_CONV_EXCL='*'

native_path() {  # C:/x on Windows, unchanged elsewhere
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}

temp_dir() {  # temp_dir <prefix>: a new temp folder in the native path form
  local base="${TMPDIR:-/tmp}"     # macOS sets TMPDIR with a trailing slash; a // in the path would not match what the tools print
  native_path "$(mktemp -d "${base%/}/$1.XXXXXX")"
}

REPO_ROOT="$(native_path "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)")"
HG_TOOL="$REPO_ROOT/plugins/hg/bin/hg-tool"
hg() { bash "$HG_TOOL" "$@"; }
PY="$(hg python-cmd)"

json_str() {  # json_str <value>: a JSON string literal, built without jq
  local s="$1"
  s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; s="${s//$'\n'/\\n}"; s="${s//$'\t'/\\t}"
  printf '"%s"' "$s"
}

jtrue() {  # echo '{...}' | jtrue '<python expression on d>': exit 0 when true
  $PY -c 'import json,sys; d=json.loads(sys.stdin.read()); sys.exit(0 if eval(sys.argv[1]) else 1)' "$1" 2>/dev/null
}

jedit() {  # jedit <in> <out> '<python statements on d>'
  $PY -c 'import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
exec(sys.argv[3])
json.dump(d,open(sys.argv[2],"w",encoding="utf-8"),ensure_ascii=False)' "$1" "$2" "$3"
}
