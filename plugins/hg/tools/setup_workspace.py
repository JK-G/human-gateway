#!/usr/bin/env python3
"""setup_workspace.py - turn a folder into a department workspace. Non-interactive.

Usage: hg-tool setup [--root DIR] [--name N] [--language L] [--timezone Z] [--marketplace owner/repo] [--project slug]
       hg-tool setup [--root DIR] --refresh-ci      (--refresh-scan is another name for it)

Creates whatever is missing from templates/workspace, generates .claude/hg.json and runs git init when
the folder is in no repository. Never overwrites an existing file, so a second run changes nothing. Two
additions, which only add what is missing: an existing .gitignore gets the template's missing lines, because without
them intake/ reaches git, and an existing .claude/settings.json gets the template's missing permission rules and the
marketplace, because `claude plugin install --scope project` creates that file first. --project also adds vault/projects/<slug> and vault/raw/<slug>/.

CI has no plugin, so the five tools it runs are copied to .github/hg/ (scan.py, notify.py, gate.py, canonicalize.py,
kit_registry.py). --refresh-ci replaces those copies, the one case where a file is overwritten, and creates
.github/workflows/hg-scan.yml and hg-notify.yml when they are missing. It never overwrites a workflow file and touches
nothing else.

Output: created<TAB>path, skipped<TAB>path, updated<TAB>path, note<TAB>text, error<TAB>text, then one summary line.
Exit: 0 ok, 1 a file or git step failed, 2 usage error.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

TEMPLATE =Path(__file__).resolve().parent.parent / "templates" / "workspace"
TOOLS = Path(__file__).resolve().parent
CI_TOOLS = ("scan.py", "notify.py", "gate.py", "canonicalize.py", "kit_registry.py")
CI_DIR = ".github/hg"
WORKFLOWS = (".github/workflows/hg-scan.yml", ".github/workflows/hg-notify.yml")
TOKEN_FILES = {"CLAUDE.md", "AGENTS.md"}
RAW_KINDS = ("meetings", "interviews", "sources", "snapshots")
MARKETPLACE = "human-gateway"
SETTINGS = ".claude/settings.json"
FORBIDDEN_PATHS = ["vault/raw/", "gates/", ".obsidian/"]


class Report:
    def __init__(self):
        self.created = self.skipped = self.errors = 0

    def line(self, kind, text):
        print("%s\t%s" % (kind, text))
        if kind == "created":
            self.created += 1
        elif kind == "skipped":
            self.skipped += 1
        elif kind == "error":
            self.errors += 1


def native_root(raw):
    """Git Bash hands over /d/x or /tmp/x when told not to rewrite arguments; Windows Python cannot use them."""
    if os.name != "nt" or not raw.startswith("/"):
        return raw
    m = re.match(r"^/([A-Za-z])(?=/|$)", raw)
    if m:
        return m.group(1) + ":" + raw[2:]
    cygpath = shutil.which("cygpath")  # only Git Bash knows its mount points
    if cygpath:
        out = subprocess.run([cygpath, "-m", raw], capture_output=True, encoding="utf-8", errors="replace")
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return raw


def fill(text, values):
    """One pass, so a name that looks like a token is not expanded again."""
    return re.sub("|".join(re.escape(k) for k in values), lambda m: values[m.group(0)], text)


def create(root, rel, text, report):
    dest = root / rel
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "x", encoding="utf-8", newline="\n") as fh:  # "x" refuses an existing file
            fh.write(text)
    except FileExistsError:
        report.line("skipped", rel)
    except OSError as exc:
        report.line("error", "%s: %s" % (rel, exc))
    else:
        report.line("created", rel)


def with_marketplace(text, repo):
    data = json.loads(text)
    data["extraKnownMarketplaces"] = {MARKETPLACE: {"source": {"source": "github", "repo": repo}}}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def extend_gitignore(root, report):
    path = root / ".gitignore"
    lines = (TEMPLATE / ".gitignore").read_text(encoding="utf-8").splitlines()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        have = {ln.strip() for ln in text.splitlines()}
        missing = [ln for ln in lines if ln and not ln.startswith("#") and ln not in have]
        if missing:
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(("" if text.endswith("\n") or not text else "\n") + "\n# hg workspace\n" + "\n".join(missing) + "\n")
    except OSError as exc:
        report.line("error", ".gitignore: %s" % exc)
        return
    report.line("updated" if missing else "skipped", ".gitignore")


def add_permissions(have, want, report):
    """Append the rules missing from permissions.allow and .deny. Returns how many were added."""
    permissions = have.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        report.line("note", "%s: permissions is not an object, so it was left as it is and no rule was added" % SETTINGS)
        return 0
    added = 0
    for kind in ("allow", "deny"):
        rules = permissions.setdefault(kind, [])
        if not isinstance(rules, list):
            report.line("note", "%s: permissions.%s is not a list, so it was left as it is and no rule was added" % (SETTINGS, kind))
            continue
        missing = [rule for rule in want["permissions"][kind] if rule not in rules]
        rules.extend(missing)
        added += len(missing)
    return added


def add_marketplace(have, want, report):
    """Add this plugin's marketplace when the template or --marketplace gives one. Returns 1 when it was added."""
    entry = want.get("extraKnownMarketplaces", {}).get(MARKETPLACE)
    if entry is None:
        return 0
    known = have.setdefault("extraKnownMarketplaces", {})
    if not isinstance(known, dict):
        report.line("note", "--marketplace not applied: extraKnownMarketplaces in %s is not an object and was left as it is" % SETTINGS)
        return 0
    if MARKETPLACE not in known:
        known[MARKETPLACE] = entry
        return 1
    current = known[MARKETPLACE]
    if not isinstance(current, dict) or current.get("source") != entry["source"]:
        report.line("note", "--marketplace not applied: %s already names another source for %s and was left as it is" % (SETTINGS, MARKETPLACE))
    return 0


def extend_settings(root, text, report):
    """Settings made earlier, usually by `claude plugin install --scope project`, get what the workspace needs."""
    path = root / SETTINGS
    try:
        have = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(have, dict):
            raise ValueError("not an object")
    except ValueError:
        report.line("error", "%s is not valid JSON, so it was left as it is and the workspace's permission rules are not in place. "
                    "Correct the file, then run /hg:setup again." % SETTINGS)
        return
    except OSError as exc:
        report.line("error", "%s: %s" % (SETTINGS, exc))
        return
    want = json.loads(text)
    added = add_permissions(have, want, report) + add_marketplace(have, want, report)
    if not added:
        report.line("skipped", SETTINGS)
        return
    try:
        gate.write_atomic(path, json.dumps(have, indent=2, ensure_ascii=False) + "\n")
    except OSError as exc:
        report.line("error", "%s: %s" % (SETTINGS, exc))
        return
    report.line("updated", SETTINGS)


def copy_template(root, args, report):
    tokens = {"{{PROJECT_NAME}}": args.name, "{{CONTENT_LANGUAGE}}": args.language}
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(TEMPLATE).as_posix()
        if rel == ".gitignore" and (root / rel).is_file():
            extend_gitignore(root, report)
            continue
        text = src.read_text(encoding="utf-8")
        if rel in TOKEN_FILES:
            text = fill(text, tokens)
        elif rel == SETTINGS and args.marketplace:
            text = with_marketplace(text, args.marketplace)
        if rel == SETTINGS and (root / rel).is_file():
            extend_settings(root, text, report)
            continue
        create(root, rel, text, report)


def write_config(root, args, report):
    config = {
        "schemaVersion": kr.EXPECTED_SCHEMA_VERSION,
        "projectName": args.name,
        "projects": [args.project] if args.project else [],
        "timezone": args.timezone,
        "language": {"content": args.language, "infra": kr.DEFAULTS["INFRA_LANGUAGE"]},
        "forbiddenWritePaths": FORBIDDEN_PATHS,
        "neverInGit": {"extra": []},
        "scan": {"allow": {"emails": [], "domains": []}, "patterns": {}},
    }
    create(root, "/".join(kr.CONFIG_PARTS), json.dumps(config, indent=2, ensure_ascii=False) + "\n", report)


def add_project(root, args, report):
    slug = args.project
    conf = kr.load_conf(root)
    vault = conf["VAULT_DIR"].strip("/")
    template = root / vault / "projects" / "_template"
    if not template.is_dir():
        report.line("error", "%s/projects/_template is missing" % vault)
        return
    values = {"__SLUG__": slug, "__NAME__": slug.replace("-", " ").title(),
              "__DATE__": kr.local_now(conf["TIMEZONE"]).date().isoformat()}
    for src in sorted(template.rglob("*")):
        if src.is_file():
            rel = "%s/projects/%s/%s" % (vault, slug, src.relative_to(template).as_posix())
            create(root, rel, fill(src.read_text(encoding="utf-8"), values), report)
    for kind in RAW_KINDS:
        create(root, "%s/raw/%s/%s/.gitkeep" % (vault, slug, kind), "", report)
    if slug not in kr.projects(conf):
        report.line("note", "add \"%s\" to projects with: hg-tool conf-set project %s" % (slug, slug))


def refresh_ci(root):
    """Replace the five copies CI runs and create a missing workflow. One line per file."""
    if not root.joinpath(*kr.CONFIG_PARTS).is_file():
        print("error\t.claude/hg.json is missing, so this is not a department workspace. Run /hg:setup.")
        return 1
    report = Report()
    for name in CI_TOOLS:
        rel = "%s/%s" % (CI_DIR, name)
        new = (TOOLS / name).read_text(encoding="utf-8")
        dest = root / rel
        existed = dest.is_file()
        if existed and dest.read_text(encoding="utf-8") == new:
            report.line("skipped", rel)
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
        except OSError as exc:
            report.line("error", "%s: %s" % (rel, exc))
            continue
        report.line("updated" if existed else "created", rel)
    for rel in WORKFLOWS:
        create(root, rel, (TEMPLATE / rel).read_text(encoding="utf-8"), report)
    return 1 if report.errors else 0


def git_init(root, report):
    try:
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, encoding="utf-8", errors="replace")
        if inside.returncode == 0:
            report.line("skipped", ".git")
            return
        done = subprocess.run(["git", "init", "-b", "main", str(root)],
                              capture_output=True, encoding="utf-8", errors="replace")
    except OSError:
        report.line("error", "git is not installed, so no repository was created. Run /hg:setup.")
        return
    if done.returncode == 0:
        report.line("created", ".git")
    else:
        report.line("error", "git init failed: %s" % done.stderr.strip())


def parse(argv):
    parser = argparse.ArgumentParser(prog="hg-tool setup", allow_abbrev=False)
    parser.add_argument("--root")
    parser.add_argument("--name")
    parser.add_argument("--language", default=kr.DEFAULTS["CONTENT_LANGUAGE"])
    parser.add_argument("--timezone", default=kr.DEFAULTS["TIMEZONE"])
    parser.add_argument("--marketplace")
    parser.add_argument("--project")
    parser.add_argument("--refresh-ci", "--refresh-scan", dest="refresh_ci", action="store_true")
    args = parser.parse_args(argv)
    if args.name is not None and (not args.name.strip() or "\n" in args.name):
        parser.error("--name must be one non-empty line")
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*", args.language):
        parser.error("--language must be a language code such as pl or en")
    if not re.fullmatch(r"[A-Za-z0-9_+./-]+", args.timezone):
        parser.error("--timezone must be a zone name such as Europe/Warsaw")
    if args.marketplace and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.marketplace):
        parser.error("--marketplace must look like owner/repo")
    if args.project and not kr.valid_project_slug(args.project):
        parser.error("--project must be a kebab-case slug of at most 40 characters, and not cross or unknown")
    return args


def main(argv):
    kr.stdio_utf8()
    args = parse(argv)
    root = kr.kit_root(native_root(args.root) if args.root else None)
    if args.refresh_ci:
        return refresh_ci(root)
    args.name = args.name or root.name
    report = Report()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        report.line("error", "%s: %s" % (root, exc))
        return 1
    copy_template(root, args, report)
    write_config(root, args, report)
    for name in CI_TOOLS:
        create(root, "%s/%s" % (CI_DIR, name), (TOOLS / name).read_text(encoding="utf-8"), report)
    if args.project:
        add_project(root, args, report)
    git_init(root, report)
    print("setup: %d created, %d skipped, %d errors in %s" % (report.created, report.skipped, report.errors, root.as_posix()))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
