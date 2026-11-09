#!/usr/bin/env python3
"""log_append.py - the only writer of the shared event log (default vault/log.jsonl).

Usage:
  hg-tool log --op <op> --agent <id> [--project <slug>] [--status applied|queued|skipped|failed|blocked]
              [--inputs a,b] [--outputs c,d] [--note "..."] [--allow-custom-op]

Appends one JSON line {ts,op,agent,project,inputs[],outputs[],status,note}. ts is UTC ISO-8601.
Defaults: project=cross, status=applied. Ops outside the fixed vocabulary (vault/schema.md) are
rejected unless --allow-custom-op is given. People are never named here: see the gate records.

Concurrency: mkdir lock at .claude/state/locks/log.lock, retried for about 5 s, broken when older
than 60 s. After the append the last line is parsed back; a bad line fails the call.
Rotation: past LOG_ROTATE_BYTES the file moves to <dir of log>/log/YYYY.jsonl (YYYY-2.jsonl ...)
and a fresh file starts with an op:archive line.

Exit: 0 appended, 1 lock timeout or write/validation failure, 2 usage error.
"""
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402

OPS = set(("ingest rejected_ingest_scope lint query file_back dedup memory_distill supersede archive gc "
           "conflict heartbeat routine_run routine_failed playbook_run task_create task_done task_blocked "
           "notify init gate_new gate_approve").split())
STATUSES = {"applied", "queued", "skipped", "failed", "blocked"}
VALUE_FLAGS = {"--op": "op", "--agent": "agent", "--project": "project", "--status": "status",
               "--inputs": "inputs", "--outputs": "outputs", "--note": "note"}


def fail(message, code):
    print("log-append: %s" % message, file=sys.stderr)
    return code


def parse(argv):
    opts = {"op": "", "agent": "", "project": "cross", "status": "applied", "inputs": "", "outputs": "", "note": "", "custom": False}
    args = list(argv)
    while args:
        flag = args.pop(0)
        if flag in VALUE_FLAGS:
            if not args:
                raise ValueError("%s needs a value" % flag)
            opts[VALUE_FLAGS[flag]] = args.pop(0)
        elif flag == "--allow-custom-op":
            opts["custom"] = True
        else:
            raise ValueError("unknown argument '%s'" % flag)
    return opts


def build_line(op, agent, project, status, inputs, outputs, note):
    split = lambda s: [x for x in s.split(",") if x]  # noqa: E731
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.dumps({"ts": ts, "op": op, "agent": agent, "project": project, "inputs": split(inputs),
                       "outputs": split(outputs), "status": status, "note": note},
                      ensure_ascii=False, separators=(",", ":"))


def take_lock(lock):
    tries = 0
    while True:
        try:
            os.mkdir(lock)
            return True
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue
            if age > 60:
                try:
                    os.rmdir(lock)
                except OSError:
                    pass
                continue
            tries += 1
            if tries >= 50:
                return False
            time.sleep(0.1)


def rotate(log, root, limit):
    archive_dir = log.parent / "log"
    archive_dir.mkdir(parents=True, exist_ok=True)
    year = datetime.datetime.now(datetime.timezone.utc).strftime("%Y")
    dest, k = archive_dir / (year + ".jsonl"), 2
    while dest.exists():
        dest, k = archive_dir / ("%s-%d.jsonl" % (year, k)), k + 1
    log.rename(dest)
    line = build_line("archive", "log-append", "cross", "applied", log.relative_to(root).as_posix(),
                      dest.relative_to(root).as_posix(), "rotated at %d bytes" % limit)
    with open(log, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def main(argv):
    kr.stdio_utf8()
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        o = parse(argv)
    except ValueError as exc:
        return fail(str(exc), 2)
    if not o["op"] or not o["agent"]:
        return fail("--op and --agent are required", 2)
    if re.search(r"[^a-z0-9_]", o["op"]):
        return fail("op must be snake_case", 2)
    if not o["custom"] and o["op"] not in OPS:
        return fail("unknown op '%s' (see vault/schema.md; --allow-custom-op to force)" % o["op"], 2)
    if o["status"] not in STATUSES:
        return fail("bad --status '%s'" % o["status"], 2)

    root = kr.kit_root()
    conf = kr.load_conf(root)
    log = root / conf["LOG_FILE"]
    limit = int(conf["LOG_ROTATE_BYTES"])
    lock = root / ".claude" / "state" / "locks" / "log.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    line = build_line(o["op"], o["agent"], o["project"], o["status"], o["inputs"], o["outputs"], o["note"])

    if not take_lock(lock):
        return fail("lock busy (%s), giving up after about 5 s" % lock, 1)
    try:
        if log.exists() and log.stat().st_size > limit:
            rotate(log, root, limit)
        with open(log, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
        with open(log, encoding="utf-8") as fh:
            last = fh.read().rstrip("\n").rsplit("\n", 1)[-1]
        json.loads(last)
    except (OSError, ValueError) as exc:
        return fail("write failed: %s" % exc, 1)
    finally:
        os.rmdir(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
