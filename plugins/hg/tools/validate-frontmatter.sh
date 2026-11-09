#!/usr/bin/env bash
# validate-frontmatter.sh - deterministic frontmatter validator for wiki pages.
#
# Reads the type registry from vault/schema.md and the project list from
# .claude/kit.conf through kit_registry.py (never a hardcoded mirror).
#
# Usage: validate-frontmatter.sh [--root DIR] [PATH ...]
#   PATH = page file or directory (default: <VAULT_DIR>/wiki)
# Output: one finding per line, LEVEL<TAB>path[:line]<TAB>message
# Exit:   0 clean (WARN/INFO allowed), 1 ERROR findings, 2 usage/setup error.
#
# Checks: frontmatter present and parseable; universal + per-type required keys;
# known type; temporal/status enums; project in PROJECTS or "cross"; last_verified
# date format; list-valued keys are lists; page sits in its type's dir; required H2
# sections; keys not documented in schema.md (WARN); filed query answers carry
# provenance (pages a log `file_back` op created need derived_from, every `### Q:`
# entry under `## Q&A` needs a "Derived from: [[...]]" line); tags not in TAGS.md
# (INFO); living pages older than the type's stale_days (WARN).
# Env: KIT_TODAY=YYYY-MM-DD pins "today" (tests).
set -u
TOOLS="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"
PY="${HG_PYTHON:-python3}"
ROOT=""
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --root) [ $# -ge 2 ] || { echo "usage: $0 [--root DIR] [PATH ...]" >&2; exit 2; }; ROOT="$2"; shift 2 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
[ -n "$ROOT" ] || ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
[ -d "$ROOT" ] || { echo "ERROR: root not found: $ROOT" >&2; exit 2; }

exec $PY - "$TOOLS" "$ROOT" ${ARGS[@]+"${ARGS[@]}"} <<'PY'
import datetime, json, os, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import kit_registry as kr
kr.stdio_utf8()

root = Path(sys.argv[2]).resolve()
conf = kr.load_conf(root)
try:
    reg = kr.load_registry(root, conf)
except kr.RegistryError as exc:
    print("ERROR\t%s\tregistry: %s" % (conf["SCHEMA_FILE"], exc)); sys.exit(2)
types, universal = reg["types"], reg["universal_required"]
projects = set(kr.projects(conf)) | {"cross"}
vault = root / conf["VAULT_DIR"]
today = datetime.date.fromisoformat(os.environ.get("KIT_TODAY") or datetime.date.today().isoformat())
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Documented keys: backticked keys in the "Universal frontmatter" table and the
# "Type-specific keys" cells of the "Type notes" table in schema.md, plus registry keys.
schema_text = (root / conf["SCHEMA_FILE"]).read_text(encoding="utf-8")
def section(title):
    m = re.search(r"^#{2,3} %s\s*$(.*?)(?=^#{1,3} )" % re.escape(title), schema_text + "\n# ", re.M | re.S)
    return m.group(1) if m else ""
documented = set(re.findall(r"^\|\s*`([a-z_]+)`", section("Universal frontmatter"), re.M))
type_keys = {}
for row in re.findall(r"^\|\s*`([a-z-]+)`\s*\|(.*)$", section("Type notes"), re.M):
    type_keys[row[0]] = set(re.findall(r"`([a-z][a-z_]*)", row[1].split("|")[-2] if row[1].count("|") >= 2 else row[1]))

# Pages created by a `file_back` log op must carry derived_from.
filed = set()
log_files = [root / conf["LOG_FILE"]] + sorted(((root / conf["LOG_FILE"]).parent / "log").glob("*.jsonl"))
for lf in log_files:
    if lf.is_file():
        for raw in lf.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if ev.get("op") == "file_back":
                for o in ev.get("outputs") or []:
                    o = str(o)
                    filed.add((root / o) if o.startswith(conf["VAULT_DIR"].rstrip("/") + "/") else (vault / o))
filed = {p.resolve() for p in filed}

tags_file = vault / "wiki" / "TAGS.md"
canon_tags = set()
if tags_file.is_file():
    canon_tags = set(re.findall(r"^\s*[-*]\s+`([a-z0-9][a-z0-9-]*)`", tags_file.read_text(encoding="utf-8"), re.M))

targets = [Path(a) if Path(a).is_absolute() else (Path.cwd() / a) for a in sys.argv[3:]]
if not targets:
    targets = [vault / "wiki"]
files = []
for t in targets:
    if t.is_file():
        files.append(t)
    elif t.is_dir():
        files += [p for p in sorted(t.rglob("*.md")) if p.name not in kr.META_FILES and not p.name.startswith("_")]
    else:
        print("ERROR\t%s\tpath not found" % t); sys.exit(2)

findings, errors = [], 0
def emit(level, path, msg, line=None):
    global errors
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        rel = path
    loc = "%s:%d" % (rel, line) if line else str(rel)
    findings.append("%s\t%s\t%s" % (level, loc, msg))
    if level == "ERROR":
        errors += 1

for f in files:
    try:
        fm, body, body_line = kr.parse_frontmatter(f)
    except kr.RegistryError as exc:
        emit("ERROR", f, "frontmatter_yaml: %s" % exc, 1); continue
    if fm is None:
        emit("ERROR", f, "no_frontmatter: page has no --- frontmatter block", 1); continue
    t = fm.get("type")
    if t == "index":
        continue
    for k in universal:
        if k not in fm:
            emit("ERROR", f, "missing_key: '%s' (universal)" % k)
    if t not in types:
        emit("ERROR", f, "unknown_type: '%s' not in registry (%s)" % (t, ", ".join(types))); continue
    spec = types[t]
    for k in spec["required"]:
        if k not in fm:
            emit("ERROR", f, "missing_key: '%s' (required for type %s)" % (k, t))
    if "temporal" in fm and fm["temporal"] not in kr.TEMPORAL:
        emit("ERROR", f, "bad_enum: temporal='%s' (allowed: %s)" % (fm["temporal"], "|".join(kr.TEMPORAL)))
    status = fm.get("status")
    if "status" in fm and status not in kr.STATUS:
        emit("ERROR", f, "bad_enum: status='%s' (allowed: %s)" % (status, "|".join(kr.STATUS)))
    if "project" in fm and fm["project"] not in projects:
        emit("ERROR", f, "bad_project: '%s' not in kit.conf PROJECTS or 'cross'" % fm["project"])
    lv = fm.get("last_verified")
    if "last_verified" in fm and not (isinstance(lv, str) and DATE.match(lv)):
        emit("ERROR", f, "bad_date: last_verified must be YYYY-MM-DD")
    for k in ("aliases", "sources", "derived_from", "tags", "canonical_for"):
        if k in fm and fm[k] is not None and not isinstance(fm[k], list):
            emit("ERROR", f, "not_a_list: '%s' must be a YAML list" % k)
    if documented:
        for k in fm:
            if k not in documented and k not in spec["required"] and k not in type_keys.get(t, set()):
                emit("WARN", f, "unknown_key: '%s' is not documented in %s" % (k, conf["SCHEMA_FILE"]))
    if status == "superseded" and not fm.get("superseded_by"):
        emit("WARN", f, "superseded_without_pointer: add superseded_by: <page>")
    expected_dir = (vault / spec["dir"]).resolve()
    if expected_dir not in f.resolve().parents:
        emit("WARN", f, "wrong_dir: type %s belongs under %s/%s" % (t, conf["VAULT_DIR"], spec["dir"]))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", f.stem):
        emit("WARN", f, "bad_slug: filename should be lowercase kebab-case")

    h2 = {}
    lines = body.split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            h2.setdefault(m.group(1), body_line + i)
    level = "ERROR" if status in (None, "active") else "WARN"
    for s in spec["sections"]:
        if s not in h2:
            emit(level, f, "missing_section: '## %s' (required for type %s)" % (s, t))

    # Filed query answers: new pages need derived_from; every Q&A entry needs a citation line.
    if f.resolve() in filed and not fm.get("derived_from"):
        emit("ERROR", f, "uncited_query_output: page filed back from /wiki-query without derived_from")
    if "Q&A" in h2:
        start = h2["Q&A"] - body_line
        entry, cited = None, True
        for i in range(start + 1, len(lines) + 1):
            line = lines[i] if i < len(lines) else "## END"
            if line.startswith("### ") or line.startswith("## "):
                if entry is not None and not cited:
                    emit("ERROR", f, "uncited_query_output: Q&A entry without 'Derived from:' line", entry)
                if line.startswith("## "):
                    break
                entry, cited = body_line + i, False
            elif re.match(r"^\s*\*{0,2}Derived from:", line, re.I) and "[[" in line:
                cited = True

    tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
    if canon_tags:
        for tg in tags:
            if tg not in canon_tags:
                emit("INFO", f, "unknown_tag: '%s' not in wiki/TAGS.md" % tg)

    if fm.get("temporal") == "living" and status in (None, "active") and spec["stale_days"] > 0 \
            and isinstance(lv, str) and DATE.match(lv):
        age = (today - datetime.date.fromisoformat(lv)).days
        if age > spec["stale_days"]:
            # fictional example pages age by design: report them, do not warn
            lvl = "INFO" if str(f).rsplit("/", 1)[-1].startswith("example--") else "WARN"
            emit(lvl, f,"stale: last_verified %s is %d days old (stale_days %d)" % (lv, age, spec["stale_days"]))

for line in findings:
    print(line)
sys.exit(1 if errors else 0)
PY
