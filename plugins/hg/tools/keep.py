#!/usr/bin/env python3
"""keep.py - keep a note, a link or a file in one step, and say what was kept.

Usage:
  hg-tool keep <file> [--title T] [--link URL [--unread]] [--kind K] [--project P] [--date YYYY-MM-DD]
  hg-tool keep --link URL [--title T]        an address nobody could read, with no words about it
  hg-tool keep --rule '<text>'               one line for CLAUDE.local.md, the person's own rules
  hg-tool keep --status <ref>                whether a page cites the source, with the sentence to copy
  hg-tool keep --list [--json] [--days N]    what was kept, newest first

<file> is one of three kinds, and the tool decides which; no flag does:
  capture  vault/inbox/keep-*.md, written by the keep skill for this call (or by this tool for --link alone). A secret
           in it is cut out and the person is told; the file is deleted after the call, kept or refused.
  own      any other file in vault/inbox/ or intake/. Never changed; it leaves its folder only when it was kept.
  copied   a file outside this folder, or inside it but outside hg's own folders. Copied, never touched.
Anything else inside the folder (a page, a raw file, .claude/, .gateway/, .git/) is refused: it is hg's own.

A capture, and an own or copied .md or .txt file that reads as plain UTF-8 and is at most 1 MB, is wrapped: a copy
gets the frontmatter hg-tool keep writes (source_type, captured, origin, project, title, link, link_read) and goes in.
Every other file is kept byte for byte. Then hg-tool raw-add brings it into vault/raw/ with the same scan and the
same privacy rule as always. A secret in an own or copied file refuses the file whole.

What would get the reference of a raw file already here (the same bytes, kind and date) is not kept a second time:
the output names the earlier file, and has no next line when a page already cites it.

Output, tab-separated: kept<TAB><path><TAB><ref><TAB>text|link|address|stub, say lines, next<TAB>ingest<TAB><path>.
A refusal: refused<TAB>secret|link|link-shape|missing|place|setup|other, then say lines (setup: place lines). In a
folder that is not set up, a capture the skill wrote there is deleted, with vault/inbox/ and vault/ when then empty.
Nothing else goes to stdout; notes for the model go to stderr. The output of --list and --status holds private
paths and titles: it is for the person's own session and never goes into a tracked file.
Exit: 0 kept or printed, 1 refused (nothing kept) or not a reference, 2 usage error.
"""
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402
import raw_add  # noqa: E402
import raw_ref  # noqa: E402
import scan  # noqa: E402
import solo  # noqa: E402
import today_data  # noqa: E402

WRAP_MAX = 1024 * 1024
TITLE_MAX = 80
SLUG_MAX = 48
RULE_MAX = 300
LATEST = 10
CUT = "[…]"
SINGULAR = {"meetings": "meeting", "interviews": "interview", "sources": "source", "snapshots": "snapshot"}
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
KEY_LINE = re.compile(r"[A-Za-z_][\w-]*:(?:\s|$)")
TOP_OWN = ("claude.md", "claude.local.md", "agents.md", "dashboard.md", ".gitignore", ".gitattributes")
HIDDEN_OWN = (".claude", ".gateway", ".git", "gates")
CACHE = (".gateway", "cache", "refs.json")
VALUES = ("--title", "--link", "--kind", "--project", "--date", "--status", "--rule", "--days")
FLAGS = ("--unread", "--list", "--json")

TEXT = {
    True: {
        "K1": "Zapisane: „{title}”. Notatka jest w tym folderze.",
        "K2": "Zapisane: „{title}”. Mam streszczenie tej strony i jej adres.",
        "K3": "Adres zapisany: „{title}”. Tej strony nie umiem teraz przeczytać, więc zostaje sam adres i Twoje słowa o nim.",
        "K4": "Plik zapisany: „{title}”. Plików tego rodzaju jeszcze nie umiem czytać, więc strona dostanie tylko krótki opis.",
        "K5": "Liczba pominiętych fragmentów, które wyglądają na hasło albo klucz: {n} ({masked}). Reszta notatki jest zapisana.",
        "K6": "Tego pliku nie zapisano: jest w nim coś, co wygląda na hasło albo klucz ({masked}). Usuń to z pliku i podaj "
              "go jeszcze raz.",
        "K6b": "Tej notatki nie zapisano: jest w niej coś, co wygląda na hasło albo klucz ({masked}). Usuń to i wklej ją "
               "jeszcze raz.",
        "K7a": "Gotowe. Powstała strona „{page}”.",
        "K7b": "Gotowe. Powstały strony: {n}.",
        "K7c": "Gotowe. Powstała strona „{page}” z krótkim opisem. Treści z pliku albo spod adresu na niej nie ma.",
        "K8": "Notatka jest zapisana, ale strony z niej jeszcze nie ma. Napisz „dokończ zapisane”, a ją dopiszę.",
        "K9": "Dopisane do Twoich zasad dla tego folderu.",
        "K10": "Tego adresu nie zapisano: jest w nim klucz albo inny poufny fragment. Podaj adres bez tej części.",
        "K10b": "Tego adresu nie umiem zapisać jako linku. Wklej go w treści notatki i napisz „zapisz”.",
        "K11": "Nie ma takiego pliku: {name}.",
        "K12": "Dział zobaczy tę stronę dopiero po publikacji.",
        "K14": "Ten plik jest już częścią Twoich notatek, więc nie zapisuję go drugi raz.",
        "K16": "Nie udało się zapisać tej notatki. Napisz „coś nie działa”, a sprawdzę dlaczego.",
        "T1a": "{date}: {title}. Strona: „{page}”.",
        "T1b": "{date}: {title}. Strony: {n}.",
        "T1c": "{date}: {title}. Strony jeszcze nie ma.",
        "T2": "Zapisane notatki bez strony: {n}. Napisz „dokończ zapisane”, a je dopiszę.",
        "note": "Notatka",
    },
    False: {
        "K1": 'Kept: "{title}". The note is in this folder.',
        "K2": 'Kept: "{title}". I have a summary of that page and its address.',
        "K3": 'Address kept: "{title}". I cannot read this page right now, so only the address and your words about it '
              'are kept.',
        "K4": 'File kept: "{title}". I cannot read files of this kind yet, so the page gets only a short description.',
        "K5": "Left out, because it looks like a password or a key: {n} ({masked}). The rest of the note is kept.",
        "K6": "This file was not kept: it holds something that looks like a password or a key ({masked}). Remove it "
              "from the file and give the file again.",
        "K6b": "This note was not kept: it holds something that looks like a password or a key ({masked}). Remove it "
               "and paste the note again.",
        "K7a": 'Done. The page "{page}" is written.',
        "K7b": "Done. Pages written: {n}.",
        "K7c": 'Done. The page "{page}" is written with a short description. It holds nothing from inside the file or '
               'the address.',
        "K8": 'The note is kept, but there is no page from it yet. Write "finish what I kept" and I will add it.',
        "K9": "Added to your rules for this folder.",
        "K10": "This address was not kept: it holds a key or another confidential part. Give the address without that "
               "part.",
        "K10b": 'I cannot keep this address as a link. Paste it inside a note and write "keep this".',
        "K11": "There is no such file: {name}.",
        "K12": "The department sees this page only after it is published.",
        "K14": "This file is already part of your notes, so it is not kept a second time.",
        "K16": 'This note could not be kept. Write "something is not working" and I will check why.',
        "T1a": '{date}: {title}. Page: "{page}".',
        "T1b": "{date}: {title}. Pages: {n}.",
        "T1c": "{date}: {title}. No page yet.",
        "T2": 'Kept notes with no page yet: {n}. Write "finish what I kept" and I will add them.',
        "note": "Note",
    },
}


class Refusal(Exception):
    """Nothing is kept: refused<TAB><reason>, the say lines, exit 1. detail goes to stderr for the model."""

    def __init__(self, reason, says, detail="", masked="", name=""):
        super().__init__(reason)
        self.reason, self.says, self.detail, self.masked, self.name = reason, says, detail, masked, name


def inline(text):
    return today_data.inline(str(text))


def one_line(text):
    return " ".join(str(text).split())


# ---- secrets -------------------------------------------------------------------------------------------

def scan_cfg(root):
    return gate.repo_scan_cfg(root) or {"emails": set(), "domains": set(), "patterns": [], "vault": "vault"}


def secret_values(text, cfg):
    """The raw values the scanner reports as secrets, in the order found, each once. The same rules as
    hg-tool scan and raw-add, line by line."""
    found = []
    for line in text.split("\n"):
        scan.scan_line(line.rstrip("\r"), cfg, lambda kind, rule, value: found.append(value) if kind == "secret" else None)
    seen, out = set(), []
    for value in found:
        if value.strip() and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def without_contacts(text, cfg):
    """A title with each contact detail masked: the title is printed and listed, the note itself keeps them."""
    found = []
    scan.scan_line(text, cfg, lambda kind, rule, value: found.append(value) if kind == "pii" else None)
    for value in sorted(set(found), key=len, reverse=True):
        text = text.replace(value, scan.mask("pii", value))
    return text


def masked(values):
    return ", ".join(scan.mask("secret", v) for v in values) or "***"


def cut_secrets(text, values):
    """Each value replaced by [...]. A private key header takes its whole block with it, up to the END line."""
    lines, out, skipping = text.split("\n"), [], False
    for line in lines:
        if skipping:
            if re.search(r"-----END [A-Z0-9 ]*PRIVATE KEY", line):
                skipping = False
            continue
        if re.search(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----", line) and "-----END" not in line:
            out.append(CUT)
            skipping = True
            continue
        out.append(line)
    text = "\n".join(out)
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, CUT)
    return text


# ---- frontmatter, written as text lines ---------------------------------------------------------------

def own_frontmatter(text):
    """(lines between the markers, body) when text opens with a block that is frontmatter, else None. Frontmatter:
    starts with ---, has a closing ---, and every non-empty line between is a key line, an indented line or a - item,
    with at least one key line. A note that only opens with a --- rule is not frontmatter."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if close is None:
        return None
    between, keys = lines[1:close], 0
    for line in between:
        if not line.strip():
            continue
        if KEY_LINE.match(line):
            keys += 1
        elif not (line.startswith((" ", "\t")) or line.startswith("- ")):
            return None
    if not keys:
        return None
    return between, "\n".join(lines[close + 1:])


def scalar(value):
    value = value.strip()
    if value.startswith('"'):
        try:
            return str(json.loads(value))
        except ValueError:
            return value.strip('"')
    if value.startswith("'") and value.endswith("'") and len(value) > 1:
        return value[1:-1].replace("''", "'")
    return value


def key_value(lines, key):
    for line in lines:
        if line.startswith(key + ":"):
            return scalar(line[len(key) + 1:])
    return None


def blocks_of(lines):
    """[(key or None, [lines])]: a key line with the indented and - lines under it."""
    blocks = []
    for line in lines:
        m = KEY_LINE.match(line)
        if m:
            blocks.append((line.split(":", 1)[0], [line]))
        elif blocks:
            blocks[-1][1].append(line)
        else:
            blocks.append((None, [line]))
    return blocks


def with_frontmatter(text, fields, replace):
    """fields: [(key, line)] in order. Keys in replace are set; the others are added only when absent."""
    own = own_frontmatter(text)
    if own is None:
        return "---\n" + "".join(line + "\n" for _, line in fields) + "---\n" + text
    between, body = own
    blocks = blocks_of(between)
    present = {key for key, _ in blocks if key}
    for key, line in fields:
        if key in present and key in replace:
            blocks = [(k, [line] if k == key else ls) for k, ls in blocks]
        elif key not in present:
            blocks.append((key, [line]))
            present.add(key)
    lines = [ln for _, ls in blocks for ln in ls]
    return "---\n" + "".join(ln + "\n" for ln in lines) + "---\n" + body


def quoted(value):
    return json.dumps(value, ensure_ascii=False)


def first_line(body):
    for line in body.split("\n"):
        line = line.strip().lstrip("#").strip()
        if line:
            return line
    return ""


def short(text):
    text = one_line(text)
    return text[:TITLE_MAX].rstrip()


# ---- where a file is ------------------------------------------------------------------------------------

def given_path(root, raw):
    path = Path(scan.native_path(str(raw).strip()))
    return path if path.is_absolute() else root / path


def kind_of(root, conf, full):
    """capture, own, copied or place, from where the file is. full is resolved."""
    try:
        rel = full.relative_to(root)
    except ValueError:
        return "copied"
    parts = [p.casefold() for p in rel.parts]
    vault = [p.casefold() for p in Path(conf["VAULT_DIR"].strip("/")).parts]
    if parts[0] in HIDDEN_OWN or (len(parts) == 1 and parts[0] in TOP_OWN):
        return "place"
    if parts[:len(vault)] == vault:
        rest = parts[len(vault):]
        if rest[:1] == ["inbox"] and len(rest) == 2:
            name = rel.parts[-1]
            if name.startswith("keep-") and name.lower().endswith(".md"):
                return "capture"
            return "own"
        if rest[:1] == ["inbox"]:
            return "own"
        return "place"
    if parts[0] == "intake":
        return "own"
    return "copied"


def exclusive(folder, name, data):
    """Write data under name, or name-2, name-3, ... when taken. Returns the path."""
    stem, suffix = os.path.splitext(name)
    folder.mkdir(parents=True, exist_ok=True)
    for n in range(1, 1000):
        candidate = folder / (name if n == 1 else "%s-%d%s" % (stem, n, suffix))
        try:
            with open(str(candidate), "xb") as fh:
                fh.write(data)
            return candidate
        except FileExistsError:
            continue
    raise OSError("no free name for %s in %s" % (name, folder))


def plain_utf8(data):
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    return len(scan.readings(data)) == 1


def today(conf):
    pinned = os.environ.get("KIT_TODAY")
    return datetime.date.fromisoformat(pinned) if pinned else kr.local_now(conf["TIMEZONE"]).date()


# ---- keeping one thing --------------------------------------------------------------------------------------

def options(root, conf, opts):
    kind = opts.get("--kind", "sources")
    if kind not in raw_add.KINDS:
        raise gate.Usage("--kind is one of %s" % ", ".join(raw_add.KINDS))
    projects = kr.projects(conf)
    project = opts.get("--project") or (projects[0] if len(projects) == 1 else "cross")
    if project not in projects + ["cross"]:
        raise gate.Usage("unknown project '%s'. Use one of: %s." % (project, ", ".join(projects + ["cross"])))
    date = opts.get("--date") or today(conf).isoformat()
    try:
        if not DATE_RE.fullmatch(date):
            raise ValueError
        datetime.date.fromisoformat(date)
    except ValueError:
        raise gate.Usage("--date must be a real date written YYYY-MM-DD")
    return kind, project, date


def destination(root, conf, project, kind, date, slug, suffix):
    base = raw_ref.raw_base(root, conf) / project / kind
    for n in range(1, 100):
        name = "%s-%s%s" % (date, slug if n == 1 else "%s-%d" % (slug, n), suffix)
        if not os.path.lexists(str(base / name)):
            return slug if n == 1 else "%s-%d" % (slug, n)
    raise Refusal("other", ["K16"], "no free name for %s under %s" % (slug, base))


def bring_in(root, conf, src, project, kind, date, slug, capture):
    """raw_add.add with its stdout and stderr captured. Returns (dest, stderr text)."""
    out, err = io.StringIO(), io.StringIO()
    rel = src.relative_to(root).as_posix()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            dest = raw_add.add(root, [rel, "--project", project, "--kind", kind, "--date", date, "--slug", slug])
    except gate.Refused as exc:
        if str(exc).startswith("the scan found"):
            values = [ln.split("\t")[-1] for ln in out.getvalue().splitlines() if "\t" in ln]
            raise Refusal("secret", ["K6b" if capture else "K6"], str(exc), masked=", ".join(values) or "***")
        raise Refusal("other", ["K16"], str(exc))
    except (gate.Usage, kr.RegistryError, OSError) as exc:
        raise Refusal("other", ["K16"], str(exc))
    return dest, err.getvalue()


def notes_for_model(err, personal):
    for line in err.splitlines():
        m = re.search(r"sees (\d+) contact detail", line)
        if m and personal:
            print("keep: note: the scan sees %s contact detail(s) in this source. It stays in this folder." % m.group(1),
                  file=sys.stderr)
        elif line.strip():
            print(line.replace("raw-add:", "keep:", 1), file=sys.stderr)


def keep_one(root, conf, opts, positional, t):
    if len(positional) > 1:
        raise gate.Usage("give one file")
    link, unread, title_opt = opts.get("--link"), bool(opts.get("--unread")), opts.get("--title")
    if unread and not link:
        raise gate.Usage("--unread goes with --link")
    if not positional and not link:
        raise gate.Usage("give a file, or --link")
    kind, project, date = options(root, conf, opts)
    vault = conf["VAULT_DIR"].strip("/")
    inbox = root.joinpath(*Path(vault).parts) / "inbox"
    created, capture, original = [], None, None
    try:
        if positional:
            full = given_path(root, positional[0])
            if not full.is_file():
                raise Refusal("missing", ["K11"], name=inline(Path(positional[0]).name))
            full = full.resolve()
            where = kind_of(root, conf, full)
            if where == "capture":
                capture = full
            if link and where != "capture":
                raise gate.Usage("--link goes with a capture in %s/inbox/ named keep-*.md, or with no file" % vault)
            if where == "place":
                raise Refusal("place", ["K14"])
        if link:
            if not gate.link_shape_ok(link):
                raise Refusal("link-shape", ["K10b"])
            if gate.link_findings(link, gate.repo_scan_cfg(root)):
                raise Refusal("link", ["K10"])
        if not positional:
            words = short(title_opt or link) + "\n"
            name = "keep-%s.md" % hashlib.sha256(link.encode("utf-8")).hexdigest()[:8]
            full = exclusive(inbox, name, words.encode("utf-8"))
            capture, where = full, "capture"

        data = full.read_bytes()
        suffix = full.suffix.lower()
        wrapped = (where == "capture" or suffix in (".md", ".txt")) and len(data) <= WRAP_MAX and plain_utf8(data)
        stub = scan.decode(data) is None or len(data) > WRAP_MAX or suffix in scan.LINK_ONLY
        state = "address" if link and (unread or not positional) else "link" if link else "stub" if stub else "text"
        cut = []
        if wrapped:
            text = scan.without_hidden(data.decode("utf-8-sig")).replace("\r\n", "\n")
            own = own_frontmatter(text)
            body = own[1] if own else text
            title = short(title_opt or (key_value(own[0], "title") if own else None) or first_line(body)
                          or (t["note"] if where == "capture" else full.name))
            cfg = scan_cfg(root)
            values = secret_values(text + "\n" + title, cfg)
            if values:
                if where != "capture":
                    raise Refusal("secret", ["K6"], masked=masked(values))
                text, title = cut_secrets(text, values), short(cut_secrets(title, values))
                left = secret_values(text + "\n" + title, cfg)
                if left:
                    raise Refusal("secret", ["K6b"], masked=masked(left))
                cut = values
            title = without_contacts(title, cfg)
            origin = "link" if link else "note in chat" if where == "capture" else "file"
            fields = [("source_type", "source_type: %s" % SINGULAR[kind]), ("captured", "captured: %s" % date),
                      ("origin", "origin: %s" % quoted(origin)), ("project", "project: %s" % project),
                      ("title", "title: %s" % quoted(title))]
            if link:
                fields.append(("link", "link: %s" % quoted(link)))
                if state == "address":
                    fields.append(("link_read", "link_read: false"))
            wrapped_text = with_frontmatter(text, fields, ("source_type", "captured", "origin", "project"))
            src = exclusive(inbox, "keep-%s.md" % uuid.uuid4().hex[:8], wrapped_text.encode("utf-8"))
            created.append(src)
            if where == "own":
                original = full
            slug, ext = solo.slugify(title, SLUG_MAX), ".md"
        else:
            cfg = scan_cfg(root)
            values = secret_values(title_opt or "", cfg)  # the title becomes part of the file's name
            if values:
                raise Refusal("secret", ["K6b" if where == "capture" else "K6"], masked=masked(values))
            title = short(without_contacts(title_opt or full.name, cfg))
            slug = solo.slugify(without_contacts(title_opt or full.stem, cfg), SLUG_MAX)
            ext = ".md" if suffix == ".txt" else suffix
            if where == "copied":
                src = exclusive(inbox, full.name, data)
                created.append(src)
            else:
                src = full
        # The same bytes on the same day are the same reference: kept once, whether the person said "zapisz" twice
        # or the model ran this again. The working copy is deleted below and the earlier file is named.
        ref = "src:%s:%s:%s" % (kind, date, raw_ref.digest8(src))
        earlier = raw_ref.find(root, conf, ref)
        if earlier:
            dest = earlier[0]
            if original is None and where == "own":
                original = src
        else:
            slug = destination(root, conf, project, kind, date, slug, ext)
            dest, err = bring_in(root, conf, src, project, kind, date, slug, where == "capture")
            created = [p for p in created if p != src]
            notes_for_model(err, solo.is_personal(root))
            ref = raw_ref.ref_of(root, conf, dest)
        if original is not None:  # its content is now the source file
            try:
                original.unlink()
            except OSError as exc:
                print("keep: note: the file was kept, but %s could not be removed: %s" % (original.name, exc),
                      file=sys.stderr)
    finally:
        for path in created + ([capture] if capture is not None else []):
            try:
                if os.path.lexists(str(path)):
                    os.unlink(str(path))
            except OSError:
                pass
    print("kept\t%s\t%s\t%s" % (dest, ref, state))
    key = {"text": "K1", "link": "K2", "address": "K3", "stub": "K4"}[state]
    print("say\t%s" % t[key].format(title=inline(title)))
    if cut:
        print("say\t%s" % t["K5"].format(n=len(cut), masked=masked(cut)))
    if not earlier or not raw_ref.cited_by(root, conf).get(ref):  # a page already written is not written again
        print("next\tingest\t%s" % dest)
    return 0


# ---- the person's own rules --------------------------------------------------------------------------------

def add_rule(root, conf, text, t):
    text = one_line(text)
    if not text or len(text) > RULE_MAX:
        raise gate.Usage("a rule is one line of 1 to %d characters" % RULE_MAX)
    values = secret_values(text, scan_cfg(root))
    if values:
        raise Refusal("secret", ["K6b"], masked=masked(values))
    import setup_workspace  # imported here: only a first rule needs the file's heading
    path = root / setup_workspace.LOCAL_RULES
    lang = "pl" if gate.is_polish(conf) else "en"
    try:
        with open(str(path), "x", encoding="utf-8", newline="\n") as fh:
            fh.write(setup_workspace.SAY[lang]["rules"])
    except FileExistsError:
        pass
    old = path.read_text(encoding="utf-8", errors="replace")
    last = ([ln for ln in old.splitlines() if ln.strip()] or [""])[-1]
    gap = ("" if not old or old.endswith("\n") else "\n") + ("" if not last or last.startswith("- ") else "\n")
    with open(str(path), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(gap + "- %s\n" % text)
    print("say\t%s" % t["K9"])
    return 0


# ---- what was kept ------------------------------------------------------------------------------------------

def page_title(root, rel):
    """The page's first '# ' heading, else its file stem."""
    try:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return Path(rel).stem
    _, body, _ = kr.split_frontmatter(text)
    for line in body.split("\n"):
        if line.startswith("# "):
            return inline(line[2:].strip()) or Path(rel).stem
    return Path(rel).stem


def page_is_stub(root, rel):
    try:
        front, _, _ = kr.split_frontmatter((root / rel).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False
    return bool(front) and any(re.match(r"extraction:\s*[\"']?unextracted\b", ln) for ln in front.split("\n"))


def load_cache(root):
    try:
        data = json.loads(root.joinpath(*CACHE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(root, cache, old):
    if not cache or cache == old:
        return
    path = root.joinpath(*CACHE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        gate.write_atomic(path, json.dumps(cache, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def raw_refs(root, conf):
    """[(ref, repo-relative path, kind, date)] for every raw file with a reference. A raw file never changes, so its
    reference is cached by path, size and modification time: the dashboard runs at every session start and stop."""
    base = raw_ref.raw_base(root, conf)
    if not base.is_dir():
        return []
    kept = {k.casefold() for k in kr.kept_files(conf)}
    old = load_cache(root)
    cache, out = {}, []
    for full in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = full.relative_to(root).as_posix()
        if rel.casefold() in kept or full.name == ".gitkeep":
            continue
        shape = raw_ref.shape_of(root, conf, full)
        if not shape:
            continue
        try:
            st = full.stat()
            key = [st.st_size, st.st_mtime_ns]
            hit = old.get(rel)
            digest = hit[2] if isinstance(hit, list) and len(hit) == 3 and hit[:2] == key else raw_ref.digest8(full)
        except OSError:
            continue
        cache[rel] = key + [digest]
        out.append(("src:%s:%s:%s" % (shape[0], shape[1], digest), rel, shape[0], shape[1]))
    save_cache(root, cache, old)
    return out


def source_fields(full):
    """title and link from the frontmatter of a wrapped source, or {}."""
    if full.suffix.lower() != ".md":
        return {}
    with open(str(full), "rb") as fh:
        head = fh.read(65536).decode("utf-8", errors="replace").replace("\r\n", "\n")
    own = own_frontmatter(head)
    if own is None:
        return {}
    return {k: key_value(own[0], k) for k in ("title", "link") if key_value(own[0], k) is not None}


def slug_title(rel):
    name = Path(rel).name
    stem = name.rsplit(".", 1)[0] if "." in name[11:] else name
    return stem[11:] or stem


def list_rows(root, conf, days=None, day=None):
    """What was kept, newest first (date, then file name). Never raises on one file: a source whose frontmatter cannot
    be read gets the slug part of its name as the title."""
    t = TEXT[gate.is_polish(conf)]
    cites = raw_ref.cited_by(root, conf)
    since = None
    if days is not None:
        since = ((day or today(conf)) - datetime.timedelta(days=days)).isoformat()
    rows = []
    for ref, rel, kind, date in raw_refs(root, conf):
        if since and date <= since:  # the last N days, today included
            continue
        try:
            fields = source_fields(root / rel)
        except Exception:
            fields = {}
        title = inline(fields.get("title") or "") or inline(slug_title(rel))
        pages = [{"path": p, "title": page_title(root, p)} for p in cites.get(ref, [])]
        if len(pages) == 1:
            line = t["T1a"].format(date=date, title=title, page=pages[0]["title"])
        elif pages:
            line = t["T1b"].format(date=date, title=title, n=len(pages))
        else:
            line = t["T1c"].format(date=date, title=title)
        rows.append({"date": date, "title": title, "ref": ref, "path": rel, "kind": kind,
                     "state": "page" if pages else "pending", "pages": pages, "link": fields.get("link") or "",
                     "line": line})
    rows.sort(key=lambda r: (r["date"], Path(r["path"]).name), reverse=True)
    return rows


def kept_summary(root, conf, day):
    """The kept section of today-data."""
    t = TEXT[gate.is_polish(conf)]
    rows = list_rows(root, conf)
    since = (day - datetime.timedelta(days=7)).isoformat()
    pending = sum(1 for r in rows if r["state"] == "pending")
    return {"count_7d": sum(1 for r in rows if r["date"] > since), "pending": pending,
            "pending_line": t["T2"].format(n=pending) if pending else "",
            "latest": [{k: v for k, v in r.items() if k != "path"} for r in rows[:LATEST]]}


def status(root, conf, ref, t):
    raw_ref.parse_ref(ref)
    pages = raw_ref.cited_by(root, conf).get(ref, [])
    if not pages:
        print("pending\t%s" % ref)
        print("say\t%s" % t["K8"])
        return 0
    for rel in pages:
        print("page\t%s\t%s\t%s" % (rel, page_title(root, rel), "stub" if page_is_stub(root, rel) else "full"))
    if len(pages) > 1:
        print("say\t%s" % t["K7b"].format(n=len(pages)))
    elif page_is_stub(root, pages[0]):
        print("say\t%s" % t["K7c"].format(page=page_title(root, pages[0])))
    else:
        print("say\t%s" % t["K7a"].format(page=page_title(root, pages[0])))
    if not solo.is_personal(root):
        print("say\t%s" % t["K12"])
    return 0


def print_list(root, conf, opts):
    days = opts.get("--days")
    if days is not None and not re.fullmatch(r"\d{1,4}", days):
        raise gate.Usage("--days is a whole number")
    rows = list_rows(root, conf, int(days) if days is not None else None)
    if opts.get("--json"):
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for r in rows:
            print("%s\t%s\t%s\t%s" % (r["ref"], r["state"], r["date"], r["title"]))
    return 0


def drop_stray_capture(root, positional):
    """In a folder that is not set up: delete the capture the skill wrote (vault/inbox/keep-*.md), then vault/inbox/
    and vault/ when they are left empty. Otherwise a pasted note, its secret uncut, would stay in a folder hg does
    not know, and the vault/ it made would stop setup here (S7d)."""
    if len(positional) != 1:
        return
    inbox = root / kr.DEFAULTS["VAULT_DIR"].strip("/") / "inbox"
    try:
        full = given_path(root, positional[0]).resolve()
        if full.parent != inbox.resolve() or not full.name.startswith("keep-") or not full.name.lower().endswith(".md"):
            return
        if full.is_file() and not os.path.islink(str(full)):
            full.unlink()
    except OSError:
        return
    for folder in (inbox, inbox.parent):
        try:
            folder.rmdir()  # only an empty folder
        except OSError:
            return


def refuse(exc, t):
    print("refused\t%s" % exc.reason)
    for key in exc.says:
        print("say\t%s" % t[key].format(masked=exc.masked, name=exc.name))
    if exc.detail:
        print("keep: %s" % exc.detail, file=sys.stderr)
    return 1


def main(argv):
    kr.stdio_utf8()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        opts, positional = gate.parse(argv, VALUES, flags=FLAGS)
        modes = [k for k in ("--rule", "--status", "--list") if k in opts]
        if len(modes) > 1 or (modes and positional) or (modes and set(opts) - {modes[0], "--json", "--days"}) \
                or ((opts.get("--json") or "--days" in opts) and modes != ["--list"]):
            raise gate.Usage("--rule, --status and --list each stand alone (--list takes --json and --days)")
        root = kr.kit_root().resolve()
        if not root.joinpath(*kr.CONFIG_PARTS).is_file():
            drop_stray_capture(root, positional)
            print("refused\tsetup")
            for place in solo.places(exclude=root):
                print("place\t%s" % place)
            return 1
        conf = kr.load_conf(root)
        t = TEXT[gate.is_polish(conf)]
        if "--rule" in opts:
            return add_rule(root, conf, opts["--rule"], t)
        if "--status" in opts:
            return status(root, conf, opts["--status"], t)
        if "--list" in opts:
            return print_list(root, conf, opts)
        return keep_one(root, conf, opts, positional, t)
    except gate.Usage as exc:
        print("keep: %s" % exc, file=sys.stderr)
        return 2
    except Refusal as exc:
        return refuse(exc, TEXT[gate.is_polish(kr.load_conf(kr.kit_root().resolve()))])
    except (gate.Refused, kr.RegistryError) as exc:  # --status with something that is not a reference
        print("keep: %s" % exc, file=sys.stderr)
        return 1
    except OSError as exc:
        return refuse(Refusal("other", ["K16"], str(exc)), TEXT[gate.is_polish(kr.load_conf(kr.kit_root().resolve()))])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
