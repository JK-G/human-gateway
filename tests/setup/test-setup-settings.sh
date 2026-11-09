#!/usr/bin/env bash
# test-setup-settings.sh - hg-tool setup over an existing .claude/settings.json: what is missing is added,
# what is there stays, and a file that is not valid JSON is not touched.
# `claude plugin install hg@human-gateway --scope project` runs before /hg:setup and writes that file with
# only enabledPlugins, so this is the main install path. Self-contained. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
TEMPLATE="$REPO_ROOT/plugins/hg/templates/workspace/.claude/settings.json"
TMP="$(temp_dir hg-setup-settings)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
has()  { printf '%s' "$1" | grep -q "$2" && ok "$3" || bad "$3" "$1"; }
hasnt() { printf '%s' "$1" | grep -q "$2" && bad "$3" "$1" || ok "$3"; }
folder() {  # folder <name> <settings text>: a new folder holding only that settings file
  mkdir -p "$TMP/$1/.claude"; printf '%b' "$2" > "$TMP/$1/.claude/settings.json"; printf '%s' "$TMP/$1"
}
settings_has_template() {  # every template rule is present, once
  $PY -c 'import json,sys
want=json.load(open(sys.argv[1],encoding="utf-8"))["permissions"]
have=json.load(open(sys.argv[2],encoding="utf-8-sig"))["permissions"]
sys.exit(0 if all(have[k].count(r)==1 for k in ("allow","deny") for r in want[k]) else 1)' "$TEMPLATE" "$1/.claude/settings.json"
}
INSTALLED='{\n  "enabledPlugins": {\n    "hg@human-gateway": true\n  }\n}\n'

# --- the file exists with only enabledPlugins ------------------------------------------------
A="$(folder only-plugins "$INSTALLED")"
out="$(hg setup --root "$A" --name Dept --marketplace acme/hg-market)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds over the file the install writes" "$out"
has "$out" $'^updated\t.claude/settings.json$' "the file is reported as updated"
hasnt "$out" $'^skipped\t.claude/settings.json$' "the file is not reported as skipped"
hasnt "$out" 'not applied' "--marketplace is applied"
t 'settings_has_template "$A"' "every template allow and deny rule is added" "$(cat "$A/.claude/settings.json")"
settings="$(cat "$A/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'all(r in d["permissions"]["deny"] for r in ["Edit(vault/raw/**)","Edit(gates/**)"])' && ok "the protected paths are denied" || bad "the protected paths are denied" "$settings"
printf '%s' "$settings" | jtrue '"Bash(hg-tool *)" in d["permissions"]["allow"]' && ok "hg-tool is allowed" || bad "hg-tool is allowed" "$settings"
printf '%s' "$settings" | jtrue 'd["enabledPlugins"]=={"hg@human-gateway":True}' && ok "enabledPlugins is kept" || bad "enabledPlugins is kept" "$settings"
printf '%s' "$settings" | jtrue 'list(d)[0]=="enabledPlugins"' && ok "the existing key stays first" || bad "the existing key stays first" "$settings"
printf '%s' "$settings" | jtrue 'd["extraKnownMarketplaces"]["human-gateway"]["source"]=={"source":"github","repo":"acme/hg-market"}' && ok "the marketplace is added" || bad "the marketplace is added" "$settings"
out="$(hg doctor --root "$A")"
has "$out" $'^OK\tpermissions\t' "doctor sees the deny rules"
has "$out" $'^OK\tmarketplace\t' "doctor sees the marketplace"

N="$(folder no-marketplace "$INSTALLED")"
out="$(hg setup --root "$N" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds without --marketplace" "$out"
t 'settings_has_template "$N"' "the rules are added without --marketplace too" "$(cat "$N/.claude/settings.json")"
cat "$N/.claude/settings.json" | jtrue '"extraKnownMarketplaces" not in d' && ok "no marketplace is invented" || bad "no marketplace is invented" "$(cat "$N/.claude/settings.json")"

# --- a second run changes nothing ------------------------------------------------------------
cp "$A/.claude/settings.json" "$TMP/before.json"
out="$(hg setup --root "$A" --name Dept --marketplace acme/hg-market)"; rc=$?
t '[ $rc -eq 0 ]' "second run succeeds" "$out"
has "$out" $'^skipped\t.claude/settings.json$' "second run reports the file as skipped"
hasnt "$out" $'^note' "second run has nothing to note"
t 'cmp -s "$TMP/before.json" "$A/.claude/settings.json"' "second run leaves the same bytes" "$(cat "$A/.claude/settings.json")"

# --- a file that is not valid JSON is not touched --------------------------------------------
for shape in 'broken|{ "enabledPlugins": { ' 'array|[1, 2]\n' 'empty|'; do
  name="${shape%%|*}"
  B="$(folder "$name" "${shape#*|}")"
  cp "$B/.claude/settings.json" "$TMP/$name.json"
  out="$(hg setup --root "$B" --name Dept --marketplace acme/hg-market)"; rc=$?
  t '[ $rc -eq 1 ]' "$name: setup reports a failure" "rc=$rc $out"
  has "$out" $'^error\t.claude/settings.json is not valid JSON' "$name: the message names the problem"
  has "$out" 'Correct the file, then run /hg:setup again' "$name: the message says what to do"
  t 'cmp -s "$TMP/$name.json" "$B/.claude/settings.json"' "$name: the file keeps its bytes" "$(cat "$B/.claude/settings.json")"
  t '[ -f "$B/.claude/hg.json" ] && [ -f "$B/vault/schema.md" ]' "$name: the rest of the workspace is still created" "$out"
done
out="$(hg doctor --root "$TMP/broken")"
has "$out" $'^WARN\tpermissions\t' "doctor warns about a file it cannot read"

# --- an existing custom rule and other settings are kept -------------------------------------
C="$(folder custom '{\n  "model": "zespół",\n  "permissions": {\n    "defaultMode": "plan",\n    "allow": ["Bash(npm test)", "Bash(hg-tool *)"],\n    "deny": ["Read(./secret/**)"]\n  },\n  "enabledPlugins": {"other@acme": true}\n}\n')"
out="$(hg setup --root "$C" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds over custom settings" "$out"
has "$out" $'^updated\t.claude/settings.json$' "custom settings are reported as updated"
t 'settings_has_template "$C"' "the missing rules are added, a rule already there is not repeated" "$(cat "$C/.claude/settings.json")"
settings="$(cat "$C/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["permissions"]["allow"]==["Bash(npm test)","Bash(hg-tool *)"]' && ok "a custom allow rule is kept in its place" || bad "a custom allow rule is kept in its place" "$settings"
printf '%s' "$settings" | jtrue 'd["permissions"]["deny"][0]=="Read(./secret/**)"' && ok "a custom deny rule stays first" || bad "a custom deny rule stays first" "$settings"
printf '%s' "$settings" | jtrue 'd["permissions"]["defaultMode"]=="plan" and d["enabledPlugins"]=={"other@acme":True}' && ok "other values are kept" || bad "other values are kept" "$settings"
printf '%s' "$settings" | jtrue 'list(d)==["model","permissions","enabledPlugins"] and list(d["permissions"])==["defaultMode","allow","deny"]' && ok "the order of the keys is kept" || bad "the order of the keys is kept" "$settings"
grep -qF '"model": "zespół"' "$C/.claude/settings.json" && ok "non-ASCII text is kept" || bad "non-ASCII text is kept" "$settings"

D="$(folder bom '\xef\xbb\xbf{"enabledPlugins": {"hg@human-gateway": true}}\n')"
out="$(hg setup --root "$D" --name Dept)"; rc=$?
{ [ $rc -eq 0 ] && settings_has_template "$D"; } && ok "a file saved with a byte order mark is read" || bad "a file saved with a byte order mark is read (rc=$rc)" "$out"

# --- an entry that differs is left alone and reported ----------------------------------------
E="$(folder differs '{"extraKnownMarketplaces": {"human-gateway": {"source": {"source": "github", "repo": "acme/first"}}, "other": {"source": {"source": "github", "repo": "acme/other"}}}}\n')"
out="$(hg setup --root "$E" --name Dept --marketplace acme/second)"; rc=$?
t '[ $rc -eq 0 ]' "a differing marketplace is not a failure" "$out"
has "$out" $'^note\t--marketplace not applied' "a differing marketplace is reported"
settings="$(cat "$E/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["extraKnownMarketplaces"]["human-gateway"]["source"]["repo"]=="acme/first" and "other" in d["extraKnownMarketplaces"]' && ok "a differing marketplace is left alone" || bad "a differing marketplace is left alone" "$settings"
t 'settings_has_template "$E"' "the rules are still added" "$settings"

G="$(folder other-market '{"extraKnownMarketplaces": {"other": {"source": {"source": "github", "repo": "acme/other"}}}}\n')"
out="$(hg setup --root "$G" --name Dept --marketplace acme/hg-market)"
settings="$(cat "$G/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["extraKnownMarketplaces"]["human-gateway"]["source"]["repo"]=="acme/hg-market" and "other" in d["extraKnownMarketplaces"]' && ok "another marketplace stays beside this one" || bad "another marketplace stays beside this one" "$settings"

H="$(folder odd-allow '{"permissions": {"allow": "Bash(npm test)"}}\n')"
out="$(hg setup --root "$H" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "an allow that is not a list is not a failure" "$out"
has "$out" $'^note\t.claude/settings.json: permissions.allow is not a list' "an allow that is not a list is reported"
settings="$(cat "$H/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["permissions"]["allow"]=="Bash(npm test)" and "Edit(gates/**)" in d["permissions"]["deny"]' && ok "it is left alone and deny is still added" || bad "it is left alone and deny is still added" "$settings"

I="$(folder odd-permissions '{"permissions": true}\n')"
out="$(hg setup --root "$I" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "permissions that are not an object are not a failure" "$out"
has "$out" $'^note\t.claude/settings.json: permissions is not an object' "permissions that are not an object are reported"
has "$out" $'^skipped\t.claude/settings.json$' "and the file is not rewritten"
cat "$I/.claude/settings.json" | jtrue 'd["permissions"] is True' && ok "they are left alone" || bad "they are left alone" "$(cat "$I/.claude/settings.json")"
out="$(hg doctor --root "$I")"
has "$out" $'^WARN\tpermissions\t' "doctor warns when permissions are not an object"

# --- doctor warns when a deny rule is missing ------------------------------------------------
jedit "$A/.claude/settings.json" "$TMP/fewer.json" 'd["permissions"]["deny"].remove("Edit(gates/**)")'
cp "$TMP/fewer.json" "$A/.claude/settings.json"
out="$(hg doctor --root "$A")"; rc=$?
has "$out" $'^WARN\tpermissions\t.*Edit(gates/\*\*)' "doctor names the missing deny rule"
hasnt "$out" 'Edit(vault/raw/\*\*), ' "doctor does not name a rule that is there"
hasnt "$out" $'^ERROR\tpermissions' "a missing rule is a warning, not an error"
out="$(hg setup --root "$A")"
has "$out" $'^updated\t.claude/settings.json$' "setup puts a removed deny rule back"
out="$(hg doctor --root "$A")"
has "$out" $'^OK\tpermissions\t' "doctor is satisfied after that"

echo "setup-settings: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
