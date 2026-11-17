#!/usr/bin/env python3
"""raw_ref.py - source references: how a tracked file names a raw file that stays on one machine.

Usage:
  hg-tool raw-ref <path>           the reference of a raw file on this machine
  hg-tool raw-ref --find <ref>     its repo-relative path
  hg-tool raw-ref --say <ref>      the sentence a reader is shown, in the content language
  hg-tool raw-ref --list [--json]  every raw file here: ref<TAB>path<TAB>cited|uncited

A reference is src:<kind>:<YYYY-MM-DD>:<h8>: the folder under vault/raw/<project>/, the date in the file's
name and the first 8 hex digits of the sha256 of its bytes. Raw files never change, so it is stable. It is
computed from the file and never stored, so a vault/raw/ folder copied to another computer resolves again.
A reference is not a path and never resolves in a colleague's clone.

In a personal folder (solo.py) --say names no repository: the file is on this computer, or it is gone.

--list prints paths. Its output is for the person's own session and never goes into a tracked file.
"cited" means a file under vault/wiki/ or vault/projects/ holds the reference as text.
Exit: 0 printed (--say also when the file is not here: the sentence says so), 1 refused, 2 usage error.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402
import scan  # noqa: E402

NAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*(\.[a-z0-9]+)?")
PROJECT_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
KIND_WORDS = {"meetings": ("spotkanie", "meeting"), "interviews": ("rozmowa", "interview"),
              "sources": ("dokument", "document"), "snapshots": ("zapis stanu", "snapshot")}
SAY_HERE = ("Źródło prywatne ({kind}, {date}). Plik jest na tym komputerze: {path}. W repozytorium go nie ma.",
            "Private source ({kind}, {date}). The file is on this computer: {path}. It is not in the repository.")
SAY_AWAY = ("Źródło prywatne ({kind}, {date}). Pliku nie ma w repozytorium ani na tym komputerze. Został u osoby, "
            "która go wniosła. Kto opublikował stronę, pokazuje historia zmian tej strony.",
            "Private source ({kind}, {date}). The file is not in the repository and not on this computer. It stayed "
            "with the person who brought it in. The page's change history shows who published the page.")
# A personal folder has no repository to compare with: the file is here or it is gone (solo.py).
SAY_PERSONAL_HERE = ("Źródło: {kind}, {date}. Plik jest na tym komputerze: {path}.",
                     "Source: {kind}, {date}. The file is on this computer: {path}.")
SAY_PERSONAL_AWAY = ("Źródło: {kind}, {date}. Pliku nie ma już na tym komputerze.",
                     "Source: {kind}, {date}. The file is no longer on this computer.")
CITED_DIRS = ("wiki", "projects")
CITED_MAX_BYTES = 5 * 1024 * 1024


def digest8(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:8]


def raw_base(root, conf):
    return root.joinpath(*Path(conf["VAULT_DIR"].strip("/"), "raw").parts)


def shape_of(root, conf, full):
    """(kind, date) when full is a file at vault/raw/<project>/<kind>/<date>-<slug>[.ext], else None."""
    try:
        rel = full.relative_to(raw_base(root, conf))
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) != 3 or not PROJECT_RE.fullmatch(parts[0]) or parts[1] not in kr.RAW_KINDS:
        return None
    m = NAME_RE.fullmatch(parts[2])
    if not m or not full.is_file() or os.path.islink(str(full)):
        return None
    return parts[1], m.group(1)


def ref_of(root, conf, path):
    """The reference of a raw file on this machine. Raises gate.Refused for anything else."""
    given = Path(scan.native_path(str(path).strip()))
    full = (given if given.is_absolute() else root / given).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        raise gate.Refused("%s is outside this workspace." % path)
    shape = shape_of(root, conf, full)
    if shape is None:
        raise gate.Refused("%s is not a raw file: a file in vault/raw/<project>/<kind>/ named YYYY-MM-DD-<slug>." % path)
    return "src:%s:%s:%s" % (shape[0], shape[1], digest8(full))


def parse_ref(ref):
    if not isinstance(ref, str) or not kr.SRC_REF_RE.fullmatch(ref):
        # The value is not repeated: it may be a raw file's name.
        raise gate.Refused("that is not a source reference (src:<kind>:<YYYY-MM-DD>:<8 hex digits>).")
    _, kind, date, h8 = ref.split(":")
    return kind, date, h8


def find(root, conf, ref):
    """Every repo-relative path on this machine whose reference is ref, sorted."""
    kind, date, h8 = parse_ref(ref)
    base = raw_base(root, conf)
    if not base.is_dir():
        return []
    hits = []
    for full in sorted(base.glob("*/%s/%s-*" % (kind, date))):
        if shape_of(root, conf, full) == (kind, date) and digest8(full) == h8:
            hits.append(full.relative_to(root).as_posix())
    return hits


def raw_files(root, conf):
    """[(ref or None, repo-relative path)] for every file under vault/raw/ but its README and a .gitkeep."""
    base = raw_base(root, conf)
    out = []
    if not base.is_dir():
        return out
    kept = {k.casefold() for k in kr.kept_files(conf)}
    for full in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = full.relative_to(root).as_posix()
        if rel.casefold() in kept or full.name == ".gitkeep":  # an empty placeholder an earlier setup made
            continue
        shape = shape_of(root, conf, full)
        out.append(("src:%s:%s:%s" % (shape[0], shape[1], digest8(full)) if shape else None, rel))
    return out


def refs_in(text):
    return [m.group(0) for m in kr.SRC_REF_RE.finditer(text)]


def cited_by(root, conf):
    """{reference: [repo-relative paths of the text files under vault/wiki/ or vault/projects/ that hold it]}, each
    list sorted."""
    found = {}
    vault = root / conf["VAULT_DIR"].strip("/")
    for name in CITED_DIRS:
        folder = vault / name
        if not folder.is_dir():
            continue
        for full in sorted(folder.rglob("*")):
            try:
                if not full.is_file() or full.stat().st_size > CITED_MAX_BYTES:
                    continue
                refs = set(refs_in(full.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
            rel = full.relative_to(root).as_posix()
            for ref in refs:
                found.setdefault(ref, []).append(rel)
    return found


def cited(root, conf):
    """Every reference that a text file under vault/wiki/ or vault/projects/ holds."""
    return set(cited_by(root, conf))


def say(root, conf, ref):
    kind, date, _ = parse_ref(ref)
    polish = gate.is_polish(conf)
    word = KIND_WORDS[kind][0 if polish else 1]
    hits = find(root, conf, ref)
    import solo  # imported here: the top-level imports of this file are tested
    here, away = (SAY_PERSONAL_HERE, SAY_PERSONAL_AWAY) if solo.is_personal(root) else (SAY_HERE, SAY_AWAY)
    if hits:
        return here[0 if polish else 1].format(kind=word, date=date, path=hits[0])
    return away[0 if polish else 1].format(kind=word, date=date)


def run(root, argv):
    conf = kr.load_conf(root)
    if len(argv) == 1 and not argv[0].startswith("--"):
        return [ref_of(root, conf, argv[0])]
    if len(argv) == 2 and argv[0] == "--find":
        hits = find(root, conf, argv[1])
        if not hits:
            raise gate.Refused("this source is not on this machine.")
        return hits
    if len(argv) == 2 and argv[0] == "--say":
        return [say(root, conf, argv[1])]
    if argv in (["--list"], ["--list", "--json"], ["--json", "--list"]):
        refs = cited(root, conf)
        rows = raw_files(root, conf)
        if "--json" in argv:
            return [json.dumps([{"ref": r or "", "path": p, "cited": bool(r and r in refs)} for r, p in rows],
                               ensure_ascii=False)]
        return ["%s\t%s\t%s" % (r or "", p, "cited" if r and r in refs else "uncited") for r, p in rows]
    raise gate.Usage("see hg-tool raw-ref --help")


def main(argv):
    kr.stdio_utf8()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        for line in run(kr.kit_root().resolve(), list(argv)):
            print(line)
    except gate.Usage as exc:
        print("raw-ref: %s" % exc, file=sys.stderr)
        return 2
    except (gate.Refused, kr.RegistryError) as exc:
        print("raw-ref: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        print("raw-ref: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
