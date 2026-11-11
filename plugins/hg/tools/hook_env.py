#!/usr/bin/env python3
"""hook_env.py - read the guard-bash hook payload and print shell assignments for it.

Prints CMD, CWD, ROOT_NATIVE, FORBIDDEN_WRITE_PATHS and VAULT_DIR, each quoted with shlex, for guard-bash.sh
to eval. Values are data from the payload and .claude/hg.json; nothing from the repo runs as code.
An unreadable payload leaves CMD empty, and guard-bash then fails open.
"""
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402


def main():
    command = cwd = ""
    try:
        payload = json.loads(sys.stdin.buffer.read(262144).decode("utf-8", "replace"))
        command = (payload.get("tool_input") or {}).get("command") or ""
        cwd = payload.get("cwd") or ""
    except (ValueError, AttributeError):
        pass
    root = kr.kit_root()
    conf = kr.load_conf(root)
    pairs = [("CMD", command), ("CWD", cwd), ("ROOT_NATIVE", str(root)),
             ("FORBIDDEN_WRITE_PATHS", conf["FORBIDDEN_WRITE_PATHS"]), ("VAULT_DIR", conf["VAULT_DIR"])]
    text = "".join("%s=%s\n" % (name, shlex.quote(value)) for name, value in pairs)
    sys.stdout.buffer.write(text.encode("utf-8", "replace"))  # a lone surrogate becomes ?, never an empty CMD
    return 0


if __name__ == "__main__":
    sys.exit(main())
