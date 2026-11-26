r"""Start fresh: the owner's own rules and lists are put aside, so the assistant works as it would for someone who has
never used it and learns them again from his cards (the RSI plan, "Start fresh"); Bring back puts them back. The store
map is in ITEMS.md ("Start fresh").

Put aside: what is taken out of each store is kept in one file, personal\Set aside\set_aside.json (a second Start
fresh adds to it). Bring back puts every one of them back where it came from, then deletes that file outright: a rule
taught since is kept beside them.

Run only on the owner's confirmed press of Start fresh in Settings (answers.py hands that one press here); no pass, setup
or update calls it, and a press that reached no listener is refused, not done late. Nothing is deleted; it is put aside:

- a store that is wholly his (voice.json, the consolidation drafts of his rules documents) is taken away. filter_rules.json
  is left holding no rules and its next rule number, so a new rule never takes the number of an old one that the rule
  book or a kept version names;
- a file that also holds other things (personal.json, settings.json, the rules documents) is rewritten in place without
  his entries only.

Core rules are part of the program (its core_rules folder), never in a home, so nothing here reaches them: every entry in
the home's rules documents is his. The rule book, RSI versions and state, standing approvals, taught guardrails, mods,
cards and every setting choice are left as they are. A home with nothing of his left changes nothing.

    start_fresh(home)      {"moved": [...], "record": None, "said": plain words}   (moved: what was put aside)
    bring_back(home)       {"back": [...], "said": plain words}                     (back: what was put back)
    from_press(rec)        the Settings press: done only when it carries the confirm (or Bring back); returns the plain words
"""
import datetime as dt
import json
import os
import re
import paths

CONFIRM = {"start_fresh": "confirmed"}        # what the page sends only after his yes to the question
BRING_BACK = {"start_fresh": "bring_back"}    # Bring back: his rules and lists put aside by Start fresh go back
QUESTION = ("This puts your own rules and lists aside, so I work as I would for someone new. The built-in rules, the rule "
            "book and your cards stay. Bring back puts them back any time. Continue?")
NOT_CONFIRMED = "Not done: Start fresh needs your yes to its question first. Nothing was changed."
MISSED = ("Not done: this page couldn't reach your computer when you pressed it, so nothing was changed. "
          "Press it in Settings again.")
NOTHING = "Nothing to put aside: your own rules and lists are already cleared."
NOTHING_ASIDE = "Nothing to bring back: none of your rules or lists are set aside."
ASIDE = ("personal", "Set aside", "set_aside.json")
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


# --- putting aside ---------------------------------------------------------------------------------------------
class _Run:
    def __init__(self, home):
        self.home = home
        self.when = dt.datetime.now()
        self.moved = []
        self.aside = []         # what to put back: {"kind", "rel", ...}, kept in personal\Set aside\set_aside.json

    def _rel(self, path):
        return os.path.relpath(path, self.home)

    def take_whole(self, store, rel, kind):
        """A store that is wholly his: its text is kept aside, then the file is taken away."""
        src = os.path.join(self.home, *rel)
        self.aside.append({"kind": kind, "store": store, "rel": list(rel), "text": _read_text(src)})
        os.remove(src)
        if os.path.exists(src):
            raise RuntimeError(f"{store}: it was not taken away")
        self.moved.append({"store": store, "file": self._rel(src), "what": "whole file put aside"})

    def rewrite(self, store, rel, entries, write, kind):
        """The file rewritten in place by write(), without his entries, which are kept aside."""
        src = os.path.join(self.home, *rel)
        self.aside.append({"kind": kind, "store": store, "rel": list(rel), "entries": entries})
        write(src)
        self.moved.append({"store": store, "file": self._rel(src), "what": "his entries put aside", "entries": entries})


def _filter_rules(run):
    rel = ("personal", "filter_rules.json")
    p = os.path.join(run.home, *rel)
    got = _read_json(p)
    if not got or not got.get("rules"):
        return
    nxt = max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in got["rules"]
                                             if isinstance(r, dict) and str(r.get("id", "")).isdigit()])
    run.aside.append({"kind": "filter_rules", "store": "his rules (show less, always show, how cards are written)",
                      "rel": list(rel), "entries": got["rules"]})
    _write_json(p, {"rules": [], "next": nxt})
    run.moved.append({"store": "his rules (show less, always show, how cards are written)", "file": run._rel(p),
                      "what": "his entries put aside"})


def _voice(run):
    rel = ("personal", "voice.json")
    if _read_json(os.path.join(run.home, *rel)):
        run.take_whole("his writing style (learned and his own corrections)", rel, "whole")


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
    run.rewrite("senders to ignore, words that keep a mailing", rel, his, write, "lists")


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
    run.rewrite("priority senders", rel, his, write, "filter_lists")


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
                    rel, his, lambda path, kept=kept: _write_text(path, "\n".join(kept)), "doc")
    d = os.path.join(run.home, *DRAFTS)
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".md") and os.path.isfile(os.path.join(d, name)):
                run.take_whole("a shortened draft of a rules document", DRAFTS + (name,), "whole")


def _save_aside(home, aside):
    p = os.path.join(home, *ASIDE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    got = _read_json(p) or {}
    got.setdefault("stores", []).extend(aside)
    got["at"] = dt.datetime.now().isoformat(timespec="seconds")
    _write_json(p, got)


def start_fresh(home):
    """Every personal-rule store of this home put aside: a store wholly his taken away, or his entries taken out of a
    shared file; what was taken is kept in personal/Set aside/set_aside.json for Bring back."""
    home = os.path.abspath(str(home or ""))
    if not os.path.isdir(os.path.join(home, "personal")):
        raise ValueError(f"not an assistant home (no personal folder): {home}")
    run = _Run(home)
    try:
        for step in (_filter_rules, _voice, _personal_lists, _filter_lists, _rules_docs):
            step(run)
    finally:
        if run.aside:           # whatever was taken is kept, even if a later store failed
            _save_aside(home, run.aside)
    if not run.moved:
        return {"moved": [], "record": None, "said": NOTHING}
    n = len(run.moved)
    said = (f"Started fresh: I put {n} of your own set{'s' if n != 1 else ''} of rules and lists aside, so I work as I "
            f"would for someone new. The built-in rules, the rule book and your cards stay. Bring back puts them back.")
    return {"moved": run.moved, "record": None, "said": said}


# --- bringing back ---------------------------------------------------------------------------------------------
def _back_one(home, s):
    p = os.path.join(home, *s["rel"])
    kind = s.get("kind")
    if kind == "whole":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        _write_text(p, s["text"])
    elif kind == "filter_rules":
        cur = _read_json(p) or {"rules": [], "next": 1}
        have = {str(r.get("id")) for r in cur.get("rules") or [] if isinstance(r, dict)}
        rules = list(cur.get("rules") or []) + [r for r in s["entries"] if str(r.get("id")) not in have]
        rules.sort(key=lambda r: int(r["id"]) if str(r.get("id", "")).isdigit() else 0)
        nxt = max([int(cur.get("next") or 1)] + [int(r["id"]) + 1 for r in rules if str(r.get("id", "")).isdigit()])
        _write_json(p, dict(cur, rules=rules, next=nxt))
    elif kind in ("lists", "filter_lists"):
        cur = _read_json(p) or {}
        box = cur.setdefault("filter", {}) if kind == "filter_lists" else cur
        if not isinstance(box, dict):
            box = cur["filter"] = {}
        for k, v in s["entries"].items():
            now = box.get(k)
            if isinstance(v, list) and isinstance(now, list):
                box[k] = now + [x for x in v if x not in now]
            elif not now:
                box[k] = v
        _write_json(p, cur)
    elif kind == "doc":
        text = _read_text(p) if os.path.exists(p) else ""
        add = [e for e in s["entries"] if e not in text]
        if add:
            _write_text(p, text.rstrip("\n") + "\n" + "\n".join(add) + "\n")
    else:
        raise ValueError(f"unknown kind of store set aside: {kind}")
    return {"store": s.get("store"), "file": os.path.join(*s["rel"])}


def bring_back(home):
    """Every rule and list Start fresh put aside goes back where it came from; then the set-aside file is deleted."""
    home = os.path.abspath(str(home or ""))
    p = os.path.join(home, *ASIDE)
    got = _read_json(p)
    if not got or not got.get("stores"):
        return {"back": [], "said": NOTHING_ASIDE}
    back = [_back_one(home, s) for s in got["stores"]]
    os.remove(p)
    try:
        os.rmdir(os.path.dirname(p))
    except OSError:
        pass
    n = len(back)
    return {"back": back, "said": f"Brought back {n} of your own set{'s' if n != 1 else ''} of rules and lists, as they were."}


def from_press(rec):
    """The Start fresh press from Settings: done only when it carries the confirm the page sends after his yes, and only
    while it is fresh (pressed within FRESH_FOR, by the page's own clock); one a listener finds later is refused."""
    try:
        body = json.loads(str((rec or {}).get("text") or ""))
    except ValueError:
        body = None
    if body not in (CONFIRM, BRING_BACK):
        return NOT_CONFIRMED
    try:
        age = dt.datetime.now() - dt.datetime.fromisoformat(str((rec or {}).get("at") or ""))
    except ValueError:
        return MISSED
    if not dt.timedelta(minutes=-2) <= age <= FRESH_FOR:
        return MISSED
    return (bring_back if body == BRING_BACK else start_fresh)(paths.HOME)["said"]
