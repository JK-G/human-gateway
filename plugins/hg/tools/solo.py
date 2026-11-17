#!/usr/bin/env python3
"""solo.py - the mode of a folder, and what a personal folder needs to know about where it lies.

A folder is personal when .claude/hg.json parses as an object whose "mode" is exactly the string "personal".
Anything else, a missing key, another value or a broken file, is shared: every folder made before this key
existed stays what it was. Only `hg-tool setup --personal` writes the value; no tool changes it.

Usage: hg-tool mode       prints personal, shared, or none when .claude/hg.json is missing. Always exits 0.

Not one of the files CI copies, so a change here never makes a shared folder's copies differ. Imports the
standard library and kit_registry only, and starts no process except where a function says so.
"""
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_registry as kr  # noqa: E402

MODES = ("personal", "shared")
PLACES_FILE = "places"
# Written by setup --personal, kept out of git with .gateway/. It outlives a hand edit of the mode key: a folder set up
# as personal holds pages that name people and were never cleaned, so it is not published (publish.py, doctor.py).
PERSONAL_MARK = (".gateway", "personal")
MARK_TEXT = "This folder was set up as one person's own folder.\n"
# Files every session loads or the librarian obeys, which nothing writes in a personal folder's daily work. No preview
# shows a change to them afterwards, so Claude Code asks first there: an ask rule wins over the two allow rules.
PERSONAL_ASK = ["Edit(vault/CLAUDE.md)", "Edit(vault/schema.md)", "Edit(vault/cleaning.md)"]
# What the person reads where no place for notes is set up (today-data, and through it the skills).
NOT_SET_UP = {
    "pl": ("Ten folder nie jest jeszcze miejscem na notatki. Napisz „zacznij”, a je tu założę.",
           "Ten folder nie jest miejscem na notatki. Twoje notatki są w folderze {path}: otwórz go w aplikacji i tam "
           "napisz „zapisz”."),
    "en": ("This folder is not a place for notes yet. Write \"start\" and I will set one up here.",
           "This folder is not a place for notes. Your notes are in the folder {path}: open it in the app and write "
           "\"keep this\" there."),
}
SLUG_MAX = 40
CLOUD_PARTS = ("dropbox", "google drive", "googledrive", "icloud drive", "iclouddrive")
CLOUD_ENV = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")


# ---- the mode ---------------------------------------------------------------------------------------

def mode_of(data):
    """'personal' only for a parsed hg.json object whose mode is exactly that string."""
    return "personal" if isinstance(data, dict) and data.get("mode") == "personal" else "shared"


def mode(root=None):
    return mode_of(kr.raw_config(root))


def is_personal(root=None):
    return mode(root) == "personal"


def state(root=None):
    """'personal', 'shared', or 'none' when the folder has no .claude/hg.json."""
    if not kr.kit_root(root).joinpath(*kr.CONFIG_PARTS).is_file():
        return "none"
    return mode(root)


def was_personal(root=None):
    """The folder was set up as personal, whatever its mode key says now."""
    return kr.kit_root(root).joinpath(*PERSONAL_MARK).is_file()


def not_set_up(root=None):
    """today-data in a folder with no .claude/hg.json: the places for notes and the sentence to say, in both
    languages (the first place, or an offer to set one up here)."""
    found = places(exclude=kr.kit_root(root))
    say = {lang: (texts[1].format(path=found[0]) if found else texts[0]) for lang, texts in NOT_SET_UP.items()}
    return {"mode": "none", "places": found, "say": say}


# ---- where git is and is not used ----------------------------------------------------------------------

def repo_dir(root):
    """root when root/.git exists (a folder or a file), else None. A .git higher up is never the folder's own
    repository. No git process is started."""
    root = Path(root)
    return root if os.path.lexists(str(root / ".git")) else None


def repo_above(root):
    """The nearest folder strictly above root that holds .git, or None. No git process is started."""
    try:
        here = Path(root).resolve()
    except OSError:
        here = Path(os.path.abspath(str(root)))
    for parent in here.parents:
        if os.path.lexists(str(parent / ".git")):
            return parent
    return None


def git_usable():
    """git is on the path, and on macOS the developer tools are installed: without them /usr/bin/git is a stub that
    opens an install dialog."""
    if not shutil.which("git"):
        return False
    if sys.platform == "darwin" and shutil.which("xcode-select"):
        try:
            out = subprocess.run(["xcode-select", "-p"], capture_output=True)
        except OSError:
            return False
        return out.returncode == 0
    return True


# ---- names ---------------------------------------------------------------------------------------------

def fold(text):
    """Case and diacritics folded: ł and Ł become l, combining marks are dropped."""
    text = str(text).replace("ł", "l").replace("Ł", "L")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def slugify(text, limit=SLUG_MAX):
    """ł to l, NFKD, combining marks dropped, lower case, runs of anything but a-z0-9 become '-', '-' stripped, cut
    at `limit` characters on a '-' boundary. Empty, 'cross' or 'unknown' gives 'notes'."""
    slug = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
    if len(slug) > limit:
        cut = slug[:limit + 1]
        slug = cut[:cut.rfind("-")] if "-" in cut else slug[:limit]
        slug = slug.strip("-")
    return slug if slug and slug not in ("cross", "unknown") else "notes"


# ---- where the folder lies ------------------------------------------------------------------------------

def _same_or_under(path, top):
    try:
        path.relative_to(top)
        return True
    except ValueError:
        return False


def _norm(path):
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(os.path.abspath(str(path)))
    return Path(os.path.normcase(str(resolved)))


def sync_root(root):
    """True when the folder lies under a folder this computer is known to copy to a cloud. Decided from names and
    the environment only; nothing is started. True when one of the environment variables OneDrive,
    OneDriveCommercial, OneDriveConsumer names a folder at or above root; or a part of root's path starts with
    'OneDrive' or is 'Dropbox', 'Google Drive', 'GoogleDrive', 'iCloud Drive' or 'iCloudDrive' (case ignored); or,
    on macOS, root lies under ~/Library/Mobile Documents or ~/Library/CloudStorage."""
    here = _norm(root)
    for name in CLOUD_ENV:
        value = os.environ.get(name, "").strip()
        if value and _same_or_under(here, _norm(value)):
            return True
    for part in Path(os.path.abspath(str(root))).parts:
        low = part.casefold()
        if low.startswith("onedrive") or low in CLOUD_PARTS:
            return True
    if sys.platform == "darwin":
        home = Path.home()
        for top in (home / "Library" / "Mobile Documents", home / "Library" / "CloudStorage"):
            if _same_or_under(here, _norm(top)):
                return True
    return False


# ---- the places for notes on this computer ---------------------------------------------------------------
# One text file in the plugin's per-machine data folder, which bin/hg-tool exports as HG_DATA. One absolute folder
# path per line. A line counts only while that folder's hg.json still says personal. With HG_DATA unset (a tool
# run directly) nothing is read or written.

def places_file():
    data = os.environ.get("HG_DATA", "").strip()
    return Path(data) / PLACES_FILE if data else None


def _key(path):
    return os.path.normcase(str(path)).replace("\\", "/").rstrip("/")


def places(exclude=None):
    """The folders recorded as places for notes that are still personal, oldest first, without `exclude`."""
    path = places_file()
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    skip = _key(_norm(exclude)) if exclude is not None else None
    found, seen = [], set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        key = _key(_norm(line))
        if key in seen or key == skip:
            continue
        seen.add(key)
        if is_personal(Path(line)):
            found.append(line)
    return found


def remember_place(root):
    """Append the folder to the places file, once. Returns True when a line was written."""
    path = places_file()
    if path is None:
        return False
    here = Path(root).resolve().as_posix()
    try:
        have = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except (OSError, UnicodeDecodeError):
        have = []
    if any(_key(_norm(line.strip())) == _key(_norm(here)) for line in have if line.strip()):
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(here + "\n")
    except OSError:
        return False
    return True


# ---- lines for .git/info/exclude ------------------------------------------------------------------------

EXCLUDE_HEADER = "# kept out by hg: files at the top of this folder that hg did not create"


def exclude_line(name):
    """'/<name>' with a backslash before the characters git reads as pattern syntax, or None for a name git cannot
    hold on one line."""
    if "\n" in name or "\r" in name:
        return None
    return "/" + re.sub(r"([#!\[\]*?\\ ])", r"\\\1", name)


def exclude_lines(names):
    """([lines], [names skipped because they hold a line break])."""
    lines, skipped = [], []
    for name in names:
        line = exclude_line(name)
        if line is None:
            skipped.append(name)
        else:
            lines.append(line)
    return lines, skipped


def write_exclude(root, names):
    """Append the names to the folder's own .git/info/exclude, once each. Returns (written, skipped names)."""
    lines, skipped = exclude_lines(names)
    if not lines:
        return 0, skipped
    path = Path(root) / ".git" / "info" / "exclude"
    try:
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        text = ""
    have = {ln.strip() for ln in text.splitlines()}
    new = [ln for ln in lines if ln not in have]
    if not new:
        return 0, skipped
    block = ("" if not text or text.endswith("\n") else "\n") + ("" if EXCLUDE_HEADER in have else EXCLUDE_HEADER + "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(block + "\n".join(new) + "\n")
    return len(new), skipped


def main(argv):
    kr.stdio_utf8()
    if argv != ["mode"]:
        print(__doc__, file=sys.stderr)
        return 2
    print(state())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
