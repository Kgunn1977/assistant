r"""Look in the owner's own contacts and mail before asking them for a contact detail.

The rule (approved 11/11/26): before the owner is asked for a
person's email or phone, the saved contacts and gathered mail are searched by
the name and company given. Exactly one person on file: the saved detail is
used and he is not asked. Nobody on file: he is asked. More than one: he is
asked which, and the question names each of them.

This is code, not a hint to a thinking call. Both places a question to the owner
can arise go through settle_asks(): the item writer of the timed pass
(think._commit_items, and settle_open() over every open item each pass) and
the chat, for words typed in its box or on a card (chat.handle).

The lookup reads Live\known_people.json (every named contact, their addresses
and newest message, rewritten each pass by write_people()), so it never
waits on the database.

    python people.py "What is Dana's email at Acme?"
"""
import datetime as dt
import os
import re
import sys

import common

PEOPLE = os.path.join(common.HOME, "known_people.json")
STOP = set("""the and for you your our are was not but have has had with that this from they them then than
what when where who why how can could would should will did does about into its his her him she
already just need want know said say ask asked answer email address phone number rep job use yes
one two get got out all any more there here been were their also only still some""".split())

# A question that asks the owner FOR the detail ("What is Dana's email?", "I need a phone number
# for Sam"), not one that merely uses the word ("OK to email Sam for the dates?").
ASKING = r"(?:what(?:'s| is| are)?|which|who(?:'s| is)?|give me|i need|need|do you have|have you got|can you (?:give|send|tell)|send me|tell me|share)\b[^?]*?"
WANT_EMAIL = re.compile(r"\b" + ASKING + r"(?:'s |\bhis |\bher |\btheir |\ban? |\bthe |\bfor )(?:\w+ ){0,2}?(e-?mail|contact (?:info|information|details?))\b", re.I)
WANT_PHONE = re.compile(r"\b" + ASKING + r"(?:'s |\bhis |\bher |\btheir |\ban? |\bthe |\bfor )(?:\w+ ){0,2}?(phone|cell|mobile|telephone|number)\b", re.I)
# words that are also first names; alone they do not name a person
NOT_NAMES = set("""will mark bill rich grant may art dale guy rod chip penny june april august dawn joy hope
faith rose frank chase wade lane miles case job""".split())
GENERIC = set("""inc llc company supply the group services service sales and corp
corporation systems products industries international""".split())


def generic():
    """Words in a company's name that do not tell one company from another: the general ones above plus the
    owner's own (personal "company_words": the words of their trade that half their contacts' companies carry)."""
    mine = {str(w).strip().lower() for w in (common.personal().get("company_words") or []) if str(w).strip()}
    return GENERIC | mine


def write_people():
    """Live\\known_people.json: every named contact, their addresses and their
    newest message. Written by each pass so an answer can be checked against it
    without opening the database."""
    import db
    rows = db.query(
        """SELECT c.key, c.person_id, c.name, c.company, c.notes, coalesce(c.sent_count, 0),
                  m.last_ts, m.channel, m.subject
           FROM contacts c LEFT JOIN
                (SELECT from_key, max(ts) AS last_ts, arg_max(channel, ts) AS channel,
                        arg_max(subject, ts) AS subject FROM messages GROUP BY 1) m ON m.from_key = c.key
           WHERE c.name IS NOT NULL AND trim(c.name) <> ''""")
    # a contact kept with no name is named from the mail that shows it as "Name <address>", so it can be found by name
    named = names_in_mail()
    if named:
        rows += [(key, pid, named[key.split(":", 1)[1]], company, notes, sent, last_ts, channel, subject)
                 for key, pid, _name, company, notes, sent, last_ts, channel, subject in db.query(
                     """SELECT c.key, c.person_id, c.name, c.company, c.notes, coalesce(c.sent_count, 0),
                               m.last_ts, m.channel, m.subject
                        FROM contacts c LEFT JOIN
                             (SELECT from_key, max(ts) AS last_ts, arg_max(channel, ts) AS channel,
                                     arg_max(subject, ts) AS subject FROM messages GROUP BY 1) m ON m.from_key = c.key
                        WHERE (c.name IS NULL OR trim(c.name) = '') AND starts_with(c.key, 'email:')""")
                 if key.split(":", 1)[1] in named]
    known = {str(r[0]).split(":", 1)[1] for r in db.query("SELECT key FROM contacts WHERE starts_with(key, 'email:')")}
    senders = {str(fk).split(":", 1)[1]: nm for fk, nm in db.query(
        "SELECT m.from_key, arg_max(s.from_name, m.ts) FROM messages m JOIN mail_state s ON s.message_id = m.id "
        "WHERE m.direction = 'in' AND starts_with(m.from_key, 'email:') AND coalesce(s.from_name, '') <> '' GROUP BY 1")}
    for addr, name in list(senders.items()) + list((named or {}).items()):
        if addr not in known and name and len(name.split()) >= 1:
            known.add(addr)
            rows.append(("email:" + addr, None, name, None, None, 0, None, None, None))
    # where each address was found, for every address at once: their own newest email (one read); an address that only
    # appears inside other mail is looked up when it is used (where_found), never here, for each of thousands
    own = {str(fk).split(":", 1)[1]: ts for fk, ts in db.query(
        "SELECT from_key, max(ts) FROM messages WHERE starts_with(from_key, 'email:') GROUP BY 1") if ts}
    people = {}
    for key, pid, name, company, notes, sent, last_ts, channel, subject in rows:
        p = people.setdefault(pid if pid is not None else key,
                              {"name": name, "company": None, "email": [], "phone": [], "note": None,
                               "sent": 0, "last": None})
        p["company"] = p["company"] or company
        p["note"] = p["note"] or notes
        p["sent"] += sent or 0
        kind, _, value = str(key).partition(":")
        if kind == "email" and value not in p["email"]:
            p["email"].append(value)
            if value in own:
                p.setdefault("where", {})[value] = _their_email(own[value])
        elif kind == "phone" and value not in p["phone"]:
            p["phone"].append(value)
        if last_ts and (p["last"] is None or last_ts.isoformat() > p["last"]["at"]):
            p["last"] = {"at": last_ts.isoformat(timespec="minutes"), "by": channel, "subject": (subject or "")[:90]}
    common.write_json(PEOPLE, {"written_at": common.now().isoformat(timespec="seconds"),
                               "people": list(people.values())})
    return len(people)


def _their_email(ts):
    return f"their email of {ts.month}/{ts.day}/{ts:%y}"


def where_found(addr):
    """Where one address was found, in plain words: their own email (the newest), an email that names it, or the contacts.
    For one address at the moment it is used: the second look reads every email's words."""
    import db
    got = db.query("SELECT ts FROM messages WHERE from_key = ? ORDER BY ts DESC LIMIT 1", ("email:" + addr,))
    if got and got[0][0]:
        return _their_email(got[0][0])
    got = db.query("SELECT ts, subject FROM messages WHERE channel = 'email' AND lower(body) LIKE ? ORDER BY ts DESC LIMIT 1",
                   ("%" + addr + "%",))
    if got and got[0][0]:
        return f"the email of {got[0][0].month}/{got[0][0].day}/{got[0][0]:%y}" + (f" \"{got[0][1][:60]}\"" if got[0][1] else "")
    return "your contacts"


NAMES_SEEN = os.path.join(common.paths.STATE, "names_in_mail.json")
NAMES_PER_PASS = 3000           # messages read per pass for names; newest first, then older ones on later passes
NAME_ADDR = re.compile(r"([A-Z][A-Za-z'.\-]+(?:[ \t]+[A-Z][A-Za-z'.\-]+){0,3})[ \t]*['\"]?[ \t]*<[ \t]*(?:mailto:)?([\w.+-]+@[\w-]+(?:\.[\w-]+)+)[ \t]*>")
HTML_TAG = re.compile(r"</?(?:a|span|b|i|u|p|div|font|br|strong|em|o:p|td|tr|table|img|blockquote)\b[^>]*>", re.I)


def names_in_mail():
    """{address: name} as mail headers write them ("Pat Lee <plee@example.com>"), kept in a state file and read a
    little further each pass: new mail first, then older mail. The most common name for an address wins."""
    import html
    import db
    seen = common.read_json(NAMES_SEEN, {}) or {}
    names, high, low = seen.get("names") or {}, int(seen.get("high") or 0), seen.get("low")
    try:
        new = db.query("SELECT id, body FROM messages WHERE channel = 'email' AND id > ? AND body LIKE '%@%' ORDER BY id "
                       + ("DESC" if low is None else "ASC") + " LIMIT ?", (high, NAMES_PER_PASS))
        left = NAMES_PER_PASS - len(new)
        old = db.query("SELECT id, body FROM messages WHERE channel = 'email' AND id < ? AND body LIKE '%@%' ORDER BY id DESC LIMIT ?",
                       (int(low), left)) if low is not None and left > 0 else []
    except Exception:  # noqa: BLE001  no mail read this pass: the names already found stand
        return {a: max(c, key=c.get) for a, c in names.items()}
    for mid, body in new + old:
        text = html.unescape(HTML_TAG.sub(" ", body or ""))
        for name, addr in NAME_ADDR.findall(text):
            name, addr = " ".join(name.strip("'\". ").split()), addr.lower()
            if len(name.split()) < 2 or "@" in name:
                continue
            c = names.setdefault(addr, {})
            c[name] = c.get(name, 0) + 1
    if new:
        high = max(high, max(r[0] for r in new))
        low = min(r[0] for r in new) if low is None else low
    if old:
        low = min(r[0] for r in old)
    common.write_json(NAMES_SEEN, {"high": high, "low": low, "names": names})
    return {a: max(c, key=c.get) for a, c in names.items()}


def _plain_words(text):
    return {w for w in re.findall(r"[a-z][a-z'\-]{2,}", (text or "").lower()) if w not in STOP}


def held_for(item, text, limit=5):
    """What the system already holds about the people named in his words and
    in what the card asked him. A small list, for a thinking call."""
    people = (common.read_json(PEOPLE, {}) or {}).get("people") or []
    if not people:
        return []
    said = _plain_words(text) | _plain_words(" ".join(item.get("asks") or []))
    said |= _plain_words("\n".join((item.get("assistant_did") or "").split("\n")[-4:]))
    scored = []
    for p in people:
        name = _plain_words(p.get("name"))
        company = _plain_words(p.get("company"))
        score = 2 * len(name & said) + len(company & said)
        if name & said:
            scored.append((score, p.get("sent") or 0, p))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    out = []
    for _score, _sent, p in scored[:limit]:
        last = p.get("last")
        when = ""
        if last:
            t = dt.datetime.fromisoformat(last["at"])
            when = f"{last['by']}, {t.month}/{t.day}/{t:%y} {t.strftime('%I:%M %p').lstrip('0')}" + \
                   (f", \"{last['subject']}\"" if last.get("subject") else "")
        out.append({k: v for k, v in {"name": p["name"], "company": p.get("company"),
                                      "email_on_file": p["email"][:3], "phone_on_file": p["phone"][:2],
                                      "note_on_file": (p.get("note") or "")[:160] or None,
                                      "newest_message_from_them": when or None}.items() if v})
    return out


def wanted(text):
    """'email' or 'phone' when the text asks for that detail of a person, else None."""
    if WANT_EMAIL.search(text or ""):
        return "email"
    if WANT_PHONE.search(text or ""):
        return "phone"
    return None


def _words(text):
    return {w for w in re.findall(r"[a-z][a-z'\-]{2,}", (text or "").lower().replace("'s", ""))
            if w not in STOP}


def lookup(text, need="email"):
    """The people on file that the text names and who have the detail needed.
    Narrowed by a full name when one is given, then by the company given.
    The same person held twice comes back once."""
    said = _words(text)
    at = {w.lower() for w in re.findall(r"\b(?:at|from|with|of)\s+([A-Z][\w&'\-]+)", text or "")} | \
         {w.lower() for w in re.findall(r"\b(?:at|from)\s+([a-z][\w&'\-]{3,})", text or "")} - STOP
    hits = []
    for p in (common.read_json(PEOPLE, {}) or {}).get("people") or []:
        name = _words(p.get("name")) - NOT_NAMES
        got = name & said
        if not got:
            continue
        company = _words(p.get("company")) - generic()
        if len(got) < 2 and _other_last_name(text, got, name):
            continue        # "Sam Lee" is not the Sam Reed on file
        if len(got) < 2 and at and not (company & at) and (company or not at <= said - name):
            if company:
                continue    # "Dana at Acme" is not a Dana at another company
        hits.append((p, len(got), len(name), bool(company & said)))
    if any(n >= 2 for _p, n, _all, _c in hits):                    # a full name was given
        hits = [h for h in hits if h[1] >= 2]
    # one person may be held more than once (mail, texts): bring them together first
    merged = {}
    for p, _n, _all, at_company in hits:
        m = merged.setdefault((p.get("name") or "").strip().lower(),
                              {"name": p["name"].strip(), "company": None, "email": [], "phone": [],
                               "at_company": False, "sent": 0, "last": None})
        m["company"] = m["company"] or p.get("company")
        m["at_company"] = m["at_company"] or at_company
        m["sent"] += p.get("sent") or 0
        m["email"] += [e for e in p.get("email") or [] if e not in m["email"]]
        m.setdefault("where", {}).update(p.get("where") or {})
        m["phone"] += [e for e in p.get("phone") or [] if e not in m["phone"]]
        if p.get("last") and (m["last"] is None or p["last"]["at"] > m["last"]["at"]):
            m["last"] = p["last"]
    out = list(merged.values())
    if any(m["at_company"] for m in out):                           # the company given settles it
        out = [m for m in out if m["at_company"]]
    out = [m for m in out if m[need]]
    out.sort(key=lambda m: -m["sent"])
    return out


def _other_last_name(text, got, name):
    """True when the text gives the matched first name a different last name."""
    for first in got:
        for m in re.finditer(r"\b" + re.escape(first) + r"\s+([A-Z][a-z'\-]{2,})\b", text or "", re.I):
            nxt = m.group(1)
            if nxt[0].isupper() and nxt.lower() not in name and nxt.lower() not in STOP:
                return True
    return False


def describe(p, need="email"):
    """'Dana Reed at Acme (dana.reed@example.com)'."""
    return p["name"] + (f" at {p['company']}" if p.get("company") else "") + f" ({p[need][0]})"


def settle_asks(asks, context="", lookup_cache=None):
    """Apply the rule to a list of questions meant for the owner. `context` is text
    that may name the person when the question itself does not (his own words).
    Returns (the questions that still stand, what was found on file as plain
    sentences, the people found)."""
    keep, found, used = [], [], []
    for ask in asks or []:
        need = wanted(ask)
        if not need:
            keep.append(ask)
            continue
        who = lookup(ask, need) or (lookup(context, need) if context else [])
        if len(who) == 1:
            place = (who[0].get("where") or {}).get(who[0][need][0]) or (where_found(who[0][need][0]) if need == "email" else None)
            found.append(f"{who[0]['name']}'s {need} is on file: {who[0][need][0]}" + (f" (found in {place})." if place else "."))
            used.append(dict(who[0], need=need))
        elif len(who) > 1:
            shown = [describe(p, need) for p in who[:4]]
            keep.append("I have more than one person on file by that name. Which do you mean: "
                        + ", ".join(shown[:-1]) + " or " + shown[-1] + "?")
        else:
            keep.append(ask)
    return keep, found, used


def settle_entry(entry):
    """The rule on one item as the item writer wrote it (a dict with asks,
    recommended, state). Changed in place. Returns True when it changed."""
    asks = [a for a in entry.get("asks") or [] if a]
    keep, found, _used = settle_asks(asks)
    if keep == asks:
        return False
    entry["asks"] = keep
    if found:
        entry["recommended"] = ((entry.get("recommended") or "").strip() + " " + " ".join(found)).strip()
        if not keep and entry.get("state") == "question":
            entry["state"] = "yours"
    return True


def settle_open(pass_id):
    """Every pass: the rule over the questions on every open item, wherever
    they came from. Returns how many items changed."""
    import items
    n = 0
    for it in items.rows("state <> 'done' AND asks IS NOT NULL AND asks <> '[]'"):
        e = {"asks": list(it["asks"] or []), "recommended": it.get("recommended"), "state": it["state"]}
        if not settle_entry(e):
            continue
        fields = {"asks": e["asks"], "recommended": e["recommended"]}
        if e["state"] != it["state"]:
            fields["state"] = e["state"]
        if len(e["asks"]) < len(it["asks"]):
            fields["assistant_did"] = ((it.get("assistant_did") or "") + "\n" if it.get("assistant_did") else "") + \
                "I found the contact detail on file, so I did not ask you for it."
            if it.get("status") == "Needs one more answer" and not e["asks"]:
                fields["status"] = "Contact on file"
        items.update(it["id"], pass_id, **fields)
        n += 1
    return n


def for_prompt(text):
    """What a thinking call is shown about the people named: who is on file."""
    who = lookup(text, "email")
    return {"matched": "exactly one" if len(who) == 1 else "more than one" if who else "none",
            "people": [{k: v for k, v in {"name": p["name"], "company": p.get("company"), "email": p["email"][:2],
                                          "phone": p["phone"][:2]}.items() if v} for p in who[:4]]}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    print(wanted(q), [describe(p, wanted(q) or "email") for p in lookup(q, wanted(q) or "email")])
    print(settle_asks([q]))
