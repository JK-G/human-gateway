#!/usr/bin/env python3
"""words.py - the words that must not appear in what a personal folder shows a person (spec 4.9).

Usage: words.py <file> [<allowed pattern>,...]
  Prints line<TAB>pattern<TAB>match for every hit and exits 1 when there is one, else 0. A pattern named after the
  file (exactly as written in WORDS, for example \\bgit\\b) is not counted. Matched with Python re (re.I | re.U),
  because \\b and Polish letters behave differently in BSD and GNU grep.
As a module: hits(text, allow=()) -> [(line number, pattern, match)].
"""
import re
import sys

ENGLISH = [
    r"\bgat(e|es|ed)\b", r"publish", r"publication", r"repositor", r"\brepos?\b", r"github", r"\bcommit",
    r"\bpush(ed|es|ing)?\b", r"\bpull(ed|s|ing)?\b", r"\bremotes?\b", r"\borigin\b", r"\bbranch",
    r"\bmerg(e|ed|es|ing)\b", r"\bsign(ed|ing)?[ -]?in\b", r"\blog[ -]?in\b", r"\breaders?\b", r"\bidentit",
    r"\bdepartment", r"\bcolleague", r"\bchannel", r"\bmessenger", r"webhook", r"\bnodes?\b",
    r"\bshar(e|ed|es|ing)\b", r"\bapprov", r"\bgit\b", r"\bteams?\b",
]
POLISH = [
    r"bramk", r"bramek", r"publik", r"repozytor", r"\bdział(u|owi|em|y|ów|ami|ach|om|ie)?\b", r"\bkoleg", r"\bkoleż",
    r"\bkanał", r"komunikator", r"\bwęz(eł|ł)", r"udost[ęe]pni", r"wysył", r"wysła", r"wyśl", r"zatwierd", r"zalog",
    r"czytelni", r"tożsamo", r"\bgałę[zź]", r"\bgałą[zź]", r"zesp[oó]ł",
]
WORDS = ENGLISH + POLISH
COMPILED = [(p, re.compile(p, re.I | re.U)) for p in WORDS]


def hits(text, allow=()):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, rx in COMPILED:
            if pattern in allow:
                continue
            for m in rx.finditer(line):
                found.append((number, pattern, m.group(0)))
    return found


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="\n")
    if not argv or len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    allow = tuple(a for a in argv[1].split(",") if a) if len(argv) == 2 else ()
    unknown = [a for a in allow if a not in WORDS]
    if unknown:
        print("words.py: not a pattern of the list: %s" % ", ".join(unknown), file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    found = hits(text, allow)
    for number, pattern, match in found:
        print("%d\t%s\t%s" % (number, pattern, match))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
