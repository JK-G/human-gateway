#!/usr/bin/env bash
# test-scan.sh - hg-tool scan: each kind of finding, masking, exit codes, the allowlist, company patterns,
# --git, no false positives, and the copy of the scanner that CI uses.
# Every fake secret below is assembled from pieces at run time, so this file holds nothing secret-shaped.
# Self-contained. Exit nonzero on failure.

set -u
. "$(cd "$(dirname "$0")/.." && pwd)/lib.sh"
PLUGIN="$REPO_ROOT/plugins/hg"
TMP="$(temp_dir hg-scan)"
trap 'rm -rf "$TMP"' EXIT
unset CLAUDE_PROJECT_DIR
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "ok   - $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL - $1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/       /'; }
t()    { if eval "$1"; then ok "$2"; else bad "$2" "${3:-}"; fi; }
rep()  { printf "%${2}s" "" | tr ' ' "$1"; }  # rep <char> <count>
has()  { case "$1" in *"$2"*) return 0;; *) return 1;; esac; }

CASE="$TMP/cases"; mkdir -p "$CASE"
finds() {  # finds <kind> <label> <text> <the value that must not appear in the output>
  local f="$CASE/case.txt" out rc json
  printf 'first line\n%s\nlast line\n' "$3" > "$f"
  out="$(hg scan "$f" 2>&1)"; rc=$?
  if [ $rc -eq 1 ] && printf '%s\n' "$out" | grep -q ":2"$'\t'"$1"$'\t'; then ok "$2"; else bad "$2 (rc=$rc)" "$out"; fi
  json="$(hg scan --json "$f" 2>&1)"
  if has "$out$json" "$4"; then bad "masked: $2" "the value reached the output"; else ok "masked: $2"; fi
}
clean() {  # clean <label> <text>
  local f="$CASE/case.txt" out rc
  printf 'first line\n%s\nlast line\n' "$2" > "$f"
  out="$(hg scan "$f" 2>&1)"; rc=$?
  t '[ $rc -eq 0 ]' "not flagged: $1" "$out"
}

# --- pieces --------------------------------------------------------------------------------
pw="hun""ter2x"
plain="correct""horse"
mail="ala.nowak""@""acme-notes.test"
mail2="ola""@""mail.acme-notes.test"
mail3="kuba""@""acme-notes-partner.test"
gh="gh""p_$(rep a 36)"; ghfine="github""_pat_$(rep b 30)"
aws="AK""IA$(rep Q 16)"
slack="xo""xb-12345""67890-abcdefghij"
google="AI""za$(rep C 35)"
openai="sk""-proj$(rep d 20)42"
hook_s="https://hooks.sl""ack.com/services/T0123/B0456/abc123def"
hook_d="https://discord""app.com/api/webhooks/123456/abc-DEF_123"
hook_t="https://acme.web""hook.office.com/webhookb2/abc-123@456/IncomingWebhook/789"
hook_p="https://prod-12.westeurope.logic.az""ure.com:443/workflows/abc/triggers/manual/paths/invoke?api-version=1&sig=abc123"
opaque="Ab3dEf7hIj""9lMn1pQr"
pkey="-----BEG""IN RSA PRIV""ATE KEY-----"
ossh="-----BEG""IN OPENSSH PRIV""ATE KEY-----"
phone="+48 601 ""234 567"; phone2="601 234"" 567"; phone3="(22) 123 ""45 67"
iban="PL61 1090 ""1014 0000 ""0712 1981 2874"
pesel="4402""1512""345"

nip="526""025""0274"; regon="123""456""785"; krs="0000""123""456"; ean="590""1234""123457"
big="123 456"" 789"; round="100 000"" 000"

# --- amounts and company numbers are not personal data -------------------------------------
for unit in PLN pln zł ZŁ zl EUR USD GBP € '$' tys tys. mln mld; do
  clean "an amount followed by $unit" "Budżet to $big $unit w tym roku"
done
clean "an amount with no space before the unit" "Budżet $big""PLN"
clean "an amount with a decimal part" "Budżet $big,50 zł"
clean "a round number" "Liczba wyświetleń: $round"
clean "a round number with a country code shape" "+48 $round"
finds pii "a phone followed by an ordinary word" "$phone2 zlecenie" "$phone2"
finds pii "a phone followed by a word that starts like a unit" "$phone2 mlnx" "$phone2"
finds pii "a phone with one group of zeros at the end" "601 234"" 000" "601 234"" 000"
finds pii "a phone with zeros in the middle" "601 000"" 567" "601 000"" 567"
finds pii "a phone before an amount" "$phone2 zapłacił 49 PLN" "$phone2"
clean "an amount with a no-break space before the unit" "Budżet $big"$'\xc2\xa0'"zł"
clean "an amount after a word that only contains a phone word" "Hotel $big PLN"
finds pii "a country code before a currency" "Kontakt: $phone zł" "$phone"
finds pii "a country code with no spaces before a currency" "+48601""234567 EUR" "+48601""234567"
finds pii "a 00 prefix before a unit" "0048 601 ""234 567 mln" "0048 601 ""234 567"
finds pii "an area code in brackets before a currency" "tel. $phone3 USD" "$phone3"
finds pii "a phone column beside a currency column" "Ala"$'\t'"$phone2"$'\t'"EUR"$'\t'"1200" "$phone2"
finds pii "a phone word before grouped digits and a currency" "Kontakt: $phone2 PLN" "$phone2"
finds pii "a phone word before a decimal and a currency" "tel. $phone2,50 zł" "$phone2"
finds pii "hyphens before a currency" "601-234-""567\$" "601-234-""567"
clean "NIP with a colon" "NIP: $nip"
clean "NIP with no colon" "NIP $nip"
clean "NIP in lower case" "nip: $nip"
clean "NIP in a table" "| NIP | $nip |"
clean "NIP with a few words between" "NIP firmy Acme: $nip"
clean "REGON" "REGON: $regon"
clean "KRS" "KRS $krs"
clean "EAN" "EAN: $ean"
clean "EAN-13" "EAN-13: $ean"
clean "REGON with 14 digits" "REGON: 1234567""8512347"
clean "two labels, the second one fits" "NIP/REGON: $regon"
clean "a label and a company name with no phone word" "NIP kontrahenta Acme: $nip"
finds pii "long digits with no label" "numer $nip" "$nip"
finds pii "a run that reads as a dialling prefix, with no label" "numer $krs" "$krs"
finds pii "long digits after a word that ends like a label" "Sean $pesel" "$pesel"
finds pii "long digits on a line where the label went with an earlier number" "NIP $nip, klient $pesel" "$pesel"
finds pii "long digits labelled NIP or PESEL" "NIP/PESEL: $pesel" "$pesel"
finds pii "long digits far from the label" "NIP podajemy zawsze na fakturze, a numer klienta to $pesel" "$pesel"
nine="601""234""567"; card="4111""1111""1111""1111"
finds pii "a phone number after a NIP label and a phone word" "NIP firmy, tel. kontaktowy $nine" "$nine"
finds pii "too few digits for a NIP" "nip mi dal $nine" "$nine"
finds pii "PESEL named before NIP" "PESEL/NIP $pesel" "$pesel"
finds pii "a valid NIP after PESEL on the line" "PESEL/NIP $nip" "$nip"
finds pii "a card number after a REGON label" "REGON, karta $card" "$card"
finds pii "a card number after a KRS label" "KRS: $card" "$card"
finds pii "a dialling prefix after a KRS label" "KRS 0048$nine" "0048$nine"
finds pii "a date in the gap does not help a phone number" "NIP 2026-01-15 $nine" "$nine"
finds pii "a phone word between the label and a valid number" "NIP, tel. $nip" "$nip"
finds pii "a NIP with a wrong check digit" "NIP 526""025""0275" "526""025""0275"
finds pii "a REGON with a wrong check digit" "REGON 123""456""786" "123""456""786"
finds pii "an EAN with a wrong check digit" "EAN: 590""1234""123458" "590""1234""123458"
finds pii "ten digits under KRS that do not start with 00" "KRS 123""456""7890" "123""456""7890"
printf 'NIP\n%s\n' "$pesel" > "$CASE/lines.txt"
out="$(hg scan "$CASE/lines.txt" 2>&1)"; t '[ $? -eq 1 ]' "a label on the line above does not count" "$out"

# --- secrets -------------------------------------------------------------------------------
finds secret "private key block" "$pkey" "$pkey"
finds secret "OpenSSH private key block" "$ossh" "$ossh"
finds secret "AWS key" "aws: $aws" "$aws"
finds secret "GitHub token" "use $gh here" "$gh"
finds secret "GitHub fine-grained token" "$ghfine" "$ghfine"
finds secret "Slack token" "$slack" "$slack"
finds secret "Google key" "$google" "$google"
finds secret "OpenAI-style key" "$openai" "$openai"
finds secret "Slack webhook" "post to $hook_s now" "$hook_s"
finds secret "Discord webhook" "$hook_d" "$hook_d"
finds secret "Teams webhook" "$hook_t" "$hook_t"
finds secret "Teams workflow webhook" "$hook_p" "$hook_p"
finds secret "password assignment" "password=$pw" "$pw"
finds secret "password in YAML" "db_password: $pw" "$pw"
finds secret "plain-word password at end of line" "password: $plain" "$plain"
finds secret "plain-word value in an env file" "DB_PASSWORD=$plain" "$plain"
finds secret "quoted token" "\"api_token\": \"tok$pw\"" "tok$pw"
quoted="sec$pw"
finds secret "single quotes" "client_secret = '$quoted'" "$quoted"
finds secret "export line" "export API_KEY=$opaque" "$opaque"
finds secret "plain key with an opaque value" "key = \"$opaque\"" "$opaque"

# Credentials inside URLs and commands
finds secret "password in a connection string" "DATABASE_URL=post""gres://adm""in:$pw@10.0.0.5:5432/app" "$pw"
finds secret "password in a connection string on localhost" "post""gres://adm""in:$pw@localhost:5432/app" "$pw"
finds secret "password in an HTTPS remote" "git clone https://dep""loy:$pw@git.acme-notes.test/repo.git" "$pw"
finds secret "curl basic auth" "cu""rl -u adm""in:$pw https://api.acme-notes.test/x" "$pw"
finds secret "curl long option" "cu""rl --user=adm""in:$pw https://api.acme-notes.test/x" "$pw"

# Polish names and Markdown tables
finds secret "Polish name" "has""ło: $pw" "$pw"
finds secret "Polish name, capital" "Has""ło = $pw" "$pw"
finds secret "Polish name without the accent" "ha""slo: $pw" "$pw"
finds secret "password in a table" "| pass""word | $pw |" "$pw"
finds secret "plain-word password in a table" "| pass""word | $plain |" "$plain"
finds secret "token in a table" "| api to""ken | $opaque |" "$opaque"
finds secret "bold name in a table" "| **has""ło** | $pw | prod |" "$pw"

# Other common shapes
jwt="ey""J$(rep a 14).$(rep b 14).$(rep c 14)"
basic="YW""Rt$(rep a 8)1$(rep b 8)="
stripe="sk""_live_$(rep a 24)"; rstripe="rk""_test_$(rep b 24)"
glpat="gl""pat-$(rep a 22)"; npmt="np""m_$(rep a 36)"; sg="S""G.$(rep a 22).$(rep b 34)"; hft="h""f_$(rep a 34)"
finds secret "JWT after Bearer" "Authorization: Bea""rer $jwt" "$jwt"
finds secret "JWT alone" "$jwt" "$jwt"
finds secret "Basic header" "Authorization: Ba""sic $basic" "$basic"
finds secret "Stripe live key" "$stripe" "$stripe"
finds secret "Stripe restricted key" "$rstripe" "$rstripe"
finds secret "GitLab token" "$glpat" "$glpat"
finds secret "npm token" "$npmt" "$npmt"
finds secret "SendGrid key" "$sg" "$sg"
finds secret "Hugging Face token" "$hft" "$hft"
finds secret "short name pass" "user: adm""in, pa""ss: $pw" "$pw"
finds secret "passphrase" "pass""phrase: $plain" "$plain"
finds secret "JSON credentials" "\"creden""tials\": \"$pw\"" "$pw"
finds secret "JSON auth" "\"au""th\": \"$pw\"" "$pw"

D='$'
clean "shell reference" "API_KEY=${D}API_KEY"
clean "braced reference" "password: \"${D}{DB_PASSWORD}\""
clean "CI reference" "token: ${D}{{ secrets.DEPLOY_TOKEN }}"
clean "template token" "password: \"{{ password }}\""
clean "Windows variable" "set TOKEN=%TOKEN%"
clean "variable name" "token: GITHUB_TOKEN"
clean "process.env" "secret: process.env.SECRET"
clean "os.environ" "password = os.environ['DB_PASSWORD']"
clean "dotted name" "token = config.token"
clean "code name" "password = userPassword;"
clean "angle placeholder" "password: <your password>"
clean "your-token" "API_KEY=your-api-key-here"
clean "stars" "password: ********"
clean "type annotation" "token: string;"
clean "generic annotation" "password: Optional[str]"
clean "empty value" "API_KEY="
clean "prose after a colon" "Token: this is how we sign in"
clean "password rule in prose" "password: required for everyone"
clean "plain key" "key: value"
clean "JSON key" "\"key\": \"title\""
clean "sort key with a number" "sort_key = created2"
clean "token count" "max_tokens: 4096"
clean "plural tokens" "tokens: 12000"
clean "numeric token" "token: 1234"
clean "kebab slug with sk prefix" "sk-this-is-a-very-long-kebab-slug"
clean "webhook placeholder" "https://hooks.slack.com/services/..."
clean "URL with a port" "http://localhost:8080/path"
ph="pass""word"
clean "URL with a placeholder password" "post""gres://user:$ph@localhost:5432/app"
clean "URL with variables" "post""gres://${D}{DB_USER}:${D}{DB_PASSWORD}@db.internal:5432/app"
clean "URL with a user and no password" "ssh://git""@""git.acme-notes.test/repo.git"
clean "fetch credentials setting" "\"credentials\": \"include\""
clean "auth scheme" "\"auth\": \"basic\""
clean "auth setting" "auth: required"
clean "oauth is not auth" "oauth: abcd1234efgh"
clean "word ending in pass" "compass: north1234"
clean "bypass" "bypass: abc12345"
clean "numeric pass count" "pass: 1204"
clean "pass counter" "pass_count: 12345"
clean "basic in prose" "Basic authentication-required flow"
clean "bearer in prose" "bearer token rotation"
clean "docker user flag" "docker run -u 1000:1000 image"
clean "curl with variables" "curl -u \"${D}USER:${D}PASS\" https://api.acme-notes.test/x"
clean "curl with a placeholder" "curl -u user:password https://api.acme-notes.test/x"
clean "table header" "| token | description |"
clean "table header, capitals" "| Password | Description |"
clean "table of settings" "| max tokens | 4096 |"
clean "table with a reference" "| password | ${D}{DB_PASSWORD} |"
clean "shell pipe" "echo ${D}token | base64"
clean "Polish prose" "hasło: wymagane"

# --- personal data -------------------------------------------------------------------------
finds pii "email" "write to $mail today" "$mail"
finds pii "phone with country code" "call $phone" "$phone"
finds pii "phone in groups" "tel. $phone2" "$phone2"
finds pii "landline" "biuro $phone3" "$phone3"
finds pii "IBAN" "konto $iban" "$iban"
finds pii "PESEL-like run" "PESEL: $pesel" "$pesel"
finds pii "long digits in a CSV" "name,$pesel,city" "$pesel"

clean "ISO date" "created: 2026-01-15"
clean "ISO timestamp" "ts: 2026-01-15T10:30:00Z and 2026-01-15T10:30:00.123+01:00"
clean "compact dates" "20260115 202601151230 20260115T120000 20260115-120000"
clean "Polish date" "15.01.2026 and 15-01-2026"
clean "sha1" "bf6e9e1ad1c0f2a4d8e7c3b5a6f7089e1d2c3b4a"
clean "short hash in text" "commit 1a2b3c4 and abc1234567890"
clean "sha256" "sha256: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
clean "all-digit short hash" "sha1: 1234567890"
clean "UUID" "550e8400-e29b-41d4-a716-446655440000"
clean "uppercase md5" "D41D8CD98F00B204E9800998ECF8427E"
clean "epoch in a time field" "\"timestamp\": 176722""5600"
clean "example.com address" "write to someone""@""example.com"
clean "example.org address" "write to someone""@""example.org"
clean "subdomain of example.com" "someone""@""mail.example.com"
clean "version number" "10.0.26200.1234"
clean "IP address" "192.168.100.200"
clean "year list" "2024 2025 2026 2027"
clean "small numbers" "10 20 30 40 50 60"
clean "digits in a link" "https://tracker.example/t/901234567890"
clean "decimal" "3.141592653589"
clean "SSH remote" "git""@""github.com:acme/notes.git"
clean "image at 2x" "logo""@""2x.png"
clean "package at a version" "hg""@""human-gateway and left-pad""@""1.2.3"

# --- file types ----------------------------------------------------------------------------
for ext in xlsx xls docx doc pptx ppt fig sketch XLSX; do
  f="$CASE/report.$ext"; printf 'plain\n' > "$f"
  out="$(hg scan "$f" 2>/dev/null)"; rc=$?
  { [ $rc -eq 1 ] && printf '%s' "$out" | grep -q $'\tfiletype\tlink only$'; } && ok ".$ext is link only" || bad ".$ext is link only (rc=$rc)" "$out"
done
for name in cert.pem store.p12 store.pfx .env .env.local prod.env; do
  f="$CASE/$name"; printf '\n' > "$f"
  out="$(hg scan "$f" 2>/dev/null)"; rc=$?
  { [ $rc -eq 1 ] && printf '%s' "$out" | grep -q $'\tfiletype\tsecret file$'; } && ok "$name is a secret file" || bad "$name is a secret file (rc=$rc)" "$out"
done
for name in .env.example notes.md report.pdf environment.txt; do
  f="$CASE/$name"; printf 'plain\n' > "$f"
  out="$(hg scan "$f" 2>/dev/null)"; rc=$?
  t '[ $rc -eq 0 ]' "$name is not a file type finding" "$out"
done
f="$CASE/.env.sample"; printf 'API_KEY=%s\n' "$opaque" > "$f"
out="$(hg scan "$f" 2>/dev/null)"; rc=$?
{ [ $rc -eq 1 ] && printf '%s' "$out" | grep -q $'\tsecret\t'; } && ok "a template env file is still read" || bad "a template env file is still read (rc=$rc)" "$out"
rm -f "$CASE"/report.* "$CASE"/cert.pem "$CASE"/store.* "$CASE"/.env* "$CASE"/prod.env

# --- exit codes and output ------------------------------------------------------------------
hg scan >/dev/null 2>&1; t '[ $? -eq 2 ]' "no path is a usage error"
hg scan "$TMP/nowhere" >/dev/null 2>&1; t '[ $? -eq 2 ]' "a missing path is a usage error"
hg scan --nope "$CASE" >/dev/null 2>&1; t '[ $? -eq 2 ]' "an unknown option is a usage error"
hg scan --config "$TMP/nowhere.json" "$CASE" >/dev/null 2>&1; t '[ $? -eq 2 ]' "a missing config is a usage error"
(cd "$TMP" && hg scan --git) >/dev/null 2>&1; t '[ $? -eq 2 ]' "--git outside a repository is a usage error"

printf 'clean text\n' > "$CASE/case.txt"
out="$(hg scan "$CASE/case.txt" 2>/dev/null)"; rc=$?
{ [ $rc -eq 0 ] && [ -z "$out" ]; } && ok "clean file: exit 0, no findings" || bad "clean file: exit 0, no findings (rc=$rc)" "$out"
err="$(hg scan "$CASE/case.txt" 2>&1 >/dev/null)"
has "$err" "1 files, 0 findings" && ok "summary goes to stderr" || bad "summary goes to stderr" "$err"

printf 'a %s\nb %s\n' "$mail" "$gh" > "$CASE/two.txt"
out="$(hg scan --json "$CASE/two.txt" 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "--json keeps the exit code" "$out"
printf '%s' "$out" | jtrue 'd["scanned"]==1 and [(f["line"],f["kind"]) for f in d["findings"]]==[(1,"pii"),(2,"secret")] and all(set(f)=={"path","line","kind","rule","value"} for f in d["findings"])' && ok "--json has the fields" || bad "--json has the fields" "$out"
printf '%s' "$out" | jtrue 'd["findings"][0]["rule"]=="email" and d["findings"][1]["rule"]=="github-token" and "*" in d["findings"][1]["value"]' && ok "--json names the rule and masks" || bad "--json names the rule and masks" "$out"
printf '%s %s %s\n' "$mail" "$mail" "$gh" > "$CASE/two.txt"
out="$(hg scan "$CASE/two.txt" 2>/dev/null)"
t '[ "$(printf "%s\n" "$out" | grep -c .)" -eq 2 ]' "the same value on a line is reported once" "$out"
rm -f "$CASE/two.txt"

# --- files that are not plain UTF-8 ----------------------------------------------------------
$PY -c 'import sys; open(sys.argv[1],"wb").write(("x "+sys.argv[2]+"\n").encode("utf-16"))' "$CASE/u16.txt" "$mail"
out="$(hg scan "$CASE/u16.txt" 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "UTF-16 text is read" "$out"
printf 'zażółć %s\n' "$pw" > "$CASE/pl.txt"
hg scan "$CASE/pl.txt" >/dev/null 2>&1; t '[ $? -eq 0 ]' "non-ASCII text is fine"
$PY -c 'import sys; open(sys.argv[1],"wb").write(bytes(range(256))*8+sys.argv[2].encode())' "$CASE/data.bin" "$mail"
out="$(hg scan "$CASE/data.bin" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "binary contents are not read" "$out"
has "$out" "binary, not read" && ok "a binary file is named as not read" || bad "a binary file is named as not read" "$out"
out="$(hg scan --json "$CASE/data.bin" 2>/dev/null)"
printf '%s' "$out" | jtrue 'd["findings"]==[] and len(d["not_read"])==1 and d["not_read"][0].endswith("data.bin")' && ok "--json lists what was not read" || bad "--json lists what was not read" "$out"
$PY -c 'import sys; open(sys.argv[1],"wb").write(b"PK\3\4"+bytes(range(256))*8)' "$CASE/report.xlsx"
out="$(hg scan --json "$CASE/report.xlsx" 2>/dev/null)"
printf '%s' "$out" | jtrue 'd["not_read"]==[]' && ok "a file with a file type finding is not also not read" || bad "a file with a file type finding is not also not read" "$out"
pw_line="pass""word=$pw"
$PY -c 'import sys; open(sys.argv[1],"wb").write(b"title\0\n\n"+sys.argv[2].encode()+b"\n")' "$CASE/nul.md" "$pw_line"
out="$(hg scan "$CASE/nul.md" 2>&1)"; rc=$?
{ [ $rc -eq 1 ] && has "$out" "nul.md:3"; } && ok "a stray NUL does not hide the rest of a text file" || bad "a stray NUL does not hide the rest of a text file (rc=$rc)" "$out"
for enc in utf-16-le utf-16-be; do
  $PY -c 'import sys; open(sys.argv[1],"wb").write(sys.argv[2].encode(sys.argv[3])+b"")' "$CASE/plain16.txt" "$pw_line" "$enc"
  out="$(hg scan "$CASE/plain16.txt" 2>&1)"; rc=$?
  t '[ $rc -eq 1 ]' "$enc without a byte order mark is read" "$out"
done
hidden() {  # hidden <label> <python expression on m, the fake address, and g, the fake token, giving bytes>
  local out rc
  $PY -c 'import sys; m,g=sys.argv[2:4]; open(sys.argv[1],"wb").write(eval(sys.argv[4]))' "$CASE/hidden.md" "$mail" "$gh" "$2"
  out="$(hg scan "$CASE/hidden.md" 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && ! has "$out" "not read"; } && ok "$1" || bad "$1 (rc=$rc)" "$out"
}
hidden "UTF-32 little-endian with a byte order mark" 'b"\xff\xfe\0\0"+("x "+m+"\n").encode("utf-32-le")'
hidden "UTF-32 big-endian with a byte order mark" 'b"\0\0\xfe\xff"+("x "+m+"\n").encode("utf-32-be")'
hidden "UTF-16 that starts after a long ASCII head" 'b"plain ascii line\n"*600+("x "+m+"\n").encode("utf-16-le")'
hidden "a token in UTF-16 after a long ASCII head" 'b"plain ascii line\n"*600+("token "+g+"\n").encode("utf-16-le")'
hidden "a zero-width space inside an email domain" '("x "+m.replace("-notes","\u200b-notes")+"\n").encode("utf-8")'
hidden "a soft hyphen inside a token" '("x "+g[:8]+"\u00ad"+g[8:]+"\n").encode("utf-8")'
rm -f "$CASE/hidden.md"
rm -f "$CASE/u16.txt" "$CASE/pl.txt" "$CASE/data.bin" "$CASE/report.xlsx" "$CASE/nul.md" "$CASE/plain16.txt"

# --- folders ---------------------------------------------------------------------------------
F="$TMP/folder"; mkdir -p "$F/sub" "$F/.git/x" "$F/node_modules/y" "$F/.claude"
printf '%s\n' "$mail" > "$F/sub/a.md"
printf '%s\n' "$mail" > "$F/.git/x/b.md"
printf '%s\n' "$mail" > "$F/node_modules/y/c.md"
printf '%s\n' "$gh" > "$F/.claude/d.json"
out="$(hg scan "$F" 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "a folder is scanned" "$out"
has "$out" "sub/a.md:1" && ok "subfolders are read" || bad "subfolders are read" "$out"
has "$out" ".claude/d.json:1" && ok "dot folders are read" || bad "dot folders are read" "$out"
{ has "$out" ".git/x" || has "$out" "node_modules"; } && bad ".git and node_modules are skipped" "$out" || ok ".git and node_modules are skipped"

# --- allowlist and company patterns ---------------------------------------------------------
C="$TMP/company"; mkdir -p "$C/.claude" "$C/deep/er"
kept="kept""@""partner-firm.test"
sub="anna""@""team.acme-notes.test"
$PY -c 'import json,sys
json.dump({"scan":{"allow":{"emails":[sys.argv[1].upper()],"domains":["acme-notes.test","@other-firm.test"]},
 "patterns":{"customer-id":"CUST-[0-9]{4}","internal-key":{"regex":"INT_[A-Z]{6}","kind":"secret"}}}},open(sys.argv[2],"w",encoding="utf-8"))' "$kept" "$C/.claude/hg.json"
printf 'a %s\nb %s\nc %s\nd %s\n' "$kept" "$mail" "$sub" "bea""@""other-firm.test" > "$C/ok.md"
out="$(cd "$C" && hg scan ok.md 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "allowed addresses and domains pass" "$out"
printf 'a %s\n' "$mail3" > "$C/deep/er/no.md"
out="$(cd "$C/deep/er" && hg scan no.md 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "another domain is still flagged, and hg.json is found from a subfolder" "$out"
printf 'x %s\n' "$hook_s" > "$C/hook.md"
out="$(cd "$C" && hg scan hook.md 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "the allowlist does not touch secrets" "$out"
printf 'ref CUST-1234\nkey INT_ABCDEF\nno CUST-12\n' > "$C/p.md"
out="$(cd "$C" && hg scan p.md 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "company patterns are findings" "$out"
printf '%s\n' "$out" | grep -q 'p.md:1'$'\t''pii'$'\t' && ok "a company pattern is pii by default" || bad "a company pattern is pii by default" "$out"
printf '%s\n' "$out" | grep -q 'p.md:2'$'\t''secret'$'\t' && ok "a company pattern can be a secret" || bad "a company pattern can be a secret" "$out"
has "$out" "p.md:3" && bad "a company pattern needs a full match" "$out" || ok "a company pattern needs a full match"
has "$out" "CUST-1234" && bad "company findings are masked" "$out" || ok "company findings are masked"
printf 'a %s\n' "$kept" > "$CASE/case.txt"
hg scan "$CASE/case.txt" >/dev/null 2>&1; t '[ $? -eq 1 ]' "no config outside the repository: the address is flagged"
out="$(hg scan --config "$C/.claude/hg.json" "$CASE/case.txt" 2>&1)"; t '[ $? -eq 0 ]' "--config points at the allowlist" "$out"

for body in '{"scan":{"patterns":{"x":"("}}}' '{"scan":{"patterns":{"x":{"regex":"a","kind":"odd"}}}}' '{"scan":{"allow":["a"]}}' '{"scan":{"allow":{"emails":"a"}}}' '{"scan":3}' 'not json'; do
  printf '%s' "$body" > "$TMP/bad.json"
  hg scan --config "$TMP/bad.json" "$CASE/case.txt" >/dev/null 2>&1; rc=$?
  t '[ $rc -eq 2 ]' "bad config: $body" "rc=$rc"
done
printf '\xef\xbb\xbf{"schemaVersion":1}' > "$TMP/bom.json"
hg scan --config "$TMP/bom.json" "$CASE/case.txt" >/dev/null 2>&1; t '[ $? -eq 1 ]' "a config with a BOM and no scan key works"

# --- --git -----------------------------------------------------------------------------------
G="$TMP/repo"; mkdir -p "$G/sub"
git -C "$G" init -q
printf 'ignored.md\n' > "$G/.gitignore"
printf 'a %s\n' "$mail" > "$G/sub/tracked.md"
printf 'plain\n' > "$G/sub/plain.md"
printf 'plain\n' > "$G/top.xlsx"
printf 'b %s\n' "$gh" > "$G/untracked.md"
printf 'c %s\n' "$gh" > "$G/ignored.md"
printf 'd\n' > "$G/gone.md"
git -C "$G" add .gitignore sub top.xlsx gone.md
rm "$G/gone.md"
out="$(cd "$G" && hg scan --git 2>/dev/null)"; rc=$?
t '[ $rc -eq 1 ]' "--git finds tracked problems" "$out"
printf '%s\n' "$out" | grep -q '^sub/tracked.md:1'$'\t''pii' && ok "--git shows repo-relative paths" || bad "--git shows repo-relative paths" "$out"
has "$out" 'top.xlsx:1' && ok "--git checks file types" || bad "--git checks file types" "$out"
{ has "$out" untracked || has "$out" ignored.md; } && bad "--git reads tracked files only" "$out" || ok "--git reads tracked files only"
has "$out" gone && bad "a deleted tracked file is skipped" "$out" || ok "a deleted tracked file is skipped"
out="$(cd "$G/sub" && hg scan --git 2>/dev/null)"
has "$out" 'top.xlsx:1' && ok "--git from a subfolder covers the whole repo" || bad "--git from a subfolder covers the whole repo" "$out"
out="$(cd "$G" && hg scan --git sub/plain.md 2>/dev/null)"; rc=$?
t '[ $rc -eq 0 ]' "--git with a PATH covers only that path" "$out"

# --- no false positives ------------------------------------------------------------------------
out="$(hg scan "$REPO_ROOT/tests/fixtures/workspace/vault" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the fixture vault is clean" "$out"
out="$(hg scan "$PLUGIN/tools/scan.py" "$PLUGIN/skills" "$PLUGIN/rules" "$PLUGIN/templates" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the scanner and the plugin's text are clean" "$out"
out="$(hg scan "$REPO_ROOT/tests/scan/test-scan.sh" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "this test file holds nothing secret-shaped" "$out"

# --- windows path shapes ----------------------------------------------------------------------
if command -v cygpath >/dev/null 2>&1; then
  printf 'a %s\n' "$mail" > "$CASE/case.txt"
  for form in u w m; do
    hg scan "$(cygpath -$form "$CASE/case.txt")" >/dev/null 2>&1; rc=$?
    t '[ $rc -eq 1 ]' "PATH in the -$form shape" "rc=$rc"
  done
  drive="$(printf '%s' "${CASE%%:*}" | tr 'A-Z' 'a-z')"
  hg scan "/$drive${CASE#*:}/case.txt" >/dev/null 2>&1; rc=$?
  t '[ $rc -eq 1 ]' "PATH in the /d/x shape" "rc=$rc"
  env -u MSYS2_ARG_CONV_EXCL bash "$HG_TOOL" scan "$(cygpath -u "$CASE/case.txt")" >/dev/null 2>&1; rc=$?
  t '[ $rc -eq 1 ]' "PATH straight from Git Bash" "rc=$rc"
else
  echo "n/a  - Windows path shapes not checked on this system"
fi

# --- the copy CI uses --------------------------------------------------------------------------
W="$TMP/dept"
out="$(hg setup --root "$W" --name Dept)"; rc=$?
t '[ $rc -eq 0 ]' "setup succeeds" "$out"
printf '%s' "$out" | grep -q $'^created\t.github/hg/scan.py$' && ok "setup copies the scanner" || bad "setup copies the scanner" "$out"
printf '%s' "$out" | grep -q $'^created\t.github/workflows/hg-scan.yml$' && ok "setup adds the workflow" || bad "setup adds the workflow" "$out"
cmp -s "$PLUGIN/tools/scan.py" "$W/.github/hg/scan.py" && ok "the copy is identical" || bad "the copy is identical"
wf="$W/.github/workflows/hg-scan.yml"
for needle in 'python .github/hg/scan.py --git' 'push:' 'pull_request:'; do
  grep -qF -- "$needle" "$wf" && ok "workflow has: $needle" || bad "workflow has: $needle"
done
printf '%s' "$(cat "$W/.claude/hg.json")" | jtrue 'd["scan"]=={"allow":{"emails":[],"domains":[]},"patterns":{}}' && ok "hg.json shows where the allowlist goes" || bad "hg.json shows where the allowlist goes" "$(cat "$W/.claude/hg.json")"

git -C "$W" add -A
git -C "$W" ls-files --error-unmatch .github/hg/scan.py >/dev/null 2>&1 && ok "the copy is tracked" || bad "the copy is tracked"
out="$(cd "$W" && hg scan --git 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "a fresh workspace passes its own scan" "$out"
# CI has no plugin: the copy alone, started as the workflow starts it, away from every other tool.
out="$(cd "$W" && $PY .github/hg/scan.py --git 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the copy runs on its own" "$out"
printf 'a %s\n' "$gh" > "$W/vault/inbox/note.md"
git -C "$W" add vault/inbox/note.md
out="$(cd "$W" && $PY .github/hg/scan.py --git 2>&1)"; rc=$?
t '[ $rc -eq 1 ]' "the copy stops a tracked secret" "$out"
printf 'Budget %s PLN, NIP: %s\n' "$big" "$nip" > "$W/vault/inbox/amounts.md"
out="$(cd "$W" && $PY .github/hg/scan.py vault/inbox/amounts.md 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the copy knows amounts and company numbers" "$out"
rm "$W/vault/inbox/amounts.md"
has "$out" "$gh" && bad "the copy masks it too" "$out" || ok "the copy masks it too"
git -C "$W" rm -q --cached vault/inbox/note.md; rm "$W/vault/inbox/note.md"

status() { hg doctor --root "$W" | grep $'\tscanner\t' | cut -f1; }
t '[ "$(status)" = OK ]' "doctor accepts a matching copy" "$(hg doctor --root "$W")"
$PY -c 'import sys; p=sys.argv[1]; d=open(p,"rb").read(); open(p,"wb").write(d.replace(b"\n",b"\r\n"))' "$W/.github/hg/scan.py"
t '[ "$(status)" = OK ]' "doctor does not call line endings drift" "$(hg doctor --root "$W")"
printf '# changed\n' >> "$W/.github/hg/scan.py"
t '[ "$(status)" = WARN ]' "doctor warns on drift" "$(hg doctor --root "$W")"
out="$(hg setup --root "$W")"
grep -q '# changed' "$W/.github/hg/scan.py" && ok "plain setup never replaces the copy" || bad "plain setup never replaces the copy" "$out"

printf 'mine\n' > "$W/CLAUDE.md"
out="$(hg setup --root "$W" --refresh-scan)"; rc=$?
{ [ $rc -eq 0 ] && printf '%s' "$out" | grep -q $'^updated\t.github/hg/scan.py$'; } && ok "--refresh-scan replaces the copy" || bad "--refresh-scan replaces the copy (rc=$rc)" "$out"
cmp -s "$PLUGIN/tools/scan.py" "$W/.github/hg/scan.py" && ok "the copy matches again" || bad "the copy matches again"
t '[ "$(cat "$W/CLAUDE.md")" = mine ]' "--refresh-scan touches nothing else"
t '[ "$(status)" = OK ]' "doctor is satisfied after the refresh" "$(hg doctor --root "$W")"
out="$(hg setup --root "$W" --refresh-scan)"
printf '%s' "$out" | grep -q $'^skipped\t.github/hg/scan.py$' && ok "a second refresh changes nothing" || bad "a second refresh changes nothing" "$out"
rm -r "$W/.github/hg"
t '[ "$(status)" = WARN ]' "doctor warns when the copy is missing" "$(hg doctor --root "$W")"
out="$(hg setup --root "$W" --refresh-scan)"; rc=$?
{ [ $rc -eq 0 ] && [ -f "$W/.github/hg/scan.py" ]; } && ok "--refresh-scan restores a missing copy" || bad "--refresh-scan restores a missing copy" "$out"
out="$(hg setup --root "$TMP/not-a-workspace" --refresh-scan)"; rc=$?
{ [ $rc -eq 1 ] && [ ! -e "$TMP/not-a-workspace" ]; } && ok "--refresh-scan needs a workspace and creates nothing" || bad "--refresh-scan needs a workspace and creates nothing (rc=$rc)" "$out"

# --- a gate record names its accountable person, and only that is left out -----------------------
R="$TMP/gated"
hg setup --root "$R" --project acme-notes >/dev/null
person="anna""@""acme-notes-co.test"
git -C "$R" config user.email "$person"; git -C "$R" config user.name Anna; git -C "$R" config core.autocrlf false
printf '# brief\n' > "$R/vault/projects/acme-notes/brief.md"
git -C "$R" add -A; git -C "$R" commit -q -m base
g() { (cd "$R" && CLAUDE_PROJECT_DIR="$R" hg gate "$@"); }
out="$(g new launch --title Launch --project acme-notes --accountable "$person" --input vault/projects/acme-notes/brief.md 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "gate created" "$out"
git -C "$R" add -A; git -C "$R" commit -q -m gate
out="$(g approve launch --via person --request "ok" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "gate approved" "$out"
git -C "$R" add -A
out="$(cd "$R" && hg scan --git 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the accountable person's address in a gate record passes" "$out"
printf '\nwrite to %s\n' "$mail" >> "$R/gates/launch.md"
out="$(cd "$R" && hg scan --git 2>&1)"; rc=$?
{ [ $rc -eq 1 ] && has "$out" "gates/launch.md"; } && ok "any other address in a gate file is flagged" || bad "any other address in a gate file is flagged (rc=$rc)" "$out"
printf 'accountable: %s\n' "$person" > "$R/vault/inbox/note.md"
git -C "$R" add vault/inbox/note.md
out="$(cd "$R" && hg scan --git 2>&1)"
has "$out" "vault/inbox/note.md" && ok "the field is left out only in gates/" || bad "the field is left out only in gates/" "$out"
git -C "$R" rm -q --cached vault/inbox/note.md; rm "$R/vault/inbox/note.md"
mkdir -p "$R/vault/projects/acme-notes/gates" "$TMP/nogit/gates"
scans() {  # scans <label> <file> <text> <kind>: the text in that file is a finding of that kind
  local out rc; printf '%s\n' "$3" > "$2"
  out="$(cd "$R" && hg scan "$2" 2>&1)"; rc=$?
  { [ $rc -eq 1 ] && printf '%s\n' "$out" | grep -q $'\t'"$4"$'\t'; } && ok "$1" || bad "$1 (rc=$rc)" "$out"
  rm -f "$2"
}
nested="$R/vault/projects/acme-notes/gates/nested.md"
scans "accountable in a deeper folder named gates" "$nested" "accountable: $mail" pii
scans "a by field in a deeper folder named gates" "$nested" "\"by\": \"$mail\"" pii
scans "accountable in a gates folder of no repository" "$TMP/nogit/gates/a.md" "accountable: $mail" pii
top="$R/gates/shape.md"
scans "a token written as the accountable address" "$top" "accountable: x@$gh" secret
scans "a token written as the by address" "$top" "\"by\": \"x@ y $gh\"" secret
scans "a token as the domain of the address" "$top" "accountable: x@$aws.com" secret
scans "a by field with more after it on the line" "$top" "\"by\": \"$mail\" and more" pii
scans "an accountable address with more after it" "$top" "accountable: $mail or someone" pii
printf 'accountable: %s\n' "$person" > "$top"
out="$(cd "$R" && hg scan "$top" 2>&1)"; rc=$?
t '[ $rc -eq 0 ]' "the plain accountable address still passes at the top" "$out"
rm -f "$top"

# --- wiring and text --------------------------------------------------------------------------
grep -q 'hg-tool scan --git' "$PLUGIN/rules/boundaries.md" && ok "the rules scan before every commit" || bad "the rules scan before every commit"
grep -q 'hg-tool scan --git' "$PLUGIN/tools/session_start.py" && ok "the session start says so too" || bad "the session start says so too"
printf 'x\n' > "$R/prod.env"; git -C "$R" add -f prod.env
out="$(cd "$R" && hg scan --git 2>&1)"; rc=$?
{ [ $rc -eq 1 ] && has "$out" "prod.env"; } && ok "the scan before a commit stops a staged env file" || bad "the scan before a commit stops a staged env file (rc=$rc)" "$out"
git -C "$R" rm -q --cached prod.env; rm "$R/prod.env"
grep -q 'hg-tool scan <file>' "$PLUGIN/skills/import-source/SKILL.md" && ok "import-source runs the scan" || bad "import-source runs the scan"
grep -q 'keep the file out' "$PLUGIN/skills/import-source/SKILL.md" && ok "import-source keeps its way out" || bad "import-source keeps its way out"
grep -q 'hg-tool setup --refresh-scan' "$PLUGIN/skills/setup/SKILL.md" && ok "/hg:setup --update refreshes the copy" || bad "/hg:setup --update refreshes the copy"
out="$(grep -n $'\xe2\x80\x94' "$PLUGIN/tools/scan.py" "$REPO_ROOT/tests/scan/test-scan.sh" "$PLUGIN/skills/import-source/SKILL.md" "$wf")"
t '[ -z "$out" ]' "no em dashes" "$out"
out="$(grep -nE '^(from|import) ' "$PLUGIN/tools/scan.py" | grep -vE 'import (argparse|json|os|re|shutil|subprocess|sys|unicodedata)$')"
t '[ -z "$out" ]' "the scanner imports only the standard library" "$out"

echo "scan: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
