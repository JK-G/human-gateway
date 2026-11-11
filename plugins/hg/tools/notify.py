#!/usr/bin/env python3
"""notify.py - say in the department's Slack channel which gates wait. No model, no link, fixed templates.

Usage:
  hg-tool notify push --before SHA --after SHA    preview: print the payloads this push would send
  hg-tool notify digest [--force]                 preview: print today's list, if any (--force: any day)
  hg-tool notify test                             preview: print the test message
  hg-tool notify status                           checks, as LEVEL<TAB>check<TAB>message lines
  python .github/hg/notify.py ci [--dry-run]      the only form that posts; reads the event from the environment

Only 'ci' posts, and only 'ci' reads the secret. A preview prints one JSON payload per line on stdout and a
one-line count on stderr. 'ci' reads HG_EVENT (push, schedule, workflow_dispatch), HG_MODE (list or test, for
a manual run; digest is another name for list), HG_BEFORE and HG_AFTER. Its first step takes HG_SLACK_WEBHOOK_URL out of the process environment,
so no git child process inherits it, and the address is never printed.

A push posts one message per gate that started to wait (draft or reopened) between the tree before and the
tree after it, or one list when more than five did. A workday morning posts one list of what waits and what
has an outside source with no recent recorded check, only when there is something.

Exit (ci): 0 sent, nothing to send, the secret not set (the feature is off), the tree before the push not in
the clone, not a workday, or not a department workspace; 1 a message was due and not delivered (and in test
mode when the secret is not set); 2 usage error. A green run does not prove that a message arrived.
'status' always exits 0. The previews exit 0, 1 when refused, 2 on a usage error.

Standard library only. hg-tool setup copies it to .github/hg/ for CI, next to gate.py, canonicalize.py,
kit_registry.py and scan.py.
"""
import datetime
import hashlib
import http.client
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

HERE = Path(__file__).resolve().parent
SECRET_ENV = "HG_SLACK_WEBHOOK_URL"
WORKFLOW = ".github/workflows/hg-notify.yml"
COPIES = ("notify.py", "gate.py", "canonicalize.py", "kit_registry.py")  # scan.py is doctor's 'scanner' check
ZERO = "0" * 40
SHA_RE = re.compile(r"[0-9a-fA-F]{4,40}")
PER_GATE_MAX = 5
LIST_MAX = 10
TITLE_MAX = 80
ADDRESS_MAX = 100
TEXT_MAX = 3000
TIMEOUT = 10
GH_TIMEOUT = 15
RETRY_WAIT = 2
BETWEEN = 1

ADDRESS_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DROP_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}
QUOTES = str.maketrans({c: "'" for c in '"“”„‟«»‹›″‶〝〞〟＂'})
MARKUP = str.maketrans({"<": None, ">": None, "`": None, "*": None, "~": None, "|": None, "_": " ", "@": "(at)"})
SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
BAD_SECRET = ("notify: the secret does not look like a Slack webhook address. Paste it again on GitHub, "
              "with no space or line break around it.")


class Usage(Exception):
    """The command line or the event is wrong: exit 2."""


class Refused(Exception):
    """Understood, and the answer is no: exit 1."""


# ---- text ------------------------------------------------------------------------------------

TEXT = {
    True: {
        "new": "Nowa bramka czeka na zatwierdzenie: „{title}” ({id}). Odpowiada: {accountable}. "
               "Otwórz Claude w folderze działu i wpisz /hg:gate.",
        "reopened": "Bramka znów czeka na zatwierdzenie: „{title}” ({id}). Powód: {reasons}. Odpowiada: {accountable}. "
                    "Otwórz Claude w folderze działu i wpisz /hg:gate.",
        "reasons": {"files": "zmiana w plikach", "source": "zmiana w źródle zewnętrznym",
                    "list": "zmiana listy plików lub źródeł", "accountable": "zmiana osoby odpowiedzialnej",
                    "unreadable": "zapis zatwierdzeń nie daje się odczytać"},
        "waiting": "Czeka na zatwierdzenie ({n}):",
        "to_check": "Do sprawdzenia ({n}):",
        "wait_line": "- „{title}” ({id}), {status}. Odpowiada: {accountable}.",
        "check_line": "- „{title}” ({id}), ostatnie sprawdzenie źródła zewnętrznego zapisane w repozytorium "
                      "jest sprzed {days} dni.",
        "status": {"reopened": "otwarta ponownie", "draft": "szkic"},
        "digest_end": "Otwórz Claude w folderze działu i napisz: co mam dziś.",
        "more": "i jeszcze {k}.",
        "push_list": "Po ostatniej zmianie czekają na zatwierdzenie ({n}):",
        "push_end": "Otwórz Claude w folderze działu i wpisz /hg:gate.",
        "test": "To jest wiadomość próbna z hg. Połączenie ze Slackiem działa.",
        "nobody": "nie podano",
    },
    False: {
        "new": 'A new gate waits for approval: "{title}" ({id}). Accountable: {accountable}. '
               "Open Claude in the department folder and type /hg:gate.",
        "reopened": 'A gate waits for approval again: "{title}" ({id}). Reason: {reasons}. Accountable: {accountable}. '
                    "Open Claude in the department folder and type /hg:gate.",
        "reasons": {"files": "a file changed", "source": "an outside source changed",
                    "list": "the list of files or sources changed", "accountable": "the accountable person changed",
                    "unreadable": "the approval record cannot be read"},
        "waiting": "Waiting for approval ({n}):",
        "to_check": "To check ({n}):",
        "wait_line": '- "{title}" ({id}), {status}. Accountable: {accountable}.',
        "check_line": '- "{title}" ({id}), the last check of an outside source recorded in the repository is {days} days old.',
        "status": {"reopened": "reopened", "draft": "draft"},
        "digest_end": "Open Claude in the department folder and write: what do I have today.",
        "more": "and {k} more.",
        "push_list": "After the last change these wait for approval ({n}):",
        "push_end": "Open Claude in the department folder and type /hg:gate.",
        "test": "This is a test message from hg. The connection to Slack works.",
        "nobody": "not given",
    },
}
# The phrases of a reopened message, in this order, each for the reasons that bring it.
REASON_GROUPS = (
    ("files", {"changed", "missing"}),
    ("source", {"source_changed"}),
    ("list", {"added", "removed", "invalid", "source_added", "source_removed", "source_replaced", "source_invalid"}),
    ("accountable", {"accountable"}),
    ("unreadable", {"unreadable"}),
)


def clean(title):
    """A gate title made safe for a Slack message: one line, no mention, no link, no markup, at most 80 characters."""
    text = "".join(" " if unicodedata.category(c) in DROP_CATEGORIES else c for c in str(title))
    text = " ".join(text.split())
    text = text.translate(QUOTES).translate(MARKUP)
    while SCHEME_RE.search(text):  # one pass could join the text around a removed scheme into a new one
        text = SCHEME_RE.sub("", text)
    text = " ".join(text.split())
    text = text.replace("&", "&amp;")
    if len(text) > TITLE_MAX:
        text = re.sub(r"&[a-z]*$", "", text[:TITLE_MAX - 1]).rstrip() + "…"  # never half an &amp;
    return text


def address(value, polish):
    """The accountable address when it is one plain address, else the fixed 'not given'."""
    value = str(value or "")
    return value if len(value) <= ADDRESS_MAX and ADDRESS_RE.fullmatch(value) else TEXT[polish]["nobody"]


def slack_payload(text):
    return json.dumps({"text": text[:TEXT_MAX]}, ensure_ascii=True)


# The one seam for another channel: its address shape, its cleaning and its payload.
CHANNELS = {"slack": {"address": re.compile(r"https://hooks\.slack\.com/[A-Za-z0-9/_-]+"),
                      "clean": clean, "payload": slack_payload}}
CHANNEL = CHANNELS["slack"]


def reasons_text(changed, polish):
    whys = {c.get("why") for c in changed}
    phrases = TEXT[polish]["reasons"]
    found = [phrases[key] for key, members in REASON_GROUPS if whys & members]
    return ", ".join(found) or phrases["list"]


def fields(g, polish):
    return {"title": CHANNEL["clean"](g["title"]), "id": g["id"], "accountable": address(g["accountable"], polish)}


def gate_message(g, polish):
    t = TEXT[polish]
    if g["status"] == "draft":
        return t["new"].format(**fields(g, polish))
    return t["reopened"].format(reasons=reasons_text(g["changed"], polish), **fields(g, polish))


def wait_line(g, polish):
    t = TEXT[polish]
    return t["wait_line"].format(status=t["status"][g["status"]], **fields(g, polish))


def check_line(g, polish):
    days = max([c.get("days") or 0 for c in g["changed"] if c.get("why") == "source_stale"] or [0])
    f = fields(g, polish)
    return TEXT[polish]["check_line"].format(title=f["title"], id=f["id"], days=days)


def waiting_order(gates):
    """Reopened first, then drafts, each by id."""
    return sorted((g for g in gates if g["status"] in gate.WAITING), key=lambda g: (g["status"] != "reopened", g["id"]))


def capped(sections, polish):
    """Headers and bullet lines, at most LIST_MAX bullets in all, then 'and k more'."""
    out, shown = [], 0
    total = sum(len(lines) for _, lines in sections)
    for header, lines in sections:
        room = LIST_MAX - shown
        if not lines or room <= 0:
            continue
        out.append(header)
        out.extend(lines[:room])
        shown += min(room, len(lines))
    if total > shown:
        out.append(TEXT[polish]["more"].format(k=total - shown))
    return out


def digest_message(gates, polish):
    """The morning list, or None when nothing waits and nothing is to check."""
    t = TEXT[polish]
    waiting = waiting_order(gates)
    to_check = sorted((g for g in gates if g["status"] == "unchecked"), key=lambda g: g["id"])
    if not waiting and not to_check:
        return None
    lines = capped([(t["waiting"].format(n=len(waiting)), [wait_line(g, polish) for g in waiting]),
                    (t["to_check"].format(n=len(to_check)), [check_line(g, polish) for g in to_check])], polish)
    return "\n".join(lines + [t["digest_end"]])


def started_waiting(before, after):
    """The gates of 'after' that wait and did not wait in 'before' (a map id -> gate)."""
    return [g for g in after if g["status"] in gate.WAITING
            and (g["id"] not in before or before[g["id"]]["status"] not in gate.WAITING)]


def push_messages(started, polish):
    if not started:
        return []
    started = waiting_order(started)
    if len(started) <= PER_GATE_MAX:
        return [gate_message(g, polish) for g in started]
    t = TEXT[polish]
    lines = capped([(t["push_list"].format(n=len(started)), [wait_line(g, polish) for g in started])], polish)
    return ["\n".join(lines + [t["push_end"]])]


def test_message(polish):
    return TEXT[polish]["test"]


# ---- the trees ------------------------------------------------------------------------------

def git(root, *args):
    try:
        return subprocess.run(["git"] + list(args), cwd=str(root), capture_output=True, encoding="utf-8", errors="replace")
    except OSError:
        return None


def is_commit(root, sha):
    out = git(root, "cat-file", "-e", sha + "^{commit}")
    return out is not None and out.returncode == 0


def statuses_at(root, sha, day):
    """{id: gate} of the tree at a commit, through a temporary detached worktree that is always removed."""
    temp = Path(tempfile.mkdtemp(prefix="hg-notify-"))
    tree = temp / "tree"
    try:
        out = git(root, "worktree", "add", "--detach", "--force", str(tree), sha)
        if out is None or out.returncode != 0:
            raise Refused("notify: the tree of commit %s could not be checked out." % sha[:12])
        return {g["id"]: g for g in gate.all_gates(tree, day)}
    finally:
        git(root, "worktree", "remove", "--force", str(tree))
        shutil.rmtree(str(temp), ignore_errors=True)  # before the prune: a tree git could not remove is then pruned too
        git(root, "worktree", "prune")


def push_texts(root, before, after, polish, day):
    """The messages of one push, or None when the tree before it is not in this clone."""
    for sha, name in ((before, "--before"), (after, "--after")):
        if not sha or not SHA_RE.fullmatch(sha):
            raise Usage("notify: %s needs a commit id (hex)" % name)
    if not is_commit(root, after):
        raise Refused("notify: commit %s is not in this clone." % after[:12])
    if before == ZERO:
        old = {}
    elif not is_commit(root, before):
        return None
    else:
        old = statuses_at(root, before, day)
    new = statuses_at(root, after, day)
    return push_messages(started_waiting(old, list(new.values())), polish)


def zone_today(conf):
    pinned = os.environ.get("KIT_TODAY", "")
    try:
        return datetime.date.fromisoformat(pinned) if pinned else kr.local_now(conf["TIMEZONE"]).date()
    except ValueError:
        return kr.local_now(conf["TIMEZONE"]).date()


def workday_numbers(spec):
    """'1-5' or '1,2,3' as ISO weekday numbers; the same reading as today-data's."""
    days = set()
    for part in str(spec).replace(" ", "").split(","):
        m = re.fullmatch(r"([1-7])(?:-([1-7]))?", part)
        if m:
            days.update(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    return days or {1, 2, 3, 4, 5}


def is_workday(conf):
    return zone_today(conf).isoweekday() in workday_numbers(conf["WORKDAYS"])


def digest_texts(root, day):
    polish = gate.is_polish(kr.load_conf(root))
    text = digest_message(gate.all_gates(root, day), polish)
    return [text] if text else []


def is_workspace(root):
    return root.joinpath(*kr.CONFIG_PARTS).is_file()


# ---- sending ------------------------------------------------------------------------------

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect becomes an HTTP error: the message never goes to an address it was not given."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener():
    return urllib.request.build_opener(NoRedirect)


def send(payload, url, opener=None, sleep=time.sleep):
    """None when the message was taken, else a fixed sentence with the HTTP status or the exception's class name.

    One retry after RETRY_WAIT seconds on a network error, HTTP 429 or 5xx. Never the address or the error's text.
    """
    opener = opener or build_opener()
    data = payload.encode("ascii")
    for attempt in (1, 2):
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with opener.open(request, timeout=TIMEOUT):
                return None
        except urllib.error.HTTPError as exc:
            code = exc.code
            if attempt == 1 and (code == 429 or 500 <= code <= 599):
                sleep(RETRY_WAIT)
                continue
            return "Slack answered with HTTP %d" % code
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            if attempt == 1:
                sleep(RETRY_WAIT)
                continue
            return "the network failed (%s)" % type(exc).__name__
    return "the message could not be sent"


def take_secret():
    """The webhook address, taken out of the environment so that no child process inherits it."""
    return os.environ.pop(SECRET_ENV, "").strip()


def deliver(payloads, url, opener=None, sleep=time.sleep):
    if not CHANNEL["address"].fullmatch(url):
        print(BAD_SECRET, file=sys.stderr)
        return 1
    failed = 0
    for k, payload in enumerate(payloads, 1):
        if k > 1:
            sleep(BETWEEN)
        problem = send(payload, url, opener, sleep)
        if problem:
            failed += 1
            print("notify: message %d of %d was not delivered: %s." % (k, len(payloads), problem), file=sys.stderr)
    print("notify: %d of %d message(s) delivered." % (len(payloads) - failed, len(payloads)), file=sys.stderr)
    return 1 if failed else 0


def ci_texts(root, conf, event, mode):
    """(messages, a notice for stderr or ''). Raises Usage on an unknown event or mode."""
    polish = gate.is_polish(conf)
    day = gate.today()
    if event == "push":
        texts = push_texts(root, os.environ.get("HG_BEFORE", ""), os.environ.get("HG_AFTER", ""), polish, day)
        if texts is None:
            return [], "notify: the commit before this push is not in the clone (a force push?), so nothing is sent. The next morning list covers it."
        return texts, ""
    if event == "schedule":
        if not is_workday(conf):
            return [], "notify: today is not a workday in .claude/hg.json, so nothing is sent."
        return digest_texts(root, day), ""
    if event == "workflow_dispatch":
        if mode == "test":
            return [test_message(polish)], ""
        if mode in ("", "list", "digest"):
            return digest_texts(root, day), ""
        raise Usage("notify: unknown HG_MODE (list or test)")
    raise Usage("notify: unknown HG_EVENT (push, schedule or workflow_dispatch)")


def ci(argv):
    url = take_secret()  # first, before any git call
    try:
        if argv not in ([], ["--dry-run"]):
            raise Usage("usage: notify.py ci [--dry-run]")
        dry = bool(argv)
        root = kr.kit_root()
        event, mode = os.environ.get("HG_EVENT", ""), os.environ.get("HG_MODE", "")
        if event not in ("push", "schedule", "workflow_dispatch"):
            raise Usage("notify: unknown HG_EVENT (push, schedule or workflow_dispatch)")
        if not is_workspace(root):
            print("notify: .claude/hg.json is missing, so this is not a department workspace. Nothing to do.", file=sys.stderr)
            return 0
        texts, notice = ci_texts(root, kr.load_conf(root), event, mode)
        if notice:
            print(notice, file=sys.stderr)
        payloads = [CHANNEL["payload"](text) for text in texts]
        if dry:
            for payload in payloads:
                print(payload)
            print("notify: dry run, %d message(s) not sent." % len(payloads), file=sys.stderr)
            return 0
        if not payloads:
            if not notice:
                print("notify: nothing to send.", file=sys.stderr)
            return 0
        if not url:
            print("notify: the secret %s is not set, so %d message(s) were skipped." % (SECRET_ENV, len(payloads)), file=sys.stderr)
            return 1 if event == "workflow_dispatch" and mode == "test" else 0
        return deliver(payloads, url)
    except Usage as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # the text of an unexpected error could hold anything, the address included
        print("notify: unexpected error: %s" % type(exc).__name__, file=sys.stderr)
        return 1


# ---- status, also printed by hg-tool doctor ----------------------------------------------------

ORIGIN_RES = (
    re.compile(r"https://(?:[^@/\s]+@)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?"),
    re.compile(r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?"),
    re.compile(r"ssh://git@github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?"),
)


def file_hash(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def copies_check(root):
    if not (root / WORKFLOW).is_file():
        return ("WARN", "notify", "%s is missing, so no Slack message is sent. Run /hg:setup --update." % WORKFLOW)
    missing = [name for name in COPIES if not (root / ".github" / "hg" / name).is_file()]
    differ = [name for name in COPIES if name not in missing
              and file_hash(root / ".github" / "hg" / name) != file_hash(HERE / name)]
    if missing or differ:
        parts = (["missing in .github/hg/: %s" % ", ".join(missing)] if missing else []) \
            + (["different from the plugin's in .github/hg/: %s" % ", ".join(differ)] if differ else [])
        return ("WARN", "notify", "%s. Run /hg:setup --update." % "; ".join(parts))
    return ("OK", "notify", "the workflow and the copies it uses match the plugin")


def github_repo(root):
    """'O/R' of a github.com origin, or None. Only the two names, so a credential in the address is never printed."""
    out = git(root, "remote", "get-url", "origin")
    if out is None or out.returncode != 0:
        return None
    raw = out.stdout.strip()
    for rx in ORIGIN_RES:
        m = rx.fullmatch(raw)
        if m and not {m.group(1), m.group(2)} & {".", ".."}:
            return "%s/%s" % (m.group(1), m.group(2))
    return None


def gh_command():
    raw = os.environ.get("HG_GH", "")
    if raw:
        try:
            return shlex.split(raw) or None
        except ValueError:
            return None
    found = shutil.which("gh")
    return [found] if found else None


class GhMissing(Exception):
    pass


def gh_json(cmd, args):
    """The parsed JSON gh printed, or None when the call failed. GhMissing when gh cannot be started."""
    try:
        out = subprocess.run(cmd + args, capture_output=True, encoding="utf-8", errors="replace", timeout=GH_TIMEOUT)
    except OSError:
        raise GhMissing()
    except subprocess.TimeoutExpired:
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except ValueError:
        return None


def secret_check(cmd, repo):
    names = gh_json(cmd, ["secret", "list", "--app", "actions", "--json", "name", "-R", repo])
    if not isinstance(names, list):
        return ("WARN", "notify-secret", "could not be checked: gh is not signed in or has no access to %s." % repo)
    if any(isinstance(n, dict) and n.get("name") == SECRET_ENV for n in names):
        return ("OK", "notify-secret", "a repository secret named %s exists. Its value cannot be read from here." % SECRET_ENV)
    return ("WARN", "notify-secret", "no repository secret named %s was found. An organization secret cannot be seen from "
            "here. If neither exists, no message is sent: add one at https://github.com/%s/settings/secrets/actions/new"
            % (SECRET_ENV, repo))


def run_check(cmd, repo):
    runs = gh_json(cmd, ["run", "list", "--workflow", "hg-notify.yml", "--limit", "30",
                         "--json", "conclusion,createdAt,event,status", "-R", repo])
    if not isinstance(runs, list):
        return None
    done = [r for r in runs if isinstance(r, dict) and r.get("status") == "completed"
            and r.get("conclusion") in ("success", "failure", "cancelled", "timed_out", "startup_failure")]
    if not done:
        return None
    last = sorted(done, key=lambda r: str(r.get("createdAt", "")), reverse=True)[0]
    date = str(last.get("createdAt", ""))[:10]
    date = date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else "on an unknown date"
    event = str(last.get("event", ""))
    event = event if re.fullmatch(r"[a-z_]{1,40}", event) else "unknown event"
    if last["conclusion"] == "success":
        return ("OK", "notify-run", "last run %s (%s) did not fail. That is not proof of delivery: a run without the secret "
                "also ends green. Only the test message proves it." % (date, event))
    if last["conclusion"] == "cancelled":
        return ("WARN", "notify-run", "last run %s (%s) was cancelled, so its messages were not sent." % (date, event))
    return ("WARN", "notify-run", "last run %s (%s) failed: a message was not delivered. Open the run in the Actions tab."
            % (date, event))


def checks(root):
    """[(level, check, message)] of the notifier: the files, then the secret and the last run through gh."""
    found = [copies_check(root)]
    repo = github_repo(root)
    cmd = gh_command()
    if not repo or not cmd:
        return found
    try:
        found.append(secret_check(cmd, repo))
        last = run_check(cmd, repo)
    except GhMissing:
        return found
    if last:
        found.append(last)
    return found


# ---- command line ---------------------------------------------------------------------------

def print_payloads(texts, what):
    payloads = [CHANNEL["payload"](text) for text in texts]
    for payload in payloads:
        print(payload)
    print("notify: %d message(s) %s." % (len(payloads), what), file=sys.stderr)
    return 0


def preview(sub, args):
    root = kr.kit_root()
    if not is_workspace(root):
        raise Refused("notify: .claude/hg.json is missing, so this is not a department workspace.")
    conf = kr.load_conf(root)
    polish = gate.is_polish(conf)
    if sub == "test":
        if args:
            raise Usage("usage: hg-tool notify test")
        return print_payloads([test_message(polish)], "would be sent")
    if sub == "digest":
        if args not in ([], ["--force"]):
            raise Usage("usage: hg-tool notify digest [--force]")
        if not args and not is_workday(conf):
            print("notify: today is not a workday in .claude/hg.json, so the morning list is not sent. --force shows it.",
                  file=sys.stderr)
            return print_payloads([], "would be sent")
        return print_payloads(digest_texts(root, gate.today()), "would be sent")
    opts, rest = {}, list(args)
    while rest:
        flag = rest.pop(0)
        if flag not in ("--before", "--after") or not rest or flag in opts:
            raise Usage("usage: hg-tool notify push --before SHA --after SHA")
        opts[flag] = rest.pop(0)
    if set(opts) != {"--before", "--after"}:
        raise Usage("usage: hg-tool notify push --before SHA --after SHA")
    texts = push_texts(root, opts["--before"], opts["--after"], polish, gate.today())
    if texts is None:
        print("notify: the commit before the push is not in this clone, so nothing would be sent.", file=sys.stderr)
        return print_payloads([], "would be sent")
    return print_payloads(texts, "would be sent")


USAGE = __doc__.split("\n\n")[1]


def main(argv):
    kr.stdio_utf8()
    sub, args = (argv[0], argv[1:]) if argv else ("", [])
    if sub == "ci":
        return ci(args)
    if sub == "status":
        if args:
            print("usage: hg-tool notify status", file=sys.stderr)
            return 2
        for line in checks(kr.kit_root()):
            print("%s\t%s\t%s" % line)
        return 0
    if sub not in ("push", "digest", "test"):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return preview(sub, args)
    except Usage as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
