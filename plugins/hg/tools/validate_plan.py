#!/usr/bin/env python3
"""validate_plan.py - validate a wiki change plan before anything is written.

Usage: hg-tool validate-plan [--root DIR] [--check-pages] <plan.json>
  --check-pages  also re-hash every page named by page_hash_expected / source_hash_expected
                 and fail on mismatch (the librarian runs this right before --apply)
Output: ERROR<TAB>path<TAB>[rule] message, one finding per line.
Exit:   0 valid, 1 invalid (writes <plan>.errors.json), 2 usage error.

Checks:
  - shape: change-plan.schema.json via python jsonschema when installed, plus built-in checks
    that always run (enums, per-op required fields, patterns)
  - source exists and source_hash == sha1 of its bytes
  - target_project in hg.json projects or "cross"
  - project write guard: every touched page belongs to target_project or cross
  - new pages: type in the vault/schema.md registry, required frontmatter, placed in the type's
    dir, file does not exist yet
  - ingest map (vault/schema.md "## Ingest map"): for op ingest / file_back, every new or edited
    page type must be allowed for the source's row (rule rejected_ingest_scope)
  - dedup scope guard: no op may touch PRD.md, raw/ or planning/ paths
"""
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import canonicalize  # noqa: E402
import kit_registry as kr  # noqa: E402

EDIT_OPS = ("section_merge", "section_replace", "append", "add_alias", "add_source_ref", "extract_section",
            "replace_with_transclude", "set_canonical_for", "set_frontmatter")
FRONTMATTER_KEYS = {"status", "superseded_by", "last_verified", "temporal"}
HASH = re.compile(r"^sha1:[a-f0-9]{40}$")


class Report:
    def __init__(self):
        self.items = []

    def err(self, rule, path, message):
        message = str(message).replace("\t", " ").replace("\n", " ")
        print("ERROR\t%s\t[%s] %s" % (path, rule, message))
        self.items.append({"rule": rule, "path": path, "message": message})


def has_all(entry, *keys):
    return all(k in entry for k in keys)


def shape_checks(plan, vault, rep):
    edits = plan.get("edits") or []
    new_pages = plan.get("new_pages") or []

    def check(condition, rule, path, message):
        try:
            passed = bool(condition())
        except Exception:
            passed = False
        if not passed:
            rep.err(rule, path, message)

    def with_op(*ops):
        return [e for e in edits if e.get("op") in ops]

    def is_conf(e):
        c = e["confidence"]
        return isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1

    def is_list(entry, key):
        return isinstance(entry.get(key), list)

    check(lambda: plan.get("schema_version") == "1.0", "schema_version", ".schema_version", 'schema_version must be "1.0"')
    check(lambda: isinstance(plan.get("source"), str), "source.type", ".source", "source must be a string path")
    check(lambda: HASH.search(plan["source_hash"]), "source_hash.pattern", ".source_hash", "source_hash must be sha1:<40 hex>")
    check(lambda: re.search(r"^(cross|[a-z0-9][a-z0-9-]*)$", plan["target_project"]), "target_project.pattern",
          ".target_project", 'target_project must be a slug or "cross"')
    check(lambda: isinstance(plan.get("edits"), list), "edits.type", ".edits", "edits must be an array (may be empty)")
    check(lambda: all(e["op"] in EDIT_OPS for e in edits), "edits.op", ".edits[].op", "unknown edit op")
    check(lambda: all(is_conf(e) for e in edits), "edits.confidence", ".edits[].confidence", "confidence must be a number 0..1")
    check(lambda: all(len(e.get("rationale") or "") > 0 for e in edits), "edits.rationale", ".edits[].rationale", "every edit needs a rationale")
    check(lambda: all(has_all(e, "page", "page_hash_expected", "section", "content") for e in with_op("section_merge", "section_replace", "append")),
          "edits.mutating", ".edits[]", "section_merge/section_replace/append require page, page_hash_expected, section, content")
    check(lambda: all("page" in e and is_list(e, "values") for e in with_op("add_alias", "add_source_ref")),
          "edits.list_ops", ".edits[]", "add_alias/add_source_ref require page and values[]")
    check(lambda: all(has_all(e, "source_page", "source_hash_expected", "source_section", "target_page", "target_type", "target_frontmatter") for e in with_op("extract_section")),
          "edits.extract_section", ".edits[]", "extract_section requires source_page, source_hash_expected, source_section, target_page, target_type, target_frontmatter")
    check(lambda: all(has_all(e, "page", "page_hash_expected", "section", "transclude_target") for e in with_op("replace_with_transclude")),
          "edits.replace_with_transclude", ".edits[]", "replace_with_transclude requires page, page_hash_expected, section, transclude_target")
    check(lambda: all(has_all(e, "page", "page_hash_expected") and is_list(e, "canonical_for") for e in with_op("set_canonical_for")),
          "edits.set_canonical_for", ".edits[]", "set_canonical_for requires page, page_hash_expected, canonical_for[]")
    check(lambda: all(has_all(e, "page", "page_hash_expected") and set(e.get("frontmatter") or {}) <= FRONTMATTER_KEYS for e in with_op("set_frontmatter")),
          "edits.set_frontmatter", ".edits[]", "set_frontmatter requires page + page_hash_expected and may only set status, superseded_by, last_verified, temporal")
    check(lambda: all(HASH.search(e[k]) for e in edits for k in ("page_hash_expected", "source_hash_expected") if e.get(k) is not None),
          "edits.hash_pattern", ".edits[]", "page hashes must be sha1:<40 hex>")

    def page_refs():
        return [e[k] for e in edits for k in ("page", "source_page", "target_page") if e.get(k) is not None] + [n.get("page") for n in new_pages]

    anchor = re.compile("^%s/wiki/" % re.escape(vault))
    check(lambda: all(anchor.search(p) and p.endswith(".md") for p in page_refs()),
          "path.anchor", ".edits/.new_pages", "every page path must be %s/wiki/<...>.md" % vault)
    try:
        scope = page_refs() + [p for e in edits for p in (e.get("requires_link_update") or [])]
        bad = sorted({p for p in scope if isinstance(p, str) and (re.search(r"(^|/)PRD\.md$", p) or re.search(r"(^|/)(raw|planning)/", p))})
    except Exception:
        bad = []
    if bad:
        rep.err("dedup.scope_guard", ".edits", "PRD.md, raw/ and planning/ are never edit or dedup targets: %s" % ", ".join(bad))


def source_checks(plan, root, vault, rep):
    source = plan.get("source")
    if not isinstance(source, str) or not source:
        return
    if not re.match("^%s/(raw|wiki|journal)/" % re.escape(vault), source):
        rep.err("source.pattern", ".source", "source must be under %s/raw/<project>/<kind>/, %s/journal/ or %s/wiki/: %s" % (vault, vault, vault, source))
    path = root / source
    if not path.is_file():
        rep.err("source.exists", ".source", "source file does not exist: %s" % source)
        return
    expected = plan.get("source_hash")
    if isinstance(expected, str) and expected:
        expected = expected.replace("sha1:", "", 1)
        actual = hashlib.sha1(path.read_bytes()).hexdigest()
        if actual != expected:
            rep.err("source_hash.mismatch", ".source_hash", "source changed since planning (expected %s, actual %s)" % (expected, actual))


def schema_check(plan, schema_path, vault, rep):
    try:
        import jsonschema
    except ImportError:
        return
    raw = schema_path.read_text(encoding="utf-8").replace("^vault/", "^%s/" % re.escape(vault))
    for e in sorted(jsonschema.Draft7Validator(json.loads(raw)).iter_errors(plan), key=lambda e: list(e.path)):
        rep.err("schema", "/".join(str(x) for x in e.path) or ".", e.message[:300])


def page_project(root, rel):
    try:
        fm, _, _ = kr.parse_frontmatter(root / rel)
        return (fm or {}).get("project")
    except (kr.RegistryError, OSError):
        return None


def registry_checks(plan, root, conf, check_pages, rep):
    vault = conf["VAULT_DIR"].rstrip("/")
    try:
        reg = kr.load_registry(root, conf)
    except kr.RegistryError as exc:
        rep.err("registry", conf["SCHEMA_FILE"], exc)
        return
    types, universal = reg["types"], reg["universal_required"]
    target = plan.get("target_project")
    if target not in set(kr.projects(conf)) | {"cross"}:
        rep.err("target_project.known", ".target_project", "'%s' is not in hg.json projects or 'cross'" % target)
    allowed = {"cross"} if target == "cross" else {target, "cross"}

    def hash_ok(rel, expected, where):
        if check_pages and rel and expected and (root / rel).is_file() and canonicalize.page_hash(root / rel) != expected:
            rep.err("stale_plan", where, "%s changed since the plan was drafted (page hash mismatch)" % rel)

    for i, e in enumerate(plan.get("edits") or []):
        if not isinstance(e, dict):
            continue
        where = ".edits[%d]" % i
        for key in ("page", "source_page"):
            rel = e.get(key)
            if not rel:
                continue
            if not (root / rel).is_file():
                rep.err("page.exists", where, "%s does not exist: %s" % (key, rel))
                continue
            owner = page_project(root, rel)
            if owner not in allowed:
                rep.err("project.write_guard", where, "%s belongs to project '%s', plan targets '%s'" % (rel, owner, target))
        hash_ok(e.get("page"), e.get("page_hash_expected"), where)
        hash_ok(e.get("source_page"), e.get("source_hash_expected"), where)
        if e.get("op") == "extract_section":
            tgt, ttype, tfm = e.get("target_page") or "", e.get("target_type"), e.get("target_frontmatter") or {}
            if tgt and (root / tgt).exists():
                rep.err("target.exists", where, "extract_section target already exists: %s" % tgt)
            if ttype not in types:
                rep.err("target_type.registry", where, "target_type '%s' not in registry" % ttype)
            if tfm.get("project") not in allowed:
                rep.err("project.write_guard", where, "target_frontmatter.project '%s' not allowed for '%s'" % (tfm.get("project"), target))

    for i, n in enumerate(plan.get("new_pages") or []):
        where, rel, ptype, fm = ".new_pages[%d]" % i, n.get("page") or "", n.get("type"), n.get("frontmatter") or {}
        if ptype not in types:
            rep.err("new_page.type", where, "type '%s' not in registry (%s)" % (ptype, ", ".join(types)))
            continue
        if fm.get("type") != ptype:
            rep.err("new_page.type_mismatch", where, "frontmatter.type '%s' != type '%s'" % (fm.get("type"), ptype))
        missing = [k for k in universal + types[ptype]["required"] if k not in fm]
        if missing:
            rep.err("new_page.frontmatter", where, "missing required frontmatter for %s: %s" % (ptype, ", ".join(missing)))
        if fm.get("project") not in allowed:
            rep.err("project.write_guard", where, "frontmatter.project '%s' not allowed for target '%s'" % (fm.get("project"), target))
        type_dir = "%s/%s/" % (vault, types[ptype]["dir"].strip("/"))
        if not rel.startswith(type_dir):
            rep.err("new_page.dir", where, "%s pages belong under %s" % (ptype, type_dir))
        if (root / rel).exists():
            rep.err("new_page.exists", where, "page already exists, use an edit op instead: %s" % rel)
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", Path(rel).stem) or len(Path(rel).stem) > 80:
            rep.err("new_page.slug", where, "filename must be kebab-case, at most 80 chars: %s" % rel)

    ingest_map_check(plan, root, conf, types, vault, rep)


def ingest_map_check(plan, root, conf, types, vault, rep):
    op = plan.get("op") or "ingest"
    text = (root / conf["SCHEMA_FILE"]).read_text(encoding="utf-8")
    section = re.search(r"^## Ingest map\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    rows = []
    for line in (section.group(1) if section else "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("`"):
            globs = re.findall(r"`([^`/][^`]*)`", cells[1])
            rows.append((cells[0].strip("`"), globs[0] if globs else "", [t for t in re.findall(r"`([a-z-]+)`", cells[2]) if t in types]))
    if op not in ("ingest", "file_back") or not rows:
        return
    src = str(plan.get("source") or "")
    vsrc = src[len(vault) + 1:] if src.startswith(vault + "/") else src
    if op == "file_back":
        row = next((r for r in rows if r[0] == "query"), None)
    else:
        row = next((r for r in rows if r[1] and fnmatch.fnmatch(vsrc, re.sub(r"<[^>]+>|YYYY-MM-DD", "*", r[1]))), None)
    if row is None:
        rep.err("rejected_ingest_scope", ".source", "source %s matches no ingest-map row in %s" % (src, conf["SCHEMA_FILE"]))
        return
    touched = [(".new_pages[%d]" % i, n.get("type")) for i, n in enumerate(plan.get("new_pages") or [])]
    for i, e in enumerate(plan.get("edits") or []):
        if isinstance(e, dict) and e.get("page") and (root / e["page"]).is_file():
            try:
                touched.append((".edits[%d]" % i, (kr.parse_frontmatter(root / e["page"])[0] or {}).get("type")))
            except kr.RegistryError:
                pass
    for where, ptype in touched:
        if ptype not in row[2]:
            rep.err("rejected_ingest_scope", where, "ingest-map row '%s' may not create or update type '%s' (allowed: %s)" % (row[0], ptype, ", ".join(row[2]) or "none"))


def usage():
    print("usage: hg-tool validate-plan [--root DIR] [--check-pages] <plan.json>", file=sys.stderr)
    return 2


def main(argv):
    kr.stdio_utf8()
    root_arg, check_pages, plan_arg, args = None, False, None, list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--root":
            if not args:
                return usage()
            root_arg = args.pop(0)
        elif arg == "--check-pages":
            check_pages = True
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        elif arg.startswith("--") or plan_arg is not None:
            return usage()
        else:
            plan_arg = arg
    if plan_arg is None:
        return usage()
    root = kr.kit_root(root_arg)
    if not root.is_dir():
        print("ERROR: root not found", file=sys.stderr)
        return 2
    plan_path = Path(plan_arg).resolve()
    if not plan_path.is_file():
        print("ERROR: plan not found: %s" % plan_path, file=sys.stderr)
        return 2
    schema_path = root / ".claude" / "schemas" / "change-plan.schema.json"
    if not schema_path.is_file():
        schema_path = HERE.parent / "schemas" / "change-plan.schema.json"
    stem = str(plan_path)
    errors_path = Path((stem[:-5] if stem.endswith(".json") else stem) + ".errors.json")

    conf = kr.load_conf(root)
    vault = conf["VAULT_DIR"].rstrip("/")
    rep = Report()
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except ValueError:
        plan = None
    if not isinstance(plan, dict):
        rep.err("json", str(plan_path), "plan is not a JSON object")
    else:
        shape_checks(plan, vault, rep)
        source_checks(plan, root, vault, rep)
        schema_check(plan, schema_path, vault, rep)
        registry_checks(plan, root, conf, check_pages, rep)

    if rep.items:
        errors_path.write_text(json.dumps(rep.items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1
    if errors_path.exists():
        errors_path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
