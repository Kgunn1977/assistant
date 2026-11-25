r"""Start fresh: the owner's own rules and lists are deleted, so the assistant learns them again from his cards
(the RSI plan, "Start fresh"). The store map is in ITEMS.md ("Start fresh").

Run only on the owner's confirmed press of Start fresh in Settings (answers.py hands that one press here); no pass, setup
or update calls it, and a press that reached no listener is refused, not done late. Deleting is outright (guardrail C4):

- a store that is wholly his (voice.json, the consolidation drafts of his rules documents) is deleted. filter_rules.json
  is left holding no rules and its next rule number, so a new rule never takes the number of an old one that the rule
  book or a kept version names;
- a file that also holds other things (personal.json, settings.json, the rules documents) is rewritten in place without
  his entries only.

Core rules are part of the program (its core_rules folder), never in a home, so nothing here reaches them: every entry in
the home's rules documents is his. The rule book, RSI versions and state, standing approvals, taught guardrails, mods,
cards and every setting choice are left as they are. A home with nothing of his left changes nothing.

    start_fresh(home)      {"moved": [...], "record": None, "said": plain words}   (moved: what was deleted or cleared)
    from_press(rec)        the Settings press: done only when it carries the confirm; returns the plain words
"""
import datetime as dt
import json
import os
import re
import paths

CONFIRM = {"start_fresh": "confirmed"}        # what the page sends only after his yes to the question
QUESTION = "This deletes your own rules and lists. The built-in rules, the rule book and your cards stay. Continue?"
NOT_CONFIRMED = "Not done: Start fresh needs your yes to its question first. Nothing was deleted."
MISSED = ("Not done: this page couldn't reach your computer when you pressed Start fresh, so nothing was deleted. "
          "Press Start fresh in Settings again.")
NOTHING = "Nothing to delete: your own rules and lists are already cleared."
FRESH_FOR = dt.timedelta(minutes=10)          # a press older than this (the listener was off) is never acted on late

# The home's rules documents (core\rules.py DOCS): every entry in them is his.
DOCS = (("Resources", "Rules", "Junk rules.md"), ("Resources", "Data", "Junk senders.md"),
        ("Resources", "Rules", "Repair.md"), ("Resources", "Rules", "People and who handles what.md"),
        ("Resources", "Rules", "Reading messages.md"), ("Resources", "Rules", "Calendar.md"),
        ("Resources", "Rules", "Writing the briefing.md"), ("Resources", "Rules", "Your briefing answers.md"),
        ("Resources", "Rules", "System.md"))
DRAFTS = ("Resources", "Rules", "Draft")
ENTRY = re.compile(r"^- \[(\d+)\] ")
SAID = "  You said: "
PERSONAL_LISTS = ("ignore_senders", "keep_words")       # personal.json: senders to ignore, words that keep a mailing
FILTER_LISTS = ("always_through",)                      # settings.json "filter": priority senders


# --- reading and writing, all under the home given ----------------------------------------------------------
def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path, obj):
    """Whole file to a temp name, then renamed, as common.write_json writes."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def _read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_text(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def _owner_lines(text):
    """(kept lines, his entries) of one of the home's rules documents: each entry, with its "You said" line, is his.
    Headings, intros and anything else written in the document stay."""
    kept, his = [], []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if ENTRY.match(lines[i]):
            entry = [lines[i]]
            while i + 1 < len(lines) and lines[i + 1].startswith(SAID):
                i += 1
                entry.append(lines[i])
            his.append("\n".join(entry))
        else:
            kept.append(lines[i])
        i += 1
    return kept, his


# --- the delete -------------------------------------------------------------------------------------------------
class _Run:
    def __init__(self, home):
        self.home = home
        self.when = dt.datetime.now()
        self.moved = []

    def _rel(self, path):
        return os.path.relpath(path, self.home)

    def delete_whole(self, store, rel):
        src = os.path.join(self.home, *rel)
        os.remove(src)
        if os.path.exists(src):
            raise RuntimeError(f"{store}: the delete did not land")
        self.moved.append({"store": store, "file": self._rel(src), "what": "whole file deleted"})

    def rewrite(self, store, rel, entries, write):
        """The file rewritten in place by write(), without his entries."""
        src = os.path.join(self.home, *rel)
        write(src)
        self.moved.append({"store": store, "file": self._rel(src), "what": "his entries deleted", "entries": entries})


def _filter_rules(run):
    rel = ("personal", "filter_rules.json")
    p = os.path.join(run.home, *rel)
    got = _read_json(p)
    if not got or not got.get("rules"):
        return
    nxt = max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in got["rules"]
                                             if isinstance(r, dict) and str(r.get("id", "")).isdigit()])
    _write_json(p, {"rules": [], "next": nxt})
    run.moved.append({"store": "his rules (show less, always show, how cards are written)", "file": run._rel(p),
                      "what": "his entries deleted"})


def _voice(run):
    rel = ("personal", "voice.json")
    if _read_json(os.path.join(run.home, *rel)):
        run.delete_whole("his writing style (learned and his own corrections)", rel)


def _personal_lists(run):
    rel = ("personal", "personal.json")
    got = _read_json(os.path.join(run.home, *rel))
    if not got:
        return
    his = {k: got[k] for k in PERSONAL_LISTS if got.get(k)}
    if not his:
        return

    def write(path):
        _write_json(path, {k: v for k, v in got.items() if k not in his})
    run.rewrite("senders to ignore, words that keep a mailing", rel, his, write)


def _filter_lists(run):
    rel = ("personal", "settings.json")
    got = _read_json(os.path.join(run.home, *rel))
    f = (got or {}).get("filter")
    if not isinstance(f, dict):
        return
    his = {k: f[k] for k in FILTER_LISTS if f.get(k)}
    if not his:
        return

    def write(path):
        _write_json(path, dict(got, filter={k: v for k, v in f.items() if k not in his}))
    run.rewrite("priority senders", rel, his, write)


def _rules_docs(run):
    found = []
    for rel in DOCS:
        p = os.path.join(run.home, *rel)
        if not os.path.exists(p):
            continue
        text = _read_text(p)
        kept, his = _owner_lines(text)
        if his:
            found.append((rel, kept, his))
    for rel, kept, his in found:
        run.rewrite("his junk senders" if rel[-1] == "Junk senders.md" else "his entries in a rules document",
                    rel, his, lambda path, kept=kept: _write_text(path, "\n".join(kept)))
    d = os.path.join(run.home, *DRAFTS)
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".md") and os.path.isfile(os.path.join(d, name)):
                run.delete_whole("a shortened draft of a rules document", DRAFTS + (name,))


def start_fresh(home):
    """Every personal-rule store of this home deleted, or his entries taken out of a shared file."""
    home = os.path.abspath(str(home or ""))
    if not os.path.isdir(os.path.join(home, "personal")):
        raise ValueError(f"not an assistant home (no personal folder): {home}")
    run = _Run(home)
    for step in (_filter_rules, _voice, _personal_lists, _filter_lists, _rules_docs):
        step(run)
    if not run.moved:
        return {"moved": [], "record": None, "said": NOTHING}
    n = len(run.moved)
    said = (f"Started fresh: I deleted {n} of your own set{'s' if n != 1 else ''} of rules and lists. "
            f"The built-in rules, the rule book and your cards stay.")
    return {"moved": run.moved, "record": None, "said": said}


def from_press(rec):
    """The Start fresh press from Settings: done only when it carries the confirm the page sends after his yes, and only
    while it is fresh (pressed within FRESH_FOR, by the page's own clock); one a listener finds later is refused."""
    try:
        body = json.loads(str((rec or {}).get("text") or ""))
    except ValueError:
        body = None
    if body != CONFIRM:
        return NOT_CONFIRMED
    try:
        age = dt.datetime.now() - dt.datetime.fromisoformat(str((rec or {}).get("at") or ""))
    except ValueError:
        return MISSED
    if not dt.timedelta(minutes=-2) <= age <= FRESH_FOR:
        return MISSED
    return start_fresh(paths.HOME)["said"]
