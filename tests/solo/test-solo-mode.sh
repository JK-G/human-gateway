#!/usr/bin/env bash
# test-solo-mode.sh - a personal folder that is silent: the mode, hg-tool setup --personal, the session rules, what
# today-data, the dashboard, the node list and doctor show there, git used silently or not at all, the guard, and the
# word list over every output and every file setup creates. Also: the two allow rules for writes in both modes, with
# the deny rules still winning. Self-contained, no network, no model. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TOOLS="$PLUGIN/tools"
WORDS="$REPO_ROOT/tests/solo/words.py"
TMP="$(temp_dir hg-solo-mode)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR OneDrive OneDriveCommercial OneDriveConsumer
export CLAUDE_PLUGIN_DATA="$TMP/data"   # the places file of this test, never the user's own cache
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { printf '%s' "$1" | grep -qF -- "$2"; }
psetup() { hg setup --personal --new "$@"; }   # --new: the place check has its own tests below
in_dir() { local d="$1"; shift; (cd "$d" && CLAUDE_PROJECT_DIR="$d" hg "$@"); }
fingerprint() {  # one hash over every path and its bytes, .git excluded
  $PY -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1])
rows=sorted("%s %s"%(p.relative_to(r).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for p in r.rglob("*") if p.is_file() and ".git" not in p.relative_to(r).parts)
print(hashlib.sha256("\n".join(rows).encode()).hexdigest())' "$1" | tr -d '\r'
}
words_ok() {  # words_ok <file> <label> [allowed patterns]: 0 hits of the word list
  local out; out="$($PY "$WORDS" "$1" "${3:-}")"
  [ $? -eq 0 ] && ok "no forbidden word: $2" || bad "no forbidden word: $2" "$out"
}
nogit() {  # nogit <tool.py> [args]: run a tool with every start of git failing as if git were not installed
  $PY -c 'import subprocess, sys, shutil, runpy, os
real = subprocess.run
def run(cmd, *a, **k):
    if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
        if os.environ.get("NOGIT_LOG"):  # each start that was stopped, one line
            with open(os.environ["NOGIT_LOG"], "a") as fh: fh.write(" ".join(map(str, cmd)) + "\n")
        raise FileNotFoundError("git")
    return real(cmd, *a, **k)
subprocess.run = run
which = shutil.which
shutil.which = lambda n, *a, **k: None if n == "git" else which(n, *a, **k)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")' "$@"
}
fakegit() {  # fakegit <log> <command...>: run a command with a git first on PATH that records each start and fails
  local bin pbin; bin="$TMP/fakegit-bin"; mkdir -p "$bin"
  printf '#!/bin/sh\necho "$@" >> "%s"\nexit 127\n' "$1" > "$bin/git"; chmod +x "$bin/git"
  # PATH takes the POSIX form: the colon of C:/... would split the entry on Windows and the real git would run.
  pbin="$(cygpath -u "$bin" 2>/dev/null || printf '%s' "$bin")"
  local log="$1"; shift; PATH="$pbin:$PATH" "$@"
}
lines_of() { printf '%s\n' "$1" | grep "^$2	" | cut -f2-; }

# ===== 1. the mode ===================================================================================
mode_of() { $PY -c 'import json,sys; sys.path.insert(0, sys.argv[1]); import solo
d = json.loads(sys.argv[2]) if sys.argv[2] != "BROKEN" else "x"
print(solo.mode_of(d))' "$TOOLS" "$1"; }
t '[ "$(mode_of '"'"'{"mode": "personal"}'"'"')" = personal ]' "mode_of: the exact string is personal"
for case in '{}' '{"mode": "Personal"}' '{"mode": true}' '{"mode": "shared"}' '[1]' 'BROKEN'; do
  t '[ "$(mode_of "$case")" = shared ]' "mode_of: $case is shared"
done
B="$TMP/broken"; mkdir -p "$B/.claude"; printf '{ "mode": "personal", ' > "$B/.claude/hg.json"
t '[ "$(in_dir "$B" mode)" = shared ]' "a broken hg.json is shared"
E="$TMP/empty"; mkdir -p "$E"
out="$(in_dir "$E" mode)"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = none ]' "hg-tool mode prints none without hg.json" "rc=$rc $out"

# ===== 2. setup --personal in an empty folder ==========================================================
P="$TMP/moje notatki"
out="$(psetup --root "$P" --language pl)"; rc=$?
SETUP_PL="$out"
t '[ $rc -eq 0 ]' "setup --personal succeeds in an empty folder" "$out"
conf="$(cat "$P/.claude/hg.json")"
printf '%s' "$conf" | jtrue 'd["mode"]=="personal" and d["timezone"]=="local" and d["language"]["content"]=="pl" and d["projectName"]=="moje notatki"' \
  && ok "hg.json says personal, local time and the language" || bad "hg.json says personal, local time and the language" "$conf"
for f in .claude/hg.json .claude/settings.json .gitignore .gitattributes CLAUDE.md CLAUDE.local.md vault/CLAUDE.md vault/README.md \
         vault/cleaning.md vault/raw/README.md vault/inbox/_template.md intake/README.md vault/daily/README.md vault/journal/README.md \
         vault/index.md vault/wiki/memory/index.md vault/projects/_template/CLAUDE.md vault/schema.md vault/wiki/TAGS.md; do
  [ -f "$P/$f" ] && ok "created $f" || bad "created $f" "$out"
done
for f in AGENTS.md gates/README.md .github .claude/skills/setup/SKILL.md; do
  [ ! -e "$P/$f" ] && ok "not created in a personal folder: $f" || bad "not created in a personal folder: $f"
done
for f in vault/CLAUDE.md vault/cleaning.md intake/README.md vault/index.md vault/projects/_template/CLAUDE.md; do
  cmp -s "$P/$f" "$PLUGIN/templates/personal/$f" && ok "the personal text of $f" || bad "the personal text of $f" "$(head -n 3 "$P/$f")"
done
grep -q '^# moje notatki$' "$P/CLAUDE.md" && grep -qF 'in pl, in plain words' "$P/CLAUDE.md" && ok "CLAUDE.md has the name and the language" || bad "CLAUDE.md has the name and the language"
grep -qxF '@CLAUDE.local.md' "$P/CLAUDE.md" && grep -qxF '@vault/wiki/memory/index.md' "$P/CLAUDE.md" && ok "CLAUDE.md imports the person's rules and the memory" || bad "CLAUDE.md imports the person's rules and the memory"
grep -q "^# Moje zasady dla Claude'a$" "$P/CLAUDE.local.md" && ok "CLAUDE.local.md in the content language" || bad "CLAUDE.local.md in the content language" "$(cat "$P/CLAUDE.local.md")"
t '[ -d "$P/.git" ]' "git started silently"
t '! git -C "$P" rev-parse -q --verify HEAD >/dev/null 2>&1' "nothing was committed"
settings="$(cat "$P/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'all(r in d["permissions"]["allow"] for r in ["Bash(hg-tool *)","Edit(vault/**)","Edit(.gateway/**)"])' \
  && ok "the two allow rules for writes are in settings.json" || bad "the two allow rules for writes are in settings.json" "$settings"
$PY -c 'import json,sys
want=json.load(open(sys.argv[1],encoding="utf-8"))["permissions"]
have=json.load(open(sys.argv[2],encoding="utf-8"))["permissions"]
sys.exit(0 if all(r in have[k] for k in ("allow","ask","deny") for r in want[k]) else 1)' "$PLUGIN/templates/workspace/.claude/settings.json" "$P/.claude/settings.json" \
  && ok "every template allow, ask and deny rule is there" || bad "every template allow, ask and deny rule is there" "$settings"
for f in CLAUDE.local.md vault/raw/x/sources/x.md vault/inbox/x.md intake/x.md DASHBOARD.md .gateway/x .claude/skills/my-own/SKILL.md; do
  git -C "$P" check-ignore -q "$f" && ok "ignored: $f" || bad "ignored: $f"
done
git -C "$P" check-ignore -q .claude/skills/setup/SKILL.md && bad "only .claude/skills/my-*/ is ignored" || ok "only .claude/skills/my-*/ is ignored"
real() { $PY -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve().as_posix())' "$1" | tr -d '\r'; }
t '[ "$(cat "$CLAUDE_PLUGIN_DATA/places" 2>/dev/null | tr -d "\r")" = "$(real "$P")" ]' "the folder is recorded as a place for notes" "$(cat "$CLAUDE_PLUGIN_DATA/places" 2>&1)"

# ===== 3. a second run changes nothing ===================================================================
before="$(fingerprint "$P")"
out="$(psetup --root "$P" --language en)"; rc=$?
t '[ $rc -eq 0 ] && [ "$before" = "$(fingerprint "$P")" ]' "a second run changes no file" "$out"
t '! printf "%s\n" "$out" | grep -q "^context	" && ! printf "%s\n" "$out" | grep -q "^say	"' "a second run prints no context and no say line" "$out"
has "$out" $'skipped\t.claude/hg.json' && has "$out" $'mode\tpersonal' && ok "a second run says the folder was there and is personal" || bad "a second run says the folder was there and is personal" "$out"
out="$(hg setup --root "$P")"
t '[ ! -e "$P/AGENTS.md" ] && [ ! -e "$P/.github" ] && ! printf "%s" "$out" | grep -q "^created"' "plain setup in a personal folder uses the personal file set" "$out"
out="$(hg setup --root "$P" --refresh-ci)"; rc=$?
t '[ $rc -eq 0 ] && [ ! -e "$P/.github" ]' "--refresh-ci in a personal folder copies nothing for CI" "rc=$rc $out"

# ===== 4. --focus and slugs ===============================================================================
out="$(psetup --root "$P" --focus 'Wdrożenie cennika: progi rabatów')"; rc=$?
t '[ $rc -eq 0 ]' "--focus in an existing personal folder" "$out"
cat "$P/.claude/hg.json" | jtrue 'd["projects"]==["wdrozenie-cennika-progi-rabatow"] and d["mode"]=="personal"' \
  && ok "the topic is a project, the mode stays" || bad "the topic is a project, the mode stays" "$(cat "$P/.claude/hg.json")"
t '[ -f "$P/vault/projects/wdrozenie-cennika-progi-rabatow/CLAUDE.md" ]' "the project folder exists"
grep -q '^# Wdrożenie cennika: progi rabatów: project context$' "$P/vault/projects/wdrozenie-cennika-progi-rabatow/CLAUDE.md" \
  && ok "the project keeps the person's words as its name" || bad "the project keeps the person's words as its name"
has "$out" $'project\twdrozenie-cennika-progi-rabatow\tWdrożenie cennika: progi rabatów' && ok "the project line" || bad "the project line" "$out"
says="$(lines_of "$out" say)"
expect="Temat zapisany: Wdrożenie cennika: progi rabatów.
Co możesz teraz zrobić: wklej notatkę albo link i napisz „zapisz”. Zapytaj „co wiemy o…”. Napisz „co mam dziś”.
Powiedz mi, jak mam z Tobą pracować, a zapiszę to w Twoich zasadach.
hg nie robi kopii tych notatek. Jeśli stracisz ten komputer, stracisz je."
t '[ "$says" = "$expect" ]' "S3, S4, S5 and S6, in order, and no S1 on a second run" "$says"
slug() { $PY -c 'import sys; sys.path.insert(0, sys.argv[1]); import solo; print(solo.slugify(sys.argv[2]))' "$TOOLS" "$1"; }
t '[ "$(slug "Łódź, żółć i gęś")" = lodz-zolc-i-ges ]' "slugify: Polish letters" "$(slug "Łódź, żółć i gęś")"
t '[ "$(slug "?!; ...")" = notes ]' "slugify: only punctuation is notes"
t '[ "$(slug cross)" = notes ] && [ "$(slug Unknown)" = notes ]' "slugify: cross and unknown are notes"
long="$(slug "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma")"
t '[ ${#long} -le 40 ] && [ "${long%-}" = "$long" ] && [ "$long" = alpha-beta-gamma-delta-epsilon-zeta-eta ]' "slugify: 90 characters are cut at a hyphen, at most 40" "$long"

# ===== 5. a folder that holds files ========================================================================
U="$TMP/used"; mkdir -p "$U"; printf 'stare\n' > "$U/Notatki 2026.xlsx"; mkdir "$U/stare-notatki"; printf 'x\n' > "$U/stare-notatki/a.txt"
before="$(fingerprint "$U")"
out="$(psetup --root "$U" --language pl)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "$(printf "used\t2")"' "a folder with two entries: used 2, exit 1" "rc=$rc $out"
has "$out" $'ask\tW tym folderze są już pliki (2). Założyć tu miejsce na notatki? Istniejących plików nie zmienię.' && ok "the S7 question" || bad "the S7 question" "$out"
t '[ "$before" = "$(fingerprint "$U")" ] && [ ! -e "$U/.git" ]' "nothing is created" "$(ls -a "$U")"
printf '%s\n' "$out" | grep '^ask	' > "$TMP/s7.txt"; words_ok "$TMP/s7.txt" "the S7 line"
out="$(psetup --root "$U" --language pl --here)"; rc=$?
t '[ $rc -eq 0 ] && [ -f "$U/.claude/hg.json" ]' "with --here the folder is set up" "$out"
excl="$U/.git/info/exclude"
grep -qxF '/Notatki\ 2026.xlsx' "$excl" && grep -qxF '/stare-notatki' "$excl" && ok "both names are in .git/info/exclude" || bad "both names are in .git/info/exclude" "$(cat "$excl")"
found="$(grep -rlF -e 'Notatki 2026' -e 'stare-notatki' "$U" --exclude-dir=.git)"
t '[ -z "$found" ]' "neither name is in a file git could carry" "$found"
git -C "$U" check-ignore -q 'Notatki 2026.xlsx' && git -C "$U" check-ignore -q stare-notatki/a.txt && ok "git ignores both" || bad "git ignores both"
t '[ "$(cat "$U/Notatki 2026.xlsx")" = stare ] && [ "$(cat "$U/stare-notatki/a.txt")" = x ]' "the person's files are not changed"
V="$TMP/has-vault"; mkdir -p "$V/vault"
for flag in "" --here; do
  # shellcheck disable=SC2086
  out="$(psetup --root "$V" --language en $flag)"; rc=$?
  t '[ $rc -eq 1 ] && has "$out" "$(printf "refused\tname\tvault")" && has "$out" "This folder already holds \"vault\", and hg needs that name." && [ ! -e "$V/.claude" ]' \
    "a folder named vault is refused ${flag:-without --here}" "rc=$rc $out"
done

# ===== 6. the word list ======================================================================================
EXCEPT='^(\.gitignore|\.gitattributes|\.claude/settings\.json|\.claude/hg\.json|vault/schema\.md|vault/wiki/TAGS\.md|vault/projects/_template/PRD\.md|vault/projects/README\.md)$'
for lang in pl en; do
  L="$TMP/words-$lang"
  out="$(psetup --root "$L" --language $lang --focus 'Nowy cennik')"; rc=$?
  t '[ $rc -eq 0 ]' "$lang: setup with a topic" "$out"
  printf '%s\n' "$out" | grep -E '^(say|ask)	' > "$TMP/say-$lang.txt"; words_ok "$TMP/say-$lang.txt" "$lang: the say lines of setup"
  printf '%s\n' "$out" | grep '^context	' > "$TMP/ctx-$lang.txt"; words_ok "$TMP/ctx-$lang.txt" "$lang: the context lines of setup" '\bgit\b'
  in_dir "$L" session-start > "$TMP/ss-$lang.txt"; words_ok "$TMP/ss-$lang.txt" "$lang: session-start" '\bgit\b'
  in_dir "$L" today-data > "$TMP/td-$lang.txt"; words_ok "$TMP/td-$lang.txt" "$lang: today-data, keys included"
  (cd "$L" && CLAUDE_PROJECT_DIR="$L" bash "$HG_TOOL" dashboard); words_ok "$L/DASHBOARD.md" "$lang: DASHBOARD.md"
  in_dir "$L" nodes > "$TMP/n-$lang.txt"; words_ok "$TMP/n-$lang.txt" "$lang: nodes"
  in_dir "$L" nodes --json > "$TMP/nj-$lang.txt"; words_ok "$TMP/nj-$lang.txt" "$lang: nodes --json"
  in_dir "$L" doctor > "$TMP/dr-$lang.txt"; words_ok "$TMP/dr-$lang.txt" "$lang: doctor" '\bgit\b'
  in_dir "$L" index >/dev/null; words_ok "$L/vault/index.md" "$lang: vault/index.md after hg-tool index"
  hits=""
  while IFS= read -r f; do
    rel="${f#"$L"/}"
    printf '%s' "$rel" | grep -qE "$EXCEPT" && continue
    r="$($PY "$WORDS" "$f")" || hits="$hits
$rel: $r"
  done < <(find "$L" -path "$L/.git" -prune -o -type f -print)
  t '[ -z "$hits" ]' "$lang: every file setup created holds no forbidden word" "$hits"
done
cmp -s "$TMP/words-pl/vault/index.md" "$PLUGIN/templates/personal/vault/index.md" && ok "the personal index template is what hg-tool index writes" || bad "the personal index template is what hg-tool index writes" "$(diff "$TMP/words-pl/vault/index.md" "$PLUGIN/templates/personal/vault/index.md")"
hits=""
while IFS= read -r f; do r="$($PY "$WORDS" "$f")" || hits="$hits
${f#"$PLUGIN"/}: $r"; done < <(find "$PLUGIN/templates/personal" -type f)
t '[ -z "$hits" ]' "every file of templates/personal holds no forbidden word" "$hits"
out="$(grep -rn $'\xe2\x80\x94' "$PLUGIN/templates/personal" "$TOOLS/solo.py" "$REPO_ROOT/tests/solo" "$PLUGIN/skills/start")"
t '[ -z "$out" ]' "no em dashes in the new files" "$out"
out="$(grep -rnE '(^|[^/])/(today|dayend|ingest|import-source|wiki-query|keep|gate|publish)\b' "$PLUGIN/templates/personal" | grep -vE 'vault/|raw/')"
t '[ -z "$out" ]' "commands in the personal templates carry the hg: prefix" "$out"

# ===== 7. the session rules ====================================================================================
ss="$(in_dir "$P" session-start)"
for needle in hg:keep hg:wiki-query hg:today hg:dayend hg:doctor '"zapisz"' '"zapamiętaj"' '"zachowaj to"' '"keep this"' 'dokończ zapisane' 'finish what I kept' \
  "one person's own second brain" 'Never run a git command in this folder' 'Write to the person in pl, in plain words' \
  'Run hg-tool only with the Bash tool'; do
  has "$ss" "$needle" && ok "session-start says: $needle" || bad "session-start says: $needle" "$ss"
done
for needle in 'intake/links.md' '/hg:init' '/hg:gate' 'Nodes declared' 'hg:publish' 'department' 'gates/'; do
  has "$ss" "$needle" && bad "session-start does not say: $needle" "$ss" || ok "session-start does not say: $needle"
done
F="$TMP/first"
out="$(psetup --root "$F" --language pl --focus 'Wdrożenie cennika')"
printf '%s\n' "$out" | grep '^context	' | cut -f2- > "$TMP/ctx-first.txt"
in_dir "$F" session-start | tr -d '\r' > "$TMP/ss-first.txt"
t '[ -s "$TMP/ctx-first.txt" ] && cmp -s "$TMP/ctx-first.txt" "$TMP/ss-first.txt"' "the context lines of setup equal session-start, line for line" "$(diff "$TMP/ctx-first.txt" "$TMP/ss-first.txt")"
tail_kinds="$(printf '%s\n' "$out" | sed -n '/^context	/,$p' | cut -f1 | uniq | tr '\n' ' ')"
t '[ "$tail_kinds" = "context say " ]' "the run ends with context lines, then say lines" "$tail_kinds"
says="$(lines_of "$out" say)"
t '[ "$(printf "%s\n" "$says" | head -n 1)" = "Gotowe. Ten folder jest teraz Twoim miejscem na notatki i ustalenia. hg zapisuje wszystko w tym folderze i nikomu tego nie przekazuje." ] && [ "$(printf "%s\n" "$says" | wc -l | tr -d " ")" = 5 ]' \
  "S1, then S3 to S6" "$says"
t '[ -z "$(in_dir "$E" session-start)" ]' "session-start is silent in a folder with no hg.json"

# ===== 8. today-data ============================================================================================
data="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" KIT_TODAY=2026-11-17 hg today-data)"
printf '%s' "$data" | jtrue 'd["mode"]=="personal" and d["date"]=="2026-11-17" and not any(k in d for k in ("gates","sources","agent_approvals","unpublished"))' \
  && ok "today-data: personal, the pinned date, and the four keys absent" || bad "today-data: personal, the pinned date, and the four keys absent" "$data"

# ===== 9. nodes ==================================================================================================
out="$(in_dir "$P" nodes)"
t '[ "$(printf "%s\n" "$out" | cut -f1 | tr "\n" " ")" = "calendar backup " ]' "nodes: two lines, calendar and backup" "$out"
has "$out" 'Kopia plików źródłowych: hg jej nie robi. Bez własnej kopii utrata dysku oznacza ich utratę.' && ok "the backup line in its personal wording" || bad "the backup line in its personal wording" "$out"
out="$(in_dir "$P" nodes --json)"
printf '%s' "$out" | jtrue '[n["id"] for n in d]==["calendar","backup"]' && ok "nodes --json: the same two" || bad "nodes --json: the same two" "$out"

# ===== 10. doctor ==================================================================================================
out="$(in_dir "$P" doctor)"; rc=$?
t '[ $rc -eq 0 ]' "doctor passes on a fresh personal folder" "$out"
t '! printf "%s\n" "$out" | grep -qE "	(gh|marketplace|scanner|notify|notify-secret|notify-run|node|gates)	"' "doctor: no gh, marketplace, scanner, notify, node or gate line" "$out"
has "$out" $'OK\tmode\tpersonal: one person\'s own folder. hg sends nothing from it.' && ok "doctor: the mode line" || bad "doctor: the mode line" "$out"
has "$out" $'OK\tcalendar\t' && has "$out" $'OK\tbackup\tBackup of source files: hg makes none.' && ok "doctor: the two nodes under their own ids" || bad "doctor: the two nodes under their own ids" "$out"
has "$out" $'OK\traw\t0 source file(s) in this folder. hg makes no copy of them.' && ok "doctor: the personal raw line" || bad "doctor: the personal raw line" "$out"
C="$TMP/committed"; psetup --root "$C" >/dev/null
git -C "$C" -c user.email=t@example.com -c user.name=t commit -q --allow-empty -m x
out="$(in_dir "$C" doctor)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "$(printf "ERROR\tmode\tthis personal folder holds a change history that hg did not make.")"' "doctor: a history in a personal folder is an error" "rc=$rc $out"
out="$(in_dir "$E" doctor)"; rc=$?
t '[ $rc -eq 1 ] && ! printf "%s\n" "$out" | grep -q "^[A-Z]*	gh	" && ! printf "%s" "$out" | grep -qi department' "doctor with no hg.json: no gh line and no department" "$out"

# ===== 11. no git ==================================================================================================
X="$TMP/no git"
out="$(nogit "$TOOLS/setup_workspace.py" --personal --new --root "$X" --language pl)"; rc=$?
t '[ $rc -eq 0 ] && has "$out" "$(printf "note\tno change history was started here. Nothing in this folder needs it today.")" && [ ! -e "$X/.git" ]' \
  "without git setup --personal succeeds with a note and no .git" "rc=$rc $out"
out="$(nogit "$TOOLS/doctor.py" --root "$X")"; rc=$?
# Without git for Windows there is no Git Bash either, and that stays an error: the plugin cannot start without it.
t 'has "$out" "$(printf "WARN\tgit\tnot found. Nothing in this folder needs it today.")" && ! printf "%s\n" "$out" | grep "^ERROR" | grep -qv "	git-bash	"' \
  "without git doctor only warns about git" "rc=$rc $out"
out="$(CLAUDE_PROJECT_DIR="$X" KIT_TODAY=2026-11-17 nogit "$TOOLS/today_data.py")"
printf '%s' "$out" | jtrue 'd["mode"]=="personal"' && ok "without git today-data works" || bad "without git today-data works" "$out"
out="$(CLAUDE_PROJECT_DIR="$X" nogit "$TOOLS/session_start.py")"
has "$out" "one person's own second brain" && ok "without git session-start works" || bad "without git session-start works" "$out"
printf '{"session_id":"abcdef123456"}' | CLAUDE_PROJECT_DIR="$X" nogit "$TOOLS/journal_append.py"
t 'grep -q "^- [0-9][0-9]:[0-9][0-9] session abcdef12: 0 paths$" "$X"/vault/journal/*.md' "without git the journal hook writes its line" "$(cat "$X"/vault/journal/*.md 2>&1)"
LOG="$TMP/git-starts.log"; : > "$LOG"
fakegit "$TMP/probe.log" git probe >/dev/null 2>&1
t 'grep -qx probe "$TMP/probe.log"' "the recording git is the one a shell under fakegit starts" "$(cat "$TMP/probe.log" 2>&1)"
(cd "$X" && unset CLAUDE_PROJECT_DIR && for c in session-start today-data mode "lock status x" validate-frontmatter; do
   # shellcheck disable=SC2086
   fakegit "$LOG" bash "$HG_TOOL" $c >/dev/null 2>&1
 done)
t '[ ! -s "$LOG" ]' "in a personal folder with no repository the shell entry points start no git" "$(cat "$LOG")"
# The first run in a fresh folder, before hg.json exists: nothing starts git to find the root, in the shell or in
# Python. On a Mac without the developer tools that start opens an install dialog. (setup may still run git init
# where git is usable; only the root lookup is checked.)
FR="$TMP/fresh"; mkdir -p "$FR"; : > "$LOG"
(cd "$FR" && unset CLAUDE_PROJECT_DIR && fakegit "$LOG" bash "$HG_TOOL" mode >/dev/null 2>&1 \
  && fakegit "$LOG" bash "$HG_TOOL" setup --personal --new --language pl >/dev/null 2>&1)
t '! grep -q rev-parse "$LOG" && [ -f "$FR/.claude/hg.json" ]' "a fresh folder: mode and setup --personal ask no git for the root" "$(cat "$LOG")"
FR2="$TMP/fresh-py"; mkdir -p "$FR2"; LOG2="$TMP/git-starts-py.log"; : > "$LOG2"
(cd "$FR2" && unset CLAUDE_PROJECT_DIR && NOGIT_LOG="$LOG2" nogit "$TOOLS/setup_workspace.py" --personal --new --language pl >/dev/null)
t '[ ! -s "$LOG2" ] && [ -f "$FR2/.claude/hg.json" ]' "a fresh folder: setup --personal itself asks no git for the root" "$(cat "$LOG2")"

# ===== 12. raw-add and its privacy rule ============================================================================
printf 'notatka\n' > "$X/intake/a.md"
out="$(cd "$X" && CLAUDE_PROJECT_DIR="$X" hg raw-add intake/a.md --project cross --kind sources --date 2026-11-16 --slug a 2>&1)"; rc=$?
t '[ $rc -eq 0 ] && [ -f "$X/vault/raw/cross/sources/2026-11-16-a.md" ] && [ ! -e "$X/intake/a.md" ]' "raw-add moves the file in a personal folder with no repository" "rc=$rc $out"
cp "$X/.claude/hg.json" "$TMP/x-hg.json"
jedit "$TMP/x-hg.json" "$X/.claude/hg.json" 'd.pop("mode")'
printf 'druga\n' > "$X/intake/b.md"
out="$(cd "$X" && CLAUDE_PROJECT_DIR="$X" hg raw-add intake/b.md --project cross --kind sources --date 2026-11-16 --slug b 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "raw/ is not kept out of git in this folder" && [ -f "$X/intake/b.md" ]' "the same folder with no mode key is refused as before" "rc=$rc $out"
cp "$TMP/x-hg.json" "$X/.claude/hg.json"
out="$(in_dir "$X" raw-add --check)"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "$(printf "private\tyes")" ]' "raw-add --check: a personal folder with no .git" "rc=$rc $out"
out="$(in_dir "$P" raw-add --check)"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "$(printf "private\tyes")" ]' "raw-add --check: a personal folder with .git" "rc=$rc $out"
S="$TMP/shared"; hg setup --root "$S" --name Dept >/dev/null
grep -v '^intake/\*$' "$S/.gitignore" > "$TMP/gi"; cp "$TMP/gi" "$S/.gitignore"
out="$(in_dir "$S" raw-add --check)"; rc=$?
t '[ $rc -eq 1 ] && [ "$out" = "$(printf "private\tno\tintake/x")" ]' "raw-add --check: a shared folder whose .gitignore lost intake/*" "rc=$rc $out"
hg setup --root "$S" >/dev/null

# ===== 13. the journal ================================================================================================
J="$TMP/journal"; psetup --root "$J" >/dev/null
printf '{"session_id":"11111111"}' | CLAUDE_PROJECT_DIR="$J" hg journal
printf 'a\n' > "$J/vault/wiki/concepts/cross--a.md"; printf 'b\n' > "$J/vault/wiki/decisions/cross--b.md"
$PY -c 'import os,sys,time; m=os.stat(sys.argv[1]).st_mtime+5
for p in sys.argv[2:]: os.utime(p,(m,m))' "$J/.claude/state/journal-last-run" "$J/vault/wiki/concepts/cross--a.md" "$J/vault/wiki/decisions/cross--b.md"
printf '{"session_id":"22222222"}' | CLAUDE_PROJECT_DIR="$J" hg journal
line="$(grep -h 'session 22222222' "$J"/vault/journal/*.md)"
t 'printf "%s" "$line" | grep -q ": 2 paths (+2 new)$" && ! printf "%s" "$line" | grep -q "vault/"' "the journal counts two pages and names none" "$line"

# ===== 14. the guard ==================================================================================================
guard() {  # guard <folder> <command>: the exit code of guard-bash for that command
  local payload; payload="{\"tool_input\":{\"command\":$(json_str "$2")},\"cwd\":$(json_str "$1")}"
  printf '%s' "$payload" | CLAUDE_PROJECT_DIR="$1" HG_GUARD_BYPASS=0 hg guard-bash >/dev/null 2>"$TMP/guard.err"
}
for cmd in 'git commit -m x' 'git push' 'git remote add origin x' "bash -c 'git commit -m x'" 'git -C . pull' 'git merge x'; do
  guard "$P" "$cmd"; rc=$?
  t '[ $rc -eq 2 ]' "personal: the guard blocks: $cmd" "rc=$rc $(cat "$TMP/guard.err")"
done
grep -qF 'in a personal folder git commands that record or send changes are not run' "$TMP/guard.err" && ok "the guard says why" || bad "the guard says why" "$(cat "$TMP/guard.err")"
guard "$P" 'git status'; t '[ $? -eq 0 ]' "personal: git status passes"
guard "$S" 'git commit -m x'; t '[ $? -eq 0 ]' "shared: the guard lets git commit through, as before (a stated limit)"
psguard() {  # psguard <folder> <command>: the exit code of guard-ps for that PowerShell command
  local payload; payload="{\"tool_input\":{\"command\":$(json_str "$2")},\"cwd\":$(json_str "$1")}"
  printf '%s' "$payload" | CLAUDE_PROJECT_DIR="$1" HG_GUARD_BYPASS=0 hg guard-ps >/dev/null 2>"$TMP/guard.err"
}
for cmd in 'git commit -m x' 'git push' 'Write-Output a; git remote add origin x'; do
  psguard "$P" "$cmd"; rc=$?
  t '[ $rc -eq 2 ]' "personal: the PowerShell guard blocks: $cmd" "rc=$rc $(cat "$TMP/guard.err")"
done
psguard "$P" 'git status'; t '[ $? -eq 0 ]' "personal: git status passes in PowerShell"
psguard "$S" 'git commit -m x'; t '[ $? -eq 0 ]' "shared: the PowerShell guard lets git commit through"

# ===== 15. publish in a personal folder ===================================================================================
out="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" hg publish check 2>&1)"; rc=$?
t '[ $rc -eq 2 ] && has "$out" "this folder is personal" && [ -z "$(git -C "$P" ls-files)" ]' "publish check exits 2 and stages nothing" "rc=$rc $out"
out="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" hg publish commit 000000000000 2>&1)"; rc=$?
t '[ $rc -eq 2 ]' "publish commit exits 2" "rc=$rc $out"
out="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" hg publish withdraw vault/wiki/x.md 2>&1)"; rc=$?
t '[ $rc -eq 2 ]' "publish withdraw exits 2" "rc=$rc $out"
out="$(cd "$X" && CLAUDE_PROJECT_DIR="$X" hg publish leftout .gateway/leftout/none.json 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && ! has "$out" "not a git repository"' "publish leftout needs no repository" "rc=$rc $out"

# ===== 16. a folder with no mode key: as before =============================================================================
ss="$(in_dir "$S" session-start)"
has "$ss" 'Human Gateway department workspace' && has "$ss" 'Before any commit in a department repository' && has "$ss" 'Nodes declared' \
  && has "$ss" 'Run hg-tool only with the Bash tool' \
  && ok "shared: session-start as before" || bad "shared: session-start as before" "$ss"
data="$(in_dir "$S" today-data)"
printf '%s' "$data" | jtrue 'd["mode"]=="shared" and all(k in d for k in ("gates","sources","agent_approvals","unpublished"))' && ok "shared: today-data has the four keys" || bad "shared: today-data has the four keys" "$data"
t '[ "$(in_dir "$S" nodes --offline | wc -l | tr -d " ")" = 5 ]' "shared: five nodes"
out="$(in_dir "$S" doctor)"
t 'printf "%s\n" "$out" | grep -q "	notify	" && ! printf "%s" "$out" | grep -q kit_registry.py' "shared: doctor's notify line does not name a differing copy" "$out"
has "$out" $'\tgh\t' && ok "shared: doctor still looks for gh" || bad "shared: doctor still looks for gh" "$out"
t 'git -C "$REPO_ROOT" diff --quiet -- plugins/hg/tools/kit_registry.py plugins/hg/tools/gate.py plugins/hg/tools/notify.py plugins/hg/tools/canonicalize.py plugins/hg/tools/scan.py' \
  "the five tools CI copies are unchanged"

# ===== 17. the skills ===========================================================================================================
SK="$PLUGIN/skills"
grep -q '^name: start$' "$SK/start/SKILL.md" && ! grep -q '^disable-model-invocation' "$SK/start/SKILL.md" && ok "the model can start hg:start" || bad "the model can start hg:start"
if [ -f "$SK/keep/SKILL.md" ]; then
  grep -q '^disable-model-invocation' "$SK/keep/SKILL.md" && bad "the model can start hg:keep" || ok "the model can start hg:keep"
else
  echo "n/a  - hg:keep belongs to the next work package"
fi
for s in setup init gate; do
  grep -q '^disable-model-invocation: true' "$SK/$s/SKILL.md" && ok "only a person can start $s" || bad "only a person can start $s"
done
for needle in 'Nad czym teraz pracujesz? Wystarczy jedno zdanie.' 'What are you working on now? One sentence is enough.' \
  '**Tak, tutaj.**' '**Yes, here.**' '**Nie, wybiorę inny folder.**' '**No, I will pick another folder.**' \
  'Otwórz w aplikacji inny folder, najlepiej nowy i pusty, i napisz tam „zacznij”.' 'Open another folder in the app, best a new and empty one, and write "start" there.' \
  'Na tym komputerze brakuje programu Python' 'Python is missing on this computer' \
  '**Nie, otworzę tamten folder.**' '**No, I will open that folder.**' '**Tak, załóż drugie tutaj.**' '**Yes, set up a second one here.**' \
  'context'; do
  grep -qF -- "$needle" "$SK/start/SKILL.md" && ok "hg:start says: $needle" || bad "hg:start says: $needle"
done
for needle in 'Zatwierdzenia należą do udostępniania, a udostępnianie z folderu osobistego nie jest jeszcze dostępne.' 'Approvals belong to sharing, and sharing from a personal folder is not available yet.'; do
  grep -qF -- "$needle" "$SK/gate/SKILL.md" && ok "/hg:gate says: $needle" || bad "/hg:gate says: $needle"
done
for needle in 'Udostępnianie z folderu osobistego nie jest jeszcze dostępne.' 'Sharing from a personal folder is not available yet.'; do
  grep -qF -- "$needle" "$SK/publish/SKILL.md" && ok "/hg:publish says: $needle" || bad "/hg:publish says: $needle"
done
q="$(grep -n 'hg-tool mode' "$SK/publish/SKILL.md" | head -n 1 | cut -d: -f1)"; c="$(grep -n 'hg-tool publish check' "$SK/publish/SKILL.md" | sed -n 2p | cut -d: -f1)"
t '[ -n "$q" ] && [ -n "$c" ] && [ "$q" -lt "$c" ]' "/hg:publish asks for the mode before its first step" "q=$q c=$c"
for s in gate publish setup wiki-query ingest init; do
  grep -qF 'hg-tool mode' "$SK/$s/SKILL.md" && ok "$s reads the mode from a tool" || bad "$s reads the mode from a tool"
done
for s in today dayend; do
  grep -qF '`mode` key' "$SK/$s/SKILL.md" && ok "$s reads the mode key of today-data" || bad "$s reads the mode key of today-data"
done
r="$(grep -o 'hg-tool [^`]*' "$SK/start/SKILL.md")"; printf '%s\n' "$r" > "$TMP/start-cmds.txt"; words_ok "$TMP/start-cmds.txt" "the hg-tool commands of hg:start"

# ===== 18. inside another repository ===================================================================================================
O="$TMP/outer"; mkdir -p "$O"; git init -q "$O"
out="$(psetup --root "$O/notes" --language pl)"; rc=$?
t '[ $rc -eq 1 ] && [ "$(printf "%s\n" "$out" | head -n 1)" = inside ] && has "$out" "Ten folder leży wewnątrz innego folderu, który ma własną historię zmian." && [ ! -e "$O/notes" ]' \
  "a folder inside another repository is refused and nothing is created" "rc=$rc $out"
# As the start skill runs it: no --root, no CLAUDE_PROJECT_DIR, from a folder inside the repository. The folder is the
# one the person opened, never the repository's top, so the answer "Tak, tutaj" (--here) cannot set up the top.
mkdir -p "$O/sub"
for flag in "" --here; do
  # shellcheck disable=SC2086
  out="$(cd "$O/sub" && unset CLAUDE_PROJECT_DIR && hg setup --personal --new --language pl $flag)"; rc=$?
  t '[ $rc -eq 1 ] && [ "$(printf "%s\n" "$out" | head -n 1)" = inside ] && [ ! -e "$O/.claude" ] && [ ! -e "$O/vault" ] && [ ! -e "$O/sub/.claude" ]' \
    "no --root, inside a repository: refused ${flag:-without --here}, nothing created at its top" "rc=$rc $out $(ls -A "$O")"
done
t '! grep -qx /sub "$O/.git/info/exclude" 2>/dev/null' "nothing was written to the outer repository's exclude file" "$(cat "$O/.git/info/exclude" 2>&1)"
# A folder that is a repository of its own with a commit: its history, and perhaps a remote, would carry the notes.
H="$TMP/own-history"; mkdir -p "$H"; git init -q "$H"; printf 'a\n' > "$H/stare.md"
git -C "$H" add stare.md 2>/dev/null; git -C "$H" -c user.email=t@example.com -c user.name=t commit -qm x
for flag in "" --here; do
  # shellcheck disable=SC2086
  out="$(psetup --root "$H" --language pl $flag)"; rc=$?
  t '[ $rc -eq 1 ] && [ "$(printf "%s\n" "$out" | head -n 1)" = "$(printf "refused\thistory")" ] && has "$out" "Ten folder ma już własną historię zmian. Wybierz na notatki inny folder" && [ ! -e "$H/.claude" ] && [ ! -e "$H/vault" ]' \
    "a folder with its own history is refused ${flag:-without --here}, nothing created" "rc=$rc $out"
done
printf '%s\n' "$out" | grep '^say	' > "$TMP/s9b.txt"; words_ok "$TMP/s9b.txt" "the S9b line"
G="$TMP/with-gitignore"; mkdir -p "$G"; printf 'x\n' > "$G/.gitignore"; printf 'a\n' > "$G/a.txt"
out="$(psetup --root "$G" --language pl)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "$(printf "ask\tW tym folderze są już pliki (1). Założyć tu miejsce na notatki?")" && ! has "$out" "Istniejących plików nie zmienię"' \
  "S7 makes no promise to leave files alone when setup would add lines to .gitignore" "rc=$rc $out"

# ===== 19. a second place for notes ===================================================================================================
export CLAUDE_PLUGIN_DATA="$TMP/data-places"
R1="$TMP/place-one"; R2="$TMP/place-two"; R3="$TMP/place-three"
hg setup --personal --root "$R1" >/dev/null
out="$(hg setup --personal --root "$R2" --language pl)"; rc=$?
RR1="$(real "$R1")"
t '[ $rc -eq 1 ] && has "$out" "$(printf "place\t%s" "$RR1")" && has "$out" "Masz już miejsce na notatki w folderze $RR1. Założyć drugie tutaj?" && [ ! -e "$R2" ]' \
  "a second place is asked about and nothing is created" "rc=$rc $out"
out="$(hg setup --personal --root "$R2" --new)"; rc=$?
t '[ $rc -eq 0 ] && [ -f "$R2/.claude/hg.json" ]' "with --new the second place is created" "$out"
rm "$R1/.claude/hg.json" "$R2/.claude/hg.json"
out="$(hg setup --personal --root "$R3")"; rc=$?
t '[ $rc -eq 0 ] && ! has "$out" "$(printf "place\t")"' "a folder that is no longer personal is not offered" "$out"
export CLAUDE_PLUGIN_DATA="$TMP/data"

# ===== 20. a folder copied to a cloud ===================================================================================================
mkdir -p "$TMP/cloud"
out="$(OneDrive="$TMP/cloud" psetup --root "$TMP/cloud/notes" --language en --focus 'Prices')"
has "$out" $'say\tThis folder lies in a place this computer copies to the cloud. Your notes will go there too.' && ! has "$out" 'hg makes no copy of these notes' \
  && ok "under OneDrive: S1b and no S6" || bad "under OneDrive: S1b and no S6" "$out"
out="$(cd "$TMP/cloud/notes" && OneDrive="$TMP/cloud" CLAUDE_PROJECT_DIR="$TMP/cloud/notes" hg doctor)"
has "$out" $'WARN\tplace\tthis folder lies under a folder this computer copies to a cloud service.' && ok "under OneDrive: doctor warns" || bad "under OneDrive: doctor warns" "$out"
out="$(cd "$TMP/cloud/notes" && CLAUDE_PROJECT_DIR="$TMP/cloud/notes" hg doctor)"
has "$out" $'\tplace\t' && bad "without OneDrive: no place warning" "$out" || ok "without OneDrive: no place warning"
out="$(psetup --root "$TMP/local-notes" --language en --focus 'Prices')"
has "$out" 'hg makes no copy of these notes' && ! has "$out" 'copies to the cloud' && ok "not under a cloud folder: S6 and no S1b" || bad "not under a cloud folder: S6 and no S1b" "$out"

# ===== 21. the language ====================================================================================================================
out="$(LANG=pl_PL.UTF-8 psetup --root "$TMP/auto" --language auto)"
cat "$TMP/auto/.claude/hg.json" | jtrue 'd["language"]["content"]=="pl"' && ok "--language auto with LANG=pl_PL writes pl" || bad "--language auto with LANG=pl_PL writes pl" "$(cat "$TMP/auto/.claude/hg.json")"
out="$(in_dir "$TMP/auto" conf-set language en)"; rc=$?
{ [ $rc -eq 0 ] && has "$out" $'context\tWrite to the person in en.' && cat "$TMP/auto/.claude/hg.json" | jtrue 'd["language"]["content"]=="en" and d["mode"]=="personal"'; } \
  && ok "conf-set language in a personal folder" || bad "conf-set language in a personal folder (rc=$rc)" "$out"
out="$(in_dir "$S" conf-set language en 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "cannot be set"' "conf-set language in a shared folder is refused" "rc=$rc $out"

# ===== amendment: writes in vault/ and .gateway/ without a prompt, in both modes; deny still wins ==========================================
WS="$PLUGIN/templates/workspace/.claude/settings.json"
cat "$WS" | jtrue '"Edit(vault/**)" in d["permissions"]["allow"] and "Edit(.gateway/**)" in d["permissions"]["allow"]' && ok "the shared template allows the two writes too" || bad "the shared template allows the two writes too" "$(cat "$WS")"
cat "$S/.claude/settings.json" | jtrue '"Edit(vault/**)" in d["permissions"]["allow"] and "Edit(.gateway/**)" in d["permissions"]["allow"]' && ok "a shared folder gets the two allow rules" || bad "a shared folder gets the two allow rules" "$(cat "$S/.claude/settings.json")"
for D in "$P" "$S"; do
  name="$(cat "$D/.claude/hg.json" | jtrue 'd.get("mode")=="personal"' && echo personal || echo shared)"
  cat "$D/.claude/settings.json" | jtrue '{"Edit(vault/raw/**)","Edit(gates/**)"} <= set(d["permissions"]["deny"]) and not any(r.startswith("Edit(gates") or r.startswith("Edit(.claude") or "raw" in r for r in d["permissions"]["allow"])' \
    && ok "$name: deny rules cover vault/raw/ and gates/, and no allow rule names them" || bad "$name: deny rules cover vault/raw/ and gates/" "$(cat "$D/.claude/settings.json")"
  mkdir -p "$D/vault/raw/cross/sources"; printf 'x\n' > "$D/vault/raw/cross/sources/2026-01-01-kept.md"
  for case in "Write|$D/vault/raw/cross/sources/2026-01-01-kept.md" "Edit|$D/vault/raw/cross/sources/2026-01-01-kept.md" "Write|$D/gates/a.md"; do
    tool="${case%%|*}"; path="${case#*|}"
    printf '{"tool_name":"%s","tool_input":{"file_path":"%s"},"cwd":"%s"}' "$tool" "$path" "$D" | CLAUDE_PROJECT_DIR="$D" hg guard-write >/dev/null 2>&1; rc=$?
    t '[ $rc -eq 2 ]' "$name: the write guard still blocks $tool of ${path#"$D"/} under the allow rule" "rc=$rc"
  done
  printf '{"tool_name":"Write","tool_input":{"file_path":"%s"},"cwd":"%s"}' "$D/vault/wiki/concepts/cross--new.md" "$D" | CLAUDE_PROJECT_DIR="$D" hg guard-write >/dev/null 2>&1
  t '[ $? -eq 0 ]' "$name: a page write passes"
  rm -rf "$D/vault/raw/cross"
done
# The control files every session loads or the librarian obeys are asked about in a personal folder, where no preview
# would show a change to them. A shared folder's settings are as the template has them.
ASK='["Edit(vault/CLAUDE.md)","Edit(vault/schema.md)","Edit(vault/cleaning.md)"]'
cat "$P/.claude/settings.json" | jtrue "all(r in d['permissions']['ask'] for r in $ASK) and not any(r in d['permissions']['allow'] for r in $ASK)" \
  && ok "personal: ask rules for vault/CLAUDE.md, schema.md and cleaning.md" || bad "personal: ask rules for vault/CLAUDE.md, schema.md and cleaning.md" "$(cat "$P/.claude/settings.json")"
cat "$S/.claude/settings.json" | jtrue "d['permissions']['ask']==['Bash(hg-tool publish commit *)']" && ok "shared: the ask rules are the template's, as before" || bad "shared: the ask rules are the template's, as before" "$(cat "$S/.claude/settings.json")"
jedit "$P/.claude/settings.json" "$TMP/p-settings.json" 'd["permissions"]["ask"]=["Bash(hg-tool publish commit *)"]'
cp "$P/.claude/settings.json" "$TMP/p-settings.orig"; cp "$TMP/p-settings.json" "$P/.claude/settings.json"
out="$(in_dir "$P" doctor)"
has "$out" $'WARN\tpermissions\task rules missing from .claude/settings.json: Edit(vault/CLAUDE.md), Edit(vault/schema.md), Edit(vault/cleaning.md)' \
  && ok "personal: doctor names the missing ask rules" || bad "personal: doctor names the missing ask rules" "$out"
cp "$TMP/p-settings.orig" "$P/.claude/settings.json"

# ===== 22. review fixes: --focus in a shared folder, today-data where nothing is set up, a hand-edited mode, names =====
cp "$S/.claude/hg.json" "$TMP/s-hg.json"
out="$(hg setup --personal --root "$S" --language pl --focus 'Mój cennik prywatny')"; rc=$?
t '[ $rc -eq 0 ] && cmp -s "$S/.claude/hg.json" "$TMP/s-hg.json" && [ ! -e "$S/vault/projects/moj-cennik-prywatny" ] && ! has "$out" "$(printf "project\t")" && has "$out" "$(printf "mode\tshared")"' \
  "--focus in a shared folder adds no project and leaves hg.json as it was" "rc=$rc $out"
data="$(in_dir "$E" today-data)"; rc=$?
first="$(cat "$CLAUDE_PLUGIN_DATA/places" | tr -d '\r' | while IFS= read -r p; do [ -f "$p/.claude/hg.json" ] && grep -q '"personal"' "$p/.claude/hg.json" && { printf '%s' "$p"; break; }; done)"
printf '%s' "$data" | jtrue 'd["mode"]=="none" and sorted(d)==["mode","places","say"] and len(d["places"])>0' \
  && has "$data" "\"pl\": \"Ten folder nie jest miejscem na notatki. Twoje notatki są w folderze $first: otwórz go w aplikacji i tam napisz „zapisz”.\"" \
  && ok "today-data with no hg.json: mode none, the places and K13b, no briefing" || bad "today-data with no hg.json: mode none, the places and K13b, no briefing" "rc=$rc first=$first $data"
data="$(CLAUDE_PLUGIN_DATA="$TMP/no-places" in_dir "$E" today-data)"
printf '%s' "$data" | jtrue 'd["places"]==[] and d["say"]["en"]=="This folder is not a place for notes yet. Write \"start\" and I will set one up here."' \
  && ok "today-data with no hg.json and no place: K13a" || bad "today-data with no hg.json and no place: K13a" "$data"
printf '%s' "$data" > "$TMP/td-none.txt"; words_ok "$TMP/td-none.txt" "today-data with no hg.json"
for s in today dayend; do grep -qF 'When `mode` is `none`, this folder is not set up' "$SK/$s/SKILL.md" && ok "$s stops on mode none" || bad "$s stops on mode none"; done
grep -qF 'When it prints `none`, this folder is not set up: run `hg-tool today-data`' "$SK/wiki-query/SKILL.md" && ok "wiki-query stops on mode none" || bad "wiki-query stops on mode none"
HE="$TMP/hand-edit"; psetup --root "$HE" --language pl >/dev/null
t '[ -f "$HE/.gateway/personal" ] && git -C "$HE" check-ignore -q .gateway/personal' "setup --personal leaves its mark, kept out of git"
cp "$HE/.claude/hg.json" "$TMP/he.json"; jedit "$TMP/he.json" "$HE/.claude/hg.json" 'd["mode"]="shared"'
out="$(cd "$HE" && CLAUDE_PROJECT_DIR="$HE" hg publish check 2>&1)"; rc=$?
t '[ $rc -eq 2 ] && has "$out" "was set up as personal" && [ -z "$(git -C "$HE" diff --cached --name-only)" ]' "a personal folder whose mode was edited to shared: publish check refuses and stages nothing" "rc=$rc $out"
out="$(cd "$HE" && CLAUDE_PROJECT_DIR="$HE" hg publish commit 000000000000 2>&1)"; rc=$?
t '[ $rc -eq 2 ] && has "$out" "was set up as personal"' "the same folder: publish commit refuses" "rc=$rc $out"
out="$(in_dir "$HE" doctor)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "$(printf "ERROR\tmode\tthis folder was set up as personal")"' "the same folder: doctor reports an error" "rc=$rc $out"
out="$(grep -rnE 'People appear by role only|writes people as roles|people become roles, and no name|Write people as roles' "$P" "$PLUGIN/agents" "$SK/ingest" "$SK/init" --exclude-dir=.git)"
t '[ -z "$out" ]' "no unconditional rule of people as roles in a personal folder's files, the agents, ingest or init" "$out"
grep -qF 'in a personal folder people' "$PLUGIN/agents/wiki-librarian.md" && ok "the librarian: role sentences give way to the mode's cleaning rules" || bad "the librarian: role sentences give way to the mode's cleaning rules"

echo "solo-mode: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
