#!/usr/bin/env python3
"""scan.py - deterministic check for what must never reach git: secrets, contact data, files that stay links.

Usage: hg-tool scan [--json] [--git] [--config FILE] [PATH ...]
  PATH      a file, or a folder scanned recursively
  --git     the files git tracks, limited to PATH when PATH is given
  --json    the findings as one JSON object
  --config  default: .claude/hg.json of this repository, keys scan.allow and scan.patterns

Output: one finding per line, path:line<TAB>kind<TAB>masked value, so the scan never repeats what it found.
Kinds: secret, pii, filetype (the value says "link only" or "secret file"). Exit: 0 clean, 1 findings, 2 usage or config error.

scan.allow is {"emails": [...], "domains": [...]}. scan.patterns maps a name to a regex, or to {"regex": ..., "kind": "secret"|"pii"}.
The contents of binary files are not read: they are listed as not read (on stderr, and under "not_read" with --json)
and do not change the exit code, so that a repo may hold images. A file the scan could not read has not been checked.
Names of people need judgment, so they are not this tool's job.
A gate record in the gates/ folder at the top of a repository names the accountable person's address by design,
so only that field is left out, and only when it holds one plain address.

One file, standard library only: hg-tool setup copies it to .github/hg/scan.py for CI, where the plugin is not installed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

ALWAYS_ALLOWED_DOMAINS = ("example.com", "example.org")
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
LINK_ONLY = {".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".fig", ".sketch"}
SECRET_FILES = {".pem", ".p12", ".pfx"}
ENV_TEMPLATES = (".example", ".sample", ".template", ".dist")
PATTERN_KINDS = ("secret", "pii")

SECRET_RULES = [(name, re.compile(rx)) for name, rx in (
    ("private-key", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    ("aws-key", r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ("github-token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ("slack-token", r"\bxox[abeoprs]-[A-Za-z0-9-]{10,}|\bxapp-[A-Za-z0-9-]{10,}"),
    ("google-key", r"\bAIza[0-9A-Za-z_-]{35,}|\bya29\.[0-9A-Za-z_-]{20,}|\bGOCSPX-[0-9A-Za-z_-]{20,}"),
    ("openai-style-key", r"\bsk-(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("http-auth", r"(?i)\b(?:bearer|basic)\s+(?=[A-Za-z._+/=-]*\d)[A-Za-z0-9._+/=-]{16,}"),
    ("stripe-key", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    ("npm-token", r"\bnpm_[A-Za-z0-9]{30,}"),
    ("sendgrid-key", r"\bSG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{30,}"),
    ("huggingface-token", r"\bhf_[A-Za-z0-9]{30,}"),
    ("slack-webhook", r"https://hooks\.slack\.com/(?:services|workflows|triggers)/[A-Za-z0-9]+/[A-Za-z0-9/_-]+"),
    ("discord-webhook", r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+"),
    ("teams-webhook", r"https://[\w.-]+\.webhook\.office\.com/webhook[\w]*/[^\s\"'<>)]+"
                      r"|https://outlook\.office\.com/webhook/[^\s\"'<>)]+"
                      r"|https://[\w.-]+\.(?:logic\.azure\.com|api\.powerplatform\.com)(?::\d+)?/[^\s\"'<>)]*\bsig=[^\s\"'<>)]+"),
)]

PASSWORD_RULES = [(name, re.compile(rx)) for name, rx in (
    ("url-credentials", r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:(?P<pw>[^\s/@]+)@"),
    ("curl-credentials", r"""\bcurl\b[^\n|;&]*?\s(?:-u\s*|--user[=\s]\s*)["']?[^\s:"']+:(?P<pw>[^\s"']+)"""),
)]
SECRET_WORDS = r"passw(?:or)?d|passphrase|pwd|secret|token|key|credentials?|has[łl]o|klucz"
QUOTED_OR_BARE = r"""(?:"(?P<dq>[^"|]*)"|'(?P<sq>[^'|]*)'|(?P<bare>[^\s"'|,;]+))"""
ASSIGNMENT = re.compile(
    r"""(?<![\w.-])(?P<name>[\w.-]*?(?:%s)|(?:[\w.-]*?[._-])?(?:pass|auth))(?:[_-]?\d+)?["'\]*]*\s*(?P<sep>:=|=>|=|:)\s*"""
    % SECRET_WORDS + QUOTED_OR_BARE, re.I)
TABLE_CELLS = re.compile(r"""\|\s*[*_`]*(?P<name>[^|]*?(?:%s))[*_`]*\s*(?P<sep>\|)\s*""" % SECRET_WORDS + QUOTED_OR_BARE + r"""\s*(?=\||$)""", re.I)
PASSWORD_NAME = re.compile(r"(?:passw(?:or)?d|passphrase|pwd|has[łl]o)$", re.I)
STRONG_NAME = re.compile(r"(?:passw(?:or)?d|passphrase|pwd|secret|token|has[łl]o|(?:^|[._-])pass|(?:api|access|private|auth|secret)[_.-]?key)$", re.I)
AUTH_NAME = re.compile(r"(?:(?:^|[._-])auth|credentials?)$", re.I)  # "auth": "basic" and "credentials": "include" are settings
OPAQUE_VALUE = re.compile(r"[\w+/=-]{16,}")
REFERENCE = re.compile(r"\$|%[\w(]|\{\{|\{%|<|\[|\(|process\.env|os\.(?:environ|getenv)|getenv|env\.|secrets\.|vars\.", re.I)
ENV_NAME = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")
CODE_NAME = re.compile(r"[A-Za-z_]+(?:\.[A-Za-z_]+)+|[a-z]+(?:[A-Z_][a-z]+)+")
PLACEHOLDER = re.compile(
    r"x{3,}|\*{3,}|\.{3,}|#+|-+|change[_-]?me|your[-_ ].*|my[-_ ].*|example.*|sample.*|dummy.*|placeholder.*|redacted|masked|hidden"
    r"|none|null|nil|true|false|undefined|string|str|bytes|int|number|boolean|bool|any|object|required|optional|todo|tbd|n/?a|unknown"
    r"|value|empty|test|secret|password|passwd|pass|token|key|api[_-]?key|description"
    r"|has[łl]o|klucz|wymagane|wymagany|brak|puste|opcjonalne|ukryte|opis|warto[śs][ćc]|twoje.*|przyk[łl]ad.*", re.I)

SCRUB_FIRST = [re.compile(rx) for rx in (
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b",
    r"\b\d{2}:\d{2}(?::\d{2})?\b",
    r"\b(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?:[T_-]?\d{4}(?:\d{2})?)?Z?\b",
    r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b",
    r"\b[0-9a-fA-F]{32,}\b",
    r"(?i)\b(?:sha\d*|md5|hash|checksum|commit|digest|etag|rev|ts|time\w*|created\w*|updated\w*)[\"']?\s*[:=]\s*[\"']?\d{7,64}\b",
)]
ADDRESS = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
EMAIL = re.compile(r"(?<![A-Za-z0-9._%+-])" + ADDRESS)
MACHINE_ADDRESS = re.compile(r"git@.*|.*@\d+(?:\.\d+)?x\.[A-Za-z]+", re.I)  # SSH remotes and image names such as logo@2x.png
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
URL = re.compile(r"https?://[^\s\"'<>)\]]+")  # ids in links are not personal data, and links are what the repo keeps
PHONE = re.compile(
    r"(?<![\w.+-])(?:"
    r"(?:\+|00)\d{1,3}[ -]?(?:\(\d{1,4}\)[ -]?)?\d{1,4}(?:[ -]?\d{2,4}){1,4}"
    r"|\(\d{2,4}\)[ -]?\d{3}(?:[ -]?\d{2,4}){1,2}"
    r"|\d{3}[ -]\d{3}[ -]\d{3,4}"
    r"|\d{2}[ -]\d{3}[ -]\d{2}[ -]\d{2}"
    r")(?![\w-]|\.\d)")
LONG_DIGITS = re.compile(r"(?<![\w.])\d{9,19}(?![\w]|[.,]\d)")
AMOUNT_SHAPE = re.compile(r"[1-9]\d{0,2}(?: \d{3})+")  # a +, 00 or ( prefix, a hyphen or a short group is never an amount
AMOUNT_AFTER = re.compile(r"(?:,\d{1,2})?[   ]*(?:PLN|zł|zl|EUR|USD|GBP|€|\$|tys|mln|mld)(?![^\W\d_])", re.I)
PHONE_WORDS = r"tel|telefon\w*|phone|mobile|kom[óo]rk\w*|kontakt\w*|contact|sms|whatsapp|dzwo[nń]\w*"
CARD_WORDS = r"kart[aeyąęo]|karcie|card|kont[aou]|koncie|account|iban"
PHONE_WORD = re.compile(r"(?<![^\W\d_])(?:%s)(?![^\W\d_])" % PHONE_WORDS, re.I)
PERSONAL_WORD = re.compile(r"(?<![^\W\d_])(?:%s|%s)(?![^\W\d_])" % (PHONE_WORDS, CARD_WORDS), re.I)
COMPANY_LABEL = re.compile(r"(?<![^\W_])(NIP|REGON|KRS|EAN)(?:[- ]?(?:8|13))?(?![^\W\d_])", re.I)
COMPANY_GAP = 30
GATE_IDENTITY = re.compile(r"""^\s*accountable:\s*["']?%s["']?\s*$|^\s*"(?:by|accountable)":\s*"%s",?\s*$""" % (ADDRESS, ADDRESS))


def die(message):
    print("scan: %s" % message, file=sys.stderr)
    sys.exit(2)


def native_path(raw):
    """With argument rewriting off, Git Bash hands over /d/x or /tmp/x, which Windows Python cannot open."""
    if os.name != "nt" or not raw.startswith("/"):
        return raw
    drive = re.match(r"^/([A-Za-z])(?=/|$)", raw)
    if drive:
        return drive.group(1) + ":" + raw[2:]
    cygpath = shutil.which("cygpath")
    if cygpath:
        out = subprocess.run([cygpath, "-m", raw], capture_output=True, encoding="utf-8", errors="replace")
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return raw


def find_config():
    roots = [os.environ["CLAUDE_PROJECT_DIR"]] if os.environ.get("CLAUDE_PROJECT_DIR") else []
    here = os.getcwd()
    while True:
        roots.append(here)
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    for root in roots:
        candidate = os.path.join(root, ".claude", "hg.json")
        if os.path.isfile(candidate):
            return candidate
    return None


def compile_patterns(spec):
    if not isinstance(spec, dict):
        die("scan.patterns must map a name to a regex")
    patterns = []
    for name, item in spec.items():
        item = {"regex": item} if isinstance(item, str) else item
        if not isinstance(item, dict) or not isinstance(item.get("regex"), str):
            die("scan.patterns: '%s' needs a regex" % name)
        kind = item.get("kind", "pii")
        if kind not in PATTERN_KINDS:
            die("scan.patterns: '%s' has kind '%s', expected secret or pii" % (name, kind))
        try:
            patterns.append((name, kind, re.compile(item["regex"])))
        except re.error as exc:
            die("scan.patterns: '%s' is not a valid regex: %s" % (name, exc))
    return patterns


def string_list(value, label):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        die("%s must be a list of strings" % label)
    return value


def load_config(path):
    empty = {"emails": set(), "domains": set(), "patterns": []}
    if path is None:
        path = find_config()
        if path is None:
            return empty
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        die("cannot read config %s: %s" % (path, exc))
    scan = data.get("scan", {}) if isinstance(data, dict) else None
    if not isinstance(scan, dict):
        die("%s: scan must be an object" % path)
    allow = scan.get("allow", {})
    if not isinstance(allow, dict):
        die('scan.allow must be {"emails": [...], "domains": [...]}')
    return {
        "emails": {e.lower() for e in string_list(allow.get("emails", []), "scan.allow.emails")},
        "domains": {d.lower().lstrip("@") for d in string_list(allow.get("domains", []), "scan.allow.domains")},
        "patterns": compile_patterns(scan.get("patterns", {})),
    }


def git_files(paths):
    def git(*args, cwd=None):
        try:
            return subprocess.run(["git", *args], cwd=cwd, capture_output=True, encoding="utf-8", errors="surrogateescape")
        except OSError:
            die("git is not installed")
    top = git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        die("--git needs a git repository")
    base = None if paths else top.stdout.strip()  # with no PATH, the whole repository even from a subfolder
    listed = git("ls-files", "-z", "--", *paths, cwd=base)
    if listed.returncode != 0:
        die("git ls-files failed: %s" % listed.stderr.strip())
    for rel in filter(None, listed.stdout.split("\0")):
        full = os.path.join(base, rel) if base else rel
        if os.path.isfile(full) and not os.path.islink(full):  # a tracked file may be deleted, or be a submodule
            yield full, rel


def walk_files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path, path
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    full = os.path.join(root, name)
                    if not os.path.islink(full):
                        yield full, full
        else:
            die("no such file or folder: %s" % path)


def decode(data):
    """The text of file bytes, or None for binary. A stray NUL does not make text binary: only the share of bytes does."""
    if data[:4] in (b"\xff\xfe\0\0", b"\0\0\xfe\xff"):  # before UTF-16, whose mark is the start of this one
        return data.decode("utf-32", errors="replace")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    sample = data[:8192]
    if b"\0" not in sample:
        return data.decode("utf-8-sig", errors="replace")
    half = len(sample) / 2
    even, odd = sample[0::2].count(0), sample[1::2].count(0)
    if odd > half * 0.4 and even < half * 0.05:  # UTF-16 with no byte order mark: every other byte is NUL
        return data.decode("utf-16-le", errors="replace")
    if even > half * 0.4 and odd < half * 0.05:
        return data.decode("utf-16-be", errors="replace")
    control = sum(1 for b in sample if b < 9 or 13 < b < 32)
    invalid = sample.decode("utf-8", errors="replace").count("\ufffd")
    if sample.count(0) > len(sample) * 0.1 or control + invalid > len(sample) * 0.3:
        return None
    return data.decode("utf-8-sig", errors="replace")


def without_hidden(text):
    """NUL is left by UTF-16 that starts after the sample decode() looks at. Format characters split a value invisibly."""
    text = text.replace("\0", "")
    return text if text.isascii() else "".join(c for c in text if unicodedata.category(c) != "Cf")


def read_text(path):
    try:
        with open(path, "rb") as fh:
            text = decode(fh.read())
    except OSError as exc:
        die("cannot read %s: %s" % (path, exc))
    return None if text is None else without_hidden(text)


def file_finding(name):
    low = name.lower()
    ext = os.path.splitext(low)[1]
    if ext in LINK_ONLY:
        return ext, "link only"
    if ext in SECRET_FILES:
        return ext, "secret file"
    if low == ".env" or low.endswith(".env") or (low.startswith(".env.") and not low.endswith(ENV_TEMPLATES)):
        return ".env", "secret file"
    return None


def mask(kind, value):
    value = value.strip()
    if kind == "secret":
        return value[:2] + "***" if len(value) >= 16 else "***"
    return value[:2] + "***" + value[-2:] if len(value) > 6 else "***"


def not_a_value(value):
    return len(value) < 4 or REFERENCE.match(value) or PLACEHOLDER.fullmatch(value) or ENV_NAME.fullmatch(value)


def assigned_value(match, line):
    """The value of a key, token, secret or password assignment, or None when it holds no real value."""
    quoted = match.group("bare") is None
    value = match.group("dq") if match.group("dq") is not None else match.group("sq") if quoted else match.group("bare")
    if re.search(r"\s", value) or not_a_value(value):
        return None
    name, digit = match.group("name"), re.search(r"\d", value)
    if AUTH_NAME.search(name):
        return value if digit and len(value) >= 8 else None
    if not STRONG_NAME.search(name):  # sort_key, cache_key: a plain "key" counts only with an opaque value
        return value if digit and OPAQUE_VALUE.fullmatch(value) and re.search(r"[A-Za-z]", value) else None
    password = PASSWORD_NAME.search(name)
    if value.isdigit() and not password:
        return None
    if quoted:
        return value
    if CODE_NAME.fullmatch(value) or set(value) & set("()[]{}<>"):
        return None
    ends_line = not line[match.end():].strip(" \t;,)|")
    return value if digit or (ends_line and (match.group("sep") not in (":", "|") or password)) else None


def allowed_email(value, cfg):
    low = value.lower()
    if low in cfg["emails"] or MACHINE_ADDRESS.fullmatch(low):
        return True
    domain = low.rsplit("@", 1)[1]
    return any(domain == d or domain.endswith("." + d) for d in list(ALWAYS_ALLOWED_DOMAINS) + list(cfg["domains"]))


def not_a_phone(match):
    """Too few or too many digits, an amount of money, a round number such as 100 000 000, or a labelled company number.

    A KRS number is a run of ten digits starting with 00, which also reads as a dialling prefix.
    Grouped digits before a currency read the same as a phone number, so a phone word earlier on the line decides.
    """
    groups = re.findall(r"\d+", match.group(0))
    return (not 9 <= len("".join(groups)) <= 15 or groups[-2:] == ["000", "000"]
            or amount_of_money(match)
            or (match.group(0).isdigit() and company_number(match)))


def amount_of_money(match):
    return (bool(AMOUNT_SHAPE.fullmatch(match.group(0))) and bool(AMOUNT_AFTER.match(match.string, match.end()))
            and not PHONE_WORD.search(match.string[:match.start()]))


def weighted(digits, weights):
    return sum(int(d) * w for d, w in zip(digits, weights)) % 11


def valid_nip(d):
    return len(d) == 10 and weighted(d, (6, 5, 7, 2, 3, 4, 5, 6, 7)) == int(d[-1])  # a remainder of 10 is never valid


def valid_regon(d):
    weights = {9: (8, 9, 2, 3, 4, 5, 6, 7), 14: (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)}.get(len(d))
    return weights is not None and weighted(d, weights) % 10 == int(d[-1])


def valid_krs(d):
    return len(d) == 10 and d.startswith("00")  # no check digit, and the register has not left the 00 range


def valid_ean(d):
    return len(d) in (8, 13) and sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(reversed(d))) % 10 == 0


COMPANY_CHECKS = {"NIP": valid_nip, "REGON": valid_regon, "KRS": valid_krs, "EAN": valid_ean}


def company_number(match):
    """A number of the right length and check digit for a label close before it, with no word of another kind between."""
    before = match.string[:match.start()]
    if "pesel" in before.lower():  # a person's number on the line, as in "PESEL/NIP": never treated as a company's
        return False
    for label in COMPANY_LABEL.finditer(before):
        gap = before[label.end():]
        if len(gap) <= COMPANY_GAP and not re.search(r"\d", gap) and not PERSONAL_WORD.search(gap)\
                and COMPANY_CHECKS[label.group(1).upper()](match.group(0)):
            return True
    return False


def sweep(line, regex, hit, keep=None):
    """Report every match and blank it, so one value is reported once and no later rule reads it again."""
    def replace(match):
        if keep is None or not keep(match):
            hit(match.group(0))
        return " " * len(match.group(0))
    return regex.sub(replace, line)


def blank(line, regex):
    return regex.sub(lambda m: " " * len(m.group(0)), line)


def is_gate_record(path):
    """Directly inside the gates/ folder at the top of a git repository."""
    folder = os.path.dirname(os.path.abspath(path))
    return os.path.basename(folder) == "gates" and os.path.exists(os.path.join(os.path.dirname(folder), ".git"))


def scan_line(line, cfg, report, gate_record=False):
    for rule, regex in SECRET_RULES:
        line = sweep(line, regex, lambda v, r=rule: report("secret", r, v))
    for rule, regex in PASSWORD_RULES:
        line = sweep(line, regex, lambda v, r=rule: report("secret", r, v), keep=lambda m: not_a_value(m.group("pw")))
    for match in list(ASSIGNMENT.finditer(line)) + list(TABLE_CELLS.finditer(line)):
        value = assigned_value(match, line)
        if value:
            report("secret", "assignment", value)
    if gate_record:  # after the secret rules, so a token written as the address is still found
        line = blank(line, GATE_IDENTITY)
    for rule, kind, regex in cfg["patterns"]:
        line = sweep(line, regex, lambda v, k=kind, r=rule: report(k, r, v))
    for regex in SCRUB_FIRST:
        line = blank(line, regex)
    line = sweep(line, EMAIL, lambda v: report("pii", "email", v), keep=lambda m: allowed_email(m.group(0), cfg))
    line = sweep(line, IBAN, lambda v: report("pii", "iban", v), keep=lambda m: len(re.sub(r"\D", "", m.group(0))) < 10)
    line = blank(line, URL)
    line = sweep(line, PHONE, lambda v: report("pii", "phone", v), keep=not_a_phone)
    sweep(line, LONG_DIGITS, lambda v: report("pii", "long-digits", v), keep=company_number)


def scan_file(path, shown, cfg, unread, gate_records=False):
    findings, seen = [], set()

    def add(number, kind, rule, value, safe):
        if (number, kind, rule, value) not in seen:
            seen.add((number, kind, rule, value))
            findings.append({"path": shown.replace(os.sep, "/"), "line": number, "kind": kind, "rule": rule, "value": safe})

    typed = file_finding(os.path.basename(path))
    if typed:
        add(1, "filetype", typed[0], typed[1], typed[1])
    text = read_text(path)
    if text is None and not typed:
        unread.append(shown.replace(os.sep, "/"))
    gate_record = gate_records and is_gate_record(path)
    for number, line in enumerate(text.split("\n") if text else [], 1):
        scan_line(line.rstrip("\r"), cfg, lambda kind, rule, value, n=number: add(n, kind, rule, value, mask(kind, value)), gate_record)
    return findings


def main(argv):
    for stream in (sys.stdout, sys.stderr):  # UTF-8 with LF: Windows text mode adds CR, which breaks every shell caller
        stream.reconfigure(encoding="utf-8", newline="\n")
    parser = argparse.ArgumentParser(prog="hg-tool scan", allow_abbrev=False)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--git", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if not args.paths and not args.git:
        parser.error("give at least one PATH, or --git")
    paths = [native_path(p) for p in args.paths]
    cfg = load_config(native_path(args.config) if args.config else None)
    files = list(git_files(paths) if args.git else walk_files(paths))
    findings, unread = [], []
    for path, shown in files:
        findings.extend(scan_file(path, shown, cfg, unread, gate_records=True))
    if args.as_json:
        print(json.dumps({"scanned": len(files), "findings": findings, "not_read": unread}, ensure_ascii=False))
    else:
        for item in findings:
            print("%s:%d\t%s\t%s" % (item["path"], item["line"], item["kind"], item["value"]))
    hit_files = len({item["path"] for item in findings})
    for shown in unread:
        print("scan: binary, not read: %s" % shown, file=sys.stderr)
    print("scan: %d files, %d findings in %d files" % (len(files), len(findings), hit_files), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
