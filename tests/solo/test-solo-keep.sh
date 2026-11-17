#!/usr/bin/env bash
# test-solo-keep.sh - keeping a note, a link or a file in one step, and seeing what was kept: hg-tool keep, its
# --status, --list and --rule, the kept section of today-data and of DASHBOARD.md, a secret cut from a pasted note
# and a file with a secret refused whole, links nobody could read, the librarian's two sentences and the split of the
# cleaning rules into what always applies and what applies only in a shared folder. Self-contained, no network, no
# model. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TOOLS="$PLUGIN/tools"
WORDS="$REPO_ROOT/tests/solo/words.py"
TMP="$(temp_dir hg-solo-keep)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR OneDrive OneDriveCommercial OneDriveConsumer
export CLAUDE_PLUGIN_DATA="$TMP/data"   # the places file of this test, never the user's own cache
export KIT_TODAY=2026-11-17
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { printf '%s' "$1" | grep -qF -- "$2"; }
in_dir() { local d="$1"; shift; (cd "$d" && CLAUDE_PROJECT_DIR="$d" hg "$@"); }
lines_of() { printf '%s\n' "$1" | grep "^$2	" | cut -f2-; }
first_field() { printf '%s\n' "$1" | grep "^$2	" | head -n 1 | cut -f"$3"; }
words_ok() {  # words_ok <file> <label>: 0 hits of the word list
  local out; out="$($PY "$WORDS" "$1")"
  [ $? -eq 0 ] && ok "no forbidden word: $2" || bad "no forbidden word: $2" "$out"
}
nogit() {  # nogit <tool.py> [args]: run a tool with every start of git failing as if git were not installed
  $PY -c 'import subprocess, sys, shutil, runpy
real = subprocess.run
def run(cmd, *a, **k):
    if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git": raise FileNotFoundError("git")
    return real(cmd, *a, **k)
subprocess.run = run
which = shutil.which
shutil.which = lambda n, *a, **k: None if n == "git" else which(n, *a, **k)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")' "$@"
}
raw_count() { find "$1/vault/raw" -type f ! -name README.md | wc -l | tr -d ' '; }
inbox_count() { find "$1/vault/inbox" -type f ! -name _template.md | wc -l | tr -d ' '; }
fm() {  # fm <file> <key>: the value of one frontmatter key, as hg-tool keep wrote it
  $PY -c 'import sys; sys.path.insert(0, sys.argv[1]); import keep; sys.stdout.reconfigure(encoding="utf-8")
own = keep.own_frontmatter(open(sys.argv[2], encoding="utf-8").read())
v = keep.key_value(own[0], sys.argv[3]) if own else None
print("<none>" if v is None else v)' "$TOOLS" "$1" "$2" | tr -d '\r'
}
# A secret and an address assembled at run time, so this file holds neither.
TOKEN="gh""p_$(printf 'Ab3%.0s' 1 2 3 4 5 6 7 8 9 10 11 12)"
ZW="$(printf '\342\200\213')"
MAIL="zofia""@""sklep-test.pl"
PW1="Zaq12""wsxCde3"; PW2="Qwe12""rtyUio3"
PEM="RSA PRIV""ATE KEY"

P="$TMP/notatki"
hg setup --personal --new --root "$P" --language pl --focus 'Nowy cennik' >/dev/null
k() { in_dir "$P" keep "$@"; }

# ===== 1. a text capture ==========================================================================================
printf 'Ustalenie: próg rabatu 12 procent od stycznia.\n' > "$P/vault/inbox/keep-a.md"
out="$(k vault/inbox/keep-a.md --title 'Próg rabatu')"; rc=$?
dest="$(first_field "$out" kept 2)"; ref="$(first_field "$out" kept 3)"
t '[ $rc -eq 0 ] && [ "$dest" = vault/raw/nowy-cennik/sources/2026-11-17-prog-rabatu.md ] && [ "$(first_field "$out" kept 4)" = text ]' "a capture is kept under the topic, as text" "rc=$rc $out"
t '[ ! -e "$P/vault/inbox/keep-a.md" ] && [ "$(inbox_count "$P")" = 0 ]' "the capture is gone from the inbox" "$(ls "$P/vault/inbox")"
t '[ "$(in_dir "$P" raw-ref "$dest")" = "$ref" ]' "the kept line carries the reference raw-ref confirms" "$ref"
has "$out" $'say\tZapisane: „Próg rabatu”. Notatka jest w tym folderze.' && has "$out" $'next\tingest\tvault/raw/nowy-cennik/sources/2026-11-17-prog-rabatu.md' \
  && ok "K1 and the next line" || bad "K1 and the next line" "$out"
head -n 8 "$P/$dest" > "$TMP/fm1.txt"
expect='---
source_type: source
captured: 2026-11-17
origin: "note in chat"
project: nowy-cennik
title: "Próg rabatu"
---
Ustalenie: próg rabatu 12 procent od stycznia.'
t '[ "$(tr -d "\r" < "$TMP/fm1.txt")" = "$expect" ]' "the frontmatter of a kept note, then the note whole" "$(cat "$TMP/fm1.txt")"
t '[ "$(printf "%s\n" "$out" | cut -f1 | sort -u | tr "\n" " ")" = "kept next say " ]' "stdout holds only kept, say and next" "$out"

# ===== 2. slugs and names already taken ===============================================================================
printf 'Drugi raz.\n' > "$P/vault/inbox/keep-b.md"
out="$(k vault/inbox/keep-b.md --title 'Próg rabatu')"
t '[ "$(first_field "$out" kept 2)" = vault/raw/nowy-cennik/sources/2026-11-17-prog-rabatu-2.md ]' "the same title twice gives -2" "$out"
printf 'x\n' > "$P/vault/inbox/keep-c.md"
out="$(k vault/inbox/keep-c.md --title '?!; ...')"
t '[ "$(first_field "$out" kept 2)" = vault/raw/nowy-cennik/sources/2026-11-17-notes.md ]' "a title of punctuation gives notes" "$out"

# ===== 3. a secret in a capture is cut out =================================================================================
printf 'Spotkanie o dostępie\nhasło: %s\nklucz %s do serwisu\n' "$PW1" "$TOKEN" > "$P/vault/inbox/keep-s.md"
out="$(k vault/inbox/keep-s.md)"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ -f "$P/$dest" ] && ! grep -qF "$TOKEN" "$P/$dest" && ! grep -qF "$PW1" "$P/$dest"' "a pasted note with a secret is kept without it" "rc=$rc $out"
grep -qF 'klucz […] do serwisu' "$P/$dest" && grep -qF 'Spotkanie o dostępie' "$P/$dest" && ok "the rest of the note is kept, the cut marked" || bad "the rest of the note is kept, the cut marked" "$(cat "$P/$dest")"
has "$out" $'say\tLiczba pominiętych fragmentów, które wyglądają na hasło albo klucz: 2 (***, gh***). Reszta notatki jest zapisana.' \
  && ok "K5 with the masked values" || bad "K5 with the masked values" "$out"
t '! has "$out" "$TOKEN"' "stdout never holds the secret"
split="${TOKEN:0:10}${ZW}${TOKEN:10}"
printf 'Notatka z ukrytym znakiem\n%s\n' "$split" > "$P/vault/inbox/keep-z.md"
out="$(k vault/inbox/keep-z.md)"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && ! grep -qF "${TOKEN:10}" "$P/$dest" && has "$out" "Liczba pominiętych fragmentów"' "a secret split by a zero-width space is cut too" "rc=$rc $out"
t '[ -z "$(printf "%s\n" "$out" | cut -f1 | grep -vE "^(kept|say|next)$")" ]' "stdout holds only kept, say and next lines" "$out"
printf 'Notatka\nhasło: %s\n' "$PW2" > "$P/vault/inbox/keep-f.md"
before="$(raw_count "$P")"
out="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" $PY -c 'import sys; sys.path.insert(0, sys.argv[1]); import keep
real, calls = keep.secret_values, []
def second_scan_finds(text, cfg):
    calls.append(1)
    return real(text, cfg) if len(calls) == 1 else ["left"]
keep.secret_values = second_scan_finds
sys.exit(keep.main(["vault/inbox/keep-f.md"]))' "$TOOLS")"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = secret ] && has "$out" "Tej notatki nie zapisano: jest w niej coś, co wygląda na hasło albo klucz" && [ ! -e "$P/vault/inbox/keep-f.md" ] && [ "$(raw_count "$P")" = "$before" ]' \
  "a secret left after the cut refuses the note (K6b) and the capture is deleted" "rc=$rc $out"

# ===== 4. a file with a secret is refused whole ==============================================================================
printf 'Plik\ntoken: %s\n' "$TOKEN" > "$P/intake/dostep.md"; cp "$P/intake/dostep.md" "$TMP/dostep.orig"
before="$(raw_count "$P")"
out="$(k intake/dostep.md)"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = secret ] && cmp -s "$P/intake/dostep.md" "$TMP/dostep.orig" && [ "$(raw_count "$P")" = "$before" ]' \
  "a file in intake/ with a secret: refused, the file unchanged, nothing kept" "rc=$rc $out"
has "$out" 'Tego pliku nie zapisano: jest w nim coś, co wygląda na hasło albo klucz (gh***). Usuń to z pliku i podaj go jeszcze raz.' && ok "K6 with the masked value" || bad "K6 with the masked value" "$out"
mkdir -p "$TMP/outside"; printf 'token: %s\n' "$TOKEN" > "$TMP/outside/klucz.txt"; cp "$TMP/outside/klucz.txt" "$TMP/klucz.orig"
printf 'token: %s\n' "$TOKEN" > "$P/na-gorze.md"; cp "$P/na-gorze.md" "$TMP/gora.orig"
for f in "$TMP/outside/klucz.txt|$TMP/klucz.orig" "na-gorze.md|$TMP/gora.orig"; do
  file="${f%%|*}"; orig="${f#*|}"
  out="$(k "$file")"; rc=$?
  full="$file"; [ "${file#/}" = "$file" ] && [ "${file#?:}" = "$file" ] && full="$P/$file"
  t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = secret ] && cmp -s "$full" "$orig" && [ "$(inbox_count "$P")" = 0 ] && [ "$(raw_count "$P")" = "$before" ]' \
    "a file with a secret from ${file##*/}: refused, unchanged, nothing new in the inbox" "rc=$rc $out"
done
rm -f "$P/intake/dostep.md" "$P/na-gorze.md"
printf -- '-----BEGIN %s-----\nMIIEow\n-----END %s-----\n' "$PEM" "$PEM" > "$TMP/key.pem"
out="$(k "$TMP/key.pem")"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = secret ] && [ -f "$TMP/key.pem" ] && [ "$(inbox_count "$P")" = 0 ]' "a key file is refused whole, through the scan of raw-add" "rc=$rc $out"
printf 'Klucz serwera\n-----BEGIN %s-----\nMIIEowIBAAKCAQEA\nqwertyuiop\n-----END %s-----\nkoniec\n' "$PEM" "$PEM" > "$P/vault/inbox/keep-k.md"
out="$(k vault/inbox/keep-k.md)"; dest="$(first_field "$out" kept 2)"
t '[ -n "$dest" ] && ! grep -q "MIIEow" "$P/$dest" && grep -q "^koniec$" "$P/$dest"' "a pasted private key is cut with its whole block" "$out"

# ===== 5. contact data stays in the person's own note ==========================================================================
printf 'Dostawca %s\nKontakt do dostawcy: %s\n' "$MAIL" "$MAIL" > "$P/vault/inbox/keep-m.md"
out="$(k vault/inbox/keep-m.md 2>"$TMP/err.txt")"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && grep -qF "$MAIL" "$P/$dest" && ! has "$out" "$MAIL"' "contact data: kept in the source, not printed" "rc=$rc $out"
grep -qF 'contact detail(s) in this source. It stays in this folder.' "$TMP/err.txt" && ! grep -qF 'None of them may reach a page' "$TMP/err.txt" \
  && ok "the note for the model fits a personal folder" || bad "the note for the model fits a personal folder" "$(cat "$TMP/err.txt")"

# ===== 6. a file from outside, and one at the top of the folder ==================================================================
printf 'Raport kwartalny\nWynik 12.\n' > "$TMP/outside/raport.md"; cp "$TMP/outside/raport.md" "$TMP/raport.orig"
out="$(k "$TMP/outside/raport.md")"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && cmp -s "$TMP/outside/raport.md" "$TMP/raport.orig" && [ "$(fm "$P/$dest" origin)" = file ] && [ "$(inbox_count "$P")" = 0 ]' \
  "a file outside the folder is copied; the original keeps its bytes" "rc=$rc $out"
printf 'Lista zadań\n' > "$P/zadania.txt"; cp "$P/zadania.txt" "$TMP/zadania.orig"
out="$(k zadania.txt)"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && cmp -s "$P/zadania.txt" "$TMP/zadania.orig" && [ "${dest##*.}" = md ] && [ "$(fm "$P/$dest" title)" = "Lista zadań" ]' \
  "a file at the top of the folder is copied and left as it was" "rc=$rc $out"
printf 'Notatka z intake\n' > "$P/intake/moja.md"
out="$(k intake/moja.md)"; rc=$?
t '[ $rc -eq 0 ] && [ ! -e "$P/intake/moja.md" ] && [ "$(inbox_count "$P")" = 0 ]' "a person's file in intake/ leaves it once kept" "rc=$rc $out"

# ===== 7. hg's own files ===========================================================================================================
mkdir -p "$P/vault/wiki/concepts"; printf '# x\n' > "$P/vault/wiki/x.md"
for f in vault/wiki/x.md .claude/hg.json CLAUDE.md "$dest"; do
  out="$(k "$f")"; rc=$?
  t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = place ] && has "$out" "Ten plik jest już częścią Twoich notatek, więc nie zapisuję go drugi raz."' "one of hg's own files is refused: $f" "rc=$rc $out"
done
rm -f "$P/vault/wiki/x.md"
out="$(k vault/inbox/nie-ma.md)"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = missing ] && has "$out" "Nie ma takiego pliku: nie-ma.md."' "no such file: K11" "rc=$rc $out"

# ===== 8. links =======================================================================================================================
out="$(k --link 'https://example.com/cennik' --title 'Cennik dostawcy')"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ "$(first_field "$out" kept 4)" = address ] && [ "$(fm "$P/$dest" link)" = https://example.com/cennik ] && [ "$(fm "$P/$dest" link_read)" = false ] && [ "$(fm "$P/$dest" origin)" = link ]' \
  "a link alone: an address, with link and link_read: false" "rc=$rc $out"
has "$out" 'Adres zapisany: „Cennik dostawcy”. Tej strony nie umiem teraz przeczytać' && [ "$(inbox_count "$P")" = 0 ] && ok "K3, and no working file left" || bad "K3, and no working file left" "$out"
printf 'Strona mówi, że ceny rosną o 5 procent.\n' > "$P/vault/inbox/keep-l.md"
out="$(k vault/inbox/keep-l.md --link 'https://example.com/ceny' --title 'Ceny 2027')"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ "$(first_field "$out" kept 4)" = link ] && [ "$(fm "$P/$dest" link_read)" = "<none>" ] && has "$out" "Mam streszczenie tej strony i jej adres."' "a read link: K2 and no link_read" "rc=$rc $out"
printf 'Ania mówiła, że tam są nowe progi.\n' > "$P/vault/inbox/keep-u.md"
out="$(k vault/inbox/keep-u.md --link 'https://example.com/progi' --unread)"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ "$(first_field "$out" kept 4)" = address ] && grep -qF "Ania mówiła, że tam są nowe progi." "$P/$dest" && [ "$(fm "$P/$dest" link_read)" = false ]' \
  "--unread: an address with the person's own words" "rc=$rc $out"
out="$(k --link "https://example.com/x?access_token=$TOKEN")"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = link ] && has "$out" "Tego adresu nie zapisano: jest w nim klucz albo inny poufny fragment."' "a link with a token: K10" "rc=$rc $out"
out="$(k --link 'https://example.com/@zespol/plan')"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = link-shape ] && has "$out" "Tego adresu nie umiem zapisać jako linku."' "a link with @: K10b" "rc=$rc $out"
printf 'x\n' > "$P/intake/zwykly.md"
k intake/zwykly.md --link 'https://example.com/a' >/dev/null 2>&1; rc=$?
t '[ $rc -eq 2 ] && [ -f "$P/intake/zwykly.md" ]' "--link with a file that is not a capture is a usage error" "rc=$rc"
rm -f "$P/intake/zwykly.md"
t '[ "$(inbox_count "$P")" = 0 ]' "no refused link leaves a working file" "$(ls "$P/vault/inbox")"

# ===== 9. other files ==================================================================================================================
printf 'PK\003\004 not a real sheet \000\001\002' > "$TMP/outside/Budzet 2027.xlsx"; cp "$TMP/outside/Budzet 2027.xlsx" "$TMP/xlsx.orig"
out="$(k "$TMP/outside/Budzet 2027.xlsx")"; rc=$?
dest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ "$(first_field "$out" kept 4)" = stub ] && cmp -s "$P/$dest" "$TMP/xlsx.orig" && has "$out" "Plik zapisany: „Budzet 2027.xlsx”."' "an office file: a stub (K4), kept byte for byte" "rc=$rc $out"
printf 'a,b\n1,2\n' > "$TMP/outside/dane.csv"; printf '{"a": 1}\n' > "$TMP/outside/dane.json"
for f in dane.csv dane.json; do
  out="$(k "$TMP/outside/$f")"; dest="$(first_field "$out" kept 2)"
  t '[ -n "$dest" ] && cmp -s "$P/$dest" "$TMP/outside/$f" && [ "${dest##*.}" = "${f##*.}" ]' "$f is kept byte for byte, with no frontmatter" "$out"
done
printf -- '---\n\nTo jest notatka, która zaczyna się od kreski.\n\n---\n\nDruga część.\n' > "$P/intake/kreska.md"; cp "$P/intake/kreska.md" "$TMP/kreska.orig"
out="$(k intake/kreska.md)"; dest="$(first_field "$out" kept 2)"
$PY -c 'import sys; t=open(sys.argv[1],encoding="utf-8").read(); o=open(sys.argv[2],encoding="utf-8").read()
sys.exit(0 if t.startswith("---\nsource_type: source\n") and t.endswith(o) else 1)' "$P/$dest" "$TMP/kreska.orig" \
  && ok "a note that opens with a --- rule gets a new block in front and stays whole" || bad "a note that opens with a --- rule gets a new block in front and stays whole" "$(cat "$P/$dest")"
printf -- '---\ntitle: "Moja notatka"\ntags:\n  - a\nproject: inny\n---\nTreść.\n' > "$P/intake/fm.md"
out="$(k intake/fm.md)"; dest="$(first_field "$out" kept 2)"
t '[ "$(fm "$P/$dest" title)" = "Moja notatka" ] && [ "$(fm "$P/$dest" project)" = nowy-cennik ] && [ "$(fm "$P/$dest" source_type)" = source ] && grep -q "^  - a$" "$P/$dest" && grep -q "^Treść.$" "$P/$dest"' \
  "a note with its own frontmatter keeps its keys and gets ours" "$(cat "$P/$dest" 2>&1)"
has "$out" 'Zapisane: „Moja notatka”.' && ok "its own title is used" || bad "its own title is used" "$out"

# ===== 10. --status ======================================================================================================================
Q="$TMP/status"; hg setup --personal --new --root "$Q" --language pl >/dev/null
printf 'Decyzja o progach.\n' > "$Q/vault/inbox/keep-q.md"
out="$(in_dir "$Q" keep vault/inbox/keep-q.md --title 'Progi')"; ref="$(first_field "$out" kept 3)"
out="$(in_dir "$Q" keep --status "$ref")"; rc=$?
t '[ $rc -eq 0 ] && has "$out" "$(printf "pending\t%s" "$ref")" && has "$out" "Notatka jest zapisana, ale strony z niej jeszcze nie ma."' "--status with no page: pending and K8" "rc=$rc $out"
page="vault/wiki/decisions/cross--progi.md"
printf -- '---\ntype: decision\nsources: [%s]\n---\n# Progi rabatowe\n\nTekst.\n' "$ref" > "$Q/$page"
out="$(in_dir "$Q" keep --status "$ref")"
t 'has "$out" "$(printf "page\t%s\tProgi rabatowe\tfull" "$page")" && has "$out" "Gotowe. Powstała strona „Progi rabatowe”."' "--status with one page: its path and K7a with its heading" "$out"
printf -- '---\ntype: source-summary\nextraction: unextracted\nsources: [%s]\n---\n# Progi rabatowe\n' "$ref" > "$Q/$page"
out="$(in_dir "$Q" keep --status "$ref")"
t 'has "$out" "Powstała strona „Progi rabatowe” z krótkim opisem." && has "$out" "	stub"' "--status with a stub page: K7c" "$out"
printf -- '---\nsources: [%s]\n---\n# Drugie\n' "$ref" > "$Q/vault/wiki/concepts/cross--drugie.md"
out="$(in_dir "$Q" keep --status "$ref")"
t 'has "$out" "Gotowe. Powstały strony: 2." && [ "$(printf "%s\n" "$out" | grep -c "^page	")" = 2 ]' "--status with two pages: K7b" "$out"
in_dir "$Q" keep --status 'nie-referencja' >/dev/null 2>&1; t '[ $? -eq 1 ]' "--status with something that is not a reference exits 1"
S="$TMP/shared"; hg setup --root "$S" --name Dept --language pl >/dev/null
printf 'Ustalenie działu.\n' > "$S/vault/inbox/keep-s.md"
out="$(in_dir "$S" keep vault/inbox/keep-s.md --title 'Ustalenie')"; rc=$?; sref="$(first_field "$out" kept 3)"; sdest="$(first_field "$out" kept 2)"
t '[ $rc -eq 0 ] && [ -n "$sref" ]' "keep works in a shared folder, under its privacy rule" "rc=$rc $out"
printf -- '---\nsources: [%s]\n---\n# Ustalenie\n' "$sref" > "$S/vault/wiki/decisions/cross--ustalenie.md"
out="$(in_dir "$S" keep --status "$sref")"
t '[ "$(lines_of "$out" say | tail -n 1)" = "Dział zobaczy tę stronę dopiero po publikacji." ]' "in a shared folder K12 follows K7" "$out"
t '[ -n "$sdest" ] && git -C "$S" check-ignore -q "$sdest"' "in a shared folder the kept source stays out of git" "$sdest"
(cd "$S" && CLAUDE_PROJECT_DIR="$S" bash "$HG_TOOL" dashboard)
t '! grep -qE "Zapisane ostatnio|Kept lately|Notatka czeka" "$S/DASHBOARD.md" && grep -q "^## Bramki$" "$S/DASHBOARD.md"' "the shared dashboard is as before" "$(cat "$S/DASHBOARD.md")"

# ===== 11. --list ========================================================================================================================
L="$TMP/list"; hg setup --personal --new --root "$L" --language pl >/dev/null
lk() { in_dir "$L" keep "$@"; }
printf 'Pierwsza\n' > "$L/vault/inbox/keep-1.md"; r1="$(first_field "$(lk vault/inbox/keep-1.md --date 2026-11-10)" kept 3)"
printf 'Druga\n' > "$L/vault/inbox/keep-2.md"; r2="$(first_field "$(lk vault/inbox/keep-2.md --date 2026-11-15)" kept 3)"
printf 'Trzecia\n' > "$L/vault/inbox/keep-3.md"; r3="$(first_field "$(lk vault/inbox/keep-3.md --date 2026-11-16)" kept 3)"
printf -- '---\nsources: [%s]\n---\n# Strona pierwszej\n' "$r1" > "$L/vault/wiki/concepts/cross--p1.md"
printf -- '---\nsources: [%s]\n---\n# A\n' "$r2" > "$L/vault/wiki/concepts/cross--p2a.md"
printf -- '---\nsources: [%s]\n---\n# B\n' "$r2" > "$L/vault/wiki/concepts/cross--p2b.md"
mkdir -p "$L/vault/raw/cross/sources"; printf -- '---\ntitle: "niedomknięte\n' > "$L/vault/raw/cross/sources/2026-11-12-zepsuta-notatka.md"
out="$(lk --list --json)"; rc=$?
printf '%s' "$out" | jtrue '[r["date"] for r in d]==["2026-11-16","2026-11-15","2026-11-12","2026-11-10"] and [r["state"] for r in d]==["pending","page","pending","page"]' \
  && ok "--list: newest first, with the state" || bad "--list: newest first, with the state" "rc=$rc $out"
printf '%s' "$out" | jtrue 'd[3]["pages"]==[{"path":"vault/wiki/concepts/cross--p1.md","title":"Strona pierwszej"}] and len(d[1]["pages"])==2' \
  && ok "--list: the pages with their headings" || bad "--list: the pages with their headings" "$out"
has "$out" '"line": "2026-11-10: Pierwsza. Strona: „Strona pierwszej”."' && has "$out" '"line": "2026-11-15: Druga. Strony: 2."' \
  && has "$out" '"line": "2026-11-16: Trzecia. Strony jeszcze nie ma."' && ok "--list: the lines T1a, T1b and T1c" || bad "--list: the lines T1a, T1b and T1c" "$out"
printf '%s' "$out" | jtrue 'd[2]["title"]=="zepsuta-notatka"' && ok "a source whose frontmatter cannot be read is listed by its name" || bad "a source whose frontmatter cannot be read is listed by its name" "$out"
t '[ -f "$L/.gateway/cache/refs.json" ]' "the references are cached"
# The cache is used: a cached digest that differs from the file's own is what the next list shows.
$PY -c 'import json,sys; p=sys.argv[1]; d=json.load(open(p,encoding="utf-8"))
k=[k for k in d if "trzecia" in k][0]; d[k][2]="0000beef"; json.dump(d,open(p,"w",encoding="utf-8"))' "$L/.gateway/cache/refs.json"
out="$(lk --list --json)"
printf '%s' "$out" | jtrue 'd[0]["ref"].endswith(":0000beef")' && ok "a second run reads the cache, not the raw files" || bad "a second run reads the cache, not the raw files" "$out"
touch -d '2026-01-01 00:00' "$L/vault/raw/cross/sources/2026-11-16-trzecia.md" 2>/dev/null || $PY -c 'import os,sys; os.utime(sys.argv[1],(1e9,1e9))' "$L/vault/raw/cross/sources/2026-11-16-trzecia.md"
out="$(lk --list --json)"
printf '%s' "$out" | jtrue 'd[0]["ref"]=="'"$r3"'"' && ok "a file whose time changed is read again" || bad "a file whose time changed is read again" "$out"
out="$(lk --list --days 3)"
t '[ "$(printf "%s\n" "$out" | wc -l | tr -d " ")" = 2 ]' "--list --days 3 shows the last three days" "$out"

# ===== 12. today-data and the dashboard ======================================================================================================
printf 'roboczy\n' > "$L/vault/inbox/keep-zostal.md"
data="$(in_dir "$L" today-data)"; rc=$?
printf '%s' "$data" | jtrue 'd["kept"]["count_7d"]==3 and d["kept"]["pending"]==2 and len(d["kept"]["latest"])==4 and "path" not in d["kept"]["latest"][0]' \
  && has "$data" '"pending_line": "Zapisane notatki bez strony: 2. Napisz „dokończ zapisane”, a je dopiszę."' && ok "today-data: count_7d, pending, pending_line (T2) and latest" || bad "today-data: count_7d, pending, pending_line (T2) and latest" "rc=$rc $data"
printf '%s' "$data" | jtrue '[x for x in d["inbox_recent"] if "keep-" in x["path"]]==[]' && ok "today-data: inbox_recent lists no keep- file" || bad "today-data: inbox_recent lists no keep- file" "$data"
rm -f "$L/vault/inbox/keep-zostal.md"
(cd "$L" && CLAUDE_PROJECT_DIR="$L" bash "$HG_TOOL" dashboard); DB="$L/DASHBOARD.md"
grep -q '^## Zapisane ostatnio$' "$DB" && grep -qF -- '- 2026-11-10: [Strona pierwszej](vault/wiki/concepts/cross--p1.md)' "$DB" && grep -qF -- '- 2026-11-15: Druga. Strony: 2.' "$DB" \
  && ok "dashboard: D1, a link for a note with one page, the line for several" || bad "dashboard: D1, a link for a note with one page, the line for several" "$(cat "$DB")"
grep -qF -- '- Notatka czeka na stronę: Trzecia' "$DB" && ok "dashboard: D3 under what waits" || bad "dashboard: D3 under what waits" "$(cat "$DB")"
t '! grep -qE "Aktywność|Activity|Bramki|Gates" "$DB"' "dashboard: no activity and no gate section" "$(cat "$DB")"
E2="$TMP/nic"; hg setup --personal --new --root "$E2" --language pl >/dev/null
(cd "$E2" && CLAUDE_PROJECT_DIR="$E2" bash "$HG_TOOL" dashboard)
grep -qF 'Nic jeszcze nie zapisano. Wklej notatkę w rozmowie i napisz „zapisz”.' "$E2/DASHBOARD.md" && ok "dashboard: D2 when nothing is kept" || bad "dashboard: D2 when nothing is kept" "$(cat "$E2/DASHBOARD.md")"
t '[ ! -e "$E2/.gateway/cache" ]' "nothing kept: no cache file is written"

# ===== 13. raw-ref --say in a personal folder ===================================================================================================
out="$(in_dir "$L" raw-ref --say "$r1")"
t '[ "$out" = "Źródło: dokument, 2026-11-10. Plik jest na tym komputerze: vault/raw/cross/sources/2026-11-10-pierwsza.md." ]' "raw-ref --say: W3a" "$out"
out="$(in_dir "$L" raw-ref --say src:sources:2026-01-01:00000000)"
t '[ "$out" = "Źródło: dokument, 2026-01-01. Pliku nie ma już na tym komputerze." ]' "raw-ref --say: W3b" "$out"

# ===== 14. words =================================================================================================================================
$PY -c 'import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]); import keep, words
bad = [(lang, key, h) for lang in (True, False) for key, text in keep.TEXT[lang].items() if key != "K12" for h in words.hits(text)]
print("\n".join("%s %s %s" % b for b in bad)); sys.exit(1 if bad else 0)' "$TOOLS" "$REPO_ROOT/tests/solo" > "$TMP/w.txt"
t '[ $? -eq 0 ]' "no forbidden word in any sentence of hg-tool keep but K12, in both languages" "$(cat "$TMP/w.txt")"
grep -E '^\| K1[35]' "$PLUGIN/skills/keep/SKILL.md" > "$TMP/k13.txt"; words_ok "$TMP/k13.txt" "K13a, K13b and K15 in the skill"
for f in "$PLUGIN/skills/keep/SKILL.md" "$PLUGIN/skills/start/SKILL.md"; do
  grep -o 'hg-tool [^`]*' "$f" > "$TMP/cmds.txt"; words_ok "$TMP/cmds.txt" "the hg-tool commands of ${f#"$PLUGIN"/}"
done
sed -n '/^## \/hg:ingest algorithm/,/^## Op semantics/p' "$PLUGIN/agents/wiki-librarian.md" | grep -o 'hg-tool [^`]*' > "$TMP/lib-cmds.txt"
t '[ -s "$TMP/lib-cmds.txt" ]' "the librarian's algorithm names its commands"
words_ok "$TMP/lib-cmds.txt" "the hg-tool commands of the librarian's algorithm"
EN="$TMP/en"; hg setup --personal --new --root "$EN" --language en --focus 'Prices' >/dev/null
printf 'A decision about prices.\npassword: %s\n' "$PW1" > "$EN/vault/inbox/keep-e.md"
{ in_dir "$EN" keep vault/inbox/keep-e.md; in_dir "$EN" keep --link 'https://example.com/en' --title 'Price list'
  in_dir "$EN" keep --list; in_dir "$EN" keep --list --json; in_dir "$EN" keep --rule 'Write short answers'
  in_dir "$EN" keep --status src:sources:2026-01-01:00000000; } > "$TMP/en-out.txt" 2>/dev/null
grep -q 'Left out, because it looks like a password or a key: 1' "$TMP/en-out.txt" && ok "en: K5" || bad "en: K5" "$(cat "$TMP/en-out.txt")"
words_ok "$TMP/en-out.txt" "en: what hg-tool keep prints"
{ k --list; k --list --json; in_dir "$Q" keep --status "$ref"; } > "$TMP/pl-out.txt" 2>/dev/null; words_ok "$TMP/pl-out.txt" "pl: what --list and --status print"
in_dir "$L" today-data > "$TMP/td.txt"; words_ok "$TMP/td.txt" "pl: today-data with kept notes"
words_ok "$L/DASHBOARD.md" "pl: DASHBOARD.md with kept notes"

# ===== 15. free text under Git Bash ================================================================================================================
title="It's \"quoted\" /tmp/plan C:/x"
printf 'Tekst\n' > "$P/vault/inbox/keep-t.md"
out="$(cd "$P" && CLAUDE_PROJECT_DIR="$P" env -u MSYS2_ARG_CONV_EXCL bash "$HG_TOOL" keep vault/inbox/keep-t.md --title "$title")"
dest="$(first_field "$out" kept 2)"
t '[ "$(fm "$P/$dest" title)" = "$title" ]' "a title with quotes and path-shaped parts reaches the frontmatter unchanged" "$(fm "$P/$dest" title) / $out"

# ===== 16. no git ================================================================================================================================
X="$TMP/bez gita"
nogit "$TOOLS/setup_workspace.py" --personal --new --root "$X" --language pl >/dev/null
printf 'Bez gita.\n' > "$X/vault/inbox/keep-x.md"
out="$(cd "$X" && CLAUDE_PROJECT_DIR="$X" nogit "$TOOLS/keep.py" vault/inbox/keep-x.md)"; rc=$?
t '[ $rc -eq 0 ] && [ ! -e "$X/.git" ] && [ -f "$X/$(first_field "$out" kept 2)" ]' "without git keep works in a personal folder" "rc=$rc $out"
mkdir -p "$X/.gateway/leftout"
printf '{"schema": 1, "op": "ingest", "source": "%s", "pages": ["vault/wiki/concepts/cross--x.md"], "none": true, "left_out": []}\n' "$(first_field "$out" kept 3)" > "$X/.gateway/leftout/draft.json"
out="$(cd "$X" && CLAUDE_PROJECT_DIR="$X" HG_NEUTRAL=1 nogit "$TOOLS/publish.py" leftout .gateway/leftout/draft.json 2>&1)"; rc=$?
t '[ $rc -eq 0 ] && [ ! -e "$X/.gateway/leftout/draft.json" ] && printf "%s" "$out" | grep -q "^.gateway/leftout/[0-9a-f]*.json$"' "without git the librarian's leftout call works" "rc=$rc $out"
printf '{"schema": 2}\n' > "$X/.gateway/leftout/draft.json"
out="$(in_dir "$X" leftout .gateway/leftout/draft.json 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "hg: schema must be 1" && ! has "$out" "publish"' "hg-tool leftout speaks under the name hg" "rc=$rc $out"

# ===== 17. the person's own rules, and a folder that is not set up =========================================================================================
cp "$P/CLAUDE.local.md" "$TMP/local.orig"
out="$(k --rule 'Pisz krótko')"; rc=$?
t '[ $rc -eq 0 ] && [ "$(tail -n 1 "$P/CLAUDE.local.md" | tr -d "\r")" = "- Pisz krótko" ] && [ "$out" = "$(printf "say\tDopisane do Twoich zasad dla tego folderu.")" ]' "--rule: the line is added, K9" "rc=$rc $out"
cp "$P/CLAUDE.local.md" "$TMP/local.after"
out="$(k --rule "Używaj tokenu $TOKEN")"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = secret ] && cmp -s "$P/CLAUDE.local.md" "$TMP/local.after"' "--rule with a secret: refused, the file unchanged" "rc=$rc $out"
rm "$P/CLAUDE.local.md"; out="$(k --rule 'Pisz po polsku')"
grep -q "^# Moje zasady dla Claude'a$" "$P/CLAUDE.local.md" && grep -qx -- '- Pisz po polsku' "$P/CLAUDE.local.md" && ok "--rule creates the file when it is missing" || bad "--rule creates the file when it is missing" "$(cat "$P/CLAUDE.local.md")"
N="$TMP/not-set-up"; mkdir -p "$N"; printf 'x\n' > "$N/a.md"
out="$(in_dir "$N" keep a.md)"; rc=$?
t '[ $rc -eq 1 ] && [ "$(printf "%s\n" "$out" | head -n 1)" = "$(printf "refused\tsetup")" ] && printf "%s\n" "$out" | grep -q "^place	"' "no hg.json: refused setup and a place line" "rc=$rc $out"
out="$(CLAUDE_PLUGIN_DATA="$TMP/no-places" in_dir "$N" keep a.md)"
t '[ "$out" = "$(printf "refused\tsetup")" ]' "no hg.json and no known place: refused setup alone" "$out"
# The first message in a new folder is a note and "zapisz": the skill writes the capture before the tool says the
# folder is not set up. The capture goes, with the vault/ it made, so "zacznij" then works there.
N2="$TMP/first-note"; mkdir -p "$N2/vault/inbox"; printf 'Pierwsza notatka\nhasło: %s\n' "$PW1" > "$N2/vault/inbox/keep-a.md"
out="$(cd "$N2" && hg keep vault/inbox/keep-a.md)"; rc=$?
t '[ $rc -eq 1 ] && [ "$(first_field "$out" refused 2)" = setup ] && [ ! -e "$N2/vault" ]' "no hg.json: the capture is deleted, with the empty vault/ it made" "rc=$rc $out $(find "$N2" 2>&1)"
out="$(cd "$N2" && hg setup --personal --new --language pl)"; rc=$?
t '[ $rc -eq 0 ] && [ -f "$N2/.claude/hg.json" ]' "then setup succeeds in that folder" "rc=$rc $out"
N3="$TMP/own-inbox"; mkdir -p "$N3/vault/inbox"; printf 'moja\n' > "$N3/vault/inbox/moja.md"; printf 'x\n' > "$N3/vault/inbox/keep-b.md"
out="$(cd "$N3" && hg keep vault/inbox/moja.md)"; out2="$(cd "$N3" && hg keep vault/inbox/keep-b.md)"
t '[ -f "$N3/vault/inbox/moja.md" ] && [ ! -e "$N3/vault/inbox/keep-b.md" ]' "no hg.json: a person's own file stays, and the folders holding it" "$out $out2 $(find "$N3" 2>&1)"

# ===== 17b. the same note twice ===============================================================================================================
T2="$TMP/twice"; hg setup --personal --new --root "$T2" --language pl >/dev/null
printf 'Spotkanie o progach\n\nUstalone: próg 12 procent.\n' > "$T2/vault/inbox/keep-a.md"; out_a="$(in_dir "$T2" keep vault/inbox/keep-a.md)"
printf 'Spotkanie o progach\n\nUstalone: próg 12 procent.\n' > "$T2/vault/inbox/keep-b.md"; out_b="$(in_dir "$T2" keep vault/inbox/keep-b.md)"
t '[ -n "$(first_field "$out_a" kept 2)" ] && [ "$(first_field "$out_a" kept 2)" = "$(first_field "$out_b" kept 2)" ] && [ "$(first_field "$out_a" kept 3)" = "$(first_field "$out_b" kept 3)" ] && [ "$(raw_count "$T2")" = 1 ] && [ "$(inbox_count "$T2")" = 0 ]' \
  "the same note twice on one day: one source file, named both times, no working file left" "$out_a / $out_b"
has "$out_b" 'Zapisane: „Spotkanie o progach”.' && has "$out_b" "$(printf "next\tingest\t%s" "$(first_field "$out_a" kept 2)")" && ok "the second time: K1, and the page is still to be written" || bad "the second time: K1, and the page is still to be written" "$out_b"
data="$(in_dir "$T2" keep --list --json)"
printf '%s' "$data" | jtrue 'len(d)==1 and d[0]["state"]=="pending"' && ok "--list shows it once" || bad "--list shows it once" "$data"
tref="$(first_field "$out_a" kept 3)"
printf -- '---\nsources: [%s]\n---\n# Progi\n' "$tref" > "$T2/vault/wiki/concepts/cross--progi.md"
printf 'Spotkanie o progach\n\nUstalone: próg 12 procent.\n' > "$T2/vault/inbox/keep-c.md"
out="$(in_dir "$T2" keep vault/inbox/keep-c.md)"; rc=$?
t '[ $rc -eq 0 ] && [ "$(first_field "$out" kept 3)" = "$tref" ] && ! has "$out" "$(printf "next\t")" && [ "$(raw_count "$T2")" = 1 ]' "a third time, with its page written: no next line" "rc=$rc $out"
for n in 1 2; do out="$(in_dir "$T2" keep --link 'https://example.com/raz' --title 'Raz')"; done
t '[ "$(raw_count "$T2")" = 2 ] && [ "$(inbox_count "$T2")" = 0 ]' "the same link alone twice: one source file" "$(ls -R "$T2/vault/raw")"
printf 'Moja notatka z intake\n' > "$T2/intake/moja.md"; in_dir "$T2" keep intake/moja.md >/dev/null
printf 'Moja notatka z intake\n' > "$T2/intake/moja.md"; out="$(in_dir "$T2" keep intake/moja.md)"; rc=$?
t '[ $rc -eq 0 ] && [ "$(raw_count "$T2")" = 3 ] && [ ! -e "$T2/intake/moja.md" ] && [ "$(inbox_count "$T2")" = 0 ]' "the same own file again: no second source, and it leaves intake/ as a kept file does" "rc=$rc $out"

# ===== 18. the files of this work, the skill, the librarian and the cleaning rules =========================================================================
out="$(grep -nE '^(from|import) ' "$TOOLS/keep.py" "$TOOLS/solo.py" | grep -vE ':(import (contextlib|datetime|hashlib|io|json|os|re|shutil|subprocess|sys|unicodedata|uuid|gate|kit_registry as kr|raw_add|raw_ref|scan|solo|today_data)( +#.*)?|from pathlib import Path)$')"
t '[ -z "$out" ]' "keep.py and solo.py import only the standard library and the kit" "$out"
out="$(grep -rn $'\xe2\x80\x94' "$TOOLS/keep.py" "$PLUGIN/skills/keep" "$PLUGIN/rules/cleaning.md" "$PLUGIN/agents/wiki-librarian.md" "$REPO_ROOT/tests/solo")"
t '[ -z "$out" ]' "no em dashes in the new files" "$out"
out="$(cd "$REPO_ROOT" && hg scan plugins/hg/tools/keep.py plugins/hg/tools/solo.py plugins/hg/skills/keep tests/solo/test-solo-keep.sh tests/solo/words.py 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the scanner finds nothing in the new files" "$out"
SK="$PLUGIN/skills/keep/SKILL.md"
grep -q '^name: keep$' "$SK" && ! grep -q '^disable-model-invocation' "$SK" && ok "the model can start hg:keep" || bad "the model can start hg:keep"
for needle in zapisz zapamiętaj 'zachowaj to' 'dokończ zapisane' 'keep this' 'finish what I kept' 'hg-tool keep --status' 'hg-tool keep --list --json' 'hg-tool keep --rule' \
  'hg:wiki-librarian' 'Never start `hg:publish` here' 'Ten folder nie jest jeszcze miejscem na notatki. Napisz „zacznij”, a je tu założę.' \
  'This folder is not a place for notes. Your notes are in the folder {path}: open it in the app and write "keep this" there.'; do
  grep -qF -- "$needle" "$SK" && ok "hg:keep says: $needle" || bad "hg:keep says: $needle"
done
LIB="$PLUGIN/agents/wiki-librarian.md"
grep -qF 'link_read: false' "$LIB" && grep -qF '`link` (written by `hg-tool keep`)' "$LIB" && ok "the librarian has the two sentences about kept links" || bad "the librarian has the two sentences about kept links"
grep -qF '`hg-tool leftout .gateway/leftout/draft.json`' "$LIB" && [ "$(grep -c 'hg-tool publish leftout' "$LIB")" = 1 ] && ok "the librarian names hg-tool leftout, and the older name once" || bad "the librarian names hg-tool leftout, and the older name once"
grep -qF 'run `hg-tool mode`' "$LIB" && ok "the librarian takes the mode from a tool" || bad "the librarian takes the mode from a tool"
CL="$PLUGIN/rules/cleaning.md"
always="$(sed -n '/^## Always$/,/^## Only in a shared folder$/p' "$CL")"; shared="$(sed -n '/^## Only in a shared folder$/,/^## The left-out report$/p' "$CL")"
has "$always" '**Secrets** (`secret`)' && has "$always" '**Instructions** (`instruction`)' && has "$always" 'Never name a source file' \
  && ok "cleaning rules: secrets, instructions and source names always apply" || bad "cleaning rules: secrets, instructions and source names always apply" "$always"
has "$shared" 'People by role, never by name.' && has "$shared" '**Judgments of people**' && has "$shared" '**Personal data**' && ! has "$always" 'People by role' \
  && ok "cleaning rules: people by role, judgments and personal data apply only in a shared folder" || bad "cleaning rules: people by role only in a shared folder" "$shared"
grep -qF 'Run `hg-tool mode` before you draft.' "$CL" && grep -qF 'unless the tool printed `personal`' "$CL" && ok "cleaning rules: the mode comes from the tool" || bad "cleaning rules: the mode comes from the tool"
$PY -c 'import re,sys; sys.path.insert(0, sys.argv[1]); import publish
kinds=set(re.findall(r"\(`([a-z-]+)`", open(sys.argv[2],encoding="utf-8").read()))
sys.exit(0 if kinds and kinds <= set(publish.WHY) else 1)' "$TOOLS" "$CL" && ok "every kind in the cleaning rules is one the report accepts" || bad "every kind in the cleaning rules is one the report accepts"
ss="$(CLAUDE_PROJECT_DIR="$S" hg session-start)"
route="$(printf '%s\n' "$ss" | grep 'any language')"
has "$route" 'call hg:keep with the Skill tool, without asking where it goes' && has "$route" 'dokończ zapisane' && has "$route" 'put it in intake/' \
  && ok "the shared routing line sends zapisz to hg:keep and a batch to intake/" || bad "the shared routing line sends zapisz to hg:keep" "$route"
grep -qF '| say "zapisz", or `/hg:keep` | Keep a note, a link or a file in one step |' "$PLUGIN/templates/workspace/CLAUDE.md" && ok "the workspace map names hg:keep" || bad "the workspace map names hg:keep"
t 'git -C "$REPO_ROOT" diff --quiet -- plugins/hg/tools/kit_registry.py plugins/hg/tools/gate.py plugins/hg/tools/notify.py plugins/hg/tools/canonicalize.py plugins/hg/tools/scan.py' \
  "the five tools CI copies are unchanged"

echo "solo-keep: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
