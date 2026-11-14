#!/usr/bin/env python3
"""kit_registry.py - the one shared reader of .claude/hg.json and of the vault/schema.md type registry.
Stdlib only; validators and the index generator import it, so nothing hand-mirrors the registry.
CLI: kit_registry.py [--root DIR] types | projects [--with-cross] | conf KEY | conf --sh | frontmatter FILE | dump
  (one type / slug per line; a config value with defaults; KEY='value' lines; frontmatter as JSON; conf+registry as JSON)
Exit: 0 ok, 1 registry/parse error, 2 usage error.
"""
import datetime, json, os, re, shlex, subprocess, sys
from pathlib import Path

DEFAULTS = {  # applied when hg.json lacks a key
    "SCHEMA_VERSION": "1", "KIT_PROJECT_NAME": "workspace", "VAULT_DIR": "vault",
    "JOURNAL_DIR": "vault/journal", "LOG_FILE": "vault/log.jsonl",
    "MEMORY_INDEX": "vault/wiki/memory/index.md", "SCHEMA_FILE": "vault/schema.md", "PROJECTS": "",
    "FORBIDDEN_WRITE_PATHS": "vault/raw/ gates/ .obsidian/", "CONTENT_LANGUAGE": "en", "INFRA_LANGUAGE": "en",
    "TIMEZONE": "UTC", "WORKDAYS": "1-5", "CHEAP_MODEL": "sonnet", "ADVISOR_MODEL": "opus",
    "LOG_ROTATE_BYTES": "512000", "MAX_MD_LINES": "280", "MAX_MEMORY_LINE_CHARS": "300",
    "SOURCE_CHECK_DAYS": "7", "MESSENGER": "",
}
CONFIG_PARTS = (".claude", "hg.json")
EXPECTED_SCHEMA_VERSION = 1
JSON_TOP = {"schemaVersion": "SCHEMA_VERSION", "projectName": "KIT_PROJECT_NAME", "projects": "PROJECTS",
            "forbiddenWritePaths": "FORBIDDEN_WRITE_PATHS", "timezone": "TIMEZONE", "workdays": "WORKDAYS"}
JSON_NESTED = {
    "paths": {"vault": "VAULT_DIR", "journal": "JOURNAL_DIR", "log": "LOG_FILE",
              "memoryIndex": "MEMORY_INDEX", "schema": "SCHEMA_FILE"},
    "language": {"content": "CONTENT_LANGUAGE", "infra": "INFRA_LANGUAGE"},
    "models": {"cheap": "CHEAP_MODEL", "advisor": "ADVISOR_MODEL"},
    "limits": {"logRotateBytes": "LOG_ROTATE_BYTES", "maxMdLines": "MAX_MD_LINES",
               "maxMemoryLineChars": "MAX_MEMORY_LINE_CHARS"},
    "gates": {"sourceCheckDays": "SOURCE_CHECK_DAYS"},
}
TEMPORAL = ("living", "snapshot")
STATUS = ("active", "superseded", "retracted")
META_FILES = {"index.md", "TAGS.md", "README.md"}
REGISTRY_MARK = "# kit:type-registry"
MESSENGER_TYPES = ("slack", "teams", "webhook")  # nodes.messenger.type; notify.CHANNELS has one entry for each
# The rule for every commit in a department repository, worded once. The session start prints it and the skills,
# the agents, the rules and the workspace templates copy it word for word (a test holds this). Nothing enforces
# it: the agent keeps its own git commit and push. It names the commit step in words, so a template that copies it
# holds no line the publish check reads as an instruction to an assistant.
PUBLISH_RULE = ("Before any commit in a department repository, run hg-tool publish check, show the person the preview "
                "it writes, and commit only through the commit step of /hg:publish, after the person's own yes in "
                "this session.")
PUBLISH_WORD_RE = re.compile(r"[^\W_]+")


def valid_publish_word(entry):
    """An entry of publish.words: 2 to 60 characters on one line, holding a word; a final * needs a stem of at least
    3 characters, and no other * is allowed."""
    if not isinstance(entry, str) or not 2 <= len(entry) <= 60 or "\n" in entry or "\r" in entry:
        return False
    body = entry[:-1] if entry.endswith("*") else entry
    if "*" in body or not PUBLISH_WORD_RE.search(body):
        return False
    if entry.endswith("*"):
        words = PUBLISH_WORD_RE.findall(body)
        return bool(words) and body.rstrip() == body and len(words[-1]) >= 3
    return True

class RegistryError(Exception):
    """Registry, schema or YAML problem."""

def kit_root(override=None):
    if override:
        return Path(override).resolve()
    if os.environ.get("CLAUDE_PROJECT_DIR"):  # set by Claude Code for hooks and tools
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else Path.cwd()
    except OSError:
        return Path.cwd()

def stdio_utf8():
    """UTF-8 with LF on stdout and stderr: Windows text mode adds CR, which breaks every shell caller."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="\n")

def local_now(tzname):
    """Now in the configured zone. Windows has no zone database without the tzdata package, so fall back to the local clock."""
    if tzname.upper() == "UTC":
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(tzname))
    except Exception:
        return datetime.datetime.now()

def _flat(value):
    return " ".join(str(v) for v in value) if isinstance(value, list) else str(value)

def load_conf(root=None, strict=False):
    """Config as flat KEY -> string. A broken file falls back to the defaults, so the guards keep working; strict raises."""
    root = kit_root(root)
    conf = dict(DEFAULTS)
    path = root.joinpath(*CONFIG_PARTS)
    if not path.is_file():
        return conf
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("top level must be an object")
    except (ValueError, OSError) as exc:
        if strict:
            raise RegistryError("%s: %s" % ("/".join(CONFIG_PARTS), exc))
        print("hg: %s is unreadable (%s), using defaults" % ("/".join(CONFIG_PARTS), exc), file=sys.stderr)
        return conf
    return conf_from(data)

def conf_from(data):
    """The flat config of one parsed hg.json object, defaults filled in. load_conf reads the file on disk; the publish
    check passes the published and the staged copy."""
    conf = dict(DEFAULTS)
    for key, flat in JSON_TOP.items():
        if key in data:
            conf[flat] = _flat(data[key])
    for group, mapping in JSON_NESTED.items():
        section = data.get(group) if isinstance(data.get(group), dict) else {}
        for key, flat in mapping.items():
            if key in section:
                conf[flat] = _flat(section[key])
    conf["MESSENGER"] = messenger_type(data)
    return conf

def messenger_type(data):
    """nodes.messenger.type of a parsed hg.json when it is slack, teams or webhook, else ''."""
    nodes = data.get("nodes") if isinstance(data, dict) else None
    messenger = nodes.get("messenger") if isinstance(nodes, dict) else None
    value = messenger.get("type") if isinstance(messenger, dict) else None
    return value if isinstance(value, str) and value in MESSENGER_TYPES else ""

def raw_config(root=None):
    """The parsed .claude/hg.json as it is on disk, or {} when it is missing, unreadable or not an object."""
    path = kit_root(root).joinpath(*CONFIG_PARTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


# ---- private folders and source references --------------------------------------------------------
# A person's own files stay on one machine, outside git. scan.py holds the same five prefixes and four kept
# files itself, because it must stay one file with no imports; a test compares the two lists.
RAW_KINDS = ("meetings", "interviews", "sources", "snapshots")
SRC_REF_RE = re.compile(r"src:(meetings|interviews|sources|snapshots):\d{4}-\d{2}-\d{2}:[0-9a-f]{8}")
JOURNAL_DAY_RE = re.compile(r"journal/\d{4}-\d{2}-\d{2}\.md")
WIKI_PAGE_RE = re.compile(r"wiki/[^\s\"'`<>|\\]+\.md")


def _vault(conf):
    return str((conf or DEFAULTS).get("VAULT_DIR") or "vault").replace("\\", "/").strip("/")


def private_prefixes(conf=None):
    """Repo-relative folders that hold a person's own files: never tracked, never named in tracked text."""
    v = _vault(conf)
    return ["%s/raw/" % v, "%s/inbox/" % v, "%s/daily/" % v, "intake/", ".gateway/"]


def kept_files(conf=None):
    """The tracked template files inside the private folders."""
    v = _vault(conf)
    return ["%s/raw/README.md" % v, "%s/inbox/_template.md" % v, "%s/daily/README.md" % v, "intake/README.md"]


def is_private(rel, conf=None):
    """True for a repo-relative path inside a private folder, the kept files excepted. Case is ignored on every
    system, so a Windows clone and CI agree."""
    low = str(rel).replace("\\", "/")
    while low.startswith("./"):
        low = low[2:]
    low = low.casefold()
    if low in {k.casefold() for k in kept_files(conf)}:
        return False
    return any(low.startswith(p.casefold()) or low + "/" == p.casefold() for p in private_prefixes(conf))


def private_path_patterns(conf=None):
    """The two patterns of a path into a private folder as text: a raw file (vault-relative or repo-relative)
    and a file in intake/ or the inbox. Used by validate-plan, the log and the publish check. A path written
    with \\ is the same path: on Windows it is how a path is often written."""
    sep = r"[/\\]"
    v = sep.join(re.escape(part) for part in _vault(conf).split("/"))
    raw = re.compile(r"(?<![A-Za-z0-9_-])(?:%s%s)?raw%s[a-z0-9-]+%s(?:%s)%s[^\s\"'`)\]|<>]+"
                     % (v, sep, sep, sep, "|".join(RAW_KINDS), sep))
    # A name in intake/ or the inbox may hold spaces, as people name files: it runs to the first suffix on the line.
    other = re.compile(r"(?<![A-Za-z0-9_./\\-])(?:intake|(?:%s%s)?inbox)%s(?!README\.md|_template\.md)"
                       r"[^\s\"'`)\]|<>/\\][^\n\r\"'`|<>/\\]{0,119}?\.[A-Za-z0-9]{1,6}\b" % (v, sep, sep))
    return raw, other


def names_private_path(text, conf=None):
    return any(p.search(text) for p in private_path_patterns(conf))


def token_rule(names):
    """One regex for the name rule: a name of 6 characters or more stands as a whole token, case ignored."""
    names = sorted({n for n in names if len(n) >= 6}, key=lambda n: (-len(n), n))
    if not names:
        return None
    return re.compile(r"(?<![A-Za-z0-9._-])(?:%s)(?![A-Za-z0-9_-]|\.[A-Za-z0-9])" % "|".join(re.escape(n) for n in names),
                      re.I)


def source_name_files(root, conf=None):
    """{name: repo-relative path} of the names the source-name rule looks for, as the files are now on this computer:
    a raw file's name with and without its suffix, a file in the inbox or intake/ by its full name only."""
    v = _vault(conf)
    kept = {k.casefold() for k in kept_files(conf)}
    names = {}
    for folder, whole_only in (("%s/raw" % v, False), ("%s/inbox" % v, True), ("intake", True)):
        base = Path(root).joinpath(*folder.split("/"))
        if not base.is_dir():
            continue
        for full in sorted(base.rglob("*")):
            if not full.is_file() or full.name in ("links.md", ".gitkeep"):
                continue
            rel = full.relative_to(root).as_posix()
            if rel.casefold() in kept:
                continue
            stem, suffix = os.path.splitext(full.name)
            if whole_only:
                if suffix:
                    names.setdefault(full.name, rel)
            else:
                names.setdefault(full.name, rel)
                names.setdefault(stem, rel)
    return names


def names_source(text, root, conf=None):
    """True when the text names a private path, or the name of a file now in the raw folder, the inbox or intake/.
    A tool that writes tracked text refuses such text, so the publish check never meets it there."""
    if names_private_path(text, conf):
        return True
    rule = token_rule(source_name_files(root, conf))
    return bool(rule and rule.search(text))


def valid_source_entry(value):
    """What sources, derived_from, superseded_by and source_raw may hold: a source reference, a vault-relative
    wiki page or a journal day."""
    if not isinstance(value, str):
        return False
    if SRC_REF_RE.fullmatch(value) or JOURNAL_DAY_RE.fullmatch(value):
        return True
    return bool(WIKI_PAGE_RE.fullmatch(value)) and ".." not in value.split("/")


def source_check_days(conf):
    """N of gates.sourceCheckDays: a whole number from 1 to 90, anything else counts as 7."""
    value = str(conf.get("SOURCE_CHECK_DAYS", "7")).strip()
    return int(value) if re.fullmatch(r"\d{1,2}", value) and 1 <= int(value) <= 90 else 7

def projects(conf):
    return [p for p in conf.get("PROJECTS", "").split() if p]

def valid_project_slug(slug):
    return bool(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", slug)) and len(slug) <= 40 and slug not in ("cross", "unknown")


# ---- minimal YAML subset: block maps/lists, flow [..] {..}, quoted and plain scalars ----

def _strip_comment(s):
    q = None
    for i, ch in enumerate(s):
        if q:
            q = None if ch == q else q
        elif ch in "\"'" and (i == 0 or s[i - 1] in " \t[{,:"):
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()

_CONST = {"": None, "null": None, "~": None, "true": True, "True": True, "false": False, "False": False}


def _scalar(tok):
    t = tok.strip()
    if t in _CONST:
        return _CONST[t]
    if t[0] in "[{":
        val, rest = _flow(t, 0)
        if t[rest:].strip():
            raise RegistryError("trailing text after flow value: %r" % t)
        return val
    if t[0] == '"':
        return json.loads(t)
    if t[0] == "'":
        return t[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t) if "." in t else int(t)
    return t

def _read_token(s, i, stops):
    if s[i] in "\"'":
        q, j = s[i], i + 1
        while j < len(s) and s[j] != q:
            j += 2 if (q == '"' and s[j] == "\\") else 1
        return s[i:j + 1], j + 1
    j = i
    while j < len(s) and s[j] not in stops and not (":" in stops and s[j] == ":" and s[j + 1:j + 2] in (" ", "")):
        j += 1
    return s[i:j], j

def _skip(s, i):
    while i < len(s) and s[i] == " ":
        i += 1
    return i

def _flow(s, i):
    """Parse a flow collection starting at s[i]; return (value, next_index)."""
    is_map = s[i] == "{"
    closer, items, obj = ("}" if is_map else "]"), [], {}
    i += 1
    while True:
        while i < len(s) and s[i] in " \t,":
            i += 1
        if i >= len(s):
            raise RegistryError("unclosed flow collection")
        if s[i] == closer:
            return (obj if is_map else items), i + 1
        if not is_map:
            if s[i] in "[{":
                val, i = _flow(s, i)
            else:
                tok, i = _read_token(s, i, ",]")
                val = _scalar(tok)
            items.append(val)
            continue
        key, i = _read_token(s, i, ",}:")
        i, val = _skip(s, i), None
        if i < len(s) and s[i] == ":":
            i = _skip(s, i + 1)
            if i < len(s) and s[i] in "[{":
                val, i = _flow(s, i)
            else:
                tok, i = _read_token(s, i, ",}")
                val = _scalar(tok)
        obj[str(_scalar(key))] = val

def parse_yaml(text):
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        body = _strip_comment(raw)
        if body.strip():
            lines.append([len(body) - len(body.lstrip(" ")), body.strip()])
    val, i = _block(lines, 0, lines[0][0]) if lines else ({}, 0)
    if i != len(lines):
        raise RegistryError("unexpected indentation near: %r" % lines[i][1])
    return val

def _is_item(c):  # a block sequence entry
    return c == "-" or c.startswith("- ")
def _block(lines, i, ind):
    if _is_item(lines[i][1]):
        seq = []
        while i < len(lines) and lines[i][0] == ind and _is_item(lines[i][1]):
            rest = lines[i][1][1:].strip()
            if not rest:
                if i + 1 < len(lines) and lines[i + 1][0] > ind:
                    v, i = _block(lines, i + 1, lines[i + 1][0])
                else:
                    v, i = None, i + 1
            elif re.match(r'^[^\s"\'\[{][^:]*:(\s|$)', rest):
                lines[i] = [ind + 2, rest]
                v, i = _block(lines, i, ind + 2)
            else:
                v, i = _scalar(rest), i + 1
            seq.append(v)
        return seq, i
    obj = {}
    while i < len(lines) and lines[i][0] == ind and not _is_item(lines[i][1]):
        m = re.match(r'^("[^"]*"|\'[^\']*\'|[^:]+?)\s*:(?:\s+(.*))?$', lines[i][1])
        if not m:
            raise RegistryError("cannot parse line: %r" % lines[i][1])
        key, rest = str(_scalar(m.group(1))), (m.group(2) or "").strip()
        i += 1
        if rest in ("|", ">", "|-", ">-"):
            j = i
            while j < len(lines) and lines[j][0] > ind:
                j += 1
            obj[key], i = ("\n" if rest[0] == "|" else " ").join(l[1] for l in lines[i:j]), j
        elif rest:
            obj[key] = _scalar(rest)
        elif i < len(lines) and (lines[i][0] > ind or (lines[i][0] == ind and _is_item(lines[i][1]))):
            obj[key], i = _block(lines, i, lines[i][0])
        else:
            obj[key] = None
    return obj, i

def load_yaml(text):
    """Minimal parser first (deterministic); PyYAML only as a fallback on parse errors."""
    try:
        return parse_yaml(text)
    except (RegistryError, ValueError) as exc:
        try:
            import yaml  # optional
        except ImportError:
            raise RegistryError(str(exc))
        return json.loads(json.dumps(yaml.safe_load(text), default=str))

def load_registry(root=None, conf=None):
    root = kit_root(root)
    conf = conf or load_conf(root)
    schema = root / conf["SCHEMA_FILE"]
    if not schema.is_file():
        raise RegistryError("schema file not found: %s" % conf["SCHEMA_FILE"])
    m = re.search(r"```ya?ml[ \t]*\n(" + re.escape(REGISTRY_MARK) + r".*?)\n```",
                  schema.read_text(encoding="utf-8"), re.S)
    if not m:
        raise RegistryError("no ```yaml block starting with '%s' in %s" % (REGISTRY_MARK, conf["SCHEMA_FILE"]))
    data = load_yaml(m.group(1))
    if not isinstance(data, dict) or not isinstance(data.get("types"), dict):
        raise RegistryError("registry block must define a 'types' mapping")
    for name, spec in list(data["types"].items()):
        spec = spec or {}
        data["types"][name] = dict(spec, dir=spec.get("dir") or "wiki/%s" % name, required=list(spec.get("required") or []),
                                   sections=list(spec.get("sections") or []), stale_days=int(spec.get("stale_days") or 0))
    data["universal_required"] = list(data.get("universal_required") or [])
    return data

def split_frontmatter(text):
    """Return (frontmatter_text or None, body, body_start_line_1based)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    close = next((k for k in range(1, len(lines)) if lines[k].strip() == "---"), None)
    if lines[0].strip() != "---" or close is None:
        return None, text, 1
    return "\n".join(lines[1:close]), "\n".join(lines[close + 1:]), close + 2

def parse_frontmatter(path):
    """Return (dict or None, body, body_start_line). Raises RegistryError on bad YAML."""
    fm_text, body, start = split_frontmatter(Path(path).read_text(encoding="utf-8", errors="replace"))
    if fm_text is None:
        return None, body, start
    data = load_yaml(fm_text) if fm_text.strip() else {}
    if not isinstance(data, dict):  # e.g. a bare list
        raise RegistryError("frontmatter is not a mapping")
    return data, body, start

def wiki_dir(root=None, conf=None):
    root = kit_root(root)
    return root / (conf or load_conf(root))["VAULT_DIR"] / "wiki"

def iter_wiki_pages(root=None, conf=None, include_meta=False):
    """Wiki pages, sorted; skips index.md, TAGS.md, README.md and _-prefixed files unless include_meta."""
    base = wiki_dir(root, conf)
    pages = sorted(base.rglob("*.md")) if base.is_dir() else []
    return (p for p in pages if include_meta or not (p.name in META_FILES or p.name.startswith("_")))

def main(argv):
    stdio_utf8()
    args, root = list(argv), None
    if "--root" in args[:-1]:
        k = args.index("--root")
        root = args.pop(k + 1)
        args.pop(k)
    with_cross = "--with-cross" in args
    args = [a for a in args if a != "--with-cross"]
    try:
        conf = load_conf(root, strict=True)
        cmd, rest = args[0], args[1:]
        if cmd == "projects":
            out = "\n".join(projects(conf) + (["cross"] if with_cross else []))
        elif cmd == "conf" and rest == ["--sh"]:
            out = "\n".join("%s=%s" % (k, shlex.quote(v)) for k, v in sorted(conf.items()))
        elif cmd == "conf" and len(rest) == 1:
            out = conf.get(rest[0], "")
        elif cmd == "types":
            out = "\n".join(load_registry(root, conf)["types"])
        elif cmd == "frontmatter" and len(rest) == 1:
            out = json.dumps(parse_frontmatter(rest[0])[0], ensure_ascii=False, sort_keys=True)
        elif cmd == "dump":
            out = json.dumps({"conf": conf, "registry": load_registry(root, conf)}, indent=2, ensure_ascii=False)
        else:
            raise IndexError
        print(out)
    except IndexError:
        print(__doc__, file=sys.stderr)
        return 2
    except (RegistryError, OSError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
