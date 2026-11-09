#!/usr/bin/env python3
"""doctor.py - health check for a department workspace and the tools it needs.

Usage: hg-tool doctor [--root DIR]
Output: LEVEL<TAB>check<TAB>message, level OK, WARN or ERROR. Exit: 0 no errors, 1 at least one ERROR.
"""
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

REQUIRED_IGNORES = ("vault/daily/", "intake/", "DASHBOARD.md", ".gateway/", ".claude/state/", ".claude/settings.local.json")
TEMPLATE_SETTINGS = Path(__file__).resolve().parent.parent / "templates" / "workspace" / ".claude" / "settings.json"
JOURNAL_STALE_DAYS = 14


class Findings:
    def __init__(self):
        self.errors = 0

    def add(self, level, check, message):
        print("%s\t%s\t%s" % (level, check, message))
        if level == "ERROR":
            self.errors += 1


def check_programs(f):
    f.add("OK", "python", "%d.%d" % sys.version_info[:2])
    for name, level, message in (
            ("git", "ERROR", "not found, every department repo needs it. Run /hg:setup."),
            ("gh", "WARN", "not found. Needed only if git cannot sign in to GitHub by itself: then run /hg:setup.")):
        if shutil.which(name):
            f.add("OK", name, "found")
        else:
            f.add(level, name, message)


def find_git_bash():
    """Claude Code's own setting first, then next to git, then the installer's default folders."""
    candidates = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH") or ""]
    git = shutil.which("git")
    if git:  # git.exe sits in Git/cmd, Git/bin or Git/mingw64/bin
        candidates += [str(parent / "bin" / "bash.exe") for parent in list(Path(git).resolve().parents)[:3]]
    for var, tail in (("ProgramFiles", "Git"), ("ProgramFiles(x86)", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        if os.environ.get(var):
            candidates.append(str(Path(os.environ[var]) / tail / "bin" / "bash.exe"))
    return next((c for c in candidates if c and Path(c).is_file()), None)


def check_git_bash(f):
    if os.name != "nt":
        return
    if find_git_bash():
        f.add("OK", "git-bash", "found")
    else:
        f.add("ERROR", "git-bash", "not found, the plugin's tools and hooks need it. Install Git for Windows or run /hg:setup.")


def check_config(f, root):
    path = root.joinpath(*kr.CONFIG_PARTS)
    if not path.is_file():
        f.add("ERROR", "config", ".claude/hg.json is missing. Run /hg:setup in this folder.")
        return None
    try:
        conf = kr.load_conf(root, strict=True)
    except kr.RegistryError as exc:
        f.add("ERROR", "config", str(exc))
        return None
    if conf["SCHEMA_VERSION"] != str(kr.EXPECTED_SCHEMA_VERSION):
        f.add("ERROR", "config", "schemaVersion %s, the plugin expects %d. Run /hg:setup --update."
              % (conf["SCHEMA_VERSION"], kr.EXPECTED_SCHEMA_VERSION))
    else:
        f.add("OK", "config", "schemaVersion %s" % conf["SCHEMA_VERSION"])
    return conf


def check_layout(f, root, conf):
    vault = root / conf["VAULT_DIR"]
    for rel in ("wiki", "raw"):
        if (vault / rel).is_dir():
            f.add("OK", "vault/" + rel, "present")
        else:
            f.add("ERROR", "vault/" + rel, "folder is missing. Run /hg:setup.")
    try:
        f.add("OK", "schema", "%d page types" % len(kr.load_registry(root, conf)["types"]))
    except kr.RegistryError as exc:
        f.add("ERROR", "schema", str(exc))


def check_gitignore(f, root):
    path = root / ".gitignore"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    missing = [entry for entry in REQUIRED_IGNORES if entry not in text]
    if missing:
        f.add("WARN", "gitignore", "not ignored yet: %s. They could reach git." % ", ".join(missing))
    else:
        f.add("OK", "gitignore", "personal and generated files are ignored")


def check_marketplace(f, root):
    try:
        data = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8-sig"))
        known = data.get("extraKnownMarketplaces") or {}
    except (OSError, ValueError, AttributeError):
        known = {}
    if isinstance(known, dict) and known.get("human-gateway"):
        f.add("OK", "marketplace", "configured in .claude/settings.json")
    else:
        f.add("WARN", "marketplace", "no marketplace in .claude/settings.json, so the next person cannot install the plugin from this repo")


def check_permissions(f, root):
    required = json.loads(TEMPLATE_SETTINGS.read_text(encoding="utf-8"))["permissions"]["deny"]
    try:
        deny = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8-sig"))["permissions"]["deny"]
    except (OSError, ValueError, KeyError, TypeError):
        deny = []
    missing = [rule for rule in required if not isinstance(deny, list) or rule not in deny]
    if missing:
        f.add("WARN", "permissions", "deny rules missing from .claude/settings.json: %s. Run hg-tool setup to add them." % ", ".join(missing))
    else:
        f.add("OK", "permissions", "deny rules are in .claude/settings.json")


def file_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_scanner(f, root):
    copy = root / ".github" / "hg" / "scan.py"
    if not copy.is_file():
        f.add("WARN", "scanner", ".github/hg/scan.py is missing, so CI cannot scan this repo. Run hg-tool setup.")
    elif file_hash(copy) != file_hash(Path(__file__).resolve().parent / "scan.py"):
        f.add("WARN", "scanner", ".github/hg/scan.py differs from the plugin's scanner. Run /hg:setup --update.")
    else:
        f.add("OK", "scanner", "the copy CI uses matches the plugin")


def check_gate_names(f, root):
    ignored = gate.ignored_gate_files(root)
    if ignored:
        f.add("WARN", "gates", "%d file(s) in gates/ ignored: the name is not a gate id" % ignored)


def check_journal(f, root):
    marker = root / ".claude" / "state" / "journal-last-run"
    if not marker.exists():
        f.add("WARN", "journal", "no session has been recorded on this machine yet")
        return
    days = (time.time() - marker.stat().st_mtime) / 86400
    if days > JOURNAL_STALE_DAYS:
        f.add("WARN", "journal", "last session recorded %d days ago, the SessionEnd hook may not be running" % days)
    else:
        f.add("OK", "journal", "recorded within %d days" % JOURNAL_STALE_DAYS)


def main(argv):
    kr.stdio_utf8()
    root = kr.kit_root(argv[1] if len(argv) == 2 and argv[0] == "--root" else None)
    f = Findings()
    check_programs(f)
    check_git_bash(f)
    conf = check_config(f, root)
    if conf:
        check_layout(f, root, conf)
        check_gitignore(f, root)
        check_marketplace(f, root)
        check_permissions(f, root)
        check_scanner(f, root)
        check_gate_names(f, root)
        check_journal(f, root)
    return 1 if f.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
