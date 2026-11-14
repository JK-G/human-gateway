#!/usr/bin/env bash
# test-raw-ref.sh - hg-tool raw-ref: how a tracked file names a raw file that stays on one machine.
# A reference is computed from the file, so it resolves again wherever the same vault/raw/ folder is copied, and a
# colleague who lacks the file is told so without any path. Also: the private folders are defined once in the kit
# and once in the scanner, and the two agree.
# Self-contained: fictional data in a temp repo. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TMP="$(temp_dir hg-raw-ref)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { case "$1" in *"$2"*) return 0;; *) return 1;; esac; }

W="$TMP/dept"
out="$(hg setup --root "$W" --name Dept --project acme-notes 2>&1)"; t '[ $? -eq 0 ]' "setup succeeds" "$out"
git -C "$W" config user.email reviewer@example.com; git -C "$W" config user.name Reviewer; git -C "$W" config core.autocrlf false
git -C "$W" add -A; git -C "$W" commit -q -m base
jedit "$W/.claude/hg.json" "$W/.claude/hg.json" 'd["projects"].append("other-one")'
rr() { (cd "$1" && CLAUDE_PROJECT_DIR="$1" hg raw-ref "${@:2}"); }  # rr <workspace> <args>
printf '# Kickoff\nWe agreed on three price tiers.\n' > "$W/intake/kickoff.md"
DEST="$(cd "$W" && CLAUDE_PROJECT_DIR="$W" hg raw-add intake/kickoff.md --project acme-notes --kind meetings --date 2026-11-12 --slug kickoff 2>/dev/null)"
t '[ "$DEST" = "vault/raw/acme-notes/meetings/2026-11-12-kickoff.md" ]' "the source is brought in" "$DEST"

# --- the reference ------------------------------------------------------------------------------
REF="$(rr "$W" "$DEST")"; rc=$?
printf '%s' "$REF" | grep -qxE 'src:(meetings|interviews|sources|snapshots):[0-9]{4}-[0-9]{2}-[0-9]{2}:[0-9a-f]{8}' && [ $rc -eq 0 ] \
  && ok "a raw file gets a reference of the documented shape" || bad "a raw file gets a reference of the documented shape (rc=$rc)" "$REF"
h8="$($PY -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:8])' "$W/$DEST")"
t '[ "$REF" = "src:meetings:2026-11-12:$h8" ]' "the reference holds the folder's kind, the name's date and 8 hex digits of the file's sha256" "$REF vs $h8"
mkdir -p "$W/vault/raw/other-one/meetings"
cp "$W/$DEST" "$W/vault/raw/other-one/meetings/2026-11-12-copy.md"
t '[ "$(rr "$W" vault/raw/other-one/meetings/2026-11-12-copy.md)" = "$REF" ]' "the same bytes under another project give the same reference"
t '[ "$(rr "$W" "$W/$DEST")" = "$REF" ]' "an absolute path gives the same reference"
if command -v cygpath >/dev/null 2>&1; then
  t '[ "$(rr "$W" "$(cygpath -u "$W/$DEST")")" = "$REF" ]' "a /d/x path gives the same reference"
fi
printf 'x\n' > "$W/vault/projects/acme-notes/2026-11-12-notes.md"
out="$(rr "$W" vault/projects/acme-notes/2026-11-12-notes.md 2>&1)"; rc=$?
t '[ $rc -eq 1 ]' "a file outside vault/raw/ has no reference" "rc=$rc $out"
printf 'x\n' > "$W/vault/raw/acme-notes/meetings/kickoff-notes.md"
out="$(rr "$W" vault/raw/acme-notes/meetings/kickoff-notes.md 2>&1)"; rc=$?
t '[ $rc -eq 1 ]' "a name without a date has no reference" "rc=$rc $out"
mkdir -p "$W/vault/raw/acme-notes/notes"; printf 'x\n' > "$W/vault/raw/acme-notes/notes/2026-11-12-x.md"
out="$(rr "$W" vault/raw/acme-notes/notes/2026-11-12-x.md 2>&1)"; rc=$?
t '[ $rc -eq 1 ]' "a folder that is not one of the four kinds gives no reference" "rc=$rc $out"
rm -rf "$W/vault/raw/acme-notes/notes" "$W/vault/raw/acme-notes/meetings/kickoff-notes.md"
out="$(rr "$W" "$TMP/elsewhere.md" 2>&1)"; rc=$?
t '[ $rc -eq 1 ]' "a path outside the workspace has no reference" "rc=$rc $out"
rr "$W" >/dev/null 2>&1; t '[ $? -eq 2 ]' "no argument is a usage error"
rr "$W" --find >/dev/null 2>&1; t '[ $? -eq 2 ]' "--find with no reference is a usage error"
out="$(rr "$W" --say 'raw/acme-notes/meetings/2026-11-12-kickoff.md' 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && ! has "$out" kickoff' "a path is not a reference, and the refusal does not repeat it" "rc=$rc $out"

# --- finding it again ---------------------------------------------------------------------------
out="$(rr "$W" --find "$REF")"; rc=$?
t '[ $rc -eq 0 ] && [ "$(printf "%s\n" "$out" | head -n 1)" = "$DEST" ]' "--find prints the path of a file that is here" "rc=$rc $out"
out="$(rr "$W" --find src:meetings:2026-11-12:00000000 2>&1)"; rc=$?
t '[ $rc -eq 1 ] && has "$out" "this source is not on this machine."' "--find exits 1 for a reference no file here has" "rc=$rc $out"

# --- what a reader is told ------------------------------------------------------------------------
say_here_en="Private source (meeting, 2026-11-12). The file is on this computer: $DEST. It is not in the repository."
say_away_en="Private source (meeting, 2026-11-12). The file is not in the repository and not on this computer. It stayed with the person who brought it in. The page's change history shows who published the page."
say_here_pl="Źródło prywatne (spotkanie, 2026-11-12). Plik jest na tym komputerze: $DEST. W repozytorium go nie ma."
say_away_pl="Źródło prywatne (spotkanie, 2026-11-12). Pliku nie ma w repozytorium ani na tym komputerze. Został u osoby, która go wniosła. Kto opublikował stronę, pokazuje historia zmian tej strony."
out="$(rr "$W" --say "$REF")"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "$say_here_en" ]' "--say names the file when it is here (English)" "$out"
C="$TMP/colleague"
git clone -q "$W" "$C"
out="$(rr "$C" --say "$REF")"; rc=$?
t '[ $rc -eq 0 ] && [ "$out" = "$say_away_en" ]' "--say says it is not here, and names no person (English)" "$out"
{ has "$out" "vault/raw" || has "$out" "kickoff" || has "$out" "@"; } && bad "--say never prints a path for a source that is not here" "$out" || ok "--say never prints a path for a source that is not here"
jedit "$W/.claude/hg.json" "$W/.claude/hg.json" 'd["language"]["content"]="pl"'
jedit "$C/.claude/hg.json" "$C/.claude/hg.json" 'd["language"]["content"]="pl"'
t '[ "$(rr "$W" --say "$REF")" = "$say_here_pl" ]' "--say names the file when it is here (Polish)" "$(rr "$W" --say "$REF")"
t '[ "$(rr "$C" --say "$REF")" = "$say_away_pl" ]' "--say says it is not here, and names no person (Polish)" "$(rr "$C" --say "$REF")"
for kind in interviews:rozmowa sources:dokument snapshots:'zapis stanu'; do
  out="$(rr "$C" --say "src:${kind%%:*}:2026-01-02:0123abcd")"
  has "$out" "(${kind#*:}, 2026-01-02)" && ok "--say names the kind ${kind%%:*}" || bad "--say names the kind ${kind%%:*}" "$out"
done
rr "$C" --find "$REF" >/dev/null 2>&1; t '[ $? -eq 1 ]' "a fresh clone does not have the source"
mkdir -p "$C/vault/raw"; cp -R "$W/vault/raw/acme-notes" "$C/vault/raw/acme-notes"
out="$(rr "$C" --find "$REF")"; rc=$?
t '[ $rc -eq 0 ] && has "$out" "$DEST"' "a vault/raw/ folder copied into a fresh clone resolves again" "rc=$rc $out"
t '[ -z "$(git -C "$C" status --porcelain --untracked-files=all | grep vault/raw/)" ]' "the copied folder stays out of git in the clone" "$(git -C "$C" status --porcelain)"

# --- which sources are cited ----------------------------------------------------------------------
out="$(rr "$W" --list)"
printf '%s\n' "$out" | grep -qF "$REF"$'\t'"$DEST"$'\t'"uncited" && ok "--list marks a file uncited before any page holds its reference" || bad "--list marks a file uncited before any page holds its reference" "$out"
printf -- '---\ntype: concept\nproject: acme-notes\ntemporal: living\nstatus: active\nlast_verified: 2026-11-13\nsources: ["%s"]\naliases: []\nsummary: "Prices."\n---\n## Definition\nx\n## Related\ny\n' "$REF" > "$W/vault/wiki/concepts/acme-notes--prices.md"
out="$(rr "$W" --list)"
printf '%s\n' "$out" | grep -qF "$REF"$'\t'"$DEST"$'\t'"cited" && ok "--list marks a file cited once a wiki page holds its reference" || bad "--list marks a file cited once a wiki page holds its reference" "$out"
out="$(rr "$W" --list --json)"
printf '%s' "$out" | jtrue "any(r['ref']=='$REF' and r['path']=='$DEST' and r['cited'] for r in d)" && ok "--list --json says the same" || bad "--list --json says the same" "$out"
out="$(hg validate-frontmatter --root "$W" "$W/vault/wiki/concepts/acme-notes--prices.md" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "a page that cites a reference validates" "$out"

# --- a reference in YAML ----------------------------------------------------------------------
out="$($PY - "$PLUGIN/tools" "$REF" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import kit_registry as kr
ref = sys.argv[2]
cases = ['sources: [%s]' % ref, 'sources: ["%s"]' % ref, "sources:\n  - %s" % ref, "sources:\n  - '%s'" % ref,
         'source_raw: %s' % ref, 'source_raw: "%s"' % ref]
for text in cases:
    value = kr.parse_yaml(text)
    value = value.get("sources", [value.get("source_raw")])
    assert value == [ref], (text, value)
print("ok")
PY
)"
t '[ "$out" = ok ]' "a reference parses as a string in a flow list, a block list and a map value" "$out"

# --- one definition of the private folders, two copies ----------------------------------------------
out="$($PY - "$PLUGIN/tools" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import kit_registry as kr
import scan
for vault in ("vault", "kb", "notes/vault"):
    conf = dict(kr.DEFAULTS, VAULT_DIR=vault)
    assert kr.private_prefixes(conf) == scan.private_prefixes(vault), vault
    assert kr.kept_files(conf) == scan.kept_files(vault), vault
    probes = ["%s/raw/a/meetings/x.md" % vault, "%s/RAW/x.md" % vault.upper(), "%s/inbox/n.md" % vault, "%s/daily/d.md" % vault,
              "intake/x.xlsx", ".gateway/plans/p.json", "%s/wiki/a.md" % vault, "gates/a.md", "intake/README.md",
              "%s/raw/README.md" % vault, "%s/inbox/_template.md" % vault, "%s/daily/README.md" % vault, "intakes/x.md"]
    for p in probes:
        assert kr.is_private(p, conf) == scan.is_private(p, vault), (vault, p)
assert kr.private_prefixes() == ["vault/raw/", "vault/inbox/", "vault/daily/", "intake/", ".gateway/"]
assert kr.kept_files() == ["vault/raw/README.md", "vault/inbox/_template.md", "vault/daily/README.md", "intake/README.md"]
print("ok")
PY
)"
t '[ "$out" = ok ]' "kit_registry and scan.py agree on the private folders and the four kept files" "$out"

# --- the entry point and this stage's files -------------------------------------------------------
hg 2>&1 | grep -q 'raw-ref <path>' && ok "usage lists raw-ref" || bad "usage lists raw-ref"
grep -A3 '^  raw-ref)' "$PLUGIN/bin/hg-tool" | grep -q "MSYS2_ARG_CONV_EXCL='\*'" && ok "raw-ref is on the free-text branch" || bad "raw-ref is on the free-text branch"
out="$(grep -nE '^(from|import) ' "$PLUGIN/tools/raw_ref.py" | grep -vE 'import (hashlib|json|os|re|sys|gate|scan|kit_registry as kr)( |$)|from pathlib import Path')"
t '[ -z "$out" ]' "raw-ref imports only the standard library and the kit" "$out"
NEW="$PLUGIN/tools/raw_ref.py $REPO_ROOT/tests/raw/test-raw-ref.sh"
out="$(hg scan $NEW 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "these files hold nothing secret-shaped" "$out"
out="$(grep -n $'\xe2\x80\x94' $NEW)"
t '[ -z "$out" ]' "no em dashes" "$out"

echo "raw-ref: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
