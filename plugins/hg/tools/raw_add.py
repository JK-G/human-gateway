#!/usr/bin/env python3
"""raw_add.py - the one writer of vault/raw/. Bring one file in, scanned, under its permanent name.

Usage: hg-tool raw-add <file> --project <slug> --kind <kind> --date YYYY-MM-DD --slug <slug>
  <file>     a regular file in intake/ or vault/inbox/, relative to the repo root or absolute as D:\\x, D:/x or /d/x
  --project  a slug from projects in .claude/hg.json, or cross
  --kind     meetings, interviews, sources or snapshots
  --date     the day the source was created
  --slug     lower-case letters, digits and hyphens

The destination is vault/raw/<project>/<kind>/<date>-<slug><ext>, with the suffix lower-cased and .txt becoming
.md. It is printed as a repo-relative path. The file is moved, not copied.

vault/raw/ is a person's own folder: it stays on this computer, outside git, with no backup and no history. So
the tool refuses when git does not ignore the destination (or the folder is not a repository), and refuses a
source that git tracks: a raw file is never in git. Pages cite a raw file by the reference hg-tool raw-ref prints.

Only the two folders where files wait to be brought in are accepted, so the tool cannot take away a gate record,
the journal, the log or the repo's settings.

The file goes through the same scan as hg-tool scan. The scan no longer protects git, because raw never reaches
git. It keeps a known secret out of the material a model reads and rewrites: a secret, or a file that holds
secrets (.pem, .env), stops the move and is printed masked. Contact data in a person's own file is expected, so
it is counted in a note on stderr, never printed. A file people usually work on elsewhere (a spreadsheet, a Word
file) moves with a note. A binary file the scan could not read moves and is noted, because the skill has the agent
look through it.

An existing destination is never overwritten: the file takes the name by exclusive create before os.replace puts
it there.

Claude Code's permissions.deny on vault/raw/ also stops its own mkdir and mv, which is why this tool exists.
Exit: 0 ok, 1 refused (a value that is not allowed, or a refused file; nothing moved), 2 usage error.

In a personal folder (solo.py) with no repository of its own, or with no git on this computer, hg can commit
nothing there, so the rule that git must ignore the destination does not apply and git is not asked.

hg-tool raw-add --check says whether the private folders stay private here: private<TAB>yes, exit 0, or
private<TAB>no<TAB><path>, exit 1. /hg:init runs it instead of typing git check-ignore -q intake/x itself.
"""
import datetime
import os
import re
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402
import scan  # noqa: E402

KINDS = ("meetings", "interviews", "sources", "snapshots")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # fromisoformat alone takes other shapes from Python 3.11
SUFFIX_RE = re.compile(r"\.[a-z0-9]+")
REQUIRED = ("--project", "--kind", "--date", "--slug")


def check_values(opts, conf):
    project, kind, date, slug = (opts[flag] for flag in REQUIRED)
    allowed = kr.projects(conf) + ["cross"]
    if project not in allowed:
        raise gate.Refused("unknown project '%s'. Use one of: %s." % (project, ", ".join(allowed)))
    if kind not in KINDS:
        raise gate.Refused("unknown kind '%s'. Use one of: %s." % (kind, ", ".join(KINDS)))
    try:
        if not DATE_RE.fullmatch(date):
            raise ValueError
        datetime.date.fromisoformat(date)
    except ValueError:
        raise gate.Refused("--date must be a real date written YYYY-MM-DD, not '%s'." % date)
    if not SLUG_RE.fullmatch(slug):
        raise gate.Refused("--slug uses lower-case letters, digits and hyphens, and starts with a letter or digit.")


def source_of(root, raw, raw_parts):
    """The real path of the file to bring in and its repo-relative form. Checks only: nothing is read or moved."""
    given = Path(scan.native_path(raw.strip()))
    candidate = given if given.is_absolute() else root / given
    if os.path.islink(str(candidate)):  # looked at before resolve(), which would follow it
        raise gate.Refused("%s is a symbolic link. Bring in the file itself." % raw)
    full = candidate.resolve()
    try:
        rel = full.relative_to(root)
    except ValueError:
        raise gate.Refused("%s is outside this repository." % raw)
    folded = [part.casefold() for part in rel.parts]
    if ".git" in folded:
        raise gate.Refused("%s is inside .git." % raw)
    if folded[:len(raw_parts)] == raw_parts:
        raise gate.Refused("%s is already inside vault/raw/, where files never change." % raw)
    inbox = raw_parts[:-1] + ["inbox"]  # raw_parts is <vault>/raw
    if folded[:1] != ["intake"] and folded[:len(inbox)] != inbox:
        raise gate.Refused("%s is not in intake/ or %s/. Only a file waiting in one of those two can be brought in."
                           % (raw, "/".join(inbox)))
    try:
        regular = stat.S_ISREG(os.lstat(str(full)).st_mode)
    except FileNotFoundError:
        raise gate.Refused("%s does not exist." % raw)
    if not regular:
        raise gate.Refused("%s is not a regular file." % raw)
    return full, rel.as_posix()


def destination_of(root, base, full, opts):
    suffix = full.suffix.lower()
    if suffix and not SUFFIX_RE.fullmatch(suffix):
        raise gate.Refused("the suffix '%s' cannot be part of a file name in vault/raw/." % suffix)
    name = "%s-%s%s" % (opts["--date"], opts["--slug"], ".md" if suffix == ".txt" else suffix)
    folder = base / opts["--project"] / opts["--kind"]
    try:
        folder.resolve().relative_to(base)  # a link in the way would put the file somewhere else
    except ValueError:
        raise gate.Refused("%s does not lead into vault/raw/." % folder.relative_to(root).as_posix())
    return folder / name


def taken(dest):
    """os.path.lexists also sees a dangling link."""
    return os.path.lexists(str(dest))


def git_free(root):
    """A personal folder with no repository of its own, or no git here: hg can commit nothing in it."""
    import solo  # imported here: the top-level imports of this file are tested
    return solo.is_personal(root) and (solo.repo_dir(root) is None or not solo.git_usable())


def raw_stays_private(root, rel):
    if git_free(root):
        return True
    return gate.is_ignored(root, rel)  # as before, in both modes


def is_tracked(root, rel):
    if git_free(root):
        return False
    out = gate.git(root, "ls-files", "--error-unmatch", "--", rel)
    return out is not None and out.returncode == 0


def check(root):
    """private<TAB>yes when intake/, the raw folder and the inbox stay out of git here, else the first that does not."""
    if not root.joinpath(*kr.CONFIG_PARTS).is_file():
        raise gate.Refused(".claude/hg.json is missing. Run /hg:setup.")
    vault = kr.load_conf(root)["VAULT_DIR"].strip("/")
    for rel in ("intake/x", "%s/raw/x/sources/x.md" % vault, "%s/inbox/x.md" % vault):
        if not raw_stays_private(root, rel):
            print("private\tno\t%s" % rel)
            return 1
    print("private\tyes")
    return 0


def move_untracked(full, dest):
    try:
        open(str(dest), "xb").close()
    except FileExistsError:
        raise gate.Refused("%s already exists. Raw files are never overwritten." % dest.name)
    try:
        os.replace(str(full), str(dest))
    except OSError:
        dest.unlink()
        raise


def add(root, argv):
    opts, positional = gate.parse(argv, REQUIRED)
    if len(positional) != 1:
        raise gate.Usage("give exactly one file")
    for flag in REQUIRED:
        if flag not in opts:
            raise gate.Usage("%s is required" % flag)
    config = root.joinpath(*kr.CONFIG_PARTS)
    if not config.is_file():
        raise gate.Refused(".claude/hg.json is missing. Run /hg:setup.")
    conf = kr.load_conf(root, strict=True)
    check_values(opts, conf)
    base = root.joinpath(conf["VAULT_DIR"], "raw")
    raw_parts = [part.casefold() for part in Path(conf["VAULT_DIR"], "raw").parts]
    full, rel = source_of(root, positional[0], raw_parts)
    dest = destination_of(root, base, full, opts)
    dest_rel = dest.relative_to(root).as_posix()
    if taken(dest):
        raise gate.Refused("%s already exists. Raw files are never overwritten: pick a new slug or date." % dest_rel)
    if is_tracked(root, rel):
        raise gate.Refused("%s is tracked by git. A raw source stays out of git: take it out of git first "
                           "(git rm --cached), then bring it in." % rel)
    if not raw_stays_private(root, dest_rel):  # a shared folder with no repository fails this too
        raise gate.Refused("%s/raw/ is not kept out of git in this folder, so a raw file could be committed. "
                           "Run /hg:setup, then try again." % conf["VAULT_DIR"].strip("/"))

    unread = []
    findings = scan.scan_file(str(full), rel, scan.load_config(str(config)), unread)
    secrets = [f for f in findings if f["kind"] == "secret" or (f["kind"] == "filetype" and f["value"] == "secret file")]
    if secrets:
        for item in secrets:
            print("%s:%d	%s	%s" % (item["path"], item["line"], item["kind"], item["value"]))
        raise gate.Refused("the scan found %d secret(s). Nothing moved. Take the secret out of the file, or keep the "
                           "file out." % len(secrets))
    contacts = sum(1 for f in findings if f["kind"] == "pii")
    link_only = any(f["kind"] == "filetype" and f["value"] == "link only" for f in findings)
    dest.parent.mkdir(parents=True, exist_ok=True)
    move_untracked(full, dest)
    if contacts:
        print("raw-add: note: the scan sees %d contact detail(s) in this file. It stays on this machine. None of "
              "them may reach a page." % contacts, file=sys.stderr)
    if link_only:
        print("raw-add: note: this is a file people usually work on elsewhere. It stays on this machine. A page gets "
              "a summary and, when known, the link.", file=sys.stderr)
    if unread:
        print("raw-add: note: the scan could not read %s (binary). Look through it yourself." % dest_rel, file=sys.stderr)
    return dest_rel


def main(argv):
    kr.stdio_utf8()
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if argv == ["--check"]:
            return check(kr.kit_root().resolve())
        print(add(kr.kit_root().resolve(), argv))
    except gate.Usage as exc:
        print("raw-add: %s" % exc, file=sys.stderr)
        return 2
    except (gate.Refused, kr.RegistryError) as exc:
        print("raw-add: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("raw-add: nothing moved: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
