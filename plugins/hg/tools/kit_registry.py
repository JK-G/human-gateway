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
    "SOURCE_CHECK_DAYS": "7",
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
    for key, flat in JSON_TOP.items():
        if key in data:
            conf[flat] = _flat(data[key])
    for group, mapping in JSON_NESTED.items():
        section = data.get(group) if isinstance(data.get(group), dict) else {}
        for key, flat in mapping.items():
            if key in section:
                conf[flat] = _flat(section[key])
    return conf

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
