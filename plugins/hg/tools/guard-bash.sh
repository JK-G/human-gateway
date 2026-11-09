#!/usr/bin/env bash
# guard-bash.sh - PreToolUse hook (matcher: Bash). Layer 2 of defense in depth.
#
# Contract: stdin is the hook JSON ({"tool_input":{"command":"..."},"cwd":"..."}).
# Exit 0 = allow. Exit 2 = block, and stderr is shown to the model. Only exit 2 blocks in
# PreToolUse: any other nonzero exit is a warning and the command still runs.
#
# Blocks a command only when a path under FORBIDDEN_WRITE_PATHS (.claude/hg.json) is the
# TARGET of a write: a redirect target, a tee/cp/mv/install/ln/rsync destination, an
# rm/rmdir/truncate/touch/mkdir/chmod/chown/sed -i/perl -i argument, dd of=, find -delete,
# git -C <forbidden> (or cd <forbidden> && git ...) with a mutating subcommand, git mv/rm,
# git checkout/restore of a forbidden path (git restore --staged touches only the index and passes),
# or inline interpreter code (python -c, node -e, sh -c) that writes there. A path that merely
# appears (find -not -path, grep pattern, cat, ls, cd) passes.
# The vault raw/ prefix is append-only: creating a NEW file or directory there passes, changing
# or deleting an existing one is blocked. Skills bring a source in with hg-tool raw-add.
#
# This is a heuristic against honest mistakes, not a sandbox. It fails open (exit 0) when the
# payload cannot be parsed. Human escape hatch: HG_GUARD_BYPASS=1 in the environment that
# launched Claude Code. Agents never set it.

set -f   # no pathname expansion: protected prefixes contain globs
SELF="${BASH_SOURCE[0]}"          # this file is sourced by hg-tool, and run again for sh -c bodies
TOOLS="${HG_TOOLS:-$(cd "$(dirname "$SELF")" && { pwd -W 2>/dev/null || pwd; })}"
KIT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
[ "${HG_GUARD_BYPASS:-0}" = "1" ] && exit 0
cd "$KIT_ROOT" 2>/dev/null || exit 0
ROOT_L="$PWD"                     # logical, no "//"
cd -P . 2>/dev/null; ROOT_P="$PWD"  # physical (macOS /private/...)

# On Windows, paths arrive as D:\x or D:/x, and the shell's own form is /d/x.
WIN=0
case "${OSTYPE:-}" in msys*|cygwin*) WIN=1;; esac
to_posix() {  # sets REPLY: Windows path shapes -> /d/x, anything else unchanged
  REPLY="$1"
  [ "$WIN" = 1 ] || return 0
  REPLY="${REPLY//\\//}"
  case "$REPLY" in [A-Za-z]:|[A-Za-z]:/*) REPLY="/${REPLY:0:1}${REPLY:2}";; esac
}

if [ "${1:-}" = "--cmd" ]; then          # recursive mode for sh -c / bash -c bodies; config is exported
  CMD="$(cat)"; CWD="${KIT_GUARD_CWD:-$ROOT_L}"
else
  eval "$(${HG_PYTHON:-python3} -S "$TOOLS/hook_env.py" 2>/dev/null)"
  export FORBIDDEN_WRITE_PATHS VAULT_DIR ROOT_NATIVE
  CWD="${CWD:-$ROOT_L}"
fi
[ -z "${CMD:-}" ] && exit 0
FORBIDDEN_WRITE_PATHS="${FORBIDDEN_WRITE_PATHS:-vault/raw/ gates/ .obsidian/}"
to_posix "$CWD"; CWD="$REPLY"
ROOT_W="$ROOT_L"                 # Git Bash reports folders under its own mounts as /tmp/x, payloads say C:/.../x
if [ "$WIN" = 1 ] && [ -n "${ROOT_NATIVE:-}" ]; then to_posix "$ROOT_NATIVE"; ROOT_W="$REPLY"; fi

# --- paths ---------------------------------------------------------------------------
rel() {   # rel <path> -> path relative to KIT_ROOT on stdout; nothing if outside the root
  local p="$1" abs part out="" seg
  [ "$WIN" = 1 ] && shopt -s nocasematch   # Windows paths ignore case; this runs in a subshell, so option parsing is unaffected
  p="${p//\$\{CLAUDE_PROJECT_DIR\}/$ROOT_L}"; p="${p//\$CLAUDE_PROJECT_DIR/$ROOT_L}"
  p="${p//\$\{PWD\}/$CWD}"; p="${p//\$PWD/$CWD}"
  to_posix "$p"; p="$REPLY"
  case "$p" in ""|"~"*|*://*) return;; /*) abs="$p";; *) abs="$CWD/$p";; esac
  IFS=/ read -r -a seg <<< "$abs"
  for part in "${seg[@]}"; do
    case "$part" in ""|.) ;; ..) out="${out%/*}";; *) out="$out/$part";; esac
  done
  out="${out:-/}"
  for r in "$ROOT_L" "$ROOT_P" "$ROOT_W"; do
    case "$out" in "$r") echo "."; return;; "$r"/*) echo "${out:${#r}+1}"; return;; esac
  done
}
match() {  # match <relpath> -> prints the forbidden prefix it falls under
  local r="$1" p
  [ -z "$r" ] && return 1
  [ "$WIN" = 1 ] && shopt -s nocasematch
  for p in $FORBIDDEN_WRITE_PATHS; do
    case "$r/" in $p*) echo "$p"; return 0;; esac
    case "$p" in .*) case "/$r/" in */$p*) echo "$p"; return 0;; esac;; esac
  done
  return 1
}
block() {
  echo "BLOCKED by guard-bash: '$1' would write to '$2' (protected prefix '$3')." >&2
  echo "Reads and navigation are allowed; ask the person if this write is really needed." >&2
  exit 2
}
# chk <kind> <verb> <path>: kind w = create-or-modify, d = mkdir, x = modify/delete (never ok)
chk() {
  local kind="$1" verb="$2" r p
  r="$(rel "$3")"; p="$(match "$r")" || return 0
  if [ "$p" = "${VAULT_DIR:-vault}/raw/" ]; then     # append-only: new files and dirs only
    case "$kind" in d) return 0;; w) [ -e "$ROOT_L/$r" ] || return 0;; esac
  fi
  block "$verb" "$r" "$p"
}
dest_of() {  # dest_of <src> <dest>: cp/mv semantics when dest is a directory
  local r; r="$(rel "$2")"
  case "$2" in */) echo "$2${1##*/}"; return;; esac
  if [ -n "$r" ] && [ -d "$ROOT_L/$r" ]; then echo "$2/${1##*/}"; else echo "$2"; fi
}

# --- tokenizer: TOK entries are "w<word>" or "o<operator>" --------------------------
TOK=(); cur=""; have=0; HD=""
flush() { [ "$have" = 1 ] && TOK+=("w$cur"); cur=""; have=0; }
s="$CMD"; n=${#s}; i=0
while [ "$i" -lt "$n" ]; do
  c="${s:i:1}"; nx="${s:i+1:1}"
  case "$c" in
    "'") rest="${s:i+1}"; q="${rest%%\'*}"; cur+="$q"; have=1; i=$((i + ${#q} + 2)); continue;;
    '"') i=$((i + 1)); have=1
         while [ "$i" -lt "$n" ]; do
           c="${s:i:1}"
           if [ "$c" = '\' ]; then    # inside double quotes a backslash escapes only these, so "D:\x" survives
             case "${s:i+1:1}" in '$'|'`'|'"'|'\'|$'\n') cur+="${s:i+1:1}"; i=$((i + 2)); continue;; esac
           fi
           [ "$c" = '"' ] && break; cur+="$c"; i=$((i + 1))
         done; i=$((i + 1)); continue;;
    '\') cur+="$nx"; have=1; i=$((i + 2)); continue;;
    ' '|$'\t') flush;;
    $'\n') flush; TOK+=("o;")
       if [ -n "$HD" ]; then
         rest="${s:i+1}"; used=0
         while :; do
           case "$rest" in *$'\n'*) line="${rest%%$'\n'*}"; rest="${rest#*$'\n'}";; *) line="$rest"; rest="";; esac
           used=$((used + ${#line} + 1)); t="$line"; while [ "${t:0:1}" = $'\t' ]; do t="${t:1}"; done
           [ "$t" = "$HD" ] && break; [ -z "$rest" ] && break
         done; i=$((i + used)); HD=""
       fi;;
    ';'|'('|')'|'`') flush; TOK+=("o;");;
    '{'|'}') case "$have$nx" in 0|"0 "|0$'\t'|0$'\n'|"0;") TOK+=("o;");; *) cur+="$c"; have=1;; esac;;
    '&') flush
         if [ "$nx" = '&' ]; then TOK+=("o;"); i=$((i + 1))
         elif [ "$nx" = '>' ]; then i=$((i + 1)); if [ "${s:i+1:1}" = '>' ]; then i=$((i + 1)); fi; TOK+=("o>")
         else TOK+=("o;"); fi;;
    '|') flush; TOK+=("o;"); case "$nx" in '|'|'&') i=$((i + 1));; esac;;
    '>') case "$cur" in *[!0-9]*|"") flush;; *) cur=""; have=0;; esac
         case "$nx" in '>'|'|') i=$((i + 1));; esac
         if [ "${s:i+1:1}" = '&' ]; then              # fd duplication such as 2>&1 or >&2
           i=$((i + 2)); while case "${s:i:1}" in [0-9-]) true;; *) false;; esac; do i=$((i + 1)); done; continue
         fi; TOK+=("o>");;
    '<') flush
         if [ "$nx" = '<' ]; then
           i=$((i + 2)); [ "${s:i:1}" = '-' ] && i=$((i + 1)); [ "${s:i:1}" = '<' ] && { i=$((i + 1)); TOK+=("o<"); continue; }
           while [ "${s:i:1}" = ' ' ]; do i=$((i + 1)); done
           HD=""; while [ "$i" -lt "$n" ]; do c="${s:i:1}"; case "$c" in ' '|$'\n'|';') break;; esac; HD+="$c"; i=$((i + 1)); done
           HD="${HD//\'/}"; HD="${HD//\"/}"; HD="${HD//\\/}"; continue
         elif [ "$nx" = '(' ]; then TOK+=("o;"); i=$((i + 1))
         else TOK+=("o<"); fi;;
    '$') if [ "$nx" = '(' ]; then flush; TOK+=("o;"); i=$((i + 1))
         elif [ "$nx" = '{' ]; then rest="${s:i}"; q="${rest%%\}*}"; cur+="$q}"; have=1; i=$((i + ${#q} + 1)); continue
         else cur+="$c"; have=1; fi;;
    '#') if [ "$have" = 0 ]; then while [ "$i" -lt "$n" ] && [ "${s:i:1}" != $'\n' ]; do i=$((i + 1)); done; continue; fi
         cur+="$c";;
    *) cur+="$c"; have=1;;
  esac
  i=$((i + 1))
done
flush

# --- per-segment analysis ------------------------------------------------------------
GIT_MUT=" add am apply checkout cherry-pick clean clone commit init merge mv pull push rebase reset restore revert rm stash switch "
WRITE_HINT="open\(.*['\"][wax+]|write|unlink|remove|rmtree|rename|replace|mkdir|truncate|copy|move|appendFile|writeFile|>"
analyze() {
  local a=("$@") v j k nf=() x dest gdir="" sub="" inplace=0 hasexpr=0 code=""
  while [ "${#a[@]}" -gt 0 ]; do
    case "${a[0]}" in [A-Za-z_]*=*|sudo|env|command|nohup|time|nice|exec|builtin|-*) a=("${a[@]:1}");; *) break;; esac
  done
  [ "${#a[@]}" -eq 0 ] && return
  v="${a[0]##*/}"; a=("${a[@]:1}")
  for x in ${a[@]+"${a[@]}"}; do case "$x" in -*) ;; *) nf+=("$x");; esac; done
  k=${#nf[@]}
  case "$v" in
    cd) to_posix "${nf[0]:-~}"; x="$REPLY"; case "$x" in "~"*) CWD="$HOME";; /*) CWD="$x";; *) CWD="$CWD/$x";; esac;;
    tee) for x in ${nf[@]+"${nf[@]}"}; do chk w tee "$x"; done;;
    cp|mv|install|ln|rsync)
      for ((j = 0; j < ${#a[@]}; j++)); do
        case "${a[j]}" in -t) dest="${a[j+1]}";; --target-directory=*) dest="${a[j]#*=}";; esac
      done
      if [ "$v" = install ] && printf '%s\n' "${a[@]}" | grep -qx -- '-d'; then
        for x in ${nf[@]+"${nf[@]}"}; do chk d install "$x"; done; return
      fi
      [ "$k" -eq 0 ] && return
      if [ -z "$dest" ]; then dest="${nf[k-1]}"; k=$((k - 1)); fi
      case "$dest" in [!/]*:*) return;; esac      # remote rsync target
      if [ "$v" = mv ]; then for ((j = 0; j < k; j++)); do chk x mv "${nf[j]}"; done; fi
      if [ "$k" -gt 0 ]; then chk w "$v" "$(dest_of "${nf[k-1]}" "$dest")"; else chk w "$v" "$dest"; fi;;
    rm|rmdir|unlink|shred|truncate) for x in ${nf[@]+"${nf[@]}"}; do chk x "$v" "$x"; done;;
    touch) for x in ${nf[@]+"${nf[@]}"}; do chk w touch "$x"; done;;
    mkdir) for x in ${nf[@]+"${nf[@]}"}; do chk d mkdir "$x"; done;;
    chmod|chown|chgrp) for ((j = 1; j < k; j++)); do chk x "$v" "${nf[j]}"; done;;
    dd) for x in ${a[@]+"${a[@]}"}; do case "$x" in of=*) chk w dd "${x#of=}";; esac; done;;
    sed|perl)
      for x in ${a[@]+"${a[@]}"}; do
        case "$x" in -e|-f|--expression*) hasexpr=1;; -M*|-I*) ;; -i*|--in-place*) inplace=1;; -[a-zA-Z]*i*) [ "$v" = perl ] && inplace=1;; esac
      done
      [ "$v" = perl ] && { code="$(printf '%s\n' "${a[@]}" | grep -A1 -x -- '-[a-zA-Z]*e' | tail -n 1)"; hasexpr=1; }
      [ "$inplace" = 1 ] || return
      j=0; [ "$hasexpr" = 0 ] && j=1
      for ((; j < k; j++)); do [ "${nf[j]}" = "$code" ] || chk x "$v -i" "${nf[j]}"; done;;
    find)
      printf '%s\n' "${a[@]}" | grep -qxE -- '-delete|-exec|-execdir|-ok' || return
      printf '%s\n' "${a[@]}" | grep -qxE -- '-delete' || printf '%s\n' "${a[@]}" | grep -A1 -xE -- '-exec|-execdir|-ok' | grep -qE '(^|/)(rm|mv|truncate|shred|sed|chmod|chown)$' || return
      for x in ${a[@]+"${a[@]}"}; do case "$x" in -*|'!'|'(') break;; esac; chk x "find" "$x"; done;;
    git)
      for ((j = 0; j < ${#a[@]}; j++)); do
        case "${a[j]}" in -C) gdir="${a[j+1]}"; j=$((j + 1));; -c) j=$((j + 1));; -*) ;; *) sub="${a[j]}"; break;; esac
      done
      [ -z "$sub" ] && return
      local rest=("${a[@]:j+1}") gnf=()
      for x in ${rest[@]+"${rest[@]}"}; do case "$x" in -*) ;; *) gnf+=("$x");; esac; done
      local r p; r="$(rel "${gdir:-.}")"
      if case "$GIT_MUT" in *" $sub "*) true;; *) false;; esac && p="$(match "$r")"; then block "git $sub" "$r" "$p"; fi
      [ -n "$gdir" ] && { local old="$CWD"; CWD="$ROOT_L/$r"; }
      case "$sub" in
        rm) for x in ${gnf[@]+"${gnf[@]}"}; do chk x "git rm" "$x"; done;;
        checkout|restore)
          if ! { printf '%s\n' "${rest[@]}" | grep -qxE -- '--staged|-S' && ! printf '%s\n' "${rest[@]}" | grep -qxE -- '--worktree|-W'; }; then
            for x in ${gnf[@]+"${gnf[@]}"}; do chk x "git $sub" "$x"; done
          fi;;
        mv) k=${#gnf[@]}; [ "$k" -ge 2 ] && { for ((j = 0; j < k - 1; j++)); do chk x "git mv" "${gnf[j]}"; done
              chk w "git mv" "$(dest_of "${gnf[k-2]}" "${gnf[k-1]}")"; };;
      esac
      [ -n "$gdir" ] && CWD="$old";;
    sh|bash|zsh|dash)
      for ((j = 0; j < ${#a[@]}; j++)); do
        if [ "${a[j]}" = -c ]; then printf '%s' "${a[j+1]}" | KIT_GUARD_CWD="$CWD" bash "$SELF" --cmd || exit 2; return; fi
      done;;
    python|python3|node|ruby|deno|bun)
      for ((j = 0; j < ${#a[@]}; j++)); do case "${a[j]}" in -c|-e|--eval) code="${a[j+1]}";; esac; done
      [ -n "$code" ] && printf '%s' "$code" | grep -qE "$WRITE_HINT" || return
      for x in $FORBIDDEN_WRITE_PATHS; do
        pat="$(printf '%s' "$x" | sed 's/[.]/\\./g; s/\*/[^\/[:space:]]*/g')"
        printf '%s' "$code" | grep -qE "(^|[\"'/[:space:]])$pat" && block "$v inline code" "(inline)" "$x"
      done;;
  esac
}
SEG=(); expect=""
for t in "${TOK[@]}"; do
  case "$t" in
    "o>") expect=redir;;
    "o<") expect=skip;;
    o*) [ "${#SEG[@]}" -gt 0 ] && analyze "${SEG[@]}"; SEG=(); expect="";;
    w*) w="${t#w}"
        if [ "$expect" = redir ]; then chk w ">" "$w"; elif [ "$expect" != skip ]; then SEG+=("$w"); fi
        expect="";;
  esac
done
[ "${#SEG[@]}" -gt 0 ] && analyze "${SEG[@]}"
exit 0
