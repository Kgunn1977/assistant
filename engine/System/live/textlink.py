r"""The link to the owner's own Google Messages (SMS and RCS), straight from Google, with no browser tab.

messages_link\messages-link.exe (Go, built on the open-source libgm, see its main.go) does the talking to Google. The page
server (the listener, listen.py) starts it with itself, hidden, and it ends with the server: it reads its commands on its
input and stops when that closes. It never opens the database; it hands every text to this module, which stores it as
channel sms (the same store and de-duplication as every other text: the message's own id, then the same words in the same
direction within two minutes). During an update's hold on the database the texts wait in a file and are stored after.

    start() / stop()          the companion, with the server
    status()                  the state as last known (also in state\messages_link.json, for the pass and the Errors box)
    pair(cookie_text)         sign-in: the cookies he copied from Firefox; returns the emoji to tap on his phone
    cancel_pair()
    owns(item)                True when a queued text goes out through the link (one taker per text: never the extension too)
    kick()                    a text was queued: the sender looks now
    problems()                plain lines for the Texts section and the Errors box, each starting "Google Messages"
    pass_check()              the 15-minute pass's connection check: the same lines, plus a link that has stopped checking in

What is kept: the sign-in (cookies and pairing) in the personal folder's google_messages_link.json, written by the companion
only. Cookies are never logged or written anywhere else.
"""
import datetime as dt
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

import common

LIVE = os.path.dirname(os.path.abspath(__file__))
if LIVE not in sys.path:
    sys.path.insert(0, LIVE)

EXE = os.path.join(LIVE, "messages_link", "messages-link.exe")
AUTH = os.path.join(common.paths.PERSONAL, "google_messages_link.json")
STATUS = os.path.join(common.paths.STATE, "messages_link.json")
MEDIA = os.path.join(common.paths.STATE, "messages_link_media")
PENDING = os.path.join(common.paths.STATE, "messages_link_pending.json")
HOLD = os.path.join(common.paths.STATE, "update_hold.json")
GROUPS = os.path.join(common.paths.STATE, "google_messages_groups.json")
LOG = os.path.join(common.LOGS, "messages_link.log")
TEXTS_LOG = os.path.join(common.LOGS, "texts.log")
BEAT_SECONDS = 60
TAKE_BACK = os.path.join(common.paths.STATE, "texts_link_take_back.json")   # the pass asks the page server to take the session back
DEEP_CATCHUP = "deep_catchup_at"   # set once the one week catch-up after the extension went has run
PICTURES_CATCHUP = "pictures_catchup_at"   # when the one week catch-up that fills pictures into texts stored before the link last ran
PICTURES_BUILD = "pictures_catchup_build"   # and with which build of the companion: a new build (its download changed) runs it again
DUPLICATES = "duplicates_removed_at"       # when texts stored twice before the link were last kept once (texts.remove_duplicates)
DUPLICATES_RULE = "duplicates_rule"        # and by which rule: a changed rule runs it once more
RULE = "2"                                 # 2: the same words with spacing aside
STALE_MINUTES = 5            # no word from the link for this long: it is not running
SLOW_MINUTES = 10            # trying to connect for this long is said on the page
SIGN_IN = "press Sign in to Google Messages in the Texts section"
WANTED = ("SID", "HSID", "OSID", "SSID", "APISID", "SAPISID", "__Secure-1PSIDTS")
REQUIRED = WANTED[:6]
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_proc = None
_lock = threading.RLock()
_replies = {}
_rid = [0]
_rows = queue.Queue()
_kick = threading.Event()
_stopping = threading.Event()
_started = [False]


# --- the status file ---------------------------------------------------------------------------------------------
def _now():
    return common.now().isoformat(timespec="seconds")


def _note(**fields):
    with _lock:
        st = common.read_json(STATUS, {}) or {}
        if "state" in fields and fields["state"] != st.get("state"):
            fields["state_since"] = _now()
        st.update(fields)
        common.write_json(STATUS, st)
        return st


def status():
    return common.read_json(STATUS, {}) or {}


def _fresh(st, minutes=STALE_MINUTES):
    try:
        return (common.now() - dt.datetime.fromisoformat(st.get("beat"))).total_seconds() < minutes * 60
    except (TypeError, ValueError):
        return False


def connected(st=None):
    st = status() if st is None else st
    return st.get("state") == "connected" and _fresh(st)


def signed_in(st=None):
    """The link holds a pairing (it may be connecting or the phone may be away): it is the one that sends."""
    st = status() if st is None else st
    return bool(st.get("paired")) and _fresh(st) and st.get("state") not in ("signed_out", "signed_out_by_google", "unpaired")


def public():
    """What the page's Texts section needs: the state and, while pairing, the emoji. Nothing secret."""
    st = status()
    state = st.get("state") or "signed_out"
    if not _fresh(st) and state not in ("signed_out", "not_installed"):
        state = "not_running"
    return {"state": state, "say": st.get("say") or "", "emoji": (st.get("emoji") or "") if state == "pairing" else "",
            "signed_in_once": bool(st.get("signed_in_once")), "pair_error": st.get("pair_error") or "",
            "since": st.get("state_since") or "", "last_text": st.get("last_text") or ""}


def _when(iso):
    try:
        t = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return "a while ago"
    return t.strftime("%I:%M %p").lstrip("0") + ("" if t.date() == common.now().date() else t.strftime(" on %b %d"))


def problems(st=None):
    """Plain lines, each starting 'Google Messages', for the Texts section and the Errors box. Nothing until he has signed in once."""
    st = status() if st is None else st
    state = st.get("state")
    if not st.get("signed_in_once") or state in (None, "signed_out", "not_installed", "pairing"):
        return []
    if not _fresh(st):
        return [f"Google Messages: the texts link on this computer has not checked in since {_when(st.get('beat'))}, so new texts are not arriving."]
    if state in ("signed_out_by_google", "unpaired"):
        why = (st.get("say") or "").strip()
        return ["Google Messages: texts are disconnected" + (f". {why.rstrip('.')}" if why else "") + f". To get them back, sign in again: {SIGN_IN}."]
    if state == "phone_not_responding":
        return ["Google Messages: your phone is not answering, so new texts are not arriving. Check that it is on and has signal or Wi-Fi."]
    if state in ("connecting", "error", "stopped"):
        try:
            long_ = (common.now() - dt.datetime.fromisoformat(st.get("state_since"))).total_seconds() >= SLOW_MINUTES * 60
        except (TypeError, ValueError):
            long_ = True
        if long_ or state != "connecting":
            why = (st.get("say") or "").strip().rstrip(".")
            return [f"Google Messages: texts are not connected since {_when(st.get('state_since'))}" + (f" ({why})" if why else "") + ", so new texts are not arriving."]
    return []


PAUSED_BROWSER = "Paused while Messages is open in your browser"


def browser_mode():
    """The owner's choice (Settings, What it watches) given to the companion: take the session back at once, or let a browser
    have it until the 15-minute check (pass_check) takes it back. Google sends no word when a browser tab is closed."""
    try:
        import settings_page
        mode = settings_page.texts_browser()
    except Exception:  # noqa: BLE001
        mode = "take_back"
    _write({"cmd": "browser", "mode": "yield" if mode == "let_browser" else "take_back"})
    return mode


def take_back():
    """The session back from a browser that took it (the companion then catches up): from the pass's request, or his press of
    Take it back now. {"ok": True} when Google was asked and agreed, else {"ok": False, "error": plain words}."""
    import replay_guard
    replay_guard.refuse("taking over the texts link")
    got = _call({"cmd": "take_back"}, timeout=60)
    ok = bool(got and got.get("ok"))
    common.log_line(TEXTS_LOG, "link: took the session back from the browser" if ok else "link: could not take the session back yet")
    if ok:
        return {"ok": True}
    return {"ok": False, "error": "Google did not hand Messages back to this computer just now. Close Google Messages in your browser and press "
                                  "Take it back now again." if got is not None else "The texts link on this computer did not answer. Try again in a minute."}


def pass_check():
    """The 15-minute pass's connection check (another program: it reads the link's status file, written each minute)."""
    import replay_guard
    replay_guard.refuse("asking the page to take the texts link back")      # it may write the take-back request
    st = status()
    if st.get("signed_in_once") and not os.path.isfile(EXE):
        return ["Google Messages: the part of me that reads your texts is missing from this computer; the next update puts it back."]
    if st.get("state") == "browser_open":       # he chose to let a browser have it: the pass is when it is taken back
        common.write_json(TAKE_BACK, {"at": _now()})
        return []
    return problems(st)


# --- the companion --------------------------------------------------------------------------------------------------
def start():
    """Start the companion with the server (once). Nothing happens when the program is not on this computer."""
    import replay_guard
    replay_guard.refuse("starting the texts link")
    global _proc
    with _lock:
        if _started[0]:
            return True
        if not os.path.isfile(EXE):
            _note(state="not_installed", say="", beat=_now())
            return False
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        os.makedirs(MEDIA, exist_ok=True)
        _started[0] = True
        _stopping.clear()
    _spawn()
    for target in (_reader_loop, _store_loop, _beat_loop, _send_loop):
        threading.Thread(target=target, name="messages-link " + target.__name__, daemon=True).start()
    return True


def _spawn():
    import replay_guard
    replay_guard.refuse("starting the texts link")
    global _proc
    with _lock:
        err = open(LOG, "a", encoding="utf-8")
        _proc = subprocess.Popen([EXE, "--auth", AUTH, "--media", MEDIA], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                 creationflags=HIDDEN, cwd=os.path.dirname(EXE))
        err.close()
    common.log_line(TEXTS_LOG, f"link: started (process {_proc.pid})")
    browser_mode()
    since = _catchup_from_us()
    if not status().get(DEEP_CATCHUP):         # once: from a week back (the link's own limit), whatever the newest stored text says
        since = min(since or _week_us(), _week_us())
    if since:
        _write({"cmd": "since", "us": since})


def stop():
    """Stop the companion: its input is closed, it saves and ends; it is ended outright if it has not after a few seconds."""
    global _proc
    _stopping.set()
    with _lock:
        p, _proc = _proc, None
        _started[0] = False
    if p is None:
        return
    try:
        p.stdin.close()
        p.wait(timeout=8)
    except Exception:  # noqa: BLE001
        p.kill()
    _note(state="stopped", say="")


def _write(obj):
    with _lock:
        p = _proc
        if p is None or p.poll() is not None:
            return False
        try:
            p.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            p.stdin.flush()
            return True
        except OSError:
            return False


def _call(cmd, timeout=30):
    with _lock:
        _rid[0] += 1
        rid = str(_rid[0])
        box = [threading.Event(), None]
        _replies[rid] = box
    if not _write(dict(cmd, rid=rid)):
        _replies.pop(rid, None)
        return None
    box[0].wait(timeout)
    _replies.pop(rid, None)
    return box[1]


def _reader_loop():
    while not _stopping.is_set():
        p = _proc
        if p is None:
            return
        line = p.stdout.readline()
        if not line:
            if _stopping.is_set():
                return
            code = p.poll()
            common.log_line(TEXTS_LOG, f"link: the program ended (exit {code}); starting it again in a minute")
            _note(state="stopped", say="The texts link stopped; it is being started again.")
            time.sleep(60)
            if _stopping.is_set():
                return
            _spawn()
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:
            continue
        kind = msg.get("type")
        if kind == "reply":
            box = _replies.get(str(msg.get("rid")))
            if box:
                box[1] = msg
                box[0].set()
        elif kind == "message":
            _rows.put(msg.get("row") or {})
        elif kind == "state":
            st = _note(**_status_fields(msg))
            common.log_line(TEXTS_LOG, f"link: {st.get('state')}" + (f" ({st.get('say')})" if st.get("say") else ""))
            if st.get("state") == "connected":
                _kick.set()
                threading.Thread(target=match_all, daemon=True).start()
        elif kind == "convs":                  # the list the link read in its catch-up: older conversations matched to it
            threading.Thread(target=match, args=(msg.get("convs") or [],), daemon=True).start()
        elif kind == "pair_done":
            _note(pair_error="" if msg.get("ok") else str(msg.get("error") or "")[:300])
            common.log_line(TEXTS_LOG, "link: paired" if msg.get("ok") else "link: pairing failed")


def _status_fields(msg):
    return {"state": msg.get("state"), "say": msg.get("say") or "", "ready": bool(msg.get("ready")), "paired": bool(msg.get("paired")),
            "signed_in_once": bool(msg.get("signed_in_once")), "phone_responding": bool(msg.get("phone_responding")),
            "emoji": msg.get("emoji") or "", "last_data": msg.get("last_data") or "", "beat": _now()}


def _beat_loop():
    """Each minute the link is asked how it is; the answer is the heartbeat the pass and the page read. Once connected, the
    one week catch-up runs once (deep_catchup), then the link goes back to catching up from the newest stored text."""
    while not _stopping.wait(BEAT_SECONDS if status().get("state") != "pairing" else 5):
        got = _call({"cmd": "status"}, timeout=15)
        if got:
            _note(**_status_fields(got))
        if connected():
            if not status().get(DEEP_CATCHUP):
                deep_catchup()
            elif status().get(PICTURES_BUILD) != build():
                deep_catchup(PICTURES_CATCHUP)
            elif status().get(DUPLICATES_RULE) != RULE:
                remove_duplicates()
        if os.path.isfile(TAKE_BACK):          # the pass asked: the session back from the browser, then a catch-up
            try:
                os.remove(TAKE_BACK)
            except OSError:
                pass
            if status().get("state") == "browser_open":
                take_back()
        _kick.set()


_matching = threading.Lock()
PHONE_BOOK = os.path.join(common.paths.STATE, "phone_book.json")


def phone_book(convs, whole=False):
    """The phone's own contacts as Google Messages names them (a person's name, not a bare number), from its conversation
    list: kept for Contacts (contacts_book.py). A whole list replaces the book; a catch-up's page only adds to it."""
    got = {} if whole else {p["number"]: p for p in (common.read_json(PHONE_BOOK, {}) or {}).get("people") or [] if p.get("number")}
    for v in convs or []:
        for o in (v or {}).get("others") or []:
            name, number = " ".join(str((o or {}).get("name") or "").split()), str((o or {}).get("number") or "").strip()
            if number and name and not re.fullmatch(r"[\d\s()+.-]{3,}", name):
                got[number] = {"name": name[:120], "number": number[:40]}
    common.write_json(PHONE_BOOK, {"at": _now(), "people": sorted(got.values(), key=lambda p: p["name"].lower())})


def match(convs, whole=False):
    """Conversations stored before the link get the link's conversation id (and number): texts.link_match. Logged as counts:
    `whole` is the whole list read on connecting; otherwise it is the catch-up's newest page, matched without waiting."""
    if not convs or not _matching.acquire(blocking=whole, timeout=300 if whole else -1):
        return None
    try:
        phone_book(convs, whole)
    except Exception as e:  # noqa: BLE001  the book is filled again at the next list
        common.log_line(TEXTS_LOG, f"link: phone book not kept ({type(e).__name__})")
    try:
        import texts
        got = texts.link_match(convs)
        k = got.get("kinds") or {}
        common.log_line(TEXTS_LOG, ("link: whole conversation list, " if whole else "link: catch-up's newest conversations, ") +
                        f"{len(convs)} listed by Google Messages" + (f" ({(got.get('listed') or {}).get('one-to-one', 0)} one-to-one, "
                        f"{(got.get('listed') or {}).get('with a number', 0)} of them with a number; {(got.get('listed') or {}).get('groups', 0)} groups)" if whole else "")
                        + f": older conversations matched {got['matched']}, not matched {got['unmatched']}"
                        + (f" ({k.get('groups', 0)} groups, {k.get('with a number', 0)} one-to-one sent by number, {k.get('with neither', 0)} with "
                           f"neither; {k.get('last text in 90 days', 0)} had a text in the last 90 days)" if whole else ""))
        return got
    except Exception as e:  # noqa: BLE001  the next connect or catch-up tries again
        common.log_line(TEXTS_LOG, f"link: matching older conversations failed ({type(e).__name__}: {str(e)[:200]})")
        return None
    finally:
        _matching.release()


_listing = threading.Lock()


def match_all():
    """On each connect: the whole conversation list (inbox and archive) read and matched; one read at a time."""
    if not _listing.acquire(blocking=False):
        return None
    try:
        _note(matched_at=_now())
        got = _call({"cmd": "convs"}, timeout=900)
    finally:
        _listing.release()
    if got and got.get("ok"):
        return match(got.get("convs") or [], whole=True)
    common.log_line(TEXTS_LOG, "link: the conversation list could not be read" + (f" ({got.get('error')})" if got and got.get("error") else ""))
    return None


_build = []


def build():
    """The companion's build, as a short fingerprint of its program file ("" when it is not there)."""
    if not _build:
        try:
            with open(EXE, "rb") as f:
                _build.append(hashlib.sha1(f.read()).hexdigest()[:12])
        except OSError:
            return ""
    return _build[0]


def _week_us():
    return int((time.time() - 7 * 86400) * 1_000_000)


def deep_catchup(key=DEEP_CATCHUP):
    """Once for each key: every text of the last week the link can reach is read and stored (one already held is skipped, never
    stored twice; a picture for a text stored before the link is filled into it), so texts and pictures missed before the link
    took over come in. Says what it found in the texts log."""
    from connections import _store
    before = _store.filled[0]
    _write({"cmd": "since", "us": _week_us()})
    got = _call({"cmd": "catchup"}, timeout=330)
    if got and got.get("ok"):
        time.sleep(5)                       # the last rows are stored by the store loop
        _note(**{key: _now()})
        if key == PICTURES_CATCHUP:
            _note(**{PICTURES_BUILD: build()})
        common.log_line(TEXTS_LOG, "link: the one week catch-up ran" + (" for pictures" if key == PICTURES_CATCHUP else "")
                        + ("; it found texts not seen before" if got.get("gap") else "; nothing was missing")
                        + f"; pictures filled into texts stored before the link: {_store.filled[0] - before}")
        newest = _catchup_from_us()
        if newest:
            _write({"cmd": "since", "us": newest})      # from here on, catch-up starts at the newest stored text (or a placeholder) again
    return got


def remove_duplicates():
    """Once: texts stored twice before the link are kept once (texts.remove_duplicates). Logged as a count."""
    try:
        import texts
        n = texts.remove_duplicates()
        _note(**{DUPLICATES: _now(), DUPLICATES_RULE: RULE})
        common.log_line(TEXTS_LOG, f"link: texts stored twice before the link, kept once: {n} removed")
        return n
    except Exception as e:  # noqa: BLE001  tried again on the next beat
        common.log_line(TEXTS_LOG, f"link: removing texts stored twice failed ({type(e).__name__}: {str(e)[:200]}); tried again")
        return None


def _catchup_from_us():
    """Where the link's catch-up starts: the newest stored text, or earlier, the oldest of the last week's texts from the link still
    stored as a picture's placeholder with no picture (its picture was still coming), so the next catch-up fills it in."""
    import db
    from connections import _store
    try:
        con = db.try_connect(read_only=True)
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        return 0
    try:
        ts = con.execute("SELECT max(ts) FROM messages WHERE channel='sms'").fetchone()[0]
        bare = con.execute("SELECT min(m.ts) FROM messages m WHERE m.channel='sms' AND m.provider_id LIKE 'gl:%' AND m.body = ? AND m.ts >= ? "
                           "AND NOT EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)",
                           [_store.NO_TEXT, dt.datetime.fromtimestamp(_week_us() / 1_000_000)]).fetchone()[0]
    finally:
        con.close()
    if bare and (not ts or bare < ts):
        ts = bare - dt.timedelta(seconds=1)         # the catch-up reads texts after this time
    return int(ts.timestamp() * 1_000_000) if ts else 0


# --- received texts ------------------------------------------------------------------------------------------------
def _held():
    try:
        with open(HOLD, encoding="utf-8") as f:
            until = json.load(f).get("until")
        return bool(until) and dt.datetime.now() < dt.datetime.fromisoformat(until)
    except (OSError, ValueError, AttributeError):
        return False


def _store_loop():
    while not _stopping.is_set():
        try:
            batch = [_rows.get(timeout=5)]
        except queue.Empty:
            batch = []
        t0 = time.time()
        while batch and len(batch) < 200 and time.time() - t0 < 1.0:
            try:
                batch.append(_rows.get(timeout=0.3))
            except queue.Empty:
                break
        if batch or (common.read_json(PENDING, {}) or {}).get("rows"):
            try:
                store(batch)
            except Exception as e:  # noqa: BLE001  a store that fails keeps its texts in the waiting file for the next try
                common.log_line(TEXTS_LOG, f"link: storing failed ({type(e).__name__}: {str(e)[:200]}); kept for the next try")
                time.sleep(10)


def _key(number):
    from connections import _store
    return _store.phone_key(number) if str(number or "").strip() else None


def to_row(raw):
    """One row from the companion as the text store takes it (pictures read from their files)."""
    from connections import _store
    conv, mid = str(raw.get("conv") or "")[:120], str(raw.get("id") or "")[:200]
    us = int(raw.get("ts_us") or 0)
    if not (conv and mid and us) or raw.get("direction") not in ("in", "out"):
        return None
    ts = dt.datetime.fromtimestamp(us / 1_000_000)
    direction = raw["direction"]
    others = [o for o in (raw.get("others") or []) if isinstance(o, dict)]
    sender = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}
    conv_name = " ".join(str(raw.get("conv_name") or "").split())[:200]
    if raw.get("group"):
        key = _key(sender.get("number")) if direction == "in" else None
        name = str(sender.get("name") or "") if direction == "in" else ""
        subject = conv_name or ", ".join(str(o.get("name") or o.get("number") or "") for o in others)[:200]
    else:
        other = others[0] if others else sender
        key = _key(other.get("number"))
        name = str(other.get("name") or "") or conv_name
        subject = conv_name or name
    media = []
    for f in raw.get("media") or []:
        path = str((f or {}).get("path") or "")
        if path and os.path.isfile(path) and os.path.dirname(os.path.abspath(path)) == os.path.abspath(MEDIA):
            with open(path, "rb") as fh:
                data = fh.read()
            media.append((os.path.splitext(path)[1].lower(), str(f.get("name") or os.path.basename(path)), data,
                          str(f.get("mime") or "").startswith("image/")))
    text = str(raw.get("text") or "").strip()[:20000]
    if not text and not media and not raw.get("media") and not raw.get("pending"):     # a picture still coming is stored as its placeholder
        return None
    full = bool(media) and len(media) == len(raw.get("media") or []) and all((f or {}).get("full") for f in raw["media"])
    return {"provider_id": f"gl:{conv}:{mid}", "thread": f"gl:{conv}", "ts": ts, "direction": direction, "key": key, "name": name,
            "subject": subject or None, "text": text or _store.NO_TEXT, "media": media, "full": full}


def _drop_files(raws):
    for raw in raws:
        for f in raw.get("media") or []:
            path = str((f or {}).get("path") or "")
            if path and os.path.dirname(os.path.abspath(path)) == os.path.abspath(MEDIA):
                try:
                    os.remove(path)
                except OSError:
                    pass


def store(batch):
    """Stores the companion's rows (and any left waiting). Returns (stored, already held). While an update holds the
    database, or a pass holds it now, they wait in a file."""
    from connections import _store
    filled0, up0 = _store.filled[0], list(_store.upgraded)
    waiting = (common.read_json(PENDING, {}) or {}).get("rows") or []
    raws = [r for r in waiting + list(batch) if isinstance(r, dict)]
    if not raws:
        return 0, 0
    import replay_guard
    import onboard
    if _held() or replay_guard.import_blocked() or onboard.holding():     # an update, the day-by-day rebuild, or the setup's
        # history catalog still being built (no new message comes in before it): they wait in the file
        common.write_json(PENDING, {"rows": raws[-20000:]})
        return 0, 0
    groups = {f"gl:{r.get('conv')}" for r in raws if r.get("group") and r.get("conv")}
    if groups:
        have = (common.read_json(GROUPS, {}) or {}).get("convs") or []
        if not groups <= set(have):
            common.write_json(GROUPS, {"convs": sorted(set(have) | groups)[-5000:]})
    rows, by_pid = [], {}
    older = {}                              # the link's conversation -> the threads stored before the link that were matched to it
    for t, v in ((common.read_json(os.path.join(common.paths.STATE, "texts_link_convs.json"), {}) or {}).get("threads") or {}).items():
        if isinstance(v, dict) and v.get("gl"):
            older.setdefault(str(v["gl"]), []).append(t)
    for raw in raws:
        r = to_row(raw)
        if r:
            r["older_threads"] = older.get(str(raw.get("conv") or ""), [])
            rows.append(r)
            by_pid[r["provider_id"]] = raw
    try:
        written, held, _q = _store.text_messages(rows)
        left = []
    except _store.Deferred as e:
        written, held, _q = e.counts
        left = [by_pid[r["provider_id"]] for r in e.rest if r["provider_id"] in by_pid]
    common.write_json(PENDING, {"rows": left})
    keep = {id(x) for x in left}
    _drop_files([r for r in raws if id(r) not in keep])
    if written:
        _note(last_text=_now())
    if written or _store.filled[0] != filled0:         # a new text, or a picture filled into an older one: the page's copy again
        try:
            import texts_cache
            if texts_cache.ON:
                texts_cache.refresh()
        except Exception:  # noqa: BLE001  the copy is only for speed
            pass
    common.log_line(TEXTS_LOG, f"link: received {len(raws)}, stored {written}, already held {held}, waiting for the database {len(left)}"
                    + (f"; pictures filled into texts stored before the link {_store.filled[0] - filled0}" if _store.filled[0] != filled0 else "")
                    + (f"; pictures replaced by their full size {_store.upgraded[0] - up0[0]} ({(_store.upgraded[1] - up0[1]) // 1024} KB to "
                       f"{(_store.upgraded[2] - up0[2]) // 1024} KB)" if _store.upgraded[0] != up0[0] else ""))
    return written, held


# --- sending ---------------------------------------------------------------------------------------------------------
def owns(item):
    """A queued text goes out through the link when the link is signed in and knows where to send it (its Messages
    conversation here, or a number)."""
    return signed_in() and bool(item.get("gl") or item.get("phone"))


def kick():
    _kick.set()


def _send_loop():
    import replay_guard
    replay_guard.refuse("the texts link's sending")
    import texts
    while not _stopping.is_set():
        _kick.wait(5)
        _kick.clear()
        if _stopping.is_set():
            return
        p = _proc
        if p is None or p.poll() is not None or not connected():
            continue                    # a text is taken only by a link that is running and connected
        while True:
            item = texts.next_send(for_link=True)
            if not item:
                break
            got = _call({"cmd": "send", "conv": item.get("gl") or "", "phone": item.get("phone") or "", "text": item["text"], "tmp": ""},
                        timeout=120)
            if got is None:
                texts.report(item["id"], False, "The texts link did not answer, so it is not known whether it went. Look on your phone before you send it again.")
            else:
                texts.report(item["id"], bool(got.get("ok")), got.get("error") or "")
            common.log_line(TEXTS_LOG, "link: a text was sent" if got and got.get("ok") else "link: a text did not go" + (" (unsure)" if got and got.get("unsure") else ""))


# --- sign-in ---------------------------------------------------------------------------------------------------------
def parse_cookies(text):
    """The cookies out of whatever he pasted: a cURL command copied from Firefox, a Cookie line, a JSON object or list,
    or name and value pairs one per line. Returns ({name: value} of the wanted ones, [missing required names])."""
    text = str(text or "")[:30000]
    found = {}
    try:
        j = json.loads(text)
    except ValueError:
        j = None
    if isinstance(j, dict):
        found = {k: str(j[k]) for k in WANTED if isinstance(j.get(k), (str, int))}
    elif isinstance(j, list):
        for c in j:
            if isinstance(c, dict) and c.get("name") in WANTED and c.get("value") is not None:
                found[c["name"]] = str(c["value"])
    else:
        t = text.replace("^\"", "\"").replace("^", "") if "^\"" in text else text       # the Windows form of cURL escapes with ^
        heads = re.findall(r"(?i)(?:cookie:\s*|(?:^|\s)(?:-b|--cookie)\s+['\"]?)([^'\"\r\n]+)", t)
        pairs = []
        for h in heads:
            pairs += [p.split("=", 1) for p in h.split(";") if "=" in p]
        if not pairs:
            for line in t.splitlines():
                m = re.match(r"\s*([A-Za-z0-9_-]+)\s*(?:=|:|\t)\s*([^\s\t;]+)", line)
                if m:
                    pairs.append([m.group(1), m.group(2)])
        for k, v in pairs:
            k, v = k.strip(), v.strip().strip("'\"")
            if k in WANTED and v and k not in found:
                found[k] = v
    found = {k: v for k, v in found.items() if v and len(v) < 4000}
    return found, [k for k in REQUIRED if k not in found]


def pair(cookie_text):
    """Sign in with the cookies he pasted; returns {"ok", "emoji"} or {"ok": False, "error"}. The cookies go to the link
    only, in its input; they are not logged or kept here."""
    cookies, missing = parse_cookies(cookie_text)
    if missing:
        return {"ok": False, "error": "These cookies were not found in what you pasted: " + ", ".join(missing)
                + ". Copy the request again as the steps say, and paste all of it."}
    if not _started[0] or _proc is None:
        return {"ok": False, "error": "The texts link is not running on this computer, so it cannot sign in now."}
    _note(pair_error="")
    got = _call({"cmd": "pair", "cookies": cookies}, timeout=120)
    if got is None:
        return {"ok": False, "error": "The texts link did not answer. Try again in a minute."}
    if got.get("ok"):
        _note(state="pairing", emoji=got.get("emoji") or "", say="", beat=_now())
        return {"ok": True, "emoji": got.get("emoji") or ""}
    return {"ok": False, "error": str(got.get("error") or "Google did not accept the sign-in.")[:400]}


def cancel_pair():
    got = _call({"cmd": "cancel_pair"}, timeout=10)
    _note(emoji="")
    return {"ok": bool(got and got.get("ok"))}
