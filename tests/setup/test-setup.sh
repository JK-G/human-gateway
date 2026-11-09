#!/usr/bin/env bash
# test-setup.sh - hg-tool setup: an empty folder becomes a department workspace, a second run changes
# nothing, an existing file is never overwritten, and the result passes the plugin's own checks.
# Self-contained. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TEMPLATE="$PLUGIN/templates/workspace"
TMP="$(temp_dir hg-setup)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
fingerprint() {  # one hash over every path and its bytes, .git excluded
  $PY -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1])
rows=sorted("%s %s"%(p.relative_to(r).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for p in r.rglob("*") if p.is_file() and ".git" not in p.relative_to(r).parts)
print(hashlib.sha256("\n".join(rows).encode()).hexdigest())' "$1" | tr -d '\r'
}

# --- an empty folder becomes a workspace -------------------------------------------------
W="$TMP/dept one"
mkdir -p "$W"
out="$(hg setup --root "$W" --name "Zespół Produkt" --language pl --timezone Europe/Warsaw)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds on an empty folder" "$out"
for f in CLAUDE.md AGENTS.md .gitignore .gitattributes .claude/hg.json .claude/settings.json .claude/skills/setup/SKILL.md \
         gates/README.md intake/README.md vault/schema.md vault/index.md vault/daily/README.md vault/wiki/memory/index.md \
         vault/projects/_template/PRD.md vault/projects/_template/planning/.gitkeep vault/wiki/concepts/.gitkeep; do
  [ -f "$W/$f" ] && ok "created $f" || bad "created $f" "$out"
done
printf '%s' "$out" | grep -q $'^created\t.claude/hg.json$' && ok "reports what it created" || bad "reports what it created" "$out"
t '[ -d "$W/.git" ]' "git repository created"
branch="$(git -C "$W" symbolic-ref --short HEAD)"
t '[ "$branch" = main ]' "default branch is main" "$branch"

conf="$(cat "$W/.claude/hg.json")"
printf '%s' "$conf" | jtrue 'd["schemaVersion"]==1 and d["projectName"].endswith(" Produkt") and d["projects"]==[]' && ok "hg.json has the version and name" || bad "hg.json has the version and name" "$conf"
grep -qF '"projectName": "Zespół Produkt"' "$W/.claude/hg.json" && ok "hg.json keeps non-ASCII text" || bad "hg.json keeps non-ASCII text" "$conf"
printf '%s' "$conf" | jtrue 'd["language"]["content"]=="pl" and d["timezone"]=="Europe/Warsaw" and "gates/" in d["forbiddenWritePaths"]' && ok "hg.json has language, zone and forbidden paths" || bad "hg.json has language, zone and forbidden paths" "$conf"

left="$(grep -rlF '{{' "$W" --exclude-dir=.git)"
t '[ -z "$left" ]' "no template token is left" "$left"
grep -q '^# Zespół Produkt workspace$' "$W/CLAUDE.md" && ok "CLAUDE.md has the name" || bad "CLAUDE.md has the name"
grep -q 'Write to people in pl\.' "$W/AGENTS.md" && ok "AGENTS.md has the language" || bad "AGENTS.md has the language"
grep -q 'only under Claude Code' "$W/AGENTS.md" && ok "AGENTS.md says the hooks are Claude Code only" || bad "AGENTS.md says the hooks are Claude Code only"

leftover="$(cd "$W" && find . -path ./.git -prune -o \( -name 'example--*' -o -name 'acme*' -o -name digests \) -print)"
t '[ -z "$leftover" ]' "no fictional examples or digest folders" "$leftover"

# --- the workspace passes the plugin's own checks ----------------------------------------
out="$(hg index --root "$W" --check)"; t '[ $? -eq 0 ]' "index check passes on a fresh workspace" "$out"
out="$(hg validate-frontmatter --root "$W")"; rc=$?
t '[ $rc -eq 0 ]' "validate-frontmatter passes on a fresh workspace" "$out"
out="$(hg registry --root "$W" types)"; printf '%s\n' "$out" | grep -qx memory && ok "registry reads the template schema" || bad "registry reads the template schema" "$out"
out="$(CLAUDE_PROJECT_DIR="$W" hg session-start)"; printf '%s' "$out" | grep -q 'Human Gateway department workspace' && ok "session-start speaks in the new workspace" || bad "session-start speaks in the new workspace" "$out"
out="$(CLAUDE_PROJECT_DIR="$W" KIT_TODAY=2026-02-02 hg today-data)"; printf '%s' "$out" | jtrue 'd["date"]=="2026-02-02"' && ok "today-data works in the new workspace" || bad "today-data works in the new workspace" "$out"

out="$(hg doctor --root "$W")"; rc=$?
if printf '%s' "$out" | grep -qE $'^ERROR\t(git|gh)\t'; then
  echo "n/a  - doctor pass not asserted: git or gh missing on this machine"
else
  t '[ $rc -eq 0 ]' "doctor passes on a fresh workspace" "$out"
fi
printf '%s' "$out" | grep -q $'^WARN\tmarketplace\t' && ok "doctor warns when no marketplace is configured" || bad "doctor warns when no marketplace is configured" "$out"
printf '%s' "$out" | grep -q $'^WARN\tgitignore' && bad "doctor accepts the template's .gitignore" "$out" || ok "doctor accepts the template's .gitignore"

ignored() { git -C "$W" check-ignore -q "$1"; }
for f in vault/daily/2026-01-30.md intake/report.xlsx DASHBOARD.md .gateway/x .claude/state/x .claude/settings.local.json .env .env.local prod.env cert.pem store.p12 store.pfx; do
  ignored "$f" && ok "ignored: $f" || bad "ignored: $f"
done
for f in vault/daily/README.md intake/README.md vault/wiki/concepts/x.md gates/a.md .claude/hg.json; do
  ignored "$f" && bad "tracked: $f" || ok "tracked: $f"
done
for f in vault/log.jsonl vault/journal/2026-01-30.md; do
  [ "$(git -C "$W" check-attr merge -- "$f" | sed 's/.*: //')" = union ] && ok "merge=union: $f" || bad "merge=union: $f"
done
[ "$(git -C "$W" check-attr eol -- CLAUDE.md | sed 's/.*: //')" = lf ] && ok "eol=lf" || bad "eol=lf"

settings="$(cat "$W/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["permissions"]["allow"]==["Bash(hg-tool *)"]' && ok "settings allow hg-tool" || bad "settings allow hg-tool" "$settings"
printf '%s' "$settings" | jtrue 'all(r in d["permissions"]["deny"] for r in ["Edit(vault/raw/**)","Edit(gates/**)","Bash(git push --force*)","Bash(rm -rf ~/)"])' && ok "settings deny the protected paths" || bad "settings deny the protected paths" "$settings"
printf '%s' "$settings" | jtrue 'not any(r.startswith("Write(") for r in d["permissions"]["deny"])' && ok "no Write() deny rules: Claude Code matches file writes against Edit() only" || bad "no Write() deny rules: Claude Code matches file writes against Edit() only" "$settings"
printf '%s' "$settings" | jtrue 'd["enabledPlugins"]=={"hg@human-gateway":True} and "extraKnownMarketplaces" not in d' && ok "plugin enabled, no marketplace unless asked" || bad "plugin enabled, no marketplace unless asked" "$settings"

out="$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s/gates/a.md"},"cwd":"%s"}' "$W" "$W" | CLAUDE_PROJECT_DIR="$W" hg guard-write 2>&1)"
t '[ $? -eq 2 ]' "the guard protects gates/ in a new workspace" "$out"

# --- a second run changes nothing --------------------------------------------------------
before="$(fingerprint "$W")"; head_before="$(git -C "$W" rev-parse --git-dir >/dev/null && cat "$W/.git/HEAD")"
out="$(hg setup --root "$W" --name "Other" --language en --timezone UTC)"; rc=$?
t '[ $rc -eq 0 ]' "second run succeeds" "$out"
printf '%s' "$out" | grep -q '^created' && bad "second run creates nothing" "$out" || ok "second run creates nothing"
printf '%s' "$out" | grep -q $'^skipped\tCLAUDE.md$' && ok "second run reports skipped files" || bad "second run reports skipped files" "$out"
printf '%s' "$out" | grep -q $'^skipped\t.git$' && ok "second run does not re-init git" || bad "second run does not re-init git" "$out"
after="$(fingerprint "$W")"
t '[ "$before" = "$after" ]' "second run changes no file" "$before / $after"
t '[ "$head_before" = "$(cat "$W/.git/HEAD")" ]' "git HEAD untouched"

# --- a modified file is never overwritten, a missing one comes back ----------------------
printf 'mine\n' > "$W/CLAUDE.md"
printf '{ "schemaVersion": 1, "projectName": "Kept" }\n' > "$W/.claude/hg.json"
printf 'mine\n' > "$W/vault/schema.md"
rm "$W/vault/README.md"
out="$(hg setup --root "$W" --name Other)"; rc=$?
t '[ $rc -eq 0 ]' "run over a modified workspace succeeds" "$out"
t '[ "$(cat "$W/CLAUDE.md")" = mine ]' "a modified CLAUDE.md is kept"
t '[ "$(cat "$W/vault/schema.md")" = mine ]' "a modified schema is kept"
grep -q Kept "$W/.claude/hg.json" && ok "an existing hg.json is kept" || bad "an existing hg.json is kept"
t '[ -f "$W/vault/README.md" ]' "a missing file comes back" "$out"
t '[ "$(printf "%s" "$out" | grep -c "^created")" -eq 1 ]' "only the missing file is created" "$out"

# --- a folder that already has a .gitignore --------------------------------------------
V="$TMP/existing"
mkdir -p "$V"; printf 'node_modules/\n.env' > "$V/.gitignore"
out="$(hg setup --root "$V" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds over an existing .gitignore" "$out"
printf '%s' "$out" | grep -q $'^updated\t.gitignore$' && ok "the existing .gitignore is reported as updated" || bad "the existing .gitignore is reported as updated" "$out"
head -n 1 "$V/.gitignore" | grep -qx 'node_modules/' && ok "the person's lines stay first" || bad "the person's lines stay first" "$(cat "$V/.gitignore")"
grep -c '^\.env$' "$V/.gitignore" | grep -qx 1 && ok "a line already there is not repeated" || bad "a line already there is not repeated" "$(cat "$V/.gitignore")"
grep -qx '# hg workspace' "$V/.gitignore" && ok "the added block is marked" || bad "the added block is marked" "$(cat "$V/.gitignore")"
for f in intake/held.md vault/daily/2026-01-30.md DASHBOARD.md node_modules/x; do
  git -C "$V" check-ignore -q "$f" && ok "ignored after setup: $f" || bad "ignored after setup: $f" "$(cat "$V/.gitignore")"
done
git -C "$V" check-ignore -q intake/README.md && bad "intake/README.md stays tracked" || ok "intake/README.md stays tracked"
out="$(hg doctor --root "$V")"
printf '%s' "$out" | grep -q $'^OK\tgitignore' && ok "doctor accepts the extended .gitignore" || bad "doctor accepts the extended .gitignore" "$out"
before="$(cat "$V/.gitignore")"
out="$(hg setup --root "$V")"
printf '%s' "$out" | grep -q $'^skipped\t.gitignore$' && ok "a second run leaves .gitignore alone" || bad "a second run leaves .gitignore alone" "$out"
t '[ "$before" = "$(cat "$V/.gitignore")" ]' "the second run adds nothing"
grep -q 'gitignore' "$PLUGIN/skills/setup/SKILL.md" && ok "/hg:setup explains the gitignore warning" || bad "/hg:setup explains the gitignore warning"
grep -q 'git check-ignore -q intake/x' "$PLUGIN/skills/init/SKILL.md" && ok "/hg:init checks that intake/ is private" || bad "/hg:init checks that intake/ is private"

# --- options -----------------------------------------------------------------------------
M="$TMP/market"
out="$(hg setup --root "$M" --marketplace acme/hg-market --project acme-notes)"; rc=$?
t '[ $rc -eq 0 ]' "setup creates a missing folder" "$out"
settings="$(cat "$M/.claude/settings.json")"
printf '%s' "$settings" | jtrue 'd["extraKnownMarketplaces"]["human-gateway"]["source"]=={"source":"github","repo":"acme/hg-market"}' && ok "--marketplace is written" || bad "--marketplace is written" "$settings"
out="$(hg doctor --root "$M")"
printf '%s' "$out" | grep -q $'^OK\tmarketplace\t' && ok "doctor sees the marketplace" || bad "doctor sees the marketplace" "$out"
printf '%s' "$(cat "$M/.claude/hg.json")" | jtrue 'd["projects"]==["acme-notes"] and d["projectName"]=="market" and d["language"]["content"]=="en"' && ok "--project and defaults reach hg.json" || bad "--project and defaults reach hg.json" "$(cat "$M/.claude/hg.json")"
for f in vault/projects/acme-notes/CLAUDE.md vault/projects/acme-notes/PRD.md vault/projects/acme-notes/planning/.gitkeep \
         vault/raw/acme-notes/meetings/.gitkeep vault/raw/acme-notes/snapshots/.gitkeep; do
  [ -f "$M/$f" ] && ok "project: $f" || bad "project: $f" "$out"
done
left="$(grep -rlE '__(SLUG|NAME|DATE)__' "$M/vault/projects/acme-notes")"
t '[ -z "$left" ]' "project placeholders are filled" "$left"
grep -q '^# Acme Notes: project context$' "$M/vault/projects/acme-notes/CLAUDE.md" && ok "project name comes from the slug" || bad "project name comes from the slug"
out="$(hg index --root "$M" --check)"; t '[ $? -eq 0 ]' "index check passes with a project" "$out"

out="$(hg setup --root "$M" --project second-one)"
[ -f "$M/vault/projects/second-one/PRD.md" ] && ok "--project works in an existing workspace" || bad "--project works in an existing workspace" "$out"
printf '%s' "$out" | grep -q $'^note\tadd "second-one" to projects' && ok "an unlisted project gets a note" || bad "an unlisted project gets a note" "$out"
printf '%s' "$(cat "$M/.claude/hg.json")" | jtrue '"second-one" not in d["projects"]' && ok "hg.json stays as it was" || bad "hg.json stays as it was"
out="$(hg setup --root "$W" --marketplace acme/other)"
printf '%s' "$out" | grep -q $'^updated\t.claude/settings.json$' && ok "--marketplace is added to existing settings" || bad "--marketplace is added to existing settings" "$out"

for bad_args in "--project Bad_Slug" "--project cross" "--marketplace nope" "--language p!" "--timezone a;b" "--unknown"; do
  # shellcheck disable=SC2086
  hg setup --root "$TMP/usage" $bad_args >/dev/null 2>&1; rc=$?
  t '[ $rc -eq 2 ]' "usage error: $bad_args" "rc=$rc"
done
t '[ ! -e "$TMP/usage" ]' "a usage error creates nothing"

# --- Windows path shapes and free text ----------------------------------------------------
if command -v cygpath >/dev/null 2>&1; then
  for form in u w m; do
    D="$TMP/form-$form"
    out="$(hg setup --root "$(cygpath -$form "$D")" --name form)"; rc=$?
    { [ $rc -eq 0 ] && [ -f "$D/.claude/hg.json" ]; } && ok "root in the -$form shape" || bad "root in the -$form shape (rc=$rc)" "$out"
  done
  drive="$(printf '%s' "${TMP%%:*}" | tr 'A-Z' 'a-z')"
  D="$TMP/form-drive"
  out="$(hg setup --root "/$drive${TMP#*:}/form-drive" --name form)"; rc=$?
  { [ $rc -eq 0 ] && [ -f "$D/.claude/hg.json" ]; } && ok "root in the /d/x shape" || bad "root in the /d/x shape (rc=$rc)" "$out"
  D="$TMP/free"
  out="$(env -u MSYS2_ARG_CONV_EXCL bash "$HG_TOOL" setup --root "$D" --name "/Team/Alpha")"
  grep -q '^# /Team/Alpha workspace$' "$D/CLAUDE.md" && ok "free text is not rewritten by Git Bash" || bad "free text is not rewritten by Git Bash" "$out"
  out="$(hg doctor --root "$W")"
  printf '%s' "$out" | grep -q $'^OK\tgit-bash\t' && ok "doctor finds Git Bash" || bad "doctor finds Git Bash" "$out"
  out="$($PY -c 'import sys; sys.path.insert(0, sys.argv[1]); import doctor; doctor.find_git_bash = lambda: None; f = doctor.Findings(); doctor.check_git_bash(f); sys.exit(f.errors)' "$PLUGIN/tools")"; rc=$?
  { [ $rc -eq 1 ] && printf '%s' "$out" | grep -q $'^ERROR\tgit-bash\t'; } && ok "doctor reports a missing Git Bash as an error" || bad "doctor reports a missing Git Bash as an error (rc=$rc)" "$out"
else
  out="$(hg doctor --root "$W")"
  printf '%s' "$out" | grep -q 'git-bash' && bad "no Git Bash check outside Windows" "$out" || ok "no Git Bash check outside Windows"
fi

# --- the template itself ------------------------------------------------------------------
strict='\.claude/(tools|adapters|routines|commands)|kit\.conf|\bjq\b|heartbeat|[Rr]outine|digest|playbook|\btasks/|\bcode/|`agents/|[Aa]cme|example--|new-project|remove-examples|lint-|docs/|(^|[^/:])/(today|dayend|ingest|import-source|wiki-query|wiki-lint|wiki-dedup|capture-task|decision-log)\b'
out="$(grep -rnE "$strict" "$TEMPLATE")"
t '[ -z "$out" ]' "no stale references in the template" "$out"
out="$(grep -rn $'\xe2\x80\x94' "$TEMPLATE" "$PLUGIN/skills/setup" "$PLUGIN/tools/setup_workspace.py")"
t '[ -z "$out" ]' "no em dashes in the template" "$out"
grep -q '^disable-model-invocation: true$' "$PLUGIN/skills/setup/SKILL.md" && ok "/hg:setup can only be started by a person" || bad "/hg:setup can only be started by a person"
for needle in 'gh auth setup-git' '! gh auth login' 'claude plugin install hg@human-gateway --scope project' 'claude plugin marketplace add' '/reload-plugins' '/hg:setup' \
  'git ls-remote origin HEAD' 'If the shell cannot find `claude`' '**Add plugins**' '**Browse plugins**' 'the project scope' '/plugin marketplace add' 'quit and reopen Claude Code' 'the whole app' 'scope for their user account'; do
  grep -qF -- "$needle" "$TEMPLATE/.claude/skills/setup/SKILL.md" && ok "/setup covers: $needle" || bad "/setup covers: $needle"
done

# --- /hg:setup has the same way around a missing gh and a missing claude command as /setup ------------
HG_SETUP="$PLUGIN/skills/setup/SKILL.md"
for needle in 'If `gh` is the only thing missing, or only its install fails, carry on' '1. If `gh` is installed, run `gh auth status`' 'If `gh` is installed, ask them to type' \
  'git ls-remote origin HEAD' 'If it fails and `gh` is installed' 'ask them to contact whoever set up this' 'this folder needs no GitHub yet' 'If the shell cannot find `claude` or the command fails, leave the flag'; do
  grep -qF -- "$needle" "$HG_SETUP" && ok "/hg:setup covers: $needle" || bad "/hg:setup covers: $needle"
done
grep -qF '1. Run `gh auth status`' "$HG_SETUP" && bad "/hg:setup does not run gh unconditionally" || ok "/hg:setup does not run gh unconditionally"

# --- the second person's guide: on a Mac, sign-in comes before the clone ------------------------------
GUIDE="$REPO_ROOT/QUICKSTART-druga-osoba.md"
msg="$(grep -F 'pobierz przez HTTPS' "$GUIDE")"
case "$msg" in *'Na Macu, zanim pobierzesz'*'gh auth login'*'gh auth setup-git'*'pobierz przez HTTPS'*) ok "the pasted message signs in on a Mac before the clone";; *) bad "the pasted message signs in on a Mac before the clone" "$msg";; esac
grep -qF 'kliknij **Terminal**' "$GUIDE" && ok "the guide says where to type gh auth login on a Mac" || bad "the guide says where to type gh auth login on a Mac"

# --- gh is optional: git can sign in by itself; git itself stays required ----------------------------
without() { $PY -c 'import shutil,sys; sys.path.insert(0, sys.argv[1]); import doctor; gone=sys.argv[2]; real=shutil.which; shutil.which=lambda n,*a,**k: None if n==gone else real(n,*a,**k); f=doctor.Findings(); doctor.check_programs(f); sys.exit(f.errors)' "$PLUGIN/tools" "$1"; }
out="$(without gh)"; rc=$?
{ [ $rc -eq 0 ] && printf '%s' "$out" | grep -q $'^WARN\tgh\t'; } && ok "a missing gh is a warning, not an error" || bad "a missing gh is a warning, not an error (rc=$rc)" "$out"
out="$(without git)"; rc=$?
{ [ $rc -eq 1 ] && printf '%s' "$out" | grep -q $'^ERROR\tgit\t'; } && ok "a missing git is still an error" || bad "a missing git is still an error (rc=$rc)" "$out"

echo "setup: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
