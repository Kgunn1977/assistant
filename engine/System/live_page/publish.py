r"""Send the live item store to the owner's live page and bring their answers back.

    python publish.py              send items, health and calendar; collect answers
    python publish.py --answers    collect answers only
    python publish.py --dry-run    build the page data and stop; nothing leaves this machine
    python publish.py --items X    read items from file X instead of Live\items.json (tests)

Reads   Live\items.json, Live\health.json, Live\today.json (the last is optional), and, when the optional
        roadmap piece is applied to any project, each such project's plain copy of its roadmap (roadmaps.py).
Sends   one request to the feed door of each place the page is served from (targets(): this computer's own
        page, the owner's web host, or both; the web host over HTTPS at its address then /api/feed) with
        that page's feed key from local_settings.json. The key can only write the feed and read
        answers. No Claude run is involved, so this works when Windows starts it.
Writes  one file per answer into Live\answers\ in the shape System\live\ITEMS.md asks for.
Never   opens a database, sends a message, edits an engine file, or prints or logs the key.

Exit code 0 means the site answered that it now holds this run's build (or, with --answers,
that the answers were collected). Exit 1 is a failure, with the reason printed and logged.
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LIVE = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(ROOT, "Live")
ITEMS_JSON = os.path.join(LIVE, "items.json")
HEALTH_JSON = os.path.join(LIVE, "health.json")
TODAY_JSON = os.path.join(LIVE, "today.json")
PEOPLE_JSON = os.path.join(LIVE, "known_people.json")
ANSWERS_OUT = os.path.join(LIVE, "answers")

HOME = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(os.path.dirname(os.path.dirname(HERE)), "Live")
SETTINGS = os.path.join(HOME, "personal", "local_settings.json")   # the owner's page address and its key; never printed
STATE = os.path.join(HOME, "page_state")        # this owner's page state lives in their home, never in this folder
STAGE = os.path.join(STATE, "stage")
STATE_JSON = os.path.join(STATE, "state.json")
MIRROR = os.path.join(STATE, "answers.json")
ANSWER_LOG = os.path.join(STATE, "answers_log.jsonl")
LOG = os.path.join(STATE, "publish.log")
ERRORS_LOG = os.path.join(LIVE, "logs", "errors.log")                # every problem, from a pass or the listener, one line each
LISTENER_PROBLEMS = os.path.join(STATE, "listener_problems.json")    # what the listener has trouble with right now, for the page's status line
LISTENER_PROBLEM_HOURS = 12                                          # a trouble nobody has cleared stops showing after this
LOCK = os.path.join(STATE, "publish.lock")

PART_BYTES = 170_000
SOURCE_TEXT_MAX = 6000
DOCS_FEED_MAX = 3_000_000      # all cards' papers together, in bytes as sent; the site takes 6 MB in all
DOCS_NO_ROOM = "[This paper did not fit on the page this time; it is in the original file.]"
BOOK_MAX = 300                 # people in the page's address book, the ones written to most and most recently
BOOK_BYTES = 60_000            # and never more than this, so the page stays small
EMAIL = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[A-Za-z]{2,}$")
TIMEOUT = 60
STATE_ORDER = {"question": 0, "yours": 1, "new": 2, "in_motion": 3, "handled": 4, "done": 5}
KEEP = ("id", "kind", "area", "title", "detail", "state", "importance", "important_reason",
        "source_who", "source_when", "source_ref", "recommended", "asks", "evidence",
        "assistant_did", "answer", "answered_at", "due_date", "checkback_date", "created_at",
        "updated_at", "state_changed_at", "done_at", "from_at", "last_at",
        "calendar", "status",
        "header", "needs", "wants", "why", "shelf", "later_until",      # the card's own (ITEMS.md, "Design round 1")
        "teach", "rule", "came_back", "old_cards",                      # "Design round 2"
        "rule_offer", "rule_scan",      # a rule proposed from his words on a card, and what an approved rule did to other cards
        "rank", "group", "offer", "review", "update", "ready",          # "Design round 3"; the weekly update card; Ready to send
        "facts", "table", "tags",      # plain extras a card may carry: label and value pairs, one small table, short tags
        "choices", "best_guess", "waiting_on", "age_days", "days",
        "questions", "rec_front", "messages", "contact",      # contact: how often he is in touch with its sender     # each question with its own buttons; the recommendation; the messages Context links
        "rsi", "switches", "source_key",    # a rule change card's change, scores and Promote or Apply; the switchable buttons; the card's
                                            # own key, by which the page gives a rule card, an offer and a project write their No
        "pick", "last_time")                # what I predict he will do (its first button); what he did instead on the last card like it
MESSAGE_IDS = re.compile(r"\s*\(\d{4,6}(?:, ?\d{4,6})*\)")     # the engine's own message numbers
# What each page button becomes in the engine's answer file (ITEMS.md).
ENGINE_ACTION = {"approve": "answer", "change": "answer", "answer": "answer", "done": "done",
                 "later": "note", "snooze": "note", "reopen": "reopen", "not_mine": "not_mine"}


def now():
    return dt.datetime.now()


def iso(t):
    return t.isoformat(timespec="seconds")


def log(text):
    os.makedirs(STATE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{now():%Y-%m-%d %H:%M:%S} {text}\n")


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def settings():
    s = read_json(SETTINGS)
    if not s or not s.get("site") or not s.get("feed_key"):
        raise SystemExit("local_settings.json in the personal folder must hold the page's address and the feed key")
    if not str(s["site"]).startswith("https://"):
        raise SystemExit("the page's address must start with https://")
    return s


def hosting():
    """Where the owner's page is served from: "hosted" (their web host), "own_pc" (this computer) or "both".
    It is `page_hosting` in the personal folder's settings.json; with nothing set it is this computer."""
    got = (read_json(os.path.join(HOME, "personal", "settings.json")) or {}).get("page_hosting")
    return got if got in ("hosted", "own_pc", "both") else "own_pc"


def page_port():
    """The port this computer's page answers on (`page_port` in settings.json)."""
    got = (read_json(os.path.join(HOME, "personal", "settings.json")) or {}).get("page_port")
    return got if isinstance(got, int) and 1024 <= got <= 65535 else 47815


def targets():
    """Every place the page is served from, each with its address, its feed key and its own run state.
    This computer's page comes first and the hosted one last."""
    out, how = [], hosting()
    if how in ("own_pc", "both"):
        key = (read_json(SETTINGS) or {}).get("local_feed_key")
        if key:         # made the first time the listener serves the page
            out.append({"name": "this computer", "local": True, "site": f"http://127.0.0.1:{page_port()}", "feed_key": key,
                        "state": os.path.join(STATE, "state_local.json"), "mirror": os.path.join(STATE, "answers_local.json")})
    if how in ("hosted", "both"):
        out.append(dict(settings(), name="the site", state=STATE_JSON, mirror=MIRROR))
    return out


def safe_key(item_id):
    return re.sub(r"[^A-Za-z0-9_\-.~:@+]", "_", str(item_id))[:180]


# --- building what the page shows ---------------------------------------------
def plain_ref(text):
    """A source or evidence line without the engine's message numbers or its 'email:' prefix."""
    text = MESSAGE_IDS.sub("", str(text))
    return re.sub(r"\bemail:(?=\S+@)", "", text).strip()


def readable(text):
    """Message text as a person would want to read it: mail often arrives twice (plain, then
    the same again from its formatted half), padded with blank lines and long bare links."""
    seen, out, blank = set(), [], False
    for raw in str(text).replace("\r", "").split("\n"):
        line = raw.strip().lstrip(">").strip()
        if not line:
            blank = bool(out)
            continue
        key = re.sub(r"\s+", " ", line).lower()
        if len(key) >= 3 and re.search(r"[a-z]", key):     # bare numbers may repeat honestly
            if key in seen:
                continue
            seen.add(key)
        m = re.fullmatch(r"<?(https?://([^/\s>]+)\S*)>?", line)
        if m and len(line) > 60:
            line = f"[link to {m.group(2)}]"
        if blank:
            out.append("")
        out.append(line)
        blank = False
    return "\n".join(out)


def page_item(it):
    out = {k: it[k] for k in KEEP if it.get(k) not in (None, "", [])}
    out["key"] = safe_key(it["id"])
    for k in ("source_ref", "evidence"):
        if out.get(k):
            out[k] = plain_ref(out[k])
    out["asks"] = [a for a in (it.get("asks") or []) if a]
    press = it.get("last_press")                      # what the newest press did, in plain words
    if isinstance(press, dict):
        out["last_press"] = {k: press.get(k) for k in ("press", "at", "happened", "claude", "open", "ok")}
    if it.get("sample"):                              # a Junk or never junk card about one sender: Read a sample
        out["sample"] = True
    who = it.get("sender")                            # whom Junk and Never junk are about
    if isinstance(who, dict) and who.get("address"):
        out["sender"] = {"address": str(who["address"])[:200], "can_junk": bool(who.get("can_junk"))}
    if it.get("draft"):
        d = it["draft"]
        out["draft"] = {"to": d.get("to") or [], "cc": d.get("cc") or [], "subject": d.get("subject") or "",
                        "body": d.get("body") or "",
                        "attach": [os.path.basename(str(a)) for a in (d.get("attach") or [])]}
        if d.get("account"):            # the account it goes from, when the draft names one (Ready to send)
            out["draft"]["account"] = str(d["account"])
        if d.get("bcc"):
            out["draft"]["bcc"] = [str(x) for x in d["bcc"]][:20]
        if d.get("type") in ("new", "reply", "reply_all", "forward"):
            out["draft"]["type"] = d["type"]
        if isinstance(d.get("files"), list):        # attachments by reference (mail.py); the names above are the same files
            out["draft"]["files"] = [{"name": str(f.get("name") or "")[:200], "ref": str(f.get("ref") or "")[:300], "size": f.get("size")}
                                     for f in d["files"] if isinstance(f, dict) and f.get("ref")][:20]
            out["draft"]["attach"] = [f["name"] for f in out["draft"]["files"]]
        if d.get("base"):
            out["draft"]["base"] = str(d["base"])[:40]
        src = d.get("source")
        if isinstance(src, dict) and src.get("message"):    # the email it answers or forwards, folded on the page
            out["draft"]["source"] = {k: src.get(k) for k in ("message", "account", "from", "from_name", "to", "cc", "ts", "when", "subject", "files")}
            out["draft"]["source"]["text"] = str(src.get("text") or "")[:20000]
    reply = it.get("reply")                           # who a reply by email goes to (ITEMS.md)
    if isinstance(reply, dict):
        to = [str(a).strip().lower() for a in (reply.get("to") or []) if EMAIL.match(str(a).strip())]
        if to and reply.get("can_email", True):
            out["reply"] = {"account": str(reply.get("account") or "").strip(), "to": to[:10],
                            "subject": str(reply.get("subject") or "").strip()[:300], "can_email": True,
                            "via": str(reply.get("via") or "email"), "thread": reply.get("thread"), "in_reply_to": reply.get("in_reply_to")}
        elif reply.get("can_email") is False:
            out["reply"] = {"can_email": False, "why": str(reply.get("why") or "")[:200]}
    files =[str(f.get("label") or os.path.basename(str(f.get("path") or ""))) for f in (it.get("evidence_files") or [])
             if isinstance(f, dict)]
    if files:
        out["evidence_files"] = files
    docs = []
    for d in it.get("documents") or []:              # the papers behind the card (ITEMS.md)
        if not isinstance(d, dict) or not d.get("file"):
            continue
        one = {"file": os.path.basename(str(d["file"])), "read": bool(d.get("read")), "kind": d.get("kind") or "file"}
        if d.get("ref"):
            one["ref"] = str(d["ref"])          # opens the paper itself over the page (the page served from his computer)
        if one["read"]:
            one.update(text=str(d.get("text") or ""), cut=bool(d.get("cut")),
                       pages=d["pages"] if isinstance(d.get("pages"), int) and d["pages"] > 0 else 1)
        docs.append(one)
    if docs:
        out["documents"] = docs
    text = it.get("source_text")
    if text:
        text = readable(text)
        out["source_text"] = text if len(text) <= SOURCE_TEXT_MAX else text[:SOURCE_TEXT_MAX] + "\n[cut here; the rest is in the original message]"
    return out


def _problem_book():
    got = read_json(LISTENER_PROBLEMS)
    return got if isinstance(got, dict) and isinstance(got.get("problems"), dict) else {"problems": {}}


def note_problem(key, text):
    """The listener had trouble: one line in the error log (the time, the listener, the plain message) and a place on the page's
    status line until the same thing works again (clear_problem) or 12 hours pass. The same trouble again before it cleared is
    one more line in the error log only if its words changed."""
    text = " ".join(str(text).split())[:300]
    book = _problem_book()
    was = book["problems"].get(key)
    book["problems"][key] = {"at": iso(now()), "text": text}
    try:
        write_json(LISTENER_PROBLEMS, book)
    except OSError:
        pass
    if not was or was.get("text") != text:
        try:
            os.makedirs(os.path.dirname(ERRORS_LOG), exist_ok=True)
            with open(ERRORS_LOG, "a", encoding="utf-8") as f:
                f.write(f"{now():%Y-%m-%d %H:%M:%S} listener {key}: {text}\n")
        except OSError:
            pass


def clear_problem(key):
    book = _problem_book()
    if book["problems"].pop(key, None) is not None:
        try:
            write_json(LISTENER_PROBLEMS, book)
        except OSError:
            pass


def listener_problems():
    """The listener's present troubles, in plain words, for the page's status line."""
    out, cut = [], now() - dt.timedelta(hours=LISTENER_PROBLEM_HOURS)
    for v in _problem_book()["problems"].values():
        try:
            if dt.datetime.fromisoformat(str(v.get("at"))) >= cut and v.get("text"):
                out.append("Listening: " + str(v["text"]))
        except ValueError:
            continue
    return out


PAGE_NOT_UPDATED = "I couldn't update your page after checking for messages."
PAGE_NOT_UPDATED_WAS = "The live page could not be updated from the scheduled job"      # the same line as older checks saved it


def pass_job_off():
    """True when this home's scheduled pass (its 15-minute check) is set up but switched off. False when it is on, when
    there is none (a home with no jobs) or when it cannot be asked."""
    if os.name != "nt":
        return False
    import subprocess
    jobs = read_json(os.path.join(HOME, "personal", "jobs.json"))
    name = jobs.get("pass") if isinstance(jobs, dict) else None
    if not name:
        tag = hashlib.sha1(os.path.normcase(os.path.abspath(HOME)).encode("utf-8")).hexdigest()[:6]
        name = f"Assistant live pass {tag}"
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "LIST"], capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and "disabled" in (r.stdout or "").lower()


def health_lines(health, items_written, job_off=None):
    """The plain sentences the page prints, and when gathering last ran. While the scheduled pass is switched off, the
    page's own "Sync is off" line says so (about() marks it paused), so no sentence here repeats it."""
    problems = listener_problems()
    try:        # texts: the texts link's own word (connected says nothing; disconnected says to sign in again)
        engine = os.path.join(os.path.dirname(HERE), "live")
        if engine not in sys.path:
            sys.path.append(engine)
        import textlink
        problems += textlink.problems()
    except Exception:  # noqa: BLE001  the status line never fails over this
        pass
    gathered = items_written
    if not health:
        problems.append("My regular check for messages hasn't reported how it went yet.")
        return gathered, problems
    last = health.get("last_pass") or {}
    gathered = last.get("started") or health.get("written_at") or items_written
    if pass_job_off() if job_off is None else job_off:      # no pass runs: what the last one found is not news; only what is true right now
        return gathered, problems
    # a page that receives this was updated now: the last pass's "could not be updated" is no longer true
    problems += [str(p) for p in (health.get("problems") or []) if p and str(p) not in (PAGE_NOT_UPDATED, PAGE_NOT_UPDATED_WAS)]
    if last.get("outcome") not in (None, "", "ok") and not problems:
        problems.append(f"The last time I checked for messages, it ended as: {last.get('outcome')}.")
    for name, src in (health.get("sources") or {}).items():
        if isinstance(src, dict) and src.get("status") not in (None, "", "ok", "skipped"):
            why = str(src.get("detail") or "").split(" || ")[0]        # what went wrong, never the progress after it (connections/run.py)
            line = f"{name.split(':')[-1]} is behind" + (f": {why}" if why else ".")
            if not any(name.split(":")[-1] in p for p in problems):
                problems.append(line)
    return gathered, problems


def about(health, gathered, problems, settings, job_off=False):
    """The "Errors" block: every health problem in plain words with its kind, and whether all is well."""
    def what(p):
        low = p.lower()
        if "ai step" in low or "thinking" in low or "claude" in low or "judg" in low:
            return "thinking"
        if "page" in low:
            return "page"
        if "is behind" in low or "connection" in low or "sign" in low:
            return "source"
        if "pass" in low or "gathering" in low or "sync" in low or "for messages" in low or "time i check" in low:
            return "pass"
        return "other"
    watch, think = settings.get("watch") or {}, settings.get("thinking") or {}
    return {"problems": [{"text": p, "what": what(p)} for p in problems], "ok": not problems,
            "last_gathered": gathered, "paused": bool(watch.get("paused") or (health or {}).get("paused") or job_off),
            "limit_reached": bool(think.get("limit_reached"))}


def address_book(people):
    """The page's suggested recipients from the engine's known people (ITEMS.md): name, company and
    plain email addresses of the people written to most, then most recently, within BOOK_MAX and BOOK_BYTES."""
    rows = []
    listed = people.get("people") if isinstance(people, dict) else None
    for p in listed if isinstance(listed, list) else []:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip():
            continue
        emails = []
        for e in p.get("email") or []:
            e = str(e).strip().lower()
            if EMAIL.match(e) and e not in emails:
                emails.append(e)
        if not emails:
            continue
        sent = p.get("sent") if isinstance(p.get("sent"), int) else 0
        last = str((p.get("last") or {}).get("at") or "") if isinstance(p.get("last"), dict) else ""
        rows.append((sent, last, {"name": str(p["name"]).strip()[:80],
                                  "company": str(p.get("company") or "").strip()[:80] or None,
                                  "email": emails[:3]}))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    book, size = [], 0
    for _, _, one in rows[:BOOK_MAX]:
        n = len(json.dumps(one, ensure_ascii=False).encode("utf-8"))
        if size + n > BOOK_BYTES:
            break
        book.append(one)
        size += n
    return book


def build(items_path, changed=None):
    """The page's documents from the item store. `changed` is items the engine has just
    changed and may not have written to its snapshot yet; they replace the snapshot's."""
    store = read_json(items_path)
    if not store or "items" not in store:
        raise SystemExit(f"the item store's snapshot is missing or unreadable: {items_path}")
    if changed:
        fresh = {i["id"]: i for i in changed if isinstance(i, dict) and i.get("id")}
        store["items"] = [fresh.pop(i.get("id"), i) for i in store["items"]] + list(fresh.values())
    # a finished card the owner dismissed is off the page (the engine's history line says so; answers.PUT_AWAY)
    away = lambda it: it.get("state") == "done" and str(it.get("assistant_did") or "").split("\n")[-1].startswith("You put this away")
    shown = [it for it in store["items"] if it.get("id") and not away(it)]
    try:        # true order, and grouping when the owner chose it (order.py)
        engine = os.path.join(os.path.dirname(HERE), "live")
        if engine not in sys.path:
            sys.path.append(engine)
        import order
        order.annotate(shown)
    except Exception:  # noqa: BLE001  the page is never lost over an order
        pass
    items = [page_item(it) for it in shown]
    items.sort(key=lambda i: i.get("source_when") or "", reverse=True)
    items.sort(key=lambda i: (-(i.get("importance") or 0), STATE_ORDER.get(i.get("state"), 9)))
    room = DOCS_FEED_MAX                              # the papers' words, first cards first, within what the site takes
    for it in items:
        for d in it.get("documents") or []:
            if d.get("text"):
                size = len(json.dumps(d["text"], ensure_ascii=False).encode("utf-8"))
                if size > room:
                    d.update(text=DOCS_NO_ROOM, cut=True)
                    size = len(DOCS_NO_ROOM)
                room -= size
    health, job_off = read_json(HEALTH_JSON), pass_job_off()
    gathered, problems = health_lines(health, store.get("written_at"), job_off)
    today = read_json(TODAY_JSON)
    who = read_json(os.path.join(HOME, "personal", "personal.json")) or {}
    parts, cur, size = [], [], 0
    for it in items:
        n = len(json.dumps(it, ensure_ascii=False).encode("utf-8"))
        if cur and size + n > PART_BYTES:
            parts.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += n
    parts.append(cur)
    stamp = hashlib.sha1(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    meta = {"built": iso(now()), "stamp": stamp, "parts": len(parts), "count": len(items),
            "gathered": gathered, "written_at": store.get("written_at"), "pass_id": store.get("pass_id"),
            "problems": problems, "today": {"days": today.get("days") or []} if today else None,
            # headings: the owner's own title, and whatever names an add-on gives its sections
            "labels": store.get("labels") or {}, "page_files": page_files_mark(),
            "tips": store.get("tips") or {},        # one-time tips that are not on a card (onboard.tips): Hidden's
            "page_title": who.get("page_title"), "page_subtitle": who.get("page_subtitle"),
            # whether the owner may send an email they wrote on the page, and from which of their accounts
            "send": {"on": bool(((read_json(os.path.join(HOME, "personal", "settings.json")) or {}).get("owner_send") or {}).get("on")),
                     "accounts": list(who.get("send_accounts") or [])},
            # suggested recipients for the writing screen: the people written to most and most recently
            "people": address_book(read_json(PEOPLE_JSON)),
            # the short running conversation of the box at the top of the page
            # (a turn said in a Claude desktop session that joined it is marked "desktop")
            "chat": {"turns": [{k: t.get(k) for k in ("who", "text", "source", "at", "change", "scan", "desktop") if k not in ("change", "scan", "desktop") or t.get(k)}
                               for t in [t for t in ((read_json(os.path.join(HOME, "chat.json")) or {}).get("turns") or [])
                                         if not t.get("card")][-12:]]},      # a card's talk is that card's own, never shown here
            # the Open in the Claude app button: a new Claude Code session in the assistant's folder, asked in plain words to join
            # (the app turns a link's leading "/" into a fullwidth one, so a slash command in the link never runs)
            "desk_link": "claude://code/new?folder=" + urllib.parse.quote(os.path.abspath(os.path.dirname(HOME)), safe="") +
                         "&q=" + urllib.parse.quote("Join Talk to your assistant.", safe="")}
    try:        # the present value of every setting, for the page's Settings panel (ITEMS.md); never a password or a key
        engine = os.path.join(os.path.dirname(HERE), "live")
        if engine not in sys.path:
            sys.path.append(engine)
        import settings_page
        meta["settings"] = settings_page.for_page()
        import settings_data
        meta["settings_defs"] = settings_data.defs(meta["settings"])     # the same settings as data the page can draw from
        import rebuild
        meta["rebuild"] = rebuild.for_page()        # Rebuild all cards: running now, or when it last finished
        import tools
        meta["tools"] = tools.listed()              # Settings, Tools: each tool's name and plain words, and its Start
        import mail
        meta["mail_reload"] = mail.reload_status()  # Settings, Tools: Reload all email history, how far each mailbox has got
        import project_tools
        meta["ptools"] = project_tools.listed()     # Settings, Tools: add or remove the roadmap or the questions file in a project
        import mods
        meta["mod_parts"] = mods.page_parts()       # parts of the page the owner's own mods bring (their script, placed like Texts)
        meta["projects"] = project_tools.projects() # the projects to choose from, each with whether the roadmap and the questions file are on
    except Exception:  # noqa: BLE001  the page is never lost over its settings panel
        pass
    meta["about"] = about(health, gathered, problems, meta.get("settings") or {}, job_off)
    if hosting() in ("own_pc", "both") and os.path.exists(os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "Assistant manual.html")):
        meta["manual"] = {"url": "/manual", "label": "How your page works"}      # the page links to it at the top of Settings and in its footer
    try:        # the optional roadmap piece: one entry per project it is applied to; no key at all when it is not applied
        import roadmaps
        applied = roadmaps.for_page()
        if applied:
            meta["roadmaps"] = applied
    except Exception:  # noqa: BLE001  a roadmap that cannot be read never stops the page
        pass
    standing = read_json(os.path.join(HOME, "standing_feed.json"))         # what standing approvals did, and the ladder (standing.py)
    held = read_json(os.path.join(HOME, "held.json"))      # what was kept off the page, by day, with why (held.py)
    try:        # a day stored as a date is worded for today each time the page is built (dates.py)
        import dates
        for day in (held or {}).get("days") or []:
            for row in day.get("rows") or []:
                if isinstance(row.get("why"), str):
                    row["why"] = dates.show(row["why"])
    except Exception:  # noqa: BLE001  the list is never lost over a word
        pass
    if isinstance(held, dict) and isinstance(held.get("days"), list):
        meta["held_today"] = held.get("today") or 0
    docs = {"current": meta}
    if isinstance(held, dict) and isinstance(held.get("days"), list):
        docs["held"] = held
    if isinstance(standing, dict) and isinstance(standing.get("ladder"), list):
        docs["standing"] = standing
    try:        # changes to the program (the change skill's records): the page shows them only when this copy has the skill
        import changes_feed
        ch = changes_feed.doc()
        if ch is not None:
            docs["changes"] = ch
    except Exception:  # noqa: BLE001  the page is never lost over its list of changes
        pass
    reading = read_json(os.path.join(HOME, "state", "held_reading.json"))     # the one held-back message asked for last
    if isinstance(reading, dict) and reading.get("key"):
        docs["reading"] = reading
    try:        # each roadmap whole, for the roadmap's own page drawn inside this one (roadmaps.full_docs)
        import roadmaps
        docs.update(roadmaps.full_docs())
    except Exception:  # noqa: BLE001  a roadmap that cannot be read never stops the page
        pass
    for n, p in enumerate(parts):
        docs[f"part-{n}"] = {"stamp": stamp, "items": p}
    return docs, {i["key"]: i for i in items}


def page_files_mark():
    """A short mark of the page's own files as last confirmed on the site. An open page compares it with the
    mark it started with, and loads the newer page when they differ."""
    return (read_json(os.path.join(STATE, "page_files_on_site.json")) or {}).get("mark")


# --- the feed door ---------------------------------------------------------------
def call_site(cfg, path, body=None):
    """One HTTPS request with the feed key. Returns (ok, reply or reason). The key is never echoed."""
    url = cfg["site"].rstrip("/") + "/api/" + path
    data = None if body is None else json.dumps(body, ensure_ascii=False)
    if data is not None:
        try:        # a key for an outside program never leaves this computer in the page's data, whatever put it there
            import keys
            data = keys.scrub(data)
        except ImportError:
            pass
        data = data.encode("utf-8")
    req =urllib.request.Request(url, data=data, method="POST" if data is not None else "GET", headers={
        "X-Brief-Key": cfg["feed_key"], "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json", "User-Agent": "live-page-publish/1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if not cfg.get("local") and not r.geturl().startswith("https://"):
                return False, "the site answered over a connection that is not HTTPS"
            reply = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        words = {403: "the site refused the feed key", 429: "the site has locked this address out after wrong keys",
                 413: "the feed was too large for the site"}.get(e.code, f"the site answered {e.code}")
        return False, words
    except (urllib.error.URLError, OSError, ValueError) as e:
        if cfg.get("local"):
            return False, "this computer's page is not being served right now (the listener serves it)"
        return False, f"the site could not be reached: {type(e).__name__}"
    if not isinstance(reply, dict) or not reply.get("ok"):
        return False, "the site's answer was not understood"
    return True, reply


# --- the page's own files ----------------------------------------------------------
PAGE_FILES = ("app.css", "app.js", "shell.html", "manifest.json")      # the site takes these four and no others


def send_files():
    """Bring every place the page is served from up to the page files in this folder, and check each one:
    a web host is sent the files and must answer that it holds exactly these; this computer's own page
    serves them straight from this folder and must answer that what it serves is exactly these."""
    app = os.path.join(HERE, "site", "app")
    files, local = {}, {}
    for name in PAGE_FILES:
        with open(os.path.join(app, name), encoding="utf-8", newline="") as f:
            files[name] = f.read()
        local[name] = hashlib.sha256(files[name].replace("\r", "").encode("utf-8")).hexdigest()
    where, how, worst = targets(), hosting(), 0
    if how in ("own_pc", "both") and not any(t.get("local") for t in where):
        where.insert(0, None)       # this computer should serve the page and has never started to
    for t in where:
        if t is None:
            ok, line = False, "FAILED: this computer's page is not being served yet (the listener serves it)"
        elif t.get("local"):
            ok, reply = call_site(t, "files")
            differ = [n for n in PAGE_FILES if ((reply.get("hashes") or {}).get(n) if ok else None) != local[n]]
            if not ok:
                line = f"FAILED: this computer's page could not be checked: {reply}"
            elif differ:
                ok, line = False, "FAILED: this computer's page does not serve the files here: " + ", ".join(differ)
            else:
                line = f"this computer's page serves the files here: {len(PAGE_FILES)} files"
        else:
            ok, reply = call_site(t, "files", {"files": files})
            differ = [n for n in PAGE_FILES if (reply.get("hashes") or {}).get(n) != local[n]] if ok else []
            damaged = [str(d) for d in reply.get("damaged_files") or []] if ok else []
            if not ok:
                line = f"FAILED: page files not sent: {reply}"
            elif differ or damaged:
                ok, line = False, "FAILED: page files on the site do not match the ones here: " + ", ".join(differ + damaged)
            else:
                write_json(os.path.join(STATE, "page_files_on_site.json"),          # what an open page compares itself with
                           {"mark": hashlib.sha1("|".join(local[n] for n in PAGE_FILES).encode()).hexdigest()[:12], "at": iso(now())})
                line = f"page files on the site match the ones here: {len(PAGE_FILES)} files"
        worst = worst or (0 if ok else 1)
        log(line)
        print(line)
    return worst


# --- answers -----------------------------------------------------------------------
def engine_file(rec):
    """One answer in the shape System\\live\\ITEMS.md asks for, plus the page's own detail."""
    act = rec.get("action")
    text = (rec.get("text") or "").strip()
    if act == "approve":
        text = "Approved" + (f": {text}" if text else "")
    elif act == "change":
        text = f"Change: {text}"
    elif act == "later":
        text = "Not now"
    elif act == "snooze":
        text = f"Snooze until {rec.get('until')}"
    out = {"id": rec.get("id"), "action": ENGINE_ACTION.get(act, "note"), "text": text, "at": rec.get("at"),
           "page_action": act, "label": rec.get("label") or "", "until": rec.get("until") or None,
           "device": rec.get("device") or "", "sent": False}
    if isinstance(rec.get("open_card"), str) and rec["open_card"]:
        out["open_card"] = rec["open_card"][:20]      # the card open on his page when he wrote in the box ("this card")
    if isinstance(rec.get("question"), int) and not isinstance(rec.get("question"), bool):
        out["question"] = rec["question"]               # the numbered question on the card this answer is for
    if isinstance(rec.get("redo"), int) and not isinstance(rec.get("redo"), bool):
        out["redo"] = rec["redo"]                       # Change on one answered question: its place among them
    for f in ("button", "meaning", "pick"):             # a choice button's id and meaning: the engine checks them (presses.chosen); pick: the card's pick was pressed
        if isinstance(rec.get(f), str):
            out[f] = rec[f][:60]
    if isinstance(rec.get("calendar"), dict):           # the day and time he picked, exactly as picked
        out["page_action"] = "calendar"
        out["calendar"] = rec["calendar"]
    return out


def drop(rec):
    out = engine_file(rec)
    try:
        unix = int(dt.datetime.fromisoformat(str(out["at"])).timestamp())
    except ValueError:
        unix = int(now().timestamp())
        out["at"] = iso(now())
    path = os.path.join(ANSWERS_OUT, f"{safe_key(out['id']).replace(':', '_')}-{unix}.json")   # a colon is a key's, never a file name's (a roadmap press id has two)
    write_json(path, out)
    with open(ANSWER_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(out, delivered=iso(now()), file=os.path.basename(path)), ensure_ascii=False) + "\n")
    return path


def take_answers(state, pulled, items_by_key, mirror=None):
    """Turn what the site returned into engine files; decide what to clear from the page next time."""
    pulled = {k: v for k, v in (pulled or {}).items() if isinstance(v, dict) and v.get("id") and v.get("action")}
    delivered = state["delivered"]            # key -> the `at` of the answer last handed to the engine
    removed_by_us = set(state.pop("removing", []))
    dropped = 0
    for key, rec in pulled.items():
        if delivered.get(key) != rec.get("at"):
            drop(rec)
            delivered[key] = rec.get("at")
            state["actions"][key] = rec.get("action")
            dropped += 1
    for key in [k for k in delivered if k not in pulled]:
        # Gone from the page. If the owner pressed Undo (we did not clear it), tell the engine.
        if key not in removed_by_us and state["actions"].get(key) != "reopen":
            item = items_by_key.get(key) or {}
            drop({"id": item.get("id") or key, "action": "reopen", "text": "", "at": iso(now()), "label": "Undo"})
            dropped += 1
        delivered.pop(key, None)
        state["actions"].pop(key, None)
    today = now().date().isoformat()
    removing = []
    for key, rec in pulled.items():
        item, act, at = items_by_key.get(key), rec.get("action"), str(rec.get("at") or "")
        if items_by_key and item is None:
            gone = True                                        # the item left the store
        elif item is None:
            gone = False
        elif act == "later":
            gone = at[:10] < today
        elif act == "snooze":
            gone = str(rec.get("until") or "") <= today
        elif act == "reopen":
            gone = not item.get("answer")
        else:
            gone = item.get("state") == "done" or str(item.get("answered_at") or "") >= at
        if gone:
            removing.append([key, at])                         # cleared only if still this same answer
    state["to_remove"] = removing
    write_json(mirror or MIRROR, {"fetched_at": iso(now()), "answers": pulled})
    return len(pulled), dropped


# --- one run -------------------------------------------------------------------------
def run(args):
    global ANSWERS_OUT, ANSWER_LOG
    if args.test_dir:
        ANSWERS_OUT = os.path.join(args.test_dir, "answers")
        ANSWER_LOG = os.path.join(args.test_dir, "answers_log.jsonl")
    os.makedirs(ANSWERS_OUT, exist_ok=True)
    docs = None
    if args.answers:
        store = read_json(ITEMS_JSON) or {}
        items_by_key = {safe_key(i["id"]): i for i in store.get("items", []) if i.get("id")}
    else:
        docs, items_by_key = build(args.items or ITEMS_JSON)
        for doc_id, doc in docs.items():
            write_json(os.path.join(STAGE, doc_id + ".json"), doc)
        if args.dry_run:
            print(f"dry run: {docs['current']['count']} items in {docs['current']['parts']} part(s), "
                  f"stamp {docs['current']['stamp']}, staged in {STAGE}")
            return 0
    where = targets()
    if not where:
        line = "no page is being served yet, so there was nothing to update"
        log(line)
        print(line)
        return 0
    codes = [run_one(args, t, docs, items_by_key) for t in where]
    # this computer's page being off is the listener's to report; a page on a web host that fails is this run's failure
    return 1 if all(codes) or any(c for c, t in zip(codes, where) if not t.get("local")) else 0


def run_one(args, where, docs, items_by_key):
    """One place the page is served from: send it the items, bring its answers back."""
    state_json, mirror = where["state"], where["mirror"]
    if args.test_dir:
        tail = "_local" if where.get("local") else ""
        state_json, mirror = os.path.join(args.test_dir, f"state{tail}.json"), os.path.join(args.test_dir, f"answers{tail}.json")
    say = "this computer's page: " if where.get("local") else ""
    state = read_json(state_json) or {}
    state = {"delivered": state.get("delivered") or {}, "actions": state.get("actions") or {},
             "to_remove": [c for c in (state.get("to_remove") or []) if isinstance(c, list) and len(c) == 2 and isinstance(c[1], str)]}
    if docs is None:
        ok, reply = call_site(where, "answers")
        what = "answers collected"
    else:
        state["removing"] = [c[0] for c in state["to_remove"]]
        ok, reply = call_site(where, "feed", {"docs": docs, "clear": state["to_remove"]})
        if ok and (reply.get("built") != docs["current"]["built"] or reply.get("stamp") != docs["current"]["stamp"]):
            ok, reply = False, (f"the page was not confirmed updated: the site holds the build of "
                                f"{reply.get('built') or 'nothing'}, this run made {docs['current']['built']}")
        what = f"page confirmed current: {docs['current']['count']} items"

    if not ok:
        state.pop("removing", None)
        write_json(state_json, state)
        line = f"{say}FAILED: {reply}"
        log(line)
        print(line)
        return 1
    n_answers, dropped = take_answers(state, reply.get("answers"), items_by_key, mirror)
    write_json(state_json, state)
    line = f"{say}{what}; {n_answers} answer(s) on the page, {dropped} handed to the engine"
    if reply.get("damaged_files"):
        line += "; PAGE FILES DAMAGED ON THE SITE: " + ", ".join(map(str, reply["damaged_files"]))
    if reply.get("wrong_keys"):
        line += f"; wrong feed keys refused by the site so far: {reply['wrong_keys']}"
    log(line)
    print(line)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Send the live items to the live page and collect the owner's answers.")
    ap.add_argument("--answers", action="store_true", help="collect answers only")
    ap.add_argument("--files", action="store_true", help="put the page's own four files on the site and check they match")
    ap.add_argument("--dry-run", action="store_true", help="build the page data and stop")
    ap.add_argument("--force", action="store_true", help="kept for older callers; every run sends everything")
    ap.add_argument("--items", help="read items from this file instead of Live\\items.json")
    ap.add_argument("--test-dir", help="tests: keep answer files and run state in this folder, not the real ones")
    args = ap.parse_args()
    os.makedirs(STATE, exist_ok=True)
    if os.path.exists(LOCK) and now().timestamp() - os.path.getmtime(LOCK) < TIMEOUT * 2:
        print("another publish is still running; this one stood down")
        return 3
    with open(LOCK, "w") as f:
        f.write(str(os.getpid()))
    try:
        return send_files() if args.files else run(args)
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
