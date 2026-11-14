#!/usr/bin/env python3
"""publish.py - check what a commit would carry out of this computer, show it, and make the commit.

Usage:
  hg-tool publish check [--json] [PATH ...]   stage, check every added line and new file name, write the preview
  hg-tool publish leftout <file.json>         store a left-out report a model drafted, in .gateway/leftout/
  hg-tool publish commit <id>                 make the commit of the bundle the preview showed, nothing else
  hg-tool publish withdraw <page>             remove a published wiki page from the current version

check with no PATH regenerates the wiki index and runs git add -A. With PATH it first takes everything out of the
index, then stages exactly those paths. Ignored and private files are never staged; a private file already in the
index and not in HEAD is taken out again and reported. The bundle is the index compared with HEAD, named by the
first 12 hex digits of the sha256 of git's raw diff. Every check reads added lines only, from the index, never from
the disk: the scanner (secrets, contact data, file types), private files, file names, text files not saved as UTF-8
(a UTF-16 mark can turn plain text into noise for the checks alone), names of raw files, the
department's word list, mentions of pages that are not going out, instruction-shaped lines, hidden text, and runs of
words copied from a person's own files. The settings come from the published and the staged .claude/hg.json, the
stricter of the two, never from the file on disk. The folders the checks read (paths.*) must be the same in the file
on disk, the published and the staged copy, or check and commit exit 2. The preview is written to
.gateway/outgoing/<id>.md.

check prints, tab-separated, a first line: empty<TAB><commits not on a remote>, ok<TAB><id><TAB><preview><TAB><files>
or refused<TAB><id><TAB><preview><TAB><findings>; for refused one finding<TAB><path>:<line><TAB><kind><TAB><value>
line each; then say<TAB><sentence> lines in the content language, which a skill copies word for word.

commit takes the id and nothing else. It refuses when the index is not the bundle of that id, when the preview on
disk is not the one this tool writes for it now, when a check finds something, or when git has no user.email. The
message is built here: a fixed subject, the paths, and the trailers Hg-Publish, Hg-Bundle and Hg-Checks. It never
pushes.

What nothing enforces: an agent or a person can still run git commit and git push directly. This tool is the route
the skills and the session rule name; the git commands themselves are not blocked.

While a merge, a rebase, a cherry-pick, a revert or git am waits, check and commit exit 2: that is finished with git.
Exit: 0 ok or empty, 1 refused, 2 usage error or a state this tool does not handle.
"""
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate  # noqa: E402
import kit_registry as kr  # noqa: E402
import raw_ref  # noqa: E402
import scan  # noqa: E402

TEMPLATE = HERE.parent / "templates" / "workspace"
CONFIG = "/".join(kr.CONFIG_PARTS)
SETTINGS = ".claude/settings.json"
OFFABLE = ("instruction", "hidden", "quote")
CHECKS = ("scan", "private", "path", "source-name", "word", "unshared", "instruction", "hidden", "quote")
QUOTE_DEFAULT = 12
QUOTE_MAX_BYTES = 5 * 1024 * 1024
SHOW_LINES = 2000
KEEP_DAYS = 30
MAX_MESSAGE_PATHS = 50
WORD = re.compile(r"[^\W_]+")
LEFTOUT_OPS = ("ingest", "file_back", "dayend", "init", "edit")
WHY = ("noise", "private", "judgment", "complaint", "language", "blame", "compromising", "personal-data", "secret",
       "instruction", "off-topic", "other")
WHAT_MAX = 200

# ---- the instruction patterns (second version) -----------------------------------------------------
LEAD = r"^[\s>*_#\-\d.)\]\[`\"'„”]*"
NAMES = r"(?:agent|assistant|asystent|claude|chatgpt|copilot|gemini|ai|llm|bot|model)"
VOC = r"(?:agencie|asystencie|asystentko|modelu|bocie)"
IMP_EN = (r"(?:approve|accept|ignore|disregard|forget|override|run|execute|send|delete|remove|write|add|publish|commit|"
          r"push|summari[sz]e|mark|set|skip|reply|respond|answer|tell|say|print|output|do|don't|never|always|"
          r"you (?:must|should|will))")
IMP_PL = (r"(?:zatwierd[zź]|zignoruj|ignoruj|pomi[nń]|pomijaj|zapomnij|uruchom|wykonaj|wy[sś]lij|usu[nń]|skasuj|napisz|"
          r"dopisz|dodaj|opublikuj|zapisz|podsumuj|oznacz|ustaw|odpowiedz|powiedz|wypisz|zr[oó]b|nie|zawsze|nigdy|"
          r"musisz|masz)")
INSTRUCTION = [(name, re.compile(rx, re.I)) for name, rx in (
    ("addressed", LEAD + r"(?:" + VOC + r"\s*[:,]\s*\S|" + NAMES + r"\s*[:,]\s*(?:(?:please|prosz[eę])[\s,]+)?(?:"
     + IMP_EN + "|" + IMP_PL + r")\b)"),
    ("audience", r"\b(?:note|attention|message|instructions?)\s+(?:to|for)\s+(?:the\s+|any\s+|all\s+)?"
                 r"(?:ai(?!\s+act\b)|llms?|language models?)\b|\b(?:uwaga|wiadomo[sś][cć]|instrukcj\w*|polecen\w*|notatka)"
                 r"\s+dla\s+(?:(?:modeli|modelu)\s+j[eę]zykow\w*|(?:asystent\w*|agent\w*)\s+(?:AI|SI)|AI(?!\s+act\b)|SI|LLM)\b"),
    ("ignore-en", r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:previous|prior|above|earlier|preceding|all|"
                  r"your|these|system)\b[^.\n]{0,30}\b(?:instructions?|rules?|prompts?|guidelines|guards?)\b|"
                  r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}\b(?:instructions?|rules?|prompts?|guidelines|"
                  r"guards?)\b[^.\n]{0,10}\b(?:above|so far)\b"),
    ("ignore-pl", r"\b(?:zignoruj|ignoruj|pomi[nń]|zapomnij|pomijaj)\b[^.\n]{0,40}\b(?:instrukcj\w*|polece\w*|prompt\w*)|"
                  r"\b(?:zignoruj|ignoruj|pomi[nń]|zapomnij|pomijaj)\b[^.\n]{0,20}\b(?:poprzedni\w*|powy[zż]sz\w*|"
                  r"wcze[sś]niejsz\w*|swoj\w*|twoj\w*)\b[^.\n]{0,20}\b(?:zasad\w*|regu[lł]\w*)"),
    ("role", r"\byou are now (?:an?|the|my|in)\b|\bfrom now on,? you (?:are an?\b|are the\b|will (?:act|respond|answer|"
             r"reply)\b|must (?:ignore|act|respond|answer|reply)\b)|\bnew instructions?\s*:|\bjeste[sś] teraz\b|"
             r"\bod teraz (?:jeste[sś]|b[eę]dziesz)\b|\bnowe instrukcje\s*:"),
    ("prompt-markup", r"</?(?:system|assistant|user|instructions?|prompt)>|<\|[a-z_]+\|>|\[/?INST\]|"
                      r"\b(?:new|updated|revised) system prompt\b|\bnowy prompt systemowy\b"),
    ("conceal", r"\b(?:do not|don't|never) (?:tell|mention|reveal|show)\b[^.\n]{0,30}\bthe (?:user|human)\b|"
                r"\bnie (?:m[oó]w|wspominaj|pokazuj|ujawniaj)\b[^.\n]{0,30}\bu[zż]ytkownik\w*"),
    ("hg-command", r"\bhg-tool\s+(?:gate\s+approve|publish\s+commit)\b|\bHG_GUARD_BYPASS\b"),
    ("approve", r"\b(?:approve|accept)\b[^.\n]{0,20}\b(?:gate|this (?:plan|change|publication))\b[^.\n]{0,20}"
                r"\b(?:now|immediately|without)\b|\bzatwierd[zź]\b[^.\n]{0,20}\b(?:bramk\w*|publikacj\w*)\b[^.\n]{0,20}"
                r"\b(?:teraz|natychmiast|bez)\b"),
)]
LINK_COMMENT = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(?:#|<>)")
# Characters a reader may break a line at, though git and this tool do not: the part after one is checked as a line
# of its own, and the line refuses as hidden text (written with chr() so this file holds none of them).
BREAKS = re.compile("[\r\x0b\x0c\x85" + chr(0x2028) + chr(0x2029) + "]")
# Text a renderer does not show: an HTML element hidden by an attribute or an inline style, a collapsed block, and a
# link definition's title, which is never rendered. Hiding by a class or by colour is not caught (README limits).
HIDDEN_MARKUP = re.compile(r"<[A-Za-z][^>]*?\s(?:hidden(?=[\s/>=])|style\s*=\s*[\"'][^\"']*"
                           r"(?:display\s*:\s*none|visibility\s*:\s*hidden))|<details\b", re.I)
LINK_TITLE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*\S+\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\))\s*$")
VS_SUPPLEMENT = (0xE0100, 0xE01EF)  # variation selectors that can carry bytes no reader sees
VS_BASIC = (0xFE00, 0xFE0F)  # one after an emoji is normal; a run of two or more is not


def hidden_selectors(text):
    run = 0
    for c in text:
        code = ord(c)
        if VS_SUPPLEMENT[0] <= code <= VS_SUPPLEMENT[1]:
            return True
        run = run + 1 if VS_BASIC[0] <= code <= VS_BASIC[1] else 0
        if run >= 2:
            return True
    return False

# ---- sentences for the person (section 4 of the spec), Polish then English -------------------------
TEXT = {
    True: {
        "empty": "Nie ma nic do wysłania.",
        "empty_waiting": "Nie ma nowych zmian do sprawdzenia. Na wysłanie czekają zmiany zapisane wcześniej: {n}.",
        "control": "W tej wysyłce są pliki, które sterują asystentami całego działu: {n}. W podglądzie są na początku. "
                   "Przeczytaj je uważnie.",
        "settings": "Ta wysyłka zmienia ustawienia kontroli ({what}). Sprawdzono ją według ostrzejszej z dwóch wersji: "
                    "obecnej i nowej.",
        "ok1": "Liczba plików do wysłania: {n}. Kontrola automatyczna nic nie zatrzymała. Otwórz podgląd i przeczytaj, co "
               "dokładnie wyjdzie i co zostało pominięte: {preview}",
        "ok2": "Kontrola automatyczna wyłapuje wzorce, a model mógł coś przeoczyć. O tym, co wychodzi, decydujesz Ty.",
        "refused": "Nic nie zostało wysłane. Kontrola automatyczna zatrzymała wysyłkę. Liczba znalezisk: {k}. Lista jest "
                   "na początku podglądu: {preview}",
        "committed": "Zapisano w historii zmian. Liczba plików: {n}.",
        "withdrawn": "Strona {path} została usunięta z bieżącej wersji. Zniknie u wszystkich po wysłaniu tej zmiany. "
                     "Wcześniejsza treść zostaje w historii zmian i w kopiach, które inni już pobrali. Jeśli był tam "
                     "sekret, trzeba go wymienić.",
        "what": {"words": "lista słów", "off": "wyłączone kontrole", "quoteWords": "długość cytatu",
                 "allow": "dozwolone adresy", "patterns": "własne wzorce"},
        "file_name": "{path} (nazwa pliku)",
        "secret": "{where}: wygląda na sekret ({value}). Usuń go z pliku. Jeśli to prawdziwy sekret, trzeba go też wymienić.",
        "pii": "{where}: dane kontaktowe ({value}). Zastąp osobę rolą albo usuń dane.",
        "link only": "{path}: taki plik zostaje poza repozytorium. Do repozytorium trafia strona ze streszczeniem i "
                     "odnośnikiem.",
        "secret file": "{path}: plik z sekretami nigdy nie trafia do repozytorium.",
        "private": "{path}: ten plik zostaje na Twoim komputerze i nie może trafić do repozytorium.",
        "source-name": "{where}: tekst podaje nazwę pliku źródłowego, który zostaje na Twoim komputerze. Zastąp ją "
                       "odwołaniem do źródła.",
        "word": "{where}: słowo z listy działu ({value}).",
        "instruction": "{where}: wiersz wygląda jak polecenie dla asystenta AI. Taki tekst nie wychodzi do działu.",
        "hidden": "{where}: tekst, którego czytelnik nie widzi (komentarz albo niewidoczne znaki).",
        "path": "{path}: nazwa pliku zawiera znaki, których nie widać. Zmień nazwę pliku.",
        "encoding": "{path}: ten plik tekstowy nie jest zapisany w UTF-8, więc kontrola i czytelnik mogą widzieć w nim "
                    "inny tekst. Zapisz go w UTF-8.",
        "unshared": "{where}: tekst wskazuje stronę, której nie ma w tej wysyłce ani w repozytorium: {page}. Wyślij ją "
                    "razem z tą zmianą albo usuń wzmiankę.",
        "quote": "{where}: {n} kolejnych słów przepisanych z pliku źródłowego. Strona ma oddawać treść własnymi słowami.",
        # the preview
        "title": "# Podgląd wysyłki {id}",
        "intro": "Ten plik jest tylko na Twoim komputerze. Pokazuje dokładnie to, co trafi do repozytorium działu, jeśli "
                 "się zgodzisz.",
        "h_checks": "## Kontrola automatyczna",
        "no_finding": "Nic nie zatrzymano. Co sprawdzono:",
        "stopped": "Zatrzymano ({k}):",
        "checked": "Co sprawdzono:",
        "check_names": {"scan": "sekrety, dane kontaktowe i rodzaje plików", "private": "pliki prywatne",
                        "path": "nazwy plików", "source-name": "nazwy plików źródłowych", "word": "lista słów działu",
                        "unshared": "strony spoza wysyłki", "instruction": "polecenia dla asystenta",
                        "hidden": "ukryty tekst", "quote": "cytaty ze źródeł"},
        "ran": "- {check}: sprawdzono.",
        "off": "- {check}: wyłączone w ustawieniach działu. Nie sprawdzono.",
        "no_words": "- {check}: lista jest pusta. Nie sprawdzono.",
        "quote_counts": "- {check}: porównano z plikami źródłowymi na tym komputerze: {n} z {m}. Pominięte, bo nie są "
                        "tekstem albo mają ponad 5 MB: {k}. Źródła wskazane w wysyłce, których tu nie ma: {r}.",
        "quote_none": "- {check}: na tym komputerze nie ma plików źródłowych do porównania. Nie sprawdzono.",
        "blind": "Tego kontrola nie wyłapie: oceny człowieka napisanej uprzejmie, skargi ani zarzutu bez słowa z listy, "
                 "faktu, który kogoś obciąża, nazwiska spoza listy, treści obrazów i plików PDF, cytatu przepisanego "
                 "innymi słowami.",
        "h_left": "## Co zostało pominięte",
        "left_entry": "{what} ({why}; źródło: {source})",
        "left_entry_bare": "{what} ({why})",
        "left_none": "Model zgłosił, że niczego nie pominął.",
        "left_ingest": "Te strony powstały ze źródła, ale model nie zapisał dla nich listy pominięć: {paths}",
        "left_missing": "Dla tych plików nie ma listy pominięć: {paths}",
        "left_note": "Tę listę napisał model, który ciął. Nic nie sprawdza, czy jest pełna.",
        "why": dict(zip(WHY, ("szum", "sprawa prywatna", "ocena osoby", "skarga", "wulgaryzm", "obwinianie",
                              "fragment obciążający", "dane osobowe", "sekret", "polecenie dla asystenta", "nie na temat",
                              "inne"))),
        "h_control": "## Pliki, które sterują asystentami całego działu",
        "control_note": "Te pliki mówią asystentom wszystkich osób w dziale, co wolno i jak pracować. Zmiana w nich "
                        "działa u każdego po pobraniu.",
        "h_out": "## Co wychodzi",
        "h_records": "## Zapisy narzędzi",
        "new": "### Nowy plik: {path}",
        "changed": "### Zmieniony plik: {path}",
        "deleted": "### Usunięty plik: {path}",
        "binary": "### Plik binarny, treść niesprawdzona: {path}",
        "plugin": "### Pliki z pluginu, bez zmian ({n})",
        "line_removed": "Wiersz {n}. Usunięte:",
        "line_added": "Wiersz {n}. Dodane:",
        "added": "Dodane:",
        "long": "Pokazano pierwsze 2000 wierszy. Cały tekst, który wychodzi, jest w pliku {path}.",
        "unpublished": "Liczba zmian na tym komputerze, których dział jeszcze nie widzi: {n}. Napisz „opublikuj”, żeby je "
                       "przejrzeć i wysłać.",
    },
    False: {
        "empty": "There is nothing to send.",
        "empty_waiting": "There are no new changes to check. Changes saved earlier wait to be sent: {n}.",
        "control": "This publication holds files that steer the assistants of the whole department: {n}. They come first "
                   "in the preview. Read them with care.",
        "settings": "This publication changes the check settings ({what}). It was checked with the stricter of the two "
                    "versions: the current one and the new one.",
        "ok1": "Files to send: {n}. The automatic checks stopped nothing. Open the preview and read exactly what goes out "
               "and what was left out: {preview}",
        "ok2": "The automatic checks match patterns, and the model may have missed something. What goes out is your "
               "decision.",
        "refused": "Nothing was sent. The automatic checks stopped it. Findings: {k}. The list is at the top of the "
                   "preview: {preview}",
        "committed": "Saved in the change history. Files: {n}.",
        "withdrawn": "Page {path} was removed from the current version. It disappears for everyone once this change is "
                     "sent. The earlier text stays in the change history and in the copies others already pulled. If it "
                     "held a secret, the secret must be replaced.",
        "what": {"words": "word list", "off": "switched-off checks", "quoteWords": "quote length",
                 "allow": "allowed addresses", "patterns": "own patterns"},
        "file_name": "{path} (file name)",
        "secret": "{where}: looks like a secret ({value}). Remove it from the file. If it is a real secret, it must also "
                  "be replaced.",
        "pii": "{where}: contact data ({value}). Replace the person with a role or remove the data.",
        "link only": "{path}: a file of this kind stays out of the repository. The repository gets a page with a summary "
                     "and a link.",
        "secret file": "{path}: a file with secrets never enters the repository.",
        "private": "{path}: this file stays on your computer and cannot enter the repository.",
        "source-name": "{where}: the text names a source file that stays on your computer. Replace the name with the "
                       "source reference.",
        "word": "{where}: a word from the department's list ({value}).",
        "instruction": "{where}: the line reads like an instruction to an AI assistant. Such text does not go out to the "
                       "department.",
        "hidden": "{where}: text a reader does not see (a comment or invisible characters).",
        "path": "{path}: the file name holds characters that cannot be seen. Rename the file.",
        "encoding": "{path}: this text file is not saved as UTF-8, so the checks and a reader may see different text. "
                    "Save it as UTF-8.",
        "unshared": "{where}: the text points to a page that is neither in this publication nor in the repository: "
                    "{page}. Send it with this change or remove the mention.",
        "quote": "{where}: {n} words in a row copied from a source file. A page restates the content in its own words.",
        "title": "# Outgoing preview {id}",
        "intro": "This file is only on your computer. It shows exactly what will enter the department's repository if you "
                 "agree.",
        "h_checks": "## Automatic checks",
        "no_finding": "Nothing was stopped. What was checked:",
        "stopped": "Stopped ({k}):",
        "checked": "What was checked:",
        "check_names": {"scan": "secrets, contact data and file types", "private": "private files",
                        "path": "file names", "source-name": "names of source files",
                        "word": "the department's word list", "unshared": "pages outside this publication",
                        "instruction": "instructions to an assistant", "hidden": "hidden text",
                        "quote": "quotes from sources"},
        "ran": "- {check}: checked.",
        "off": "- {check}: switched off in the department's settings. Not checked.",
        "no_words": "- {check}: the list is empty. Not checked.",
        "quote_counts": "- {check}: compared with source files on this computer: {n} of {m}. Skipped, because they are "
                        "not text or are over 5 MB: {k}. Sources cited in this publication that are not here: {r}.",
        "quote_none": "- {check}: this computer holds no source files to compare with. Not checked.",
        "blind": "The checks will not catch: a judgment of a person written politely, a complaint or blame without a "
                 "listed word, a fact that compromises someone, a name that is not on the list, the contents of images "
                 "and PDF files, a quote put in other words.",
        "h_left": "## What was left out",
        "left_entry": "{what} ({why}; source: {source})",
        "left_entry_bare": "{what} ({why})",
        "left_none": "The model reported that it left nothing out.",
        "left_ingest": "These pages were made from a source, but the model saved no left-out list for them: {paths}",
        "left_missing": "There is no left-out list for these files: {paths}",
        "left_note": "This list was written by the model that did the cutting. Nothing checks that it is complete.",
        "why": dict(zip(WHY, ("noise", "private matter", "judgment of a person", "complaint", "swearing", "blame",
                              "compromising fragment", "personal data", "secret", "instruction to an assistant",
                              "off topic", "other"))),
        "h_control": "## Files that steer the assistants of the whole department",
        "control_note": "These files tell the assistants of everyone in the department what is allowed and how to work. "
                        "A change in them applies to everyone after they pull.",
        "h_out": "## What goes out",
        "h_records": "## Records written by the tools",
        "new": "### New file: {path}",
        "changed": "### Changed file: {path}",
        "deleted": "### Deleted file: {path}",
        "binary": "### Binary file, contents not checked: {path}",
        "plugin": "### Plugin files, unchanged ({n})",
        "line_removed": "Line {n}. Removed:",
        "line_added": "Line {n}. Added:",
        "added": "Added:",
        "long": "The first 2000 lines are shown. The full outgoing text is in the file {path}.",
        "unpublished": "Changes on this computer the department does not see yet: {n}. Write \"publish\" to review and "
                       "send them.",
    },
}
STALE = "what is staged changed since the preview was written. Run hg-tool publish check again."
NOT_OURS = "the preview on disk is not the one this tool wrote for what is staged. Run hg-tool publish check again."


# ---- small helpers ----------------------------------------------------------------------------------

def shown(path):
    """A path as it may be printed: every control or format character becomes ?."""
    return "".join("?" if unicodedata.category(c) in ("Cc", "Cf") else c for c in path)


def run_git(root, *args, data=None):
    try:
        return subprocess.run(["git", "-c", "core.quotepath=off"] + list(args), cwd=str(root), input=data,
                              capture_output=True)
    except OSError:
        raise gate.Usage("git is not installed")


def git_text(root, *args):
    out = run_git(root, *args)
    return out.returncode, out.stdout.decode("utf-8", "replace"), out.stderr.decode("utf-8", "replace")


def blob(root, spec):
    out = run_git(root, "cat-file", "blob", spec)
    return out.stdout if out.returncode == 0 else None


def has_head(root):
    return run_git(root, "rev-parse", "-q", "--verify", "HEAD").returncode == 0


def first_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[0] if lines else "no message"


def fence(lines):
    body = "\n".join(lines)
    longest = max((len(m) for m in re.findall(r"`+", body)), default=0)
    mark = "`" * max(4, longest + 1)
    return [mark] + list(lines) + [mark]


def text_lines(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [ln[:-1] if ln.endswith("\r") else ln for ln in lines]


def mask_word(matched):
    return matched[:2] + "***" if len(matched) >= 4 else "***"


name_rule = kr.token_rule  # one regex for the name rule: a name stands as a whole token, case ignored


def vault_of(conf):
    return conf["VAULT_DIR"].replace("\\", "/").strip("/") or "vault"


def is_tool_record(rel, conf):
    v = vault_of(conf)
    if re.fullmatch(r"gates/[^/]+\.lock\.json", rel) or re.fullmatch(r"gates/[^/]+\.obs/[^/]+\.json", rel):
        return True
    return is_background(rel, conf)


def is_background(rel, conf):
    """The log, a rotated log, a journal day and the index files: they change in almost every session."""
    v = vault_of(conf)
    journal = conf["JOURNAL_DIR"].replace("\\", "/").strip("/")
    return (rel == conf["LOG_FILE"].replace("\\", "/").strip("/") or bool(re.fullmatch(re.escape(v) + r"/log/[^/]+\.jsonl", rel))
            or bool(re.fullmatch(re.escape(journal) + r"/\d{4}-\d{2}-\d{2}\.md", rel))
            or bool(re.fullmatch(re.escape(v) + r"/index[^/]*\.md", rel)))


def is_control(rel, conf):
    """A tracked file that steers every colleague's assistant (publish.CONTROL in the spec)."""
    v = vault_of(conf)
    name = rel.rsplit("/", 1)[-1]
    return (name in ("CLAUDE.md", "AGENTS.md", ".gitignore", ".gitattributes") or rel.startswith((".claude/", ".github/"))
            or rel in ("%s/cleaning.md" % v, "%s/schema.md" % v))


def plugin_copy(rel):
    if rel.startswith(".github/hg/") and rel.count("/") == 2:
        return HERE / rel.rsplit("/", 1)[-1]
    if ".." in rel.split("/"):
        return None
    return TEMPLATE.joinpath(*rel.split("/"))


def plugin_identical(rel, data):
    copy = plugin_copy(rel)
    try:
        if copy is None or not copy.is_file():
            return False
        return copy.read_bytes().replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n")
    except OSError:
        return False


def is_gate_file(rel):
    return bool(re.fullmatch(r"gates/[^/]+", rel))


# ---- the workspace state ----------------------------------------------------------------------------

def workspace(argv_root=None):
    root = kr.kit_root(argv_root).resolve()
    if not root.joinpath(*kr.CONFIG_PARTS).is_file():
        raise gate.Usage("this folder is not a department workspace (.claude/hg.json is missing). Run /hg:setup.")
    code, out, _ = git_text(root, "rev-parse", "--show-toplevel")
    if code != 0:
        raise gate.Usage("this folder is not a git repository. Run /hg:setup.")
    return root


def refuse_busy(root):
    code, out, _ = git_text(root, "rev-parse", "--git-dir")
    gitdir = Path(out.strip())
    gitdir = gitdir if gitdir.is_absolute() else root / gitdir
    for name, what in (("rebase-merge", "a rebase"), ("rebase-apply", "a rebase or git am"),
                       ("CHERRY_PICK_HEAD", "a cherry-pick"), ("REVERT_HEAD", "a revert"), ("MERGE_HEAD", "a merge")):
        if (gitdir / name).exists():
            raise gate.Usage("%s is in progress here. Finish it or abort it with git first, then run hg-tool publish "
                             "check for your own changes." % what)


def resolve_arg(root, raw):
    """A path argument as a repo-relative path. /d/x, D:\\x and D:/x are accepted; outside the workspace is exit 2."""
    given = Path(scan.native_path(raw.strip()))
    full = (given if given.is_absolute() else root / given).resolve()
    try:
        rel = full.relative_to(root).as_posix()
    except ValueError:
        raise gate.Usage("%s is outside this workspace." % shown(raw))
    return "." if rel in ("", ".") else rel


def regenerate_index(root):
    out = subprocess.run([sys.executable, str(HERE / "regenerate-wiki-index.py"), "--root", str(root)],
                         capture_output=True)
    if out.returncode != 0:
        raise gate.Usage("the wiki index could not be regenerated: %s" % first_line(out.stderr.decode("utf-8", "replace")))


def index_paths(root):
    out = run_git(root, "ls-files", "-z", "--full-name")
    return [p for p in out.stdout.decode("utf-8", "surrogateescape").split("\0") if p] if out.returncode == 0 else []


def in_head(root, rel):
    return run_git(root, "cat-file", "-e", "HEAD:" + rel).returncode == 0


def stage(root, conf, paths):
    """Put the bundle into the index. Returns the private paths taken out of it again."""
    if not paths:
        regenerate_index(root)
        out = run_git(root, "add", "-A")
        if out.returncode != 0:
            raise gate.Usage("git add failed: %s" % first_line(out.stderr.decode("utf-8", "replace")))
    else:
        rels = list(dict.fromkeys(resolve_arg(root, p) for p in paths))
        for rel in rels:
            if kr.is_private(rel, conf) or (rel != "." and gate.is_ignored(root, rel)):
                raise gate.Refused("%s is kept out of git here and cannot be published." % shown(rel))
        run_git(root, "reset", "-q")
        if not has_head(root):  # before the first commit git reset leaves the index as it is
            run_git(root, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", ".")
        out = run_git(root, "--literal-pathspecs", "add", "-A", "--", *rels)
        if out.returncode != 0:
            raise gate.Usage("git add failed: %s" % first_line(out.stderr.decode("utf-8", "replace")))
    removed = []
    for rel in index_paths(root):
        if kr.is_private(rel, conf) and not in_head(root, rel):
            run_git(root, "--literal-pathspecs", "rm", "--cached", "-q", "--", rel)
            removed.append(rel)
    return removed


def raw_diff(root):
    out = run_git(root, "diff", "--cached", "--raw", "--no-renames", "--no-abbrev", "-z")
    if out.returncode != 0:
        raise gate.Usage("git diff failed: %s" % first_line(out.stderr.decode("utf-8", "replace")))
    return out.stdout


def entries_of(raw):
    parts = raw.split(b"\0")
    found, k = [], 0
    while k + 1 < len(parts):
        meta = parts[k].decode("ascii", "replace")
        if not meta.startswith(":"):
            k += 1
            continue
        fields = meta[1:].split()
        path = parts[k + 1].decode("utf-8", "replace")
        found.append({"old_mode": fields[0], "new_mode": fields[1], "old": fields[2], "new": fields[3],
                      "status": fields[4][:1], "path": path})
        k += 2
    return found


def ahead_count(root):
    """Commits no remote has, when the folder has a remote."""
    code, out, _ = git_text(root, "remote")
    if code != 0 or not out.strip() or not has_head(root):
        return 0
    code, out, _ = git_text(root, "rev-list", "--count", "HEAD", "--not", "--remotes")
    return int(out.strip()) if code == 0 and out.strip().isdigit() else 0


def unpublished(root, conf=None):
    """{count, line} for /hg:today: changes git lists that are not background records, plus commits no remote has."""
    conf = conf or kr.load_conf(root)
    out = run_git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")
    count = 0
    if out.returncode == 0:
        for item in out.stdout.decode("utf-8", "replace").split("\0"):
            if len(item) > 3 and not is_background(item[3:], conf):
                count += 1
    count += ahead_count(root)
    return {"count": count, "line": TEXT[gate.is_polish(conf)]["unpublished"].format(n=count) if count else ""}


# ---- settings: the stricter of the published and the staged copy -------------------------------------

def read_copy(root, spec, name):
    data = blob(root, spec)
    if data is None:
        return None
    try:
        parsed = json.loads(data.decode("utf-8-sig"))
    except ValueError as exc:
        raise gate.Usage("the %s copy of %s cannot be read: %s" % (name, CONFIG, exc))
    if not isinstance(parsed, dict):
        raise gate.Usage("the %s copy of %s is not an object" % (name, CONFIG))
    return parsed


FOLDERS = ("%s %s other folders in %s (paths) than the published copy. The checks read those folders, so nothing is "
           "checked or committed while they differ. Put the file back as it was published. A change of the folders is "
           "made by whoever maintains the repository, outside this tool.")


def check_folders(root, conf):
    """The folders the checks read (paths.* of .claude/hg.json: the vault, and with it the private folders, the
    source names and the quote corpus) come from the published copy, so an edit on disk cannot switch a check off.
    conf is the file on disk; it must name the same folders as the published copy, and so must the staged copy.
    Before the first commit the staged copy is the reference."""
    keys = list(kr.JSON_NESTED["paths"].values())

    def folders(c):
        return {k: str(c[k]).replace("\\", "/").strip("/") for k in keys}
    published = read_copy(root, "HEAD:" + CONFIG, "published") if has_head(root) else None
    staged = read_copy(root, ":" + CONFIG, "staged")
    reference = published if published is not None else staged
    if reference is None:
        return
    want = folders(kr.conf_from(reference))
    differ = []
    if folders(conf) != want:
        differ.append("the file on disk")
    if staged is not None and folders(kr.conf_from(staged)) != want:
        differ.append("the staged copy")
    if differ:
        raise gate.Usage(FOLDERS % (" and ".join(differ), "names" if len(differ) == 1 else "name", CONFIG))


def publish_section(data, name):
    pub = data.get("publish", {})
    if not isinstance(pub, dict):
        raise gate.Usage("the %s copy of %s: publish must be an object" % (name, CONFIG))
    words, off = pub.get("words", []), pub.get("off", [])
    for key, value in (("words", words), ("off", off)):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise gate.Usage("the %s copy of %s: publish.%s must be a list of strings" % (name, CONFIG, key))
    quote = pub.get("quoteWords", QUOTE_DEFAULT)
    if isinstance(quote, bool) or not isinstance(quote, int) or not 6 <= quote <= 40:
        quote = QUOTE_DEFAULT
    return {"words": [w for w in words if kr.valid_publish_word(w)], "off": {o for o in off if o in OFFABLE},
            "quoteWords": quote}


def settings(root):
    """The settings the checks use, and the labels of what this bundle changes in them."""
    copies = []
    if has_head(root):
        head = read_copy(root, "HEAD:" + CONFIG, "published")
        if head is not None:
            copies.append(("published", head))
    staged = read_copy(root, ":" + CONFIG, "staged")
    if staged is not None:
        copies.append(("staged", staged))
    pubs, cfgs = [], []
    for name, data in copies:
        pubs.append(publish_section(data, name))
        try:
            cfgs.append(scan.config_from(data, "the %s copy of %s" % (name, CONFIG)))
        except scan.ConfigError as exc:
            raise gate.Usage("the %s copy of %s: %s" % (name, CONFIG, exc))
    if not pubs:
        pubs, cfgs = [publish_section({}, "")], [scan.config_from({}, "")]
    words = list(dict.fromkeys(w for p in pubs for w in p["words"]))
    off = set.intersection(*[p["off"] for p in pubs])
    quote = min(p["quoteWords"] for p in pubs)
    patterns, seen = [], set()
    for cfg in cfgs:
        for item in cfg["patterns"]:
            key = (item[0], item[1], item[2].pattern)
            if key not in seen:
                seen.add(key)
                patterns.append(item)
    cfg = {"emails": set.intersection(*[c["emails"] for c in cfgs]),
           "domains": set.intersection(*[c["domains"] for c in cfgs]), "patterns": patterns, "vault": cfgs[-1]["vault"]}
    changed = []
    if len(copies) == 2:
        a, b = copies[0][1], copies[1][1]
        pa, pb = pubs[0], pubs[1]
        sa = a.get("scan") if isinstance(a.get("scan"), dict) else {}
        sb = b.get("scan") if isinstance(b.get("scan"), dict) else {}
        if sorted(set(pa["words"])) != sorted(set(pb["words"])):
            changed.append("words")
        if pa["off"] != pb["off"]:
            changed.append("off")
        if pa["quoteWords"] != pb["quoteWords"]:
            changed.append("quoteWords")
        if cfgs[0]["emails"] != cfgs[1]["emails"] or cfgs[0]["domains"] != cfgs[1]["domains"]:
            changed.append("allow")
        if json.dumps(sa.get("patterns", {}), sort_keys=True) != json.dumps(sb.get("patterns", {}), sort_keys=True):
            changed.append("patterns")
    return {"words": words, "off": off, "quoteWords": quote, "cfg": cfg, "changed": changed}


# ---- the checks ----------------------------------------------------------------------------------------

class Bundle:
    pass


def word_matcher(words):
    """[(words of the entry, last is a stem)] for publish.words."""
    rules = []
    for entry in words:
        star = entry.endswith("*")
        parts = WORD.findall((entry[:-1] if star else entry).casefold())
        if parts:
            rules.append((parts, star))
    return rules


def word_hits(line, rules):
    """The matched text of every listed word or phrase on the line."""
    tokens = [(m.group(0).casefold(), m.start(), m.end()) for m in WORD.finditer(line)]
    hits = []
    for parts, star in rules:
        n = len(parts)
        for i in range(len(tokens) - n + 1):
            ok = all(tokens[i + j][0] == parts[j] for j in range(n - 1))
            last = tokens[i + n - 1][0]
            if ok and (last == parts[-1] or (star and last.startswith(parts[-1]))):
                hits.append(line[tokens[i][1]:tokens[i + n - 1][2]])
    return hits


def source_names(root, conf):
    """Names the source-name check looks for: raw files with and without suffix, inbox and intake files in full."""
    return set(kr.source_name_files(root, conf))


def held_back(root, conf):
    """Pages under the wiki and the projects that git lists as untracked after staging: {name: path}."""
    v = vault_of(conf)
    out = run_git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")
    found = {}
    for item in out.stdout.decode("utf-8", "replace").split("\0") if out.returncode == 0 else []:
        if item.startswith("?? "):
            rel = item[3:]
            if rel.startswith(("%s/wiki/" % v, "%s/projects/" % v)):
                name = rel.rsplit("/", 1)[-1]
                for n in (name, os.path.splitext(name)[0]):
                    if len(n) >= 6:
                        found.setdefault(n.casefold(), rel)
    return found


def corpus_files(root, conf):
    v = vault_of(conf)
    kept = {k.casefold() for k in kr.kept_files(conf)}
    files = []
    for folder in ("%s/raw" % v, "%s/inbox" % v, "%s/daily" % v, "intake"):
        base = root.joinpath(*folder.split("/"))
        if base.is_dir():
            files += [p for p in base.rglob("*") if p.is_file() and p.name != ".gitkeep"
                      and p.relative_to(root).as_posix().casefold() not in kept]
    return sorted(files)


JSON_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})|\\.")


def quote_check(root, conf, units, size):
    """units: [[(word, path, line)]] in order. Returns (hits {(path, line)}, counts m n k)."""
    runs, firsts = {}, set()
    for unit in units:
        for i in range(len(unit) - size + 1):
            key = " ".join(w for w, _, _ in unit[i:i + size])
            runs.setdefault(key, set()).add((unit[i][1], unit[i][2]))
            firsts.add(unit[i][0])
    hits, m, n, k = set(), 0, 0, 0
    for full in corpus_files(root, conf):
        m += 1
        try:
            if full.stat().st_size > QUOTE_MAX_BYTES:
                k += 1
                continue
            text = scan.decode(full.read_bytes())
        except OSError:
            k += 1
            continue
        if text is None:
            k += 1
            continue
        n += 1
        if not runs:
            continue
        if full.suffix.lower() in (".json", ".jsonl", ".ndjson"):
            text = JSON_ESCAPE.sub(lambda mm: chr(int(mm.group(1), 16)) if mm.group(1) else " ", text)
        tokens = WORD.findall(scan.without_hidden(text).casefold())
        for i in range(len(tokens) - size + 1):
            if tokens[i] in firsts:
                found = runs.get(" ".join(tokens[i:i + size]))
                if found:
                    hits |= found
    return hits, (m, n, k)


def added_lines(old_text, new_text):
    """(added [(number, line)], blocks [(new line number, removed lines, added lines)]) of a changed file."""
    old, new = text_lines(old_text), text_lines(new_text)
    added, blocks = [], []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        added += [(j + 1, new[j]) for j in range(j1, j2)]
        blocks.append((j1 + 1, old[i1:i2], new[j1:j2]))
    return added, blocks


def analyze(root, conf, removed=()):
    check_folders(root, conf)
    b = Bundle()
    b.raw = raw_diff(root)
    b.id = hashlib.sha256(b.raw).hexdigest()[:12]
    b.entries = entries_of(b.raw)
    b.settings = settings(root)
    s = b.settings
    polish = gate.is_polish(conf)
    findings = []
    seen = set()

    def add(path, line, kind, value="", raw_value="", text="", **extra):
        key = (path, line, kind, value)
        if key in seen:
            return
        seen.add(key)
        findings.append(dict(path=path, line=line, kind=kind, value=value, raw=raw_value, text=text, **extra))

    raw_pats = kr.private_path_patterns(conf)
    names_rx = name_rule(source_names(root, conf))
    held = held_back(root, conf)
    held_rx = name_rule(held_name for held_name in held)
    rules = word_matcher(s["words"])
    off = s["off"]
    units, refs = [], set()
    staged_log_outputs = set()

    def check_text(e, number, line, raw_line):
        """Every check that reads a line or a new file's name (number 0)."""
        path, exempt = e["path"], e["identical"]
        report = lambda kind, rule, value: add(path, number, kind, scan.mask(kind, value), value, line)  # noqa: E731
        scan.scan_line(line, s["cfg"], report, gate_record=is_gate_file(path) and number > 0)
        if exempt:
            return
        if any(p.search(line) for p in raw_pats) or (names_rx and names_rx.search(line)):
            add(path, number, "source-name", "", "", line)
        if rules and path != CONFIG:
            target = scan.blank(line, scan.GATE_IDENTITY) if is_gate_file(path) and number > 0 else line
            for hit in word_hits(target, rules):
                add(path, number, "word", mask_word(hit), "", line)
        if held_rx and number > 0:
            for m in held_rx.finditer(line):
                add(path, number, "unshared", "", "", line, page=held.get(m.group(0).casefold(), m.group(0)))
        if "instruction" not in off and path != SETTINGS:
            if any(rx.search(part) for part in BREAKS.split(line) for _, rx in INSTRUCTION):
                add(path, number, "instruction", "", "", line)
        if "hidden" not in off and number > 0:
            cf = any(unicodedata.category(c) == "Cf" for c in raw_line) or hidden_selectors(raw_line)
            if cf or (not path.lower().endswith((".json", ".jsonl")) and
                      ("<!--" in line or "%%" in line or LINK_COMMENT.search(line) or BREAKS.search(line)
                       or HIDDEN_MARKUP.search(line) or LINK_TITLE.search(line))):
                add(path, number, "hidden", "", "", line)

    for e in b.entries:
        path = e["path"]
        data = None if e["status"] == "D" or e["new_mode"] == "160000" else blob(root, e["new"])
        e["data"] = data
        e["text"] = None if data is None else scan.decode(data)
        e["identical"] = data is not None and plugin_identical(path, data)
        e["record"] = is_tool_record(path, conf)
        e["control"] = is_control(path, conf)
        e["added"], e["blocks"] = [], []
        if e["status"] == "D":
            continue
        if kr.is_private(path, conf):
            add(path, 0, "private")
        if e["status"] == "A":
            if any(unicodedata.category(c) in ("Cc", "Cf") for c in path):
                add(path, 0, "path")
            typed = scan.file_finding(path.rsplit("/", 1)[-1])
            if typed:
                add(path, 0, "filetype", typed[1], "", path)
            check_text(e, 0, scan.without_hidden(path), path)
        if e["text"] is None:
            continue
        if e["text"] != data.decode("utf-8-sig", errors="replace"):  # read as UTF-16 or UTF-32: see scan.readings
            add(path, 0, "encoding")
        if e["status"] == "A":
            e["added"] = list(enumerate(text_lines(e["text"]), 1))
        else:
            old = None if e["old_mode"] == "160000" else blob(root, e["old"])
            old_text = scan.decode(old) if old is not None else None
            if old_text is None:
                e["added"] = list(enumerate(text_lines(e["text"]), 1))
            else:
                e["added"], e["blocks"] = added_lines(old_text, e["text"])
        unit, last = [], None
        for number, raw_line in e["added"]:
            line = scan.without_hidden(raw_line)
            check_text(e, number, line, raw_line)
            if not e["identical"]:  # the plugin's own files cite example references
                refs.update(raw_ref.refs_in(line))
            if path == conf["LOG_FILE"].replace("\\", "/").strip("/"):
                try:
                    item = json.loads(line)
                    if isinstance(item, dict) and item.get("op") == "ingest":
                        staged_log_outputs.update(str(o) for o in item.get("outputs") or [])
                except ValueError:
                    pass
            if e["identical"]:
                continue
            words = [(w, path, number) for w in WORD.findall(line.casefold())]
            table = line.lstrip().startswith("|")
            if table or last is None or number != last + 1:
                if unit:
                    units.append(unit)
                unit = []
            unit += words
            if table:
                units.append(unit)
                unit = []
            last = number
        if unit:
            units.append(unit)
    for rel in list(removed) + [p for p in index_paths(root) if kr.is_private(p, conf)]:
        add(rel, 0, "private")

    quote_state = None
    if "quote" not in off:
        hits, (m, n, k) = quote_check(root, conf, units, s["quoteWords"])
        missing = sum(1 for ref in sorted(refs) if not raw_ref.find(root, conf, ref))
        quote_state = {"m": m, "n": n, "k": k, "r": missing}
        texts = {(e["path"], number): line for e in b.entries for number, line in e["added"]}
        for path, number in sorted(hits):
            add(path, number, "quote", "", "", scan.without_hidden(texts.get((path, number), "")), n=s["quoteWords"])
    b.quote = quote_state
    b.staged_log_outputs = staged_log_outputs
    order = {e["path"]: k for k, e in enumerate(b.entries)}
    findings.sort(key=lambda f: (order.get(f["path"], len(order)), f["path"], f["line"]))
    for f in findings:
        f["say"] = say_finding(f, polish)
    b.findings = findings
    b.checks = check_states(b)
    b.status = "refused" if findings else ("empty" if not b.entries else "ok")
    b.preview_rel = ".gateway/outgoing/%s.md" % b.id
    b.reports = reports_for(root, conf, {e["path"] for e in b.entries})
    b.preview, b.long_files = build_preview(b, conf, polish)
    return b


def check_states(b):
    s, states = b.settings, {}
    for name in CHECKS:
        if name in s["off"]:
            states[name] = "off"
        elif name == "word" and not s["words"]:
            states[name] = "nothing"
        elif name == "quote":
            states[name] = dict(b.quote) if b.quote and b.quote["m"] else "nothing"
        else:
            states[name] = "ran"
    return states


def where_of(f, polish):
    path = shown(f["path"])
    return TEXT[polish]["file_name"].format(path=path) if f["line"] == 0 else "%s:%d" % (path, f["line"])


def say_finding(f, polish):
    t = TEXT[polish]
    kind = f["kind"]
    key = f["value"] if kind == "filetype" else kind
    return t[key].format(where=where_of(f, polish), path=shown(f["path"]), value=f["value"],
                         page=shown(f.get("page", "")), n=f.get("n", ""))


def finding_line(f):
    return "finding\t%s:%d\t%s\t%s" % (shown(f["path"]), f["line"], f["kind"], f["value"])


# ---- left-out reports -------------------------------------------------------------------------------------

def leftout_dir(root):
    return root / ".gateway" / "leftout"


def valid_report(data, root, conf):
    """The broken rule of a left-out report, or None. pages are normalized in place."""
    if not isinstance(data, dict):
        return "the report must be one JSON object"
    if data.get("schema") != 1:
        return "schema must be 1"
    if data.get("op") not in LEFTOUT_OPS:
        return "op must be one of %s" % ", ".join(LEFTOUT_OPS)
    source = data.get("source", "")
    if not isinstance(source, str) or (source and not (kr.SRC_REF_RE.fullmatch(source)
                                                       or re.fullmatch(r"(?:%s/)?wiki/[^\s`]+\.md" % re.escape(vault_of(conf)), source))):
        return "source must be a source reference (src:...), a wiki page or empty"
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages or not all(isinstance(p, str) and p.strip() for p in pages):
        return "pages must list at least one repo-relative path"
    fixed = []
    for page in pages:
        rel = page.strip().replace("\\", "/")
        if rel.startswith("wiki/"):
            rel = "%s/%s" % (vault_of(conf), rel)
        full = (root / rel).resolve()
        try:
            rel = full.relative_to(root).as_posix()
        except ValueError:
            return "a page path is outside the repository"
        if re.match(r"[A-Za-z]:|/", page.strip()) or kr.is_private(rel, conf):
            return "a page path is absolute or in a folder that stays on one machine"
        fixed.append(rel)
    items = data.get("left_out")
    if not isinstance(items, list):
        return "left_out must be a list"
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("what"), str) or not isinstance(item.get("why"), str):
            return "each left_out entry is {\"what\": ..., \"why\": ...}"
        what = item["what"].strip()
        if item["why"] not in WHY:
            return "why must be one of %s" % ", ".join(WHY)
        if not what or len(what) > WHAT_MAX:
            return "what must be one line of 1 to %d characters" % WHAT_MAX
        if "`" in what or "://" in what or any(unicodedata.category(c) in ("Cc", "Cf") for c in what):
            return "what may not hold a backtick, a link (://), a line break, or a control or format character"
    none = data.get("none", False)
    if not isinstance(none, bool):
        return "none must be true or false"
    if none and items:
        return "none: true goes with an empty left_out list"
    if not none and not items:
        return "an empty left_out list needs \"none\": true, so that no report and nothing cut never look the same"
    data["pages"] = list(dict.fromkeys(fixed))
    return None


def reports_for(root, conf, paths):
    found = []
    folder = leftout_dir(root)
    for full in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(full.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if valid_report(data, root, conf) is None and set(data["pages"]) & paths:
            found.append((full, data))
    return found


def source_label(source, polish):
    if kr.SRC_REF_RE.fullmatch(source or ""):
        _, kind, date, _ = source.split(":")
        return "%s, %s" % (raw_ref.KIND_WORDS[kind][0 if polish else 1], date)
    return source


# ---- the preview ------------------------------------------------------------------------------------------

def file_block(e, t, heading, long_files, b):
    out = ["", t[heading].format(path=shown(e["path"]))]
    if heading in ("deleted", "binary"):
        return out
    if e["status"] == "A" or not e["blocks"]:
        lines = [line for _, line in e["added"]]
        shown_lines = [scan.without_hidden(line) for line in lines[:SHOW_LINES]]
        out += [""] + fence(shown_lines)
    else:
        # What goes out is the added text, so only added lines count against SHOW_LINES. Removed lines have a
        # budget of their own: a long removal never pushes the outgoing text out of the preview.
        body, n_added, n_removed = [], 0, 0
        for number, removed, added in e["blocks"]:
            if n_added >= SHOW_LINES:
                break
            removed = [scan.without_hidden(x) for x in removed][:max(0, SHOW_LINES - n_removed)]
            n_removed += len(removed)
            added = [scan.without_hidden(x) for x in added][:SHOW_LINES - n_added]
            n_added += len(added)
            if removed:
                body += ["", t["line_removed"].format(n=number), ""] + fence(removed)
                if added:
                    body += ["", t["added"], ""] + fence(added)
            elif added:
                body += ["", t["line_added"].format(n=number), ""] + fence(added)
        out += body
        lines = [x for _, _, a in e["blocks"] for x in a]
    if len(lines) > SHOW_LINES:
        long_files.append(e)
        out += ["", t["long"].format(path=".gateway/outgoing/%s/%d.txt" % (b.id, len(long_files)))]
    return out


def ordered(entries):
    def rank(e):
        if e["status"] == "D":
            return 2
        if e["text"] is None:
            return 3
        return 0 if e["status"] == "A" else 1
    return sorted(entries, key=lambda e: (rank(e), e["path"]))


def heading_of(e):
    if e["status"] == "D":
        return "deleted"
    if e["text"] is None:
        return "binary"
    return "new" if e["status"] == "A" else "changed"


def build_preview(b, conf, polish):
    t = TEXT[polish]
    out = [t["title"].format(id=b.id), "", t["intro"]]
    if b.settings["changed"]:
        out += ["", t["settings"].format(what=", ".join(t["what"][k] for k in b.settings["changed"]))]
    out += ["", t["h_checks"], ""]
    if b.findings:
        out.append(t["stopped"].format(k=len(b.findings)))
        for f in b.findings:
            out += ["", f["say"], ""] + fence([f["text"] if f["line"] else shown(f["path"])])
        out += ["", t["checked"]]
    else:
        out.append(t["no_finding"])
    out.append("")
    for name in CHECKS:
        label, state = t["check_names"][name], b.checks[name]
        if state == "off":
            out.append(t["off"].format(check=label))
        elif name == "word" and state == "nothing":
            out.append(t["no_words"].format(check=label))
        elif name == "quote":
            out.append(t["quote_counts"].format(check=label, **state) if isinstance(state, dict)
                       else t["quote_none"].format(check=label))
        else:
            out.append(t["ran"].format(check=label))
    out += ["", t["blind"]]

    v = vault_of(conf)
    left, none = [], False
    for _, data in b.reports:
        none = none or data["none"]
        for item in data["left_out"]:
            why = t["why"][item["why"]]
            src = source_label(data.get("source", ""), polish)
            left.append(t["left_entry"].format(what=item["what"].strip(), why=why, source=src) if src
                        else t["left_entry_bare"].format(what=item["what"].strip(), why=why))
    covered = {p for _, data in b.reports for p in data["pages"]}
    lacking = [e["path"] for e in b.entries
               if e["status"] != "D" and not e["identical"] and not e["record"] and not e["control"]
               and e["path"] not in covered]
    made = [p for p in lacking if p in b.staged_log_outputs or (p.startswith(v + "/") and p[len(v) + 1:] in b.staged_log_outputs)]
    other = [p for p in lacking if p not in made]
    section = []
    if left:
        section += [""] + fence(left)
    if none:
        section += ["", t["left_none"]]
    if made:
        section += ["", t["left_ingest"].format(paths=", ".join(shown(p) for p in made))]
    if other:
        section += ["", t["left_missing"].format(paths=", ".join(shown(p) for p in other))]
    if left:
        section += ["", t["left_note"]]
    if section:
        out += ["", t["h_left"]] + section

    long_files = []
    control = [e for e in b.entries if e["control"] and not e["identical"]]
    if control:
        out += ["", t["h_control"], "", t["control_note"]]
        for e in ordered(control):
            out += file_block(e, t, heading_of(e), long_files, b)
    pages = [e for e in b.entries if not e["control"] and not e["record"] and not e["identical"]]
    identical = sorted(e["path"] for e in b.entries if e["identical"])
    out += ["", t["h_out"]]
    for e in ordered(pages):
        out += file_block(e, t, heading_of(e), long_files, b)
    if identical:
        out += ["", t["plugin"].format(n=len(identical)), ""] + fence([shown(p) for p in identical])
    records = [e for e in b.entries if e["record"] and not e["control"] and not e["identical"]]
    if records:
        out += ["", t["h_records"]]
        for e in ordered(records):
            out += file_block(e, t, heading_of(e), long_files, b)
    text = "\n".join(out) + "\n"
    secrets = sorted({f["raw"] for f in b.findings if f["kind"] in ("secret", "pii") and f["raw"]}, key=len, reverse=True)
    for value in secrets:
        text = text.replace(value, scan.mask("secret" if any(f["raw"] == value and f["kind"] == "secret"
                                                              for f in b.findings) else "pii", value))
    return text, long_files


def write_preview(root, b):
    folder = root / ".gateway" / "outgoing"
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / ("%s.md" % b.id), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(b.preview)
    if b.long_files:
        extra = folder / b.id
        extra.mkdir(exist_ok=True)
        for k, e in enumerate(b.long_files, 1):
            (extra / ("%d.txt" % k)).write_bytes(e["data"])


def housekeeping(root):
    """Previews, their folders and sent reports older than 30 days are deleted."""
    limit = time.time() - KEEP_DAYS * 86400
    for folder in (root / ".gateway" / "outgoing", leftout_dir(root) / "sent"):
        if not folder.is_dir():
            continue
        for item in folder.iterdir():
            try:
                if item.stat().st_mtime < limit:
                    shutil.rmtree(str(item)) if item.is_dir() else item.unlink()
            except OSError:
                pass


# ---- commands ---------------------------------------------------------------------------------------------

def say_lines(b, polish):
    t = TEXT[polish]
    lines = []
    control = [e for e in b.entries if e["control"] and not e["identical"]]
    if control:
        lines.append(t["control"].format(n=len(control)))
    if b.settings["changed"]:
        lines.append(t["settings"].format(what=", ".join(t["what"][k] for k in b.settings["changed"])))
    if b.status == "ok":
        lines += [t["ok1"].format(n=len(b.entries), preview=b.preview_rel), t["ok2"]]
    else:
        lines.append(t["refused"].format(k=len(b.findings), preview=b.preview_rel))
        lines += [f["say"] for f in b.findings]
    return lines


def cmd_check(root, conf, args):
    as_json = "--json" in args
    paths = [a for a in args if a != "--json"]
    if any(a.startswith("--") for a in paths):
        raise gate.Usage("check takes --json and paths")
    refuse_busy(root)
    check_folders(root, conf)
    housekeeping(root)
    removed = stage(root, conf, paths)
    b = analyze(root, conf, removed)
    polish = gate.is_polish(conf)
    if b.status == "empty":
        waiting = ahead_count(root)
        say = [TEXT[polish]["empty_waiting"].format(n=waiting) if waiting else TEXT[polish]["empty"]]
        if as_json:
            print(json.dumps({"status": "empty", "waiting": waiting, "say": say}, ensure_ascii=False))
        else:
            print("empty\t%d" % waiting)
            for line in say:
                print("say\t%s" % line)
        return 0
    write_preview(root, b)
    say = say_lines(b, polish)
    if as_json:
        print(json.dumps({"status": b.status, "id": b.id, "preview": b.preview_rel, "files": len(b.entries),
                          "checks": b.checks, "merge": False,
                          "findings": [{"path": shown(f["path"]), "line": f["line"], "kind": f["kind"],
                                        "value": f["value"], "say": f["say"]} for f in b.findings],
                          "control": [shown(e["path"]) for e in b.entries if e["control"] and not e["identical"]],
                          "say": say}, ensure_ascii=False))
    else:
        if b.status == "ok":
            print("ok\t%s\t%s\t%d" % (b.id, b.preview_rel, len(b.entries)))
        else:
            print("refused\t%s\t%s\t%d" % (b.id, b.preview_rel, len(b.findings)))
            for f in b.findings:
                print(finding_line(f))
        for line in say:
            print("say\t%s" % line)
    return 0 if b.status == "ok" else 1


def ran_checks(b):
    names = []
    for name in CHECKS:
        state = b.checks[name]
        if state == "off" or state == "nothing":
            continue
        if name == "quote" and (not isinstance(state, dict) or state["n"] == 0):
            continue
        names.append(name)
    return names


def message_of(b):
    lines = ["hg publish: %d file(s)" % len(b.entries), ""]
    for e in b.entries[:MAX_MESSAGE_PATHS]:
        lines.append("%s %s" % (e["status"], shown(e["path"])))
    if len(b.entries) > MAX_MESSAGE_PATHS:
        lines.append("... and %d more" % (len(b.entries) - MAX_MESSAGE_PATHS))
    lines += ["", "Hg-Publish: 1", "Hg-Bundle: %s" % b.id, "Hg-Checks: %s" % " ".join(ran_checks(b))]
    return "\n".join(lines) + "\n"


def cmd_commit(root, conf, args):
    if len(args) != 1 or not re.fullmatch(r"[0-9a-f]{12}", args[0]):
        raise gate.Usage("commit takes one argument: the 12-digit id hg-tool publish check printed")
    refuse_busy(root)
    b = analyze(root, conf)
    if not b.entries or b.id != args[0]:
        raise gate.Refused(STALE)
    preview = root / ".gateway" / "outgoing" / ("%s.md" % b.id)
    try:
        on_disk = preview.read_bytes()
    except OSError:
        raise gate.Refused(NOT_OURS)
    if on_disk != b.preview.encode("utf-8"):
        raise gate.Refused(NOT_OURS)
    if b.findings:
        raise gate.Refused("\n".join([finding_line(f) for f in b.findings] + ["nothing was committed."]))
    if not gate.git_email(root):
        raise gate.Refused("git has no user.email here, and a commit must say who made it. Set it with git config.")
    out = run_git(root, "commit", "-q", "-F", "-", data=message_of(b).encode("utf-8"))
    if out.returncode != 0:
        raise gate.Refused("git refused the commit: %s" % first_line((out.stderr or out.stdout).decode("utf-8", "replace")))
    _, sha, _ = git_text(root, "rev-parse", "HEAD")
    paths = {e["path"] for e in b.entries}
    sent = leftout_dir(root) / "sent"
    for full, data in b.reports:
        if set(data["pages"]) <= paths:
            sent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(str(full), str(sent / full.name))
            except OSError:
                pass
    print("committed\t%s\t%d" % (sha.strip()[:12], len(b.entries)))
    print("say\t%s" % TEXT[gate.is_polish(conf)]["committed"].format(n=len(b.entries)))
    return 0


def cmd_leftout(root, conf, args):
    if len(args) != 1:
        raise gate.Usage("leftout takes one argument: the report a model drafted")
    rel = resolve_arg(root, args[0])
    full = root / rel
    try:
        data = json.loads(full.read_text(encoding="utf-8-sig"))
    except OSError:
        raise gate.Refused("%s cannot be read." % shown(rel))
    except ValueError as exc:
        raise gate.Refused("the report is not valid JSON: %s" % exc)
    if isinstance(data, dict) and "created" not in data:
        data["created"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    problem = valid_report(data, root, conf)
    if problem is None and not isinstance(data.get("created"), str):
        problem = "created must be a time as text"
    if problem:
        raise gate.Refused(problem)
    report = {"schema": 1, "created": data["created"], "op": data["op"], "source": data.get("source", ""),
              "pages": data["pages"], "none": data.get("none", False),
              "left_out": [{"what": i["what"].strip(), "why": i["why"]} for i in data["left_out"]]}
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    folder = leftout_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / ("%s.json" % hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    if full.resolve() != dest.resolve():
        try:
            full.unlink()
        except OSError:
            pass
    print(dest.relative_to(root).as_posix())
    return 0


def cmd_withdraw(root, conf, args):
    if len(args) != 1:
        raise gate.Usage("withdraw takes one argument: the wiki page")
    rel = resolve_arg(root, args[0])
    v = vault_of(conf)
    tracked = run_git(root, "--literal-pathspecs", "ls-files", "--error-unmatch", "--", rel).returncode == 0
    if not rel.startswith(v + "/wiki/") or not tracked:
        raise gate.Refused("%s is not a published wiki page. Only a tracked file under %s/wiki/ can be withdrawn."
                           % (shown(rel), v))
    project = "cross"
    head = blob(root, "HEAD:" + rel)
    if head is not None:
        try:
            front = kr.split_frontmatter(head.decode("utf-8", "replace"))[0]
            value = (kr.load_yaml(front) or {}).get("project") if front else None
            project = value if isinstance(value, str) and kr.valid_project_slug(value) else "cross"
        except (kr.RegistryError, ValueError, AttributeError):
            pass
    out = run_git(root, "--literal-pathspecs", "rm", "-q", "--", rel)
    if out.returncode != 0:
        raise gate.Refused("git could not remove the page: %s" % first_line(out.stderr.decode("utf-8", "replace")))
    regenerate_index(root)
    import log_append  # imported here: only a withdrawal writes the log
    if log_append.main(["--op", "archive", "--agent", "hg-publish", "--project", project,
                        "--inputs", rel[len(v) + 1:], "--note", "withdrawn"]) != 0:
        print("publish: the page was removed, but the log line was not written", file=sys.stderr)
    print("say\t%s" % TEXT[gate.is_polish(conf)]["withdrawn"].format(path=shown(rel)))
    return 0


COMMANDS = {"check": cmd_check, "leftout": cmd_leftout, "commit": cmd_commit, "withdraw": cmd_withdraw}


def main(argv):
    kr.stdio_utf8()
    if not argv or argv[0] in ("-h", "--help") or argv[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        root = workspace()
        conf = kr.load_conf(root)
        return COMMANDS[argv[0]](root, conf, list(argv[1:]))
    except gate.Usage as exc:
        print("publish: %s" % exc, file=sys.stderr)
        return 2
    except gate.Refused as exc:
        print("publish: %s" % exc, file=sys.stderr)
        return 1
    except kr.RegistryError as exc:
        print("publish: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
