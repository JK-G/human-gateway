#!/usr/bin/env python3
"""canonicalize.py - stable canonical form of a wiki page, for page hashing.

Change plans carry `page_hash_expected`; the librarian re-hashes the page right
before applying an edit and aborts that edit on mismatch. The hash must not move
when an editor merely reorders frontmatter keys, switches a list between flow and
block style, or saves with CRLF line endings, otherwise every plan goes stale for
cosmetic reasons (this happened with a notes app that reorders YAML on save).

Canonical form:
  - CRLF / CR -> LF, trailing whitespace stripped from every line
  - frontmatter parsed and re-emitted one `key: <json>` line per key, keys sorted
    (values as sorted-key JSON, so flow vs block lists hash the same)
  - leading blank lines of the body dropped, trailing blank lines collapsed,
    exactly one final newline
If the frontmatter cannot be parsed, its top-level key blocks are sorted textually.

Stdlib only. Parsing uses kit_registry.load_yaml (minimal parser; PyYAML only as
a fallback for exotic YAML), so the hash is identical with or without PyYAML.
file_digest() is what gates store: it uses the minimal parser alone, because a gate's status is
computed on several machines and in hooks that start Python without site-packages.

Usage:
  canonicalize.py <file>          print the canonical text
  canonicalize.py --hash <file>   print sha1:<40 hex> of the canonical text
  canonicalize.py --sha1 <file>   print the plain sha1 of the file's bytes
  canonicalize.py --plan-name <file>   rename a change plan to <first 12 hex of its sha1>.json, print the new path
Exit: 0 ok, 1 file missing, 2 usage error.
"""
import hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry  # noqa: E402

TEXT_SUFFIXES = (".md", ".markdown", ".txt")


def _textual_sort(fm_text):
    blocks, cur = [], []
    for line in fm_text.split("\n"):
        if line and not line[0].isspace() and not line.startswith("-") and cur:
            blocks.append("\n".join(cur))
            cur = []
        if line.strip():
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return "\n".join(sorted(blocks))


def canonical_str(raw, parse=kit_registry.load_yaml):
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = "\n".join(line.rstrip() for line in raw.split("\n"))
    fm_text, body, _ = kit_registry.split_frontmatter(raw)
    body = body.lstrip("\n").rstrip("\n")
    if fm_text is None:
        return body + "\n"
    try:
        data = parse(fm_text) if fm_text.strip() else {}
        if not isinstance(data, dict):
            raise kit_registry.RegistryError("not a mapping")
        fm_out = "\n".join(
            "%s: %s" % (k, json.dumps(data[k], sort_keys=True, ensure_ascii=False, default=str))
            for k in sorted(data))
    except (kit_registry.RegistryError, ValueError, IndexError, TypeError):
        fm_out = _textual_sort(fm_text)
    out = "---\n" + fm_out + ("\n" if fm_out else "") + "---\n"
    return out + (body + "\n" if body else "")


def canonical_text(path):
    return canonical_str(Path(path).read_bytes().decode("utf-8", errors="replace"))


def bytes_digest(data, name):
    """sha256 of a file's content, so a save with other line endings keeps the digest.

    Markdown and .txt hash their canonical text, any other UTF-8 text its text with LF line endings, and
    everything else its raw bytes. A file that is not valid UTF-8 counts as everything else: decoding it
    with errors=replace would turn different letters into the same replacement character and hide the change.
    """
    if b"\0" not in data:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            if Path(name).suffix.lower() in TEXT_SUFFIXES:
                text = canonical_str(text, kit_registry.parse_yaml)
            data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_digest(path):
    return bytes_digest(Path(path).read_bytes(), str(path))


def page_hash(path):
    return "sha1:" + hashlib.sha1(canonical_text(path).encode("utf-8")).hexdigest()


def main(argv):
    kit_registry.stdio_utf8()
    mode = None
    if argv and argv[0] in ("--hash", "--sha1", "--plan-name"):
        mode, argv = argv[0], argv[1:]
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    p = Path(argv[0])
    if not p.is_file():
        print("ERROR: %s not found" % p, file=sys.stderr)
        return 1
    if mode == "--sha1":
        print(hashlib.sha1(p.read_bytes()).hexdigest())
    elif mode == "--plan-name":
        target = p.with_name(hashlib.sha1(p.read_bytes()).hexdigest()[:12] + ".json")
        p.replace(target)
        print(target.as_posix())
    elif mode == "--hash":
        print(page_hash(p))
    else:
        sys.stdout.write(canonical_text(p))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
