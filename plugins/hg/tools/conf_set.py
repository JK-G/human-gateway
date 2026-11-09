#!/usr/bin/env python3
"""conf_set.py - change one allowed key of .claude/hg.json and keep everything else.

Usage: hg-tool conf-set readers "role, role"
       hg-tool conf-set project <slug>

An agent's Edit in .claude/ prompts the person, so what /hg:init saves goes through here.
readers is stored as a list of roles, because hg.json is tracked and must not name people.
project appends a kebab-case slug to projects, once.
Exit: 0 ok, 1 refused, 2 usage error.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

ALLOWED = ("readers", "project")


def roles(raw):
    cleaned = (" ".join(part.split()) for part in raw.split(","))
    return list(dict.fromkeys(part for part in cleaned if part))


def main(argv):
    kr.stdio_utf8()
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    key, raw = argv
    if key not in ALLOWED:
        print("conf-set: '%s' cannot be set here. Allowed: %s." % (key, ", ".join(ALLOWED)), file=sys.stderr)
        return 1
    if key == "project":
        value = [raw.strip()]
        if not value[0]:
            print("conf-set: give a project slug.", file=sys.stderr)
            return 2
        if not kr.valid_project_slug(value[0]):
            print("conf-set: a project is a kebab-case slug of at most 40 characters, and not cross or unknown.", file=sys.stderr)
            return 1
    else:
        value = roles(raw)
        if not value:
            print("conf-set: give at least one role.", file=sys.stderr)
            return 2
        if any("@" in role for role in value):
            print("conf-set: readers are roles, not addresses.", file=sys.stderr)
            return 1
    path = kr.kit_root().joinpath(*kr.CONFIG_PARTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        print("conf-set: .claude/hg.json is missing. Run /hg:setup.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print("conf-set: .claude/hg.json is unreadable and was not changed: %s" % exc, file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("conf-set: .claude/hg.json is not an object and was not changed.", file=sys.stderr)
        return 1
    if key == "project":
        known = data.get("projects", [])
        known = known.split() if isinstance(known, str) else known
        if not isinstance(known, list):
            print("conf-set: projects in .claude/hg.json is not a list and was not changed.", file=sys.stderr)
            return 1
        if value[0] in known:
            print("%s\t%s" % (key, value[0]))
            return 0
        data["projects"] = known + value
    else:
        data[key] = value
    gate.write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("%s\t%s" % (key, ", ".join(value)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
