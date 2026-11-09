#!/usr/bin/env python3
"""journal_append.py - SessionEnd hook: one line per session into the daily action journal.

  - Append-only, one line per session in <journal>/YYYY-MM-DD.md. guard_write blocks agent edits.
  - The signal is the list of paths changed in the working tree (git status), not the transcript.
    The journal itself, .obsidian and .claude/state are excluded. No names: session id and paths only.
  - Best effort: always exits 0.
  - Touches .claude/state/journal-last-run so /hg:doctor can detect a silent outage.

stdin: the SessionEnd hook JSON (session_id, transcript_path, cwd, reason). Any garbage is fine.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402

MAX_SHOWN = 12


def session_id(raw):
    try:
        value = json.loads(raw).get("session_id")
    except (ValueError, AttributeError):
        return "unknown"
    return (value or "unknown")[:8]


def changed_paths(root, journal):
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=all"],
        cwd=str(root), capture_output=True, encoding="utf-8", errors="replace").stdout
    skip = re.compile(r"^(%s/|\.claude/state/)|(^|/)\.obsidian/" % re.escape(journal))
    paths = []
    for line in out.splitlines():
        path = line[3:].split(" -> ")[-1].replace('"', "")
        if path and not skip.search(path):
            paths.append(path)
    return paths


def run():
    root = kr.kit_root()
    if not root.is_dir():
        return
    conf = kr.load_conf(root)
    journal = conf["JOURNAL_DIR"].rstrip("/")
    now = kr.local_now(conf["TIMEZONE"])
    day_file = root / journal / (now.strftime("%Y-%m-%d") + ".md")
    state = root / ".claude" / "state"
    day_file.parent.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)

    sid = session_id(sys.stdin.buffer.read(65536).decode("utf-8", "replace"))
    paths = changed_paths(root, journal)
    line = "- %s session %s: %d paths" % (now.strftime("%H:%M"), sid, len(paths))
    if paths:
        line += ": " + ", ".join(paths[:MAX_SHOWN])
        if len(paths) > MAX_SHOWN:
            line += " (+%d more)" % (len(paths) - MAX_SHOWN)

    if not day_file.exists():
        header = "# Journal %s\n\n_Append-only. Written by the SessionEnd hook. Do not hand-edit._\n\n" % now.strftime("%Y-%m-%d")
        with open(day_file, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(header)
    with open(day_file, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")
    (state / "journal-last-run").touch()


def main():
    try:
        run()
    except Exception:  # a journal outage must never disturb the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
