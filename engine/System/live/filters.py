r"""What reaches the owner: their filter settings, their own rules in plain sentences, and the holds the
machinery itself makes before anything is read by Claude.

ITEMS.md ("Design round 2") is the contract. Everything here is general: no sender, word or kind of
mail is written in; the owner's choices live in their personal folder (settings.json "filter", and
filter_rules.json for the rules). An absent setting is its default.

    get()                 the settings in force, defaults filled in
    rules()               the owner's rules: [{"id", "text", "way", "on", "made", "from", "reason"}]; "reason" (why the rule
                          exists, one short line) is absent on a rule made before reasons were kept
    lines_for_sorting()   the settings and rules as plain sentences for the sorting step's instructions
    holds()               (message id, source) for unjudged mail the settings hold back mechanically
    gets_through(key)     True for a sender on "people who always get through"
"""
import os
import re

import common

RULES_FILE = os.path.join(common.PERSONAL, "filter_rules.json")
# id: (allowed values, the first is the default)
CHOICES = {
    "strict": ("balanced", "show_more", "needs_me"),
    "nothing_needed": ("line", "hide", "full"),
    "first_time": ("show", "ask_once", "hold"),
    "newsletters": ("never", "show"),
    "kept_mailings": ("show_each", "only_due_or_wrong"),
    "notices": ("only_failed", "show_each"),
    "copied_only": ("only_if_named", "show", "fyi"),
    "unknown_texts": ("fyi", "show", "hide"),
    "short_texts": ("hide", "show"),            # texts from a short number (6 digits or fewer): rule 560 on, or read like any text
    "show_why": ("on", "off"),
    "waiting_back_days": (3, 2, 5, 7, 0),
    "old_card_days": (14, 7, 30, 0),
}
# What a new home starts with (a new user starts with nothing hidden): written once into settings.json by setup_steps.make_home
# when the home is made. A home made before keeps what it has: an absent setting there is still the first value above.
NEW_HOME = {"strict": "show_more", "newsletters": "show", "notices": "show_each", "copied_only": "show", "short_texts": "show"}
LISTS = ("always_through",)
FIELDS = tuple(CHOICES) + LISTS + ("rules", "rules_seen")
_seen = {"ids": None}       # the rule numbers the page held when it drew its list; only those can be removed by a Save
WAYS = ("show_less", "always_show", "card_rule")      # card_rule: how cards are written, saved from his corrections
WAY_WORDS = {"show_less": "show less", "always_show": "always show", "card_rule": "how cards are written"}
RULE_MIN, RULE_MAX, RULES_MOST = 8, 300, 60
REASON_MAX = 300            # why a rule exists: optional, one short line, capped like the rule's own words


def get():
    """Every filter setting in force: the owner's saved choice where it is an allowed one, else the default."""
    saved = common.settings().get("filter")
    saved = saved if isinstance(saved, dict) else {}
    out = {k: (saved.get(k) if saved.get(k) in allowed and not isinstance(saved.get(k), bool) else allowed[0])
           for k, allowed in CHOICES.items()}
    out["always_through"] = [str(x).strip() for x in saved.get("always_through") or [] if str(x).strip()]
    return out


# --- the owner's rules ----------------------------------------------------------------------------
def rules(only_on=False):
    got = common.read_json(RULES_FILE, {}) or {}
    out = [r for r in got.get("rules") or [] if isinstance(r, dict) and r.get("text") and r.get("way") in WAYS]
    return [r for r in out if r.get("on", True)] if only_on else out


def _write_rules(rows):
    got = common.read_json(RULES_FILE, {}) or {}
    got["rules"] = rows
    got["next"] = max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in rows])
    common.write_json(RULES_FILE, got)


def next_rule_id():
    got = common.read_json(RULES_FILE, {}) or {}
    n = max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in rules()])
    got.setdefault("rules", rules())
    got["next"] = n + 1
    common.write_json(RULES_FILE, got)
    return n


def _reason(text):
    return " ".join(str(text or "").split())[:REASON_MAX]


def add_rule(text, way, source="", rid=None, reason=""):
    """One more rule, switched on, with why it exists when that is known. Returns it."""
    rows = rules()
    rule = {"id": rid or next_rule_id(), "text": " ".join(str(text).split())[:RULE_MAX], "way": way, "on": True,
            "made": common.now().isoformat(timespec="seconds"), "from": " ".join(str(source or "").split())[:120]}
    if _reason(reason):
        rule["reason"] = _reason(reason)
    _write_rules([r for r in rows if r["id"] != rule["id"]] + [rule])
    return rule


STOP = set("""a an the and or of to for from in on at by with is are be it its this that these those i me my you your
never always show hide dont do not no any all every unless only when if then about mail email emails message messages
card cards sender senders kind kinds thing things""".split())


def _words(text):
    return {w for w in re.findall(r"[a-z0-9']{3,}", str(text).lower()) if w not in STOP}


def contradictions(rows):
    """Pairs of rules that are on and plainly pull against each other: one says show less and the other
    always show about the same thing (most of the shorter one's telling words are in the other)."""
    on = [r for r in rows if r.get("on", True)]
    out = []
    for i, a in enumerate(on):
        for b in on[i + 1:]:
            if a["way"] == b["way"] or "card_rule" in (a["way"], b["way"]):
                continue
            wa, wb = _words(a["text"]), _words(b["text"])
            small = min(len(wa), len(wb))
            if small and len(wa & wb) / small >= 0.6:
                out.append((a, b))
    return out


def check_rules(value):
    """The rules list of a Save, checked: [{"id" or None, "text", "way", "on"}, and "reason" when the Save carried one (empty
    clears it; left out keeps the saved one)]. Raises ValueError with plain words."""
    if not isinstance(value, list) or len(value) > RULES_MOST:
        raise ValueError(f"Rules must be a list of at most {RULES_MOST}.")
    out = []
    for r in value:
        if not isinstance(r, dict) or set(r) - {"id", "text", "way", "on", "made", "from", "reason"}:
            raise ValueError("A rule holds its words, why it is there, show less or always show, and on or paused.")
        text = " ".join(str(r.get("text") or "").split())
        if not RULE_MIN <= len(text) <= RULE_MAX:
            raise ValueError(f"A rule is a sentence of {RULE_MIN} to {RULE_MAX} characters.")
        if r.get("way") not in WAYS or not isinstance(r.get("on", True), bool):
            raise ValueError("A rule is show less, always show or how cards are written, and either on or paused.")
        rid = r.get("id")
        if rid is not None and (isinstance(rid, bool) or not isinstance(rid, int)):
            raise ValueError("A rule's number was not understood.")
        row = {"id": rid, "text": text, "way": r["way"], "on": bool(r.get("on", True))}
        if "reason" in r:
            if r["reason"] is not None and not isinstance(r["reason"], str):
                raise ValueError("A rule's reason is a line of plain words.")
            row["reason"] = " ".join(str(r["reason"] or "").split())
            if len(row["reason"]) > REASON_MAX:
                raise ValueError(f"A rule's reason is at most {REASON_MAX} characters.")
        out.append(row)
    return out


def save_rules(clean, seen=None):
    """Write a checked rules list: an entry keeps when it was made and what it came from, a new one starts now,
    one left out is gone. When the page says which rules it had seen, a rule it never saw (approved from a card
    meanwhile) is kept. Returns the pairs that contradict."""
    old = {r["id"]: r for r in rules()}
    sent = {r["id"] for r in clean if r["id"] is not None}
    rows = [r for i, r in old.items() if seen is not None and i not in seen and i not in sent]
    for r in clean:
        was = old.get(r["id"]) if r["id"] is not None else None
        row = {"id": r["id"] if was else next_rule_id(), "text": r["text"], "way": r["way"], "on": r["on"],
               "made": (was or {}).get("made") or common.now().isoformat(timespec="seconds"),
               "from": (was or {}).get("from") or "You wrote it in Settings"}
        reason = _reason(r["reason"] if "reason" in r else (was or {}).get("reason"))      # a Save that sent none keeps it
        if reason:
            row["reason"] = reason
        rows.append(row)
    _write_rules(rows)
    return contradictions(rows)


def rules_for_page():
    return [{k: r.get(k) for k in ("id", "text", "way", "on", "made", "from", "reason")} for r in rules()]


# --- what the sorting step is told ----------------------------------------------------------------
def because(rule):
    """The end of a rule's line in a prompt: " (because: ...)" when the rule carries its reason, else nothing."""
    reason = _reason((rule or {}).get("reason"))
    return f" (because: {reason})" if reason else ""


def lines_for_sorting():
    """The owner's filter settings and rules as plain sentences, for the sorting step's instructions.
    Only what the machinery cannot settle by itself is said here."""
    f, owner = get(), common.owner()
    out = [f"Each of {owner}'s settings starts with its tag in brackets. When a setting is the reason for a verdict of noise or "
           "ignore, put its tag, without the brackets, in leaned_on exactly (for example `setting strict`)."]
    out.append("[setting strict] " + {"balanced": f"How strict: balanced. Show {owner} what asks something of them or what they would plainly want to know; "
                            "hold routine mail that needs nothing.",
                "show_more": f"How strict: show more. When in doubt whether {owner} would want to see it, show it. Anything a person "
                             f"wrote to {owner} themselves is a task, even when it says no reply is needed.",
                "needs_me": f"How strict: only what needs {owner}. Make a task only when the message asks {owner} to decide, answer or do "
                            "something, or reports a problem only they can deal with; everything else, including a message that only informs "
                            "them, is noise or ignore."}[f["strict"]])
    if f["newsletters"] == "show":
        out.append(f"[setting newsletters] Mailings: {owner} chose to have mail with an unsubscribe link read like any other mail. No junk rule about "
                   "unsubscribe links applies; judge each one on what it says.")
    if f["short_texts"] == "show":
        out.append(f"[setting short_texts] Texts from short numbers: {owner} chose to have texts from a short number (6 digits or fewer) read like any other "
                   "text. No junk rule about short numbers applies; judge each one on what it says.")
    kept = [str(w) for w in (common.personal().get("keep_words") or []) if str(w).strip()]
    if kept and f["kept_mailings"] == "show_each":
        out.append(f"[setting kept_mailings] Mailings {owner} keeps: mail with an unsubscribe link whose subject holds one of these words is NOT junk, whatever "
                   f"a junk rule says: {', '.join(kept)}. Each is a task, even when its detail says nothing is asked of {owner}.")
    if f["kept_mailings"] == "only_due_or_wrong":
        out.append(f"[setting kept_mailings] Mailings {owner} keeps (mail with an unsubscribe link whose subject holds one of: {', '.join(kept) or 'no words yet'}): a task only when something is due, "
                   "late, failed, refused, or differs from what was expected; otherwise noise.")
    if f["notices"] == "only_failed":
        out.append("[setting notices] Automated notices from apps and systems (no person wrote them): a task only when something failed, was refused, "
                   "or needs an action; a notice that all went well is noise.")
    else:
        out.append("[setting notices] Automated notices from apps and systems: each one is a task, never noise or ignore; when all went well its detail "
                   f"says nothing is asked of {owner}.")
    if f["copied_only"] == "fyi":
        out.append(f"[setting copied_only] Mail where none of {owner}'s own addresses is among the To addresses (they are only copied): never noise or ignore. "
                   f"Make it a task whose detail says nothing is asked of {owner} (it shows as information only), unless it names them "
                   "and asks something.")
    if f["unknown_texts"] == "fyi":
        out.append(f"[setting unknown_texts] A text from a number with no name in the payload's reference: never noise or ignore. Make it a task whose detail "
                   f"says nothing is asked of {owner} (it shows as information only), unless it plainly asks them something.")
    if f["always_through"]:
        out.append(f"[setting always_through] People who always get through: {'; '.join(f['always_through'])}. A message from any of them is always a task, never "
                   "noise or ignore.")
    live = rules(only_on=True)
    if live:
        out.append(f"{owner}'s own rules, in their words. Obey each one. When a rule is the reason for a verdict of noise or ignore, "
                   "start the reason with `owner rule <its number>:` exactly.")
        for r in live:
            out.append(f"  owner rule {r['id']} ({WAY_WORDS[r['way']]}): {r['text']}{because(r)}")
    return out


def lines_for_writing():
    """The owner's rules on how cards are written (saved from his corrections), as plain lines for every step that writes
    or rewrites a card: the card writer, the answer reader and the rebuild. Empty when he has none on."""
    live = [r for r in rules(only_on=True) if r["way"] == "card_rule"]
    try:            # the urgency part of a pick rule the owner promoted (work_rules.py): never mark such a card important
        import work_rules
        more = work_rules.writer_lines()
    except Exception:  # noqa: BLE001
        more = []
    if not live and not more:
        return "(none yet)"
    return "\n".join([f"- owner rule {r['id']}: {r['text']}{because(r)}" for r in live] + more)


def save_correction(text, source, reason=""):
    """A correction he gave, saved as one of his rules on how cards are written. Returns (the rule, the line to show
    him), or (None, "") when the words are not a usable rule. Kept in his own data, so updates never touch it."""
    text = " ".join(str(text or "").split())
    if not RULE_MIN <= len(text) <= RULE_MAX:
        return None, ""
    low = text.lower()
    same = next((r for r in rules() if r["way"] == "card_rule" and " ".join(r["text"].lower().split()) == low), None)
    rule = same or add_rule(text, "card_rule", source, reason=reason)
    shown = text if low.startswith("from now on") else "from now on, " + text[:1].lower() + text[1:]
    return rule, f"Saved: {shown[:1].upper() + shown[1:]} (Settings, Filters, Rules, to change or remove it.)"


# --- holds the machinery makes ---------------------------------------------------------------------
def _through_entries():
    return [e.lower() for e in get()["always_through"]]


def gets_through(from_key, name=""):
    """True when the sender is on "people who always get through": an address, a domain, or a name."""
    addr = str(from_key or "").lower().split(":", 1)[-1]
    name = " ".join(str(name or "").lower().split())
    dom = addr.rsplit("@", 1)[-1] if "@" in addr else ""
    for e in _through_entries():
        e = e.lstrip("@")
        if e == addr or (dom and "@" not in e and "." in e and (dom == e or dom.endswith("." + e))) or (name and e == name):
            return True
    return False


SOURCES = {
    "setting:first_time": "It's the first message from this sender, and your setting hides first-time senders.",
    "setting:first_time_ask": "It's the first message from this sender. A card asks you once whether to show their mail.",
    "setting:copied_only": "You were only copied on it and it doesn't name you. Your setting hides those.",
    "setting:unknown_texts": "It's a text from a number that isn't in your contacts. Your setting hides those.",
    "setting:nothing_needed": "It needs nothing from you, and your setting hides those.",
}


def holds(db, known, ids=None):
    """(message id, source) for inbound mail nothing has ruled on yet that a setting holds back before any
    reading. `known(from_key)` is the junk guard: True for the owner's contacts, people they wrote to and
    their own domains. A sender who always gets through is never held. With ids, the same test on those
    messages whatever has been ruled on them (to say what the settings WOULD hold)."""
    f = get()
    me = common.personal()
    names = [n.lower() for n in {str(me.get("owner") or ""), str(me.get("full_name") or "")} if len(n.strip()) >= 3
             and n != common.STARTER["owner"]]
    mine = {a.lower() for a in common.paths.accounts()}
    out = []
    rows = db.query(
        """SELECT m.id, m.channel, m.from_key, m.to_keys, m.subject, substr(m.body, 1, 6000),
                  (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL),
                  EXISTS (SELECT 1 FROM messages e WHERE e.from_key = m.from_key AND e.direction = 'in' AND e.id < m.id
                          AND EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = 'msg:' || e.id))
           FROM messages m WHERE m.direction = 'in' AND m.from_key IS NOT NULL AND m.from_key <> 'assistant' AND """
        + ("NOT EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key = 'msg:' || m.id)" if ids is None
           else f"m.id IN ({','.join(str(int(i)) for i in ids) or 'NULL'})"))
    for mid, channel, fk, to_keys, subject, body, name, seen_before in rows:
        if gets_through(fk, name):
            continue
        text = f"{subject or ''}\n{body or ''}".lower()
        named = any(re.search(r"\b" + re.escape(n) + r"\b", text) for n in names)
        try:                # a kind of message one of the owner's own mods brings: that mod's own rule
            import mods
            got = mods.hold({"id": mid, "channel": channel, "from_key": fk, "subject": subject or "", "text": text, "named": named})
        except Exception:  # noqa: BLE001
            got = None
        if got:
            out.append((mid, got))
            continue
        if channel == "sms":
            if f["unknown_texts"] == "hide" and not known(fk):
                out.append((mid, "setting:unknown_texts"))
            continue
        if channel != "email":
            continue
        if f["first_time"] in ("hold", "ask_once") and not seen_before and not known(fk):
            out.append((mid, "setting:first_time" if f["first_time"] == "hold" else "setting:first_time_ask"))
            continue
        if f["copied_only"] == "only_if_named" and mine and not named:
            to = str(to_keys or "").lower()
            if to.strip() and not any(a in to for a in mine):
                out.append((mid, "setting:copied_only"))
    return out


# --- a Save of the group "filter" (called by settings_page) ------------------------------------------
def check(vals):
    """Clean values for a Save of this group. Raises ValueError with the plain reason."""
    out = {}
    for k, v in vals.items():
        if k in CHOICES:
            if isinstance(v, bool) or v not in CHOICES[k]:
                raise ValueError("Choose one of the choices shown.")
            out[k] = v
        elif k == "always_through":
            if not isinstance(v, list) or any(not isinstance(x, str) for x in v) or len(v) > 200:
                raise ValueError("People who always get through must be a list of names, addresses or domains.")
            rows = list(dict.fromkeys(" ".join(x.split()) for x in v if x.strip()))
            if any(len(x) > 120 or len(x) < 3 for x in rows):
                raise ValueError("Each line of people who always get through is 3 to 120 characters.")
            out[k] = rows
        elif k == "rules":
            out[k] = check_rules(v)
        elif k == "rules_seen":
            if not isinstance(v, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in v):
                raise ValueError("The list of rules the page had seen was not understood.")
            _seen["ids"] = set(v)
    return out


def present():
    f = get()
    f["rules"] = [dict({k: r.get(k) for k in ("id", "text", "way", "on")}, reason=_reason(r.get("reason"))) for r in rules()]
    return f


def write(vals):
    """Write a checked Save. Returns extra words for the result line (a contradiction), or ''."""
    said = ""
    if "rules" in vals:
        seen, _seen["ids"] = _seen["ids"], None
        for a, b in save_rules(vals["rules"], seen)[:1]:
            said = (f" These two pull against each other: \"{a['text']}\" and \"{b['text']}\". Both are saved; change or pause one.")
    rest = {k: v for k, v in vals.items() if k != "rules"}
    if rest:
        s = common.settings()
        f = s.get("filter") if isinstance(s.get("filter"), dict) else {}
        f.update(rest)
        s["filter"] = f
        common.write_json(common.SETTINGS, s)
    return said
