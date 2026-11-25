"""The rules, kept as documents: one document per subject.

    python rules.py list [doc]            what a document holds
    python rules.py pending               proposals waiting on the owner
    python rules.py add <doc> "<text>"    a rule the owner approved whole, in session
    python rules.py propose <doc> "<text>" "<their words>"
    python rules.py confirm <id> ["<edited text>"]
    python rules.py reject <id>           a proposal they turned down
    python rules.py never <id>            a junk proposal they answered "never junk"
    python rules.py delete <id>           a rule they said to delete

Each agent reads only the documents written for it (READERS). Core rules (how
the system works) are part of the program, in its core_rules folder: Goals.md
and a document's core entries (Junk rules 559-562 and 631). They are read from
there, never copied into a home, and nothing here writes or removes one, so an
update reaches them. A home's own documents hold only the owner's rules, which
he can open and edit by hand; an entry there with a core rule's number (a copy
an older home was given) is not read, because the program's is. Goals.md is not
parsed as rules; goals() returns its text, which rides every agent payload. The junk sender lists are
data: they live in Resources/Data/Junk senders.md, in the same entry format,
and junk(), propose() and confirm() read and write that file.

THE FORMAT, one entry per line, numbers never reused:
    - [323] (G1) rule text
    - [360] from `%@reply.%`: label                      (junk senders)
    - [490] from `<sender>` with subject `<shape>`: label (junk senders)
Under "## Waiting for your OK" an entry carries its proposal date and where it
goes when confirmed, and the owner's own words on the next line:
    - [549] (proposed 2026-09-30 04:15, for Always junk) from `...`: ...
      You said: ...
Edits touch only the lines of the entry they change, so anything else the
owner writes in a document stays where they put it.

Confirm before permanent: a proposal never reaches an agent, rejection deletes
it, and an unanswered one expires after PROPOSAL_TTL_DAYS.

A document named here but missing from the folder reads as empty.
"""

import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import paths  # noqa: E402

RULES_DIR = os.environ.get("ASSISTANT_RULES_DIR") or paths.RULES
DATA_DIR = os.environ.get("ASSISTANT_DATA_DIR") or paths.DATA
DRAFT_DIR = os.path.join(RULES_DIR, "Draft")
CORE_DIR = paths.CORE_RULES   # the program's own core rules: read only
PROPOSAL_TTL_DAYS = 5  # unconfirmed proposals expire
SIZE_CAP = 4000        # a rules document over this is consolidated

# key -> (file title, who reads it)
DOCS = {
    "junk": ("Junk rules", "the judge, when sorting messages"),
    "senders": ("Junk senders", "the judge and the junk prefilter"),
    "repair": ("Repair", "every run agent"),
    "people": ("People and who handles what", "the judge"),
    "reading": ("Reading messages", "the judge"),
    "calendar": ("Calendar", "the judge and the briefing writer"),
    "briefing": ("Writing the briefing", "the briefing writer"),
    "answers": ("Your briefing answers",
                "the session where you answer the briefing"),
    "system": ("System", "the judge"),
}
READERS = {
    "judge": ["junk", "senders", "people", "reading", "calendar",
              "system", "repair"],
    "composer": ["briefing", "calendar", "repair"],
    "answers": ["answers"],
}
# documents kept as data, outside the rules folder; never size-capped
DATA_DOCS = {"senders"}
# the old database domains, still accepted by callers that pass one
LEGACY = {"noise": "junk", "judgment": "reading", "contacts": "people",
          "routing": "people", "calendar": "calendar", "briefing": "briefing",
          "briefing-session": "answers", "system": "system"}

RULES = "Rules"
ALWAYS, PROBABLY, NEVER = "Always junk", "Probably junk", "Never junk"
JUNK_SECTIONS = (ALWAYS, PROBABLY, NEVER)
SUBJECTS = "Subject patterns"
CAL_ADD = "Added to your calendar without asking"
WAITING = "Waiting for your OK"
SECTION_ORDER = {
    "senders": [ALWAYS, PROBABLY, NEVER, SUBJECTS],
    "calendar": [CAL_ADD, RULES],
}
JUNK_INTRO = {
    ALWAYS: "Settled before the judge reads anything.",
    PROBABLY: "Usually junk; the judge still reads these.",
    NEVER: "Never treated as junk, whatever the list above says.",
}

ENTRY = re.compile(r"^- \[(\d+)\] (?:\(proposed (\d{4}-\d{2}-\d{2} \d{2}:\d{2}),"
                   r" for ([^)]+)\) )?(.*)$")
JUNK_BODY = re.compile(r"^from `([^`]*)`(?: with subject `([^`]*)`)?: (.*)$")
SAID = "  You said: "
NEXT = re.compile(r"Next rule number: (\d+)")


class RulesError(Exception):
    pass


def resolve(doc):
    doc = LEGACY.get(doc, doc)
    if doc not in DOCS:
        raise RulesError(f"no rules document called {doc!r}")
    return doc


def _sender_doc(doc, pattern):
    """A junk entry that carries a sender pattern belongs in the sender data."""
    return "senders" if doc == "junk" and pattern is not None else doc


def path_of(doc):
    doc = resolve(doc)
    base = DATA_DIR if doc in DATA_DOCS else RULES_DIR
    return os.path.join(base, DOCS[doc][0] + ".md")


def missing():
    """Titles of the documents whose file is not on disk."""
    return [DOCS[d][0] for d in DOCS if not os.path.exists(path_of(d))]


def goals():
    """The program's Goals.md as written, for the "goals" key of every agent payload."""
    p = os.path.join(CORE_DIR, "Goals.md")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        return f.read().strip()


def reference():
    """Resources\\Data\\Reference.md as written, for the "reference" key of every agent payload."""
    p = os.path.join(DATA_DIR, "Reference.md")
    if not os.path.exists(p):
        return ""
    with open(p, encoding="utf-8") as f:
        return f.read().strip()


def _one_line(s):
    return re.sub(r"\s*\n\s*", " ", (s or "").strip())


# --- reading -----------------------------------------------------------
def _read_lines(doc):
    """The home's lines of a document; a document not on disk reads as empty
    (missing() names it)."""
    return _lines_at(path_of(doc))


def _lines_at(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return f.read().split("\n")


def core_path(doc):
    """Where the program keeps a document's core rules (it may hold none)."""
    return os.path.join(CORE_DIR, DOCS[resolve(doc)][0] + ".md")


def core_ids():
    """The numbers of every core rule, in every document."""
    return {e["id"] for d in DOCS for e in _parse_lines(d, _lines_at(core_path(d)), True)}


def parse(doc, home_only=False):
    """Every entry in one document, with the line numbers it occupies: the
    program's core entries ("core": True, line numbers in the program's copy),
    then the home's own (line numbers in the home's file). An entry in the home
    with a core rule's number is not read: the program's copy is. home_only:
    the home's own entries alone, line numbers all in the home's file."""
    doc = resolve(doc)
    core = [] if home_only else _parse_lines(doc, _lines_at(core_path(doc)), True)
    skip = core_ids()
    return core + [e for e in _parse_lines(doc, _read_lines(doc), False) if e["id"] not in skip]


def _parse_lines(doc, lines, core):
    out, section = [], None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if line.startswith(SAID) and out and out[-1]["last"] == i - 1:
            out[-1]["owner_said"] = line[len(SAID):]
            out[-1]["last"] = i
            continue
        if not line.startswith("- ["):
            continue
        m = ENTRY.match(line)
        if not m:
            raise RulesError(f"{DOCS[doc][0]}, line {i + 1}: cannot read {line[:60]!r}")
        rid, when, target, body = m.groups()
        e = {"id": int(rid), "doc": doc, "title": DOCS[doc][0], "core": core,
             "section": section, "status": "active", "text": body,
             "pattern": None, "pattern2": None, "owner_said": None,
             "proposed_at": None, "target": None, "first": i, "last": i}
        if section == WAITING:
            if not when:
                raise RulesError(f"{DOCS[doc][0]}, line {i + 1}: a waiting "
                                 "entry needs its proposal date and target")
            e.update(status="proposed", target=target.strip(),
                     proposed_at=dt.datetime.strptime(when, "%Y-%m-%d %H:%M"))
        if (e["target"] or section) in JUNK_SECTIONS:
            j = JUNK_BODY.match(body)
            if not j:
                raise RulesError(f"{DOCS[doc][0]}, line {i + 1}: a junk entry "
                                 "reads from `sender`: label")
            e["pattern"], e["pattern2"], e["text"] = j.groups()
        out.append(e)
    return out


def everything():
    """All entries in all documents; a number used twice is an error."""
    out, seen = [], {}
    for doc in DOCS:
        for e in parse(doc):
            if e["id"] in seen:
                raise RulesError(f"rule {e['id']} is in both {seen[e['id']]} "
                                 f"and {e['title']}")
            seen[e["id"]] = e["title"]
            out.append(e)
    return out


def load(docs):
    """Active rules from the named documents, or from a reader's set."""
    if isinstance(docs, str):
        docs = READERS[docs]
    return [e for d in docs for e in parse(d) if e["status"] == "active"]


def junk(sections=JUNK_SECTIONS):
    return [e for e in parse("senders") if e["section"] in sections]


def pending(include_age=False):
    """Proposals waiting on the owner: (id, doc title, text, their words, when)."""
    rows = [(e["id"], e["title"], e["text"], e["owner_said"], e["proposed_at"])
            for e in everything() if e["status"] == "proposed"]
    rows.sort(key=lambda r: r[4], reverse=True)
    if not include_age:
        return rows
    now = dt.datetime.now()
    return [(*r, PROPOSAL_TTL_DAYS - (now - r[4]).days) for r in rows]


# --- writing: in place, only the lines that change -----------------------
def _write_lines(doc, lines):
    os.makedirs(os.path.dirname(path_of(doc)), exist_ok=True)
    with open(path_of(doc), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def _readme():
    return os.path.join(RULES_DIR, "README.md")


def _next_id():
    text = ""
    if os.path.exists(_readme()):
        with open(_readme(), encoding="utf-8") as f:
            text = f.read()
    m = NEXT.search(text)
    n = max(int(m.group(1)) if m else 1,
            max((e["id"] for e in everything()), default=0) + 1)
    os.makedirs(RULES_DIR, exist_ok=True)
    with open(_readme(), "w", encoding="utf-8", newline="\n") as f:
        f.write(NEXT.sub(f"Next rule number: {n + 1}", text) if m
                else text + f"\nNext rule number: {n + 1}\n")
    return n


def _entry_line(rid, text, pattern=None, pattern2=None, when=None, target=None):
    body = _one_line(text)
    if pattern is not None:
        body = (f"from `{pattern}`"
                + (f" with subject `{pattern2}`" if pattern2 else "")
                + f": {body}")
    head = f"- [{rid}] "
    if when:
        head += f"(proposed {when:%Y-%m-%d %H:%M}, for {target}) "
    return head + body


def _insert(doc, section, new_lines):
    """Append lines at the end of a section, creating it in its place."""
    lines = _read_lines(doc) or [f"# {DOCS[doc][0]}", ""]
    heads = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    names = [h for _i, h in heads]
    if section not in names:
        order = SECTION_ORDER.get(doc, [RULES]) + [WAITING]
        rank = order.index(section) if section in order else len(order) - 1
        after = [i for i, h in heads if h in order and order.index(h) > rank]
        at = after[0] if after else len(lines)
        while at > 0 and lines[at - 1] == "":
            at -= 1
        block = ["", f"## {section}", ""]
        if doc == "senders" and section in JUNK_INTRO:
            block += [JUNK_INTRO[section], ""]
        lines[at:at] = block
        heads = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
    start = [i for i, h in heads if h == section][0]
    nxt = [i for i, _h in heads if i > start]
    end = nxt[0] if nxt else len(lines)
    at = end
    while at > start + 1 and lines[at - 1] == "":
        at -= 1
    lines[at:at] = new_lines
    _write_lines(doc, lines)


def _remove(rid):
    """Take an entry of the home's own out of its document. A core rule is the
    program's and is never removed: None, nothing changed."""
    for e in everything():
        if e["id"] == rid and not e["core"]:
            lines = _read_lines(e["doc"])
            del lines[e["first"]:e["last"] + 1]
            _write_lines(e["doc"], lines)
            return e
    return None


def add(doc, text, section=None, pattern=None, pattern2=None):
    """A rule the owner approved whole, in session: active at once."""
    doc = _sender_doc(resolve(doc), pattern)
    rid = _next_id()
    _insert(doc, section or RULES, [_entry_line(rid, text, pattern, pattern2)])
    return rid


def propose(doc, text, owner_said, section=None, pattern=None, pattern2=None):
    doc = _sender_doc(resolve(doc), pattern)
    rid = _next_id()
    new = [_entry_line(rid, text, pattern, pattern2, dt.datetime.now(),
                       section or RULES)]
    if owner_said:
        new.append(SAID + _one_line(owner_said))
    _insert(doc, WAITING, new)
    return rid


def confirm(rid, text=None):
    e = next((x for x in everything() if x["id"] == rid
              and x["status"] == "proposed"), None)
    if not e:
        return False
    _remove(rid)
    _insert(e["doc"], e["target"], [_entry_line(
        rid, text if text is not None else e["text"], e["pattern"], e["pattern2"])])
    return True


def reject(rid):
    e = next((x for x in everything() if x["id"] == rid
              and x["status"] == "proposed"), None)
    return bool(e and _remove(rid))


def never(rid):
    """A junk proposal the owner answered "never junk": its sender goes on the
    Never junk list instead of the one it was proposed for."""
    e = next((x for x in everything() if x["id"] == rid
              and x["status"] == "proposed" and x["pattern"]), None)
    if not e:
        return False
    _remove(rid)
    _insert(e["doc"], NEVER, [_entry_line(rid, e["text"], e["pattern"],
                                          e["pattern2"])])
    return True


def matches(value, pattern):
    """A junk pattern against a sender, as SQL ILIKE reads it: % any run,
    _ one character, backslash escapes."""
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            out += re.escape(pattern[i + 1])
            i += 2
            continue
        out += ".*" if c == "%" else "." if c == "_" else re.escape(c)
        i += 1
    return re.fullmatch(out, value or "", re.I | re.S) is not None


def delete(rid):
    """The owner said to delete it: the line goes, its number is never reused."""
    return bool(_remove(rid))


def expire(ttl_days=PROPOSAL_TTL_DAYS):
    cutoff = dt.datetime.now() - dt.timedelta(days=ttl_days)
    dropped = [e for e in everything()
               if e["status"] == "proposed" and e["proposed_at"] < cutoff]
    for e in dropped:
        _remove(e["id"])
    return [(e["id"], e["title"], e["text"]) for e in dropped]


# --- the names the rest of the system already calls ---------------------
def propose_rule(text, owner_said, domain="judgment", rtype="judgment",
                 source="", item_key=None, pattern=None, match_field=None,
                 area=None, action=None, pattern2=None):
    doc = _sender_doc(resolve(domain), pattern)
    section = None
    if doc == "senders":
        section = (NEVER if rtype == "noise_exception"
                   else ALWAYS if action == "auto" else PROBABLY)
    return propose(doc, text, owner_said, section, pattern, pattern2)


# --- the size cap ---------------------------------------------------------
def _norm(text):
    """Rule text compared without its goal tag, case or punctuation."""
    t = re.sub(r"^\(G\d+\)\s*", "", text or "")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def over_cap(cap=SIZE_CAP):
    """(doc, title, characters) for each rules document over the cap."""
    out = []
    for d in DOCS:
        if d in DATA_DOCS or not os.path.exists(path_of(d)):
            continue
        n = len("\n".join(_read_lines(d)))
        if n > cap:
            out.append((d, DOCS[d][0], n))
    return out


def consolidate_draft(doc, cap=SIZE_CAP):
    """Write Draft\\<title>.md for a document over the cap: entries whose text
    is the same merged into the lower number. The live document is never
    touched; an existing draft newer than the live document is kept for
    the owner's approval, and one older than it is retired and rebuilt.
    Returns (path, characters after, still over cap, written)."""
    doc = resolve(doc)
    out_path = os.path.join(DRAFT_DIR, DOCS[doc][0] + ".md")
    if os.path.exists(out_path):
        if os.path.getmtime(out_path) >= os.path.getmtime(path_of(doc)):
            with open(out_path, encoding="utf-8") as f:
                n = len(f.read())
            return out_path, n, n > cap, False
        _retire(out_path)
    lines = _read_lines(doc)
    keep, drop = {}, set()
    for e in sorted(parse(doc, home_only=True), key=lambda x: x["id"]):
        if e["status"] != "active":
            continue
        key = (e["section"], e["pattern"], e["pattern2"], _norm(e["text"]))
        if key in keep:
            drop.update(range(e["first"], e["last"] + 1))
        else:
            keep[key] = e["id"]
    text = "\n".join(l for i, l in enumerate(lines) if i not in drop)
    os.makedirs(DRAFT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return out_path, len(text), len(text) > cap, True


def _retire(path):
    """Delete a retired draft outright, unless other files still name it."""
    import inuse
    inuse.refuse_if_used(path)
    os.remove(path)
    return path


def retire_drafts(over_titles):
    """Retire every consolidated draft whose document is no longer over the cap."""
    if not os.path.isdir(DRAFT_DIR):
        return []
    gone = []
    for d in DOCS:
        title = DOCS[d][0]
        p = os.path.join(DRAFT_DIR, title + ".md")
        if title not in over_titles and os.path.isfile(p):
            _retire(p)
            gone.append(title)
    return gone


expire_proposals = expire
confirm_rule = confirm
reject_rule = reject


def main(argv):
    if not argv or argv[0] not in ("list", "pending", "add", "propose",
                                   "confirm", "reject", "never", "delete"):
        print(__doc__)
        return 2
    cmd, a = argv[0], argv[1:]
    if cmd == "list":
        for doc in ([resolve(a[0])] if a else DOCS):
            rs = parse(doc)
            print(f"{DOCS[doc][0]}: {len(rs)} entries, read by {DOCS[doc][1]}")
    elif cmd == "pending":
        for rid, title, text, said, when in pending():
            print(f"[{rid}] {title}, proposed {when:%m/%d %I:%M %p}: {text}")
    elif cmd == "add":
        print(f"added rule {add(a[0], a[1])} to {DOCS[resolve(a[0])][0]}")
    elif cmd == "propose":
        print(f"proposed rule {propose(a[0], a[1], a[2] if len(a) > 2 else '')}")
    elif cmd == "confirm":
        print("confirmed" if confirm(int(a[0]), a[1] if len(a) > 1 else None)
              else f"no proposal {a[0]}")
    elif cmd == "reject":
        print("rejected" if reject(int(a[0])) else f"no proposal {a[0]}")
    elif cmd == "never":
        print("moved to Never junk" if never(int(a[0])) else f"no proposal {a[0]}")
    elif cmd == "delete":
        print("deleted" if delete(int(a[0])) else f"rule {a[0]} is a core rule, part of the program; it is not changed here"
              if int(a[0]) in core_ids() else f"no rule {a[0]}")
    if cmd in ("confirm", "reject", "never", "delete"):
        close_junk_ask()
    return 0


def close_junk_ask():
    """A junk question whose sender no longer waits closes in the same
    session instead of at the next pass (one card per sender, and the older
    one card that asked about them all once none waits)."""
    keep = {f"system::noise rule proposals::{e['id']}" for e in parse("senders")
            if e["status"] == "proposed" and e["pattern"]}
    import db
    con = db.connect()
    try:
        for (key,) in con.execute(
                "SELECT item_key FROM tasks WHERE status='needs_me' AND"
                " (item_key=? OR item_key LIKE ?)",
                ["system::noise rule proposals",
                 "system::noise rule proposals::%"]).fetchall():
            if key not in keep and (key.count("::") > 1 or not keep):
                con.execute(
                    "UPDATE tasks SET status='done', resolved_reason=?,"
                    " updated_at=now() WHERE item_key=? AND status='needs_me'",
                    ["every sender it asked about was answered", key])
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
