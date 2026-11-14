#!/usr/bin/env bash
# test-nodes.sh - hg-tool nodes: the five nodes and their states, declaring them in .claude/hg.json, what the
# department's repository holds (a bare remote in the temp folder), the secret through a gh stub (HG_GH, never
# the real gh), recorded tool readings, the platform table and watch, session-start and doctor.
# Self-contained: fictional data in temp repos, no network. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
NODES="$PLUGIN/tools/nodes.py"
TMP="$(temp_dir hg-nodes)"
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { printf '%s' "$1" | grep -qF -- "$2"; }

export PYTHONDONTWRITEBYTECODE=1
unset HG_NOTIFY_WEBHOOK_URL KIT_TODAY GH_STUB GH_LOG
DEAD_PROXY="http://127.0.0.1:9"

cat > "$TMP/gh.py" <<'PY'
import json, os, sys
args, mode = sys.argv[1:], os.environ.get("GH_STUB", "")
if os.environ.get("GH_LOG"):
    with open(os.environ["GH_LOG"], "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\n")
if args[:2] == ["secret", "list"]:
    if mode == "nosign":
        sys.exit(1)
    print(json.dumps([{"name": "HG_NOTIFY_WEBHOOK_URL" if mode == "secret" else "OTHER_NAME"}]))
else:
    sys.exit(1)
PY
export HG_GH="$PY $TMP/gh.py"
GHLOG="$TMP/gh.log"

in_ws() { local dir="$1"; shift; (cd "$dir" && CLAUDE_PROJECT_DIR="$dir" "$@"); }
nodes() {  # nodes <workspace> [args]: the output without CR, with the tool's exit code; stderr in $TMP/err
  local dir="$1" rc; shift
  in_ws "$dir" bash "$HG_TOOL" nodes "$@" >"$TMP/nodes.out" 2>"$TMP/err"; rc=$?
  tr -d '\r' < "$TMP/nodes.out"; return $rc
}
TAB="$(printf '\t')"
field() { printf '%s\n' "$1" | grep "^$2$TAB" | cut -f"$3"; }   # field <output> <node id> <column>

# ===== a fresh workspace =========================================================================
W="$TMP/dept"
hg setup --root "$W" --name Dept --language pl --project acme-notes >/dev/null
git -C "$W" config user.email reviewer@example.com; git -C "$W" config user.name Reviewer; git -C "$W" config core.autocrlf false
E="$TMP/english"
hg setup --root "$E" --name English --language en >/dev/null

out="$(nodes "$W")"; rc=$?
ids="$(printf '%s\n' "$out" | cut -f1 | tr '\n' ' ')"
{ [ $rc -eq 0 ] && [ "$ids" = "messenger projects calendar agent backup " ] && [ "$(printf '%s\n' "$out" | grep -c .)" = 5 ]; } \
  && ok "a fresh workspace lists five nodes in order" || bad "a fresh workspace lists five nodes in order (rc=$rc)" "$out"
states="$(printf '%s\n' "$out" | cut -f2 | tr '\n' ' ')"
t '[ "$states" = "empty empty session unavailable unavailable " ]' "messenger, projects are empty, calendar is session, agent and backup are unavailable" "$states"

PL_M='Komunikator: niepodłączony. Podłączony kanał działu dostaje wiadomość, gdy bramka zaczyna czekać na zatwierdzenie, a w dni robocze rano listę tego, co czeka. Działa ze Slackiem, Microsoft Teams i każdym adresem, który przyjmuje JSON. Podłączysz go przez /hg:setup --nodes.'
PL_P='Platformy projektowe: żadna nie jest zadeklarowana. Po zadeklarowaniu /hg:gate i /hg:init podpowiadają, które pole zadania albo tablicy śledzić. Dzięki temu bramka otwiera się po zmianie w tym systemie. hg niczego nie pobiera: czyta tylko sesja, która ma do tej platformy własne narzędzie.'
PL_C='Kalendarz: hg nie widzi, czy Twoja sesja ma narzędzie kalendarza. Gdy ma, /hg:today pokazuje dzisiejsze spotkania i wolne bloki. Gdy nie ma, pomija tę część.'
EN_M='Messenger: not plugged in. A plugged-in department channel gets a message when a gate starts to wait for approval, and on workday mornings a list of what waits. It works with Slack, Microsoft Teams and any address that takes JSON. Plug it in with /hg:setup --nodes.'
EN_P='Project platforms: none is declared. Once one is, /hg:gate and /hg:init suggest which field of a task or a board to watch. That is how a gate reopens after a change in that system. hg fetches nothing: only a session with its own tool for that platform reads it.'
EN_C="Calendar: hg cannot see whether your session has a calendar tool. When it does, /hg:today shows today's meetings and free blocks. When it does not, that part is skipped."
en="$(nodes "$E")"
{ [ "$(field "$out" messenger 3)" = "$PL_M" ] && [ "$(field "$out" projects 3)" = "$PL_P" ] && [ "$(field "$out" calendar 3)" = "$PL_C" ] \
  && [ "$(field "$en" messenger 3)" = "$EN_M" ] && [ "$(field "$en" projects 3)" = "$EN_P" ] && [ "$(field "$en" calendar 3)" = "$EN_C" ]; } \
  && ok "every empty line says what plugging in unlocks" || bad "every empty line says what plugging in unlocks" "$out
$en"
a_pl="$(field "$out" agent 3)"; b_pl="$(field "$out" backup 3)"; a_en="$(field "$en" agent 3)"; b_en="$(field "$en" backup 3)"
{ case "$a_pl" in 'Agent do orkiestracji: jeszcze niedostępny. '*) true;; *) false;; esac \
  && case "$b_pl" in 'Kopia plików źródłowych: jeszcze niedostępna. '*) true;; *) false;; esac \
  && case "$a_en" in 'Agent for orchestration: not available yet. '*) true;; *) false;; esac \
  && case "$b_en" in 'Backup of source files: not available yet. '*) true;; *) false;; esac \
  && [ "$(printf '%s\n%s\n' "$a_en" "$b_en" | grep -o 'not available yet' | wc -l | tr -d ' ')" = 2 ]; } \
  && ok "agent and backup say not available yet, in one sentence each" || bad "agent and backup say not available yet, in one sentence each" "$a_pl / $b_pl / $a_en / $b_en"
json="$(nodes "$W" --json)"
printf '%s' "$json" | jtrue '[n["id"] for n in d] == ["messenger", "projects", "calendar", "agent", "backup"] and all(isinstance(n["available"], bool) and n["line"] for n in d)' \
  && ok "--json is the same five nodes" || bad "--json is the same five nodes" "$json"

# ===== declare ===================================================================================
cp "$W/.claude/hg.json" "$TMP/hg.before.json"
out="$(nodes "$W" declare messenger teams)"; rc=$?
$PY - "$TMP/hg.before.json" "$W/.claude/hg.json" <<'PY' >"$TMP/cmp.out" 2>&1
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8")); b = json.load(open(sys.argv[2], encoding="utf-8"))
rest = {k: v for k, v in b.items() if k != "nodes"}
assert list(rest) == list(a) and rest == a, "other keys changed"
assert b["nodes"] == {"messenger": {"type": "teams"}}, b.get("nodes")
assert list(b)[-1] == "nodes"
PY
{ [ $rc -eq 0 ] && [ ! -s "$TMP/cmp.out" ] && has "$out" $'messenger\tdeclared\tKomunikator: zadeklarowany Microsoft Teams.'; } \
  && ok "declare messenger teams writes only the nodes key and keeps the order of the others" || bad "declare messenger teams writes only the nodes key and keeps the order of the others (rc=$rc)" "$out $(cat "$TMP/cmp.out")"
nodes "$W" declare messenger none >/dev/null; rc=$?
nokey() { $PY -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if "nodes" not in d else 1)' "$W/.claude/hg.json"; }
t '[ $rc -eq 0 ] && nokey && [ "$(field "$(nodes "$W")" messenger 2)" = empty ]' "declare messenger none removes it" "$(cat "$W/.claude/hg.json")"
cp "$W/.claude/hg.json" "$TMP/hg.now.json"
nodes "$W" declare messenger discord >/dev/null; rc=$?
{ [ $rc -eq 1 ] && has "$(cat "$TMP/err")" "not a messenger type" && cmp -s "$TMP/hg.now.json" "$W/.claude/hg.json"; } \
  && ok "an unknown type is refused" || bad "an unknown type is refused (rc=$rc)" "$(cat "$TMP/err")"
out="$(nodes "$W" declare projects clickup,jira)"; rc=$?
{ [ $rc -eq 0 ] && $PY -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if d["nodes"]["projects"]==["clickup","jira"] else 1)' "$W/.claude/hg.json" \
  && [ "$out" = $'projects\tdeclared\tPlatformy projektowe: zadeklarowane ClickUp, Jira. hg nie widzi, czy Twoja sesja ma narzędzie do ich czytania.' ]; } \
  && ok "declare projects clickup,jira" || bad "declare projects clickup,jira (rc=$rc)" "$out $(cat "$TMP/err")"
cp "$W/.claude/hg.json" "$TMP/hg.now.json"
nodes "$W" declare projects clickup,basecamp >/dev/null; rc=$?
{ [ $rc -eq 1 ] && has "$(cat "$TMP/err")" "'basecamp' is not a platform this plugin knows" && cmp -s "$TMP/hg.now.json" "$W/.claude/hg.json"; } \
  && ok "an unknown platform is refused" || bad "an unknown platform is refused (rc=$rc)" "$(cat "$TMP/err")"
nodes "$W" declare projects none >/dev/null; rc=$?
{ [ $rc -eq 0 ] && nokey; } && ok "declare projects none" || bad "declare projects none (rc=$rc)" "$(cat "$W/.claude/hg.json")"
mkdir -p "$TMP/none"
out="$(nodes "$TMP/none" declare messenger slack)"; rc=$?
{ [ $rc -eq 1 ] && has "$(cat "$TMP/err")" ".claude/hg.json is missing"; } && ok "declare without a config is refused" || bad "declare without a config is refused (rc=$rc)" "$(cat "$TMP/err")"

# ===== the messenger and the department's repository ==========================================
BARE="$TMP/dept.git"
git init -q --bare "$BARE"
git -C "$W" remote add origin https://github.com/acme/notes.git          # what gh is asked about
git -C "$W" config remote.origin.pushurl "$BARE"                          # where a push really goes: no network
git -C "$W" add -A && git -C "$W" commit -q -m base
mline() { : > "$GHLOG"; out="$(in_ws "$W" env GH_STUB="$1" GH_LOG="$GHLOG" HTTPS_PROXY="$DEAD_PROXY" bash "$HG_TOOL" nodes ${2:-} 2>/dev/null | tr -d '\r')"
  MSTATE="$(field "$out" messenger 2)"; MLINE="$(field "$out" messenger 3)"; }

nodes "$W" declare messenger slack >/dev/null
mline secret
{ [ "$MSTATE" = declared ] && [ "$MLINE" = 'Komunikator: zadeklarowany Slack. W repozytorium działu brakuje jeszcze: deklaracji komunikatora, pliku hg-notify.yml, pliku notify.py. Opublikuj zmiany, potem ustaw sekret.' ]; } \
  && ok "with no upstream all three are named" || bad "with no upstream all three are named" "$MSTATE $MLINE"
git -C "$W" stash -q   # the declaration waits; the base goes out without it
git -C "$W" push -q -u origin HEAD 2>/dev/null
git -C "$W" stash pop -q
mline secret
{ [ "$MSTATE" = declared ] && [ "$MLINE" = 'Komunikator: zadeklarowany Slack. W repozytorium działu brakuje jeszcze: deklaracji komunikatora. Opublikuj zmiany, potem ustaw sekret.' ]; } \
  && ok "declared with the still-lacks line while the declaration is not pushed, naming the declaration" || bad "declared with the still-lacks line while the declaration is not pushed, naming the declaration" "$MSTATE $MLINE"
git -C "$W" commit -q -am 'declare slack'
mline secret
t 'has "$MLINE" "brakuje jeszcze: deklaracji komunikatora."' "a committed declaration that is not pushed still lacks" "$MLINE"
git -C "$W" push -q 2>/dev/null
mline secret
{ [ "$MSTATE" = plugged ] && [ "$MLINE" = 'Komunikator: Slack, podłączony. W repozytorium działu są deklaracja, plik hg-notify.yml i sekret HG_NOTIFY_WEBHOOK_URL. To, że wiadomości dochodzą, potwierdza tylko wiadomość próbna.' ] \
  && has "$(cat "$GHLOG")" "secret list --app actions --json name -R acme/notes"; } \
  && ok "messenger is plugged when the upstream holds the type, the workflow and notify.py, and gh lists the secret" || bad "messenger is plugged when the upstream holds the type, the workflow and notify.py, and gh lists the secret" "$MSTATE $MLINE $(cat "$GHLOG")"
json="$(in_ws "$W" env GH_STUB=secret bash "$HG_TOOL" nodes --json 2>/dev/null)"
printf '%s' "$json" | jtrue 'd[0]["type"] == "slack" and d[0]["facts"] == [{"kind": "declared", "what": "type", "value": "slack"}, {"kind": "recorded", "what": "published", "value": "type, workflow, notifier"}, {"kind": "checked", "what": "secret", "value": "found"}]' \
  && ok "the plugged messenger's facts are declared, recorded and checked" || bad "the plugged messenger's facts are declared, recorded and checked" "$json"
printf '%s' "$json" | jtrue 'all(f.get("kind") in ("declared", "recorded", "checked") for n in d for f in n["facts"]) and any(n["facts"] for n in d)' \
  && ok "--json gives every fact a kind" || bad "--json gives every fact a kind" "$json"
mline other
{ [ "$MSTATE" = declared ] && [ "$MLINE" = 'Komunikator: zadeklarowany Slack. W repozytorium na GitHubie nie znaleziono sekretu HG_NOTIFY_WEBHOOK_URL. Sekretu ustawionego dla całej organizacji stąd nie widać. Bez sekretu nic nie jest wysyłane.' ]; } \
  && ok "declared with the no-secret line when gh lists another name" || bad "declared with the no-secret line when gh lists another name" "$MSTATE $MLINE"
CANNOT='Komunikator: zadeklarowany Slack. Stąd nie da się sprawdzić, czy sekret jest ustawiony: potrzebne są repozytorium na GitHubie i program gh z zalogowanym kontem.'
out="$(in_ws "$W" env HG_GH="$TMP/no-such-gh" bash "$HG_TOOL" nodes 2>/dev/null | tr -d '\r')"
m1="$(field "$out" messenger 3)"
mline nosign; m2="$MLINE"
{ [ "$m1" = "$CANNOT" ] && [ "$m2" = "$CANNOT" ] && [ "$(field "$out" messenger 2)" = declared ]; } \
  && ok "declared with the cannot-check line without gh" || bad "declared with the cannot-check line without gh" "$m1 / $m2"
mline secret --offline
{ [ ! -s "$GHLOG" ] && [ "$MLINE" = "$CANNOT" ]; } && ok "--offline never starts gh" || bad "--offline never starts gh" "$(cat "$GHLOG") $MLINE"
: > "$GHLOG"
json="$(in_ws "$W" env GH_STUB=secret GH_LOG="$GHLOG" bash "$HG_TOOL" nodes --json --offline 2>/dev/null)"
{ printf '%s' "$json" | jtrue 'not any(f["kind"] == "checked" for n in d for f in n["facts"])' && [ ! -s "$GHLOG" ]; } \
  && ok "no fact has kind checked with --offline" || bad "no fact has kind checked with --offline" "$json"
git -C "$W" rm -q .github/workflows/hg-notify.yml && git -C "$W" commit -q -m 'no workflow' && git -C "$W" push -q 2>/dev/null
mline secret
{ [ "$MSTATE" = declared ] && [ "$MLINE" = 'Komunikator: zadeklarowany Slack. W repozytorium działu brakuje jeszcze: pliku hg-notify.yml. Opublikuj zmiany, potem ustaw sekret.' ] && [ ! -s "$GHLOG" ]; } \
  && ok "declared with the still-lacks line naming hg-notify.yml when the upstream has no workflow" || bad "declared with the still-lacks line naming hg-notify.yml when the upstream has no workflow" "$MSTATE $MLINE"
git -C "$W" revert --no-edit HEAD >/dev/null && git -C "$W" push -q 2>/dev/null
nodes "$W" declare messenger teams >/dev/null
mline secret
t 'has "$MLINE" "zadeklarowany Microsoft Teams. W repozytorium działu brakuje jeszcze: deklaracji komunikatora."' "a published declaration of another type still lacks the declaration" "$MLINE"
git -C "$W" checkout -q -- .claude/hg.json
sed "s/HG_NOTIFY_WEBHOOK_URL/HG_""SLACK_WEBHOOK_URL/g" "$W/.github/workflows/hg-notify.yml" > "$TMP/old-wf.yml"
cp "$TMP/old-wf.yml" "$W/.github/workflows/hg-notify.yml"
git -C "$W" commit -q -am 'an older workflow' && git -C "$W" push -q 2>/dev/null
mline secret
{ [ "$MSTATE" = declared ] && has "$MLINE" "brakuje jeszcze: pliku hg-notify.yml"; } \
  && ok "a published workflow that passes the old secret name is not plugged in" || bad "a published workflow that passes the old secret name is not plugged in" "$MSTATE $MLINE"
git -C "$W" revert --no-edit HEAD >/dev/null && git -C "$W" push -q 2>/dev/null

# the messenger counts what the default branch holds: GitHub runs hg-notify.yml from there only
V="$TMP/side"
hg setup --root "$V" --name Side --language pl --project acme-notes >/dev/null
git -C "$V" config user.email reviewer@example.com; git -C "$V" config user.name Reviewer; git -C "$V" config core.autocrlf false
git init -q --bare "$TMP/side.git"
git -C "$V" remote add dept https://github.com/acme/other.git; git -C "$V" config remote.dept.pushurl "$TMP/side.git"
git -C "$V" add -A && git -C "$V" commit -q -m base && git -C "$V" push -q -u dept HEAD 2>/dev/null
git -C "$V" checkout -q -b side
nodes "$V" declare messenger slack >/dev/null
git -C "$V" commit -q -am 'declare slack' && git -C "$V" push -q -u dept side 2>/dev/null
vline() { : > "$GHLOG"; out="$(in_ws "$V" env GH_STUB=secret GH_LOG="$GHLOG" HTTPS_PROXY="$DEAD_PROXY" bash "$HG_TOOL" nodes 2>/dev/null | tr -d '\r')"
  VSTATE="$(field "$out" messenger 2)"; VLINE="$(field "$out" messenger 3)"; }
vline
{ [ "$VSTATE" = declared ] && has "$VLINE" "brakuje jeszcze: deklaracji komunikatora"; } \
  && ok "a declaration pushed only to another branch is not plugged in" || bad "a declaration pushed only to another branch is not plugged in" "$VSTATE $VLINE"
git -C "$V" checkout -q main && git -C "$V" merge -q --ff-only side && git -C "$V" push -q dept main 2>/dev/null && git -C "$V" checkout -q side
vline
{ [ "$VSTATE" = plugged ] && has "$(cat "$GHLOG")" "-R acme/other"; } \
  && ok "once the default branch holds it, it is plugged in, and the secret is asked of the upstream's remote" || bad "once the default branch holds it, it is plugged in, and the secret is asked of the upstream's remote" "$VSTATE $VLINE $(cat "$GHLOG")"

# ===== project platforms ==========================================================================
B=vault/projects/acme-notes/brief.md
printf '# Brief\n' > "$W/$B"; git -C "$W" add -A; git -C "$W" commit -q -m brief
g() { in_ws "$W" bash "$HG_TOOL" gate "$@"; }
g new plan --title Plan --project acme-notes --accountable reviewer@example.com --input "$B" \
  --source 'task=https://app.clickup.com/t/86abc' --watch task=date_updated \
  --source 'issue=https://acme.atlassian.net/browse/ACME-1' --watch issue=updated >/dev/null || bad "the gate with two sources is drafted" "$(g list)"
nodes "$W" declare projects clickup,jira >/dev/null
SEEN=""
pstate() { out="$(nodes "$W" --offline)"; PSTATE="$(field "$out" projects 2)"; PLINE="$(field "$out" projects 3)"; SEEN="$SEEN $PSTATE"; }
pstate
{ [ "$PSTATE" = declared ] && [ "$PLINE" = 'Platformy projektowe: zadeklarowane ClickUp, Jira. hg nie widzi, czy Twoja sesja ma narzędzie do ich czytania.' ]; } \
  && ok "projects is declared without a recorded reading" || bad "projects is declared without a recorded reading" "$PSTATE $PLINE"
g observe plan issue --declare unchanged --request 'I looked at it' >/dev/null || bad "a statement is recorded" "$(g list)"
pstate
t '[ "$PSTATE" = declared ] && ! has "$PLINE" "zapisany odczyt"' "a person's statement is not a reading" "$PSTATE $PLINE"
g observe plan task --field date_updated --mark '2026-11-12T10:00:00Z' >/dev/null || bad "a reading is recorded" "$(g list)"
day="$(date -u +%Y-%m-%d)"
pstate
{ [ "$PSTATE" = declared ] && [ "$PLINE" = "Platformy projektowe: zadeklarowane ClickUp, Jira. hg nie widzi, czy Twoja sesja ma narzędzie do ich czytania. W repozytorium jest zapisany odczyt narzędziem: ClickUp ($day). Dla pozostałych nie ma zapisanego odczytu." ]; } \
  && ok "with a reading for some platforms the state stays declared and says so" || bad "with a reading for some platforms the state stays declared and says so" "$PSTATE $PLINE"
nodes "$W" declare projects clickup >/dev/null
pstate
{ [ "$PSTATE" = recorded ] && [ "$PLINE" = "Platformy projektowe: ClickUp. W repozytorium jest zapisany odczyt narzędziem: ClickUp ($day)." ]; } \
  && ok "projects is recorded once a tool reading of a ClickUp source is recorded" || bad "projects is recorded once a tool reading of a ClickUp source is recorded" "$PSTATE $PLINE"
json="$(nodes "$W" --json --offline)"
printf '%s' "$json" | jtrue 'd[1]["facts"] == [{"kind": "declared", "what": "platforms", "value": "clickup"}, {"kind": "recorded", "what": "reading", "value": "clickup '"$day"'"}] and "{platform}" in d[1]["session_yes"] and "{platform}" in d[1]["session_no"]' \
  && ok "the projects node carries its facts and the two session sentences" || bad "the projects node carries its facts and the two session sentences" "$json"
pstate; SEEN="$SEEN $(field "$(nodes "$E")" projects 2)"
t 'has "$SEEN" empty && has "$SEEN" declared && has "$SEEN" recorded && ! has "$SEEN" plugged' "no state of projects is plugged" "$SEEN"

# ===== watch ======================================================================================
w() { bash "$HG_TOOL" nodes watch "$@" 2>&1 | tr -d '\r'; }
out="$(w 'https://app.clickup.com/t/86abc')"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "clickup${TAB}date_updated" ]' "watch prints clickup and date_updated for an app.clickup.com link" "$out"
out="$(w 'https://acme.atlassian.net/browse/ACME-1')"
t '[ "$out" = "jira${TAB}updated" ]' "watch prints jira and updated for a subdomain of atlassian.net" "$out"
out="$(w 'https://atlassian.net.example.org/x')"
out2="$(w 'https://evilatlassian.net/x')"
t '[ "$out" = unknown ] && [ "$out2" = unknown ]' "a host that only looks like a listed one is unknown" "$out / $out2"
out="$(bash "$HG_TOOL" nodes watch 'https://intranet.example.com/x' 2>/dev/null)"; rc=$?; out="$(printf '%s' "$out" | tr -d '\r')"
t '[ $rc -eq 1 ] && [ "$out" = unknown ]' "watch exits 1 for an unknown host" "rc=$rc $out"
out="$(env HTTPS_PROXY="$DEAD_PROXY" HTTP_PROXY="$DEAD_PROXY" https_proxy="$DEAD_PROXY" http_proxy="$DEAD_PROXY" $PY -c '
import socket, sys
def refuse(*a, **k):
    raise SystemExit("a connection was opened")
socket.socket.connect = refuse
socket.create_connection = refuse
sys.path.insert(0, sys.argv[1]); sys.argv = ["nodes.py", "watch", "https://www.notion.so/acme/Page-1"]
import nodes
raise SystemExit(nodes.main(sys.argv[1:]))' "$PLUGIN/tools" 2>&1 | tr -d '\r')"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "notion${TAB}last_edited_time" ]' "watch opens no connection" "rc=$rc $out"
out="$(bash "$HG_TOOL" nodes watch 'https://app.clickup.com/t/86abc' --json | tr -d '\r')"
printf '%s' "$out" | jtrue 'd == {"platform": "clickup", "name": "ClickUp", "item": "task", "field": "date_updated"}' && ok "watch --json names the platform, the item and the field" || bad "watch --json names the platform, the item and the field" "$out"
out="$($PY -c '
import re, sys
sys.path.insert(0, sys.argv[1])
import gate, nodes
bad = [k for k, row in nodes.PLATFORMS.items() if row[3] and not (gate.WATCH_RE.fullmatch(row[3]) and gate.MARK_CHARS.fullmatch(row[3]))]
print(" ".join(bad) or "none", len(nodes.PLATFORMS))' "$PLUGIN/tools" | tr -d '\r')"
t '[ "$out" = "none 10" ]' "every field in the table fits the characters gate observe takes" "$out"

# ===== session-start and doctor ==================================================================
: > "$GHLOG"
out="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" GH_STUB=secret GH_LOG="$GHLOG" hg session-start | tr -d '\r')"
lines="$(printf '%s\n' "$out" | grep -c '^- Nodes declared')"
{ [ "$lines" = 1 ] && [ ! -s "$GHLOG" ] \
  && has "$out" '- Nodes declared in .claude/hg.json (not checked here): messenger slack; project platforms clickup. Not available yet: agent, backup. hg-tool nodes prints the full list.'; } \
  && ok "session-start prints one nodes line and starts no gh" || bad "session-start prints one nodes line and starts no gh" "$out $(cat "$GHLOG")"
out="$(cd "$E" && CLAUDE_PROJECT_DIR="$E" hg session-start | tr -d '\r')"
has "$out" 'messenger none; project platforms none.' && ok "session-start says none for what is not declared" || bad "session-start says none for what is not declared" "$out"

out="$(hg doctor --root "$E" | tr -d '\r')"
n="$(printf '%s\n' "$out" | grep -c $'^OK\tnode\t')"
{ [ "$n" = 4 ] && ! has "$out" $'\tnode\tMessenger' && has "$out" $'OK\tnode\tCalendar: hg cannot see' && has "$out" $'OK\tnotify\t' && ! has "$out" 'notify-secret'; } \
  && ok "doctor prints one node line per node other than the messenger" || bad "doctor prints one node line per node other than the messenger" "$out"
$PY -c 'import json,sys; p=sys.argv[1]; d=json.load(open(p,encoding="utf-8")); d["nodes"]={"projects":["clickup","basecamp"],"messenger":{"type":"discord"}}
json.dump(d,open(p,"w",encoding="utf-8",newline=""),indent=2)' "$E/.claude/hg.json"
out="$(hg doctor --root "$E" | tr -d '\r')"
{ has "$out" $'WARN\tnode\tnodes.projects names 1 platform this plugin does not know. Known: clickup, jira, asana, trello, linear, github, notion, monday, miro, other.' \
  && has "$out" $'WARN\tnode\tnodes.messenger.type is not slack, teams or webhook, so nothing is sent.'; } \
  && ok "doctor warns about an unknown platform key" || bad "doctor warns about an unknown platform key" "$out"
out="$(nodes "$E")"
t '[ "$(field "$out" messenger 2)" = empty ] && [ "$(field "$out" projects 2)" = declared ]' "an unknown type is an empty messenger, an unknown key is ignored" "$out"
DOC="$PLUGIN/skills/doctor/SKILL.md"
last="$(grep -v '^[[:space:]]*$' "$DOC" | tail -n 3)"
{ grep -qF 'hg-tool nodes' "$DOC" && has "$last" 'hg-tool nodes' && grep -qi 'always ends with the node list' "$DOC"; } \
  && ok "the doctor skill always ends with the node list" || bad "the doctor skill always ends with the node list" "$last"

# ===== the skills that use the nodes =============================================================
for f in gate init; do
  grep -qF "hg-tool nodes watch '<link>'" "$PLUGIN/skills/$f/SKILL.md" && ok "/hg:$f asks the platform table for the field to watch" || bad "/hg:$f asks the platform table for the field to watch"
done
grep -qF 'hg-tool nodes --json --offline' "$PLUGIN/skills/today/SKILL.md" && grep -qF 'session_yes' "$PLUGIN/skills/today/SKILL.md" \
  && ! grep -qF 'no adapter, skipped' "$PLUGIN/skills/today/SKILL.md" \
  && ok "/hg:today copies the calendar node's session sentence" || bad "/hg:today copies the calendar node's session sentence"
SETUP="$PLUGIN/skills/setup/SKILL.md"
{ grep -q '^argument-hint: "\[--update | --nodes\]"$' "$SETUP" && grep -q '^## Nodes$' "$SETUP" && grep -qF 'hg-tool nodes declare messenger' "$SETUP" \
  && grep -qF 'hg-tool nodes declare projects' "$SETUP" && grep -qF 'Send webhook alerts to a channel' "$SETUP" && ! grep -q -- '--slack' "$SETUP"; } \
  && ok "/hg:setup walks the nodes" || bad "/hg:setup walks the nodes"

# ===== the files ===================================================================================
out="$(grep -nE '^(from|import) ' "$NODES" | grep -vE 'import (json|re|sys|urllib\.parse)$|^[0-9]+:from pathlib import Path$|import (gate|kit_registry as kr)  # noqa: E402$')"
t '[ -z "$out" ]' "nodes imports only the standard library and the kit" "$out"
t '[ "$($PY -c "import sys; sys.path.insert(0, sys.argv[1]); import nodes, notify; print(nodes.NOTIFY_SECRET == notify.SECRET_ENV)" "$PLUGIN/tools")" = True ]'   "nodes names the same secret as notify"
out="$(cd "$REPO_ROOT" && hg scan plugins/hg/tools/nodes.py tests/nodes 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the scanner finds nothing in the new files" "$out"
out="$(grep -n $'\xe2\x80\x94' "$NODES" "$REPO_ROOT/tests/nodes/test-nodes.sh" "$DOC" "$SETUP")"
t '[ -z "$out" ]' "no em dashes" "$out"

echo "nodes: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
