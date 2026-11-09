#!/usr/bin/env python3
r"""guard_write.py - PreToolUse hook (matcher: Write|Edit|MultiEdit|NotebookEdit).

Contract: stdin is the hook JSON ({"tool_name":"Edit","tool_input":{"file_path":"..."},"cwd":"..."}).
Exit 0 = allow. Exit 2 = block, and stderr goes to the model. Only exit 2 blocks in PreToolUse.

Blocks when the target, relative to the workspace root, falls under:
  - forbiddenWritePaths from .claude/hg.json (a prefix starting with "." matches at any depth).
    Exception: <vault>/raw/ is append-only, so the Write tool may CREATE a new file there.
  - the journal folder, except its README.md (HG_ALLOW_JOURNAL_WRITE=1 for a human repair).
  - .claude/settings.local.json and .claude/state/.

Paths come in the shapes D:\x, D:/x, /d/x (Git Bash) and /x (macOS, Linux). All are normalized
before matching, and on Windows the comparison ignores case. Paths outside the root pass.
Fails open (exit 0) when the payload cannot be parsed.
Human escape hatch: HG_GUARD_BYPASS=1 in the environment that launched Claude Code.
"""
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402

WIN = os.name == "nt"


def canon(path):
    """On Windows turn every path shape into D:/x. Elsewhere leave it alone."""
    if not WIN:
        return path
    p = path.replace("\\", "/")
    m = re.match(r"^/([A-Za-z])(?=/|$)", p)
    return m.group(1) + ":" + p[2:] if m else p


def normalize(path, cwd):
    """Absolute path with . and .. collapsed."""
    p = canon(path)
    if not (p.startswith("/") or re.match(r"^[A-Za-z]:/", p)):
        p = canon(cwd).rstrip("/") + "/" + p
    drive = ""
    m = re.match(r"^[A-Za-z]:", p)
    if m:
        drive, p = m.group(0), p[2:]
    out = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
        else:
            out.append(seg)
    return drive + "/" + "/".join(out)


def fold(s):
    return s.casefold() if WIN else s


def root_forms(root):
    """The root as given and as resolved: macOS reports /private/var for /var."""
    forms = {normalize(str(root), "/"), normalize(os.path.realpath(str(root)), "/")}
    given = os.environ.get("CLAUDE_PROJECT_DIR")
    if given:
        forms.add(normalize(given, "/"))
    return forms


def relative(abs_path, roots):
    low = fold(abs_path)
    for root in roots:
        trimmed = root.rstrip("/")
        if low.startswith(fold(trimmed) + "/"):
            return abs_path[len(trimmed) + 1:]
    return None


def under(rel, prefix):
    r, p = fold(rel), fold(prefix)
    if fnmatch.fnmatchcase(r + "/", p + "*"):
        return True
    return p.startswith(".") and fnmatch.fnmatchcase("/" + r + "/", "*/" + p + "*")


def deny(tool, rel, why):
    print("BLOCKED by guard-write: %s to '%s' is not allowed (%s)." % (tool, rel, why), file=sys.stderr)
    print("If this change is genuinely needed, stop and ask the person.", file=sys.stderr)
    return 2


def main():
    kr.stdio_utf8()
    if os.environ.get("HG_GUARD_BYPASS") == "1":
        return 0
    try:
        payload = json.loads(sys.stdin.buffer.read(1048576).decode("utf-8", "replace"))
        tool_input = payload.get("tool_input") or {}
        tool = payload.get("tool_name") or "write"
        target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        cwd = payload.get("cwd") or ""
    except (ValueError, AttributeError):
        return 0
    if not target or target.startswith("~"):
        return 0

    root = kr.kit_root()
    conf = kr.load_conf(root)
    rel = relative(normalize(target, cwd or str(root)), root_forms(root))
    if rel is None:
        return 0

    journal = conf["JOURNAL_DIR"].rstrip("/")
    if fold(rel) != fold(journal + "/README.md") and fold(rel).startswith(fold(journal + "/")):
        if os.environ.get("HG_ALLOW_JOURNAL_WRITE") != "1":
            return deny(tool, rel, "the journal is append-only and written only by the SessionEnd hook")
    if fold(rel) == ".claude/settings.local.json":
        return deny(tool, rel, "settings.local.json belongs to the person")
    if fold(rel).startswith(".claude/state/"):
        return deny(tool, rel, ".claude/state/ is written only by the plugin's tools")

    raw_prefix = conf["VAULT_DIR"].rstrip("/") + "/raw/"
    for prefix in conf["FORBIDDEN_WRITE_PATHS"].split():
        if not under(rel, prefix):
            continue
        if prefix == raw_prefix and tool == "Write" and not (root / rel).exists():
            return 0
        return deny(tool, rel, "protected prefix '%s'" % prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
