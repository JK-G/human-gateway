#!/usr/bin/env python3
r"""guard_ps.py - PreToolUse hook (matcher: PowerShell). A coarse guard for the second shell.

Contract: stdin is the hook JSON ({"tool_input":{"command":"..."},"cwd":"..."}).
Exit 0 = allow. Exit 2 = block, and stderr goes to the model. Only exit 2 blocks in PreToolUse.

In the Claude desktop app on Windows the PowerShell tool is the primary shell and the Bash tool is the second one.
guard-bash.sh reads a Bash command token by token. Nothing here parses PowerShell, so this guard works on the text
of the command and stops more than it has to:

  1. A command that starts hg-tool or bash. hg-tool is a bash script, and in PowerShell `bash` can be the Windows
     one (WSL), which sees other files and another Python. The Bash tool is the place for both.
  2. A command that names a protected folder (forbiddenWritePaths from .claude/hg.json: vault/raw/, gates/, ...),
     as a path with either kind of slash. A read is stopped too, because a read and a write cannot be told apart
     here. The Read tool and the Bash tool stay open for it.
  3. The git forms guard-bash stops in a workspace: git add --force, git clean -x, git stash --all and
     git update-index, and in a personal folder the commands that record or send changes. In a shared folder
     git commit and git push pass, as they do in the Bash tool.

What it does not see: a path built from variables, a folder reached by cd first, an alias, a script file. It is a
heuristic against honest mistakes, not a sandbox. Fails open (exit 0) when the payload cannot be parsed.
Human escape hatch: HG_GUARD_BYPASS=1 in the environment that launched Claude Code.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402
import solo  # noqa: E402

FLAGS = re.I | re.M
# A statement starts at the start of a line or after ; | & ( { and may open with the call operator &.
# The program may be bare, a path without spaces, or a quoted path. Only the command position counts: a path that is
# merely read (Get-Content .../bin/hg-tool) passes.
START = r"(?:^|[;|&({])[ \t]*(?:&[ \t]*)?(?:[\"'][^\"'\n]*/|[\"']|[\w:.~-]*/(?:[\w.~-]+/)*)?"
END = r"(?:\.exe)?[\"']?(?=[ \t;|&)}]|$)"
RUNS_SHELL = re.compile(START + r"(?:bash|hg-tool)" + END, FLAGS)
GIT = re.compile(START + r"git" + END + r"([^;|&\n)}]*)", FLAGS)
SENDS = {"commit", "push", "pull", "merge", "rebase", "cherry-pick", "am", "revert", "remote"}

USE_BASH = ("hg-tool and bash are started with the Bash tool, not the PowerShell tool. In PowerShell, bash can be a "
            "different program that sees other files. Run the same command with the Bash tool.")
FORCE_ADD = "git add --force would put a file into git that this workspace keeps out on purpose."
CLEAN = ("git clean -x deletes files that are kept out of git, such as a person's source files and daily notes. "
         "They have no other copy.")
STASH = ("git stash --all moves files that are kept out of git into a stash and deletes them from this folder. "
         "A person's source files have no other copy.")
UPDATE_INDEX = "git update-index can put a file into git that this workspace keeps out on purpose."
PERSONAL = ("in a personal folder git commands that record or send changes are not run. "
            "Tell the person what you needed.")


def deny(why):
    print("BLOCKED by guard-ps: %s" % why, file=sys.stderr)
    return 2


def named_prefix(text, prefixes):
    """The first protected prefix the text names as whole path segments, or None. `text` has forward slashes."""
    for prefix in prefixes:
        body = re.escape(prefix.strip("/")).replace(r"\*", r"[^/\s\"']*")
        if body and re.search(r"(?<![\w.-])" + body + r"(?![\w.-])", text, re.I):
            return prefix
    return None


def inside(path, cwd, root):
    """True unless the path, taken from cwd, clearly lies outside the workspace."""
    try:
        target = Path(path) if os.path.isabs(path) else Path(cwd or root) / path
        target.resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False
    except OSError:
        return True


def git_reason(args, cwd, root, personal):
    """Why this git call is stopped, or None. `args` is the text after the word git."""
    words = [w.strip("\"'") for w in args.split()]
    where, i = "", 0
    while i < len(words):
        w = words[i]
        if w == "-C" and i + 1 < len(words):
            where, i = words[i + 1], i + 2
        elif w == "-c":
            i += 2
        elif w.startswith("-"):
            i += 1
        else:
            break
    if i >= len(words) or not inside(where or ".", cwd, root):
        return None
    sub, rest = words[i].lower(), []
    for w in words[i + 1:]:
        if w == "--":
            break
        rest.append(w)
    longs = [w for w in rest if w.startswith("--")]
    shorts = "".join(w[1:] for w in rest if w.startswith("-") and not w.startswith("--"))
    if personal and sub in SENDS:
        return PERSONAL
    if sub == "add" and ("f" in shorts or any(len(w) >= 3 and "--force".startswith(w) for w in longs)):
        return FORCE_ADD
    if sub == "clean" and ("x" in shorts.lower()):
        return CLEAN
    if sub == "stash" and ("a" in shorts or any(len(w) >= 3 and "--all".startswith(w) for w in longs)):
        return STASH
    if sub == "update-index":
        return UPDATE_INDEX
    return None


def main():
    kr.stdio_utf8()
    if os.environ.get("HG_GUARD_BYPASS") == "1":
        return 0
    try:
        payload = json.loads(sys.stdin.buffer.read(262144).decode("utf-8", "replace"))
        command = (payload.get("tool_input") or {}).get("command") or ""
        cwd = payload.get("cwd") or ""
    except (ValueError, AttributeError):
        return 0
    if not isinstance(command, str) or not command.strip():
        return 0
    text = command.replace("\\", "/")

    if RUNS_SHELL.search(text):
        return deny(USE_BASH)

    root = kr.kit_root()
    conf = kr.load_conf(root)
    prefix = named_prefix(text, conf["FORBIDDEN_WRITE_PATHS"].split())
    if prefix:
        return deny("this PowerShell command names '%s', a protected folder. A PowerShell command cannot be checked "
                    "well enough here to tell a read from a write. To read a file there use the Read tool; for "
                    "anything else use the Bash tool. If a change there is really needed, ask the person." % prefix)

    personal = solo.is_personal(root)
    for found in GIT.finditer(text):
        why = git_reason(found.group(1), cwd, str(root), personal)
        if why:
            return deny(why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
