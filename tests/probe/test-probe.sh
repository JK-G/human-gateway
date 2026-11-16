#!/usr/bin/env bash
# test-probe.sh - the hg-probe and hg-probe-panel plugins' shape: nothing that needs bash or Python to load,
# a hook that works in bash and in PowerShell, the panel module kept in its own plugin so a surface that refuses
# a module is not confused with one that refuses plugins, a skill that asks for every fact the owner needs, and the guide.
# Self-contained. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PROBE="$REPO_ROOT/plugins/hg-probe"
PANEL="$REPO_ROOT/plugins/hg-probe-panel"
SKILL="$PROBE/skills/sprawdz/SKILL.md"
GUIDE="$REPO_ROOT/docs/hg-probe.md"
TMP="$(temp_dir hg-probe)"
[ -n "$TMP" ] || { echo "FAIL - no temp folder"; exit 1; }
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }

# --- nothing that needs bash or Python of its own ---------------------------------------------
for dir in "$PROBE" "$PANEL"; do
  name="${dir##*/}"
  [ -d "$dir" ] && ok "$name: the plugin folder exists" || bad "$name: the plugin folder exists"
  [ ! -e "$dir/bin" ] && ok "$name: no bin/ folder" || bad "$name: no bin/ folder"
  out="$(find "$dir" -type f \( -name '*.py' -o -name '*.sh' \))"
  [ -z "$out" ] && ok "$name: no .py and no .sh file" || bad "$name: no .py and no .sh file" "$out"
  for f in "$dir/.claude-plugin/plugin.json" "$dir/hooks/hooks.json"; do
    $PY -c 'import json,sys; json.load(open(sys.argv[1],encoding="utf-8"))' "$f" && ok "$name: ${f#"$dir"/} parses" || bad "$name: ${f#"$dir"/} parses"
  done
done

# --- hg-probe carries no module, so a refused module cannot hide behind it ----------------------
out="$(find "$PROBE" -type f \( -name '*.tsx' -o -name '*.ts' -o -name '*.jsx' -o -name '*.js' \))"
[ -z "$out" ] && ok "hg-probe: no module file" || bad "hg-probe: no module file" "$out"
out="$(grep -rlF '"modules"' "$PROBE")"
[ -z "$out" ] && ok "hg-probe: no modules key anywhere" || bad "hg-probe: no modules key anywhere" "$out"

# --- manifest, hooks, marketplace -------------------------------------------------------------
$PY -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if d["name"]=="hg-probe" else 1)' "$PROBE/.claude-plugin/plugin.json" \
  && ok "plugin.json parses and names hg-probe" || bad "plugin.json parses and names hg-probe"
HOOKS="$PROBE/hooks/hooks.json"
cmd="$($PY -c 'import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
hs=[h for g in d["hooks"]["SessionStart"] for h in g["hooks"]]
print(hs[0]["command"] if len(hs)==1 and hs[0]["type"]=="command" else "")' "$HOOKS")"
[ -n "$cmd" ] && ok "one SessionStart command hook" || bad "one SessionStart command hook"
case "$cmd" in *bash*|*python*|*py\ *|*'${'*|*'$('*) bad "the hook calls no bash, no Python and no variable" "$cmd";; *) ok "the hook calls no bash, no Python and no variable";; esac
$PY -c 'import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
p=[x for x in d["plugins"] if x["name"]=="hg-probe"]
sys.exit(0 if len(p)==1 and p[0]["source"]=="./plugins/hg-probe" else 1)' "$REPO_ROOT/.claude-plugin/marketplace.json" \
  && ok "the marketplace lists hg-probe" || bad "the marketplace lists hg-probe"
$PY -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if d["name"]=="hg-probe-panel" else 1)' "$PANEL/.claude-plugin/plugin.json" \
  && ok "the panel's plugin.json names hg-probe-panel" || bad "the panel's plugin.json names hg-probe-panel"
$PY -c 'import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
p=[x for x in d["plugins"] if x["name"]=="hg-probe-panel"]
sys.exit(0 if len(p)==1 and p[0]["source"]=="./plugins/hg-probe-panel" else 1)' "$REPO_ROOT/.claude-plugin/marketplace.json" \
  && ok "the marketplace lists hg-probe-panel" || bad "the marketplace lists hg-probe-panel"

# --- the hook command leaves its marker in bash and in PowerShell ------------------------------------
mkdir -p "$TMP/bash" "$TMP/ps"
( cd "$TMP/bash" && bash -c "$cmd" )
[ "$(wc -c < "$TMP/bash/.hg-probe-hook" 2>/dev/null | tr -d ' ')" = 14 ] && ok "in bash the hook writes a 14-byte marker" || bad "in bash the hook writes a 14-byte marker"
if command -v powershell.exe >/dev/null 2>&1; then
  ( cd "$TMP/ps" && powershell.exe -NoProfile -NonInteractive -Command "$cmd" )
  [ "$(wc -c < "$TMP/ps/.hg-probe-hook" 2>/dev/null | tr -d ' ')" = 32 ] && ok "in Windows PowerShell the hook writes a 32-byte marker" || bad "in Windows PowerShell the hook writes a 32-byte marker"
else
  echo "n/a  - Windows PowerShell is not here, the hook was not run in it"
fi

# --- the panel plugin: one module and nothing else ----------------------------------------------------
PHOOKS="$PANEL/hooks/hooks.json"
$PY -c 'import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
sys.exit(0 if "hooks" not in d and isinstance(d.get("modules"),list) and len(d["modules"])==1 else 1)' "$PHOOKS" \
  && ok "hg-probe-panel: hooks.json holds one module and no command hook" || bad "hg-probe-panel: hooks.json holds one module and no command hook" "$(cat "$PHOOKS")"
out="$(grep -rlE '"type"[[:space:]]*:[[:space:]]*"command"' "$PANEL")"
[ -z "$out" ] && ok "hg-probe-panel: no command hook anywhere" || bad "hg-probe-panel: no command hook anywhere" "$out"
out="$(find "$PANEL" -type f \( -name '*.tsx' -o -name '*.ts' -o -name '*.jsx' -o -name '*.js' \) | wc -l | tr -d ' ')"
[ "$out" = 1 ] && ok "hg-probe-panel: exactly one module file" || bad "hg-probe-panel: exactly one module file" "found $out"
module="$($PY -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["modules"][0])' "$PHOOKS")"
[ -f "$PANEL/hooks/$module" ] && ok "the panel module named in hooks.json exists" || bad "the panel module named in hooks.json exists" "$module"
grep -qF 'hg-probe: panel działa' "$PANEL/hooks/$module" && ok "the panel shows its fixed line" || bad "the panel shows its fixed line"
grep -qF '.hg-probe-panel' "$PANEL/hooks/$module" && grep -qF '.hg-probe-panel' "$SKILL" && ok "the panel marker is the one the skill reads" || bad "the panel marker is the one the skill reads"
grep -qF 'Znacznik wtyczki hg-probe-panel znaleziony' "$SKILL" && ok "the skill reports a found panel marker with its content" || bad "the skill reports a found panel marker with its content"
grep -qF 'albo ta wtyczka nie została dodana' "$SKILL" && grep -qF 'albo jej kod tu się nie wczytał' "$SKILL" && grep -qF 'Nie zgaduj' "$SKILL" \
  && ok "the skill reports a missing panel marker without guessing why" || bad "the skill reports a missing panel marker without guessing why"

# --- the skill names every fact ---------------------------------------------------------------------
[ -f "$SKILL" ] && grep -q '^name: sprawdz$' "$SKILL" && ok "skill sprawdz" || bad "skill sprawdz"
grep -q '^disable-model-invocation: true' "$SKILL" && bad "the model can start the skill" || ok "the model can start the skill"
grep -qF 'Sprawdź moje środowisko dla hg' "$SKILL" && ok "the skill's description holds the sentence to type" || bad "the skill's description holds the sentence to type"
for needle in 'uname -srm' 'OSVersion' 'narzędzie o nazwie `Bash`' 'narzędzie o nazwie `PowerShell`' \
  'bash --version' 'git --version' 'python --version' 'python3 --version' 'py -3 --version' 'command -v bash git python python3 py' 'Get-Command bash, git, python, python3, py' \
  'xcode-select -p' 'WindowsApps' 'pwd' '(Get-Location).Path' 'widoczności' '"$HOME"' 'hostname' '$env:COMPUTERNAME' 'kształt' \
  "env | cut -d= -f1" 'Get-ChildItem Env:' 'tylko nazwy' 'CLAUDE_CODE_ENTRYPOINT' '.dockerenv' 'Win32_ComputerSystem' \
  'zakładka Code' 'zakładka Cowork' 'W terminalu' 'Gdzie indziej' 'Innych pytań nie zadajesz' \
  '.hg-probe-hook' 'nie znaleziono znacznika' 'Nie pisz, dlaczego' \
  'projektów i zadań' 'dokumenty i pliki' 'kalendarz' 'komunikator' 'Niczego nie wywołuj' \
  'harmonogramu' 'Niczego nie tworzysz' \
  'hg-probe-report.md' '`~`' '<user>' 'Nie łączysz się z siecią'; do
  grep -qF -- "$needle" "$SKILL" && ok "the skill names: $needle" || bad "the skill names: $needle"
done
grep -qF -- 'id -un' "$SKILL" && grep -qF -- '$env:USERNAME' "$SKILL" && ok "the skill checks the report for the user and host name" || bad "the skill checks the report for the user and host name"

# --- the guide ----------------------------------------------------------------------------------------
[ -f "$GUIDE" ] && ok "the guide exists" || bad "the guide exists"
grep -qxF 'Sprawdź moje środowisko dla hg.' "$GUIDE" && ok "the guide holds the sentence to type" || bad "the guide holds the sentence to type"
for needle in '/hg-probe:sprawdz' 'hg-probe-report.md' 'hg-probe-panel' 'nieobowiązkowa' 'nową rozmowę' 'JK-G/human-gateway' 'może wyglądać inaczej' 'Code' 'Cowork' 'hg-probe: panel działa'; do
  grep -qF -- "$needle" "$GUIDE" && ok "the guide names: $needle" || bad "the guide names: $needle"
done

# --- no em dashes -------------------------------------------------------------------------------------
out="$(grep -rn $'\xe2\x80\x94' "$PROBE" "$PANEL" "$GUIDE" "$0" 2>/dev/null)"
[ -z "$out" ] && ok "no em dashes" || bad "no em dashes" "$out"

if command -v claude >/dev/null 2>&1; then
  out="$(claude plugin validate "$REPO_ROOT" 2>&1)"; [ $? -eq 0 ] && ok "marketplace validates" || bad "marketplace validates" "$out"
  out="$(claude plugin validate "$PROBE" 2>&1)"; [ $? -eq 0 ] && ok "hg-probe validates" || bad "hg-probe validates" "$out"
  out="$(claude plugin validate "$PANEL" 2>&1)"; [ $? -eq 0 ] && ok "hg-probe-panel validates" || bad "hg-probe-panel validates" "$out"
else
  echo "n/a  - claude is not installed here, plugin validation not run"
fi

echo "probe: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
