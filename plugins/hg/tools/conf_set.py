#!/usr/bin/env python3
"""conf_set.py - change one allowed key of .claude/hg.json and keep everything else.

Usage: hg-tool conf-set readers "role, role"
       hg-tool conf-set project <slug>
       hg-tool conf-set word '<entry>'

An agent's Edit in .claude/ prompts the person, so what /hg:init saves goes through here.
readers is stored as a list of roles, because hg.json is tracked and must not name people.
project appends a kebab-case slug to projects, once.
word appends one entry to publish.words, once: a word, a stem ending in * (at least 3 characters before it) or a
phrase, 2 to 60 characters on one line. hg-tool publish check refuses a page that holds one. The list is tracked, so
everyone who can read the repository can read it.
language sets language.content, in a personal folder only (hg-tool conf-set language <code>), and prints a context
line for the model with the new language. A shared folder refuses it as any other key.
Exit: 0 ok, 1 refused, 2 usage error.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402

ALLOWED = ("readers", "project", "word")
PERSONAL_ONLY = ("language",)
LANGUAGE_RE = r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*"


def append_project(path, slug):
    """Append a slug to projects in the hg.json at path, once. Returns None when done, or the reason it was not.
    hg-tool setup --focus uses it too."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return ".claude/hg.json is missing. Run /hg:setup."
    except (OSError, ValueError) as exc:
        return ".claude/hg.json is unreadable and was not changed: %s" % exc
    if not isinstance(data, dict):
        return ".claude/hg.json is not an object and was not changed."
    known = data.get("projects", [])
    known = known.split() if isinstance(known, str) else known
    if not isinstance(known, list):
        return "projects in .claude/hg.json is not a list and was not changed."
    if slug in known:
        return None
    data["projects"] = known + [slug]
    gate.write_atomic(Path(path), json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return None


def set_language(raw):
    """language.content of a personal folder."""
    import re  # imported here: the top-level imports of this file are tested
    code = raw.strip()
    if not code:
        print("conf-set: give a language code such as pl or en.", file=sys.stderr)
        return 2
    if not re.fullmatch(LANGUAGE_RE, code):
        print("conf-set: a language is a code such as pl or en.", file=sys.stderr)
        return 1
    path = kr.kit_root().joinpath(*kr.CONFIG_PARTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print("conf-set: .claude/hg.json is unreadable and was not changed: %s" % exc, file=sys.stderr)
        return 1
    language = data.get("language", {}) if isinstance(data, dict) else None
    if not isinstance(language, dict):
        print("conf-set: language in .claude/hg.json is not an object and was not changed.", file=sys.stderr)
        return 1
    data["language"] = dict(language, content=code)
    gate.write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("language\t%s" % code)
    print("context\tWrite to the person in %s." % code)
    return 0


def roles(raw):
    cleaned = (" ".join(part.split()) for part in raw.split(","))
    return list(dict.fromkeys(part for part in cleaned if part))


def main(argv):
    kr.stdio_utf8()
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    key, raw = argv
    if key in PERSONAL_ONLY:
        import solo  # imported here: the top-level imports of this file are tested
        if solo.is_personal():
            return set_language(raw)
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
    elif key == "word":
        value = [raw.strip()]
        if not value[0]:
            print("conf-set: give a word.", file=sys.stderr)
            return 2
        if not kr.valid_publish_word(value[0]):
            print("conf-set: a word is 2 to 60 characters on one line; a stem ends in * after at least 3 characters, "
                  "and no other * is allowed.", file=sys.stderr)
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
    if key == "word":
        section = data.get("publish", {})
        words = section.get("words", []) if isinstance(section, dict) else None
        if not isinstance(words, list):
            print("conf-set: publish.words in .claude/hg.json is not a list and was not changed.", file=sys.stderr)
            return 1
        if value[0] in words:
            print("%s	%s" % (key, value[0]))
            return 0
        data["publish"] = dict(section, words=words + value)
    elif key == "project":
        problem = append_project(path, value[0])
        if problem:
            print("conf-set: %s" % problem, file=sys.stderr)
            return 1
        print("%s\t%s" % (key, value[0]))
        return 0
    else:
        data[key] = value
    gate.write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("%s\t%s" % (key, ", ".join(value)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
