#!/usr/bin/env python3
"""gate.py - approvals that reopen when their inputs change. The only writer of gates/.

Usage:
  hg-tool gate new <id> --title T --project P --accountable EMAIL --input PATH [--input PATH ...]
                        [--source ID=URL ...] [--watch ID=FIELD ...] [--summary TEXT]
  hg-tool gate list [--json]
  hg-tool gate approve <id> --via person|agent --request "the person's words"
  hg-tool gate note <id> --text TEXT --author TEXT
  hg-tool gate source <id> add ID=URL [--watch FIELD]
  hg-tool gate source <id> remove ID
  hg-tool gate observe <id> <source-id> --field FIELD --mark VALUE
  hg-tool gate observe <id> <source-id> --declare unchanged|changed --request "the person's words"

Input paths are relative to the repo root, or absolute as D:\\x, D:/x or /d/x.

gates/<id>.md is the readable record. gates/<id>.lock.json holds {"approvals": [...]}, to which an
approval is only ever appended. The status (draft, approved, reopened, unchecked) is computed from the
current inputs and is never stored, so reading it writes nothing. The list of inputs is part of what is
approved: adding or removing one reopens the gate, and so does changing the accountable person, whom
each approval records. A note does not.

A gate may also name outside sources: a link and the field that is its mark (a last-modified time or a
version). This tool never fetches a source. The person's agent reads the mark with its own read tool and
records it with 'gate observe', one small file per reading in gates/<id>.obs/; a person's statement is
recorded with --declare. A reading with another mark after the approval reopens the gate until the next
approval. A source whose newest recorded check is older than gates.sourceCheckDays (default 7) makes an
approved gate 'unchecked'.

'by' comes from git config user.email, ignoring variables that inject config for a single call. There is
deliberately no argument for it. Git does not verify the address, so it is a declaration, like 'via'.
Exit: 0 ok, 1 refused, 2 usage error.
"""
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonicalize  # noqa: E402
import kit_registry as kr  # noqa: E402

GATES_DIR = "gates"
ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
NEXT_HEADINGS = ("Dla następnej osoby", "For the next person")
VIA = ("person", "agent")

# Outside sources (see the docstring). Git for Windows cannot check out a file named after a device.
SOURCE_ID_MAX = 40
DEVICE_NAMES = {"con", "prn", "aux", "nul"} | {"com%d" % k for k in range(1, 10)} | {"lpt%d" % k for k in range(1, 10)}
WATCH_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,39}")
URL_RE = re.compile(r"https?://[^\s<>\"'\\@`]+")
URL_MAX = 500
MARK_MAX = 200
REQUEST_MAX = 200
MARK_CHARS = re.compile(r"[A-Za-z0-9 .,:+/_=-]+")  # the same set as the Bash guard's rule for a mark line
AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", re.ASCII)
TOOL_MARK_RE = re.compile(r"t:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z|v:sha256:[0-9a-f]{64}", re.ASCII)
OBS_NAME_RE = re.compile(r"([a-z0-9][a-z0-9-]*)\.(\d{8}T\d{6}Z)\.([0-9a-f]{8})\.json", re.ASCII)
KINDS = ("read", "unchanged", "changed")
ISO_TIME = re.compile(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:?\d{2})?")
HTTP_TIME = re.compile(r"(?:[A-Za-z]{3}, )?\d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}(?::\d{2})? (?:GMT|UTC|[+-]\d{4})")
WAITING = ("draft", "reopened")
# Computed, not written as numbers: CI copies this file into the department repo, whose scan reports long digit runs.
EPOCH_2001 = int(datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
EPOCH_2100 = int(datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc).timestamp())


class Refused(Exception):
    """The request is understood and the answer is no: exit 1, with a plain message."""


class Usage(Exception):
    """The command line is wrong: exit 2."""


def is_polish(conf):
    return conf["CONTENT_LANGUAGE"].lower().startswith("pl")


def one_line(text):
    return " ".join(text.split())


def write_atomic(path, text):
    tmp = path.with_name(".%s.%d.tmp" % (path.name, os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            tmp.unlink()


def git(root, *args, env=None):
    try:
        return subprocess.run(["git", "--literal-pathspecs"] + list(args), cwd=str(root), capture_output=True,
                              encoding="utf-8", errors="replace", env=env)
    except OSError:
        return None


def git_email(root):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG")}  # no identity for one call only
    out = git(root, "config", "user.email", env=env)
    return out.stdout.strip() if out is not None and out.returncode == 0 else ""


def head_blob(root, rel):
    """The committed bytes of a file as a checkout would write them, or None when HEAD does not have it."""
    try:
        out = subprocess.run(["git", "cat-file", "--filters", "HEAD:" + rel], cwd=str(root), capture_output=True)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def now():
    """Now in UTC. KIT_TODAY=YYYY-MM-DD pins it to 12:00:00Z of that day, so tests pin observations and ages."""
    pinned = os.environ.get("KIT_TODAY", "")
    try:
        day = datetime.date.fromisoformat(pinned) if pinned else None
    except ValueError:
        day = None
    if day:
        return datetime.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def today():
    return now().date()


def utc_text(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_at(text):
    """A UTC time written as YYYY-MM-DDTHH:MM:SSZ, or None."""
    if not isinstance(text, str) or not AT_RE.fullmatch(text):
        return None
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def age_days(at, day):
    """Whole UTC days from the date of an observation's at to day."""
    return (day - datetime.date.fromisoformat(at[:10])).days


# ---- reading: nothing in this part writes -------------------------------------------------

def gate_path(root, gate_id):
    return root / GATES_DIR / (gate_id + ".md")


def lock_path(root, gate_id):
    return root / GATES_DIR / (gate_id + ".lock.json")


def read_approvals(root, gate_id):
    """The list of approvals, [] when there is no lock file, None when the file cannot be trusted."""
    path = lock_path(root, gate_id)
    if not path.exists():
        return []
    try:
        approvals = json.loads(path.read_text(encoding="utf-8-sig"))["approvals"]
    except (ValueError, KeyError, TypeError, OSError):
        return None
    if not isinstance(approvals, list) or not all(isinstance(a, dict) and isinstance(a.get("inputs"), dict) for a in approvals):
        return None
    if not all(valid_approved_sources(a["sources"]) for a in approvals if "sources" in a):
        return None
    return approvals


def valid_approved_sources(value):
    """The sources map of an approval: id -> {url, watch, mark, seen}, all strings, seen a UTC time.

    seen is compared with observation times and its date gives the age of a check, so one that is not a
    time would break every read of the gates instead of reopening this one.
    """
    return isinstance(value, dict) and all(
        isinstance(entry, dict) and all(isinstance(entry.get(key), str) for key in ("url", "mark"))
        and parse_at(entry.get("seen")) is not None
        and isinstance(entry.get("watch", ""), str) for entry in value.values())


def digest_or_none(path):
    try:
        return canonicalize.file_digest(path) if path.is_file() else None
    except OSError:
        return None


def current_digests(root, inputs):
    return {rel: digest_or_none(root / rel) for rel in inputs}


def compare(approved, now):
    """What differs between the inputs of an approval and the inputs as they are now."""
    changed = []
    for rel in sorted(set(approved) | set(now)):
        if rel not in approved:
            why = "added"
        elif rel not in now:
            why = "removed"
        elif now[rel] is None:
            why = "missing"
        elif now[rel] != approved[rel]:
            why = "changed"
        else:
            continue
        changed.append({"path": rel, "why": why})
    return changed


def differences(gate_id, approval, digests, accountable):
    """What makes an approval no longer hold: its inputs, or the person it was made for."""
    changed = compare(approval["inputs"], digests)
    if str(approval.get("accountable", "")).casefold() != accountable.casefold():
        changed.append({"path": "%s/%s.md" % (GATES_DIR, gate_id), "why": "accountable"})
    return changed


def meta_of(text):
    try:
        front = kr.split_frontmatter(text)[0]
        data = kr.load_yaml(front) if front and front.strip() else {}
    except (kr.RegistryError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def terms_of(meta):
    """The parts of a gate file an approval depends on: its inputs and the accountable person."""
    raw_inputs = meta.get("inputs")
    inputs = [str(x).replace("\\", "/") for x in raw_inputs if x] if isinstance(raw_inputs, list) else []
    return inputs, str(meta.get("accountable") or "")


def valid_input(rel):
    """A hand-edited list skips repo_relative, and a path outside the repo would hash differently in every clone."""
    parts = rel.split("/")
    return not (rel.startswith("/") or re.match(r"[A-Za-z]:", rel) or ".." in parts or parts[0].lower() == GATES_DIR)


# ---- outside sources ---------------------------------------------------------------------------

def valid_source_id(value):
    return (isinstance(value, str) and bool(ID_RE.fullmatch(value)) and len(value) <= SOURCE_ID_MAX
            and value not in DEVICE_NAMES)


def link_shape_ok(url):
    return isinstance(url, str) and len(url) <= URL_MAX and bool(URL_RE.fullmatch(url))


def link_findings(url, cfg=None):
    """How many findings the scanner reports in a link. cfg None: the built-in rules only, no config read."""
    import scan  # imported here: a gate without sources never loads the scanner
    cfg = cfg or {"emails": set(), "domains": set(), "patterns": []}
    found = []
    scan.scan_line(url, cfg, lambda kind, rule, value: found.append(kind))
    return len(found)


def repo_scan_cfg(root):
    """The repo's own scan.allow and scan.patterns, or None (the built-in rules) when they cannot be read."""
    path = root.joinpath(*kr.CONFIG_PARTS)
    if not path.is_file():
        return None
    import scan
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return scan.load_config(str(path))
    except SystemExit:  # scan.die exits
        return None


def sources_of(meta, cfg=None):
    """(valid sources as [{id, url, watch}], labels of invalid entries). Reads no config unless cfg is given.

    A label is the entry's id when that is well formed, else '#<position>', so no free text reaches a surface.
    'sources' as the label means the key holds something that is not a list.
    """
    raw = meta.get("sources")
    if raw is None or raw == []:
        return [], []
    if not isinstance(raw, list):
        return [], ["sources"]
    valid, invalid, seen = [], [], set()
    for position, entry in enumerate(raw, 1):
        entry = entry if isinstance(entry, dict) else {}
        sid, url, watch = entry.get("id"), entry.get("url"), entry.get("watch", "")
        good_id = valid_source_id(sid) and sid not in seen
        ok = (good_id and link_shape_ok(url) and isinstance(watch, str) and (watch == "" or bool(WATCH_RE.fullmatch(watch)))
              and not link_findings(url, cfg))
        if ok:
            valid.append({"id": sid, "url": url, "watch": watch})
        else:
            invalid.append(sid if good_id else "#%d" % position)
        if good_id:
            seen.add(sid)
    return valid, invalid


def fingerprint(url, watch):
    return hashlib.sha256(("%s\n%s" % (url, watch)).encode("utf-8")).hexdigest()[:8]


def obs_dir(root, gate_id):
    return root / GATES_DIR / (gate_id + ".obs")


def valid_observation(obs, source_id, moment):
    if not isinstance(obs, dict) or obs.get("source") != source_id or obs.get("kind") not in KINDS:
        return False
    at = parse_at(obs.get("at"))
    if at is None or at > moment + datetime.timedelta(hours=24):
        return False
    if not (isinstance(obs.get("of"), str) and re.fullmatch(r"[0-9a-f]{8}", obs["of"])):
        return False
    mark = obs.get("mark")
    if not isinstance(mark, str):
        return False
    if obs["kind"] == "read":
        return (isinstance(obs.get("field"), str) and bool(WATCH_RE.fullmatch(obs["field"]))
                and bool(TOOL_MARK_RE.fullmatch(mark)) and "request" not in obs)
    request = obs.get("request")
    if not (isinstance(request, str) and request.strip() and len(request) <= REQUEST_MAX and "\n" not in request
            and "field" not in obs):
        return False
    if obs["kind"] == "changed":
        return mark.startswith("p:changed:") and parse_at(mark[len("p:changed:"):]) is not None
    return (bool(TOOL_MARK_RE.fullmatch(mark)) or mark == "p:seen"
            or (mark.startswith("p:changed:") and parse_at(mark[len("p:changed:"):]) is not None))


def read_observations(root, gate_id, moment=None):
    """({source id: [observations sorted by (at, file name)]}, number of files ignored). Writes nothing.

    A file whose name starts with a dot is a write in progress and is skipped without being counted.
    The hash in the name is not checked: it only makes names unique, and a CRLF checkout changes the bytes.
    """
    folder = obs_dir(root, gate_id)
    found, ignored = {}, 0
    if not folder.is_dir():
        return found, ignored
    moment = moment or now()
    for path in sorted(folder.iterdir()):
        if path.name.startswith("."):
            continue
        m = OBS_NAME_RE.fullmatch(path.name)
        obs = None
        if m and path.is_file():
            try:
                obs = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, OSError, RecursionError):  # RecursionError: JSON nested too deep
                obs = None
        if obs is None or not valid_observation(obs, m.group(1), moment):
            ignored += 1
            continue
        found.setdefault(obs["source"], []).append(dict(obs, file=path.name))
    for items in found.values():
        items.sort(key=lambda o: (o["at"], o["file"]))
    return found, ignored


def is_tool_mark(mark):
    return mark.startswith(("t:", "v:"))


def source_track(src, base, observations):
    """later, newest and tool of section 5.3 for one source as it is defined now.

    observations: every valid observation of this source id. base: the last approval's entry when its url and
    watch equal the definition's, else None.
    """
    fp = fingerprint(src["url"], src["watch"])
    usable = [o for o in observations if o["of"] == fp]
    later = usable if base is None else [o for o in usable if o["at"] >= base["seen"]]
    if later:
        newest = {"mark": later[-1]["mark"], "at": later[-1]["at"]}
    elif base is not None:
        newest = {"mark": base["mark"], "at": base["seen"]}
    else:
        newest = None
    tool = ([base["mark"]] if base is not None and is_tool_mark(base["mark"]) else []) \
        + [o["mark"] for o in later if is_tool_mark(o["mark"])]
    return later, newest, tool


def approved_sources(approvals):
    return (approvals[-1].get("sources") or {}) if approvals else {}


def base_of(src, approved):
    entry = approved.get(src["id"])
    if entry is not None and entry["url"] == src["url"] and entry.get("watch", "") == src["watch"]:
        return {"mark": entry["mark"], "seen": entry["seen"]}
    return None


def source_status(defined, approvals, observations, limit, day):
    """(reasons that reopen, stale reasons, {id: (state, newest)}) of section 5.3, against the last approval."""
    approved = approved_sources(approvals)
    by_id = {s["id"]: s for s in defined}
    reasons, stale, states = [], [], {}
    for sid in sorted(set(by_id) | set(approved)):
        if sid not in by_id:
            reasons.append({"path": sid, "why": "source_removed"})
            continue
        src = by_id[sid]
        base = base_of(src, approved)
        later, newest, tool = source_track(src, base, observations.get(sid, []))
        changed = False
        if approvals and sid not in approved:
            reasons.append({"path": sid, "why": "source_added"})
        elif approvals and base is None:
            reasons.append({"path": sid, "why": "source_replaced"})
        elif approvals:
            changed = (any(o["kind"] == "changed" and o["mark"] != base["mark"] for o in later)
                       or len(set(tool)) > 1)
            if changed:
                reasons.append({"path": sid, "why": "source_changed"})
        is_stale = newest is not None and age_days(newest["at"], day) > limit
        if is_stale:
            stale.append({"path": sid, "why": "source_stale", "days": age_days(newest["at"], day)})
        if newest is None:
            state = "never"
        elif changed:
            state = "changed"
        elif is_stale:
            state = "stale"
        else:
            state = "ok"
        states[sid] = (state, newest)
    return reasons, stale, states


def observe_command(gate_id, source):
    """The one builder of the observe line a skill copies. '' for a source with no watch."""
    if not source.get("watch"):
        return ""
    return "hg-tool gate observe %s %s --field %s --mark '<value>'" % (gate_id, source["id"], source["watch"])


def source_entries(gate_id, defined, states, day):
    entries = []
    for src in defined:
        state, newest = states[src["id"]]
        entries.append({"id": src["id"], "url": src["url"], "watch": src["watch"], "state": state,
                        "checked": newest["at"] if newest else "",
                        "days": age_days(newest["at"], day) if newest else None,
                        "command": observe_command(gate_id, src)})
    return entries


def load(root, path, conf=None, day=None):
    gate_id = path.stem
    conf = conf or kr.load_conf(root)
    limit = kr.source_check_days(conf)
    if day is None:
        moment = now()
        day = moment.date()
    else:
        moment = datetime.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=datetime.timezone.utc)
    try:
        meta = meta_of(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        meta = {}
    listed, accountable = terms_of(meta)
    inputs = [rel for rel in listed if valid_input(rel)]
    invalid = [rel for rel in listed if not valid_input(rel)]
    flagged = [{"path": rel, "why": "invalid"} for rel in invalid]
    defined, bad_sources = sources_of(meta)
    flagged += [{"path": label, "why": "source_invalid"} for label in bad_sources]
    approvals = read_approvals(root, gate_id)
    observations = read_observations(root, gate_id, moment)[0] if defined else {}
    unreadable = approvals is None
    if unreadable:  # an unreadable record never counts as an approval
        approvals = []
    reasons, stale, states = source_status(defined, approvals, observations, limit, day)
    if unreadable:
        status, changed = "reopened", [{"path": lock_path(root, gate_id).relative_to(root).as_posix(), "why": "unreadable"}]
    elif not approvals:
        unchecked = [{"path": s["id"], "why": "source_unchecked"} for s in defined if states[s["id"]][1] is None]
        status, changed = "draft", flagged + unchecked + stale
    else:
        changed = differences(gate_id, approvals[-1], current_digests(root, inputs), accountable) + flagged + reasons
        status = "reopened" if changed else "unchecked" if stale else "approved"
        if status == "unchecked":
            changed = stale
    return {"id": gate_id, "title": str(meta.get("title") or gate_id), "project": str(meta.get("project") or "cross"),
            "accountable": accountable, "inputs": inputs, "invalid": invalid, "status": status,
            "changed": changed, "approvals": approvals, "sources": source_entries(gate_id, defined, states, day)}


def is_gate_file(path):
    return path.name.lower() != "readme.md" and bool(ID_RE.fullmatch(path.stem))


def all_gates(root, today=None):
    """Every gate's computed state. today: a datetime.date to compute ages for (the notifier, a history reader)."""
    folder = root / GATES_DIR
    if not folder.is_dir():
        return []
    conf = kr.load_conf(root)
    return [load(root, p, conf, today) for p in sorted(folder.glob("*.md")) if is_gate_file(p)]


def source_unreadable_count(root):
    """How many files in gates/*.obs/ are ignored. Only the count: a file name is committed text."""
    folder = root / GATES_DIR
    if not folder.is_dir():
        return 0
    moment = now()
    return sum(read_observations(root, p.name[:-len(".obs")], moment)[1]
               for p in sorted(folder.glob("*.obs")) if p.is_dir())


def ignored_gate_files(root):
    """How many gates/*.md are not gates. Only the count: a file name is committed text and must not reach a session."""
    folder = root / GATES_DIR
    if not folder.is_dir():
        return 0
    return sum(1 for p in folder.glob("*.md") if p.name.lower() != "readme.md" and not is_gate_file(p))


def agent_approvals(root, gates, since):
    """Agent approvals the local person was accountable for, newest first.

    One that is still the latest of its gate is listed whatever its age, so none goes unseen. One that a later
    approval replaced is listed only since a YYYY-MM-DD date.
    The person is the one the approval recorded, so changing a gate's accountable person moves no past approval.
    'own' says whether the approval was also made under this person's git identity.
    """
    email = git_email(root).casefold()
    if not email:
        return []
    found = [{"gate": g["id"], "title": g["title"], "at": str(a.get("at", "")), "by": str(a.get("by", "")),
              "request": str(a.get("request", "")), "own": str(a.get("by", "")).casefold() == email}
             for g in gates for a in g["approvals"]
             if a.get("via") == "agent" and str(a.get("accountable", "")).casefold() == email
             and (a is g["approvals"][-1] or str(a.get("at", ""))[:10] >= since)]
    return sorted(found, key=lambda a: a["at"], reverse=True)


def changed_text(changed):
    return ", ".join("%s (%s)" % (c["path"], c["why"]) for c in changed)


# ---- commands ------------------------------------------------------------------------------

def parse(args, values, repeated=(), flags=()):
    """Hand-written so a value that starts with a dash stays a value: --request holds a person's words."""
    opts, positional, args = {}, [], list(args)
    while args:
        arg = args.pop(0)
        if arg in flags:
            opts[arg] = True
        elif arg in values or arg in repeated:
            if not args:
                raise Usage("%s needs a value" % arg)
            if arg in repeated:
                opts.setdefault(arg, []).append(args.pop(0))
            else:
                opts[arg] = args.pop(0)
        elif arg.startswith("--"):
            raise Usage("unknown argument '%s'" % arg)
        else:
            positional.append(arg)
    return opts, positional


def need_id(positional):
    if len(positional) != 1:
        raise Usage("give exactly one gate id")
    return positional[0]


def existing(root, gate_id):
    path = gate_path(root, gate_id)
    if not ID_RE.fullmatch(gate_id) or not path.is_file():
        raise Refused("gate '%s' does not exist. 'hg-tool gate list' shows the gates." % gate_id)
    return path


def repo_relative(root, raw):
    from setup_workspace import native_root  # imported here: hooks read gates and never need this
    candidate = Path(native_root(raw.strip()))
    full = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        rel = full.relative_to(root)
    except ValueError:
        raise Refused("input %s is outside this repository." % raw)
    if full.is_dir():
        raise Refused("input %s is a folder. List the files one by one." % raw)
    if rel.parts[0].lower() == GATES_DIR:
        raise Refused("input %s is inside gates/. Those files change with every note and approval." % raw)
    return rel.as_posix()


def scalar(value):
    if re.fullmatch(r"[^\W\d][\w./@+-]*", value) and value.lower() not in ("true", "false", "null"):
        return value
    # \u0022 instead of \": the frontmatter parser's comment stripping does not know about escaped quotes.
    return json.dumps(value, ensure_ascii=False).replace('\\"', "\\u0022")


def render_sources(sources):
    """The sources block of 2.1. id and watch through scalar(), so digits and true read back as strings."""
    if not sources:
        return []
    lines = ["sources:"]
    for s in sources:
        lines += ["  - id: %s" % scalar(s["id"]), "    url: %s" % json.dumps(s["url"], ensure_ascii=False)]
        if s["watch"]:
            lines.append("    watch: %s" % scalar(s["watch"]))
    return lines


def render_gate(gate_id, title, project, accountable, inputs, summary, polish, sources=()):
    front = ["---", "id: %s" % gate_id, "title: %s" % scalar(title), "project: %s" % scalar(project),
             "accountable: %s" % scalar(accountable), "inputs:"] + ["  - %s" % scalar(i) for i in inputs] \
        + render_sources(sources) + ["---"]
    approved = "Co jest akceptowane" if polish else "What is approved"
    fallback = "Brak streszczenia." if polish else "No summary yet."
    body = ["", "# %s" % title, "", "## %s" % approved, "", summary.strip() or fallback, "",
            "## %s" % NEXT_HEADINGS[0 if polish else 1], ""]
    return "\n".join(front + body)


def log_op(op, project, inputs, outputs, note=""):
    import log_append  # a log outage is reported and does not undo the gate record
    code = log_append.main(["--op", op, "--agent", "hg-gate", "--project", project, "--inputs", ",".join(inputs),
                            "--outputs", outputs, "--note", note])
    if code != 0:
        print("gate: recorded, but the log line was not written", file=sys.stderr)


LINK_FINDING = ("source %s: the link holds something the scanner reports (a key, a token or an address). "
                "Use a link without it.")


def source_problems(sid, url, watch, cfg, taken=()):
    """What breaks the rules of 2.1 for one source given on a command line. The link itself is never repeated."""
    if not (isinstance(sid, str) and ID_RE.fullmatch(sid) and len(sid) <= SOURCE_ID_MAX):
        return ["source id '%s' is not valid: use lower-case letters, digits and hyphens, at most %d characters."
                % (one_line(sid)[:60], SOURCE_ID_MAX)]
    if sid in DEVICE_NAMES:
        return ["source id '%s' is a name Windows reserves for a device. Choose another id." % sid]
    if sid in taken:
        return ["source %s is named twice. Each source needs its own id." % sid]
    if not link_shape_ok(url):
        return ["source %s: a link starts with http:// or https://, has at most %d characters, no spaces and none of "
                "< > \" ' \\ @ or a backtick." % (sid, URL_MAX)]
    if watch and not WATCH_RE.fullmatch(watch):
        return ["source %s: the field to watch is a name of letters, digits, _ . and -, starting with a letter, "
                "at most 40 characters." % sid]
    if link_findings(url, cfg):
        return [LINK_FINDING % sid]
    return []


def split_source(raw):
    if "=" not in raw:
        raise Usage("a source is given as ID=URL")
    sid, url = raw.split("=", 1)
    return sid.strip(), url.strip()


def cmd_new(root, conf, args):
    opts, positional = parse(args, ("--title", "--project", "--accountable", "--summary"),
                             repeated=("--input", "--source", "--watch"))
    gate_id = need_id(positional)
    for flag in ("--title", "--project", "--accountable", "--input"):
        if not opts.get(flag):
            raise Usage("%s is required" % flag)
    if not ID_RE.fullmatch(gate_id) or gate_id == "readme":
        raise Usage("a gate id uses lower-case letters, digits and hyphens")
    title, project, accountable = one_line(opts["--title"]), one_line(opts["--project"]), opts["--accountable"].strip()
    if not title or not project:
        raise Usage("--title and --project cannot be empty")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", accountable):
        raise Refused("--accountable must be an email address, the one in that person's git config.")
    given = [split_source(raw) for raw in opts.get("--source", [])]
    watches = {}
    for raw in opts.get("--watch", []):
        sid, field = split_source(raw)
        if sid not in [g[0] for g in given] or sid in watches:
            raise Usage("--watch %s names no source given with --source, or names it twice" % sid)
        watches[sid] = field
    sources, problems, cfg = [], [], repo_scan_cfg(root) if given else None
    for sid, url in given:
        problems += source_problems(sid, url, watches.get(sid, ""), cfg, [s["id"] for s in sources])
        sources.append({"id": sid, "url": url, "watch": watches.get(sid, "")})
    if problems:
        raise Refused("\n".join(problems))
    inputs = list(dict.fromkeys(repo_relative(root, raw) for raw in opts["--input"]))
    path = gate_path(root, gate_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_gate(gate_id, title, project, accountable, inputs, opts.get("--summary", ""), is_polish(conf), sources)
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as fh:  # "x" refuses an existing gate
            fh.write(text)
    except FileExistsError:
        raise Refused("gate '%s' already exists." % gate_id)
    for rel in inputs:
        if not (root / rel).is_file():
            print("gate: note: %s does not exist yet; approve will refuse until it does" % rel, file=sys.stderr)
    log_op("gate_new", project, inputs, path.relative_to(root).as_posix())
    print(path.relative_to(root).as_posix())


def cmd_list(root, conf, args):
    opts, positional = parse(args, (), flags=("--json",))
    if positional:
        raise Usage("list takes no arguments")
    gates = all_gates(root)
    if opts.get("--json"):
        print(json.dumps(gates, ensure_ascii=False, indent=2))
    elif not gates:
        print("No gates yet.")
    else:
        for g in gates:
            print("\t".join((g["id"], g["status"], g["title"], changed_text(g["changed"]))).rstrip("\t"))


def refuse_unless_committed(root, gate_id, gate, extra=()):
    """Compares content with HEAD instead of asking git status, which trusts git update-index flags.

    extra: problems found before this check (the sources), refused together with these in one message.
    """
    problems = ["input %s is not a path inside this repository. Correct the list in gates/%s.md." % (rel, gate_id)
                for rel in gate["invalid"]]
    for rel in gate["inputs"]:
        if not (root / rel).is_file():
            problems.append("input %s is missing." % rel)
            continue
        blob = head_blob(root, rel)
        if blob is None:
            problems.append("input %s is not committed. Commit it first: nobody else could check an uncommitted file." % rel)
        elif canonicalize.bytes_digest(blob, rel) != digest_or_none(root / rel):
            problems.append("input %s differs from the last commit. Commit it or restore it first." % rel)
    blob = head_blob(root, "%s/%s.md" % (GATES_DIR, gate_id))
    if blob is None:
        problems.append("gates/%s.md is not committed. Commit it first: an approval has to match what others see." % gate_id)
    else:
        head_meta = meta_of(blob.decode("utf-8", errors="replace"))
        inputs, accountable = terms_of(head_meta)
        if sorted(inputs) != sorted(gate["inputs"] + gate["invalid"]) or accountable != gate["accountable"]:
            problems.append("gates/%s.md has a new input list or accountable person that is not committed. Commit it or restore it first." % gate_id)
        if sources_of(head_meta) != sources_of(gate_meta(root, gate_id)):
            problems.append("gates/%s.md has a new source list that is not committed. Commit it or restore it first." % gate_id)
    problems += list(extra)
    if problems:
        raise Refused("\n".join(problems))


def gate_meta(root, gate_id):
    try:
        return meta_of(gate_path(root, gate_id).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def approve_source_problems(root, conf, gate_id, approvals):
    """The refusals of an approval about sources, the sources map it records (None: no sources) and what changed."""
    defined, bad = sources_of(gate_meta(root, gate_id))
    problems = []
    for label in bad:
        if label == "sources":
            problems.append("the sources list in gates/%s.md is not a list. Correct it." % gate_id)
        else:
            problems.append("source %s in gates/%s.md is not valid. Correct the list." % (label, gate_id))
    cfg = repo_scan_cfg(root) if defined else None
    if cfg is not None:  # the built-in rules already ran in sources_of
        problems += [LINK_FINDING % s["id"] for s in defined if link_findings(s["url"], cfg)]
    limit, day = kr.source_check_days(conf), today()
    observations = read_observations(root, gate_id)[0] if defined else {}
    approved = approved_sources(approvals)
    record = {}
    for src in defined:
        newest = source_track(src, base_of(src, approved), observations.get(src["id"], []))[1]
        if newest is None:
            problems.append("source %s has never been checked. Read it and run hg-tool gate observe, "
                            "or let the person state it with --declare." % src["id"])
        elif age_days(newest["at"], day) > limit:
            problems.append("source %s was last checked %d days ago, more than the %d allowed. Check it again first."
                            % (src["id"], age_days(newest["at"], day), limit))
        else:
            record[src["id"]] = {"url": src["url"], "watch": src["watch"], "mark": newest["mark"], "seen": newest["at"]}
    reasons = source_status(defined, approvals, observations, limit, day)[0] if approvals else []
    return problems, (record if defined else None), reasons


def cmd_approve(root, conf, args):
    opts, positional = parse(args, ("--via", "--request"))
    gate_id = need_id(positional)
    if opts.get("--via") not in VIA:
        raise Usage("--via must be person or agent")
    if "--request" not in opts:
        raise Usage("--request is required")
    gate = load(root, existing(root, gate_id), conf)
    request = opts["--request"].strip()
    if not request:
        raise Refused("--request is empty. Pass the person's own words.")
    if not gate["inputs"] and not gate["invalid"]:
        raise Refused("gate '%s' lists no inputs, so there is nothing to approve." % gate_id)
    approvals = read_approvals(root, gate_id)
    if approvals is None:
        raise Refused("%s cannot be read. Approvals are only appended, so repair it with git first."
                      % lock_path(root, gate_id).relative_to(root).as_posix())
    problems, sources, source_reasons = approve_source_problems(root, conf, gate_id, approvals)
    refuse_unless_committed(root, gate_id, gate, problems)
    by = git_email(root)
    if not by:
        raise Refused("git has no user.email here, and an approval must say who made it. Set it with git config.")
    digests = current_digests(root, gate["inputs"])
    since_last = differences(gate_id, approvals[-1], digests, gate["accountable"]) + source_reasons if approvals else []
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # the real clock, never KIT_TODAY
    approval = {"at": at, "by": by, "accountable": gate["accountable"], "via": opts["--via"], "request": request,
                "inputs": digests, "changed_since_last": since_last}
    if sources is not None:  # only a gate with sources: old records and a tested key set stay as they were
        approval["sources"] = sources
    approvals.append(approval)
    lock = lock_path(root, gate_id)
    write_atomic(lock, json.dumps({"approvals": approvals}, ensure_ascii=False, indent=2) + "\n")
    note = "via=%s" % opts["--via"] + ("; changed: %s" % changed_text(since_last) if since_last else "")
    log_op("gate_approve", gate["project"], gate["inputs"], lock.relative_to(root).as_posix(), note)
    print("approved %s (via %s)" % (gate_id, opts["--via"]))


def sources_block(lines, close):
    """(start, end) of the top-level 'sources:' block inside the frontmatter lines[1:close], or None.

    Raises Refused when 'sources:' carries a value on its own line (flow style), which the tool does not rewrite.
    """
    for k in range(1, close):
        bare = lines[k].rstrip("\r")
        if bare.rstrip() == "sources:":
            end = k + 1
            while end < close and (lines[end][:1] in (" ", "-") or not lines[end].strip()):
                end += 1
            while end > k + 1 and not lines[end - 1].strip():  # blank lines after the block stay outside it
                end -= 1
            return k, end
        if re.match(r"sources\s*:", bare):
            raise Refused("the sources list in this gate file is written on one line. Correct it in an editor, "
                          "as a list with one '- id:' entry per source.")
    return None


def cmd_source(root, conf, args):
    opts, positional = parse(args, ("--watch",))
    if len(positional) != 3 or positional[1] not in ("add", "remove"):
        raise Usage("use: gate source <gate-id> add ID=URL [--watch FIELD], or gate source <gate-id> remove ID")
    gate_id, action, arg = positional
    if action == "remove" and "--watch" in opts:
        raise Usage("--watch goes only with add")
    path = existing(root, gate_id)
    text = path.read_bytes().decode("utf-8", errors="replace")
    lines = text.split("\n")
    close = next((k for k in range(1, len(lines)) if lines[k].strip() == "---"), None)
    if lines[0].strip() != "---" or close is None:
        raise Refused("gates/%s.md has no frontmatter the tool can rewrite. Correct it in an editor." % gate_id)
    block = sources_block(lines, close)
    current, bad = sources_of(meta_of(text))
    if bad:
        raise Refused("the sources list in gates/%s.md has entries the tool cannot read. Correct them in an editor first."
                      % gate_id)
    ids = [s["id"] for s in current]
    if action == "add":
        sid, url = split_source(arg)
        if sid in ids:
            raise Refused("source %s is already in gates/%s.md. Remove it first to change it." % (sid, gate_id))
        watch = opts.get("--watch", "").strip()
        problems = source_problems(sid, url, watch, repo_scan_cfg(root))
        if problems:
            raise Refused("\n".join(problems))
        current.append({"id": sid, "url": url, "watch": watch})
    else:
        if arg not in ids:
            raise Refused("gates/%s.md has no source %s." % (gate_id, one_line(arg)[:60]))
        current = [s for s in current if s["id"] != arg]
    eol = "\r" if lines[0].endswith("\r") else ""
    rendered = [ln + eol for ln in render_sources(current)]
    start, end = block if block else (close, close)
    write_atomic(path, "\n".join(lines[:start] + rendered + lines[end:]))
    print(path.relative_to(root).as_posix())


def normalize_mark(value, field="", moment=None):
    """The stored form of a mark: t:<UTC time to the second> for a time, v:sha256:<hex> for anything else."""
    moment = moment or now()
    value = value.strip()
    if not value or len(value) > MARK_MAX:
        raise Refused("the value is empty or longer than %d characters. Read the field again." % MARK_MAX)
    if not MARK_CHARS.fullmatch(value):
        raise Refused("this value has characters the tool does not take. Do not pass it; the person can state what they saw.")
    instant = None
    if re.fullmatch(r"\d{13}|\d{10}", value):
        seconds = int(value) // 1000 if len(value) == 13 else int(value)
        if EPOCH_2001 <= seconds < EPOCH_2100:  # never refused: a version id may look like this
            instant = datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc)
    else:
        instant = iso_instant(value) or http_instant(value)
        if instant is not None and instant > moment + datetime.timedelta(hours=24):
            raise Refused("this time is in the future; check that you read `%s`." % field)
    if instant is not None:
        try:
            return "t:" + utc_text(instant)
        except OverflowError:  # year 1 or 9999 with an offset that leaves the calendar: stored as a version
            pass
    return "v:sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def iso_instant(value):
    m = ISO_TIME.fullmatch(value)
    if not m:
        return None
    year, month, day, hour, minute, second = (int(m.group(k) or 0) for k in range(1, 7))
    zone = m.group(8)
    try:
        if zone and zone != "Z":
            digits = zone[1:].replace(":", "")
            offset = datetime.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
            tz = datetime.timezone(offset if zone[0] == "+" else -offset)
        else:
            tz = datetime.timezone.utc  # no offset counts as UTC
        return datetime.datetime(year, month, day, hour, minute, second, tzinfo=tz)
    except ValueError:
        return None


def http_instant(value):
    if not HTTP_TIME.fullmatch(value):  # the parser is lenient: it reads 'mon 2 feb 3 4:5' as a date
        return None
    import email.utils
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):  # 3.9 raises TypeError for what it cannot parse, 3.10+ ValueError
        return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)  # never astimezone()


def write_observation(root, gate_id, obs):
    text = json.dumps(obs, ensure_ascii=False) + "\n"
    h8 = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    folder = obs_dir(root, gate_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = "%s.%s.%s.json" % (obs["source"], obs["at"].replace("-", "").replace(":", ""), h8)
    write_atomic(folder / name, text)  # the name comes from the content: a second write puts the same bytes in place


def cmd_observe(root, conf, args):
    opts, positional = parse(args, ("--field", "--mark", "--declare", "--request"))
    if len(positional) != 2:
        raise Usage("give a gate id and a source id")
    gate_id, source_id = positional
    reading, stating = ("--field" in opts or "--mark" in opts), ("--declare" in opts or "--request" in opts)
    if reading == stating:
        raise Usage("use either --field and --mark, or --declare and --request")
    if reading and not ("--field" in opts and "--mark" in opts):
        raise Usage("--field and --mark go together")
    if stating and opts.get("--declare") not in ("unchanged", "changed"):
        raise Usage("--declare must be unchanged or changed")
    if stating and "--request" not in opts:
        raise Usage("--declare needs --request with the person's words")
    path = existing(root, gate_id)
    defined = sources_of(meta_of(path.read_text(encoding="utf-8", errors="replace")))[0]
    src = next((s for s in defined if s["id"] == source_id), None)
    if src is None:
        raise Refused("gate '%s' has no valid source '%s'. 'hg-tool gate list --json' shows its sources."
                      % (gate_id, one_line(source_id)[:60]))
    moment = now()
    at = utc_text(moment)
    limit = kr.source_check_days(conf)
    approvals = read_approvals(root, gate_id) or []
    observations = read_observations(root, gate_id, moment)[0].get(source_id, [])
    newest, tool = source_track(src, base_of(src, approved_sources(approvals)), observations)[1:]
    known = tool[-1] if tool else None
    obs = {"at": at, "source": source_id, "of": fingerprint(src["url"], src["watch"])}
    if reading:
        if not src["watch"]:
            raise Refused("only a person's statement counts for this source; use --declare.")
        if opts["--field"] != src["watch"]:
            raise Refused("this source's mark is its `%s`; read that field." % src["watch"])
        mark = normalize_mark(opts["--mark"], src["watch"], moment)
        if known is None:
            outcome = "first"
        elif mark != known:
            outcome = "changed"
            if mark.startswith("t:") and known.startswith("t:") and mark < known:
                print("gate: note: this time is earlier than the last one recorded. Check that you read %s." % src["watch"],
                      file=sys.stderr)
        elif age_days(newest["at"], moment.date()) >= max(1, limit // 2):
            outcome = "same"
        else:
            print("unchanged\t%s\t%s" % (gate_id, source_id))
            return
        obs.update(kind="read", field=src["watch"], mark=mark)
    else:
        request = one_line(opts["--request"])
        if not request:
            raise Refused("--request is empty. Pass the person's own words.")
        if len(request) > REQUEST_MAX:
            raise Refused("--request is longer than %d characters. Pass the person's words in short." % REQUEST_MAX)
        if link_findings(request, repo_scan_cfg(root)):
            raise Refused("--request holds something the scanner reports (a key, a token or an address). "
                          "Pass the person's words without it: an observation cannot be edited afterwards.")
        if opts["--declare"] == "unchanged":
            outcome, mark = "same", (newest["mark"] if newest else "p:seen")
        else:
            outcome, mark = "changed", "p:changed:" + at
        obs.update(kind=opts["--declare"], mark=mark, request=request)
    before = load(root, path, conf)["status"]
    write_observation(root, gate_id, obs)
    print("recorded\t%s\t%s\t%s" % (gate_id, source_id, outcome))
    after = load(root, path, conf)
    if after["status"] == "reopened" and before != "reopened":
        import today_data  # imported here: today_data imports this module
        print(today_data.changed_line(after["title"], source_id, is_polish(conf)))


def cmd_note(root, conf, args):
    opts, positional = parse(args, ("--text", "--author"))
    path = existing(root, need_id(positional))
    text, author = one_line(opts.get("--text", "")), one_line(opts.get("--author", ""))
    if not text or not author:
        raise Usage("--text and --author are required")
    entry = "- %s, %s: %s" % (kr.local_now(conf["TIMEZONE"]).strftime("%Y-%m-%d %H:%M"), author, text)
    lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    heads = [k for k, ln in enumerate(lines) if ln.startswith("## ") and ln[3:].strip() in NEXT_HEADINGS]
    if not heads:
        lines += ["", "## %s" % NEXT_HEADINGS[0 if is_polish(conf) else 1]]
        heads = [len(lines) - 1]
    start = heads[-1]
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    insert = ["", entry] if end == start + 1 else [entry]
    tail = [""] + lines[end:] if end < len(lines) else []
    write_atomic(path, "\n".join(lines[:end] + insert + tail) + "\n")
    print("noted")


COMMANDS = {"new": cmd_new, "list": cmd_list, "approve": cmd_approve, "note": cmd_note, "source": cmd_source,
            "observe": cmd_observe}


def main(argv):
    kr.stdio_utf8()
    if not argv or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    root = kr.kit_root().resolve()
    try:
        COMMANDS[argv[0]](root, kr.load_conf(root), argv[1:])
    except Usage as exc:
        print("gate: %s" % exc, file=sys.stderr)
        return 2
    except Refused as exc:
        print("gate: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
