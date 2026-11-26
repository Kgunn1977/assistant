r"""Settings the owner changes on their page, and what the engine reads of them.

    import settings_page
    settings_page.for_page()        the present values, for the page's Settings panel (ITEMS.md)
    settings_page.act(record)       one Save press from the page; the listener calls it through answers.py

WHAT A PAGE MAY CHANGE is the fixed list GROUPS below and nothing else. A save names one group and its
fields; any other group, any other field, or a value outside what a field takes refuses the whole save
and writes nothing. Sending email, where the page lives, its port, connections, keys and
roadmaps are not in the list and never will be: they are changed with a command typed in Claude on the owner's own computer.

Everything saved goes to the owner's personal folder, through the same functions the setup window calls
(setup_steps.py) where one exists. An absent setting behaves as it did before settings existed.
Nothing here is logged but the names of the fields saved: never a value, never the notification channel's name.
"""
import datetime as dt
import json
import os
import re
import subprocess
import time

import common
import filters
import rule_book

# Learning levels, one per kind of work (the rule book's sections): 1 he teaches on the cards, 2 the loop proposes one change
# with both scores for Promote or Reject, 3 the loop promotes on its own, at most 10 tries (levels.py, rsi_loop.py). Kept in
# settings.json under "rsi": {"levels": {section: level}}; a home with none, or a value not taken, reads 1.
LEARN = {"learn_" + s: s for s in rule_book.SECTIONS}
LEARN_LEVELS = (1, 2, 3)
LEARN_DEFAULT = 1


def _section_words(section):
    return rule_book.SECTION_WORDS.get(section, section)

GROUPS = {
    "you": ("first_name", "full_name", "about", "page_title", "page_subtitle", "areas"),
    "watch": ("important", "own_domains", "ignore_senders", "keep_words", "paused", "every_minutes", "texts_browser"),
    "calendar": ("calendars",),
    "alerts": ("on", "mail", "quiet_from", "quiet_to"),
    "page": ("theme", "look", "text_size", "order", "hidden", "titles", "open_if_filled", "feed_order", "done_days", "snooze_days", "clock", "later_offers", "group_by", "sort_by", "group_kinds", "mail_order", "mail_pictures"),
    "signin": ("days",),
    "thinking": ("model", "daily_limit", "fast_sort"),
    "filter": filters.FIELDS,       # what reaches the owner: filters.py holds the choices and the checks
    "acting": ("ladder", "offer_after", "send_cap"),            # standing approvals: standing.py holds the kinds, levels and checks
    "review": ("review_day", "review_time"),        # the weekly review: review.py
    "voice": ("level", "greetings", "signoffs", "phrases", "never", "styles", "people"),     # the owner's voice for drafts: voice.py
    "learning": tuple(LEARN),       # a learning level per section: learning_levels()
}
LATER_OFFERS = ("today", "tomorrow", "next_week", "date", "someday")
# The page's modules and the four areas they are placed in (Settings, "How the page looks"): top and bottom run the full
# width, left is the wide column, right the narrow one; on a phone they stack top, left, right, bottom. Each connected
# roadmap is its own module, "rm:<key>". The default is the page as it was before modules could be moved.
AREAS = ("top", "left", "right", "bottom")
DEFAULT_AREA = {"top": ("chat", "about"), "left": ("feed", "roadmaps"), "right": ("today",), "bottom": ("mail", "texts", "calendar")}
# the card kinds the Cards feed holds (once each a part of its own): a saved arrangement naming one places Cards there; Ready to send
# (now Drafts, in Mail) and Changes to your assistant (now Change history, in Settings) are no longer parts of the arrangement
FEED_KINDS = ("decide", "small", "tracked", "fyi", "someday", "handled", "saidso", "held")
# Card order ranks the Cards filters' kinds (Hidden is always last); an order saved as single kinds reads as their filters
FEED_GROUPS = {"needs": ("decide", "small"), "waiting": ("tracked", "someday"), "fyi": ("fyi",), "done": ("handled", "saidso")}
NOT_PARTS = ("ready", "changes")
CORE_MODULES = tuple(m for a in AREAS for m in DEFAULT_AREA[a] if m != "roadmaps")
LOOKS = ("glass", "workshop", "broadsheet",
         "dense", "expressive", "tiles", "paper", "retro", "soft", "panel", "starship", "terminal", "greenscreen", "grid", "frost",
         "monolith", "haze")   # the page's styles; page.html draws each, glass dark is the default
EVERY = (15, 30, 60)
DONE_DAYS = (3, 7, 14, 30)
SNOOZE_DAYS = (0, 1, 3, 7)
SIGNIN_DAYS = (1, 7, 30, 90)
# the models the thinking steps can be started on (ai_steps.py takes these names), in plain words
MODELS = (("haiku", "Fastest and cheapest"), ("sonnet", "Faster and cheaper"), ("opus", "Most careful, the default"))
DEFAULT_MODEL = "opus"
SETUP_ONLY = "It is changed with a command in Claude on your computer: /assistant:change, or /assistant:introduce for projects."
LIMIT_SAYS = "I've reached today's limit on AI use, so I read nothing new until midnight."

RUNS = os.path.join(common.HOME, "ai_runs.json")
LAST_GATHER = os.path.join(common.HOME, "last_gather.json")
ALERTS_HELD = os.path.join(common.HOME, "alerts_held.json")
LOG = os.path.join(common.LOGS, "settings.log")
CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
ADDRESS = re.compile(r"^[^@\s<>,;\"']+@[a-z0-9-]+(\.[a-z0-9-]+)+$")
LABEL = {"first_name": "your first name", "full_name": "your whole name", "about": "the sentence about you",
         "page_title": "the page's heading", "page_subtitle": "the line under the heading", "areas": "your areas",
         "important": "what matters", "calendars": "the calendars under Today", "own_domains": "your own mail domains",
         "ignore_senders": "senders to ignore", "keep_words": "the words that keep a mailing", "paused": "Check for new messages", "every_minutes": "Check every",
         "on": "phone notifications", "mail": "mail notifications", "quiet": "quiet hours", "theme": "light or dark", "look": "the page's style", "text_size": "text size",
         "mail_order": "the order of mailboxes", "order": "the order of sections", "hidden": "which sections show", "titles": "the names of sections", "open_if_filled": "which sections open only when they hold something", "done_days": "how long Done cards stay",
         "snooze_days": "the default snooze date", "feed_order": "Card order", "texts_browser": "what the texts link does when Messages is opened in a browser", "clock": "12 or 24 hour times", "mail_pictures": "pictures from the internet in emails", "days": "how long a sign-in lasts",
         "model": "the AI model", "daily_limit": "the daily limit on AI use",
         "later_offers": "snooze options", "fast_sort": "the fast first look for plain junk",
         "strict": "how strict the filter is", "nothing_needed": "things that need nothing", "first_time": "first-time senders",
         "newsletters": "newsletters and promotions", "kept_mailings": "mailings kept by a word", "notices": "automated notices",
         "always_through": "priority senders", "copied_only": "mail you are only copied on",
         "unknown_texts": "texts from numbers not in your contacts", "short_texts": "texts from short numbers", "show_why": "the Here because line",
         "waiting_back_days": "when a waiting card comes back", "old_card_days": "when old cards are asked about",
         "rules": "your rules", "group_by": "how cards are grouped", "sort_by": "the order of cards", "group_kinds": "grouping cards by kind",
         "ladder": "what I do without asking", "offer_after": "when I offer to do something without asking", "send_cap": "the daily limit on replies I send without asking",
         "review_day": "the day of your weekly review", "review_time": "the time of your weekly review",
         "level": "Tone", "greetings": "Greetings", "signoffs": "Sign-offs", "phrases": "Common phrases", "never": "Phrases to avoid",
         "styles": "How you write on each channel", "people": "How you write to certain people",
         **{f: "the learning level for " + rule_book.SECTION_WORDS[s].lower() for f, s in LEARN.items()}}


_said = {}      # extra words a save wants on its result line (two rules that pull against each other)


class Refused(Exception):
    """A save that is not allowed. The message is the plain reason."""


EMAIL_LIKE = re.compile(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", re.I)
PHONE_LIKE = re.compile(r"(?:\+?\d[\s().-]*){7,}")
STREET_LIKE = re.compile(r"^\s*\d+\s+\w.*\b(st|street|ave|avenue|rd|road|dr|drive|ln|lane|blvd|boulevard|way|ct|court|pl|place|hwy|highway)\b\.?", re.I)


def _personal_title(text):
    """True for a section name that is the owner's own name (whole, or a part of it), an email address, a phone number or a
    street address: what a browser fills into a box by itself, never a name someone picks for a part of their page."""
    t = str(text or "").strip()
    if not t:
        return False
    if EMAIL_LIKE.search(t) or PHONE_LIKE.search(t) or STREET_LIKE.search(t):
        return True
    p = common.personal()
    whole = [str(p.get(k) or "") for k in ("owner", "name", "first_name", "last_name", "full_name", "nickname")]
    parts = {w.lower() for n in whole for w in re.findall(r"[A-Za-z][A-Za-z'.-]+", n) if len(w) > 1}
    return t.lower() in parts or t.lower() in {n.strip().lower() for n in whole if n.strip()}


# --- what the engine reads ----------------------------------------------------------------------
def _projects():
    import projects
    return projects


def _standing():
    import standing
    return standing


def _voice():
    import voice
    return voice


def _review():
    import review
    return review


def _ordermod():
    import order
    return order


def _s():
    """The settings file as it is; never made here, so reading a setting changes nothing."""
    got = common.read_json(common.SETTINGS, {})
    return got if isinstance(got, dict) else {}


def _part(name):
    got = _s().get(name)
    return got if isinstance(got, dict) else {}


def mail_order():
    """The owner's order of mailboxes (Mail page: dragged in the left column): lower-case addresses, first to last."""
    got = _part("page").get("mail_order")
    return [str(x).lower() for x in got if isinstance(x, str)] if isinstance(got, list) else []


def mail_ordered(items, key=lambda x: x):
    """items sorted by the saved mailbox order; a mailbox not named there goes after those that are, in its own order."""
    order = mail_order()
    at = {a: i for i, a in enumerate(order)}
    return sorted(items, key=lambda x: at.get(str(key(x)).lower(), len(order)))


_JOB = {"at": 0.0, "off": None}
JOB_SECONDS = 20                # the scheduled pass's state is asked again after this long


def pass_job_off():
    """Whether this home's scheduled pass (the job that gathers every 15 minutes) is switched off: True or False, or None when
    there is no such job here or it cannot be asked. It is the real switch of gathering."""
    if os.name != "nt":
        return None
    if time.time() - _JOB["at"] < JOB_SECONDS:
        return _JOB["off"]
    import paths
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", paths.job_names()[0], "/FO", "LIST"], capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        off = ("disabled" in (r.stdout or "").lower()) if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        off = None
    _JOB.update(at=time.time(), off=off)
    return off


def switch_pass(on):
    """Gathering on or off for real: the scheduled pass switched on or off. "" when done (or there is no such job here, as on a
    home with no jobs), else the plain reason."""
    if pass_job_off() is None:
        return ""
    import paths
    try:
        r = subprocess.run(["schtasks", "/Change", "/TN", paths.job_names()[0], "/ENABLE" if on else "/DISABLE"], capture_output=True,
                           text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    _JOB["at"] = 0.0
    return "" if ok else ("I couldn't switch the regular check on your computer " + ("on" if on else "off") + ", so "
                          + ("I still don't check for new messages" if on else "I may still check for new messages") + ". Try again, or restart the computer and try again.")


def paused_flag():
    """Paused by the owner's own choice on the page (a pass run by hand stands down only for this)."""
    return bool(_part("gathering").get("paused"))


def paused():
    """Gathering is paused: by his choice on the page, or because the scheduled pass is switched off (what really runs)."""
    return paused_flag() or bool(pass_job_off())


def paused_since():
    return _part("gathering").get("paused_at") if paused() else None


def texts_browser():
    """What the texts link does when Google Messages is opened in a browser and takes the active session: "take_back" (at once,
    the default) or "let_browser" (it waits, and the 15-minute check takes the session back)."""
    t = _s().get("texts")
    return "let_browser" if isinstance(t, dict) and t.get("browser") == "let_browser" else "take_back"


def every_minutes():
    got = _part("gathering").get("every_minutes")
    return got if got in EVERY else 15


def gathered_now():
    common.write_json(LAST_GATHER, {"at": common.now().isoformat(timespec="seconds")})


def gather_due():
    """False when the owner chose a longer gap between gatherings and the last one is too recent.
    The job still starts every 15 minutes; two and a half minutes of leeway cover a late start."""
    every = every_minutes()
    if every <= 15:
        return True
    try:
        last = dt.datetime.fromisoformat(str((common.read_json(LAST_GATHER, {}) or {}).get("at")))
    except (ValueError, TypeError):
        return True
    return (common.now() - last).total_seconds() >= every * 60 - 150


def quiet_hours():
    """(from, to) as "HH:MM" when the owner set quiet hours for phone notifications, else None."""
    q = _part("alerts").get("quiet")
    q = q if isinstance(q, dict) else {}
    a, b = str(q.get("from") or ""), str(q.get("to") or "")
    return (a, b) if CLOCK.match(a) and CLOCK.match(b) and a != b else None


def in_quiet(now=None):
    q = quiet_hours()
    if not q:
        return False
    t = (now or common.now()).strftime("%H:%M")
    return q[0] <= t < q[1] if q[0] < q[1] else (t >= q[0] or t < q[1])       # hours that cross midnight


def done_days():
    got = _part("page").get("done_days")
    return got if got in DONE_DAYS else 7


def learning_levels():
    """{section: learning level} for every section of the rule book: the saved level where it is 1, 2 or 3, else 1 (a home
    with none, or a value not understood)."""
    got = _part("rsi").get("levels")
    got = got if isinstance(got, dict) else {}
    return {s: got[s] if got.get(s) in LEARN_LEVELS and not isinstance(got.get(s), bool) else LEARN_DEFAULT
            for s in rule_book.SECTIONS}


def think_model():
    got = _part("thinking").get("model")
    return got if got in dict(MODELS) else DEFAULT_MODEL


def daily_limit():
    got = _part("thinking").get("daily_limit")
    return got if isinstance(got, int) and not isinstance(got, bool) and got > 0 else 0


def runs_today():
    got = common.read_json(RUNS, {}) or {}
    return int(got.get("runs") or 0) if got.get("day") == common.now().date().isoformat() else 0


def count_run():
    """One more Claude run started today. Called by everything that starts one. Never raises."""
    try:
        common.write_json(RUNS, {"day": common.now().date().isoformat(), "runs": runs_today() + 1})
    except OSError:
        pass


def at_limit():
    limit = daily_limit()
    return bool(limit) and runs_today() >= limit


def ignored():
    return [str(x).strip().lower() for x in (common.personal().get("ignore_senders") or []) if str(x).strip()]


def is_ignored(address, entries=None, own=None):
    """True when mail from this address is on the owner's ignore list. Their own domains never are."""
    address = str(address or "").strip().lower().split(":", 1)[-1]
    if "@" not in address:
        return False
    domain = address.rsplit("@", 1)[-1]
    own = common.paths.own_domains() if own is None else own
    if any(domain == d or domain.endswith("." + d) for d in own):
        return False
    for e in ignored() if entries is None else entries:
        if e == address or ("@" not in e and (domain == e or domain.endswith("." + e))):
            return True
    return False


# --- what the page shows ------------------------------------------------------------------------
def KIND_WORDS():
    return {k: v["title"] for k, v in common.channels().items()}


def _roadmap_modules():
    """"rm:<key>" for every connected roadmap, in the order they were connected."""
    try:
        import hashlib
        import sys
        live_page = os.path.join(common.paths.SYSTEM, "live_page")
        if live_page not in sys.path:
            sys.path.insert(0, live_page)
        import roadmaps
        return ["rm:" + hashlib.sha1(os.path.normcase(f).encode("utf-8")).hexdigest()[:10] for f in roadmaps.applied()]
    except Exception:  # noqa: BLE001  no roadmap part: nothing to place
        return []


def _mod_modules():
    try:
        import mods
        return [p["id"] for p in mods.page_parts() if p["id"] not in CORE_MODULES]
    except Exception:  # noqa: BLE001  no mod part: nothing to place
        return []


def modules():
    return list(CORE_MODULES) + _mod_modules() + _roadmap_modules()


def _order(saved, known=None):
    """The arrangement in force: {"top", "left", "right", "bottom": [module, ...]}, every known module placed once.
    A saved arrangement of the older shape ({"main", "side"}) is read as left and right. A module the saved one does not
    name (a roadmap just connected, a section new in an update) goes where the default puts it, at the end."""
    saved = saved if isinstance(saved, dict) else {}
    if "main" in saved or "side" in saved:
        saved = {"top": ["ready", "chat"], "left": saved.get("main") or [], "right": saved.get("side") or [], "bottom": []}
    known = list(known if known is not None else modules())
    out, placed = {}, set()
    for a in AREAS:
        out[a] = []
        for x in saved.get(a) or []:
            x = str(x)
            x = "feed" if x in FEED_KINDS else x
            if x in NOT_PARTS:
                continue
            if x == "roadmaps":             # the old single roadmaps section: its roadmaps, where it was
                got = [m for m in known if m.startswith("rm:") and m not in placed]
            else:
                got = [x] if x in known and x not in placed else []
            out[a] += got
            placed |= set(got)
    for a in AREAS:
        for i, x in enumerate(DEFAULT_AREA[a]):
            got = [m for m in known if m.startswith("rm:")] if x == "roadmaps" else [x]
            # a part the saved one does not name goes before the next default part placed there, else at the end
            later = [out[a].index(y) for y in DEFAULT_AREA[a][i + 1:] if y in out[a]]
            for m in got:
                if m in known and m not in placed:
                    if later and x != "roadmaps":
                        out[a].insert(later[0], m)
                    else:
                        out[a].append(m)
                    placed.add(m)
    for m in known:          # a part a mod brings, not placed yet: at the bottom, before Hidden
        if m not in placed and not m.startswith("rm:"):
            b = out["bottom"]
            b.insert(b.index("held") if "held" in b else len(b), m)
            placed.add(m)
    return out


def feed_order():
    """The order the card kinds show in the Cards feed (Hidden today always last, so not in it)."""
    got = []
    for x in list(_part("page").get("feed_order") or []) + list(FEED_GROUPS):
        g = x if x in FEED_GROUPS else next((k for k, kinds in FEED_GROUPS.items() if x in kinds), None)
        if g and g not in got:
            got.append(g)
    return got


def _accounts():
    health = (common.read_json(common.HEALTH_JSON, {}) or {}).get("sources") or {}
    listed = (common.read_json(common.paths.CONNECTIONS_JSON, {}) or {}).get("connections") or []
    out = []
    for c in listed:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        kind, address = str(c.get("kind") or ""), str(c.get("address") or "")
        name = str(c.get("label") or address or c["id"])
        if not c.get("on", True):
            out.append({"name": name, "health": "Switched off"})
            continue
        src = health.get(f"{kind}:{address}".lower()) or health.get(f"{kind}:{address}") or health.get(kind)
        if not isinstance(src, dict):
            said = "Not read yet"
        elif src.get("status") == "ok":
            said = "Working"
        else:
            said = "Needs a look: " + str(src.get("detail") or src.get("status") or "")[:160]
        out.append({"name": (KIND_WORDS().get(kind, kind.capitalize()) + ": " if kind else "") + name, "health": said})
    return out


def _version():
    r"""The version laid down here (personal\install.json "version"), or "" when it cannot be read."""
    try:
        v = (common.read_json(os.path.join(common.PERSONAL, "install.json"), {}) or {}).get("version")
        return str(v).strip() if isinstance(v, (str, int, float)) and str(v).strip() else ""
    except Exception:
        return ""


def for_page():
    """The present value of every setting, in the shape ITEMS.md gives. Reads plain files only."""
    me, s = common.personal(), _s()
    alerts, page = _part("alerts"), _part("page")
    quiet = quiet_hours() or ("", "")
    today = common.read_json(os.path.join(common.HOME, "today.json"), {}) or {}
    shown = [str(c).strip() for c in (me.get("today_calendars") or []) if str(c).strip()]
    known = list(dict.fromkeys([str(c) for c in (today.get("calendars") or []) if str(c).strip()] + shown))
    lives = s.get("page_hosting") if s.get("page_hosting") in ("own_pc", "hosted", "both") else "own_pc"
    where = []
    reach = s.get("page_reach") if isinstance(s.get("page_reach"), dict) else {}
    public = str(reach.get("address") or "") if reach.get("how") == "tailscale" and lives in ("own_pc", "both") else ""
    if lives in ("own_pc", "both"):
        where.append(f"this computer (http://127.0.0.1:{s.get('page_port') or 47815})")
        if public:
            where.append(f"from anywhere at {public}")
    if lives in ("hosted", "both"):
        site = str((common.read_json(common.PAGE_KEY, {}) or {}).get("site") or "")
        where.append("your own website" + (f" ({site})" if site else ""))
    limit = daily_limit()
    return {
        "version": _version(),
        "you": {"first_name": "" if me.get("owner") == common.STARTER["owner"] else str(me.get("owner") or ""),
                "full_name": str(me.get("full_name") or ""), "about": str(me.get("about") or ""),
                "page_title": str(me.get("page_title") or ""), "page_subtitle": str(me.get("page_subtitle") or ""),
                "areas": [str(a) for a in (me.get("areas") or [])]},
        "calendar": {"calendars": [{"name": c, "on": c in shown} for c in known]},
        "watch": {"important": common.important_lines(),
                  "own_domains": [str(d) for d in (me.get("own_domains") or [])], "ignore_senders": ignored(),
                  "keep_words": [str(k) for k in (me.get("keep_words") or []) if str(k).strip()],
                  "paused": paused(), "paused_since": paused_since(), "every_minutes": every_minutes(), "texts_browser": texts_browser()},
        "alerts": {"on": bool(str(alerts.get("topic") or "").strip()), "topic": str(alerts.get("topic") or "").strip(),
                   "server": str(alerts.get("server") or "").strip(),
                   "mail": alerts.get("mail") if alerts.get("mail") in ("matters", "every", "none") else "matters", "quiet_from": quiet[0], "quiet_to": quiet[1]},
        "page": {"theme": page.get("theme") if page.get("theme") in ("auto", "light", "dark") and (page.get("look") in LOOKS or not page.get("look")) else "dark",
                 "look": page.get("look") if page.get("look") in LOOKS else "glass",
                 "text_size": page.get("text_size") if page.get("text_size") in ("small", "normal", "large") else "normal",
                 "order": _order(page.get("order")),
                 "feed_order": feed_order(),
                 "hidden": [x for x in (page.get("hidden") or []) if x in modules()],
                 "titles": {k: v.strip() for k, v in (page.get("titles") or {}).items()
                            if isinstance(page.get("titles"), dict) and k in modules() and isinstance(v, str) and v.strip()},
                 "open_if_filled": [x for x in (page.get("open_if_filled") if isinstance(page.get("open_if_filled"), list) else ["about"]) if x in modules()],
                 "mail_order": mail_order(),
                 "done_days": done_days(),
                 "snooze_days": page.get("snooze_days") if page.get("snooze_days") in SNOOZE_DAYS else 0,
                 "clock": "24" if str(page.get("clock")) == "24" else "12",
                 "mail_pictures": "hide" if page.get("mail_pictures") == "hide" else "show",      # shown unless he chose Hide
                 "later_offers": [x for x in LATER_OFFERS if x in page["later_offers"]] if isinstance(page.get("later_offers"), list)
                 and page.get("later_offers") else list(LATER_OFFERS),
                 "group_by": _ordermod().settings()[0], "sort_by": _ordermod().settings()[1],
                 "group_kinds": page.get("group_kinds") is not False},        # the bar at the top of Cards: on unless he turned it off
        "filter": dict(filters.get(), rules=filters.rules_for_page()),
        "acting": {"ladder": _standing().for_page(), "offer_after": _standing().offer_after(), "send_cap": _standing().send_cap()},
        "review": dict(zip(("day", "time"), _review().settings())),
        "learning": {f: learning_levels()[s] for f, s in LEARN.items()},
        "voice": _voice().for_page(),
        "signin": {"days": s.get("signin_days") if s.get("signin_days") in SIGNIN_DAYS else 90},
        "thinking": {"model": think_model(), "models": [{"id": m, "words": w} for m, w in MODELS],
                     "daily_limit": limit, "runs_today": runs_today(), "limit_reached": at_limit(),
                     "fast_sort": "on" if _part("thinking").get("fast_sort") == "on" else "off"},
        "pc_only": {"roadmaps": [os.path.basename(str(e.get("folder") or "").rstrip("\\/")) for e in (s.get("roadmaps") or [])
                                 if isinstance(e, dict) and e.get("folder")],
                    "accounts": _accounts(), "projects": _projects().names(), "sending": bool(_part("owner_send").get("on")),
                    "lives": (" and ".join(where))[:1].upper() + (" and ".join(where))[1:], **({"public_address": public} if public else {})},
    }


# --- one Save press -----------------------------------------------------------------------------
def _why(key):
    """The plain reason a field is not taken."""
    k = str(key).lower()
    if "send" in k:
        return "Sending email is not switched on or off from a page. " + SETUP_ONLY
    if "roadmap" in k:
        return "Roadmaps are not applied or taken off from a page. " + SETUP_ONLY
    if any(w in k for w in ("host", "port", "site", "lives", "address", "reach")):
        return "Where your page lives is not changed from a page. " + SETUP_ONLY
    if any(w in k for w in ("connect", "account", "key", "token", "secret", "password", "source", "topic", "server")):
        return "Accounts, sign-ins and keys are not changed from a page. " + SETUP_ONLY
    return f"\"{str(key)[:40]}\" is not a setting this page can change."


def _text(v, most, name, need=False):
    if not isinstance(v, str):
        raise Refused(f"{LABEL[name].capitalize()} must be words.")
    v = " ".join(v.split()) if name != "about" else v.strip()
    if len(v) > most:
        raise Refused(f"{LABEL[name].capitalize()} is too long ({most} characters at most).")
    if need and not v:
        raise Refused("A first name is needed.")
    return v


def _lines(v, name, most=60, each=300):
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        raise Refused(f"{LABEL[name].capitalize()} must be a list of lines.")
    out = list(dict.fromkeys(" ".join(x.split()) for x in v if x.strip()))
    if len(out) > most or any(len(x) > each for x in out):
        raise Refused(f"{LABEL[name].capitalize()}: too many lines, or a line that is too long.")
    return out


def _one_of(v, allowed, name):
    if isinstance(v, bool) or v not in allowed:
        raise Refused(f"{LABEL[name].capitalize()}: choose one of " + ", ".join(str(a) for a in allowed) + ".")
    return v


def check(body):
    """(group, clean values) for a save that is allowed; raises Refused with the plain reason otherwise.
    Writes nothing."""
    if not isinstance(body, dict) or "settings" not in body:
        raise Refused("That was not a settings save.")
    for k in body:
        if k != "settings":
            raise Refused(_why(k))
    st = body["settings"]
    if not isinstance(st, dict):
        raise Refused("That was not a settings save.")
    for k in st:
        if k not in ("group", "values"):
            raise Refused(_why(k))
    group, vals = st.get("group"), st.get("values")
    if not isinstance(group, str) or group not in GROUPS:
        raise Refused(_why(group))
    if not isinstance(vals, dict) or not vals:
        raise Refused("There was nothing to save.")
    for k in vals:
        if k not in GROUPS[group]:
            raise Refused(_why(k))
    v, out = vals, {}
    if group == "you":
        for name, most in (("first_name", 60), ("full_name", 120), ("about", 1000), ("page_title", 80), ("page_subtitle", 120)):
            if name in v:
                out[name] = _text(v[name], most, name, need=name == "first_name")
        if "areas" in v:
            out["areas"] = _lines(v["areas"], "areas", most=20, each=40)
    elif group == "calendar":
        now = for_page()["calendar"]["calendars"]
        names = _lines(v["calendars"], "calendars", most=200)
        strange = [n for n in names if n not in [c["name"] for c in now]]
        if strange:
            raise Refused(f"\"{strange[0][:60]}\" is not a calendar I know.")
        out["calendars"] = names
    elif group == "watch":
        if "important" in v:
            out["important"] = _lines(v["important"], "important")
        own = None
        if "own_domains" in v:
            own = [d.lower().lstrip("@") for d in _lines(v["own_domains"], "own_domains", most=30, each=120)]
            bad = [d for d in own if not DOMAIN.match(d)]
            if bad:
                raise Refused(f"\"{bad[0][:60]}\" is not a mail domain. Write it like example.com.")
            out["own_domains"] = own
        if "keep_words" in v:
            words = [k.lower() for k in _lines(v["keep_words"], "keep_words", most=100, each=40)]
            if any(len(k) < 3 for k in words):
                raise Refused("A word that keeps a mailing needs 3 letters or more.")
            out["keep_words"] = words
        if "ignore_senders" in v:
            entries = [e.lower().lstrip("@") for e in _lines(v["ignore_senders"], "ignore_senders", most=300, each=200)]
            bad = [e for e in entries if not (ADDRESS.match(e) or DOMAIN.match(e))]
            if bad:
                raise Refused(f"\"{bad[0][:60]}\" is not an address or a domain. Write it like sam@example.com or example.com.")
            mine = tuple(dict.fromkeys((own or []) + list(common.paths.own_domains())))
            for e in entries:
                d = e.rsplit("@", 1)[-1]
                if any(d == m or d.endswith("." + m) for m in mine):
                    raise Refused(f"{e} is one of your own mail domains, and those are never ignored.")
            out["ignore_senders"] = entries
        if "texts_browser" in v:
            out["texts_browser"] = _one_of(v["texts_browser"], ("take_back", "let_browser"), "texts_browser")
        if "paused" in v:
            if not isinstance(v["paused"], bool):
                raise Refused("Check for new messages: choose On or Off.")
            out["paused"] = v["paused"]
        if "every_minutes" in v:
            out["every_minutes"] = _one_of(v["every_minutes"], EVERY, "every_minutes")
    elif group == "alerts":
        if "on" in v:
            if not isinstance(v["on"], bool):
                raise Refused("Phone notifications: choose On or Off.")
            out["on"] = v["on"]
        if "mail" in v:
            out["mail"] = _one_of(v["mail"], ("matters", "every", "none"), "mail")
        if ("quiet_from" in v) != ("quiet_to" in v):
            raise Refused("Quiet hours need both a from time and a to time.")
        if "quiet_from" in v:
            a, b = v["quiet_from"], v["quiet_to"]
            if not isinstance(a, str) or not isinstance(b, str) or bool(a) != bool(b):
                raise Refused("Quiet hours need both a from time and a to time, or neither.")
            if a and (not CLOCK.match(a) or not CLOCK.match(b) or a == b):
                raise Refused("Quiet hours need two different times.")
            out["quiet"] = (a, b)
    elif group == "page":
        if "theme" in v:
            out["theme"] = _one_of(v["theme"], ("auto", "light", "dark"), "theme")
        if "look" in v:
            out["look"] = _one_of(v["look"], LOOKS, "look")
        if "text_size" in v:
            out["text_size"] = _one_of(v["text_size"], ("small", "normal", "large"), "text_size")
        if "feed_order" in v:
            fo = v["feed_order"]
            if not isinstance(fo, list) or any(x not in FEED_GROUPS for x in fo) or len(fo) != len(set(fo)):
                raise Refused("Card order: Needs you, Waiting, FYI and Done, each once.")
            out["feed_order"] = [str(x) for x in fo]
        if "order" in v:
            o = v["order"]
            known = modules()
            names = [str(x) for a in AREAS for x in (o.get(a) or [])] if isinstance(o, dict) else []
            if not isinstance(o, dict) or set(o) - set(AREAS) or any(not isinstance(o.get(a, []), list) for a in AREAS) \
                    or len(names) != len(set(names)) or any(x not in known for x in names):
                raise Refused("Each part of the page goes in one place: top, left, right or bottom.")
            out["order"] = _order({a: list(o.get(a) or []) for a in AREAS}, known)
        if "hidden" in v:
            if not isinstance(v["hidden"], list) or any(x not in modules() for x in v["hidden"]):
                raise Refused("Which sections show: that is not a section of the page.")
            out["hidden"] = list(dict.fromkeys(v["hidden"]))
        if "titles" in v:
            t = v["titles"]
            if not isinstance(t, dict) or any(k not in modules() or not isinstance(x, str) for k, x in t.items()):
                raise Refused("A section's name goes with one of the page's sections.")
            if any(len(x.strip()) > 60 or re.search(r"[<>]", x) for x in t.values()):
                raise Refused("A section's name is up to 60 letters, with no < or >.")
            # a name typed in this save that is the owner's own name, an address or a phone number (a browser filling the box by
            # itself) is not taken: that section keeps the name it had, and the rest of the save goes through; a name already
            # stored and not changed now is never a reason to refuse anything
            had = _part("page").get("titles") if isinstance(_part("page").get("titles"), dict) else {}
            new_bad = [k for k, x in t.items() if x.strip() != str(had.get(k) or "").strip() and _personal_title(x)]
            if new_bad:
                t = dict(t, **{k: str(had.get(k) or "") for k in new_bad})
                _said["titles"] = (" A section's name was left as it was: it can't be your own name, an address or a phone number "
                                   "(usually the browser filling in the box by itself).")
            out["titles"] = {k: x.strip() for k, x in t.items() if x.strip()}
        if "open_if_filled" in v:
            if not isinstance(v["open_if_filled"], list) or any(x not in modules() for x in v["open_if_filled"]):
                raise Refused("Which sections open only when they hold something: that is not a section of the page.")
            out["open_if_filled"] = list(dict.fromkeys(v["open_if_filled"]))
        if "done_days" in v:
            out["done_days"] = _one_of(v["done_days"], DONE_DAYS, "done_days")
        if "snooze_days" in v:
            out["snooze_days"] = _one_of(v["snooze_days"], SNOOZE_DAYS, "snooze_days")
        if "clock" in v:
            out["clock"] = _one_of(v["clock"], ("12", "24"), "clock")
        if "mail_pictures" in v:
            out["mail_pictures"] = _one_of(v["mail_pictures"], ("show", "hide"), "mail_pictures")
    elif group == "signin":
        out["days"] = _one_of(v.get("days"), SIGNIN_DAYS, "days")
    elif group == "thinking":
        if "model" in v:
            out["model"] = _one_of(v["model"], tuple(m for m, _ in MODELS), "model")
        if "daily_limit" in v:
            n = v["daily_limit"]
            if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 10000:
                raise Refused("The daily limit must be a whole number from 0 to 10000. 0 means no limit.")
            out["daily_limit"] = n
        if "fast_sort" in v:
            out["fast_sort"] = _one_of(v["fast_sort"], ("off", "on"), "fast_sort")
    elif group == "filter":
        try:
            out = filters.check(v)
        except ValueError as e:
            raise Refused(str(e))
    elif group == "acting":
        if "ladder" in v:
            try:
                import standing
                out["ladder"] = standing.check_ladder(v["ladder"])
            except ValueError as e:
                raise Refused(str(e))
        if "offer_after" in v:
            out["offer_after"] = _one_of(v["offer_after"], (5, 3, 10, 0), "offer_after")
        if "send_cap" in v:
            out["send_cap"] = _one_of(v["send_cap"], (3, 1, 5, 10), "send_cap")
    elif group == "review":
        if "review_day" in v:
            out["review_day"] = _one_of(v["review_day"], ("off", "mon", "tue", "wed", "thu", "fri", "sat", "sun"), "review_day")
        if "review_time" in v:
            if not isinstance(v["review_time"], str) or not CLOCK.match(v["review_time"]):
                raise Refused("The time of your weekly review is a time like 15:00.")
            out["review_time"] = v["review_time"]
    if group == "voice":
        if "level" in v:
            out["level"] = _one_of(v["level"], ("choose", "casual", "everyday", "formal"), "level")
        for name in ("greetings", "signoffs", "phrases", "never"):
            if name in v:
                out[name] = _lines(v[name], name, most=12, each=120)
        for name in ("styles", "people"):
            if name in v:
                out[name] = _lines(v[name], name, most=80, each=300)
    if group == "learning":
        for name in v:
            out[name] = _one_of(v[name], LEARN_LEVELS, name)
    if group == "page" and "group_by" in v:
        out["group_by"] = _one_of(v["group_by"], ("nothing", "sender", "area", "conversation"), "group_by")
    if group == "page" and "sort_by" in v:
        out["sort_by"] = _one_of(v["sort_by"], _ordermod().SORT_BY, "sort_by")
    if group == "page" and "group_kinds" in v:
        if not isinstance(v["group_kinds"], bool):
            raise Refused("Group by kind: choose On or Off.")
        out["group_kinds"] = v["group_kinds"]
    if group == "page" and "mail_order" in v:
        mo = v["mail_order"]
        if not isinstance(mo, list) or len(mo) > 50 or any(not isinstance(x, str) or not ADDRESS.match(x.strip().lower()) for x in mo):
            raise Refused("The order of mailboxes is a list of mail addresses.")
        out["mail_order"] = list(dict.fromkeys(x.strip().lower() for x in mo))
    if group == "page" and "later_offers" in v:
        lo = v["later_offers"]
        if not isinstance(lo, list) or not lo or any(x not in LATER_OFFERS for x in lo):
            raise Refused("Snooze must offer at least one of its choices.")
        out["later_offers"] = [x for x in LATER_OFFERS if x in lo]
    return group, out


def _present(group):
    """The present values of a group, in the same shape a save carries, to tell what a save changed."""
    now = for_page()
    g = dict(now[group])
    if group == "calendar":
        g = {"calendars": [c["name"] for c in g["calendars"] if c["on"]]}
    if group == "alerts":
        g["quiet"] = (g.pop("quiet_from"), g.pop("quiet_to"))
    if group == "filter":
        g = filters.present()
    if group == "acting":
        g["ladder"] = [{k: e.get(k) for k in ("id", "kind", "area", "level", "on")} for e in g["ladder"]]
    if group == "review":
        g = {"review_day": g["day"], "review_time": g["time"]}
    if group == "voice":
        g = {k: g.get(k) for k in GROUPS["voice"]}
    return g


def _write(group, vals):
    """Write an allowed save. Only the owner's personal folder is touched."""
    import setup_steps
    if group == "filter":
        _said["more"] = filters.write(vals)
        return
    if group == "acting":
        if "ladder" in vals:
            import standing
            _said["more"] = " " + standing.save_ladder(vals["ladder"]) + "." if vals["ladder"] or True else ""
            standing.write_feed()
        if "offer_after" in vals or "send_cap" in vals:
            s = common.settings()
            a = s.get("acting") if isinstance(s.get("acting"), dict) else {}
            for k in ("offer_after", "send_cap"):
                if k in vals:
                    a[k] = vals[k]
            s["acting"] = a
            common.write_json(common.SETTINGS, s)
        return
    if group == "voice":
        if "level" in vals:
            s = common.settings()
            s["voice"] = dict(s.get("voice") if isinstance(s.get("voice"), dict) else {}, level=vals["level"])
            common.write_json(common.SETTINGS, s)
        _voice().save_owner(vals)
        return
    if group == "learning":         # under "rsi", beside the grader's own cap (rsi.daily_runs), which is kept as it is
        import levels               # what each new level does on its own, said back as it takes effect
        _said["more"] = " ".join(f"{_section_words(LEARN[f])}: {levels.says(LEARN[f], n)}" for f, n in vals.items())
        s = common.settings()
        r = s.get("rsi") if isinstance(s.get("rsi"), dict) else {}
        lv = r.get("levels") if isinstance(r.get("levels"), dict) else {}
        lv.update({LEARN[f]: n for f, n in vals.items()})
        r["levels"] = lv
        s["rsi"] = r
        common.write_json(common.SETTINGS, s)
        return
    if group == "review":
        s = common.settings()
        r = s.get("review") if isinstance(s.get("review"), dict) else {}
        for k, name in (("review_day", "day"), ("review_time", "time")):
            if k in vals:
                r[name] = vals[k]
        s["review"] = r
        common.write_json(common.SETTINGS, s)
        return
    if group == "you":
        me = common.personal()
        title = vals.get("page_title", str(me.get("page_title") or ""))
        setup_steps.you(vals.get("first_name", str(me.get("owner") or "")), vals.get("full_name", str(me.get("full_name") or "")),
                        vals.get("about", str(me.get("about") or "")), vals.get("areas", me.get("areas") or []))
        first = common.personal().get("owner")
        setup_steps.page_heading(title or f"{first}'s desk", vals.get("page_subtitle", str(me.get("page_subtitle") or "")))
        return
    if group == "calendar":
        setup_steps.show_calendars(vals["calendars"])
        try:                    # Today is rewritten now, so the change shows without waiting for the next check
            import items
            items.write_today()
        except Exception:  # noqa: BLE001  it is rewritten at the next check
            pass
        return
    if group == "watch":
        if "important" in vals:
            setup_steps.what_matters(vals["important"])
        if "own_domains" in vals:
            setup_steps.own_mail_domains(vals["own_domains"])
        if "keep_words" in vals:
            me = common.read_json(common.PERSONAL_JSON, {}) or {}
            me["keep_words"] = list(vals["keep_words"])
            common.write_json(common.PERSONAL_JSON, me)
        if "ignore_senders" in vals:
            setup_steps.ignore_senders(vals["ignore_senders"])
    if group == "alerts" and "on" in vals and vals["on"] != bool(str(_part("alerts").get("topic") or "").strip()):
        setup_steps.phone_alerts(vals["on"])
    s = common.settings()
    if group == "watch" and ("paused" in vals or "every_minutes" in vals):
        g = s.get("gathering") if isinstance(s.get("gathering"), dict) else {}
        if "paused" in vals:            # the scheduled pass is switched with it: the setting is the one real switch
            why = switch_pass(not vals["paused"])
            if why:
                _said["more"] = " " + why
        if "paused" in vals and vals["paused"] != bool(g.get("paused")):
            g["paused"] = vals["paused"]
            if vals["paused"]:
                g["paused_at"] = common.now().isoformat(timespec="seconds")
            else:
                g.pop("paused_at", None)
        if "every_minutes" in vals:
            g["every_minutes"] = vals["every_minutes"]
        s["gathering"] = g
    if group == "watch" and "texts_browser" in vals:
        t = s.get("texts") if isinstance(s.get("texts"), dict) else {}
        t["browser"] = vals["texts_browser"]
        s["texts"] = t
    if group == "alerts" and "mail" in vals:
        s.setdefault("alerts", dict(common.DEFAULT_SETTINGS["alerts"]))["mail"] = vals["mail"]
    if group == "alerts" and "quiet" in vals:
        a = s.setdefault("alerts", dict(common.DEFAULT_SETTINGS["alerts"]))
        if vals["quiet"][0]:
            a["quiet"] = {"from": vals["quiet"][0], "to": vals["quiet"][1]}
        else:
            a.pop("quiet", None)
    if group == "page":
        p = s.get("page") if isinstance(s.get("page"), dict) else {}
        p.update(vals)
        s["page"] = p
    if group == "signin":
        s["signin_days"] = vals["days"]
    if group == "thinking":
        t = s.get("thinking") if isinstance(s.get("thinking"), dict) else {}
        t.update(vals)
        s["thinking"] = t
    if group in ("watch", "alerts", "page", "signin", "thinking"):
        common.write_json(common.SETTINGS, s)


def _clock_now():
    now = common.now()
    return now.strftime("%H:%M") if str(_part("page").get("clock")) == "24" else now.strftime("%I:%M %p").lstrip("0")


def save(body):
    """Check and write one save. Returns (saved, the plain line for the page)."""
    st = body.get("settings") if isinstance(body, dict) else None
    if isinstance(st, dict) and str(st.get("group") or "").startswith("mod:"):
        import mods         # a mod's own section: the mod checks it and it is written to the mod's own part
        return mods.save_settings(str(st["group"])[4:], st.get("values"))
    _said.pop("titles", None)
    try:
        group, vals = check(body)
    except Refused as e:
        _said.pop("titles", None)
        return False, f"Not saved. {e} Nothing was changed."
    note = _said.pop("titles", "")
    before = _present(group)
    changed = [k for k, v in vals.items() if before.get(k) != (tuple(v) if k == "quiet" else v)]
    if not changed:
        return True, f"Checked {_clock_now()}: nothing was different, so nothing was changed." + note
    _write(group, {k: vals[k] for k in vals} if group == "you" else {k: vals[k] for k in changed})
    if "texts_browser" in changed:      # the running texts link (in this page server) is told at once
        try:
            import textlink
            textlink.browser_mode()
        except Exception:  # noqa: BLE001  it is told again the next time it starts
            pass
    common.log_line(LOG, f"{group}: saved {', '.join(changed)}")
    what = ", ".join(LABEL[k] for k in changed)
    if group == "watch" and "paused" in changed:
        effect = _said.pop("more", "").strip() or ("I've stopped checking for new messages. Your answers on cards still work." if vals["paused"] else
                                                  f"I'm checking for new messages again, next within {every_minutes()} minutes.")
        if len(changed) > 1:
            effect += " The rest starts the next time I check for messages."
    else:
        effect = {"you": "It shows on your page now, and I use it from the next time I check for messages.",
                  "watch": "It starts the next time I check for messages.",
                  "calendar": "It takes effect at once.",
                  "alerts": "It takes effect now.",
                  "page": "It takes effect now, on every device." + (" Done cards follow the next time I check for messages." if "done_days" in changed else ""),
                  "signin": "It applies the next time you sign in.",
                  "thinking": "It starts the next time I check for messages.",
                  "filter": "It starts the next time I check for messages.{more}",
                  "acting": "It starts the next time I check for messages.{more}",
                  "review": "It starts the next time I check for messages.",
                  "voice": "I use it from the next email I write.",
                  "learning": "It starts the next time I check for messages. {more}"}[group].replace("{more}", _said.pop("more", ""))
    return True, f"Saved {_clock_now()}: {what}. {effect}" + note


def act(rec):
    """One Save press from the page, in the shape answers.act_on_answer returns. A refusal is a result
    the page shows, not a failure of the listener."""
    try:
        body = json.loads(rec.get("text") or "")
    except (ValueError, TypeError):
        body = None
    try:
        saved, said = save(body)
    except Exception as e:  # noqa: BLE001  a save that trips never takes the listener with it
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"settings save: {type(e).__name__}: {e}")
        saved, said = False, f"Not saved. Something went wrong on your computer ({type(e).__name__}). Nothing else was changed."
    if not saved:
        common.log_line(LOG, "a save was refused")
    return {"ok": True, "items": [], "result": said, "thought": False, "saved": saved, "secs": {}}
