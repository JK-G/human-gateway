#!/usr/bin/env bash
# test-notify.sh - the Slack message: which gates started to wait in a push, the morning list, the fixed
# templates and their cleaning, sending and the secret, the five CI copies, hg-notify.yml and notify status.
# Self-contained: fictional data in temp repos. No test touches the network: sending goes through a stub
# opener or a server on 127.0.0.1, every ci run that holds a webhook-shaped secret has a dead local proxy as
# a safety net, and gh is always a local stub (HG_GH). A webhook-shaped string is built from pieces at run
# time. Every address ends in @example.com. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
NOTIFY="$PLUGIN/tools/notify.py"
TMP="$(temp_dir hg-notify)"
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { printf '%s' "$1" | grep -qF -- "$2"; }

export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ next to the copies in .github/hg/
unset HG_SLACK_WEBHOOK_URL HG_EVENT HG_MODE HG_BEFORE HG_AFTER KIT_TODAY
ALL="$TMP/all-output.log"; : > "$ALL"   # every output of the sending cases, checked for the address at the end
CANARY="canary$$x$RANDOM"
HOOK="https://hooks.""slack.com/services/""TQ0A/BQ0B/""$CANARY"   # webhook-shaped, built from pieces
DEAD_PROXY="http://127.0.0.1:9"                                  # any send that slipped through fails here

cat > "$TMP/gh.py" <<'PY'
import json, os, sys
args, mode = sys.argv[1:], os.environ.get("GH_STUB", "").split(",")
if os.environ.get("GH_LOG"):
    with open(os.environ["GH_LOG"], "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\n")
def run(conclusion, day, status="completed", event="push"):
    return {"conclusion": conclusion, "createdAt": "2026-11-%02dT06:31:00Z" % day, "event": event, "status": status}
if args[:2] == ["secret", "list"]:
    if "nosign" in mode:
        sys.exit(1)
    print(json.dumps([{"name": "HG_SLACK_WEBHOOK_URL" if "secret" in mode else "OTHER_NAME"}]))
elif args[:2] == ["run", "list"]:
    runs = {"green": [run("success", 9, event="schedule"), run("failure", 8)],
            "failed": [run("failure", 9), run("success", 8)],
            "cancelled": [run("cancelled", 9), run("success", 8)],
            "skipped5": [run("skipped", 9 - k) for k in range(5)] + [run("failure", 3), run("success", 2)]}
    print(json.dumps(next((v for k, v in runs.items() if k in mode), [])))
else:
    sys.exit(1)
PY
export HG_GH="$PY $TMP/gh.py"   # never the real gh

cat > "$TMP/fake.py" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import notify
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
kind, rest = sys.argv[2], sys.argv[3:]
polish, data = rest[0] == "pl" if len(rest) == 2 else False, json.loads(rest[-1])
if kind == "gate":
    print(notify.gate_message(data, polish))
elif kind == "digest":
    print(notify.digest_message(data, polish) or "")
elif kind == "push":
    print("\n---\n".join(notify.push_messages(data, polish)))
elif kind == "clean":
    print(notify.clean(data))
elif kind == "len":
    print(len(notify.clean(data)))
elif kind == "address":
    print(notify.address(data, polish))
elif kind == "test":
    print(notify.test_message(polish))
PY
fake() { $PY "$TMP/fake.py" "$PLUGIN/tools" "$@" | tr -d '\r'; }
G() {  # G <id> <status> [title] [accountable] [changed as JSON]: one gate as gate.all_gates gives it
  printf '{"id": "%s", "status": "%s", "title": %s, "accountable": "%s", "changed": %s}' \
    "$1" "$2" "${3:-\"T $1\"}" "${4:-anna@example.com}" "${5:-[]}"
}
texts() { $PY -c 'import json,sys
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
for line in sys.stdin:
    if line.strip():
        print(json.loads(line)["text"])' | tr -d '\r'; }
count() { printf '%s\n' "$1" | grep -c '^{' ; }

# ===== which gates started to wait ============================================================
W="$TMP/dept"
hg setup --root "$W" --name Dept --language pl --project acme-notes >/dev/null
git -C "$W" config user.email reviewer@example.com; git -C "$W" config user.name Reviewer; git -C "$W" config core.autocrlf false
B=vault/projects/acme-notes/brief.md
printf '# Brief\n' > "$W/$B"
commit() { git -C "$W" add -A && git -C "$W" commit -q -m "$1" && git -C "$W" rev-parse HEAD | tr -d '\r'; }
g() { (cd "$W" && CLAUDE_PROJECT_DIR="$W" hg gate "$@"); }
mk() { local id="$1"; shift; g new "$id" --title "T $id" --project acme-notes --accountable anna@example.com --input "$B" "$@" >/dev/null; }
approve() { g approve "$1" --via person --request ok >/dev/null || echo "approve $1 failed" >&2; }
push() {  # push <before> <after>: OUT = payloads, ERR = stderr, RC
  OUT="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg notify push --before "$1" --after "$2" 2>"$TMP/err" | tr -d '\r')"; RC=$?
  ERR="$(cat "$TMP/err")"; printf '%s\n' "$OUT" >> "$TMP/pushes"
}
export KIT_TODAY=2026-11-02
C0="$(commit base)"
mk d1
C1="$(commit 'gate d1')"
push "$C0" "$C1"
{ [ $RC -eq 0 ] && [ "$(count "$OUT")" = 1 ] \
  && has "$(printf '%s\n' "$OUT" | texts)" 'Nowa bramka czeka na zatwierdzenie: „T d1” (d1). Odpowiada: anna@example.com.'; } \
  && ok "a new draft gives one message" || bad "a new draft gives one message (rc=$RC)" "$OUT $ERR"
has "$ERR" "1 message(s)" && ok "the preview counts on stderr" || bad "the preview counts on stderr" "$ERR"

approve d1
C2="$(commit 'approve d1')"
push "$C1" "$C2"
t '[ $RC -eq 0 ] && [ -z "$OUT" ]' "an approval gives nothing" "$OUT"

printf '# Brief\n\nNew line.\n' > "$W/$B"
C3="$(commit 'brief changed')"
push "$C2" "$C3"
{ [ "$(count "$OUT")" = 1 ] && has "$(printf '%s\n' "$OUT" | texts)" 'Bramka znów czeka na zatwierdzenie: „T d1” (d1). Powód: zmiana w plikach. Odpowiada: anna@example.com. Otwórz Claude w folderze działu i wpisz /hg:gate.'; } \
  && ok "an approved gate whose file changed gives one reopened message" || bad "an approved gate whose file changed gives one reopened message" "$OUT $ERR"

printf '# Brief\n\nNew line.\nAnother.\n' > "$W/$B"
C4="$(commit 'brief changed again')"
push "$C3" "$C4"
t '[ $RC -eq 0 ] && [ -z "$OUT" ]' "a gate that was already waiting gives nothing" "$OUT"

approve d1
C5="$(commit 'approve d1 again')"
printf '# Brief\n\nThird.\n' > "$W/$B"; commit 'reopen' >/dev/null
approve d1
C6="$(commit 'approve d1 a third time')"
push "$C5" "$C6"
t '[ $RC -eq 0 ] && [ -z "$OUT" ]' "a gate reopened and approved again inside one push gives nothing" "$OUT"

mk d2
commit 'gate d2' >/dev/null
approve d2
C7="$(commit 'approve d2')"
push "$C6" "$C7"
t '[ $RC -eq 0 ] && [ -z "$OUT" ]' "a draft and its approval pushed together give nothing" "$OUT"

# a source: observed and approved on one day, another mark the next day
TASK=https://app.clickup.example/t/86abc
mk s1 --source roadmap="$TASK" --watch roadmap=date_updated
commit 'gate s1' >/dev/null
g observe s1 roadmap --field date_updated --mark '2026-11-01T10:00:00Z' >/dev/null
approve s1
C8="$(commit 'approve s1')"
export KIT_TODAY=2026-11-03
g observe s1 roadmap --field date_updated --mark '2026-11-03T08:00:00Z' >/dev/null
C9="$(commit 'roadmap changed')"
push "$C8" "$C9"
{ [ "$(count "$OUT")" = 1 ] && has "$(printf '%s\n' "$OUT" | texts)" 'Bramka znów czeka na zatwierdzenie: „T s1” (s1). Powód: zmiana w źródle zewnętrznym. Odpowiada: anna@example.com.'; } \
  && ok "an approved gate whose source changed gives the source reason" || bad "an approved gate whose source changed gives the source reason" "$OUT $ERR"

waiting="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg gate list | cut -f2 | grep -cE '^(draft|reopened)$')"
push 0000000000000000000000000000000000000000 "$C9"
{ [ "$waiting" -ge 1 ] && [ "$(count "$OUT")" = "$waiting" ]; } && ok "a first push, before all zeros, treats every waiting gate as new" \
  || bad "a first push, before all zeros, treats every waiting gate as new (waiting=$waiting)" "$OUT $ERR"

for k in 1 2 3 4 5 6; do mk "six-$k"; done
C10="$(commit 'six gates')"
push "$C9" "$C10"
body="$(printf '%s\n' "$OUT" | texts)"
{ [ "$(count "$OUT")" = 1 ] && has "$body" 'Po ostatniej zmianie czekają na zatwierdzenie (6):' \
  && has "$body" '- „T six-1” (six-1), szkic. Odpowiada: anna@example.com.' \
  && [ "$(printf '%s\n' "$body" | tail -n 1)" = 'Otwórz Claude w folderze działu i wpisz /hg:gate.' ]; } \
  && ok "six gates starting to wait give one list, not six messages" || bad "six gates starting to wait give one list, not six messages" "$OUT"
git -C "$W" rm -q gates/six-*.md; C11="$(commit 'drop the six')"

push deadbeefdeadbeefdeadbeefdeadbeefdeadbeef "$C11"
{ [ $RC -eq 0 ] && [ -z "$OUT" ] && has "$ERR" "not in this clone"; } \
  && ok "a before commit that is not in the clone sends nothing and exits 0" || bad "a before commit that is not in the clone sends nothing and exits 0 (rc=$RC)" "$OUT $ERR"

# twenty commits: a gate is created, approved, reopened and approved again in between
P0="$(git -C "$W" rev-parse HEAD | tr -d '\r')"
for k in $(seq 1 20); do
  printf 'step %s\n' "$k" >> "$W/vault/projects/acme-notes/steps.md"
  case $k in
    2) mk twenty ;;
    4) approve twenty ;;
    9) printf '# Brief\n\nFourth.\n' > "$W/$B" ;;
  esac
  c="$(commit "step $k")"
  case $k in 9) P9="$c" ;; esac
  case $k in 12) approve twenty; approve d1; approve d2; approve s1 ;; esac
done
P20="$(git -C "$W" rev-parse HEAD | tr -d '\r')"
push "$P0" "$P20"
r1="$RC/$(count "$OUT")"
push "$P0" "$P9"
r2="$(count "$OUT")"
t '[ "$r1" = 0/0 ] && [ "$r2" -ge 1 ]' "the two trees are compared by state, across twenty commits" "end-to-end=$r1 to-the-middle=$r2 $ERR"

n="$(git -C "$W" worktree list | wc -l | tr -d ' ')"
t '[ "$n" = 1 ]' "no worktree is left behind" "$(git -C "$W" worktree list)"
ls -d "${TMPDIR:-/tmp}"/hg-notify-* >/dev/null 2>&1 && bad "no temp tree is left behind" "$(ls -d "${TMPDIR:-/tmp}"/hg-notify-*)" || ok "no temp tree is left behind"

printf 'staged\n' > "$W/vault/projects/acme-notes/staged.md"; git -C "$W" add vault/projects/acme-notes/staged.md
printf 'loose\n' >> "$W/vault/projects/acme-notes/steps.md"
st_before="$(git -C "$W" status --porcelain=v1)"; ix_before="$(git -C "$W" diff --cached | $PY -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
push "$C0" "$P20"
st_after="$(git -C "$W" status --porcelain=v1)"; ix_after="$(git -C "$W" diff --cached | $PY -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())')"
t '[ "$st_before" = "$st_after" ] && [ "$ix_before" = "$ix_after" ]' "the working tree and the index are untouched" "$st_before / $st_after"
git -C "$W" reset -q; git -C "$W" checkout -q -- vault/projects/acme-notes/steps.md; rm -f "$W/vault/projects/acme-notes/staged.md"

# a source whose last check grows old: unchecked on both sides, never a per-gate message
export KIT_TODAY=2026-11-04
mk u1 --source plan="$TASK/plan" --watch plan=date_updated
commit 'gate u1' >/dev/null
g observe u1 plan --field date_updated --mark '2026-11-01T10:00:00Z' >/dev/null
approve u1
U1="$(commit 'approve u1')"
printf 'later\n' >> "$W/vault/projects/acme-notes/steps.md"; U2="$(commit 'later')"
export KIT_TODAY=2026-11-14
st="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg gate list | grep '^u1' | cut -f2)"
push "$U1" "$U2"
t '[ "$st" = unchecked ] && [ -z "$OUT" ]' "an unchecked gate gives no per-gate message" "status=$st $OUT"
pushed="$(texts < "$TMP/pushes")"
{ [ -n "$pushed" ] && ! has "$pushed" "://"; } && ok "the push messages hold no link" || bad "the push messages hold no link" "$pushed"

# ===== the morning list =======================================================================
M="$TMP/morning"
hg setup --root "$M" --name Morning --language pl --project acme-notes >/dev/null
git -C "$M" config user.email reviewer@example.com; git -C "$M" config user.name Reviewer; git -C "$M" config core.autocrlf false
printf '# Brief\n' > "$M/$B"
mc() { git -C "$M" add -A && git -C "$M" commit -q -m "$1"; }
mg() { (cd "$M" && CLAUDE_PROJECT_DIR="$M" hg gate "$@"); }
mmk() { local id="$1" who="$2"; shift 2; mg new "$id" --title "T $id" --project acme-notes --accountable "$who" --input "$B" "$@" >/dev/null; }
digest() { OUT="$(cd "$M" && CLAUDE_PROJECT_DIR="$M" hg notify digest --force 2>"$TMP/err" | tr -d '\r')"; RC=$?; ERR="$(cat "$TMP/err")"; BODY="$(printf '%s\n' "$OUT" | texts)"; }
export KIT_TODAY=2026-11-02
mc base
mmk ok1 anna@example.com
mc 'gate ok1'; mg approve ok1 --via person --request ok >/dev/null; mc 'approve ok1'
digest
t '[ $RC -eq 0 ] && [ -z "$OUT" ]' "nothing waits: no message" "$OUT $ERR"

mmk zz-reopened anna@example.com; mc 'gate'; mg approve zz-reopened --via person --request ok >/dev/null
printf '# Brief\n\nchanged\n' > "$M/$B"; mc 'reopen'
mmk aa-draft jan@example.com; mc 'draft'
digest
{ [ "$(count "$OUT")" = 1 ] && has "$BODY" 'Czeka na zatwierdzenie (3):' && ! has "$BODY" 'Do sprawdzenia'; } \
  && ok "a section with nothing in it is left out" || bad "a section with nothing in it is left out" "$BODY"
mmk src anna@example.com --source plan="https://app.clickup.example/t/src" --watch plan=date_updated
mc 'gate src'
mg observe src plan --field date_updated --mark '2026-11-02T09:00:00Z' >/dev/null
mg approve src --via person --request ok >/dev/null; mc 'approve src'
export KIT_TODAY=2026-11-09
digest
t '! has "$BODY" "Do sprawdzenia"' "a source is not in the list on the day it reaches N days" "$BODY"
export KIT_TODAY=2026-11-10
digest
{ has "$BODY" 'Do sprawdzenia (1):' && has "$BODY" '- „T src” (src), ostatnie sprawdzenie źródła zewnętrznego zapisane w repozytorium jest sprzed 8 dni.'; } \
  && ok "a source turns up in the list on the day it passes N days" || bad "a source turns up in the list on the day it passes N days" "$BODY"
{ has "$BODY" 'Czeka na zatwierdzenie (3):' && has "$BODY" 'Do sprawdzenia (1):'; } \
  && ok "the list has the waiting section and the to-check section" || bad "the list has the waiting section and the to-check section" "$BODY"
order="$(printf '%s\n' "$BODY" | grep -E '^- ' | sed -E 's/^- „T ([a-z0-9-]+)”.*/\1/' | tr '\n' ' ')"
t '[ "$order" = "ok1 zz-reopened aa-draft src " ]' "order is reopened, draft, unchecked" "$order"
reopened_line="$(printf '%s\n' "$BODY" | grep -F '(zz-reopened)')"
t '[ "$reopened_line" = "- „T zz-reopened” (zz-reopened), otwarta ponownie. Odpowiada: anna@example.com." ]' "a waiting line names the accountable address" "$reopened_line"
check="$(printf '%s\n' "$BODY" | grep -F '(src)')"
{ [ -n "$check" ] && ! has "$check" '@' && ! has "$check" '(at)' && has "$check" 'zapisane w repozytorium'; } \
  && ok "a to-check line names no person and says 'recorded in the repository'" || bad "a to-check line names no person and says 'recorded in the repository'" "$check"
t '[ "$(printf "%s\n" "$BODY" | tail -n 1)" = "Otwórz Claude w folderze działu i napisz: co mam dziś." ]' "the list ends with what to write" "$BODY"
en="$(fake digest en "[$(G src unchecked '"T src"' anna@example.com '[{"path": "plan", "why": "source_stale", "days": 9}]')]")"
{ has "$en" '- "T src" (src), the last check of an outside source recorded in the repository is 9 days old.' && ! has "$en" '@'; } \
  && ok "the English to-check line says 'recorded in the repository' and names no one" || bad "the English to-check line says 'recorded in the repository' and names no one" "$en"

many=""; for k in 01 02 03 04 05 06 07 08 09 10 11 12; do many="$many${many:+,}$(G "g$k" draft)"; done
out="$(fake digest pl "[$many]")"
{ [ "$(printf '%s\n' "$out" | grep -c '^- ')" = 10 ] && has "$out" 'i jeszcze 2.'; } && ok "more than ten gates end with 'and N more'" || bad "more than ten gates end with 'and N more'" "$out"
out="$(fake digest en "[$many]")"
has "$out" 'and 2 more.' && ok "the English list ends with 'and N more'" || bad "the English list ends with 'and N more'" "$out"

ci() { local dir="$1"; shift
  (cd "$dir" && CLAUDE_PROJECT_DIR="$dir" HTTPS_PROXY="$DEAD_PROXY" HTTP_PROXY="$DEAD_PROXY" NO_PROXY= "$@") >"$TMP/out" 2>"$TMP/err"; RC=$?
  OUT="$(tr -d '\r' < "$TMP/out")"; ERR="$(cat "$TMP/err")"; printf '%s\n%s\n' "$OUT" "$ERR" >> "$ALL"; }
ci "$M" env KIT_TODAY=2026-11-14 HG_EVENT=schedule $PY "$NOTIFY" ci --dry-run          # a Saturday
{ [ $RC -eq 0 ] && [ -z "$OUT" ] && has "$ERR" "not a workday"; } && ok "a schedule run on a day outside workdays sends nothing" || bad "a schedule run on a day outside workdays sends nothing (rc=$RC)" "$OUT $ERR"
ci "$M" env KIT_TODAY=2026-11-14 HG_EVENT=workflow_dispatch HG_MODE=list $PY "$NOTIFY" ci --dry-run
{ [ $RC -eq 0 ] && [ "$(count "$OUT")" = 1 ]; } && ok "a manual digest run ignores the workday test" || bad "a manual digest run ignores the workday test (rc=$RC)" "$OUT $ERR"
ci "$M" env KIT_TODAY=2026-11-10 HG_EVENT=schedule $PY "$NOTIFY" ci --dry-run          # a Tuesday
t '[ $RC -eq 0 ] && [ "$(count "$OUT")" = 1 ]' "a schedule run on a workday sends the list" "$OUT $ERR"

# ===== text ===================================================================================
pl_new="$(fake gate pl "$(G cennik-2027 draft '"Cennik 2027"')")"
pl_re="$(fake gate pl "$(G cennik-2027 reopened '"Cennik 2027"' anna@example.com '[{"path": "a.md", "why": "changed"}, {"path": "roadmap", "why": "source_changed"}, {"path": "b.md", "why": "added"}, {"path": "gates/cennik-2027.md", "why": "accountable"}]')")"
pl_unread="$(fake gate pl "$(G cennik-2027 reopened '"Cennik 2027"' anna@example.com '[{"path": "gates/cennik-2027.lock.json", "why": "unreadable"}]')")"
pl_list="$(fake push pl "[$(G a1 reopened),$(G a2 draft),$(G a3 draft),$(G a4 draft),$(G a5 draft),$(G a6 draft)]")"
pl_test="$(fake test pl '{}')"
ok_pl=1
for needle in \
  'Nowa bramka czeka na zatwierdzenie: „Cennik 2027” (cennik-2027). Odpowiada: anna@example.com. Otwórz Claude w folderze działu i wpisz /hg:gate.' ; do
  has "$pl_new" "$needle" || { ok_pl=0; bad "Polish template: $needle" "$pl_new"; }; done
for needle in \
  'Bramka znów czeka na zatwierdzenie: „Cennik 2027” (cennik-2027). Powód: zmiana w plikach, zmiana w źródle zewnętrznym, zmiana listy plików lub źródeł, zmiana osoby odpowiedzialnej. Odpowiada: anna@example.com. Otwórz Claude w folderze działu i wpisz /hg:gate.'; do
  has "$pl_re" "$needle" || { ok_pl=0; bad "Polish template: $needle" "$pl_re"; }; done
has "$pl_unread" 'Powód: zapis zatwierdzeń nie daje się odczytać.' || { ok_pl=0; bad "Polish template: unreadable" "$pl_unread"; }
for needle in 'Po ostatniej zmianie czekają na zatwierdzenie (6):' '- „T a1” (a1), otwarta ponownie. Odpowiada: anna@example.com.' \
  '- „T a2” (a2), szkic. Odpowiada: anna@example.com.' 'Otwórz Claude w folderze działu i wpisz /hg:gate.'; do
  has "$pl_list" "$needle" || { ok_pl=0; bad "Polish template: $needle" "$pl_list"; }; done
has "$pl_test" 'To jest wiadomość próbna z hg. Połączenie ze Slackiem działa.' || { ok_pl=0; bad "Polish template: test" "$pl_test"; }
has "$(fake address pl '"nobody"')" 'nie podano' || { ok_pl=0; bad "Polish template: not given"; }
[ $ok_pl = 1 ] && ok "the Polish templates, word for word"

en_new="$(fake gate en "$(G pricing-2027 draft '"Pricing 2027"')")"
en_re="$(fake gate en "$(G pricing-2027 reopened '"Pricing 2027"' anna@example.com '[{"path": "a.md", "why": "missing"}, {"path": "roadmap", "why": "source_changed"}, {"path": "roadmap", "why": "source_replaced"}, {"path": "gates/x.md", "why": "accountable"}]')")"
en_unread="$(fake gate en "$(G pricing-2027 reopened '"Pricing 2027"' anna@example.com '[{"path": "x", "why": "unreadable"}]')")"
en_list="$(fake push en "[$(G a1 reopened),$(G a2 draft),$(G a3 draft),$(G a4 draft),$(G a5 draft),$(G a6 draft)]")"
en_digest="$(fake digest en "[$(G a1 reopened),$(G a2 draft)]")"
ok_en=1
has "$en_new" 'A new gate waits for approval: "Pricing 2027" (pricing-2027). Accountable: anna@example.com. Open Claude in the department folder and type /hg:gate.' || { ok_en=0; bad "English template: new" "$en_new"; }
has "$en_re" 'A gate waits for approval again: "Pricing 2027" (pricing-2027). Reason: a file changed, an outside source changed, the list of files or sources changed, the accountable person changed. Accountable: anna@example.com. Open Claude in the department folder and type /hg:gate.' || { ok_en=0; bad "English template: reopened" "$en_re"; }
has "$en_unread" 'Reason: the approval record cannot be read.' || { ok_en=0; bad "English template: unreadable" "$en_unread"; }
for needle in 'After the last change these wait for approval (6):' '- "T a1" (a1), reopened. Accountable: anna@example.com.' '- "T a2" (a2), draft. Accountable: anna@example.com.'; do
  has "$en_list" "$needle" || { ok_en=0; bad "English template: $needle" "$en_list"; }; done
for needle in 'Waiting for approval (2):' 'Open Claude in the department folder and write: what do I have today.'; do
  has "$en_digest" "$needle" || { ok_en=0; bad "English template: $needle" "$en_digest"; }; done
has "$(fake test en '{}')" 'This is a test message from hg. The connection to Slack works.' || { ok_en=0; bad "English template: test"; }
has "$(fake address en '"nobody"')" 'not given' || { ok_en=0; bad "English template: not given"; }
[ $ok_en = 1 ] && ok "the English templates, word for word"

payload="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg notify test 2>/dev/null | tr -d '\r')"
printf '%s' "$payload" | jtrue 'list(d) == ["text"]' && ok "the payload has the one key text" || bad "the payload has the one key text" "$payload"
printf '%s' "$payload" | $PY -c 'import sys; b=sys.stdin.buffer.read(); sys.exit(0 if b and all(c < 128 for c in b) else 1)' \
  && ok "the payload is plain ASCII" || bad "the payload is plain ASCII" "$payload"

c="$(fake clean '"Plan <!channel> now"')"
t '! has "$c" "<!" && ! has "$c" "<" && ! has "$c" ">"' "a title with <!channel> cannot notify the channel" "$c"
c="$(fake clean '"Ask <@U123> today"')"
t '! has "$c" "<@" && ! has "$c" "@" && has "$c" "(at)U123"' "a title with <@U123> cannot mention anyone" "$c"
c="$(fake clean '"See <https://x.example/a|here>"')"
t '! has "$c" "<" && ! has "$c" ">" && ! has "$c" "|"' "a title with a link in angle brackets loses the brackets" "$c"
c="$(fake clean '"Open https://x.example/a and ftp://y"')"
t '! has "$c" "://" && has "$c" "x.example/a"' "a title with https:// loses the scheme" "$c"
c="$(fake clean '"Plan https:/a:///evil.example/login and hthttps://tps://x.example/b"')"
t '! has "$c" "://" && has "$c" "evil.example/login"' "a scheme rebuilt from the text around a removed one is removed too" "$c"
c="$(fake clean '"one\ntwo\r\nthree four"')"
t '[ "$c" = "one two three four" ]' "a title with a line break stays on one line" "$c"
c="$(fake clean '"abc‮def​ghi"')"
t '[ "$c" = "abc def ghi" ]' "a title with a direction override loses it" "$c"
c="$(fake clean '"a\"b„c”d«e»f“g"')"
t '[ "$c" = "a'"'"'b'"'"'c'"'"'d'"'"'e'"'"'f'"'"'g" ]' "a title cannot close the quotes of the template" "$c"
m="$(fake gate pl "$(G q draft '"x”. Odpowiada: ktos@example.com „y"')")"
has "$m" '„x'"'"'. Odpowiada: ktos(at)example.com '"'"'y” (q)' && ok "a title with the template's own quotes stays inside them" || bad "a title with the template's own quotes stays inside them" "$m"
c="$(fake clean '"*bold* _it_ ~gone~ `code` a|b"')"
t '! printf "%s" "$c" | grep -q "[*_~\`|]"' "a title with * _ ~ and a backtick carries no markup" "$c"
c="$(fake clean '"R&D &amp; more"')"
t '[ "$c" = "R&amp;D &amp;amp; more" ]' "an ampersand is escaped once" "$c"
long='"'"$(printf 'word %.0s' $(seq 1 40))"'"'
n="$(fake len "$long")"; c="$(fake clean "$long")"
t '[ "$n" = 80 ] && [ "${c%…}" != "$c" ]' "a long title is cut to 80" "$n $c"   # a suffix test: it also holds in a C locale, where the last "character" is one byte
c="$(fake clean '"'"$(printf 'R&D%.0s' $(seq 1 30))"'"')"
t '! printf "%s" "$c" | grep -qE "&[a-z]*…$"' "a cut never leaves half an escape" "$c"
a1="$(fake address en '"anna@example.com, jan@example.com"')"; a2="$(fake address en '""')"; a3="$(fake address en '"<!here>@example.com"')"
t '[ "$a1" = "not given" ] && [ "$a2" = "not given" ] && [ "$a3" = "not given" ]' "an accountable value that is not one address reads 'not given'" "$a1 / $a2 / $a3"
m="$(fake gate en "$(G q reopened '"See https://x.example/a, www.example.com/b"' 'mailto:x@example.com' '[{"path": "a", "why": "changed"}]')")"
t '! has "$m" "://" && ! has "$m" "<" && ! has "$m" "mailto:"' "the message never holds a link" "$m"

# ===== sending, and what happens to the webhook address ==============================
cat > "$TMP/send.py" <<'PY'
import http.server, io, os, sys, threading, urllib.error
sys.path.insert(0, sys.argv[1])
import notify
mode, url = sys.argv[2], sys.argv[3]
calls, sleeps = [], []
class Resp:
    def __enter__(self): return self
    def __exit__(self, *a): return False
class Stub:
    def __init__(self, answers): self.answers = list(answers)
    def open(self, req, timeout=None):
        calls.append(req.full_url)
        a = self.answers.pop(0)
        if a == 200:
            return Resp()
        if a == "net":
            raise urllib.error.URLError("no route to " + req.full_url)
        raise urllib.error.HTTPError(req.full_url, a, "error at " + req.full_url, {}, io.BytesIO(req.full_url.encode()))
payload = notify.CHANNEL["payload"]("x")
nap = lambda s: sleeps.append(s)
if mode == "http":
    rc = notify.deliver([payload], url, Stub([403]), nap); print("rc=%d calls=%d" % (rc, len(calls)))
elif mode == "net":
    rc = notify.deliver([payload], url, Stub(["net", "net"]), nap); print("rc=%d calls=%d sleeps=%s" % (rc, len(calls), sleeps))
elif mode == "retry":
    rc = notify.deliver([payload, payload], url, Stub([500, 200, 200]), nap); print("rc=%d calls=%d sleeps=%s" % (rc, len(calls), sleeps))
elif mode == "strip":
    os.environ[notify.SECRET_ENV] = url + "\n"
    got = notify.take_secret()
    rc = notify.deliver([payload], got, Stub([200]), nap)
    print("rc=%d calls=%d same=%s left=%s" % (rc, len(calls), calls == [url], notify.SECRET_ENV in os.environ))
elif mode == "redirect":
    hits = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(self.path)
            self.send_response(302 if self.path == "/start" else 200)
            self.send_header("Location", "/elsewhere"); self.send_header("Content-Length", "0"); self.end_headers()
        do_GET = do_POST
        def log_message(self, *a): pass
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for k in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        os.environ.pop(k, None)
    os.environ["no_proxy"] = "127.0.0.1,localhost"   # also keeps a proxy from the Windows registry out
    problem = notify.send(payload, "http://127.0.0.1:%d/start" % server.server_port, sleep=nap)
    server.shutdown()
    print("problem=%s hits=%s" % (problem, hits))
elif mode == "crash":
    os.environ[notify.SECRET_ENV] = url
    os.environ.update({"HG_EVENT": "workflow_dispatch", "HG_MODE": "digest"})
    def boom(*a, **k):
        raise RuntimeError("leaked " + url)
    notify.digest_texts = boom
    print("rc=%d" % notify.ci([]))
PY
sendpy() { (cd "$W" && CLAUDE_PROJECT_DIR="$W" HTTPS_PROXY="$DEAD_PROXY" HTTP_PROXY="$DEAD_PROXY" $PY "$TMP/send.py" "$PLUGIN/tools" "$@") >"$TMP/out" 2>"$TMP/err"; RC=$?
  OUT="$(tr -d '\r' < "$TMP/out")"; ERR="$(cat "$TMP/err")"; printf '%s\n%s\n' "$OUT" "$ERR" >> "$ALL"; }

ci "$M" env KIT_TODAY=2026-11-10 HG_EVENT=workflow_dispatch HG_MODE=digest $PY "$NOTIFY" ci
{ [ $RC -eq 0 ] && has "$ERR" "is not set, so 1 message(s) were skipped"; } && ok "ci without the secret exits 0 and says how many messages were skipped" || bad "ci without the secret exits 0 and says how many messages were skipped (rc=$RC)" "$ERR"
ci "$M" env HG_EVENT=workflow_dispatch HG_MODE=test $PY "$NOTIFY" ci
t '[ $RC -eq 1 ]' "ci in test mode without the secret exits 1" "rc=$RC $ERR"
ci "$M" env HG_SLACK_WEBHOOK_URL="$HOOK" HG_EVENT=workflow_dispatch HG_MODE=test $PY "$NOTIFY" ci --dry-run
{ [ $RC -eq 0 ] && [ "$(count "$OUT")" = 1 ] && has "$(printf '%s\n' "$OUT" | texts)" 'To jest wiadomość próbna z hg.' \
  && ! has "$OUT$ERR" "$CANARY" && ! has "$ERR" "delivered"; } \
  && ok "ci --dry-run prints the payload and never sends or prints the secret" || bad "ci --dry-run prints the payload and never sends or prints the secret (rc=$RC)" "$OUT $ERR"

MARK="$TMP/leaked"; RAN="$TMP/hook-ran"
printf '#!/bin/sh\n: > "%s"\n[ -n "${HG_SLACK_WEBHOOK_URL:-}" ] && : > "%s"\nexit 0\n' "$RAN" "$MARK" > "$W/.git/hooks/post-checkout"
chmod +x "$W/.git/hooks/post-checkout"
(cd "$W" && HG_SLACK_WEBHOOK_URL="$HOOK" git worktree add -q --detach "$TMP/control" HEAD >/dev/null 2>&1)
control=no; [ -e "$MARK" ] && control=yes
git -C "$W" worktree remove --force "$TMP/control"; rm -f "$MARK" "$RAN"
ci "$W" env HG_SLACK_WEBHOOK_URL="$HOOK" HG_EVENT=push HG_BEFORE="$C0" HG_AFTER="$C1" $PY "$NOTIFY" ci --dry-run
{ [ "$control" = yes ] && [ -e "$RAN" ] && [ ! -e "$MARK" ] && [ $RC -eq 0 ] && [ "$(count "$OUT")" = 1 ]; } \
  && ok "git child processes of ci do not get the secret" || bad "git child processes of ci do not get the secret (control=$control rc=$RC)" "$OUT $ERR"
rm -f "$W/.git/hooks/post-checkout"

ci "$M" env HG_SLACK_WEBHOOK_URL="https://example.com/hook/$CANARY" HG_EVENT=workflow_dispatch HG_MODE=test $PY "$NOTIFY" ci
{ [ $RC -eq 1 ] && has "$ERR" "does not look like a Slack webhook address" && ! has "$OUT$ERR" "$CANARY"; } \
  && ok "a secret that is not a Slack address is refused and not printed" || bad "a secret that is not a Slack address is refused and not printed (rc=$RC)" "$ERR"
sendpy strip "$HOOK"
t '[ $RC -eq 0 ] && has "$OUT" "rc=0 calls=1 same=True left=False"' "a secret with a trailing line break is accepted after stripping" "$OUT $ERR"
ci "$M" env HG_SLACK_WEBHOOK_URL="https://hooks.""slack.com/services/TQ0A B/$CANARY" HG_EVENT=workflow_dispatch HG_MODE=test $PY "$NOTIFY" ci
{ [ $RC -eq 1 ] && has "$ERR" "Paste it again on GitHub" && ! has "$OUT$ERR" "$CANARY"; } \
  && ok "a secret with a space inside is refused, and the message says to paste it again" || bad "a secret with a space inside is refused, and the message says to paste it again (rc=$RC)" "$ERR"
sendpy http "$HOOK"
{ has "$OUT" "rc=1 calls=1" && has "$ERR" "Slack answered with HTTP 403" && ! has "$ERR" "error at"; } \
  && ok "an HTTP error exits 1 and prints only the status number" || bad "an HTTP error exits 1 and prints only the status number" "$OUT $ERR"
sendpy net "$HOOK"
{ has "$OUT" "rc=1 calls=2" && has "$ERR" "(URLError)" && ! has "$ERR" "no route"; } \
  && ok "a network error exits 1 and prints only the class name" || bad "a network error exits 1 and prints only the class name" "$OUT $ERR"
sendpy retry "$HOOK"
t 'has "$OUT" "rc=0 calls=3 sleeps=[2, 1]"' "one retry after a 500, then success" "$OUT $ERR"
sendpy redirect "$HOOK"
t 'has "$OUT" "problem=Slack answered with HTTP 302 hits=['"'"'/start'"'"']"' "no redirect is followed" "$OUT $ERR"
sendpy crash "$HOOK"
{ has "$OUT" "rc=1" && has "$ERR" "unexpected error: RuntimeError" && ! has "$ERR" "leaked"; } \
  && ok "an unexpected error in ci prints only its class name and exits 1" || bad "an unexpected error in ci prints only its class name and exits 1" "$OUT $ERR"
ci "$M" env HG_SLACK_WEBHOOK_URL="$HOOK" HG_EVENT=pull_request $PY "$NOTIFY" ci
t '[ $RC -eq 2 ]' "an unknown HG_EVENT is a usage error" "rc=$RC $ERR"
ci "$W" env HG_EVENT=push HG_BEFORE= HG_AFTER="$C1" $PY "$NOTIFY" ci
t '[ $RC -eq 2 ]' "a push event with a missing SHA is a usage error" "rc=$RC $ERR"
mkdir -p "$TMP/plain"
ci "$TMP/plain" env HG_SLACK_WEBHOOK_URL="$HOOK" HG_EVENT=workflow_dispatch HG_MODE=test $PY "$NOTIFY" ci
t '[ $RC -eq 0 ]' "outside a department repo ci exits 0" "rc=$RC $ERR"
out="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg notify ci 2>&1)"; rc=$?
t '[ $rc -eq 2 ]' "hg-tool notify ci is refused: only CI posts" "$out"
has "$(cat "$ALL")" "$CANARY" && bad "the address appears in no output of any case above" "$(grep -F "$CANARY" "$ALL")" || ok "the address appears in no output of any case above"

# ===== the copies and the workflow ==============================================================
F="$TMP/fresh"
out="$(hg setup --root "$F" --name Fresh)"
ok_c=1
for f in scan.py notify.py gate.py canonicalize.py kit_registry.py; do
  printf '%s' "$out" | grep -q $'^created\t.github/hg/'"$f"'$' || { ok_c=0; bad "setup copies $f" "$out"; }
done
[ $ok_c = 1 ] && ok "setup copies the five tools CI needs"
ok_c=1
for f in scan.py notify.py gate.py canonicalize.py kit_registry.py; do
  cmp -s "$PLUGIN/tools/$f" "$F/.github/hg/$f" || { ok_c=0; bad "the copy of $f is identical"; }
done
[ $ok_c = 1 ] && ok "each copy is identical to the plugin's file"
printf '%s' "$out" | grep -q $'^created\t.github/workflows/hg-notify.yml$' && ok "setup adds hg-notify.yml" || bad "setup adds hg-notify.yml" "$out"
cmp -s "$PLUGIN/templates/workspace/.github/workflows/hg-notify.yml" "$F/.github/workflows/hg-notify.yml" && ok "the workflow is the template's" || bad "the workflow is the template's"
out="$(cd "$F" && env -u HG_TOOLS -u CLAUDE_PROJECT_DIR $PY .github/hg/notify.py digest 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the copy runs on its own, from a clone with no plugin" "$out"
git -C "$F" add -A
out="$(cd "$F" && CLAUDE_PROJECT_DIR="$F" hg scan --git 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "a fresh workspace still passes its own scan" "$out"
out="$(cd "$F" && env -u HG_TOOLS -u CLAUDE_PROJECT_DIR $PY .github/hg/scan.py --git 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the scan copy passes the other copies" "$out"

dstat() { hg doctor --root "$F" | tr -d '\r' | grep $'\tnotify\t'; }
line="$(dstat)"
t 'has "$line" "OK"' "doctor says OK notify on a fresh workspace" "$line"
printf '# changed\n' >> "$F/.github/hg/gate.py"
line="$(dstat)"
t 'has "$line" "WARN" && has "$line" "gate.py"' "doctor warns when a copy differs" "$line"
out="$(hg setup --root "$F" --refresh-ci)"; rc=$?
{ [ $rc -eq 0 ] && printf '%s' "$out" | grep -q $'^updated\t.github/hg/gate.py$' && cmp -s "$PLUGIN/tools/gate.py" "$F/.github/hg/gate.py" \
  && printf '%s' "$out" | grep -q $'^skipped\t.github/hg/scan.py$'; } \
  && ok "--refresh-ci replaces a changed copy" || bad "--refresh-ci replaces a changed copy (rc=$rc)" "$out"
rm "$F/.github/workflows/hg-notify.yml"
line="$(dstat)"
t 'has "$line" "WARN" && has "$line" "hg-notify.yml is missing"' "doctor warns when the workflow is missing" "$line"
printf '# mine\n' >> "$F/.github/workflows/hg-scan.yml"
out="$(hg setup --root "$F" --refresh-ci)"
{ printf '%s' "$out" | grep -q $'^created\t.github/workflows/hg-notify.yml$' && printf '%s' "$out" | grep -q $'^skipped\t.github/workflows/hg-scan.yml$' \
  && grep -q '# mine' "$F/.github/workflows/hg-scan.yml"; } \
  && ok "--refresh-ci creates a missing workflow and never replaces an existing one" || bad "--refresh-ci creates a missing workflow and never replaces an existing one" "$out"
printf '# changed\n' >> "$F/.github/hg/notify.py"
out="$(hg setup --root "$F" --refresh-scan)"; rc=$?
{ [ $rc -eq 0 ] && printf '%s' "$out" | grep -q $'^updated\t.github/hg/notify.py$' && cmp -s "$PLUGIN/tools/notify.py" "$F/.github/hg/notify.py"; } \
  && ok "--refresh-scan still works, as the same thing" || bad "--refresh-scan still works, as the same thing (rc=$rc)" "$out"
out="$(hg doctor --root "$F" | tr -d '\r')"
has "$out" "notify-" && bad "doctor prints no secret line without a GitHub origin" "$out" || ok "doctor prints no secret line without a GitHub origin"

git -C "$F" remote add origin https://github.com/acme/notes.git
st() { (cd "$F" && CLAUDE_PROJECT_DIR="$F" GH_STUB="$1" hg notify status | tr -d '\r'); }
out="$(st secret,green)"; rc=$?
{ printf '%s\n' "$out" | grep -qxF $'OK\tnotify-secret\ta repository secret named HG_SLACK_WEBHOOK_URL exists. Its value cannot be read from here.'; } \
  && ok "notify status reports the secret as set, by name" || bad "notify status reports the secret as set, by name" "$out"
run_line="$(printf '%s\n' "$out" | grep $'\tnotify-run\t')"
{ has "$run_line" $'OK\tnotify-run\tlast run 2026-11-09 (schedule) did not fail.' && has "$run_line" "not proof of delivery" \
  && ! has "$run_line" "succeeded" && ! has "$run_line" "was delivered"; } \
  && ok "a green last run is reported as 'did not fail', never as delivered" || bad "a green last run is reported as 'did not fail', never as delivered" "$run_line"
out="$(st none)"
line="$(printf '%s\n' "$out" | grep $'\tnotify-secret\t')"
{ has "$line" "WARN" && has "$line" "no repository secret named HG_SLACK_WEBHOOK_URL was found" && has "$line" "An organization secret cannot be seen from here" \
  && has "$line" "https://github.com/acme/notes/settings/secrets/actions/new"; } \
  && ok "notify status reports the secret as not found, says an organization secret cannot be seen, and gives the settings link" \
  || bad "notify status reports the secret as not found, says an organization secret cannot be seen, and gives the settings link" "$out"
out="$(st nosign)"
has "$out" $'WARN\tnotify-secret\tcould not be checked: gh is not signed in or has no access to acme/notes.' && ok "notify status says when gh cannot check" || bad "notify status says when gh cannot check" "$out"
out="$(st secret,failed)"
has "$out" $'WARN\tnotify-run\tlast run 2026-11-09 (push) failed: a message was not delivered.' && ok "notify status reports a failed last run" || bad "notify status reports a failed last run" "$out"
out="$(st secret,cancelled)"
has "$out" $'WARN\tnotify-run\tlast run 2026-11-09 (push) was cancelled' && ok "notify status reports a cancelled last run as a warning" || bad "notify status reports a cancelled last run as a warning" "$out"
out="$(st secret,skipped5)"
has "$out" $'WARN\tnotify-run\tlast run 2026-11-03 (push) failed' && ok "notify status skips five skipped runs and finds the failed one behind them" || bad "notify status skips five skipped runs and finds the failed one behind them" "$out"
out="$(cd "$F" && CLAUDE_PROJECT_DIR="$F" HG_GH="$TMP/no-such-gh" hg notify status | tr -d '\r')"
has "$out" "notify-" && bad "without gh, status stops after the files" "$out" || ok "without gh, status stops after the files"
out="$(hg doctor --root "$F" | tr -d '\r')"
has "$out" $'\tnotify-secret\t' && ok "doctor prints the secret line with a GitHub origin" || bad "doctor prints the secret line with a GitHub origin" "$out"

TOKEN="gh""p_""$(printf 'Ab1%.0s' $(seq 1 12))"
git -C "$F" remote set-url origin "https://x-access-token:$TOKEN@github.com/acme/notes.git"
: > "$TMP/gh.log"
out="$(cd "$F" && CLAUDE_PROJECT_DIR="$F" GH_STUB=secret GH_LOG="$TMP/gh.log" hg notify status 2>&1; hg doctor --root "$F" 2>&1)"
{ has "$out" "acme/notes" || has "$(cat "$TMP/gh.log")" "-R acme/notes"; } && ! has "$out$(cat "$TMP/gh.log")" "$TOKEN" \
  && ok "an origin with a token in it is never printed" || bad "an origin with a token in it is never printed" "$out"

wf="$PLUGIN/templates/workspace/.github/workflows/hg-notify.yml"
scanwf="$PLUGIN/templates/workspace/.github/workflows/hg-scan.yml"
t '! grep -qE "^[[:space:]]*(pull_request|pull_request_target|workflow_run|issue_comment|pull_request_review[a-z_]*):" "$wf"' "the workflow has no pull_request trigger"
t '! grep -qE "^[[:space:]]*concurrency:" "$wf"' "the workflow has no concurrency key"
sec="$(grep -n 'secrets\.' "$wf")"
envline="$(grep -n '^        env:$' "$wf" | cut -d: -f1)"
{ [ "$(printf '%s\n' "$sec" | grep -c .)" = 1 ] && has "$sec" '          HG_SLACK_WEBHOOK_URL: ${{ secrets.HG_SLACK_WEBHOOK_URL }}' \
  && [ "$(printf '%s\n' "$envline" | grep -c .)" = 1 ] && [ "${sec%%:*}" -gt "$envline" ]; } \
  && ok "the workflow names the secret once, in one step's env" || bad "the workflow names the secret once, in one step's env" "$sec / env at $envline"
t '! grep -q "secrets\." "$scanwf"' "hg-scan.yml names no secret"
runs="$(grep -E '^[[:space:]]*run:' "$wf")"
{ [ "$(printf '%s\n' "$runs" | grep -c .)" = 1 ] && has "$runs" 'run: python .github/hg/notify.py ci' && ! has "$runs" '${{'; } \
  && ok "the workflow passes event values through env, not through the run line" || bad "the workflow passes event values through env, not through the run line" "$runs"
SETUP="$PLUGIN/skills/setup/SKILL.md"
grep -qF 'never pasted into the chat' "$SETUP" && ok "the setup skill says the address is never pasted into the chat" || bad "the setup skill says the address is never pasted into the chat"
grep -q 'hg-tool setup --refresh-ci' "$SETUP" && ok "/hg:setup --update refreshes the copies" || bad "/hg:setup --update refreshes the copies"
out="$(cd "$REPO_ROOT" && hg scan plugins/hg/tools/notify.py plugins/hg/templates/workspace/.github tests/notify 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "no new file holds anything shaped like a webhook address" "$out"
out="$(grep -nE '^(from|import) ' "$NOTIFY" | grep -vE 'import (datetime|hashlib|http\.client|json|os|re|shlex|shutil|subprocess|sys|tempfile|time|unicodedata|urllib\.error|urllib\.request)$|^[0-9]+:from pathlib import Path$|import (gate|kit_registry as kr)  # noqa: E402$')"
t '[ -z "$out" ]' "the notifier imports only the standard library and its two neighbors" "$out"
out="$(grep -n $'\xe2\x80\x94' "$NOTIFY" "$wf" "$REPO_ROOT/tests/notify/test-notify.sh" "$SETUP" "$PLUGIN/skills/doctor/SKILL.md")"
t '[ -z "$out" ]' "no em dashes" "$out"

echo "notify: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
