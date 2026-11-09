#!/usr/bin/env python3
"""gate.py - approvals that reopen when their inputs change. The only writer of gates/.

Usage:
  hg-tool gate new <id> --title T --project P --accountable EMAIL --input PATH [--input PATH ...] [--summary TEXT]
  hg-tool gate list [--json]
  hg-tool gate approve <id> --via person|agent --request "the person's words"
  hg-tool gate note <id> --text TEXT --author TEXT

Input paths are relative to the repo root, or absolute as D:\\x, D:/x or /d/x.

gates/<id>.md is the readable record. gates/<id>.lock.json holds {"approvals": [...]}, to which an
approval is only ever appended. The status (draft, approved, reopened) is computed from the current
inputs and is never stored, so reading it writes nothing. The list of inputs is part of what is
approved: adding or removing one reopens the gate, and so does changing the accountable person, whom
each approval records. A note does not.

'by' comes from git config user.email, ignoring variables that inject config for a single call. There is
deliberately no argument for it. Git does not verify the address, so it is a declaration, like 'via'.
Exit: 0 ok, 1 refused, 2 usage error.
"""
import datetime
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
    return approvals


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


def load(root, path):
    gate_id = path.stem
    try:
        meta = meta_of(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        meta = {}
    listed, accountable = terms_of(meta)
    inputs = [rel for rel in listed if valid_input(rel)]
    invalid = [rel for rel in listed if not valid_input(rel)]
    flagged = [{"path": rel, "why": "invalid"} for rel in invalid]
    approvals = read_approvals(root, gate_id)
    if approvals is None:  # an unreadable record never counts as an approval
        status, changed, approvals = "reopened", [{"path": lock_path(root, gate_id).relative_to(root).as_posix(), "why": "unreadable"}], []
    elif not approvals:
        status, changed = "draft", flagged
    else:
        changed = differences(gate_id, approvals[-1], current_digests(root, inputs), accountable) + flagged
        status = "reopened" if changed else "approved"
    return {"id": gate_id, "title": str(meta.get("title") or gate_id), "project": str(meta.get("project") or "cross"),
            "accountable": accountable, "inputs": inputs, "invalid": invalid, "status": status,
            "changed": changed, "approvals": approvals}


def is_gate_file(path):
    return path.name.lower() != "readme.md" and bool(ID_RE.fullmatch(path.stem))


def all_gates(root):
    folder = root / GATES_DIR
    if not folder.is_dir():
        return []
    return [load(root, p) for p in sorted(folder.glob("*.md")) if is_gate_file(p)]


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


def render_gate(gate_id, title, project, accountable, inputs, summary, polish):
    front = ["---", "id: %s" % gate_id, "title: %s" % scalar(title), "project: %s" % scalar(project),
             "accountable: %s" % scalar(accountable), "inputs:"] + ["  - %s" % scalar(i) for i in inputs] + ["---"]
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


def cmd_new(root, conf, args):
    opts, positional = parse(args, ("--title", "--project", "--accountable", "--summary"), repeated=("--input",))
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
    inputs = list(dict.fromkeys(repo_relative(root, raw) for raw in opts["--input"]))
    path = gate_path(root, gate_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_gate(gate_id, title, project, accountable, inputs, opts.get("--summary", ""), is_polish(conf))
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


def refuse_unless_committed(root, gate_id, gate):
    """Compares content with HEAD instead of asking git status, which trusts git update-index flags."""
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
        inputs, accountable = terms_of(meta_of(blob.decode("utf-8", errors="replace")))
        if sorted(inputs) != sorted(gate["inputs"] + gate["invalid"]) or accountable != gate["accountable"]:
            problems.append("gates/%s.md has a new input list or accountable person that is not committed. Commit it or restore it first." % gate_id)
    if problems:
        raise Refused("\n".join(problems))


def cmd_approve(root, conf, args):
    opts, positional = parse(args, ("--via", "--request"))
    gate_id = need_id(positional)
    if opts.get("--via") not in VIA:
        raise Usage("--via must be person or agent")
    if "--request" not in opts:
        raise Usage("--request is required")
    gate = load(root, existing(root, gate_id))
    request = opts["--request"].strip()
    if not request:
        raise Refused("--request is empty. Pass the person's own words.")
    if not gate["inputs"] and not gate["invalid"]:
        raise Refused("gate '%s' lists no inputs, so there is nothing to approve." % gate_id)
    approvals = read_approvals(root, gate_id)
    if approvals is None:
        raise Refused("%s cannot be read. Approvals are only appended, so repair it with git first."
                      % lock_path(root, gate_id).relative_to(root).as_posix())
    refuse_unless_committed(root, gate_id, gate)
    by = git_email(root)
    if not by:
        raise Refused("git has no user.email here, and an approval must say who made it. Set it with git config.")
    digests = current_digests(root, gate["inputs"])
    since_last = differences(gate_id, approvals[-1], digests, gate["accountable"]) if approvals else []
    at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    approvals.append({"at": at, "by": by, "accountable": gate["accountable"], "via": opts["--via"], "request": request,
                      "inputs": digests, "changed_since_last": since_last})
    lock = lock_path(root, gate_id)
    write_atomic(lock, json.dumps({"approvals": approvals}, ensure_ascii=False, indent=2) + "\n")
    note = "via=%s" % opts["--via"] + ("; changed: %s" % changed_text(since_last) if since_last else "")
    log_op("gate_approve", gate["project"], gate["inputs"], lock.relative_to(root).as_posix(), note)
    print("approved %s (via %s)" % (gate_id, opts["--via"]))


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


COMMANDS = {"new": cmd_new, "list": cmd_list, "approve": cmd_approve, "note": cmd_note}


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
