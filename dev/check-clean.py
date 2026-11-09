#!/usr/bin/env python3
"""check-clean.py - local check to run before every push.

Fails when a file that git would track, a file path or any commit's author or committer contains
a term from .local/forbidden-terms.txt. The list stays local because it names what it protects.

Exit: 0 clean, 1 at least one hit, 2 the list is missing, so nothing can be vouched for.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS_FILE = ROOT / ".local" / "forbidden-terms.txt"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, encoding="utf-8", errors="replace")


def load_terms():
    lines = TERMS_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip().casefold() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def main():
    if not TERMS_FILE.is_file():
        print("check-clean: %s is missing, nothing was checked" % TERMS_FILE, file=sys.stderr)
        return 2
    terms = load_terms()
    hits = 0
    listed = git("ls-files", "-co", "--exclude-standard").stdout.splitlines()
    for rel in listed:
        low = rel.casefold()
        for term in terms:
            if term in low:
                print("PATH  %s  (%s)" % (rel, term))
                hits += 1
        path = ROOT / rel
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_bytes().decode("utf-8", "ignore").splitlines(), 1):
            low = line.casefold()
            for term in terms:
                if term in low:
                    print("TEXT  %s:%d  (%s)" % (rel, number, term))
                    hits += 1
    log = git("log", "--all", "--format=%h %an %ae %cn %ce")
    commits = log.stdout.splitlines() if log.returncode == 0 else []
    for entry in commits:
        low = entry.casefold()
        for term in terms:
            if term in low:
                print("GIT   %s  (%s)" % (entry.split()[0], term))
                hits += 1
    print("check-clean: %d files, %d commits, %d hits" % (len(listed), len(commits), hits))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
