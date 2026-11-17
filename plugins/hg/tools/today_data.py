#!/usr/bin/env python3
"""today_data.py - the facts /hg:today and /hg:dayend need, as JSON, so no skill depends on date or jq.

Usage: hg-tool today-data
Dates come from the configured zone, or the local clock when the machine has no zone database.
Env: KIT_TODAY=YYYY-MM-DD pins "today" (tests).
In a folder with no .claude/hg.json it prints only {"mode": "none", "places": [...], "say": {"pl": ..., "en": ...}}.
"""
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402
import solo  # noqa: E402

LOG_OPS = ("ingest", "query", "file_back", "supersede")
GATE_KEYS = ("id", "title", "status", "changed", "accountable")
AGENT_APPROVAL_DAYS = 14
INLINE_MAX = 80
# Quotes become ' so the text cannot close the sentence's own quotes; these marks would start a link, tag or code span.
INLINE_MARKS = str.maketrans({'"': "'", "„": "'", "”": "'", "“": "'", "[": None, "]": None, "<": None, ">": None, "`": None})


def workday_numbers(spec):
    days = set()
    for part in spec.replace(" ", "").split(","):
        m = re.fullmatch(r"([1-7])(?:-([1-7]))?", part)
        if m:
            days.update(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    return days or {1, 2, 3, 4, 5}


def dated_files(folder, before):
    if not folder.is_dir():
        return []
    named = [p for p in folder.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem) and p.stem < before]
    return sorted(named, key=lambda p: p.stem)


def last_note(root, vault, today):
    notes = dated_files(root / vault / "daily", today)
    if not notes:
        return None
    text = notes[-1].read_text(encoding="utf-8", errors="replace")
    return {"path": notes[-1].relative_to(root).as_posix(),
            "unchecked": [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- [ ]")]}


def recent_inbox(root, vault):
    folder = root / vault / "inbox"
    if not folder.is_dir():
        return []
    cutoff, found = time.time() - 86400, []
    for path in sorted(folder.iterdir()):
        if path.name.startswith("keep-"):  # hg's own working files, written and removed within one call
            continue
        if path.is_file() and not path.name.startswith((".", "_")) and path.name != "README.md" and path.stat().st_mtime >= cutoff:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            found.append({"path": path.relative_to(root).as_posix(), "first_line": lines[0] if lines else ""})
    return found


def last_journal(root, conf, today):
    days = dated_files(root / conf["JOURNAL_DIR"], today)
    if not days:
        return None
    lines = days[-1].read_text(encoding="utf-8", errors="replace").splitlines()
    return {"path": days[-1].relative_to(root).as_posix(), "sessions": [ln for ln in lines if ln.startswith("- ")][:20]}


def log_summary(root, conf, today):
    counts = {op: 0 for op in LOG_OPS}
    conflicts = []
    path = root / conf["LOG_FILE"]
    if not path.is_file():
        return {"counts_7d": counts, "conflicts_queued": conflicts}
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=7)).isoformat()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("op") == "conflict" and entry.get("status") == "queued":
            conflicts.append(entry.get("note", ""))
        if entry.get("op") in counts and str(entry.get("ts", ""))[:10] >= since:
            counts[entry["op"]] += 1
    return {"counts_7d": counts, "conflicts_queued": conflicts}


def open_questions(root, vault):
    """Bullets under '## Open' in every project's context map."""
    found = []
    for path in sorted((root / vault / "projects").glob("*/context-map.md")):
        inside = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("## "):
                inside = line[3:].strip().casefold() == "open"
            elif inside and line.lstrip().startswith(("- ", "* ")):
                found.append({"project": path.parent.name, "path": path.relative_to(root).as_posix(),
                              "text": line.strip()[2:].strip()})
    return found


def next_workday(day, workdays):
    for step in range(1, 8):
        candidate = day + datetime.timedelta(days=step)
        if candidate.isoweekday() in workdays:
            return candidate
    return day + datetime.timedelta(days=1)


def inline(text):
    """Committed text made safe to sit inside a sentence that is copied word for word."""
    text = gate.one_line(text.translate(INLINE_MARKS))
    return text if len(text) <= INLINE_MAX else text[:INLINE_MAX - 1].rstrip() + "…"


def approval_line(entry, polish):
    """The sentence /hg:today copies as it is: from the raw fields a model wrote "You approved" and "yesterday".

    Title and account come from committed files any repo writer can edit. The title stays one quoted title.
    The account is not quoted, so only its first word is kept: an email address has no spaces.
    """
    day = entry["at"][:10] if re.match(r"\d{4}-\d{2}-\d{2}", entry["at"]) else ""
    title, by = inline(entry["title"]), inline((entry["by"].split() or [""])[0])
    if polish:
        account = "na Twoim koncie" if entry["own"] else "na koncie %s" % by if by else "na nieznanym koncie"
        return "Agent zatwierdził bramkę „%s” %s %s, a odpowiadasz za nią Ty." % (
            title, account, "dnia " + day if day else "w nieznanym dniu")
    account = "on your account" if entry["own"] else "on the account of %s" % by if by else "on an unknown account"
    return 'An agent approved gate "%s" %s %s, and you are accountable for it.' % (
        title, account, "on " + day if day else "on an unknown date")


SOURCE_TEXT = {
    True: {
        "changed": "Źródło „{source}” bramki „{title}” zmieniło się po zatwierdzeniu. Bramka czeka na ponowne zatwierdzenie.",
        "stale": "Ostatnie zapisane sprawdzenie źródła „{source}” bramki „{title}” jest sprzed {days} dni ({date}). "
                 "Nie wiadomo, czy zatwierdzenie jest aktualne.",
        "never": "Źródło „{source}” bramki „{title}” nie ma jeszcze zapisanego sprawdzenia.",
        "person": "Źródło „{source}” bramki „{title}” sprawdza tylko człowiek. Ostatnio {date}.",
        "no_tool": "Źródła „{source}” bramki „{title}” ta sesja nie umie odczytać. Ostatnio sprawdzone {date}.",
        "no_tool_never": "Źródła „{source}” bramki „{title}” ta sesja nie umie odczytać.",
    },
    False: {
        "changed": 'Source "{source}" of gate "{title}" changed after the approval. The gate waits for a new approval.',
        "stale": 'The last recorded check of source "{source}" of gate "{title}" is {days} days old ({date}). '
                 'It is not known whether the approval still holds.',
        "never": 'No check of source "{source}" of gate "{title}" has been recorded yet.',
        "person": 'Only a person checks source "{source}" of gate "{title}". Last on {date}.',
        "no_tool": 'This session cannot read source "{source}" of gate "{title}". Last checked on {date}.',
        "no_tool_never": 'This session cannot read source "{source}" of gate "{title}".',
    },
}


def changed_line(title, source, polish):
    """The sentence for a source that changed after the approval; also the second line of 'gate observe'."""
    return SOURCE_TEXT[bool(polish)]["changed"].format(source=source, title=inline(title))


def source_lines(entry, polish):
    """(line, no_tool_line) for one source of an approved gate: finished sentences /hg:today copies as they are."""
    text = SOURCE_TEXT[bool(polish)]
    fill = {"source": entry["source"], "title": inline(entry["title"]), "days": entry["days"], "date": entry["checked"]}
    state, watched = entry["state"], bool(entry["watch"])
    if state == "never":
        return text["never"].format(**fill), text["no_tool_never"].format(**fill) if watched else ""
    no_tool = text["no_tool"].format(**fill) if watched else ""
    if state in ("changed", "stale"):
        return text[state].format(**fill), no_tool
    return ("" if watched else text["person"].format(**fill)), no_tool


def source_data(gates, polish):
    """One entry per source of every gate with at least one approval. Drafts are read in the approve flow."""
    found = []
    for g in gates:
        if not g["approvals"]:
            continue
        for s in g["sources"]:
            entry = {"gate": g["id"], "source": s["id"], "url": s["url"], "watch": s["watch"], "state": s["state"],
                     "checked": s["checked"][:10], "days": s["days"], "command": s["command"]}
            line, no_tool_line = source_lines(dict(entry, title=g["title"]), polish)
            found.append(dict(entry, line=line, no_tool_line=no_tool_line))
    return found


class Context:
    """What the sections share: the folder, its config, the day, and the gates read once, only when a section
    asks for them."""

    def __init__(self, root, conf, day):
        self.root, self.conf, self.day = root, conf, day
        self._gates = None

    @property
    def gates(self):
        if self._gates is None:
            self._gates = gate.all_gates(self.root)
        return self._gates


def gates_section(ctx):
    return [{key: g[key] for key in GATE_KEYS} for g in ctx.gates]


def sources_section(ctx):
    return source_data(ctx.gates, gate.is_polish(ctx.conf))


def approvals_section(ctx):
    since = (ctx.day - datetime.timedelta(days=AGENT_APPROVAL_DAYS)).isoformat()
    return [dict(a, line=approval_line(a, gate.is_polish(ctx.conf))) for a in gate.agent_approvals(ctx.root, ctx.gates, since)]


def unpublished_section(ctx):
    return unpublished(ctx.root, ctx.conf)


KEPT_EMPTY = {"count_7d": 0, "pending": 0, "pending_line": "", "latest": []}


def kept_section(ctx):
    """What was kept and which kept sources have no page yet (hg-tool keep --list). One unreadable source never
    fails the section: keep.list_rows catches per row, and anything else gives the empty section."""
    import keep  # imported here: keep imports this module for inline()
    try:
        return keep.kept_summary(ctx.root, ctx.conf, ctx.day)
    except Exception:
        return dict(KEPT_EMPTY)


# (key, function(ctx) -> value, the modes that have the key). A personal folder leaves a key out, not empty: a model
# that reads "gates": [] tends to say there are no gates. The next pieces of work add rows here.
SECTIONS = (
    ("gates", gates_section, ("shared",)),
    ("sources", sources_section, ("shared",)),
    ("agent_approvals", approvals_section, ("shared",)),
    ("unpublished", unpublished_section, ("shared",)),
    ("kept", kept_section, ("personal", "shared")),
)


def collect(root, skip=()):
    """skip: keys of SECTIONS the caller does not need (the shared dashboard does not show kept)."""
    conf = kr.load_conf(root)
    mode = solo.mode(root)
    vault = conf["VAULT_DIR"].rstrip("/")
    pinned = os.environ.get("KIT_TODAY")
    day = datetime.date.fromisoformat(pinned) if pinned else kr.local_now(conf["TIMEZONE"]).date()
    today = day.isoformat()
    workdays = workday_numbers(conf["WORKDAYS"])
    data = {
        "mode": mode,
        "date": today,
        "weekday": day.strftime("%A"),
        "weekday_number": day.isoweekday(),
        "is_workday": day.isoweekday() in workdays,
        "next_workday": next_workday(day, workdays).isoformat(),
        "last_note": last_note(root, vault, today),
        "inbox_recent": recent_inbox(root, vault),
        "last_journal": last_journal(root, conf, today),
        "log": log_summary(root, conf, today),
        "open_questions": open_questions(root, vault),
    }
    ctx = Context(root, conf, day)
    for key, section, modes in SECTIONS:
        if mode in modes and key not in skip:
            data[key] = section(ctx)
    return data


def unpublished(root, conf):
    """Changes the department does not see yet: what git lists, the log, the journal and the index left out, plus
    commits no remote has. No path. A folder without git counts 0."""
    import publish  # imported here: only this key needs it
    try:
        return publish.unpublished(root, conf)
    except Exception:
        return {"count": 0, "line": ""}


def main():
    kr.stdio_utf8()
    root = kr.kit_root()
    if not root.joinpath(*kr.CONFIG_PARTS).is_file():  # not set up: only where the notes are, never a briefing
        print(json.dumps(solo.not_set_up(root), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(collect(root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
