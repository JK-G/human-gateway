#!/usr/bin/env python3
"""journal_append.py - SessionEnd hook: one line per session into the daily action journal.

  - Append-only, one line per session in <journal>/YYYY-MM-DD.md. guard_write blocks agent edits.
  - The signal is the list of paths changed in the working tree (git status), not the transcript.
    The journal itself, .obsidian and .claude/state are excluded. No names: session id and paths only.
  - Paths of published files only; new files are counted. The journal is tracked, so a draft page that the
    person later holds back or deletes must not be named to the department: a path HEAD does not have (git
    status ?? or A, and a rename or copy target) is counted as (+N new) and never written.
  - A path in a private folder (vault/raw/, vault/inbox/, vault/daily/, intake/, .gateway/) is dropped. With a
    correct .gitignore git never lists one; this holds when the .gitignore is broken.
  - Best effort: always exits 0.
  - Touches .claude/state/journal-last-run so /hg:doctor can detect a silent outage.
  - In a personal folder (solo.py) nothing is ever committed, so git status cannot tell what a session touched.
    There the signal is the pages under vault/wiki/ and vault/projects/ changed since the last run (by modification
    time, against journal-last-run, else .claude/hg.json). All count as new, so the line holds a count and no name,
    and git is not started.

stdin: the SessionEnd hook JSON (session_id, transcript_path, cwd, reason). Any garbage is fine.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402
import solo  # noqa: E402

MAX_SHOWN = 12


def session_id(raw):
    try:
        value = json.loads(raw).get("session_id")
    except (ValueError, AttributeError):
        return "unknown"
    return (value or "unknown")[:8]


def changed_paths(root, journal, conf=None):
    """[(path, is_new)] from git status, without the journal, editor state and private folders."""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "--ignore-submodules=all"],
        cwd=str(root), capture_output=True, encoding="utf-8", errors="replace").stdout
    skip = re.compile(r"^(%s/|\.claude/state/)|(^|/)\.obsidian/" % re.escape(journal))
    paths = []
    for line in out.splitlines():
        code = line[:2]
        path = line[3:].split(" -> ")[-1].replace('"', "")
        if path and not skip.search(path) and not kr.is_private(path, conf):
            paths.append((path, code == "??" or "A" in code or code[:1] in ("R", "C")))
    return paths


def personal_paths(root, conf):
    """[(path, True)] for the pages changed since the last run, without git."""
    marker = root / ".claude" / "state" / "journal-last-run"
    since_file = marker if marker.exists() else root.joinpath(*kr.CONFIG_PARTS)
    try:
        since = since_file.stat().st_mtime
    except OSError:
        since = 0.0
    vault = conf["VAULT_DIR"].strip("/")
    found = []
    for folder in ("wiki", "projects"):
        base = root / vault / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            try:
                if path.is_file() and path.stat().st_mtime > since:
                    found.append((path.relative_to(root).as_posix(), True))
            except OSError:
                continue
    return found


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
    paths = personal_paths(root, conf) if solo.is_personal(root) else changed_paths(root, journal, conf)
    named = [p for p, new in paths if not new]
    fresh = len(paths) - len(named)
    line = "- %s session %s: %d paths" % (now.strftime("%H:%M"), sid, len(paths))
    if named:
        line += ": " + ", ".join(named[:MAX_SHOWN])
        if len(named) > MAX_SHOWN:
            line += " (+%d more)" % (len(named) - MAX_SHOWN)
    if fresh:
        line += " (+%d new)" % fresh

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
