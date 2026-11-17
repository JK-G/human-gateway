#!/usr/bin/env python3
"""setup_workspace.py - turn a folder into a department workspace. Non-interactive.

Usage: hg-tool setup [--root DIR] [--name N] [--language L] [--timezone Z] [--marketplace owner/repo] [--project slug]
       hg-tool setup [--root DIR] --refresh-ci      (--refresh-scan is another name for it)

Creates whatever is missing from templates/workspace, generates .claude/hg.json and runs git init when
the folder is in no repository. Never overwrites an existing file, so a second run changes nothing. Two
additions, which only add what is missing: an existing .gitignore gets the template's missing lines, because without
them intake/ reaches git, and an existing .claude/settings.json gets the template's missing permission rules and the
marketplace, because `claude plugin install --scope project` creates that file first. The permission rules are
allow, ask (the person is asked before hg-tool publish commit runs) and deny. --project also adds
vault/projects/<slug>. It creates nothing under vault/raw/: that folder stays outside git, hg-tool raw-add makes the
folders it needs, and a placeholder file there would exist on one machine only.

CI has no plugin, so the five tools it runs are copied to .github/hg/ (scan.py, notify.py, gate.py, canonicalize.py,
kit_registry.py). --refresh-ci replaces those copies, the one case where a file is overwritten, and creates
.github/workflows/hg-scan.yml and hg-notify.yml when they are missing. It overwrites a workflow file only when it is
hg-notify.yml of an earlier release, which passes a secret name notify.py no longer reads. It also adds the missing
.gitignore lines, as setup does.

Both forms take out of the index the empty placeholders an earlier release made, vault/raw/<slug>/<kind>/.gitkeep,
once vault/raw/ is ignored (git rm --cached; the files stay on disk). The next /hg:publish sends that deletion. A
real raw file that is tracked is never touched: whoever maintains the repository runs git rm -r --cached vault/raw.

Output: created<TAB>path, skipped<TAB>path, updated<TAB>path, untracked<TAB>path, note<TAB>text, error<TAB>text, then
one summary line.
Exit: 0 ok, 1 a file or git step failed, 2 usage error.

A personal folder, one person's own (solo.py):

  hg-tool setup --personal [--language L|auto] [--name N] [--focus '<text>'] [--here] [--new] [--root DIR]

creates a folder whose .claude/hg.json says "mode": "personal" and "timezone": "local". It takes the texts of
templates/personal over those of templates/workspace and leaves out what only a shared folder needs (SHARED_ONLY,
and no copies for CI). It writes CLAUDE.local.md, starts git silently when git is there and the folder has no
repository of its own, and never commits. In a folder that already has hg.json it fills in what is missing in that
folder's own mode and never changes the mode. Plain `hg-tool setup` in a personal folder uses the personal file set.

Before it creates hg.json it creates nothing and exits 1 in five cases, each with its line: the folder lies inside
another repository (inside, then a say line); the folder is a repository of its own with a commit
(refused<TAB>history, then a say line); another place for notes is recorded on this computer and --new is
absent (place<TAB><path>, ask<TAB><sentence>); the folder holds files and --here is absent (used<TAB><n>,
ask<TAB><sentence>); an entry has a name hg needs (refused<TAB>name<TAB><name>, then a say line).
After the summary line: mode<TAB><mode>, project<TAB><slug><TAB><name> with --focus, the session rules as
context<TAB><line> lines in the run that created hg.json, then say<TAB><sentence> lines for the person.
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
import solo  # noqa: E402

TEMPLATE =Path(__file__).resolve().parent.parent / "templates" / "workspace"
PERSONAL_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "personal"
# What only a shared folder needs. Each would add a word or a command (/setup) to what a person sees in a personal
# folder. The CI copies (.github/hg/) are left out by the code that writes them.
SHARED_ONLY = ("AGENTS.md", "gates/README.md", ".github/", ".claude/skills/setup/SKILL.md")
# Names a personal folder must not already hold: an existing vault/ would be taken for hg's own.
NEEDED_NAMES = ("vault", "intake", "gates", "claude.md", "claude.local.md", "agents.md", "dashboard.md")
NEEDED_HIDDEN = (".gateway", ".github")
QUIET_NAMES = ("desktop.ini", "thumbs.db")
KEPT_AT_TOP = (".git", ".gitignore", ".gitattributes", ".claude")
LOCAL_RULES = "CLAUDE.local.md"
FOCUS_MAX = 80

# What the person reads, in the content language. Model-facing lines stay English.
SAY = {
    "pl": {
        "S1": "Gotowe. Ten folder jest teraz Twoim miejscem na notatki i ustalenia. hg zapisuje wszystko w tym folderze "
              "i nikomu tego nie przekazuje.",
        "S1b": "Ten folder leży w miejscu, które ten komputer kopiuje do chmury. Twoje notatki też tam trafią.",
        "S3": "Temat zapisany: {name}.",
        "S4": "Co możesz teraz zrobić: wklej notatkę albo link i napisz „zapisz”. Zapytaj „co wiemy o…”. "
              "Napisz „co mam dziś”.",
        "S5": "Powiedz mi, jak mam z Tobą pracować, a zapiszę to w Twoich zasadach.",
        "S6": "hg nie robi kopii tych notatek. Jeśli stracisz ten komputer, stracisz je.",
        "S7": "W tym folderze są już pliki ({n}). Założyć tu miejsce na notatki? Istniejących plików nie zmienię.",
        "S7e": "W tym folderze są już pliki ({n}). Założyć tu miejsce na notatki?",
        "S7d": "W tym folderze jest już „{name}”, a tej nazwy potrzebuje hg. Wybierz inny folder, najlepiej nowy i pusty.",
        "S9": "Ten folder leży wewnątrz innego folderu, który ma własną historię zmian. Wybierz na notatki folder poza "
              "nim, na przykład nowy folder w Dokumentach.",
        "S9b": "Ten folder ma już własną historię zmian. Wybierz na notatki inny folder, na przykład nowy folder w "
               "Dokumentach.",
        "S10": "Masz już miejsce na notatki w folderze {path}. Założyć drugie tutaj?",
        "rules": "# Moje zasady dla Claude'a\n\nTu są zasady, które podałeś Claude'owi dla tego folderu. Możesz je też "
                 "dopisać ręcznie, zwykłymi zdaniami.\n",
    },
    "en": {
        "S1": "Done. This folder is now your place for notes and decisions. hg keeps everything in this folder and "
              "sends it nowhere.",
        "S1b": "This folder lies in a place this computer copies to the cloud. Your notes will go there too.",
        "S3": "Topic saved: {name}.",
        "S4": "What you can do now: paste a note or a link and write \"keep this\". Ask \"what do we know about…\". "
              "Write \"what is on today\".",
        "S5": "Tell me how I should work with you, and I will write it into your rules.",
        "S6": "hg makes no copy of these notes. If you lose this computer, you lose them.",
        "S7": "This folder already holds files ({n}). Set up the place for notes here? I will not change the files "
              "that are here.",
        "S7e": "This folder already holds files ({n}). Set up the place for notes here?",
        "S7d": "This folder already holds \"{name}\", and hg needs that name. Pick another folder, best a new and "
               "empty one.",
        "S9": "This folder lies inside another folder that keeps its own change history. Pick a folder outside it "
              "for your notes, for example a new folder in Documents.",
        "S9b": "This folder already keeps its own change history. Pick another folder for your notes, for example a "
               "new folder in Documents.",
        "S10": "You already have a place for notes in the folder {path}. Set up a second one here?",
        "rules": "# My rules for Claude\n\nHere are the rules you gave Claude for this folder. You can also add them "
                 "by hand, in plain sentences.\n",
    },
}
NO_HISTORY = "no change history was started here. Nothing in this folder needs it today."
TOOLS = Path(__file__).resolve().parent
CI_TOOLS = ("scan.py", "notify.py", "gate.py", "canonicalize.py", "kit_registry.py")
CI_DIR = ".github/hg"
WORKFLOWS = (".github/workflows/hg-scan.yml", ".github/workflows/hg-notify.yml")
TOKEN_FILES = {"CLAUDE.md", "AGENTS.md"}
MARKETPLACE = "human-gateway"
SETTINGS = ".claude/settings.json"
FORBIDDEN_PATHS = ["vault/raw/", "gates/", ".obsidian/"]
NOTIFY_WORKFLOW = ".github/workflows/hg-notify.yml"
OLD_SECRET = "secrets.HG_" "SLACK_WEBHOOK_URL"  # what hg-notify.yml of an earlier release passes; in two pieces on purpose


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
    """Append the rules missing from permissions.allow, .ask and .deny. Returns how many were added."""
    permissions = have.setdefault("permissions", {})
    if not isinstance(permissions, dict):
        report.line("note", "%s: permissions is not an object, so it was left as it is and no rule was added" % SETTINGS)
        return 0
    added = 0
    for kind in ("allow", "ask", "deny"):
        if not want["permissions"].get(kind):
            continue
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


def shared_only(rel):
    return any(rel == item or (item.endswith("/") and rel.startswith(item)) for item in SHARED_ONLY)


def template_files(personal):
    """[(repo-relative path, source file)]: the workspace template, and for a personal folder the overlay's text in
    place of the workspace text and nothing from SHARED_ONLY."""
    files = {}
    for src in sorted(TEMPLATE.rglob("*")):
        if src.is_file() and "__pycache__" not in src.parts:
            files[src.relative_to(TEMPLATE).as_posix()] = src
    if personal:
        files = {rel: src for rel, src in files.items() if not shared_only(rel)}
        for src in sorted(PERSONAL_TEMPLATE.rglob("*")):
            if src.is_file() and "__pycache__" not in src.parts:
                files[src.relative_to(PERSONAL_TEMPLATE).as_posix()] = src
    return sorted(files.items())


def with_ask(text, rules):
    data = json.loads(text)
    ask = data.setdefault("permissions", {}).setdefault("ask", [])
    ask.extend(rule for rule in rules if rule not in ask)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def copy_template(root, args, report, personal=False):
    tokens = {"{{PROJECT_NAME}}": args.name, "{{CONTENT_LANGUAGE}}": args.language}
    for rel, src in template_files(personal):
        if rel == ".gitignore" and (root / rel).is_file():
            extend_gitignore(root, report)
            continue
        text = src.read_text(encoding="utf-8")
        if rel in TOKEN_FILES:
            text = fill(text, tokens)
        elif rel == SETTINGS and args.marketplace:
            text = with_marketplace(text, args.marketplace)
        if rel == SETTINGS and personal:
            text = with_ask(text, solo.PERSONAL_ASK)
        if rel == SETTINGS and (root / rel).is_file():
            extend_settings(root, text, report)
            continue
        create(root, rel, text, report)


def write_config(root, args, report, personal=False):
    config = {"schemaVersion": kr.EXPECTED_SCHEMA_VERSION}
    if personal:
        config["mode"] = "personal"
    config.update({
        "projectName": args.name,
        "projects": [args.project] if args.project else [],
        "timezone": args.timezone,
        "language": {"content": args.language, "infra": kr.DEFAULTS["INFRA_LANGUAGE"]},
        "forbiddenWritePaths": FORBIDDEN_PATHS,
        "neverInGit": {"extra": []},
        "scan": {"allow": {"emails": [], "domains": []}, "patterns": {}},
        "publish": {"words": [], "quoteWords": 12, "off": []},
    })
    create(root, "/".join(kr.CONFIG_PARTS), json.dumps(config, indent=2, ensure_ascii=False) + "\n", report)


def add_project(root, args, report, slug=None, name=None, listed=False):
    """vault/projects/<slug>/ from the folder's own _template. With listed, the slug is also appended to projects
    in hg.json (hg-tool setup --focus); otherwise an unlisted slug gets a note."""
    slug = slug or args.project
    conf = kr.load_conf(root)
    vault = conf["VAULT_DIR"].strip("/")
    template = root / vault / "projects" / "_template"
    if not template.is_dir():
        report.line("error", "%s/projects/_template is missing" % vault)
        return
    values = {"__SLUG__": slug, "__NAME__": name or slug.replace("-", " ").title(),
              "__DATE__": kr.local_now(conf["TIMEZONE"]).date().isoformat()}
    for src in sorted(template.rglob("*")):
        if src.is_file():
            rel = "%s/projects/%s/%s" % (vault, slug, src.relative_to(template).as_posix())
            create(root, rel, fill(src.read_text(encoding="utf-8"), values), report)
    if slug in kr.projects(conf):
        return
    if listed:
        import conf_set  # imported here: only --focus needs it
        problem = conf_set.append_project(root.joinpath(*kr.CONFIG_PARTS), slug)
        if problem:
            report.line("error", problem)
        else:
            report.line("updated", "/".join(kr.CONFIG_PARTS))
    else:
        report.line("note", "add \"%s\" to projects with: hg-tool conf-set project %s" % (slug, slug))


def git_out(root, *args):
    try:
        return subprocess.run(["git", "-c", "core.quotepath=off"] + list(args), cwd=str(root), capture_output=True)
    except OSError:
        return None


def untrack_placeholders(root, report):
    """Take the tracked, empty vault/raw/<slug>/<kind>/.gitkeep of an earlier release out of the index, once the
    folder is ignored. Nothing else under vault/raw/ is touched."""
    vault = kr.load_conf(root)["VAULT_DIR"].replace("\\", "/").strip("/")
    listed = git_out(root, "ls-files", "-z", "--full-name", "--", "%s/raw" % vault)
    if listed is None or listed.returncode != 0:
        return
    shape = re.compile(re.escape(vault) + r"/raw/[a-z0-9-]+/(?:%s)/\.gitkeep" % "|".join(kr.RAW_KINDS))
    for rel in sorted(p for p in listed.stdout.decode("utf-8", "replace").split("\0") if shape.fullmatch(p)):
        size = git_out(root, "cat-file", "-s", ":" + rel)
        ignored = git_out(root, "check-ignore", "-q", "--no-index", "--", rel)
        if size is None or size.stdout.strip() != b"0" or ignored is None or ignored.returncode != 0:
            continue
        done = git_out(root, "--literal-pathspecs", "rm", "--cached", "-q", "--", rel)
        if done is not None and done.returncode == 0:
            report.line("untracked", rel)
        else:
            report.line("error", "%s: git rm --cached failed" % rel)


def refresh_ci(root):
    """Replace the five copies CI runs, create a missing workflow, replace an earlier release's notify workflow, add
    the missing .gitignore lines and untrack the old placeholders. One line per file."""
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
        text = (TEMPLATE / rel).read_text(encoding="utf-8")
        dest = root / rel
        try:
            old = rel == NOTIFY_WORKFLOW and dest.is_file() and OLD_SECRET in dest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            old = False
        if not old:
            create(root, rel, text, report)
            continue
        try:
            gate.write_atomic(dest, text)
        except OSError as exc:
            report.line("error", "%s: %s" % (rel, exc))
        else:
            report.line("updated", rel)
    if (root / ".gitignore").is_file():
        extend_gitignore(root, report)
    untrack_placeholders(root, report)
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


def personal_git_init(root, report):
    """A personal folder uses git silently when it is there: git init at the folder when it has no repository of its
    own. A missing git or a failed init is a note, not an error: nothing in a personal folder needs git today."""
    if solo.repo_dir(root) is not None:
        report.line("skipped", ".git")
        return
    if not solo.git_usable():
        report.line("note", NO_HISTORY)
        return
    try:
        done = subprocess.run(["git", "init", "-b", "main", str(root)], capture_output=True, encoding="utf-8",
                              errors="replace")
    except OSError:
        report.line("note", NO_HISTORY)
        return
    if done.returncode == 0:
        report.line("created", ".git")
    else:
        report.line("note", NO_HISTORY)


def auto_language():
    """pl when the environment's locale or, on Windows, the user-interface language is Polish, else en."""
    for name in ("LC_ALL", "LANG", "LANGUAGE"):
        if os.environ.get(name, "").lower().startswith("pl"):
            return "pl"
    if os.name == "nt":
        try:
            import ctypes
            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x15:
                return "pl"
        except Exception:
            pass
    return "en"


def top_entries(root):
    """The names at the top of the folder, sorted; [] when it does not exist yet."""
    try:
        return sorted(p.name for p in Path(root).iterdir())
    except OSError:
        return []


def say_text(language):
    return SAY["pl" if str(language).lower().startswith("pl") else "en"]


def has_history(root):
    """The folder is a repository of its own with at least one commit. Asked only when git is usable."""
    if solo.repo_dir(root) is None or not solo.git_usable():
        return False
    head = git_out(root, "rev-parse", "-q", "--verify", "HEAD")
    return head is not None and head.returncode == 0


def refuse_personal(root, args):
    """The five cases in which a new personal folder is not created. Returns (exit code, kept names) and prints the
    lines; exit None means go on. Nothing is created here."""
    t = say_text(args.language)
    if solo.repo_above(root) is not None:
        print("inside")
        print("say\t%s" % t["S9"])
        return 1, []
    if has_history(root):  # its commits, and perhaps a remote, would carry the notes away
        print("refused\thistory")
        print("say\t%s" % t["S9b"])
        return 1, []
    if not args.new:
        others = solo.places(exclude=root)
        if others:
            print("place\t%s" % others[0])
            print("ask\t%s" % t["S10"].format(path=others[0]))
            return 1, []
    names = top_entries(root)
    for name in names:
        low = name.casefold()
        if low in NEEDED_NAMES or low in NEEDED_HIDDEN:
            print("refused\tname\t%s" % name)
            print("say\t%s" % t["S7d"].format(name=today_inline(name)))
            return 1, []
    used = [n for n in names if not n.startswith(".") and n.casefold() not in QUIET_NAMES]
    if used and not args.here:
        print("used\t%d" % len(used))
        # .gitignore and .claude/settings.json get hg's lines added, so the promise to change no file is left out
        changed = any((root / rel).is_file() for rel in (".gitignore", SETTINGS))
        print("ask\t%s" % t["S7e" if changed else "S7"].format(n=len(used)))
        return 1, []
    return None, [n for n in names if n not in KEPT_AT_TOP]


def today_inline(text):
    import today_data  # imported here: only a refusal needs it
    return today_data.inline(text)


def parse(argv):
    parser = argparse.ArgumentParser(prog="hg-tool setup", allow_abbrev=False)
    parser.add_argument("--root")
    parser.add_argument("--name")
    parser.add_argument("--language", default=kr.DEFAULTS["CONTENT_LANGUAGE"])
    parser.add_argument("--timezone")
    parser.add_argument("--marketplace")
    parser.add_argument("--project")
    parser.add_argument("--refresh-ci", "--refresh-scan", dest="refresh_ci", action="store_true")
    parser.add_argument("--personal", action="store_true")
    parser.add_argument("--focus")
    parser.add_argument("--here", action="store_true")
    parser.add_argument("--new", action="store_true")
    args = parser.parse_args(argv)
    if args.name is not None and (not args.name.strip() or "\n" in args.name):
        parser.error("--name must be one non-empty line")
    if args.language == "auto":
        args.language = auto_language()
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*", args.language):
        parser.error("--language must be a language code such as pl or en")
    if args.timezone is not None and not re.fullmatch(r"[A-Za-z0-9_+./-]+", args.timezone):
        parser.error("--timezone must be a zone name such as Europe/Warsaw")
    if args.focus is not None:
        args.focus = " ".join(args.focus.split())[:FOCUS_MAX].strip()
        if not args.focus:
            parser.error("--focus must hold some words")
    if (args.focus is not None or args.here or args.new) and not args.personal:
        parser.error("--focus, --here and --new go with --personal")
    if args.personal and args.refresh_ci:
        parser.error("--refresh-ci does not go with --personal")
    if args.marketplace and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.marketplace):
        parser.error("--marketplace must look like owner/repo")
    if args.project and not kr.valid_project_slug(args.project):
        parser.error("--project must be a kebab-case slug of at most 40 characters, and not cross or unknown")
    return args


def refresh_personal(root):
    """--refresh-ci in a personal folder: no copies for CI, only the missing .gitignore lines."""
    report = Report()
    if (root / ".gitignore").is_file():
        extend_gitignore(root, report)
    return 1 if report.errors else 0


def main(argv):
    kr.stdio_utf8()
    args = parse(argv)
    if args.personal and not args.root and not os.environ.get("CLAUDE_PROJECT_DIR"):
        # The folder the person opened, never the top of a repository it lies in: that is refused below (S9). Set for
        # everything this run calls, so nothing asks git for the root.
        os.environ["CLAUDE_PROJECT_DIR"] = os.getcwd()
    root = kr.kit_root(native_root(args.root) if args.root else None)
    config_path = root.joinpath(*kr.CONFIG_PARTS)
    if args.refresh_ci:
        return refresh_personal(root) if solo.is_personal(root) else refresh_ci(root)
    existed = config_path.is_file()
    personal = solo.is_personal(root) if existed else args.personal
    if args.focus and existed and not personal:
        # A shared folder's projects are tracked and go out with the next publication: never from a person's words.
        print("note\t--focus adds a project only in a personal folder. This folder is shared, so none was added.")
        args.focus = None
    kept = []
    if personal and not existed:
        code, kept = refuse_personal(root, args)
        if code is not None:
            return code
    args.name = args.name or root.name
    if args.timezone is None:
        args.timezone = "local" if personal and not existed else kr.DEFAULTS["TIMEZONE"]
    report = Report()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        report.line("error", "%s: %s" % (root, exc))
        return 1
    copy_template(root, args, report, personal)
    write_config(root, args, report, personal)
    created = not existed and config_path.is_file()
    if personal:
        create(root, LOCAL_RULES, say_text(kr.load_conf(root)["CONTENT_LANGUAGE"])["rules"], report)
        create(root, "/".join(solo.PERSONAL_MARK), solo.MARK_TEXT, report)
    else:
        for name in CI_TOOLS:
            create(root, "%s/%s" % (CI_DIR, name), (TOOLS / name).read_text(encoding="utf-8"), report)
    if args.project:
        add_project(root, args, report)
    focus = None
    if args.focus:
        focus = (solo.slugify(args.focus), args.focus)
        add_project(root, args, report, slug=focus[0], name=focus[1], listed=True)
    if personal:
        personal_git_init(root, report)
        if solo.repo_dir(root) is not None and solo.git_usable():
            untrack_placeholders(root, report)
            if created and kept:
                _, skipped = solo.write_exclude(root, kept)
                for name in skipped:
                    report.line("note", "a name at the top of this folder holds a line break and was not kept out of git")
        if created:
            solo.remember_place(root)
    else:
        git_init(root, report)
        untrack_placeholders(root, report)
    print("setup: %d created, %d skipped, %d errors in %s" % (report.created, report.skipped, report.errors, root.as_posix()))
    if args.personal or personal:
        say_personal(root, args, created, personal, focus)
    return 1 if report.errors else 0


def say_personal(root, args, created, personal, focus):
    """The mode line, the session rules as context lines when this run created hg.json, then what the person reads."""
    print("mode\t%s" % ("personal" if personal else "shared"))
    if focus:
        print("project\t%s\t%s" % focus)
    if not personal:
        return
    if created:
        import session_start  # imported here: only the run that creates hg.json prints the rules
        for line in session_start.block(root).splitlines():
            print("context\t%s" % line)
    t = say_text(kr.load_conf(root)["CONTENT_LANGUAGE"])
    synced = solo.sync_root(root) and (created or focus)
    lines = []
    if created:
        lines.append(t["S1"])
    if synced:
        lines.append(t["S1b"])
    if focus:
        lines += [t["S3"].format(name=today_inline(focus[1])), t["S4"], t["S5"]]
        if not synced:
            lines.append(t["S6"])
    for line in lines:
        print("say\t%s" % line)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
