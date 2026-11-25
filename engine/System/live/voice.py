r"""The owner's voice: learned from what they sent (mail, texts from the phone or the page, any other channel connected), used for
every draft the assistant writes, and taught by how the owner changes those drafts.

    build(now=None)             learn the profile from the owner's sent messages: greetings, sign-offs, typical phrases, how
                                formal they are with each kind of recipient, the stock phrases they never use, and their style on
                                each channel (email, texts, any other) and with each person who gets a different one (how formal,
                                how long, how they open and sign off). Kept in <home>\personal\voice.json (the owner's computer
                                only), with the owner's own corrections and what their edits taught, which a rebuild never replaces.
    refresh()                   build(), by a pass, at most once a day (program code, no AI); also on the owner's asking (Settings,
                                Your voice, Learn my voice now; the Writing style builder in Settings, Tools; assistant.py voice-learn)
    learn_now()                 build(), with the words the page and the command say
    profile()                   the profile as it stands, the owner's corrections over what was learned
    level_for(to)               Casual, Everyday or Formal for these recipients: the owner's Settings choice, or, under "Let the
                                assistant choose", by how often they are in touch (a close colleague Everyday, someone new Formal)
    style_for(channel, to)      (the channel's style, this person's own or None): the owner's lines in Settings, else learned
    write(body, to)             an email draft in the owner's voice: run through the humanize pass (the plugin's humanize-text
                                skill, as prompts\humanize.md) with the voice, then the greeting and sign-off for this person or
                                level put in. Returns (body, {"level", "humanized", "style"}).
    write_text(text, to, name)  a text draft shaped to how the owner texts this person, or texts at all
    compare(drafted, sent)      what the owner changed in a draft before sending it
    learn_edit(...)             what one sent draft teaches the profile (writing.py calls it)
    for_page() / save_owner()   what Settings shows, and the owner's corrections from it

No warning is given before a send that does not sound like the owner (a declared assumption; it can be added later).
"""
import datetime as dt
import json
import os
import re
import sys
from collections import Counter

import common

FILE = os.path.join(common.PERSONAL, "voice.json")
LEVELS = ("casual", "everyday", "formal")
LABEL = {"casual": "Casual", "everyday": "Everyday", "formal": "Formal", "choose": "Let me choose"}
GREETING = re.compile(r"^\s*(hi|hey|hello|dear|good morning|good afternoon|morning|hiya)\b[^\n]{0,60}?[,!:.]?\s*$", re.I)
SIGNOFF = re.compile(r"^\s*(thanks( so much| again| a lot)?|thank you( so much)?|thx|cheers|best( regards| wishes)?|kind regards|regards|"
                     r"warm regards|all the best|talk soon|sincerely|take care|many thanks)\s*[,!.]?\s*$", re.I)
CASUAL_GREETINGS, FORMAL_GREETINGS = ("hey", "hiya", "morning"), ("dear", "hello", "good morning", "good afternoon")
FORMAL_SIGNOFFS, CASUAL_SIGNOFFS = ("best regards", "kind regards", "sincerely", "regards", "warm regards"), ("cheers", "thx", "talk soon")
# stock phrases of written-for-you mail; the ones the owner never wrote are the profile's "never says"
STOCK = ("I hope this email finds you well", "I hope you are doing well", "Please don't hesitate to reach out", "Please do not hesitate to contact me",
         "I wanted to reach out", "I am writing to", "Thank you for your patience", "At your earliest convenience", "Per my last email",
         "Circling back", "Touch base", "Going forward", "I trust this finds you well", "Looking forward to hearing from you",
         "delve", "leverage", "seamless", "Kind regards", "Best regards", "Warm regards")
WORD = re.compile(r"[a-z']+")
SMALL = set("the a an and or of to in on for with is are was were be been it its this that these those you your we our i me my do does "
            "did can could should would will shall may might what which who when where why how any some there here have has had not no "
            "yes from by at as into about than then so if just also".split())


def _text(body, subject=""):
    if common.paths.MODULE_A not in sys.path:
        sys.path.insert(0, common.paths.MODULE_A)
    import cleantext
    return cleantext.new_text(body or "", limit=4000, subject=subject or "")


def _lines(text):
    return [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]


def _greeting(lines):
    m = GREETING.match(lines[0]) if lines else None
    return m.group(1).capitalize() if m else None


def _signoff(lines):
    """The sign-off the owner typed: the first sign-off line after the opening, before anything quoted or forwarded (the
    signature under it is not part of it); else one of the last lines."""
    for l in lines[1:]:
        if CUT_HERE.match(l):
            break
        m = SIGNOFF.match(l)
        if m:
            w = m.group(0).strip().rstrip(",!. ")
            return w[:1].upper() + w[1:] + ","
    for l in reversed(lines[-4:]):
        m = SIGNOFF.match(l)
        if m:
            w = m.group(0).strip().rstrip(",!. ")
            return w[:1].upper() + w[1:] + ","
    return None


CONTACT_LINE = re.compile(r"@|https?://|www\.|\b\d{3}[\s.)-]*\d{3}[\s.-]*\d{4}\b|\b(?:suite|ste|street|st|avenue|ave|road|rd|blvd|drive|dr|"
                          r"lane|ln|way|po box|p\.o\.|fax|tel|phone|cell|mobile|office|direct)\b\.?\s*[:#\d]", re.I)
CUT_HERE = re.compile(r"^\s*(?:--\s*$|__+|sent from my|get outlook|on .{3,120} wrote:|from:\s|-+\s*original message|-+\s*forwarded message|"
                      r"begin forwarded message|this (?:e-?mail|message) (?:and any|is intended|may contain)|confidentiality notice|disclaimer)", re.I)
BOILER = re.compile(r"^\s*(?:this (?:message|e-?mail) is formatted in|this is a multi-part message|please consider the environment)", re.I)
PLACE_WORDS = set("building buildings room rooms hall street st road rd avenue ave lane drive church office campus center centre gym kitchen "
                  "school lobby parking lot warehouse shop site plant suite floor wing field park".split())   # a phrase ending in one names a place
MIN_RECIPIENTS = 3              # a phrase is the owner's own only when they write it to at least this many different people
MIN_MESSAGES = 3                # ... in at least this many different messages
TEST_SUBJECT = re.compile(r"\btest(?:ing)?\b", re.I)       # a test send (the assistant's own setup checks, or the owner's): not their voice
ADDR = re.compile(r"[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}")
LIST_LINE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)]|\d{1,2}(?::\d\d)?\s*(?:am|pm)\b)|\b\d{1,2}(?::\d\d)?\s*(?:am|pm)\b", re.I)


def _listy(lines):
    """A schedule, a list or a table rather than words to someone: most of its lines are list items or carry a time."""
    return len(lines) >= 3 and sum(1 for l in lines if LIST_LINE.search(l)) * 2 > len(lines)


def _typed(lines):
    """The lines the owner typed: the greeting on, up to the sign-off (the signature, company, address and anything quoted or
    forwarded after it are not their words), without lines that are contact details."""
    out = []
    for i, l in enumerate(lines):
        if CUT_HERE.match(l) or (i and SIGNOFF.match(l)):
            break
        if l.startswith(">") or CONTACT_LINE.search(l) or BOILER.match(l):
            continue
        out.append(l)
    return out


def _cased(lines, tally):
    """Counts, for each word in the middle of a sentence, how often it is written capitalised and how often not."""
    for l in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", l):
            for w in re.findall(r"[A-Za-z][A-Za-z']*", sentence)[1:]:
                if w.lower() != "i" and not w.startswith("I'"):
                    tally.setdefault(w.lower(), [0, 0])[0 if w[0].isupper() else 1] += 1


def _proper(tally):
    """Names, companies and places: words written capitalised mid-sentence at least a third of the time. Never part of a phrase."""
    return {w for w, (up, low) in tally.items() if up * 2 >= low and up}


def _kind_of(con, to_keys):
    """close, known or new: how often the owner is in touch with the main recipient. con is a database connection, or the
    levels read beforehand (contact_strength.levels), so a long job can ask with the database closed."""
    import contact_strength
    addr = re.search(r"[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}", str(to_keys or "").lower())
    key = ("email:" + addr.group(0)) if addr else str(to_keys or "").split(",")[0].strip().lower()
    if isinstance(con, dict):
        level = con.get(key, 0) if key else 0
    else:
        level = contact_strength.for_person(con, key)["level"] if key else 0
    return "close" if level >= 2 else "known" if level == 1 else "new"


def _level_of(greets, signs, contractions, words):
    """How formal a set of messages is: casual, everyday or formal."""
    g, s = Counter(x.lower() for x in greets if x), Counter(x.lower().rstrip(",") for x in signs if x)
    formal = sum(v for k, v in g.items() if k in FORMAL_GREETINGS) + sum(v for k, v in s.items() if k in FORMAL_SIGNOFFS)
    casual = sum(v for k, v in g.items() if k in CASUAL_GREETINGS) + sum(v for k, v in s.items() if k in CASUAL_SIGNOFFS)
    rate = contractions / max(1, words)
    if formal > casual and rate < 0.02:
        return "formal"
    if casual > formal:
        return "casual"
    return "everyday"


def build(now=None, con=None, save=True, extra_rows=()):
    """Learn the profile from the messages the owner wrote. Returns it (and saves it, keeping the owner's corrections; with
    save=False only returns what it would learn). The database is open only to read the sent messages, the owner's own
    addresses and the contact levels; the learning runs with it closed. extra_rows: more sent messages as (channel, to_keys,
    subject, body, thread_id), read from outside the stored mail (the setup's sent emails, fetched from the catalog). Left out: mail sent only to the owner's own
    addresses, test sends (a subject saying test), and a body sent word for word more than once (a template counts once)."""
    import contact_strength
    import db
    now = now or dt.datetime.now()
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        rows = con.execute("SELECT channel, to_keys, subject, body, thread_id FROM messages WHERE direction = 'out' AND ts >= ? "
                           "ORDER BY ts DESC LIMIT 2000", [now - dt.timedelta(days=365)]).fetchall()
        known = contact_strength.levels(con)
        names = _names(con)
        mine ={str(a).lower() for (a,) in con.execute("SELECT DISTINCT account FROM messages WHERE channel = 'email'").fetchall() if a}
        mine |= {str(f).split(":", 1)[1].lower() for (f,) in con.execute(
            "SELECT DISTINCT from_key FROM messages WHERE direction = 'out' AND starts_with(from_key, 'email:')").fetchall()}
    finally:
        if own:
            con.close()
    rows = list(rows) + list(extra_rows)
    # the learning, with no database open
    greets, signs, grams, by_kind, all_text = Counter(), Counter(), Counter(), {}, []
    emails, feats = 0, []                # feats: each message's shape, for the style of each channel and each person
    said_to, cased = {}, {}              # each phrase: the people it was written to; each word: written capitalised or not
    import common as _c
    own_name = {w.lower() for w in re.findall(r"[A-Za-z']+", str(_c.owner() or ""))}
    bodies = set()
    for channel, to_keys, subject, body, _th in rows:
        if channel == "email" and TEST_SUBJECT.search(str(subject or "")):
            continue                    # a test send
        to = set(ADDR.findall(str(to_keys or "").lower()))
        if channel == "email" and to and to <= mine:
            continue                    # sent only to the owner's own addresses
        text = _text(body) if channel == "email" else str(body or "")      # no subject: a forward is cut at its header
        lines = _lines(text)
        if not lines:
            continue
        same = " ".join(WORD.findall(" ".join(lines).lower()))
        if _listy(lines):
            continue                    # a schedule or list: not how the owner talks
        if same in bodies:
            continue                    # the same words sent again: a template counts once
        bodies.add(same)
        all_text.append(text.lower())
        g, s = (_greeting(lines), _signoff(lines)) if channel == "email" else (None, None)
        if channel == "email":
            emails += 1
        if g:
            greets[g] += 1
        if s:
            signs[s] += 1
        words = WORD.findall(text.lower())
        typed = _typed(lines)
        _cased(typed, cased)
        tw = WORD.findall(" ".join(typed).lower())
        who = (re.search(r"[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}", str(to_keys or "").lower()) or [str(to_keys or "").split(",")[0].strip().lower()])[0]
        seen, run, runs = set(), [], []
        for w in tw + ["0"]:            # a word with a digit (v2, 40132018) ends a run of words: a phrase never spans it
            if any(ch.isdigit() for ch in w):
                if run:
                    runs.append(run)
                run = []
            else:
                run.append(w)
        for part in runs:
            for n in (2, 3):
                for i in range(len(part) - n + 1):
                    gram = part[i:i + n]
                    if gram[0] in SMALL or gram[-1] in SMALL:
                        continue
                    seen.add(" ".join(gram))
        for x in seen:
            grams[x] += 1
            said_to.setdefault(x, set()).add(who)
        k = by_kind.setdefault(_kind_of(known, to_keys), {"messages": 0, "greets": [], "signs": [], "contractions": 0, "words": 0})
        k["messages"] += 1
        k["greets"].append(g)
        k["signs"].append(s)
        k["contractions"] += len(re.findall(r"\b\w+'(s|t|re|ll|ve|d|m)\b", text.lower()))
        k["words"] += len(words)
        feats.append({"group": group_of(channel), "addr": _addr_of(to_keys), "words": len(tw) if channel == "email" else len(words),
                      "greeting": _greeting(lines), "signoff": _signoff(lines) if len(lines) > 1 else None,
                      "lower": bool(re.match(r"[a-z]", lines[0])), "bare": not re.search(r"[.!?)]\s*$", (typed or lines)[-1]),
                      "contr": len(re.findall(r"\b\w+'(s|t|re|ll|ve|d|m)\b", text.lower())), "all": len(words)})
    skip = {x.lower().rstrip(",") for x in list(greets) + list(signs)}
    drop = _proper(cased) | own_name
    phrases = [p for p, c in grams.most_common(400) if c >= MIN_MESSAGES and p not in skip and len(said_to.get(p, ())) >= MIN_RECIPIENTS
               and not (set(p.split()) & drop) and p.split()[-1] not in PLACE_WORDS]
    phrases = [p for p in phrases if not any(p != q and p in q for q in phrases)][:8]     # "v credential" inside "credential test" kept once
    joined = "\n".join(all_text)
    kinds = {k: {"messages": v["messages"], "level": _level_of(v["greets"], v["signs"], v["contractions"], v["words"]),
                 "greeting": (Counter(x for x in v["greets"] if x).most_common(1) or [[None]])[0][0],
                 "signoff": (Counter(x for x in v["signs"] if x).most_common(1) or [[None]])[0][0]} for k, v in by_kind.items()}
    top = lambda c, pick, dflt: next((x for x, _n in c.most_common() if pick(x.lower().rstrip(","))), dflt)   # noqa: E731
    greets_rarely = emails >= 10 and sum(greets.values()) * 3 < emails       # most of his emails open with no greeting at all
    learned = {
        "built_at": now.isoformat(timespec="seconds"), "messages": len(all_text),
        "greetings": [NO_GREETING] if greets_rarely else [x for x, _n in greets.most_common(4)],
        "greeted": f"{sum(greets.values())} of {emails} emails", "signoffs": [x for x, _n in signs.most_common(4)],
        "phrases": phrases, "kinds": kinds, **_styles(feats, names),
        "never": [p for p in STOCK if p.lower() not in joined][:10],
        "levels": {"casual": {"greeting": top(greets, lambda x: x in CASUAL_GREETINGS, "Hey"),
                              "signoff": top(signs, lambda x: x in CASUAL_SIGNOFFS or x.startswith("thanks"), "Thanks,")},
                   "everyday": {"greeting": top(greets, lambda x: x not in CASUAL_GREETINGS and x not in FORMAL_GREETINGS, "Hi"),
                                "signoff": top(signs, lambda x: x not in FORMAL_SIGNOFFS and x not in CASUAL_SIGNOFFS, "Thanks,")},
                   "formal": {"greeting": top(greets, lambda x: x in FORMAL_GREETINGS, "Hello"),
                              "signoff": top(signs, lambda x: x in FORMAL_SIGNOFFS, "Best regards,")}},
    }
    if not save:
        return learned
    saved = common.read_json(FILE, {}) or {}
    common.write_json(FILE, dict(saved, learned=learned, owner=saved.get("owner") or {}))     # his corrections and edits stay
    return profile()


NO_GREETING = "(no greeting)"   # how "he does not open with a greeting" is kept, learned or his own choice
NO_SIGNOFF = "(no sign-off)"


# --- how he writes on each channel and to each person ------------------------------------------------------------------
TEXT_CHANNELS = ("sms", "mms", "rcs", "text", "texts")
GROUP_NAMES = {"email": "Email", "text": "Texts"}
PERSON_MIN = 3                  # a person's own style is kept from this many messages to them, when it differs from the channel's
PEOPLE_MOST = 60
EDITS_KEPT = 100                # the newest edits kept in the profile's own history
EDIT_WEIGHT = 0.3               # how far one edit moves a length the profile holds
PEOPLE_LINE = re.compile(r"^\s*(.*?)\s*<([^>]*)>\s*,\s*([^:]+):\s*(.*)$")


def group_of(channel):
    """email, text (texts from the phone or the page), or any other channel connected by its own name."""
    c = str(channel or "").strip().lower()
    return "email" if c == "email" else "text" if c in TEXT_CHANNELS else (c or "other")


def group_name(g):
    return GROUP_NAMES.get(g, str(g or "other").replace("_", " ").capitalize())


def _addr_of(to_keys):
    """The main recipient as the profile knows a person: an email address, a phone number's last ten digits, or the channel's
    own name for them."""
    s = str(to_keys or "")
    if s.startswith("["):
        try:
            s = ",".join(str(x) for x in json.loads(s))
        except ValueError:
            pass
    if isinstance(to_keys, (list, tuple)):
        s = ",".join(str(x) for x in to_keys)
    m = ADDR.search(s.lower())
    if m:
        return m.group(0)
    first = re.sub(r"^(email|phone|sms|tel|mobile|text):", "", s.split(",")[0].strip().lower())
    digits = re.sub(r"\D", "", first)
    return digits[-10:] if len(digits) >= 10 else first


def _same_addr(a, b):
    a, b = str(a or "").strip().lower(), str(b or "").strip().lower()
    if not a or not b:
        return False
    da, dbb = re.sub(r"\D", "", a), re.sub(r"\D", "", b)
    if "@" not in a and "@" not in b and len(da) >= 10 and len(dbb) >= 10:
        return da[-10:] == dbb[-10:]
    return a == b


def _names(con):
    """{address or ten digits: the name on file}, read while the database is open; {} when it cannot be."""
    out = {}
    try:
        for key, name in con.execute("SELECT key, max(name) FROM contacts WHERE coalesce(name, '') <> '' GROUP BY key").fetchall():
            k = str(key or "").lower()
            if k.startswith("email:"):
                out[k[6:]] = name
            else:
                d = re.sub(r"\D", "", k)
                if len(d) >= 10:
                    out.setdefault(d[-10:], name)
    except Exception:  # noqa: BLE001  a name is only a label
        pass
    return out


def _style(ms, group):
    """One channel's or one person's style from its messages' shapes: formality, usual length, greeting, sign-off."""
    n = len(ms)
    lens = sorted(m["words"] for m in ms)
    g = Counter(m["greeting"] for m in ms if m["greeting"])
    s = Counter(m["signoff"] for m in ms if m["signoff"])
    level = Counter(_level_of([m["greeting"]], [m["signoff"]], m["contr"], m["all"]) for m in ms).most_common(1)[0][0]  # most of them
    lower = sum(1 for m in ms if m["lower"]) * 2 >= n
    if group != "email" and level == "everyday" and (lens[n // 2] < 15 or lower) and not any(x.lower() in FORMAL_GREETINGS for x in g):
        level = "casual"                # short, plain texts: casual unless he opens them formally
    return {"messages": n, "words": lens[n // 2], "level": level,
            "greeting": g.most_common(1)[0][0] if sum(g.values()) * 2 >= n else NO_GREETING,
            "signoff": s.most_common(1)[0][0] if sum(s.values()) * 2 >= n else NO_SIGNOFF,
            "lowercase": lower, "end_mark": sum(1 for m in ms if not m["bare"]) * 2 >= n}


def _differs(a, b):
    if a["level"] != b["level"] or a["greeting"] != b["greeting"] or a["signoff"] != b["signoff"]:
        return True
    lo, hi = sorted((max(1, a["words"]), max(1, b["words"])))
    return hi >= 2 * lo


def _styles(feats, names):
    """{"styles": {channel: style}, "people": [a person's own style, where it differs from the channel's]}."""
    by_group, by_person = {}, {}
    for f in feats:
        by_group.setdefault(f["group"], []).append(f)
        if f["addr"]:
            by_person.setdefault((f["group"], f["addr"]), []).append(f)
    styles = {g: _style(ms, g) for g, ms in by_group.items()}
    people = []
    for (g, a), ms in sorted(by_person.items(), key=lambda kv: -len(kv[1])):
        if len(ms) < PERSON_MIN:
            continue
        st = _style(ms, g)
        if _differs(st, styles[g]):
            people.append(dict(st, group=g, addr=a, name=names.get(a) or ""))
        if len(people) >= PEOPLE_MOST:
            break
    return {"styles": styles, "people": people}


def _merged(saved=None):
    """(styles, people) as learned from what he sent, with what his edits to my drafts taught laid over it."""
    saved = saved if saved is not None else (common.read_json(FILE, {}) or {})
    learned, ed = saved.get("learned") or {}, saved.get("edits") or {}
    styles = {g: dict(st) for g, st in (learned.get("styles") or {}).items()}
    for g, over in (ed.get("styles") or {}).items():
        styles[g] = dict(styles.get(g) or {"messages": 0, "level": "everyday", "words": 0, "greeting": NO_GREETING,
                                           "signoff": NO_SIGNOFF}, **over)
    people = {f"{p['group']}|{p['addr']}": dict(p) for p in learned.get("people") or [] if p.get("addr")}
    for k, over in (ed.get("people") or {}).items():
        g, a = k.split("|", 1)
        base = people.get(k) or dict(styles.get(g) or {}, group=g, addr=a, name="", messages=0)
        people[k] = dict(base, **{x: y for x, y in over.items() if y not in (None, "")})
    return styles, people


def _style_words(st):
    parts = [st.get("level") or "everyday"]
    if st.get("words"):
        parts.append(f"about {st['words']} words")
    g, s = st.get("greeting"), st.get("signoff")
    parts.append("no greeting" if not g or g == NO_GREETING else f'opens "{g}"')
    parts.append("no sign-off" if not s or s == NO_SIGNOFF else f'signs "{s}"')
    if st.get("lowercase"):
        parts.append("starts lowercase")
    if st.get("end_mark") is False:
        parts.append("no period at the end")
    return ", ".join(parts)


def _parse(words):
    """A style line's words back into a style (what Settings shows, or the owner's own edit of it)."""
    w = str(words or "")
    st = {"level": next((x for x in LEVELS if re.search(rf"\b{x}\b", w, re.I)), None)}
    m = re.search(r"about (\d+) words", w, re.I)
    st["words"] = int(m.group(1)) if m else None
    m = re.search(r'opens "([^"]*)"', w, re.I)
    st["greeting"] = m.group(1) if m else NO_GREETING if re.search(r"no greeting", w, re.I) else None
    m = re.search(r'signs "([^"]*)"', w, re.I)
    st["signoff"] = m.group(1) if m else NO_SIGNOFF if re.search(r"no sign-?off", w, re.I) else None
    st["lowercase"] = bool(re.search(r"starts lowercase", w, re.I))
    st["end_mark"] = not re.search(r"no period", w, re.I)
    return st


def style_lines(saved=None):
    styles, _p = _merged(saved)
    order = sorted(styles, key=lambda g: (g != "email", g != "text", g))
    return [f"{group_name(g)}: {_style_words(styles[g])}" for g in order]


def people_lines(saved=None):
    _s, people = _merged(saved)
    got = sorted(people.values(), key=lambda p: (-(p.get("messages") or 0), p["addr"]))
    return [f"{p.get('name') or p['addr']} <{p['addr']}>, {group_name(p['group']).lower()}: {_style_words(p)}" for p in got]


def style_for(group, addr="", name=""):
    """(the channel's style, this person's style or None) as drafts use them: the owner's own lines in Settings when he saved
    some, else what was learned with what his edits taught."""
    saved = common.read_json(FILE, {}) or {}
    own = saved.get("owner") or {}
    gname = group_name(group).lower()
    ch = next((_parse(l.split(":", 1)[1]) for l in (own.get("styles") or style_lines(saved))
               if ":" in l and l.split(":", 1)[0].strip().lower() == gname), None)
    per = None
    for l in own.get("people") or people_lines(saved):
        m = PEOPLE_LINE.match(l)
        if not m or m.group(3).strip().lower() != gname:
            continue
        if (addr and _same_addr(m.group(2), addr)) or (name and m.group(1).strip().lower() == str(name).strip().lower()):
            per = _parse(m.group(4))
            break
    return ch, per


def _first_line_greeting(lines):
    """The draft's greeting word ("Hi", "Hello") or None: a first line that is a greeting and little else."""
    first = next((l for l in lines if l.strip()), "")
    m = GREETING.match(first)
    return m.group(1).capitalize() if m and len(first.split()) <= 4 else None


def _parts(text):
    """(greeting, sign-off, the words between) of a draft or a sent message, his name under the sign-off left out."""
    lines = [l.rstrip() for l in str(text or "").replace("\r", "").split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    g = _first_line_greeting(lines)
    body = list(lines)
    if g:
        i = next(i for i, l in enumerate(body) if l.strip())
        body = body[i + 1:]
    s = None
    for i in range(len(body) - 1, max(-1, len(body) - 4), -1):
        if SIGNOFF.match(body[i]):
            w = body[i].strip().rstrip(",!. ")
            s, body = w[:1].upper() + w[1:] + ",", body[:i]
            break
    return g, s, "\n".join(body).strip()


def _sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", str(text or "")) if len(WORD.findall(x.lower())) >= 3]


def compare(drafted, sent):
    """What he changed between my draft and what went out: {"unchanged", "kept" (0 to 1, the share of my words that stayed, in
    order), "changes": [plain words], "greeting", "signoff", "words": (drafted, sent)}."""
    norm = lambda t: " ".join(str(t or "").split()).strip().lower()     # noqa: E731
    if norm(drafted) == norm(sent):
        g, s, b = _parts(sent)
        return {"unchanged": True, "kept": 1.0, "changes": [], "greeting": g, "signoff": s,
                "words": (len(WORD.findall(b.lower())),) * 2}
    import difflib
    dg, ds, db_ = _parts(drafted)
    sg, ss, sb = _parts(sent)
    dw, sw = WORD.findall(str(drafted or "").lower()), WORD.findall(str(sent or "").lower())
    m = difflib.SequenceMatcher(None, dw, sw, autojunk=False)
    kept = round(sum(b.size for b in m.get_matching_blocks()) / max(1, len(dw)), 2)
    changes = []
    if dg != sg:
        changes.append(f'You took out the greeting "{dg}".' if not sg else f'You opened with "{sg}" instead of "{dg}".' if dg
                       else f'You added the greeting "{sg}".')
    if ds != ss:
        changes.append(f'You took out the sign-off "{ds}".' if not ss else f'You signed off "{ss}" instead of "{ds}".' if ds
                       else f'You added the sign-off "{ss}".')
    a, b = len(WORD.findall(db_.lower())), len(WORD.findall(sb.lower()))
    if a and b and (b <= 0.8 * a or b >= 1.25 * a):
        changes.append(f"You made it {'shorter' if b < a else 'longer'}: {a} words to {b}.")
    gone = [x for x in _sentences(db_) if norm(x) not in norm(sb)]
    new = [x for x in _sentences(sb) if norm(x) not in norm(db_)]
    for x in gone[:2]:
        changes.append(f'You took out "{x[:90]}".')
    for x in new[:2]:
        changes.append(f'You wrote "{x[:90]}".')
    if not changes:
        changes.append("You changed a few words.")
    return {"unchanged": False, "kept": min(kept, 1.0), "changes": changes, "greeting": sg, "signoff": ss, "words": (a, b),
            "taken_out": [p for p in STOCK if p.lower() in norm(drafted) and p.lower() not in norm(sent)]}


def learn_edit(drafted, sent, channel, to="", name=""):
    """What one sent draft teaches the profile, kept in voice.json's "edits" (a rebuild from his sent messages keeps it): his
    greeting, sign-off and length for this person on this channel, the channel's usual length moved toward what he sent, and
    stock phrases he took out added to the ones drafts never use. Returns compare()'s result."""
    got = compare(drafted, sent)
    g = group_of(channel)
    addr = _addr_of(to)
    saved = common.read_json(FILE, {}) or {}
    ed = saved.setdefault("edits", {})
    styles, people = _merged(saved)
    words, key = got["words"][1], f"{g}|{addr}"
    if addr and (not got["unchanged"] or key in people):      # an unchanged send to someone with no style of their own adds none
        p = ed.setdefault("people", {}).setdefault(key, {})
        had = (people.get(key) or {}).get("words")
        p.update(greeting=got["greeting"] or NO_GREETING, signoff=got["signoff"] or NO_SIGNOFF)
        if words:
            p["words"] = round(had + (words - had) * EDIT_WEIGHT) if had else words
        if name:
            p["name"] = name
    if words and not got["unchanged"]:
        had = (styles.get(g) or {}).get("words") or words
        ed.setdefault("styles", {}).setdefault(g, {})["words"] = round(had + (words - had) * EDIT_WEIGHT)
    if got.get("taken_out"):
        ed["never"] = sorted(set(ed.get("never") or []) | set(got["taken_out"]))
    ed["history"] = ((ed.get("history") or []) + [{"at": common.now().isoformat(timespec="seconds"), "channel": g, "to": addr,
                                                   "kept": got["kept"], "unchanged": got["unchanged"], "changes": got["changes"]}])[-EDITS_KEPT:]
    common.write_json(FILE, saved)
    return got


def write_text(text, to="", name=""):
    """A text the assistant drafted, shaped to how he texts this person (or texts at all): no greeting or sign-off when he
    writes none, starting lowercase and leaving off the last period when that is his habit. (text, how)."""
    ch, per = style_for("text", to, name)
    st = per or ch
    t = str(text or "").replace("\r", "").strip()
    if not st or not t:
        return t, {"channel": "text", "style": None}
    lines = t.split("\n")
    if st.get("greeting") == NO_GREETING and len(lines) > 1 and _first_line_greeting(lines[:1]):
        lines = lines[1:]
    me = (common.personal().get("first_name") or common.owner() or "").split(" ")[0].lower()
    if st.get("signoff") == NO_SIGNOFF:
        while len(lines) > 1 and (SIGNOFF.match(lines[-1]) or (me and lines[-1].strip().lower() == me) or not lines[-1].strip()):
            lines.pop()
    t = "\n".join(lines).strip()
    if st.get("lowercase") and re.match(r"[A-Z][a-z]", t) and not re.match(r"I\b|I'", t):
        t = t[0].lower() + t[1:]
    if st.get("end_mark") is False and t.endswith(".") and not t.endswith(".."):
        t = t[:-1]
    return t, {"channel": "text", "style": "person" if per else "channel"}


def refresh(now=None):
    """The profile learned again from what he sent, by a pass, at most once a day (program code only, no AI). True when it
    learned. A replay never writes it."""
    if os.environ.get("ASSISTANT_REPLAY") == "1":
        return False
    now = now or dt.datetime.now()
    built = ((common.read_json(FILE, {}) or {}).get("learned") or {}).get("built_at")
    try:
        if built and now - dt.datetime.fromisoformat(built) < dt.timedelta(hours=24):
            return False
    except ValueError:
        pass
    return bool(build(now).get("messages"))


def for_chat(text=""):
    """How he writes, for Talk to your assistant to draft in: his style on each channel, and each person's own named in the words."""
    low = str(text or "").lower()
    ppl = [l for l in people_lines() if (PEOPLE_LINE.match(l) or [None, ""])[1] and
           (PEOPLE_LINE.match(l).group(1).split(" ")[0].lower() in low)]
    return {"by_channel": style_lines(), "these_people": ppl[:5]}


def profile():
    """What was learned, with the owner's corrections over it."""
    saved = common.read_json(FILE, {}) or {}
    out = dict(saved.get("learned") or {})
    taken_out = (saved.get("edits") or {}).get("never") or []       # stock phrases he took out of my drafts
    if taken_out:
        out["never"] = list(dict.fromkeys(list(out.get("never") or []) + taken_out))
    for k, v in (saved.get("owner") or {}).items():
        if isinstance(v, list):
            out[k] = v
    return out


def setting():
    v = str(((common.settings().get("voice") or {}) if isinstance(common.settings().get("voice"), dict) else {}).get("level") or "choose")
    return v if v in LEVELS + ("choose",) else "choose"


def level_for(to, con=None):
    s = setting()
    if s != "choose":
        return s
    import db
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        kind = _kind_of(con, ",".join(to) if isinstance(to, list) else to)
    finally:
        if own:
            con.close()
    learned = ((profile().get("kinds") or {}).get(kind) or {}).get("level")
    if kind == "new":
        return "formal"                 # someone new: formal, whatever the owner's habit with friends
    return learned if kind == "known" and learned in LEVELS else "everyday"


def _first_name(to):
    import db
    addr = re.search(r"[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}", (",".join(to) if isinstance(to, list) else str(to or "")).lower())
    if not addr:
        return ""
    try:
        con = db.connect(read_only=True)
        try:
            row = con.execute("SELECT max(c.name) FROM contacts c WHERE c.person_id = (SELECT person_id FROM contacts WHERE key = ?)",
                              ["email:" + addr.group(0)]).fetchone()
            name = row[0] if row and row[0] else None
            if not name:
                got = con.execute("SELECT s.from_name FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.from_key = ? "
                                  "AND coalesce(s.from_name, '') <> '' ORDER BY m.ts DESC LIMIT 1", ["email:" + addr.group(0)]).fetchone()
                name = got[0] if got else None
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        name = None
    return str(name or "").split(" ")[0]


def shape(body, to, level):
    """The level's greeting first and its sign-off last, in the owner's own words; the rest as written."""
    p = profile()
    own = (common.read_json(FILE, {}) or {}).get("owner") or {}
    words = ((p.get("levels") or {}).get(level) or {})
    greet, sign = words.get("greeting") or {"casual": "Hey", "everyday": "Hi", "formal": "Hello"}[level], words.get("signoff") or {
        "casual": "Thanks,", "everyday": "Thanks,", "formal": "Best regards,"}[level]
    if own.get("greetings"):        # the owner's own choice is used at every level (a formal "Sincerely," never replaces it)
        greet = own["greetings"][0]
    if own.get("signoffs"):
        sign = own["signoffs"][0]
    _ch, per = style_for("email", _addr_of(to)) if _addr_of(to) else (None, None)
    if per and setting() == "choose":   # how he writes to this person, learned or taught by his edits; a fixed Tone wins
        if not own.get("greetings") and per.get("greeting"):
            greet = None if per["greeting"] == NO_GREETING else per["greeting"]
        if not own.get("signoffs") and per.get("signoff"):
            sign = None if per["signoff"] == NO_SIGNOFF else per["signoff"]
    if (p.get("greetings") or [None])[0] == NO_GREETING:
        greet = None                # he rarely opens with a greeting: none is put in, and one the draft has is taken out
    name = _first_name(to)
    lines = str(body or "").replace("\r", "").split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip()), None)
    if greet is None:
        if first is not None and GREETING.match(lines[first]):
            lines = lines[:first] + lines[first + 1:]
            while lines and not lines[0].strip():
                lines.pop(0)
    else:
        opener = f"{greet} {name}," if name else f"{greet},"
        if first is not None and GREETING.match(lines[first]):
            lines[first] = opener
        else:
            lines = [opener, ""] + lines
    last = None
    for i in range(len(lines) - 1, max(-1, len(lines) - 6), -1):
        if SIGNOFF.match(lines[i]):
            last = i
            break
    me = (common.personal().get("first_name") or common.owner() or "").split(" ")[0]
    tail = ([sign] + ([me] if me else [])) if sign else []      # no sign-off: he signs none to this person
    if last is not None:
        lines = lines[:last] + tail
    else:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ([""] + tail) if tail else []
    return "\n".join(lines).strip()


HUMANIZE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "humanize.md")
HUMANIZE_SECONDS = 180


def _claude(prompt):
    """One Claude run for the humanize pass, with no tools: (reply text or None, why, seconds, report)."""
    import ai_steps
    import convo
    flags = ["--tools", "", "--strict-mcp-config", "--setting-sources", "",
             "--append-system-prompt", "Now you rewrite one email body. Reply with the rewritten body only, nothing else.",
             "--system-prompt-snapshot", "off"] + ai_steps.run_settings("humanize")
    return convo.run("humanize", prompt, flags, "sonnet", HUMANIZE_SECONDS)


def write(body, to, subject=""):
    """A draft in the owner's voice: humanized with the voice, then the level's greeting and sign-off. (body, how)."""
    level = level_for(to)
    p = profile()
    ch, per = style_for("email", _addr_of(to))
    how = {"level": LABEL[level], "humanized": False, "style": "person" if per else "channel" if ch else None}
    try:
        with open(HUMANIZE, encoding="utf-8") as f:
            skill = f.read()
    except OSError:
        skill = ""
    import settings_page
    if skill and str(body or "").strip() and not settings_page.at_limit():
        voice = {"level": LABEL[level], "typical_phrases": p.get("phrases") or [], "never_says": p.get("never") or [],
                 "greetings": p.get("greetings") or [], "signoffs": p.get("signoffs") or [],
                 "how_they_write_email": _style_words(ch) if ch else "", "how_they_write_to_this_person": _style_words(per) if per else ""}
        prompt = (skill + "\n\n---\nRewrite the email body below so it reads as the owner wrote it: plain, specific, no tells. Keep every "
                  "fact, name, number and date, and keep it about as long. Write it at this level of formality, in this voice (their "
                  "own typical phrases where they fit; never the phrases under never_says):\n" + json.dumps(voice) +
                  f"\n\nSubject: {subject}\n\nThe body:\n" + str(body))
        reply, why, _secs, _rep = _claude(prompt)
        if reply and reply.strip():
            body, how["humanized"] = reply.strip(), True
        else:
            how["why_not"] = why or "no reply"
    return shape(body, to, level), how


def for_page():
    p = profile()
    kinds = p.get("kinds") or {}
    said = []
    for k, w in (("close", "people you write to often"), ("known", "people you have written to before"), ("new", "people new to you")):
        if kinds.get(k):
            said.append(f"With {w}: {LABEL[kinds[k]['level']].lower()} ({kinds[k]['messages']} sent).")
    saved = common.read_json(FILE, {}) or {}
    own = saved.get("owner") or {}
    return {"level": setting(), "greetings": p.get("greetings") or [], "signoffs": p.get("signoffs") or [],
            "phrases": p.get("phrases") or [], "never": p.get("never") or [],
            "styles": own.get("styles") or style_lines(saved), "people": own.get("people") or people_lines(saved),
            "learned": (f"Learned from {p.get('messages', 0)} message{'' if p.get('messages') == 1 else 's'} you sent, last on {str(p.get('built_at') or '')[:10]}. " + " ".join(said))
            if p.get("built_at") else "Not learned yet: press Learn style now to learn it from the messages you sent."}


def learn_now():
    """The voice learned now, from what the owner sent, and saved; their own corrections stay. Returns the words to show."""
    p = build()
    n = p.get("messages") or 0
    return (f"Your writing style is learned from {n} message{'' if n == 1 else 's'} you sent and saved; drafts use it from now on."
            if n else "Nothing you sent was found to learn from yet, so the voice is not set. Try again once your sent mail has been read.")


def save_owner(vals):
    """The owner's corrections from Settings (lists replace what was learned; an empty list goes back to the learned one)."""
    saved = common.read_json(FILE, {}) or {}
    own = dict(saved.get("owner") or {})
    for k in ("greetings", "signoffs", "phrases", "never", "styles", "people"):
        if k in vals:
            if vals[k]:
                own[k] = list(vals[k])
            else:
                own.pop(k, None)
    saved["owner"] = own
    common.write_json(FILE, saved)
