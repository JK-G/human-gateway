#!/usr/bin/env python3
"""nodes.py - the optional integrations of a department workspace, and what is known about each.

Usage:
  hg-tool nodes [--json] [--offline]                          one line per node: id<TAB>state<TAB>line
  hg-tool nodes declare messenger slack|teams|webhook|none    set or remove nodes.messenger.type
  hg-tool nodes declare projects <key>[,<key>...]|none        set or remove nodes.projects
  hg-tool nodes watch <link> [--json]                         platform<TAB>field proposed as the mark of a link

Five nodes, always in this order: messenger, projects, calendar, agent, backup. A state is empty, declared,
plugged, recorded, session or unavailable. Declarations live under "nodes" in .claude/hg.json, which is tracked.

What the tool knows, by kind of fact:
  declared   someone wrote it into .claude/hg.json
  recorded   read from git: what the department's repository held at the last pull or push (the branch's
             upstream ref, no network), or a tool reading of a gate source on that platform, with its date
  checked    looked at just now: the messenger's secret, by name, through gh. --offline skips this one step.
What only a session can know (which tools it has) is never stored: the session copies session_yes or
session_no, a sentence that says the session reports it.

'watch' reads only the platform table: it never opens the link. Exit 1 with 'unknown' for a host the table
does not know.

Exit: 'nodes' always 0. 'declare': 0 written, 1 refused (an unknown type or platform, a missing or
unreadable config), 2 usage. 'watch': 0 known host, 1 unknown, 2 usage.
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

ORDER = ("messenger", "projects", "calendar", "agent", "backup")

# key: (shown as, link hosts, item, field proposed as the mark). A host "*.x" is any subdomain of x.
# Every field is the name the platform's public API documentation gives the item's last-modified time.
PLATFORMS = {
    "clickup": ("ClickUp", ("app.clickup.com",), "task", "date_updated"),
    "jira": ("Jira", ("*.atlassian.net",), "issue", "updated"),
    "asana": ("Asana", ("app.asana.com",), "task", "modified_at"),
    "trello": ("Trello", ("trello.com",), "card or board", "dateLastActivity"),
    "linear": ("Linear", ("linear.app",), "issue", "updatedAt"),
    "github": ("GitHub", ("github.com",), "issue or pull request", "updated_at"),
    "notion": ("Notion", ("notion.so", "*.notion.site"), "page", "last_edited_time"),
    "monday": ("monday.com", ("*.monday.com",), "item", "updated_at"),
    "miro": ("Miro", ("miro.com",), "board", "modifiedAt"),
    "other": ("another platform", (), "any", ""),
}

NAMES = {True: {"slack": "Slack", "teams": "Microsoft Teams", "webhook": "webhook JSON"},
         False: {"slack": "Slack", "teams": "Microsoft Teams", "webhook": "a JSON webhook"}}
MISSING = {True: {"declaration": "deklaracji komunikatora", "workflow": "pliku hg-notify.yml", "notifier": "pliku notify.py"},
           False: {"declaration": "the messenger declaration", "workflow": "the file hg-notify.yml",
                   "notifier": "the file notify.py"}}
PUBLISHED = ((".claude/hg.json", "declaration"), (".github/workflows/hg-notify.yml", "workflow"),
             (".github/hg/notify.py", "notifier"))
FACT_WORDS = {"declaration": "type", "workflow": "workflow", "notifier": "notifier"}

TEXT = {
    True: {
        "messenger_empty": "Komunikator: niepodłączony. Podłączony kanał działu dostaje wiadomość, gdy bramka zaczyna czekać "
                           "na zatwierdzenie, a w dni robocze rano listę tego, co czeka. Działa ze Slackiem, Microsoft Teams "
                           "i każdym adresem, który przyjmuje JSON. Podłączysz go przez /hg:setup --nodes.",
        "messenger_no_secret": "Komunikator: zadeklarowany {name}. W repozytorium na GitHubie nie znaleziono sekretu "
                               "HG_NOTIFY_WEBHOOK_URL. Sekretu ustawionego dla całej organizacji stąd nie widać. Bez sekretu "
                               "nic nie jest wysyłane.",
        "messenger_unknown": "Komunikator: zadeklarowany {name}. Stąd nie da się sprawdzić, czy sekret jest ustawiony: "
                             "potrzebne są repozytorium na GitHubie i program gh z zalogowanym kontem.",
        "messenger_lacks": "Komunikator: zadeklarowany {name}. W repozytorium działu brakuje jeszcze: {missing}. "
                           "Opublikuj zmiany, potem ustaw sekret.",
        "messenger_plugged": "Komunikator: {name}, podłączony. W repozytorium działu są deklaracja, plik hg-notify.yml i "
                             "sekret HG_NOTIFY_WEBHOOK_URL. To, że wiadomości dochodzą, potwierdza tylko wiadomość próbna.",
        "projects_empty": "Platformy projektowe: żadna nie jest zadeklarowana. Po zadeklarowaniu /hg:gate i /hg:init "
                          "podpowiadają, które pole zadania albo tablicy śledzić. Dzięki temu bramka otwiera się po zmianie "
                          "w tym systemie. hg niczego nie pobiera: czyta tylko sesja, która ma do tej platformy własne "
                          "narzędzie.",
        "projects_declared": "Platformy projektowe: zadeklarowane {list}. hg nie widzi, czy Twoja sesja ma narzędzie do ich "
                             "czytania.",
        "projects_recorded": "Platformy projektowe: {list}. W repozytorium jest zapisany odczyt narzędziem: {readings}.",
        "projects_reading": "W repozytorium jest zapisany odczyt narzędziem: {readings}.",
        "projects_others": "Dla pozostałych nie ma zapisanego odczytu.",
        "projects_yes": "Ta sesja zgłasza narzędzie do czytania: {platform}.",
        "projects_no": "Ta sesja nie zgłasza narzędzia do czytania: {platform}. Źródła z tej platformy sprawdza wtedy "
                       "człowiek.",
        "calendar": "Kalendarz: hg nie widzi, czy Twoja sesja ma narzędzie kalendarza. Gdy ma, /hg:today pokazuje "
                    "dzisiejsze spotkania i wolne bloki. Gdy nie ma, pomija tę część.",
        "calendar_yes": "Ta sesja zgłasza narzędzie kalendarza.",
        "calendar_no": "Ta sesja nie zgłasza narzędzia kalendarza. Podłącza się je w ustawieniach Claude, poza hg.",
        "agent": "Agent do orkiestracji: jeszcze niedostępny. Dziś każdy krok wykonuje sesja osoby, która o niego "
                 "poprosiła. Między sesjami działa tylko wiadomość wysyłana z GitHub Actions.",
        "backup": "Kopia plików źródłowych: jeszcze niedostępna. Pliki źródłowe są tylko na komputerze osoby, która je "
                  "wniosła. hg nie robi ich kopii, więc utrata dysku oznacza ich utratę.",
    },
    False: {
        "messenger_empty": "Messenger: not plugged in. A plugged-in department channel gets a message when a gate starts to "
                           "wait for approval, and on workday mornings a list of what waits. It works with Slack, Microsoft "
                           "Teams and any address that takes JSON. Plug it in with /hg:setup --nodes.",
        "messenger_no_secret": "Messenger: {name} is declared. No secret named HG_NOTIFY_WEBHOOK_URL was found in the "
                               "repository on GitHub. A secret set for the whole organization cannot be seen from here. "
                               "Without the secret nothing is sent.",
        "messenger_unknown": "Messenger: {name} is declared. Whether the secret is set cannot be checked from here: that "
                             "needs a repository on GitHub and the gh program with a signed-in account.",
        "messenger_lacks": "Messenger: {name} is declared. The department's repository still lacks: {missing}. Publish the "
                           "changes, then set the secret.",
        "messenger_plugged": "Messenger: {name}, plugged in. The department's repository holds the declaration, the file "
                             "hg-notify.yml and a secret named HG_NOTIFY_WEBHOOK_URL. Only the test message proves that "
                             "messages arrive.",
        "projects_empty": "Project platforms: none is declared. Once one is, /hg:gate and /hg:init suggest which field of a "
                          "task or a board to watch. That is how a gate reopens after a change in that system. hg fetches "
                          "nothing: only a session with its own tool for that platform reads it.",
        "projects_declared": "Project platforms: {list} are declared. hg cannot see whether your session has a tool to read "
                             "them.",
        "projects_recorded": "Project platforms: {list}. A reading made with a tool is recorded in the repository: "
                             "{readings}.",
        "projects_reading": "A reading made with a tool is recorded in the repository: {readings}.",
        "projects_others": "For the others no reading is recorded.",
        "projects_yes": "This session reports a tool that reads: {platform}.",
        "projects_no": "This session reports no tool that reads: {platform}. A person checks sources from that platform "
                       "then.",
        "calendar": "Calendar: hg cannot see whether your session has a calendar tool. When it does, /hg:today shows "
                    "today's meetings and free blocks. When it does not, that part is skipped.",
        "calendar_yes": "This session reports a calendar tool.",
        "calendar_no": "This session reports no calendar tool. One is connected in Claude's settings, outside hg.",
        "agent": "Agent for orchestration: not available yet. Today every step runs in the session of the person who "
                 "asked for it. Between sessions only the message sent from GitHub Actions runs.",
        "backup": "Backup of source files: not available yet. Source files exist only on the computer of the person who "
                  "brought them in. hg makes no copy of them, so a lost disk loses them.",
    },
}


class Refused(Exception):
    """Understood, and the answer is no: exit 1."""


class Usage(Exception):
    """The command line is wrong: exit 2."""


# ---- what .claude/hg.json declares ------------------------------------------------------------

def section(data):
    nodes = data.get("nodes") if isinstance(data, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def declared_type(data):
    """(the raw value of nodes.messenger.type or None, the valid type or '')."""
    messenger = section(data).get("messenger")
    raw = messenger.get("type") if isinstance(messenger, dict) else None
    return raw, kr.messenger_type(data)


def declared_platforms(data):
    """(known keys in the order given, once each; unknown entries)."""
    raw = section(data).get("projects")
    raw = raw if isinstance(raw, list) else []
    known, unknown = [], []
    for key in raw:
        if isinstance(key, str) and key in PLATFORMS:
            if key not in known:
                known.append(key)
        else:
            unknown.append(key)
    return known, unknown


# ---- the platform table ------------------------------------------------------------------------

def host_of(link):
    try:
        parts = urllib.parse.urlsplit(str(link).strip())
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return host if parts.scheme.lower() in ("http", "https") else ""


def host_matches(host, pattern):
    if pattern.startswith("*."):
        return host.endswith(pattern[1:]) and len(host) > len(pattern) - 1
    return host in (pattern, "www." + pattern)


def platform_of(link):
    """The table key for a link's host, or None. Never opens the link."""
    host = host_of(link)
    if not host:
        return None
    for key, (_, hosts, _, _) in PLATFORMS.items():
        if any(host_matches(host, h) for h in hosts):
            return key
    return None


# ---- the messenger -------------------------------------------------------------------------------

NOTIFY_SECRET = "HG_NOTIFY_WEBHOOK_URL"  # notify.SECRET_ENV, which a test holds equal; notify is imported lazily


def published_ref(root):
    """(ref, remote): the remote-tracking ref of the branch GitHub runs hg-notify.yml from, its default branch, as
    this computer last saw it, or (None, remote). The remote is the checked-out branch's upstream remote, else origin.
    The default branch is refs/remotes/<remote>/HEAD when a clone set it, else init.defaultBranch, main or master,
    the first one this computer has. No network."""
    def value(*args):
        out = gate.git(root, *args)
        return out.stdout.strip() if out is not None and out.returncode == 0 else ""
    branch = value("symbolic-ref", "-q", "--short", "HEAD")
    remote = value("config", "--get", "branch.%s.remote" % branch) if branch else ""
    remote = remote if remote and remote != "." else "origin"
    default = value("symbolic-ref", "-q", "refs/remotes/%s/HEAD" % remote)
    if default:
        return default, remote
    for name in dict.fromkeys(n for n in (value("config", "--get", "init.defaultBranch"), "main", "master") if n):
        ref = "refs/remotes/%s/%s" % (remote, name)
        if value("rev-parse", "-q", "--verify", ref + "^{commit}"):
            return ref, remote
    return None, remote


def upstream_holds(root, declared, ref=None):
    """[(label, present)] of what the department's default branch holds (published_ref), as this computer last saw
    it: a branch pushed elsewhere does not count, because GitHub runs the workflow from the default branch only. The
    workflow counts only when it passes the secret notify.py reads. No network."""
    if ref is None:
        ref = published_ref(root)[0]
    found = []
    for rel, label in PUBLISHED:
        out = gate.git(root, "cat-file", "-p", "%s:%s" % (ref, rel)) if ref else None
        present = out is not None and out.returncode == 0
        if present and label == "declaration":
            try:
                present = kr.messenger_type(json.loads(out.stdout.lstrip("﻿"))) == declared
            except ValueError:
                present = False
        elif present and label == "workflow":
            present = ("secrets." + NOTIFY_SECRET) in out.stdout
        found.append((label, present))
    return found


def secret_state(root, remote="origin"):
    """'found', 'absent' or None when it cannot be checked. Asks gh, the one network step."""
    import notify  # imported here: only this step needs it, and session-start never runs it
    repo, cmd = notify.github_repo(root, remote), notify.gh_command()
    if not repo or not cmd:
        return None
    try:
        names = notify.gh_json(cmd, ["secret", "list", "--app", "actions", "--json", "name", "-R", repo])
    except notify.GhMissing:
        return None
    if not isinstance(names, list):
        return None
    return "found" if any(isinstance(n, dict) and n.get("name") == notify.SECRET_ENV for n in names) else "absent"


def messenger_node(root, data, polish, online):
    t = TEXT[polish]
    _, kind = declared_type(data)
    node = {"id": "messenger", "state": "empty", "available": True, "type": kind or None, "line": t["messenger_empty"],
            "facts": []}
    if not kind:
        return node
    name = NAMES[polish][kind]
    ref, remote = published_ref(root)
    held = upstream_holds(root, kind, ref)
    present = [label for label, ok in held if ok]
    missing = [label for label, ok in held if not ok]
    node["facts"] = [{"kind": "declared", "what": "type", "value": kind},
                     {"kind": "recorded", "what": "published",
                      "value": ", ".join(FACT_WORDS[label] for label in present) or "none"}]
    node["state"] = "declared"
    if missing:
        node["line"] = t["messenger_lacks"].format(name=name, missing=", ".join(MISSING[polish][m] for m in missing))
        return node
    state = secret_state(root, remote) if online else None
    if state is None:
        node["line"] = t["messenger_unknown"].format(name=name)
        return node
    node["facts"].append({"kind": "checked", "what": "secret", "value": state})
    if state == "found":
        node["state"], node["line"] = "plugged", t["messenger_plugged"].format(name=name)
    else:
        node["line"] = t["messenger_no_secret"].format(name=name)
    return node


# ---- project platforms -----------------------------------------------------------------------------

def readings(root):
    """{platform key: newest date of a tool reading recorded for a gate source on that platform}."""
    newest = {}
    try:
        gates = gate.all_gates(root)
    except Exception:  # a broken gate file must not break the node list
        return newest
    for g in gates:
        by_link = {s["id"]: platform_of(s["url"]) for s in g.get("sources") or []}
        if not any(by_link.values()):
            continue
        observations, _ = gate.read_observations(root, g["id"])
        for sid, items in observations.items():
            key = by_link.get(sid)
            if not key:
                continue
            for obs in items:
                if obs.get("kind") == "read":  # a person's statement is not a reading
                    day = str(obs.get("at", ""))[:10]
                    if day > newest.get(key, ""):
                        newest[key] = day
    return newest


def projects_node(root, data, polish):
    t = TEXT[polish]
    known, _ = declared_platforms(data)
    node = {"id": "projects", "state": "empty", "available": True, "platforms": known, "line": t["projects_empty"],
            "session_yes": t["projects_yes"], "session_no": t["projects_no"], "facts": []}
    if not known:
        return node
    shown = ", ".join(PLATFORMS[k][0] for k in known)
    node["facts"].append({"kind": "declared", "what": "platforms", "value": ", ".join(known)})
    found = readings(root)
    read = [k for k in known if k in found]
    for k in read:
        node["facts"].append({"kind": "recorded", "what": "reading", "value": "%s %s" % (k, found[k])})
    text = ", ".join("%s (%s)" % (PLATFORMS[k][0], found[k]) for k in read)
    if read and len(read) == len(known):
        node["state"], node["line"] = "recorded", t["projects_recorded"].format(list=shown, readings=text)
        return node
    node["state"], line = "declared", t["projects_declared"].format(list=shown)
    if read:
        line += " " + t["projects_reading"].format(readings=text) + " " + t["projects_others"]
    node["line"] = line
    return node


def collect(root, online=True, polish=None):
    """The five nodes, in order, as the dicts 'nodes --json' prints. polish None: the workspace's content language."""
    root = kr.kit_root(root)
    data = kr.raw_config(root)
    if polish is None:
        polish = gate.is_polish(kr.load_conf(root))
    t = TEXT[polish]
    return [
        messenger_node(root, data, polish, online),
        projects_node(root, data, polish),
        {"id": "calendar", "state": "session", "available": True, "line": t["calendar"],
         "session_yes": t["calendar_yes"], "session_no": t["calendar_no"], "facts": []},
        {"id": "agent", "state": "unavailable", "available": False, "line": t["agent"], "facts": []},
        {"id": "backup", "state": "unavailable", "available": False, "line": t["backup"], "facts": []},
    ]


def warnings(root):
    """English WARN messages for doctor: unknown platform keys and a messenger type that is not one of the three."""
    data = kr.raw_config(root)
    found = []
    _, unknown = declared_platforms(data)
    if unknown:
        found.append("nodes.projects names %d platform%s this plugin does not know. Known: %s."
                     % (len(unknown), "" if len(unknown) == 1 else "s", ", ".join(PLATFORMS)))
    raw, kind = declared_type(data)
    if raw is not None and not kind:
        found.append("nodes.messenger.type is not slack, teams or webhook, so nothing is sent.")
    return found


def summary_line(root):
    """The session-start line, from .claude/hg.json alone: no git, no network, no gh."""
    data = kr.raw_config(root)
    _, kind = declared_type(data)
    known, _ = declared_platforms(data)
    return ("- Nodes declared in .claude/hg.json (not checked here): messenger %s; project platforms %s. Not available "
            "yet: agent, backup. hg-tool nodes prints the full list." % (kind or "none", ", ".join(known) or "none"))


# ---- command line -------------------------------------------------------------------------------

def line_of(node):
    return "%s\t%s\t%s" % (node["id"], node["state"], node["line"])


def declare(root, args):
    if len(args) != 2 or args[0] not in ("messenger", "projects"):
        raise Usage("usage: hg-tool nodes declare messenger slack|teams|webhook|none\n"
                    "       hg-tool nodes declare projects <key>[,<key>...]|none")
    what, value = args[0], args[1].strip()
    if what == "messenger":
        if value not in kr.MESSENGER_TYPES + ("none",):
            raise Refused("nodes: '%s' is not a messenger type. Use slack, teams, webhook or none." % value[:40])
        entry = None if value == "none" else {"type": value}
    else:
        keys = [k.strip() for k in value.split(",") if k.strip()]
        if value == "none":
            entry = None
        else:
            bad = [k for k in keys if k not in PLATFORMS]
            if bad or not keys:
                raise Refused("nodes: %s not a platform this plugin knows. Known: %s."
                              % ("'%s' is" % bad[0][:40] if bad else "an empty list is", ", ".join(PLATFORMS)))
            entry = list(dict.fromkeys(keys))
    path = root.joinpath(*kr.CONFIG_PARTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise Refused("nodes: .claude/hg.json is missing. Run /hg:setup.")
    except (OSError, ValueError) as exc:
        raise Refused("nodes: .claude/hg.json is unreadable and was not changed: %s" % exc)
    if not isinstance(data, dict):
        raise Refused("nodes: .claude/hg.json is not an object and was not changed.")
    nodes = data.get("nodes", {})
    if not isinstance(nodes, dict):
        raise Refused("nodes: the key nodes in .claude/hg.json is not an object and was not changed.")
    if entry is None:
        nodes.pop(what, None)
    else:
        nodes[what] = entry
    if nodes:
        data["nodes"] = nodes
    else:
        data.pop("nodes", None)
    gate.write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    node = next(n for n in collect(root, online=False) if n["id"] == what)
    print(line_of(node))
    return 0


def watch(args):
    as_json = "--json" in args
    rest = [a for a in args if a != "--json"]
    if len(rest) != 1:
        raise Usage("usage: hg-tool nodes watch <link> [--json]")
    key = platform_of(rest[0])
    if key is None:
        print(json.dumps({"platform": "unknown", "field": ""}) if as_json else "unknown")
        return 1
    shown, _, item, field = PLATFORMS[key]
    if as_json:
        print(json.dumps({"platform": key, "name": shown, "item": item, "field": field}, ensure_ascii=False))
    else:
        print("%s\t%s" % (key, field))
    return 0


def main(argv):
    kr.stdio_utf8()
    try:
        if argv[:1] == ["declare"]:
            return declare(kr.kit_root(), argv[1:])
        if argv[:1] == ["watch"]:
            return watch(argv[1:])
        if any(a not in ("--json", "--offline") for a in argv):
            raise Usage(__doc__.split("\n\n")[1])
        nodes = collect(kr.kit_root(), online="--offline" not in argv)
        if "--json" in argv:
            print(json.dumps(nodes, ensure_ascii=False, indent=1))
        else:
            for node in nodes:
                print(line_of(node))
        return 0
    except Usage as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
