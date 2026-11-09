#!/usr/bin/env bash
# test-raw-add.sh - hg-tool raw-add, the one writer of vault/raw/: where a file lands, what is refused, that
# nothing is overwritten, and that the template and the skills still send every source through it.
# Self-contained: fictional data in a temp repo. Every fake value is assembled at run time.
# Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TMP="$(temp_dir hg-raw)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { case "$1" in *"$2"*) return 0;; *) return 1;; esac; }
rep()  { printf "%${2}s" "" | tr ' ' "$1"; }  # rep <char> <count>

W="$TMP/dept"
out="$(hg setup --root "$W" --name Dept --project acme-notes 2>&1)"; t '[ $? -eq 0 ]' "setup succeeds" "$out"
git -C "$W" init -q
git -C "$W" config user.email reviewer@example.com
git -C "$W" config user.name Reviewer
git -C "$W" config core.autocrlf false
git -C "$W" add -A; git -C "$W" commit -q -m base
export CLAUDE_PROJECT_DIR="$W"
RAW=vault/raw/acme-notes
ra()   { hg raw-add "$@"; }
add()  { ra "$1" --project acme-notes --kind meetings --date 2026-01-15 --slug "$2"; }  # add <file> <slug>
new()  { printf '%s\n' "${2:-some notes}" > "$W/$1"; }                                 # new <path> [text]

# --- where a file lands -----------------------------------------------------------------------
new intake/notes.md '# Kickoff'
out="$(add intake/notes.md kickoff 2>/dev/null)"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "$RAW/meetings/2026-01-15-kickoff.md" ]' "prints the repo-relative destination" "rc=$rc out=$out"
t '[ -f "$W/$RAW/meetings/2026-01-15-kickoff.md" ] && [ ! -e "$W/intake/notes.md" ]' "the file moved"
t '[ "$(cat "$W/$RAW/meetings/2026-01-15-kickoff.md")" = "# Kickoff" ]' "the content arrived"

new intake/plain.TXT 'plain'
out="$(add intake/plain.TXT plain 2>/dev/null)"
t '[ "$out" = "$RAW/meetings/2026-01-15-plain.md" ]' ".TXT becomes .md" "$out"
new intake/Report.Md 'mixed'
out="$(add intake/Report.Md mixed 2>/dev/null)"
t '[ "$out" = "$RAW/meetings/2026-01-15-mixed.md" ]' "the suffix is lower-cased" "$out"
new intake/noext 'no suffix'
out="$(add intake/noext bare 2>/dev/null)"
t '[ "$out" = "$RAW/meetings/2026-01-15-bare" ]' "a file with no suffix stays without one" "$out"
new intake/x.md 'cross'
out="$(ra intake/x.md --project cross --kind snapshots --date 2024-02-29 --slug leap-day 2>/dev/null)"
t '[ "$out" = "vault/raw/cross/snapshots/2024-02-29-leap-day.md" ] && [ -f "$W/$out" ]' "cross is a project, the folders are created, a leap day is a date" "$out"
new intake/y.md 'order'
out="$(ra --slug any-order --date 2026-03-01 --kind sources --project acme-notes intake/y.md 2>/dev/null)"
t '[ "$out" = "$RAW/sources/2026-03-01-any-order.md" ]' "the options may come first" "$out"

# --- binary files ----------------------------------------------------------------------------
bin="$W/intake/scan.PDF"
for i in 1 2 3 4 5 6 7 8; do printf '\000\001\002\003\004\005\006\007'; done > "$bin"
before="$($PY -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$bin")"
out="$(add intake/scan.PDF binary 2>"$TMP/err")"; rc=$?
err="$(cat "$TMP/err")"
t '[ $rc -eq 0 ] && [ "$out" = "$RAW/meetings/2026-01-15-binary.pdf" ]' "a binary file the scan cannot read is allowed" "rc=$rc out=$out err=$err"
has "$err" "could not read" && ok "and noted on stderr" || bad "and noted on stderr" "$err"
after="$($PY -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$W/$out")"
t '[ "$before" = "$after" ]' "a binary file arrives byte for byte"

# --- tracked files keep their history ---------------------------------------------------------
new vault/inbox/tracked.md 'tracked note'
git -C "$W" add vault/inbox/tracked.md; git -C "$W" commit -q -m tracked
out="$(add vault/inbox/tracked.md tracked 2>/dev/null)"; rc=$?
t '[ $rc -eq 0 ] && [ -f "$W/$out" ] && [ ! -e "$W/vault/inbox/tracked.md" ]' "a tracked file moves" "rc=$rc out=$out"
status="$(git -C "$W" status --porcelain -- vault/inbox/tracked.md "$RAW/meetings/2026-01-15-tracked.md")"
has "$status" "R  vault/inbox/tracked.md -> $RAW/meetings/2026-01-15-tracked.md" && ok "git records it as a rename" || bad "git records it as a rename" "$status"
git -C "$W" commit -q -m moved

# --- path shapes -------------------------------------------------------------------------------
abs="$W/intake/abs.md"; new intake/abs.md abs
out="$(add "$abs" abs-native 2>/dev/null)"
t '[ "$out" = "$RAW/meetings/2026-01-15-abs-native.md" ]' "an absolute path" "$out"
if command -v cygpath >/dev/null 2>&1; then
  new intake/win.md win; new intake/msys.md msys; new intake/bare.md bare
  out="$(add "$(cygpath -w "$W/intake/win.md")" shape-win 2>/dev/null)"
  t '[ "$out" = "$RAW/meetings/2026-01-15-shape-win.md" ]' 'D:\x' "$out"
  out="$(add "$(cygpath -u "$W/intake/msys.md")" shape-msys 2>/dev/null)"
  t '[ "$out" = "$RAW/meetings/2026-01-15-shape-msys.md" ]' '/d/x' "$out"
  out="$(env -u MSYS2_ARG_CONV_EXCL bash "$HG_TOOL" raw-add "$(cygpath -u "$W/intake/bare.md")" --project acme-notes --kind meetings --date 2026-01-15 --slug shape-plain 2>/dev/null)"
  t '[ "$out" = "$RAW/meetings/2026-01-15-shape-plain.md" ]' '/d/x straight from Git Bash' "$out"
else
  echo "n/a  - cygpath is not here, Windows path shapes not run"
fi

# --- refused sources ----------------------------------------------------------------------------
refused() {  # refused <label> <file> [rc]
  local out rc; out="$(add "$2" refused-one 2>&1)"; rc=$?
  { [ $rc -eq "${3:-1}" ] && [ ! -e "$W/$RAW/meetings/2026-01-15-refused-one.md" ]; } && ok "refused: $1" || bad "refused: $1 (rc=$rc)" "$out"
}
printf 'x\n' > "$TMP/outside.md"
refused "a file outside the repo" "$TMP/outside.md"
t '[ -f "$TMP/outside.md" ]' "the outside file is left alone"
refused "a parent-directory escape" "../outside.md"
refused "a file inside .git" ".git/config"
t '[ -f "$W/.git/config" ]' "the .git file is left alone"
new "$RAW/sources/already.md" 'raw'
refused "a file already in vault/raw/" "$RAW/sources/already.md"
t '[ -f "$W/$RAW/sources/already.md" ]' "the raw file is left alone"
refused "a folder" "intake"
refused "a file that does not exist" "intake/missing.md"

# Only intake/ and vault/inbox/ are accepted: everything else in the repo is a control file or someone's work.
mkdir -p "$W/gates" "$W/vault/journal"
new gates/g1.md 'gate record'; new gates/g1.lock.json '{"approvals": []}'
new vault/journal/2026-01-15.md '- a session'; new vault/log.jsonl '{}'
for f in gates/g1.md gates/g1.lock.json .claude/settings.json .claude/hg.json .github/hg/scan.py \
         vault/journal/2026-01-15.md vault/log.jsonl vault/schema.md CLAUDE.md .gitignore; do
  refused "$f" "$f"
  t '[ -f "$W/$f" ]' "$f stays where it is"
done
refused "a control file named from inside intake/" "intake/../gates/g1.md"
refused "a control file by its absolute path" "$W/gates/g1.lock.json"
t '[ -f "$W/gates/g1.lock.json" ]' "the lock file stays where it is"
rm -f "$W/gates/g1.md" "$W/gates/g1.lock.json"

link="$W/intake/link.md"; printf 'real\n' > "$W/intake/real.md"
if MSYS=winsymlinks:nativestrict ln -s "$W/intake/real.md" "$link" 2>/dev/null && [ -L "$link" ]; then
  refused "a symbolic link" "intake/link.md"
  t '[ -L "$link" ] && [ -f "$W/intake/real.md" ]' "the link and its target are left alone"
  rm -f "$link"
  mkdir -p "$TMP/elsewhere"
  MSYS=winsymlinks:nativestrict ln -s "$TMP/elsewhere" "$W/vault/raw/linked"
  mkdir -p "$W/vault/raw/linked/meetings"
  conf="$W/.claude/hg.json"; cp "$conf" "$TMP/conf.bak"
  jedit "$conf" "$conf" 'd["projects"].append("linked")'
  out="$(ra intake/real.md --project linked --kind meetings --date 2026-01-15 --slug out 2>&1)"; rc=$?
  t '[ $rc -eq 1 ] && [ -z "$(ls -A "$TMP/elsewhere/meetings")" ] && [ -f "$W/intake/real.md" ]' "a link inside vault/raw/ cannot lead the file out" "rc=$rc $out"
  cp "$TMP/conf.bak" "$conf"; rm -f "$W/vault/raw/linked"
else
  echo "n/a  - this system cannot make symbolic links here, real link cases not run"
fi
# Windows without developer mode cannot create a link, so the refusal is also checked with the test stubbed in.
out="$($PY - "$PLUGIN/tools" "$W" <<'PY'
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import gate, raw_add
root = Path(sys.argv[2]).resolve()
real_islink = os.path.islink
os.path.islink = lambda p: str(p).endswith("real.md") or real_islink(p)
try:
    raw_add.source_of(root, "intake/real.md", ["vault", "raw"])
    print("accepted")
except gate.Refused as exc:
    print(exc)
PY
)"
has "$out" "symbolic link" && ok "a link is refused before it is followed" || bad "a link is refused before it is followed" "$out"

# --- values --------------------------------------------------------------------------------------
new intake/v.md 'values'
value() {  # value <label> <flag> <bad value>
  local out rc p=acme-notes k=meetings d=2026-01-15 s=fine
  case "$2" in --project) p="$3";; --kind) k="$3";; --date) d="$3";; --slug) s="$3";; esac
  out="$(ra intake/v.md --project "$p" --kind "$k" --date "$d" --slug "$s" 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && [ -f "$W/intake/v.md" ]; } && ok "refused: $1" || bad "refused: $1 (rc=$rc)" "$out"
}
value "an unknown project" --project nope
value "a project that climbs out" --project ../..
value "an unknown kind" --kind notes
value "a kind with another case" --kind Meetings
value "a day that does not exist" --date 2026-02-30
value "a month that does not exist" --date 2026-13-01
value "a date without dashes" --date 20260115
value "a week date" --date 2026-W03-4
value "an unpadded date" --date 2026-1-5
value "an empty date" --date ''
value "a slug with capitals" --slug Fine
value "a slug starting with a hyphen" --slug -fine
value "a slug with a slash" --slug a/b
value "a slug with a dot" --slug a.b
value "an empty slug" --slug ''

usage() {  # usage <label> <args...>
  local label="$1" out rc; shift
  out="$(ra "$@" 2>&1)"; rc=$?
  { [ $rc -eq 2 ] && [ -f "$W/intake/v.md" ]; } && ok "usage: $label" || bad "usage: $label (rc=$rc)" "$out"
}
usage "no arguments"
usage "no file" --project acme-notes --kind meetings --date 2026-01-15 --slug a
usage "two files" intake/v.md intake/v.md --project acme-notes --kind meetings --date 2026-01-15 --slug a
usage "no --project" intake/v.md --kind meetings --date 2026-01-15 --slug a
usage "no --kind" intake/v.md --project acme-notes --date 2026-01-15 --slug a
usage "no --date" intake/v.md --project acme-notes --kind meetings --slug a
usage "no --slug" intake/v.md --project acme-notes --kind meetings --date 2026-01-15
usage "a flag with no value" intake/v.md --project acme-notes --kind meetings --date 2026-01-15 --slug
usage "an unknown flag" intake/v.md --project acme-notes --kind meetings --date 2026-01-15 --slug a --force

# --- the scan decides --------------------------------------------------------------------------
gh="gh""p_$(rep a 36)"
mail="ala.nowak""@""acme-notes.test"
stopped() {  # stopped <label> <file> <kind> <the value that must not be printed>
  local out rc; out="$(add "$2" scanned 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && [ -f "$W/$2" ] && [ ! -e "$W/$RAW/meetings/2026-01-15-scanned.md" ]; } && ok "stopped by the scan: $1" || bad "stopped by the scan: $1 (rc=$rc)" "$out"
  printf '%s\n' "$out" | grep -q "$2:[0-9]*"$'\t'"$3"$'\t' && ok "the finding is printed: $1" || bad "the finding is printed: $1" "$out"
  [ -n "$4" ] && { has "$out" "$4" && bad "masked: $1" "the value reached the output" || ok "masked: $1"; }
}
printf 'first\ntoken %s\n' "$gh" > "$W/intake/secret.md"
stopped "a secret" intake/secret.md secret "$gh"
printf 'first\nwrite to %s\n' "$mail" > "$W/intake/contact.md"
stopped "personal data" intake/contact.md pii "$mail"
printf 'x' > "$W/intake/budget.xlsx"
stopped "a file that stays a link" intake/budget.xlsx filetype ""
printf 'first\ntoken %s\n' "$gh" > "$W/vault/inbox/tracked-secret.md"
git -C "$W" add vault/inbox/tracked-secret.md
out="$(add vault/inbox/tracked-secret.md scanned 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && [ -f "$W/vault/inbox/tracked-secret.md" ]' "a tracked file with a finding stays where it is" "rc=$rc $out"
git -C "$W" rm -q --cached vault/inbox/tracked-secret.md; rm "$W/vault/inbox/tracked-secret.md"
jedit "$W/.claude/hg.json" "$TMP/conf.allow" 'd["scan"]["allow"]["domains"]=["acme-notes.test"]'
cp "$W/.claude/hg.json" "$TMP/conf.base"; cp "$TMP/conf.allow" "$W/.claude/hg.json"
out="$(add intake/contact.md allowed 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the scan uses the repo's own allowlist" "rc=$rc $out"
cp "$TMP/conf.base" "$W/.claude/hg.json"
mkdir -p "$W/intake/gates" "$W/intake/nested/.git" "$W/intake/nested/gates"
printf 'accountable: %s\n' "$mail" > "$W/intake/gates/leak.md"
stopped "an address in a folder that is only named gates" intake/gates/leak.md pii "$mail"
printf 'accountable: %s\n' "$mail" > "$W/intake/nested/gates/leak.md"
stopped "no gate exemption, even at the top of a nested repository" intake/nested/gates/leak.md pii "$mail"
rm -rf "$W/intake/nested"
$PY -c 'import sys; open(sys.argv[1],"wb").write(("write to "+sys.argv[2]+"\n").encode("utf-32"))' "$W/intake/u32.md" "$mail"
stopped "UTF-32 text" intake/u32.md pii "$mail"
tsv_phone="601 234"" 567"
printf 'Ala\t%s\tEUR\t1200\n' "$tsv_phone" > "$W/intake/people.tsv"
stopped "a phone column beside a currency column" intake/people.tsv pii "$tsv_phone"
nine="601""234""567"
printf 'NIP firmy, tel. kontaktowy %s\n' "$nine" > "$W/intake/label.md"
stopped "a phone number after a company label" intake/label.md pii "$nine"
new intake/noconf.md 'x'
mv "$W/.claude/hg.json" "$TMP/conf.gone"
out="$(add intake/noconf.md noconf 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && [ -f "$W/intake/noconf.md" ]' "no workspace: refused" "rc=$rc $out"
mv "$TMP/conf.gone" "$W/.claude/hg.json"

# --- what git mv carries is what was scanned -----------------------------------------------------
stale() {  # stale <label> <file>: refused, unmoved, and no value in the message
  local out rc; out="$(add "$2" stale 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && [ -f "$W/$2" ] && [ ! -e "$W/$RAW/meetings/2026-01-15-stale.md" ] && ! has "$out" "$gh"; } && ok "refused: $1" || bad "refused: $1 (rc=$rc)" "$out"
}
ci() { git -C "$W" add "$1"; git -C "$W" commit -q -m "$1"; }  # ci <file>
in_index() { git -C "$W" show ":$1"; }

new vault/inbox/staged.md 'clean'; ci vault/inbox/staged.md
printf 'token %s\n' "$gh" > "$W/vault/inbox/staged.md"; git -C "$W" add vault/inbox/staged.md; new vault/inbox/staged.md 'clean'
stale "a secret that is staged but gone from the file on disk" vault/inbox/staged.md
has "$(in_index vault/inbox/staged.md)" "$gh" && ok "the index was not touched" || bad "the index was not touched"
git -C "$W" add vault/inbox/staged.md
out="$(add vault/inbox/staged.md staged-clean 2>&1)"; rc=$?
t '[ $rc -eq 0 ] && ! has "$(in_index "$RAW/meetings/2026-01-15-staged-clean.md")" "$gh"' "once staged again it moves, and the secret stays behind" "rc=$rc $out"
git -C "$W" commit -q -m staged-clean

printf 'token %s\n' "$gh" > "$W/vault/inbox/staged-new.md"; git -C "$W" add vault/inbox/staged-new.md; new vault/inbox/staged-new.md 'clean'
stale "the same for a file that was never committed" vault/inbox/staged-new.md
git -C "$W" rm -q --cached -f vault/inbox/staged-new.md; rm "$W/vault/inbox/staged-new.md"

new vault/inbox/edited.md 'first version'; ci vault/inbox/edited.md
new vault/inbox/edited.md 'second version'
stale "a clean edit that is not staged" vault/inbox/edited.md
git -C "$W" add vault/inbox/edited.md
out="$(add vault/inbox/edited.md edited 2>&1)"; rc=$?
t '[ $rc -eq 0 ] && [ "$(in_index "$out")" = "second version" ]' "once staged, what is committed is what was scanned" "rc=$rc $out"
git -C "$W" commit -q -m edited

new vault/inbox/flagged.md 'first version'; ci vault/inbox/flagged.md
git -C "$W" update-index --assume-unchanged vault/inbox/flagged.md
new vault/inbox/flagged.md 'second version'
stale "an edit hidden with assume-unchanged" vault/inbox/flagged.md
git -C "$W" update-index --no-assume-unchanged vault/inbox/flagged.md
git -C "$W" checkout -q -- vault/inbox/flagged.md

git -C "$W" config core.autocrlf true
printf 'one\ntwo\n' > "$W/vault/inbox/crlf.md"; ci vault/inbox/crlf.md 2>/dev/null
printf 'one\r\ntwo\r\n' > "$W/vault/inbox/crlf.md"
out="$(add vault/inbox/crlf.md crlf 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "line endings alone do not count as a different version" "rc=$rc $out"
git -C "$W" commit -q -m crlf 2>/dev/null
git -C "$W" config core.autocrlf false

# --- never overwrites ---------------------------------------------------------------------------
new "$RAW/meetings/2026-02-01-taken.md" 'the original'
git -C "$W" add "$RAW/meetings/2026-02-01-taken.md"; git -C "$W" commit -q -m taken
taken_case() {  # taken_case <label> <file>
  local out rc; out="$(ra "$2" --project acme-notes --kind meetings --date 2026-02-01 --slug taken 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && [ -f "$W/$2" ] && [ "$(cat "$W/$RAW/meetings/2026-02-01-taken.md")" = "the original" ]; } && ok "never overwrites: $1" || bad "never overwrites: $1 (rc=$rc)" "$out"
}
new intake/again.md 'a newcomer'
taken_case "an untracked file" intake/again.md
new vault/inbox/again.md 'a tracked newcomer'
git -C "$W" add vault/inbox/again.md; git -C "$W" commit -q -m again
taken_case "a tracked file" vault/inbox/again.md
new intake/upper.TXT 'other suffix'
taken_case "a name that only becomes equal after the suffix changes" intake/upper.TXT
rm "$W/$RAW/meetings/2026-02-01-taken.md"
out="$(ra intake/again.md --project acme-notes --kind meetings --date 2026-02-01 --slug taken 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && [ -f "$W/intake/again.md" ] && [ ! -e "$W/$RAW/meetings/2026-02-01-taken.md" ]' "never overwrites: a name git still holds" "rc=$rc $out"
git -C "$W" checkout -q -- "$RAW/meetings/2026-02-01-taken.md"

# Exclusive create is what stops a second writer between the check and the move.
out="$($PY - "$PLUGIN/tools" "$W" <<'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import gate, raw_add
root = Path(sys.argv[2])
src, dest = root / "intake" / "race.md", root / "intake" / "race-dest.md"
src.write_text("mine", encoding="utf-8")
dest.write_text("theirs", encoding="utf-8")
try:
    raw_add.move_untracked(src, dest)
    print("moved")
except gate.Refused:
    print(dest.read_text(encoding="utf-8"), src.read_text(encoding="utf-8"))
PY
)"
t '[ "$out" = "theirs mine" ]' "the untracked move refuses a name taken after the check" "$out"
rm -f "$W/intake/race.md" "$W/intake/race-dest.md"

# --- the guard, the permissions and the skills ---------------------------------------------------
cmd="hg-tool raw-add vault/inbox/x.md --project acme-notes --kind meetings --date 2026-01-15 --slug x"
out="$(printf '{"tool_name":"Bash","tool_input":{"command":%s},"cwd":"%s"}' "$(json_str "$cmd")" "$W" | hg guard-bash 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the Bash guard lets raw-add through" "$out"

settings="$PLUGIN/templates/workspace/.claude/settings.json"
for rule in 'Edit(vault/raw/**)' 'Edit(gates/**)'; do
  cat "$settings" | jtrue "'$rule' in d['permissions']['deny']" && ok "the template still denies $rule" || bad "the template still denies $rule" "$(cat "$settings")"
done
out="$(grep -nE 'mkdir|\bmv\b' "$PLUGIN"/skills/*/SKILL.md)"
t '[ -z "$out" ]' "no skill tells the agent to mkdir or mv" "$out"
out="$(grep -rnE '\bgit mv\b' "$PLUGIN/templates/workspace" "$PLUGIN/skills")"
t '[ -z "$out" ]' "no template or skill sends a file through git mv" "$out"

SKILL="$PLUGIN/skills/import-source/SKILL.md"
grep -qF 'hg-tool raw-add <file> --project <p> --kind <k> --date <captured> --slug <slug>' "$SKILL" && ok "import-source runs raw-add" || bad "import-source runs raw-add"
grep -qF 'stops' "$SKILL" && grep -qF 'Any refusal' "$SKILL" && ok "a refusal stops the flow" || bad "a refusal stops the flow"
grep -qF 'under `vault/inbox/` or `intake/`' "$SKILL" && ok "import-source names the two accepted folders" || bad "import-source names the two accepted folders"
grep -qF 'hg-tool raw-add' "$PLUGIN/rules/boundaries.md" && ok "the boundaries name the writer" || bad "the boundaries name the writer"
grep -qF 'hg-tool raw-add' "$PLUGIN/templates/workspace/vault/raw/README.md" && ok "the raw README names the writer" || bad "the raw README names the writer"
hg 2>&1 | grep -q 'raw-add <file>' && ok "usage lists raw-add" || bad "usage lists raw-add"
grep -A3 '^  raw-add)' "$PLUGIN/bin/hg-tool" | grep -q "MSYS2_ARG_CONV_EXCL='\*'" && ok "raw-add is on the free-text branch" || bad "raw-add is on the free-text branch"

# --- every file of this stage ----------------------------------------------------------------
NEW="$PLUGIN/tools/raw_add.py $REPO_ROOT/tests/raw/test-raw-add.sh"
out="$(hg scan $NEW 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "these files hold nothing secret-shaped" "$out"
out="$(grep -n $'\xe2\x80\x94' $NEW "$SKILL")"
t '[ -z "$out" ]' "no em dashes" "$out"
out="$(grep -nE '^(from|import) ' "$PLUGIN/tools/raw_add.py" | grep -vE 'import (datetime|os|re|stat|sys|gate|scan|kit_registry as kr)( |$)|from pathlib import Path')"
t '[ -z "$out" ]' "raw-add imports only the standard library and the kit" "$out"

echo "raw-add: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
