r"""The guardrails' checks: one plain function per guard, read by the program and by the hooks alike.

Contract: Plugin build\RULEBOOK.md. Standard library only: no engine import, no database, no Claude, so a hook runs it in a
moment. Nothing here writes anything.

    check_card(card, context)              (a) cards follow the page's rules or never reach the page
    check_send(message, authority)         (b) nothing is sent except on the owner's press or a standing approval
    check_program_edit(path, change)       (c) program edits only on an agreed change with a clear go, undo copy first
    check_general_text(path, text, home)   (d) nothing personal in the general part
    check_part(path, writer, home)         (e) the three parts stay apart

Each returns {"ok": bool, "guard": "a".."e", "broken": [{"rule", "says", "field", "fixable"}]}.

Command line, for hooks:  python rulebook.py route <file.json | ->   (one tool call, as rulebook_guard.py sends it)
                          python rulebook.py <a|b|c|d|e> <file.json | ->
    a: {"card": {...}, "context": {...}}            b: {"message": {...}, "authority": {...}}
    c: {"path": "...", "change": {...} | null}      d: {"path": "...", "text": "...", "home": "...", "extra_terms": {...}}
    e: {"path": "...", "writer": "...", "home": "..."}
prints the verdict as JSON; exit 0 when ok, 2 when refused, 1 when the check itself failed (a hook refuses on 1 too).
"""
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERAL = os.path.dirname(os.path.dirname(HERE))           # System
BOOK = os.path.join(HERE, "rulebook.json")
TAUGHT_KINDS = ("a", "b")                                  # a taught rule may add or tighten only these guards
_cache = {}


def home_dir():
    return os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(GENERAL), "Live")


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def book(home=None):
    """The general guardrails with the owner's taught rules layered on top. Returns (rules by id, words, skipped lines)."""
    home = home or home_dir()
    mod_files = sorted(glob.glob(os.path.join(home, "mods", "*", "mod.json")) + glob.glob(os.path.join(home, "mods", "*", "rules.json")))
    marks = [os.path.getmtime(BOOK)] + [os.path.getmtime(p) for p in glob.glob(os.path.join(home, "taught", "rules", "*.json"))] + \
        [os.path.getmtime(p) for p in mod_files]
    key = (home, tuple(marks))
    if _cache.get("key") == key:
        return _cache["rules"], _cache["words"], _cache["skipped"]
    g = _read(BOOK, {}) or {}
    rules = {r["id"]: dict(r, source="general") for r in g.get("rules") or []}
    words = dict(g.get("words") or {})
    skipped = []
    for p in sorted(glob.glob(os.path.join(home, "taught", "rules", "*.json"))):
        t = _read(p, {}) or {}
        for r in t.get("rules") or []:
            rid, name = str(r.get("id") or ""), os.path.basename(p)
            if r.get("guard") not in TAUGHT_KINDS:
                skipped.append(f"taught rule {name}:{rid} skipped: only guards a and b take taught rules")
            elif rid in rules:
                skipped.append(f"taught rule {name}:{rid} skipped: it would replace general rule {rid}")
            else:
                rules[rid] = dict(r, source=f"taught:{name}")
    # the owner's mods (mods.py): each may add rules of its own (guards a and b, named <mod>.<id>), and may loosen a
    # general rule only where its mod.json records the owner's yes for that rule
    for mj in sorted(glob.glob(os.path.join(home, "mods", "*", "mod.json"))):
        m = _read(mj, {}) or {}
        name = os.path.basename(os.path.dirname(mj))
        if not isinstance(m, dict) or m.get("name") != name or not m.get("on", True):
            continue
        t = _read(os.path.join(os.path.dirname(mj), "rules.json"), {}) or {}
        for r in t.get("rules") or []:
            rid = str(r.get("id") or "")
            rid = rid if rid.startswith(name + ".") else f"{name}.{rid}"
            if r.get("guard") not in TAUGHT_KINDS:
                skipped.append(f"mod {name} rule {rid} skipped: a mod adds rules to guards a and b only")
            elif rid in rules:
                skipped.append(f"mod {name} rule {rid} skipped: it would replace rule {rid}")
            else:
                rules[rid] = dict(r, id=rid, source=f"mod:{name}")
        yes = {str(x.get("rule")): str(x.get("yes") or "").strip() for x in m.get("loosens") or [] if isinstance(x, dict)}
        for rid, says in (t.get("loosens") or {}).items():
            if rid not in rules or rules[rid].get("source") != "general":
                skipped.append(f"mod {name} loosens {rid}: there is no such general rule")
            elif not yes.get(rid):
                skipped.append(f"mod {name} loosens {rid}: not without the owner's yes, recorded in its mod.json")
            else:
                rules[rid] = dict(rules[rid], says=str(says), source=f"mod:{name}", loosened_with=yes[rid])
    _cache.update(key=key, rules=rules, words=words, skipped=skipped)
    return rules, words, skipped


def _verdict(guard, broken):
    return {"ok": not broken, "guard": guard, "broken": broken}


def _broke(rules, rid, field=None, fixable=False, more=""):
    r = rules.get(rid) or {"says": rid}
    return {"rule": rid, "says": r["says"] + (f" ({more})" if more else ""), "field": field, "fixable": fixable}


def said(verdict):
    """One plain line for a refusal: 'rule A3: ...; rule A5: ...'."""
    return "; ".join(f"rule {b['rule']}: {b['says']}" for b in verdict.get("broken") or [])


def as_text(home=None):
    """The whole set of guardrails in plain lines, for a Claude run to carry: each rule's id and sentence, by guard."""
    rules, _w, _s = book(home)
    names = {"a": "Cards on the page", "b": "Sending", "c": "Changing the program", "d": "Nothing personal in the general part",
             "e": "The parts kept apart"}
    out = []
    for g in "abcde":
        out.append(names[g] + ":")
        out += [f"- {r['id']}: {r['says']}" + (" (taught by the owner)" if str(r.get("source", "")).startswith("taught") else
                                                 f" (from the owner's mod {r['source'][4:]}" + (", loosened with the owner's yes)" if r.get("loosened_with") else ")")
                                                 if str(r.get("source", "")).startswith("mod:") else "")
                for r in rules.values() if r.get("guard") == g]
    return "\n".join(out)


# --- (a) cards ---------------------------------------------------------------------------------------------------------
def check_card(card, context=None):
    """card: one card as the engine stores it. context: {"message_ids": [...], "new": bool, "areas": [...], "loose_ids": [...]}.
    Only the rules the program refuses today are tested here; the rest are said (rulebook.json, check "said")."""
    rules, _w, _s = book((context or {}).get("home"))
    c, ctx = card or {}, context or {}
    out = []
    lim = rules["A1"].get("limits") or {}
    if not str(c.get("title") or "").strip():
        out.append(_broke(rules, "A3", "title", more="it has no title"))
    if c.get("state") not in (lim.get("written_states") or []):
        out.append(_broke(rules, "A1", "state", more=f"state {c.get('state')!r} is not allowed"))
    if ctx.get("new"):
        if c.get("kind") not in (lim.get("new_kinds") or []):
            out.append(_broke(rules, "A1", "kind", more=f"kind {c.get('kind')!r} is not allowed"))
        if not str(c.get("area") or "").strip():
            out.append(_broke(rules, "A7", "area", more="it has no area"))
        loose = {int(i) for i in ctx.get("loose_ids") or [] if str(i).isdigit()}
        ids = {int(i) for i in c.get("messages") or [] if str(i).isdigit()}
        if "loose_ids" in ctx and (not ids or not ids <= loose):
            out.append(_broke(rules, "A7", "messages", more="its messages must be ids from the loose messages given"))
    if not isinstance(c.get("asks", []), list):
        out.append(_broke(rules, "A18", "asks"))
    if "message_ids" in ctx:
        lo, hi = (rules["A5"].get("limits") or {}).get("id_digits") or [4, 6]
        cited = set(re.findall(r"\b\d{%d,%d}\b" % (lo, hi), str(c.get("evidence") or "")))
        if not cited & {str(i) for i in ctx["message_ids"]}:
            out.append(_broke(rules, "A5", "evidence", more="the evidence must cite at least one message id it was given"))
    if c.get("important") and not str(c.get("important_reason") or "").strip():
        out.append(_broke(rules, "A6", "important_reason", more="important without a reason"))
    for r in rules.values():                       # the owner's taught card rules: words a card must not carry
        if r.get("source", "").startswith("taught") and r.get("guard") == "a" and r.get("check") == "words_not":
            text = " ".join(str(c.get(k) or "") for k in ("title", "short_header", "detail")).lower()
            hit = [w for w in (r.get("limits") or {}).get("words") or [] if str(w).lower() in text]
            if hit:
                out.append(_broke(rules, r["id"], "title"))
    return _verdict("a", out)


# --- (b) sending -------------------------------------------------------------------------------------------------------
def said_refusal(said, at=None, now=None, rules=None, want=None, not_words=None):
    """Why the owner's own words do not ask for this send or change (B11), or '' when they do. want and not_words: the regexes
    his words must and must not match (B11's send words when None). Words that put it off or negate it are not a go."""
    rules = rules or book()[0]
    lim = (rules.get("B11") or {}).get("limits") or {}
    text = " ".join(str(said or "").split())
    if not text:
        return "nothing in the owner's own words asks for it"
    if not re.search(want or lim.get("send_words") or r"\bsend\b", text, re.I):
        return "the owner's words in this message do not ask for it"
    nots = not_words if not_words is not None else lim.get("not_words")
    if nots and re.search(nots, text, re.I):
        return "the owner's words put it off or only ask about it"
    if at:
        try:
            n = dt.datetime.fromisoformat(str(now)) if now else dt.datetime.now()
            if abs((n - dt.datetime.fromisoformat(str(at))).total_seconds()) > lim.get("fresh_seconds", 600):
                return "the owner's words are too old"
        except ValueError:
            return "the owner's words carry no readable time"
    return ""


def check_send(message, authority):
    """message: {"account", "to", "cc", "bcc", "subject", "body", "attach"}.
    authority: {"kind": "press", "switched_on", "accounts", "press": {"action", "origin", "device", "at", "shown"}, "now"}
            or {"kind": "standing", "switched_on", "accounts", "entry": {...}, "card": {"state", "shelf", "reply"}, "left": n}
            or {"kind": "said", "switched_on", "accounts", "said": {"words", "at"}, "now"} (the owner's own words in Talk to
               your assistant, or typed on a card, telling it to send this one email it wrote)
            or {"kind": "level", "switched_on", "accounts", "level", "section", "card": {"state", "shelf", "reply"}, "left": n}
               (a reply drafted for him in a kind of work he raised to learning level 2 or 3: his standing approval, B12)
            or {"kind": "none"} (a hook: Claude itself trying to send)."""
    rules, words, _s = book(authority.get("home") if isinstance(authority, dict) else None)
    m, a = message or {}, authority or {}
    out = []
    kind = a.get("kind")
    if kind not in ("press", "standing", "said", "level"):
        return _verdict("b", [_broke(rules, "B1", more="only the program sends, on the owner's press, his own words telling it to, or his standing approval")])
    if kind == "said":
        s = a.get("said") or {}
        why = said_refusal(s.get("words"), s.get("at"), a.get("now"), rules)
        if why:
            out.append(_broke(rules, "B11", "said", more=why))
    addr = re.compile(words["address"])
    clean = lambda xs: [str(x).strip() for x in (xs or []) if str(x).strip()]      # noqa: E731
    to, cc, bcc = clean(m.get("to")), clean(m.get("cc")), clean(m.get("bcc"))
    if not a.get("switched_on"):
        out.append(_broke(rules, "B2", "switched_on", more="sending is switched off"))
    account = str(m.get("account") or "").strip()
    if account.lower() not in {str(x).lower() for x in a.get("accounts") or []}:
        out.append(_broke(rules, "B2", "account", more="not one of the owner's sending accounts"))
    lim = rules["B4"].get("limits") or {}
    if not to:
        out.append(_broke(rules, "B4", "to", more="nobody in To"))
    if len(to) + len(cc) + len(bcc) > lim.get("most_recipients", 20):
        out.append(_broke(rules, "B4", "to", more="too many recipients"))
    bad = [x for x in to + cc + bcc if not addr.match(x)]
    if bad:
        out.append(_broke(rules, "B4", "to", more="not an email address: " + ", ".join(bad[:3])))
    if not str(m.get("subject") or "").strip() or not str(m.get("body") or "").strip():
        out.append(_broke(rules, "B4", "body", more="the subject or the message is empty"))
    if kind == "said":
        pass            # his words were checked above (B11); what goes is the draft as the assistant wrote it, said back in full
    elif kind == "press":
        p = a.get("press") or {}
        if p.get("action") != "answer" or p.get("origin") or not p.get("device") or not p.get("at"):
            out.append(_broke(rules, "B3", "press", more="that did not come from a Send press on the page"))
        else:
            try:
                now = dt.datetime.fromisoformat(str(a.get("now"))) if a.get("now") else dt.datetime.now()
                age = abs((now - dt.datetime.fromisoformat(str(p["at"]))).total_seconds())
                if age > (rules["B3"].get("limits") or {}).get("fresh_seconds", 600):
                    out.append(_broke(rules, "B3", "at", more="the press is too old"))
            except ValueError:
                out.append(_broke(rules, "B3", "at", more="the press carries no readable time"))
        sh = p.get("shown") if isinstance(p.get("shown"), dict) else None
        if sh is None or str(sh.get("account") or "").strip() != account or clean(sh.get("to")) != to or clean(sh.get("cc")) != cc \
                or clean(sh.get("bcc")) != bcc or str(sh.get("type") or "new") != str(m.get("type") or "new") \
                or [str(n) for n in (sh.get("attach") or [])] != [str(n) for n in (m.get("attach") or [])]:
            out.append(_broke(rules, "B3", "shown", more="what was on the screen is not what would be sent"))
    elif kind == "level":
        card = a.get("card") or {}
        lim12 = (rules.get("B12") or {}).get("limits") or {}
        if a.get("level") not in (2, 3):
            out.append(_broke(rules, "B12", "level", more="that kind of work is not at learning level 2 or 3"))
        if a.get("section") not in (lim12.get("sections") or ["replies"]):
            out.append(_broke(rules, "B12", "section", more="only reply drafts are sent at a learning level"))
        if int(a.get("left") or 0) <= 0:
            out.append(_broke(rules, "B12", "left", more="the daily limit is used up"))
        reply = card.get("reply") if isinstance(card.get("reply"), dict) else None
        wrote = [str(x).lower() for x in (reply or {}).get("to") or []]
        if not reply or reply.get("via", "email") != "email" or len(wrote) != 1 or [x.lower() for x in to] != wrote:
            out.append(_broke(rules, "B12", "to", more="it is not a reply to the one person who wrote the card's own email"))
        if cc or bcc or m.get("attach"):
            out.append(_broke(rules, "B12", "cc", more="it has a copy or an attachment"))
        if reply and account.lower() != str(reply.get("account") or "").lower():
            out.append(_broke(rules, "B12", "account", more="it is not from the account that email came to"))
        body = str(m.get("body") or "")
        if len(body) > lim12.get("most_body", 800) or re.search(words["no_link"], body + " " + str(m.get("subject") or ""), re.I):
            out.append(_broke(rules, "B12", "body", more="it is long or holds a link"))
        if str(card.get("state")) not in ("question", "yours") or card.get("shelf"):
            out.append(_broke(rules, "B12", "card", more="the card is not waiting on the owner"))
    else:
        e, card = a.get("entry") or {}, a.get("card") or {}
        scope = str(e.get("scope") or "").lower()
        if e.get("kind") != "send_reply" or not e.get("on", True) or e.get("level") not in ("tell", "quiet"):
            out.append(_broke(rules, "B5", "entry", more="that standing approval is not on"))
        if int(a.get("left") or 0) <= 0:
            out.append(_broke(rules, "B5", "left", more="the daily limit is used up"))
        if not scope or [x.lower() for x in to] != [scope]:
            out.append(_broke(rules, "B5", "to", more="it goes to someone the approval does not name"))
        reply = card.get("reply") if isinstance(card.get("reply"), dict) else None
        if not reply or reply.get("via", "email") != "email" or [str(x).lower() for x in reply.get("to") or []] != [scope]:
            out.append(_broke(rules, "B5", "reply", more="it is not a reply to that person's own message"))
        if cc or bcc or m.get("attach"):
            out.append(_broke(rules, "B5", "cc", more="it has a copy or an attachment"))
        if account.lower() != str(e.get("account") or "").lower():
            out.append(_broke(rules, "B5", "account", more="it is not from the account the approval names"))
        body = str(m.get("body") or "")
        if len(body) > (rules["B5"].get("limits") or {}).get("most_body", 800) or re.search(words["no_link"], body + " " + str(m.get("subject") or ""), re.I):
            out.append(_broke(rules, "B5", "body", more="it is long or holds a link"))
        if str(card.get("state")) not in ("question", "yours") or card.get("shelf"):
            out.append(_broke(rules, "B5", "card", more="the card is not waiting on the owner"))
    return _verdict("b", out)


def check_draft(draft, known, started=False):
    """An email the assistant wrote, before it goes on the page: every recipient is a plain address among `known` (the owner's
    known contacts and the people on the email it answers or forwards), and it has a subject and a message.
    started: a draft the owner started from his mail with one press (a forward with nobody in To yet, no words yet); only
    its recipients so far are checked, and he fills in the rest before Send."""
    rules, words, _s = book()
    addr = re.compile(words["address"])
    known = {str(k).strip().lower() for k in known or []}
    out = []
    every = [str(x).strip() for x in (draft.get("to") or []) + (draft.get("cc") or []) + (draft.get("bcc") or []) if str(x).strip()]
    if started:
        bad = [x for x in every if not addr.match(x) or x.lower() not in known]
        return _verdict("b", [_broke(rules, "B10", "to", more="not one of your contacts: " + ", ".join(bad[:3]))] if bad else [])
    if not draft.get("to"):
        out.append(_broke(rules, "B10", "to", more="it names nobody to send to"))
    bad = [x for x in every if not addr.match(x)]
    unknown = [x for x in every if addr.match(x) and x.lower() not in known]
    if bad:
        out.append(_broke(rules, "B10", "to", more="not an email address: " + ", ".join(bad[:3])))
    if unknown:
        out.append(_broke(rules, "B10", "to", more="not one of your contacts: " + ", ".join(unknown[:3])))
    if not str(draft.get("subject") or "").strip() or not str(draft.get("body") or "").strip():
        out.append(_broke(rules, "B10", "body", more="the subject or the message is empty"))
    return _verdict("b", out)


# --- (c) program edits -------------------------------------------------------------------------------------------------
YES = re.compile(r"^\s*(yes|yes,? (do it|go|go ahead|make it|make the change|change it)|go ahead|do it|make it so)\b", re.I)


def check_program_edit(path, change):
    """path: a file about to be written or removed in the owner's own part: a mod or a taught add-on.
    change: the change record (<home>\\changes\\<id>.json) or None."""
    rules, _w, _s = book()
    c = change if isinstance(change, dict) else None
    out = []
    if not c:
        return _verdict("c", [_broke(rules, "C1", "change", more="there is no agreed change with a go")])
    if c.get("state") not in ("go", "doing"):
        out.append(_broke(rules, "C1", "state", more=f"the change is {c.get('state') or 'not agreed'}, not under a go"))
    go = c.get("go") if isinstance(c.get("go"), dict) else {}
    if not str(c.get("agreed") or "").strip() or not YES.match(str(go.get("words") or "")) or not go.get("at"):
        out.append(_broke(rules, "C1", "go", more="no clear yes was given to the change as said back"))
    elif c.get("agreed_at") and str(go.get("at")) < str(c.get("agreed_at")):
        out.append(_broke(rules, "C1", "go", more="the yes came before the change was said back"))
    norm = lambda p: os.path.normcase(os.path.abspath(str(p)))      # noqa: E731
    files = {norm(f) for f in c.get("files") or []}
    if norm(path) not in files:
        out.append(_broke(rules, "C1", "files", more="this file is not one the change names"))
    undo = str(c.get("undo") or "")
    if undo:
        rel = os.path.splitdrive(norm(path))[1].lstrip("\\/")
        kept = os.path.join(undo, rel)
        if not (os.path.exists(kept) or os.path.exists(kept + ".new")):
            out.append(_broke(rules, "C1", "undo", more="the undo copy of this file is not saved yet"))
    else:
        out.append(_broke(rules, "C1", "undo", more="the change has no undo copy"))
    part = part_of(path)
    if c.get("part") and part != c.get("part"):
        out.append(_broke(rules, "C1", "part", more=f"the change is for the {c.get('part')} part, this file is in the {part} part"))
    return _verdict("c", out)


# --- (d) nothing personal in the general part ----------------------------------------------------------------------------
def owner_terms(home=None):
    """The owner's own words, read from the home now and never written anywhere: {group: [terms]}."""
    home = home or home_dir()
    _r = lambda rel: _read(os.path.join(home, rel), {}) or {}      # noqa: E731
    me, conns, people, items, page = (_r("personal/personal.json"), _r("personal/connections.json"), _r("known_people.json"),
                                      _r("items.json"), _r("personal/local_settings.json"))
    _rules, words, _s = book(home)
    public, generic = set(words.get("public_mail") or []), set(words.get("generic_areas") or [])
    g = {}
    g["owner's private words and names"] = [str(w) for w in me.get("private_words") or []] + [str(me.get("owner") or ""), str(me.get("full_name") or "")]
    addresses = [str(c.get("address") or "") for c in conns.get("connections") or []] + [str(a) for a in me.get("send_accounts") or []]
    g["owner's own addresses and their domains"] = addresses + [a.split("@")[-1] for a in addresses if "@" in a and a.split("@")[-1] not in public]
    ids = [str(v) for app in (conns.get("apps") or {}).values() if isinstance(app, dict) for v in app.values()]
    ids += [str((me.get("chat_session") or {}).get("id") or ""), str(page.get("site") or "").replace("https://", ""), str(page.get("feed_key") or "")]
    g["owner's ids"] = ids
    g["owner's calendar and area names"] = [str(x) for x in me.get("today_calendars") or []] + [str(a) for a in me.get("areas") or [] if a not in generic]
    ppl = people.get("people") or []
    g["people on file"] = [str(p.get("name") or "") for p in ppl if len(str(p.get("name") or "").split()) >= 2] + \
        [str(e) for p in ppl for e in (p.get("email") if isinstance(p.get("email"), list) else [p.get("email") or ""])] + \
        [str(p.get("company") or "") for p in ppl if len(str(p.get("company") or "")) >= 6]
    its = items.get("items") or []
    g["people and senders named on the owner's cards"] = [str(i.get("source_who") or "") for i in its if len(str(i.get("source_who") or "")) >= 6
                                                           and "assistant" not in str(i.get("source_who")).lower()]
    skip = {str(x).strip().lower() for x in words.get("placeholder_names") or []}      # the starter's stand-in name is nobody's
    return {k: sorted({t.strip().lower() for t in v if len(t.strip()) >= 4 and t.strip().lower() not in skip}) for k, v in g.items()}


def find_terms(text, terms):
    """How many times the terms occur: short plain words as whole words, longer ones anywhere."""
    low, n = text.lower(), 0
    for t in terms:
        n += len(re.findall(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", low)) if t.isalnum() and len(t) < 6 else low.count(t)
    return n


def check_general_text(path, text, home=None, extra_terms=None, terms=None, checksum_file=False):
    """path: the file in the general part; text: what it would hold. extra_terms: more groups the caller adds (the owner's own
    fixed list, kept outside the general part). terms: owner_terms() already read (a caller checking many files reads once).
    The verdict names the kind of word found and how many, never the word."""
    rules, words, _s = book(home)
    out = []
    groups = dict(terms if terms is not None else owner_terms(home))
    groups.update(extra_terms or {})
    for group, ts in groups.items():
        n = find_terms(text, ts)
        if n:
            out.append(_broke(rules, "D1", "text", more=f"{n} of the {group}"))
    if not checksum_file:
        for label, pat in (words.get("secret_shapes") or {}).items():
            n = len(re.findall(pat, text))
            if n:
                out.append(_broke(rules, "D2", "text", more=f"{n} {label}"))
    name = os.path.basename(str(path)).lower()
    if any(name == h or name.endswith(h) or h in str(path).replace("\\", "/").lower().split("/") for h in words.get("home_files") or []):
        out.append(_broke(rules, "D3", "path", more=f"{name} is a file of the home"))
    return _verdict("d", out)


# --- (e) the parts ---------------------------------------------------------------------------------------------------------
def part_of(path, home=None):
    home = os.path.normcase(os.path.abspath(home or home_dir()))
    p = os.path.normcase(os.path.abspath(str(path)))
    gen = os.path.normcase(GENERAL)
    inside = lambda root: p == root or p.startswith(root + os.sep)      # noqa: E731
    if inside(gen):
        return "general"
    if inside(os.path.join(home, "personal")):
        return "personal"
    if inside(os.path.join(home, "taught")):
        return "taught"
    if inside(os.path.join(home, "mods")):
        return "mods"
    if inside(home):
        return "home"
    return "outside"


MAY = {"program": ("home", "personal"), "change": ("mods", "taught"), "run": ("home",), "chat": (), "setup": ("personal", "home", "general")}


def check_part(path, writer, home=None):
    """May this writer write this path? writer: program | change | run | chat | setup. A run may write only in the home's
    state folder; a change also needs check_program_edit."""
    rules, _w, _s = book(home)
    part = part_of(path, home)
    out = []
    if part not in MAY.get(writer, ()):
        out.append(_broke(rules, "E1", "path", more=f"a {writer} does not write in the {part} part"))
    elif writer == "run":
        state = os.path.normcase(os.path.join(os.path.abspath(home or home_dir()), "state"))
        if not os.path.normcase(os.path.abspath(str(path))).startswith(state + os.sep):
            out.append(_broke(rules, "E3", "path", more="a hidden run writes only in the home's state folder"))
    return _verdict("e", out)


# --- one tool call, as a hook sees it ----------------------------------------------------------------------------------
SEND_TOOL = re.compile(r"(^|__|_)(send|post|reply|forward|schedule)(_|$)|send_?mail|send_?message|draft_send", re.I)
APP_TOOL = re.compile(r"^mcp__ccd_session(_mgmt)?__", re.I)    # the Claude app's own session messaging: not mail, not chat
SEND_ENDPOINT = r"gmail\.googleapis\.com/.*/send|graph\.microsoft\.com/.*/sendMail|chat\.postMessage|ntfy\.sh"
SEND_URL = re.compile(SEND_ENDPOINT, re.I)
SEND_COMMAND = re.compile(r"send_owner_email|send_standing|connections\.send|\bsend\.py\b|smtplib|sendmail|"
                          r"send-mailmessage|smtpclient|" + SEND_ENDPOINT, re.I)
SEND_SCRIPTS = {"send.py"}                       # scripts that send when run
SEND_MODULES = {"send", "smtplib"}               # modules that send when imported and called
SEND_NAMES = {"send", "send_owner_email", "send_standing", "send_mime"}     # names that send, imported from a module
# a send in code is a call (Kevin 11/25/26: judge what code does): importing or naming the send module is not
SEND_CALL = re.compile(r"\b(?:send_owner_email|send_standing|send_mime|sendmail|send_message)\s*\(|\bsmtplib\.\w+\s*\(|"
                       r"\bconnections\.send\s*\(", re.I)
EXEC_WORDS = re.compile(r"\b(?:exec|eval|execfile|runpy|run_path|run_module|subprocess|system|popen|spawn\w*|startfile|"
                        r"__import__|importlib|import_module)\b", re.I)
PY_IMPORT = re.compile(r"\bimport\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)")
PY_FROM = re.compile(r"\bfrom\s+([\w.]+)\s+import\s+(\([^)]*\)|[\w \t,*]+)")     # one line, or a ( ... ) list
HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][\w-]*)\1")
PYTHONS = re.compile(r"^(?:python[\d.]*w?|py|pypy[\d.]*)$")
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
POWERSHELLS = {"powershell", "pwsh"}
HTTP_CLIENTS = {"curl", "wget", "iwr", "irm", "invoke-webrequest", "invoke-restmethod", "http", "https", "xh"}
TEXT_ONLY = {"cat", "type", "more", "less", "head", "tail", "sed", "grep", "egrep", "fgrep", "rg", "ag", "findstr", "get-content",
             "gc", "select-string", "sls", "ls", "dir", "get-childitem", "gci", "wc", "cmp", "fc", "diff", "comm", "sort", "uniq",
             "cut", "tr", "nl", "stat", "file", "sha256sum", "sha1sum", "md5sum", "certutil", "get-filehash", "echo", "printf",
             "write-output", "write-host", "pwd", "cd", "set-location", "pushd", "popd", "test", "jq", "find", "git",
             "join-path", "split-path", "resolve-path", "test-path"}
GIT_TEXT = {"status", "log", "diff", "show", "add", "commit", "blame", "grep", "rev-parse", "ls-files", "branch", "shortlog",
            "describe", "reflog", "cat-file", "merge-base", "rm", "mv", "restore", "stash"}
FILE_WRITERS = {"tee", "out-file", "set-content", "add-content", "sc", "ac", "cp", "copy", "copy-item", "cpi", "mv", "move",
                "move-item", "mi"}
PREFIXES = {"env", "sudo", "nohup", "time", "nice", "exec", "command", "builtin", "stdbuf", "timeout"}
RUNNERS = {"uv", "poetry", "pipenv", "pdm", "hatch", "rye", "conda"}
PS_EXPR = re.compile(r"^\$(?:_|psitem)$|^\$[A-Za-z_][\w:]*[.\[]", re.I)    # $_ or $x.Name: a PowerShell value, not a run
PS_LITERAL_SET = re.compile(r"""(^|[;\n{}()]|&&|\|\|)([ \t]*)\$[A-Za-z_][\w:]*[ \t]*=[ \t]*("[^"`$]*"|'[^']*')[ \t]*(?=[;\n{}()]|$)""")
SUBST = "\x01subst\x01"                          # stands where a $( ) or `...` was taken out
DYNAMIC_PROG = re.compile(r"\$\{?[A-Za-z_]\w*\}?|\$env:[A-Za-z_]\w*|" + re.escape(SUBST), re.I)   # a program that is only a value


def _prog(word):
    p = os.path.basename(word.replace("\\", "/")).lower()
    return p[:-4] if p.endswith(".exe") else p


def _heredocs(text):
    """Takes each heredoc body out of the command and leaves a here-string word (<<< key) in its place, so a body is
    judged only as what its command reads (a commit message is text; a body fed to python is code)."""
    bodies, pos = {}, 0
    while True:
        m = HEREDOC.search(text, pos)
        if not m:
            return text, bodies
        eol = text.find("\n", m.end())
        end = re.compile(r"^[ \t]*" + re.escape(m.group(2)) + r"[ \t]*$", re.M).search(text, eol + 1) if eol >= 0 else None
        if not end:
            pos = m.end()
            continue
        key = f"\x00{len(bodies)}\x00"
        bodies[key] = text[eol + 1:end.start()]
        text = text[:m.start()] + f" <<< {key} " + text[m.end():eol + 1] + text[end.end():]
        pos = m.start() + len(key) + 6


def _substitutions(text):
    """Takes out each $( ), <( ), >( ) and `...` (they run even inside double quotes) and returns the outer text with a
    plain word in each place, and the inner commands."""
    out, inner, i, n, q = [], [], 0, len(text), None
    while i < n:
        c = text[i]
        if q == "'":
            q = None if c == "'" else q
        elif c == "'" and q is None:
            q = "'"
        elif c == '"':
            q = None if q == '"' else '"'
        elif (text[i:i + 2] == "$(" or (q is None and text[i:i + 2] in ("<(", ">("))):
            depth, j, qq = 1, i + 2, None
            while j < n and depth:
                d = text[j]
                if qq:
                    qq = None if d == qq else qq
                elif d in "'\"":
                    qq = d
                elif d == "(":
                    depth += 1
                elif d == ")":
                    depth -= 1
                j += 1
            inner.append(text[i + 2:j - 1 if not depth else j])
            out.append(SUBST)
            i = j
            continue
        elif c == "`":
            j = text.find("`", i + 1)
            if j > 0:
                inner.append(text[i + 1:j])
                out.append(SUBST)
                i = j + 1
                continue
        out.append(c)
        i += 1
    return "".join(out), inner


def _segments(text):
    """The command's simple commands, each a list of words with quotes taken off, the way a shell (bash or PowerShell)
    splits them: on ; && || | & newline and parentheses; a backslash outside quotes is kept (Windows paths); a # at the
    start of a word begins a comment; < and > are words of their own."""
    segs, words, cur, quoted, i, n = [], [], "", False, 0, len(text)

    def end_word():
        nonlocal cur, quoted
        if cur or quoted:
            words.append(cur)
        cur, quoted = "", False

    def end_seg():
        end_word()
        if words:
            segs.append(list(words))
        words.clear()

    while i < n:
        c = text[i]
        if c in "'\"":
            i, quoted = i + 1, True
            while i < n and text[i] != c:
                if c == '"' and text[i] in "\\`" and i + 1 < n and text[i + 1] in '"\\`$':
                    i += 1
                cur += text[i]
                i += 1
            i += 1
        elif c == "#" and not cur and not quoted:
            while i < n and text[i] != "\n":
                i += 1
        elif c in " \t\r":
            end_word()
            i += 1
        elif (c == "{" and not cur and not quoted) or (c == "}" and "{" not in cur and not quoted):
            end_seg()                              # a PowerShell script block: what runs inside is a command of its own
            i += 1
        elif c in ";|&\n()":
            end_seg()
            i += 2 if text[i:i + 2] in ("&&", "||") else 1
        elif c in "<>":
            if cur.isdigit():
                cur = ""
            end_word()
            j = i
            while j < n and text[j] in "<>&":
                j += 1
            words.append(text[i:j])
            i = j
        else:
            cur += c
            i += 1
    end_seg()
    return segs


def _code_sends(code):
    """True when Python code would send: it imports or calls a sending module or function, runs a string that names
    one, or names a sending web address. Names inside strings and comments alone are text."""
    if SEND_URL.search(code):
        return True
    import io
    import tokenize
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, SyntaxError):
        return bool(SEND_COMMAND.search(code))
    text = {tokenize.STRING} | {getattr(tokenize, k) for k in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END") if hasattr(tokenize, k)}
    bare = re.sub(r"\s*\.\s*", ".", " ".join(t.string for t in toks if t.type not in text and t.type != tokenize.COMMENT))
    strings = [t.string for t in toks if t.type in text]
    if SEND_CALL.search(bare):
        return True
    # importing the send module, smtplib or connections is not a send; calling what sends through them is, under any
    # name it was given (import send as s; s.send_owner_email(...) / from connections import send as go; go(...))
    calls = set()
    for m in PY_IMPORT.finditer(bare):
        for x in m.group(1).split(","):
            parts = re.split(r"\s+as\s+", x.strip())
            mod = parts[0].rsplit(".", 1)[-1].lower()
            if mod in SEND_MODULES | {"connections"}:
                alias = re.escape(parts[-1].strip())
                calls.add(alias + r"\.(?:send|send_owner_email|send_standing|send_mime|sendmail|smtp\w*)\s*\(")
    for m in PY_FROM.finditer(bare):
        mod = m.group(1).rsplit(".", 1)[-1].lower()
        for x in re.sub(r"[()]", " ", m.group(2)).split(","):
            parts = re.split(r"\s+as\s+", x.strip())
            name = parts[0].strip()
            if name != "*" and (name.lower() in SEND_NAMES or mod == "smtplib"):
                calls.add(r"(?<![\w.])" + re.escape(parts[-1].strip()) + r"\s*\(")
            if name == "*" and mod in SEND_MODULES | {"connections"}:
                calls.add(r"(?<![\w.])(?:send|send_owner_email|send_standing|send_mime|smtp\w*)\s*\(")
    if any(re.search(c, bare, re.I) for c in calls):
        return True
    return bool(EXEC_WORDS.search(bare)) and any(SEND_COMMAND.search(s) or re.fullmatch(r"[rRbBuUfF]*(['\"]{1,3})send\1", s)
                                                 for s in strings)


def _python_sends(args, stdin, whole):
    i = 1
    while i < len(args):
        a = args[i]
        if a == "-":
            break
        if a.startswith("--") or not a.startswith("-") or len(a) < 2:
            if a.startswith("--"):
                i += 1
                continue
            return os.path.basename(a.replace("\\", "/")).lower() in SEND_SCRIPTS      # the script it runs
        flags = a[1:]
        for k, f in enumerate(flags):
            if f in "cm":
                val = flags[k + 1:] or (args[i + 1] if i + 1 < len(args) else "")
                if f == "c":
                    return _code_sends(val)
                return val.rsplit(".", 1)[-1].lower() in SEND_MODULES                   # python -m <module>
            if f in "WX":
                i += 0 if flags[k + 1:] else 1
                break
        i += 1
    if stdin and stdin[0] == "text":
        return _code_sends(stdin[1])
    return bool(SEND_COMMAND.search(whole))       # its program comes from a pipe or a file: judged on the whole command


def _name(word):
    """A file word as one name to compare a file written with a file run: its last part, lower case."""
    return os.path.basename(str(word or "").replace("\\", "/").rstrip("/")).lower()


def _ran_file(p, args):
    """The file a command runs, as a name (python x.py, bash x.sh, ./x, powershell -File x.ps1), or ''."""
    if re.search(r"\.(?:py|sh|ps1|bat|cmd)$", p) or args[0].startswith(("./", ".\\")):
        return _name(args[0])
    if p in POWERSHELLS:
        for j, a in enumerate(args[1:], 1):
            if re.fullmatch(r"-(?:f|fi|fil|file)", a.lower()) and j + 1 < len(args):
                return _name(args[j + 1])
        return ""
    if PYTHONS.match(p) or p in SHELLS | {"node", "ruby", "perl", "source", "."}:
        rest = args[1:]
        if PYTHONS.match(p) and any(re.fullmatch(r"-\w*[cm]\w*", a) for a in rest[:3]):
            return ""
        return next((_name(a) for a in rest if not a.startswith("-")), "")
    return ""


def _run_word(p, args):
    """The word for what a command runs, as written: the program itself, or the script an interpreter is handed
    (python x.py, bash x.sh, powershell -File x.ps1, node x.js); '' when it runs code given inline (-c, -m, -Command)."""
    if p in POWERSHELLS:
        for j, a in enumerate(args[1:], 1):
            if re.fullmatch(r"-(?:f|fi|fil|file)", a.lower()) and j + 1 < len(args):
                return args[j + 1]
        return ""
    if PYTHONS.match(p) or p in SHELLS | {"node", "ruby", "perl", "source", "."}:
        rest = args[1:]
        if PYTHONS.match(p) and any(re.fullmatch(r"-\w*[cm]\w*", a) for a in rest[:3]):
            return ""
        if p in SHELLS and any(re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a) for a in rest[:3]):
            return ""
        return next((a for a in rest if not a.startswith("-")), "")
    return args[0]


def _built(word):
    """True when a word is made while the command runs: a variable, a substitution or a process substitution."""
    return "$" in word or SUBST in word or word.startswith(("<(", ">("))


def _segment_sends(words, bodies, whole, depth):
    """(sends, the file it runs as a set of names, the files it writes as a set of names) for one simple command."""
    args, stdin, written, i = [], None, set(), 0
    while i < len(words):
        w = words[i]
        if w and set(w) <= set("<>&"):
            target = words[i + 1] if i + 1 < len(words) else ""
            if w == "<<<":
                stdin = ("text", bodies.get(target, target))
            elif w.startswith("<"):
                stdin = ("file", target)
            else:
                written.add(_name(target))
            i += 2
            continue
        args.append(w)
        i += 1
    sends, runs, writes = _segment_judge(args, stdin, written, bodies, whole, depth)
    return sends, runs, writes


def _segment_judge(args, stdin, written, bodies, whole, depth):
    """_segment_sends after the redirects are taken off: (sends, names run, names written)."""
    writes = written
    while args:                                  # what runs the command: VAR=x, env, sudo, uv run ... come off
        p = _prog(args[0])
        if re.match(r"^[A-Za-z_]\w*=", args[0]):
            args = args[1:]
        elif p in PREFIXES:
            args = args[1:]
            while args and (args[0].startswith("-") or (p == "timeout" and re.fullmatch(r"[\d.]+[smhd]?", args[0]))):
                args = args[1:]
        elif p in RUNNERS and len(args) > 1 and args[1] == "run":
            args = args[2:]
            while args and args[0].startswith("-"):
                args = args[1:]
        else:
            break
    if not args:
        return False, set(), writes
    p, text = _prog(args[0]), " ".join(args)
    if stdin and stdin[0] == "text":
        text += " " + stdin[1]
    ran = _ran_file(p, args)
    runs = {ran} if ran else set()
    if p in FILE_WRITERS:
        plain = [a for a in args[1:] if not a.startswith("-")]
        writes = writes | ({_name(a) for a in plain} if p in ("tee",) else {_name(plain[-1])} if plain else set())
    if p in TEXT_ONLY:
        if p == "git":
            rest = args[1:]
            while rest and rest[0] in ("-C", "--no-pager", "-P", "--git-dir", "--work-tree"):
                rest = rest[2:] if rest[0] in ("-C", "--git-dir", "--work-tree") else rest[1:]
            if not rest or rest[0] not in GIT_TEXT:
                return bool(SEND_COMMAND.search(text)), runs, writes
        if p == "find" and set(args) & {"-exec", "-execdir", "-ok", "-okdir"}:
            return bool(SEND_COMMAND.search(text)), runs, writes
        return False, runs, writes                # it only reads, searches, shows or records text
    if PS_EXPR.match(args[0]):
        return False, runs, writes                # a PowerShell value ($_.Name, $x[0]) is read, not run
    run = _run_word(p, args)
    if run and _built(run):
        # what runs (the program, or the script an interpreter is handed) is built while the command runs (Kevin
        # 11/25/26: judge what a command does, not the words around it). A path that names a send is a send; a word
        # that is only a variable or a substitution cannot be known, so it is judged on the words; a program made of
        # text and values ("$($_.Name): $x") is text being printed, not a run. A value in any other argument never
        # decides on its own.
        if SEND_COMMAND.search(run):
            return True, runs, writes
        if run is not args[0] and not _built(_name(run)):
            pass                                   # python $S/x.py: only the folder is a value; x.py is judged by its name below
        elif run is not args[0] or DYNAMIC_PROG.fullmatch(run):
            return bool(SEND_COMMAND.search(whole)), runs, writes
        else:
            return False, runs, writes
    if PYTHONS.match(p):
        return _python_sends(args, stdin, whole), runs, writes
    if p in HTTP_CLIENTS:
        return bool(SEND_URL.search(text)), runs, writes
    if p in SHELLS:
        for j, a in enumerate(args[1:], 1):
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a):
                return would_send(args[j + 1] if j + 1 < len(args) else "", depth + 1), runs, writes
            if not a.startswith("-"):
                return bool(SEND_COMMAND.search(text)), runs, writes       # a script file: judged on its words
        return (would_send(stdin[1], depth + 1) if stdin and stdin[0] == "text" else bool(SEND_COMMAND.search(whole))), runs, writes
    if p == "cmd":
        for j, a in enumerate(args[1:], 1):
            if a.lower() in ("/c", "/k"):
                return would_send(" ".join(args[j + 1:]), depth + 1), runs, writes
        return bool(SEND_COMMAND.search(whole)), runs, writes
    if p in POWERSHELLS:
        j = 1
        while j < len(args):
            a, low = args[j], args[j].lower()
            if re.fullmatch(r"-(?:e|ec|en|enc|enco|encod|encode|encoded|encodedc\w*)", low):
                try:
                    import base64
                    return would_send(base64.b64decode(args[j + 1]).decode("utf-16-le"), depth + 1), runs, writes
                except Exception:
                    return True, runs, writes      # a command that cannot be read is not let through
            if re.fullmatch(r"-(?:f|fi|fil|file)", low):
                return bool(SEND_COMMAND.search(text)), runs, writes
            if re.fullmatch(r"-c(?:o(?:m(?:m(?:a(?:n(?:d)?)?)?)?)?)?", low) or not a.startswith("-"):
                return would_send(" ".join(args[j + (1 if a.startswith("-") else 0):]), depth + 1), runs, writes
            j += 2 if low.lstrip("-") in ("executionpolicy", "ep", "windowstyle", "w", "workingdirectory", "wd",
                                            "outputformat", "of", "inputformat", "if", "version", "v") else 1
        return bool(SEND_COMMAND.search(whole)), runs, writes
    if p in ("eval", "iex", "invoke-expression"):
        return (would_send(" ".join(args[1:]), depth + 1) if len(args) > 1 else bool(SEND_COMMAND.search(whole))), runs, writes
    if p == "xargs":
        return bool(SEND_COMMAND.search(whole)), runs, writes
    return bool(SEND_COMMAND.search(text)), runs, writes       # anything else that names a send is refused as before


def would_send(cmd, depth=0):
    """True when a terminal command would send: it runs send.py or a module that sends, imports or calls a sending
    function, or reaches a sending web address with a web tool. A sending name that is only text (read, searched,
    diffed, a path given to a tool that reads, a string, a comment, a commit message) does not count."""
    cmd = str(cmd or "")
    if depth > 6:
        return bool(SEND_COMMAND.search(cmd))
    if not (SEND_COMMAND.search(cmd) or re.search(r"\bsend\b", cmd, re.I) or re.search(r"(?i)\s-e(?:c|n\w*)?\s", cmd)):
        return False                               # names nothing that sends, hides nothing: nothing to judge
    try:
        text, bodies = _heredocs(HARMLESS_REDIRECT.sub(" ", cmd))
        return _judge(text, bodies, cmd, depth)
    except Exception:
        return bool(SEND_COMMAND.search(cmd))      # a command this cannot take apart is judged on its words, as before


def _judge(text, bodies, whole, depth):
    text, inner = _substitutions(text)
    text = PS_LITERAL_SET.sub(r"\1\2", text)     # $f = "a path": PowerShell keeps a text; what later runs $f is judged there
    if any(_judge(s, bodies, whole, depth + 1) for s in inner):
        return True
    writes, runs = set(), set()
    for words in _segments(text):
        s, r, w = _segment_sends(words, bodies, whole, depth)
        if s:
            return True
        runs, writes = runs | r, writes | w
    made = writes & runs - {""}
    if not made:
        return False
    # the file written is the one run, in the same command (Kevin 11/25/26: judge what it does). When its content is
    # written here (cat > x.py <<'EOF' ... EOF), that content is judged as what runs: Python by what it imports and
    # calls (send words in its strings, such as replacement text it writes elsewhere, are text), anything else as a
    # command. When its content is not here, the command's own words decide, as before.
    contents = {}
    for words in _segments(text):
        target = key = None
        for k, w in enumerate(words[:-1]):
            if w in (">", ">>", "1>"):
                target = _name(words[k + 1])
            elif w == "<<<":
                key = words[k + 1]
        if target and key in bodies:
            contents[target] = bodies[key]
    for name in made:
        if name in contents:
            body = contents[name]
            if _code_sends(body) if name.endswith((".py", ".pyw")) else would_send(body, depth + 1):
                return True
        elif SEND_COMMAND.search(whole):
            return True
    return False


# --- where a terminal command writes (the program-files lock judges by this; reading is never a write) -------------------
ALL_ARGS_WRITE = {"rm", "del", "erase", "remove-item", "ri", "rmdir", "rd", "touch", "mkdir", "md", "new-item", "ni", "truncate",
                  "clear-content", "clc", "set-content", "sc", "add-content", "ac", "out-file", "tee", "tee-object", "ren",
                  "rename-item", "rni", "attrib", "icacls", "takeown", "unlink", "shred", "chmod", "chown", "mv", "move",
                  "move-item", "mi"}
DEST_WRITE = {"cp", "copy", "copy-item", "cpi", "xcopy", "install", "ln", "rsync", "robocopy"}
PS_PATH = {"-path", "-literalpath", "-lp", "-pspath", "-filepath", "-destination"}
PS_VALUE = {"-value", "-encoding", "-itemtype", "-type", "-filter", "-include", "-exclude", "-erroraction", "-ea", "-name",
            "-newname", "-inputobject", "-width", "-delimiter"}
CODE_WRITES = re.compile(r"open\([^)]*,\s*(?:mode\s*=\s*)?[rRbBuUfF]*['\"][^'\"]*[wax+]|\.open\(\s*(?:mode\s*=\s*)?['\"][^'\"]*[wax+]|"
                         r"write_text|write_bytes|shutil\.|os\.(?:remove|unlink|rename|replace|makedirs|mkdir|rmdir|removedirs)|"
                         r"\.(?:unlink|mkdir|touch|rename|rmdir)\(|writealltext|writeallbytes|appendalltext|\[io\.file\]", re.I)
PY_STRINGS = re.compile(r"""[rRbBuUfF]*('''.*?'''|\"\"\".*?\"\"\"|'[^'\n]*'|"[^"\n]*")""", re.S)


def _path(word, here):
    """A file word as a full path, read from the folder here; None when it cannot be known."""
    w = str(word or "").strip().strip("\"'")
    if not w or "$" in w or SUBST in w or "%" in w or w.startswith("~") or "\x00" in w:
        return None
    m = re.match(r"^/([A-Za-z])(/.*)?$", w)                      # Git Bash /c/x is C:\x
    if m:
        w = m.group(1) + ":\\" + (m.group(2) or "").lstrip("/")
    if not os.path.isabs(w) and not re.match(r"^[A-Za-z]:", w):
        if not here:
            return None
        w = os.path.join(here, w)
    return os.path.abspath(w)


def _code_targets(code):
    """(files, unknown) a piece of code may write: when it writes at all, every string in it that could be a path."""
    if not CODE_WRITES.search(code):
        return [], False
    found = [s.strip("'\"") for s in PY_STRINGS.findall(code)]
    found = [s for s in found if s and ("/" in s or "\\" in s or "." in s)]
    return found, not found


def command_targets(cmd, cwd=None, depth=0):
    """Where a terminal command writes: (full paths, unknown). unknown is True when a write's place cannot be read (a
    variable, a substitution, code that writes to a path it builds). Reading, searching and running a program are not
    writes; a file is written by a redirect, a command that writes, moves, copies or deletes files, sed -i, or code
    (python -c, a here-document fed to python, PowerShell's file calls) that writes."""
    if depth > 6:
        return [], True
    text, bodies = _heredocs(HARMLESS_REDIRECT.sub(" ", str(cmd or "")))
    text, inner = _substitutions(text)
    out, unknown, here = [], False, cwd
    for s in inner:
        t, u = command_targets(s, here, depth + 1)
        out, unknown = out + t, unknown or u

    def add(words, where):
        nonlocal unknown
        for w in words:
            p = _path(bodies.get(w, w), where)
            if p is None:
                unknown = True
            else:
                out.append(p)
    for words in _segments(text):
        args, stdin, i = [], None, 0
        while i < len(words):
            w = words[i]
            if w and set(w) <= set("<>&"):
                target = words[i + 1] if i + 1 < len(words) else ""
                if w == "<<<":
                    stdin = bodies.get(target, target)
                elif not w.startswith("<"):
                    add([target], here)
                i += 2
                continue
            args.append(w)
            i += 1
        while args and (re.match(r"^[A-Za-z_]\w*=", args[0]) or _prog(args[0]) in PREFIXES):
            args = args[1:]
        if not args:
            continue
        p = _prog(args[0])
        low = [a.lower() for a in args]
        if p in ("cd", "set-location", "sl", "pushd", "chdir") and len(args) > 1:
            here = _path(next((a for a in args[1:] if not a.startswith("-")), ""), here)
            continue
        if re.search(r"writealltext|writeallbytes|appendalltext|\[io\.file\]", " ".join(low)):
            t, u = _code_targets(" ".join("'%s'" % a for a in args))
            add(t, here)
            unknown = unknown or u
            continue
        if p in ALL_ARGS_WRITE or p in DEST_WRITE or (p == "sed" and any(re.fullmatch(r"-\w*i\w*|--in-place\S*", a) for a in args[1:])) \
                or (p == "perl" and any(re.fullmatch(r"-\w*i\w*", a) for a in args[1:])):
            plain, named, j = [], [], 1
            while j < len(args):
                a, la = args[j], low[j]
                if la in PS_PATH:
                    named += args[j + 1:j + 2]
                    j += 2
                    continue
                if la in PS_VALUE:
                    j += 2
                    continue
                if not a.startswith("-") or a == "-":
                    plain.append(a)
                j += 1
            if p == "sed" and not any(a in ("-e", "--expression", "-f") or a.startswith("--expression") for a in args):
                plain = plain[1:]                              # the first word is sed's own script
            if p in DEST_WRITE:
                dest = [a for a in named if a] if any(la == "-destination" for la in low) else []
                plain = dest or (plain[1:2] if p == "robocopy" else plain[-1:])
                named = []
            add(plain + named, here)
            continue
        if p == "dd":
            add([a[3:] for a in args[1:] if a.startswith("of=")], here)
            continue
        if p == "find" and ("-delete" in low or any(_prog(a) in ALL_ARGS_WRITE | DEST_WRITE for a in args[1:])):
            start = []
            for a in args[1:]:
                if a.startswith("-") or a in ("(", "!"):
                    break
                start.append(a)
            add(start or ["."], here)
            continue
        if PYTHONS.match(p):
            code = None
            for j, a in enumerate(args[1:], 1):
                if re.fullmatch(r"-\w*c", a):
                    code = args[j + 1] if j + 1 < len(args) else ""
                    break
                if not a.startswith("-"):
                    break
            if code is None and stdin is not None:
                code = stdin
            if code is not None:
                t, u = _code_targets(code)
                add(t, here)
                unknown = unknown or u
            continue
        if p in SHELLS or p == "cmd" or p in POWERSHELLS or p in ("eval", "iex", "invoke-expression"):
            inner_cmd = None
            for j, a in enumerate(args[1:], 1):
                if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*|/c|/k|-command", a.lower()):
                    inner_cmd = " ".join(args[j + 1:])
                    break
            if p in ("eval", "iex", "invoke-expression"):
                inner_cmd = " ".join(args[1:])
            if inner_cmd is None and stdin is not None and p in SHELLS | POWERSHELLS:
                inner_cmd = stdin
            if inner_cmd:
                t, u = command_targets(inner_cmd, here, depth + 1)
                out, unknown = out + t, unknown or u
            continue
        if p == "xargs" and any(_prog(a) in ALL_ARGS_WRITE | DEST_WRITE for a in args[1:]):
            unknown = True
    return out, unknown


OWN_SCRIPTS = re.compile(r"(?<![A-Za-z0-9_.-])(setup_home|assistant)\.py(?![A-Za-z0-9_])", re.I)   # the program's own scripts: they make their own checks
READS_ONLY = re.compile(r"^\s*(?:cat|type|tail|head|cmp|fc|diff|grep|findstr|get-content|gc|select-string|sls|wc|sort|uniq|ls|dir|"
                        r"echo|pwd|cd|test|stat|sha256sum|certutil|get-filehash|git\s+(?:status|log|diff|show))\b", re.I)
HARMLESS_REDIRECT = re.compile(r"\d?>&\d|\d?>{1,2}\s*(?:/dev/null|nul|\$null)(?![\w.])", re.I)


def own_script_call(cmd):
    """True when the command runs the program's own scripts, alone or chained only with commands that read (a check of a
    file or a log beside an update step): the scripts make their own checks. Any other part, or a redirect into a file,
    and it is judged like any other command."""
    plain = HARMLESS_REDIRECT.sub(" ", cmd)
    if "`" in plain or ">" in plain or not OWN_SCRIPTS.search(plain):
        return False
    parts = [p for p in re.split(r"\s*(?:;|&&|\|\||\||\n)\s*", plain) if p.strip()]
    return all(OWN_SCRIPTS.search(p) or READS_ONLY.match(p) for p in parts)
REPLAY_CALL = re.compile(r'^\s*python[w3]?(?:\.exe)?\s+("?)([^\s"]*replay\.py)\1\s+(?:erase|run-week|continue|status|report|dry-run)'
                         r'(?:\s+--(?:start|texts-folder)\s+(?:"[^"$]*"|[^\s"$]+))*\s*$', re.I)
REPLAY_AROUND = re.compile(r"^\s*(?:tail|head)(?:\s+-n?\s*\d+)?\s*$|^\s*cd\s+(\S.*?)\s*$", re.I)


def replay_call(cmd, cwd, root):
    r"""True when the command is the program's own rebuild tool (System\live\replay.py of this copy) run with one of its
    commands: erase, run-week, continue, status, report, dry-run, from that folder (the working folder, or a cd to it, or
    its full path), alone or piped into tail/head. Any other script, redirect into a file or chained command is not."""
    plain = HARMLESS_REDIRECT.sub(" ", cmd)
    if "`" in plain or ">" in plain or "$(" in plain or "<" in plain:
        return False
    live = os.path.normcase(os.path.abspath(os.path.join(root, "System", "live")))
    here, seen = str(cwd or ""), False
    for part in (p for p in re.split(r"\s*(?:;|&&|\|\||\||\n)\s*", plain) if p.strip()):
        m = REPLAY_CALL.match(part)
        if m:
            script = m.group(2).replace("/", os.sep)
            script = script if os.path.isabs(script) else os.path.join(here, script)
            if os.path.normcase(os.path.abspath(script)) != os.path.join(live, "replay.py"):
                return False
            seen = True
            continue
        a = REPLAY_AROUND.match(part)
        if not a:
            return False
        if a.group(1):
            d = a.group(1).strip("\"'").replace("/", os.sep)
            here = d if os.path.isabs(d) else os.path.join(here, d)
    return seen


ITEM_OUTPUT = re.compile(r"^live_items_out\.json$", re.I)       # the item writer's output (think._write_batch)


def open_changes(home):
    """The change records with a go on them (state go or doing), newest first."""
    out = []
    for f in sorted(glob.glob(os.path.join(home, "changes", "*.json")), key=os.path.getmtime, reverse=True):
        c = _read(f, None)
        if isinstance(c, dict) and c.get("state") in ("go", "doing"):
            out.append(c)
    return out


def route(ev):
    """Which guards apply to one tool call, and their joint verdict. ev is what the hook sends (rulebook_guard.event):
    {"tool", "input", "cwd", "root", "home", "where": hidden|assistant|elsewhere, "writes": [{"path", "text"}],
     "command", "command_writes"}."""
    home = ev.get("home") or home_dir()
    rules, _w, _s = book(home)
    tool, where = str(ev.get("tool") or ""), ev.get("where")
    broken, guards = [], set()
    root = os.path.abspath(ev.get("root") or os.path.dirname(GENERAL))
    general = os.path.join(root, "System")

    def in_general(path):
        q = os.path.normcase(os.path.abspath(path))
        g = os.path.normcase(general)
        return q == g or q.startswith(g + os.sep)

    def in_taught(path):
        return part_of(path, home) in ("taught", "mods")       # the owner's own: taught add-ons and mods

    mine = where in ("assistant", "hidden")      # (b) to (e) guard the assistant's own work; (a) holds everywhere
    # (b) Claude never sends: a connector's sending tool, or a command that would send
    if mine and tool.startswith("mcp__") and not APP_TOOL.search(tool) and SEND_TOOL.search(tool.split("__")[-1]):
        guards.add("b")
        broken += check_send({}, {"kind": "none", "home": home})["broken"]
    cmd = str(ev.get("command") or "")
    sends = bool(cmd) and would_send(cmd)
    own_script = bool(cmd) and where != "hidden" and not sends and (
        own_script_call(cmd) or replay_call(cmd, ev.get("cwd"), root))   # the script, with nothing but reads beside it
    if mine and sends:
        guards.add("b")
        broken += check_send({}, {"kind": "none", "home": home})["broken"]
    # writes by file tools
    changes = None
    for w in ev.get("writes") or []:
        path = w.get("path") or ""
        if where == "hidden" and part_of(path, home) == "mods":
            # the one exception to E3: the hidden run that makes a change the owner agreed and pressed go on from the page
            # (change_job.py) writes that change's own mod files, and nothing else
            guards |= {"c", "e"}
            changes = open_changes(home) if changes is None else changes
            if not [c for c in changes if c.get("part") == "mods" and check_program_edit(path, c)["ok"]]:
                broken += check_part(path, "run", home)["broken"]
            continue
        if where == "hidden":
            guards.add("e")
            broken += check_part(path, "run", home)["broken"]
            if ITEM_OUTPUT.search(os.path.basename(path)) and isinstance(w.get("text"), str):
                guards.add("a")          # an item writer's output: every card in it follows the page's rules
                try:
                    out = json.loads(w["text"])
                except ValueError:
                    out = None
                given = _read(os.path.join(os.path.dirname(path), "live_items_payload.json"), {}) or {}
                known = sorted({str(m.get("id")) for e in given.get("items") or [] for m in e.get("messages") or []} |
                               {str(m.get("id")) for m in given.get("loose_messages") or []})
                loose = [m.get("id") for m in given.get("loose_messages") or []]
                for n, card in enumerate((out or {}).get("items") or [] if isinstance(out, dict) else []):
                    for b in check_card(card, {"home": home, "message_ids": known})["broken"]:
                        broken.append(dict(b, field=f"items[{n}].{b.get('field')}"))
                for n, card in enumerate((out or {}).get("new_items") or [] if isinstance(out, dict) else []):
                    for b in check_card(card, {"home": home, "new": True, "message_ids": known, "loose_ids": loose})["broken"]:
                        broken.append(dict(b, field=f"new_items[{n}].{b.get('field')}"))
            continue
        if in_general(path) and where != "hidden":
            guards |= {"c", "e"}         # the program's own files: only an update writes them; an owner's change is a mod
            broken.append(_broke(rules, "C1", "path", more="the program's own files are never edited here; "
                                                           "an owner's change is made as a mod (in the mods folder)"))
        elif in_taught(path):
            guards |= {"c", "e"}
            changes = open_changes(home) if changes is None else changes
            fits = [c for c in changes if check_program_edit(path, c)["ok"]]
            if not fits:
                broken += check_program_edit(path, changes[0] if changes else None)["broken"]
            if in_general(path) and isinstance(w.get("text"), str):
                guards.add("d")
                broken += check_general_text(path, w["text"], home)["broken"]
    # writes by terminal commands: inside the program they need a change under a go; a hidden run writes nothing that way.
    # A command is judged by where it writes: reading the program while writing elsewhere is not a change to it.
    if cmd and where == "hidden" and ev.get("command_writes") and not own_script:
        guards.add("e")
        broken.append(_broke(rules, "E3", "command", more="a hidden run does not change files by command"))
    elif cmd and mine and not own_script:
        targets, unknown = command_targets(cmd, ev.get("cwd"))
        low = cmd.replace("/", "\\").lower()
        cwd_general = bool(ev.get("cwd")) and in_general(ev["cwd"])
        mine_dirs = (os.path.join(home, "taught").lower(), os.path.join(home, "mods").lower())
        if any(in_general(t) for t in targets) or (unknown and (general.lower() in low or cwd_general)):
            guards.add("c")
            broken.append(_broke(rules, "C1", "command", more="the program's own files are never changed here; "
                                                              "an owner's change is made as a mod (in the mods folder)"))
        elif any(in_taught(t) for t in targets) or (unknown and any(d in low for d in mine_dirs)):
            guards.add("c")
            if not open_changes(home):
                broken += check_program_edit(os.path.join(home, "mods"), None)["broken"]
    v = _verdict("".join(sorted(guards)) or "-", broken)
    return v


# --- the command line ------------------------------------------------------------------------------------------------------
def main(argv):
    if len(argv) == 3 and argv[1] == "route":
        try:
            v = route(json.loads(sys.stdin.read() if argv[2] == "-" else open(argv[2], encoding="utf-8").read()))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"ok": False, "why": f"{type(e).__name__}: {e}"}))
            return 1
        print(json.dumps(v))
        if not v["ok"]:
            print(said(v), file=sys.stderr)
        return 0 if v["ok"] else 2
    if len(argv) != 3 or argv[1] not in "abcde":
        print(__doc__)
        return 1
    try:
        raw = sys.stdin.read() if argv[2] == "-" else open(argv[2], encoding="utf-8").read()
        q = json.loads(raw)
        g = argv[1]
        v = (check_card(q.get("card"), q.get("context")) if g == "a" else
             check_send(q.get("message"), q.get("authority") or {"kind": "none"}) if g == "b" else
             check_program_edit(q.get("path"), q.get("change")) if g == "c" else
             check_general_text(q.get("path"), q.get("text") or "", q.get("home"), q.get("extra_terms")) if g == "d" else
             check_part(q.get("path"), q.get("writer"), q.get("home")))
    except Exception as e:  # noqa: BLE001  a check that cannot run is a refusal, never a pass
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1
    print(json.dumps(v))
    if not v["ok"]:
        print(said(v), file=sys.stderr)
    return 0 if v["ok"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
