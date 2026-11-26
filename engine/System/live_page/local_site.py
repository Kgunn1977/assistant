r"""The page served from the owner's own computer: no web host and no PHP.

It is the same page as the hosted one (the files in site\app, made from page.html) behind the same doors
as site\index.php: sign-in with a password set once at a one-time address, the page's data and answers for a
signed-in browser, and the feed door for the engine's key. It runs as threads inside the listener
(listen.py starts it); nothing here starts a program of its own.

    python local_site.py --setup      makes a one-time address where the owner sets the page's password
                                      and prints it once (add --open to open it in the browser instead;
                                      add --public to make it for the page's public address, when it has one)

Reach    It listens on 127.0.0.1 only and refuses any request whose Host is not one of its own names: this
         computer's local address, and, when the owner switched on being reached from anywhere (page_reach in the
         home's settings, written only by the setup window), this home's own public name and port. That relay
         (Tailscale Funnel) hands each request to this same server from 127.0.0.1 with the public name as its
         Host and the visitor's address in X-Forwarded-For. A request that came by the public name:
           - gets a sign-in cookie marked Secure, and must come from the https page itself to change anything;
           - is never let through the engine's own doors (the feed key works only at this computer);
           - has its wrong passwords counted apart from sign-ins made at this computer: 5 from one visitor,
             or 20 from all visitors together, in 15 minutes lock sign-in from outside for the rest of that
             time. Sign-in at this computer itself is never locked by anything done from outside, and a
             browser already signed in stays signed in.
         Every request has a size limit and a time limit, and only so many are served at once.
Keeps    Its data in the home's page_state\local_site: the password's hash, sign-ins, the feed and the answers.
         The feed key for the engine's own programs is in the personal folder's local_settings.json.
Never    prints or logs a password, a sign-in or the feed key.
"""
import base64
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish  # noqa: E402  the same folder's sender: paths and the hosting setting

APP = os.path.join(HERE, "site", "app")
EC = os.path.join(HERE, "vendor", "event-calendar-5.21.1")      # the Calendar part's EventCalendar, as its makers ship it
DATA = os.path.join(publish.STATE, "local_site")
HOLD = os.path.join(publish.HOME, "state", "update_hold.json")   # written by an update for its check pass (scripts/assistant.py)
HOLD_OPEN = ("api/feed", "api/progress", "api/wait", "api/files")  # what the check pass itself uses: never held (and its own answers read)


def update_hold():
    """True while an update's check pass holds the database: its file names a time not yet passed (a hold left by an update
    that was cut off ends by itself)."""
    try:
        with open(HOLD, encoding="utf-8") as f:
            until = json.load(f).get("until")
        return bool(until) and dt.datetime.now() < dt.datetime.fromisoformat(until)
    except (OSError, ValueError, AttributeError):
        return False
SESSION_SECONDS = 90 * 86400    # how long a sign-in lasts unless the owner chose another length in Settings
SIGNIN_DAYS = (1, 7, 30, 90)
WINDOW = 900                 # wrong tries are counted over 15 minutes
PASS_TRIES = 5               # wrong passwords before sign-in is locked for the rest of the window
KEY_TRIES = 10               # wrong feed keys before the feed door is locked for the rest of the window
MAX_BODY = 6_000_000         # the engine's feed, which only arrives at this computer itself
PAGE_BODY = 400_000          # anything a signed-in browser sends (an answer holds at most 60,000 characters)
FORM_BODY = 10_000           # a sign-in or set-up form
UPLOAD_BODY = 15_000_000     # a file the owner adds to an email from his computer (the Mail part)
OUTSIDE_TRIES = 20           # wrong passwords from all outside visitors together before sign-in from outside is locked
REQUEST_SECONDS = 20         # a connection that sends nothing for this long is dropped
MOST_AT_ONCE = 200           # connections served at the same time; more than this are turned away at once
MIN_PASSWORD = 10
HOLD_ENGINE = 25             # seconds the listener's own line waits for an answer
HOLD_PAGE = 20               # seconds an open page's line is held open waiting for a change
ACTIONS = ("approve", "change", "answer", "done", "later", "snooze", "reopen")
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; frame-src 'self'; form-action 'self'; "
       "base-uri 'none'; frame-ancestors 'none'; manifest-src 'self'")
# the manual (manual.html, made by the package build) is one finished page with its own style and script inline and no network use:
# it gets its own, narrower-than-nothing policy (inline allowed, nothing fetched, no form, never framed) and only after sign-in
# the one copy of the manual: <root>\docs\Assistant manual.html, put there by the package's lay-down and update (no other copy, no fallback)
MANUAL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "Assistant manual.html")
# a paper opened over the page (a PDF in a frame of the page itself, a picture as a picture): nothing it may run or fetch
VIEW_KINDS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
              ".webp": "image/webp"}
VIEW_CSP = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; frame-ancestors 'self'"
# an email as it was sent, in a frame of the Mail part: no script, no form, nothing sent anywhere; its pictures only from this
# computer (its own, kept as attachments) unless Settings shows them (the default) or the owner pressed Show pictures for it; opened alone, it is still sandboxed
BODY_CSP = ("default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src data:; "
            "form-action 'none'; base-uri 'none'; frame-ancestors 'self'; sandbox allow-same-origin allow-popups allow-popups-to-escape-sandbox")
BODY_CSP_PICTURES = BODY_CSP.replace("img-src 'self' data:", "img-src 'self' data: https: http:").replace("font-src data:", "font-src data: https:")
MANUAL_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; "
              "frame-src about: data: blob:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")

changed = threading.Condition(threading.RLock())    # held for every read and write of the stores below
mem = {"feed": None, "answers": None, "sessions": None}
wrong = {"login": [], "feed": [], "outside": {}}       # "outside": wrong passwords by visitor, for requests that came by the public name
wrong_keys_total = 0


# --- small stores, each one JSON file in the home ---------------------------------------------------
def _file(name):
    return os.path.join(DATA, name + ".json")


def _load(name):
    if name != "config" and mem.get(name) is not None:
        return mem[name]
    got = publish.read_json(_file(name), None)
    got = got if isinstance(got, dict) else {}
    if name != "config":
        mem[name] = got
    return got


def _save(name, value):
    publish.write_json(_file(name), value)
    if name != "config":
        mem[name] = value


def address():
    return f"http://127.0.0.1:{publish.page_port()}"


def cookie_name():
    """Browsers keep one cookie jar for every port of this computer, so each copy's page names its sign-in by its port."""
    return f"brief_local_{publish.page_port()}"


def local_hosts():
    port = publish.page_port()
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def public_hosts():
    """The Host names of this home's own public address, when the owner switched on being reached from anywhere
    and this computer serves the page; empty otherwise. Read from the home's settings at each request, so
    switching it off in the setup window closes the door at once."""
    got = (publish.read_json(os.path.join(publish.HOME, "personal", "settings.json")) or {}).get("page_reach")
    if not isinstance(got, dict) or got.get("how") != "tailscale":
        return set()
    m = re.fullmatch(r"https://([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)(?::(\d{2,5}))?/?",
                     str(got.get("address") or "").strip().lower())
    if not m:
        return set()
    name, port = m.group(1), int(m.group(2) or 443)
    return {f"{name}:{port}"} | ({name} if port == 443 else set())


def public_address():
    """The page's public address ("" when there is none), for the one-time set-up address."""
    got = sorted(public_hosts(), key=len)
    return "https://" + got[0] if got else ""


def allowed_hosts():
    """The names a browser may call this page by: this computer's own, and this home's own public name. Nothing else."""
    return local_hosts() | public_hosts()


def ensure_key():
    """The feed key the engine's own programs use for this page: made once, kept beside the hosted page's key."""
    with changed:
        own = publish.read_json(publish.SETTINGS, None)
        own = own if isinstance(own, dict) else {}
        cfg = _load("config")
        key = own.get("local_feed_key")
        if not key:
            key = secrets.token_urlsafe(48)
            own["local_feed_key"] = key
            publish.write_json(publish.SETTINGS, own)
        want = hashlib.sha256(key.encode()).hexdigest()
        if cfg.get("feed_key") != want:
            cfg["feed_key"] = want
            _save("config", cfg)


def make_setup(public=False):
    """A one-time address, good for 7 days, where the owner sets this page's password. With public it is made
    for the page's public address (for an owner who is at their phone); the same one-time code works at either."""
    code = secrets.token_urlsafe(32)
    with changed:
        cfg = _load("config")
        cfg["setup"] = {"hash": hashlib.sha256(code.encode()).hexdigest(), "exp": int(time.time()) + 7 * 86400}
        _save("config", cfg)
    return f"{(public and public_address()) or address()}/setup#{code}"


def password_is_set():
    return bool(_load("config").get("pass"))


def session_seconds():
    """How long a new sign-in lasts: the owner's choice in Settings, as the engine last sent it with the
    page's data (settings.signin.days), else 90 days."""
    days = (((_load("feed").get("docs") or {}).get("current") or {}).get("settings") or {}).get("signin") or {}
    days = days.get("days") if isinstance(days, dict) else None
    return days * 86400 if days in SIGNIN_DAYS and not isinstance(days, bool) else SESSION_SECONDS


def _hash_password(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    got = hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(got).decode()


def _password_ok(pw, stored):
    try:
        kind, salt, _got = str(stored).split("$")
        return kind == "scrypt" and hmac.compare_digest(_hash_password(pw, base64.b64decode(salt)), stored)
    except (ValueError, TypeError):
        return False


def _wait_seconds(bucket, tries):
    now = time.time()
    wrong[bucket] = [t for t in wrong[bucket] if t > now - WINDOW]
    return max(0, int(wrong[bucket][-tries] + WINDOW - now)) if len(wrong[bucket]) >= tries else 0


def _outside_wait(who):
    """Seconds sign-in stays locked for this outside visitor: after PASS_TRIES wrong passwords of their own, or
    OUTSIDE_TRIES from all outside visitors together, inside the window. Sign-in at this computer is not counted here."""
    now, per = time.time(), wrong["outside"]
    for k in list(per):
        per[k] = [t for t in per[k] if t > now - WINDOW]
        if not per[k]:
            del per[k]
    mine = per.get(who) or []
    every = sorted(t for v in per.values() for t in v)
    wait = 0
    if len(mine) >= PASS_TRIES:
        wait = max(wait, mine[-PASS_TRIES] + WINDOW - now)
    if len(every) >= OUTSIDE_TRIES:
        wait = max(wait, every[-OUTSIDE_TRIES] + WINDOW - now)
    return max(0, int(wait))


def _outside_wrong(who):
    per = wrong["outside"]
    if who not in per and len(per) >= 500:      # never grows without end, whatever addresses are claimed
        who = "many"
    per.setdefault(who, []).append(time.time())


# --- the page's own files -----------------------------------------------------------------------------
def files_mark():
    """A short mark of the page files this computer serves. An open page loads the newer page when it changes."""
    h = hashlib.sha1()
    for name in ("app.css", "app.js", "shell.html"):
        try:
            with open(os.path.join(APP, name), "rb") as f:
                h.update(hashlib.sha256(f.read().replace(b"\r", b"")).hexdigest().encode())
        except OSError:
            h.update(b"-")
    return h.hexdigest()[:12]


def desk_title():
    t = ((_load("feed").get("docs") or {}).get("current") or {}).get("page_title")
    return t.strip()[:80] if isinstance(t, str) and t.strip() else "Your desk"


def desk_user():
    m = re.match(r"[A-Za-z]+", desk_title())
    return m.group(0).lower() if m else "owner"


def page_head(title, css, js):
    e = html.escape
    o = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
         '<meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="same-origin">'
         f"<title>{e(title)}</title>"
         '<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&amp;'
         'family=IBM+Plex+Sans+Condensed:wght@500;600;700&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap">')
    # so a phone can put the page on its home screen: the web app manifest, its icon, and the bar colour
    o += ('<link rel="manifest" href="/s/app.webmanifest"><link rel="icon" type="image/png" href="/s/icon-192.png">'
          '<link rel="apple-touch-icon" href="/s/icon-192.png"><meta name="theme-color" content="#1f3a5f">'
          '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
          '<meta name="apple-mobile-web-app-title" content="Assistant">')
    o += "".join(f'<link rel="stylesheet" href="/s/{e(c)}">' for c in css)
    o += "".join(f'<script src="/s/{e(j)}" defer></script>' for j in js)
    return o + "</head><body>"


def sign_in_page(say=""):
    e = html.escape
    return (page_head("Sign in", ["login.css"], [])
            + f'<main class="box"><h1>{e(desk_title())}</h1><p class="sub">Sign in to open the page.</p>'
            + (f'<p class="say" role="alert">{e(say)}</p>' if say else "")
            + '<form method="post" action="/login" autocomplete="on">'
            + f'<input type="text" name="username" value="{e(desk_user())}" autocomplete="username" hidden>'
            + '<label for="p">Password</label><input id="p" type="password" name="password" autocomplete="current-password" required autofocus>'
            + '<button type="submit">Sign in</button></form></main></body></html>')


def setup_page(say=""):
    e = html.escape
    return (page_head("Set your password", ["login.css"], ["login.js"])
            + f'<main class="box"><h1>{e(desk_title())}</h1><p class="sub">Choose the password for this page. This address works once.</p>'
            + (f'<p class="say" role="alert">{e(say)}</p>' if say else "")
            + '<form method="post" action="/setup" id="setup" autocomplete="on"><input type="hidden" name="token" id="token">'
            + f'<input type="text" name="username" value="{e(desk_user())}" autocomplete="username" hidden>'
            + f'<label for="p1">New password, {MIN_PASSWORD} characters or more</label><input id="p1" type="password" name="password" autocomplete="new-password" minlength="{MIN_PASSWORD}" required autofocus>'
            + f'<label for="p2">The same password again</label><input id="p2" type="password" name="again" autocomplete="new-password" minlength="{MIN_PASSWORD}" required>'
            + '<button type="submit">Set password and sign in</button></form></main></body></html>')


# --- what the listener and the feed door do, in this program --------------------------------------------
def _answers():
    a = _load("answers")
    a.setdefault("items", {})
    a.setdefault("undone", {})
    a.setdefault("v", 0)
    a.setdefault("av", 0)
    return a


def _apply_marks(items, marks):
    hit = False
    for m in marks or []:
        if not isinstance(m, (list, tuple)) or len(m) < 3 or m[0] not in items or items[m[0]].get("at") != m[1] \
                or m[2] not in ("working", "done", "failed"):
            continue
        items[m[0]]["status"] = m[2]
        items[m[0]]["outcome"] = m[3][:2000] if len(m) > 3 and isinstance(m[3], str) else ""
        items[m[0]]["as_of"] = m[4][:40] if len(m) > 4 and isinstance(m[4], str) else ""
        hit = True
    return hit


def take_feed(body):
    """The engine's items for the page, with any answers to clear and how far each answer has got."""
    docs = (body or {}).get("docs")
    if not isinstance(docs, dict) or not isinstance(docs.get("current"), dict) or "built" not in docs["current"]:
        return None
    with changed:
        _save("feed", {"docs": docs, "received": dt.datetime.now().isoformat(timespec="seconds")})
        a = _answers()
        hit = False
        for c in body.get("clear") or []:
            if isinstance(c, (list, tuple)) and len(c) == 2 and c[0] in a["items"] and a["items"][c[0]].get("at") == c[1]:
                del a["items"][c[0]]
                hit = True
        hit = _apply_marks(a["items"], body.get("progress")) or hit
        if hit:
            a["v"] += 1
            _save("answers", a)
        changed.notify_all()
        return {"ok": True, "built": docs["current"].get("built"), "stamp": docs["current"].get("stamp"),
                "answers": dict(a["items"]), "wrong_keys": wrong_keys_total, "damaged_files": []}


def mark(marks):
    with changed:
        a = _answers()
        if _apply_marks(a["items"], marks):
            a["v"] += 1
            _save("answers", a)
            changed.notify_all()
    return {"ok": True}


def wait(since, hold=HOLD_ENGINE):
    """The listener's line: comes back the moment the owner answers something, or when the hold runs out."""
    end = time.time() + hold
    with changed:
        while _answers()["av"] == since and time.time() < end:
            changed.wait(max(0.05, end - time.time()))
        a = _answers()
        return {"ok": True, "av": a["av"], "changed": a["av"] != since, "held": hold, "answers": json.loads(json.dumps(a["items"])),
                "undone": dict(a["undone"])}


def refresh_feed():
    """When the page starts being served: show the items as they are now, not as they were when it last stopped."""
    try:
        docs, _ = publish.build(publish.ITEMS_JSON)
        take_feed({"docs": docs})
    except BaseException:  # noqa: BLE001  no items yet (a new home): the page says it is waiting
        pass


# --- one request -------------------------------------------------------------------------------------------
class Door(BaseHTTPRequestHandler):
    server_version = "page"
    sys_version = ""
    timeout = REQUEST_SECONDS           # a connection that goes quiet is dropped, so slow ones cannot hold every thread
    outside = False                     # True for a request that came by this home's public name (through the relay)

    def send_error(self, code, message=None, explain=None):
        """A request this server cannot read gets a bare status: no page, no words about this computer."""
        try:
            self.close_connection = True
            self.send_response(code if isinstance(code, int) and 400 <= code < 600 else 400)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
        except Exception:  # noqa: BLE001
            pass

    def _visitor(self):
        """Who an outside request came from, as the relay reports it; one shared name when it does not say."""
        first = (self.headers.get("X-Forwarded-For") or "").split(",")[-1].strip()      # the last one is the relay's own word
        return first[:64] if re.fullmatch(r"[0-9A-Fa-f:.]{3,64}", first) else "unknown"

    def _locked(self):
        with changed:
            return _outside_wait(self._visitor()) if self.outside else _wait_seconds("login", PASS_TRIES)

    def _count_wrong(self):
        with changed:
            if self.outside:
                _outside_wrong(self._visitor())
            else:
                wrong["login"].append(time.time())

    def _clear_wrong(self):
        with changed:
            if self.outside:
                wrong["outside"].pop(self._visitor(), None)
            else:
                wrong["login"] = []

    def log_message(self, *a):          # nothing about a request is written anywhere
        pass

    # replies
    def _send(self, code, body, kind, extra=(), csp=None, frame=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        for k, v in (("Content-Type", kind), ("Content-Length", str(len(data))), ("Cache-Control", "no-store, private, max-age=0"),
                     ("X-Robots-Tag", "noindex, nofollow, noarchive, nosnippet"), ("X-Content-Type-Options", "nosniff"),
                     ("X-Frame-Options", frame or "DENY"), ("Referrer-Policy", "same-origin"), ("Cross-Origin-Opener-Policy", "same-origin"),
                     ("Cross-Origin-Resource-Policy", "same-origin"),
                     ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"),
                     ("Content-Security-Policy", csp or CSP)) + tuple(extra):
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, code, obj, extra=()):
        self._send(code, json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026"),
                   "application/json; charset=utf-8", extra)

    def _html(self, code, text, extra=()):
        self._send(code, text, "text/html; charset=utf-8", extra)

    def _go_home(self, extra=()):
        self._send(303, b"", "text/plain", (("Location", "/"),) + tuple(extra))

    def _static_bytes(self, name, kind):
        try:
            with open(os.path.join(APP, name), "rb") as f:
                self._send(200, f.read(), kind, (("Cache-Control", "public, max-age=86400"),))
        except OSError:
            self._send(404, b"", "text/plain")

    def _static(self, name, kind):
        try:
            with open(os.path.join(APP, name), "rb") as f:
                self._send(200, f.read(), kind + "; charset=utf-8")
        except OSError:
            self._send(404, b"", "text/plain")

    # what came in
    def _body(self, most=MAX_BODY):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > most or n < 0 or self.headers.get("Transfer-Encoding"):
            self.close_connection = True        # what was sent is not read; the connection ends with the reply
            return None
        return self.rfile.read(n) if n > 0 else b""

    def _body_json(self, most=MAX_BODY):
        raw = self._body(most)
        if raw is None:
            self._json(413, {"error": "too large"})
            return None
        try:
            got = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            got = None
        if not isinstance(got, dict):
            self._json(400, {"error": "not understood"})
            return None
        return got

    def _form(self):
        raw = self._body(FORM_BODY) or b""
        return {k: v[0] for k, v in parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True).items()}

    def _same_origin(self):
        o = self.headers.get("Origin") or ""
        return o == "" or o.lower() == ("https://" if self.outside else "http://") + (self.headers.get("Host") or "").lower()

    def _cookie(self, token, expires):
        when = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(expires))
        return ("Set-Cookie", f"{cookie_name()}={token}; Expires={when}; Path=/; HttpOnly; SameSite=Lax"
                + ("; Secure" if self.outside else ""))       # by the public name the page is https, so the sign-in never travels in the clear

    def _session(self):
        tok = ""
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == cookie_name():
                tok = v
        if not 40 <= len(tok) <= 200:
            return None
        sid, now = hashlib.sha256(tok.encode()).hexdigest(), int(time.time())
        with changed:
            every = _load("sessions")
            s = every.get(sid)
            if not s or s.get("exp", 0) < now:
                return None
            if now - s.get("seen", 0) > 86400:          # slide the sign-in's own length forward, once a day
                s["seen"], s["exp"] = now, now + int(s.get("len") or SESSION_SECONDS)
                _save("sessions", every)
            return dict(s, id=sid)

    def _open_session(self):
        tok, now = secrets.token_urlsafe(48), int(time.time())
        with changed:
            lasts = session_seconds()
            every = {k: v for k, v in _load("sessions").items() if v.get("exp", 0) > now}
            every = dict(sorted(every.items(), key=lambda kv: -kv[1].get("seen", 0))[:19])      # at most 20 devices signed in
            every[hashlib.sha256(tok.encode()).hexdigest()] = {"made": now, "seen": now, "exp": now + lasts, "len": lasts,
                                                                "csrf": secrets.token_hex(32)}
            _save("sessions", every)
        return self._cookie(tok, now + lasts)

    def _key_ok(self):
        global wrong_keys_total
        with changed:
            locked = _wait_seconds("feed", KEY_TRIES)
        if locked:
            self._json(429, {"error": "locked", "retry_in": locked}, (("Retry-After", str(locked)),))
            return False
        key, want = self.headers.get("X-Brief-Key") or "", _load("config").get("feed_key") or ""
        if not key or not want or not hmac.compare_digest(want, hashlib.sha256(key.encode()).hexdigest()):
            with changed:
                wrong["feed"].append(time.time())
                wrong_keys_total += 1
            time.sleep(0.4)
            self._json(403, {"error": "refused"})
            return False
        return True

    # the doors
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_HEAD(self):
        self._route("GET")

    def _route(self, method):
        try:
            self._answer(method)
        except (BrokenPipeError, ConnectionError):
            pass
        except Exception:  # noqa: BLE001  one bad request never stops the page
            try:
                self._json(500, {"error": "trouble"})
            except Exception:  # noqa: BLE001
                pass

    def _answer(self, method):
        host = (self.headers.get("Host") or "").lower()
        self.outside = host not in local_hosts() and host in public_hosts()
        if not self.outside and host not in local_hosts():
            self.close_connection = True
            return self._send(403, b"", "text/plain")       # not one of this page's own names: refused before anything else
        if len(self.path) > 2000:
            self.close_connection = True
            return self._send(414, b"", "text/plain")
        route = urlparse(self.path).path.strip("/")
        if route.startswith("api/") and route not in HOLD_OPEN and not (route == "api/answers" and self.headers.get("X-Brief-Key"))                 and update_hold():
            # an update's check pass has the database: the page asks again shortly; nothing is lost
            return self._json(503, {"error": "updating", "say": "I'm being updated; this page comes back in a minute."},
                              (("Retry-After", "30"),))
        cfg = _load("config")
        if self.outside and route in ("api/feed", "api/progress", "api/files", "api/wait") or \
                (self.outside and route == "api/answers" and self.headers.get("X-Brief-Key") is not None):
            self.close_connection = True                    # the engine's own doors open only at this computer itself
            return self._send(404, b"", "text/plain")

        # engine side: the feed key only
        if route == "api/feed" and method == "POST":
            if not self._key_ok():
                return None
            body = self._body_json()
            if body is None:
                return None
            out = take_feed(body)
            return self._json(200, out) if out else self._json(400, {"error": "no feed in the request"})
        if route == "api/progress" and method == "POST":
            if not self._key_ok():
                return None
            body = self._body_json()
            return None if body is None else self._json(200, mark(body.get("marks") if isinstance(body.get("marks"), list) else []))
        if route == "api/files" and method == "GET" and self.headers.get("X-Brief-Key") is not None:
            if not self._key_ok():
                return None
            hashes = {}
            for name in publish.PAGE_FILES:     # exactly what a browser is served: read from the folder at this moment
                try:
                    with open(os.path.join(APP, name), "rb") as f:
                        hashes[name] = hashlib.sha256(f.read().replace(b"\r", b"")).hexdigest()
                except OSError:
                    hashes[name] = ""
            return self._json(200, {"ok": True, "hashes": hashes})
        if route == "api/answers" and method == "GET" and self.headers.get("X-Brief-Key") is not None:
            if not self._key_ok():
                return None
            with changed:
                return self._json(200, {"ok": True, "answers": dict(_answers()["items"])})

        # sign-in, setup
        if route == "login" and method == "POST":
            form = self._form()
            if not self._same_origin():
                return self._html(403, sign_in_page("That request did not come from this page."))
            locked = self._locked()
            if locked:
                return self._html(429, sign_in_page(f"Too many wrong passwords. Try again in {-(-locked // 60)} minutes."),
                                  (("Retry-After", str(locked)),))
            pw = form.get("password") or ""
            if cfg.get("pass") and pw and len(pw) <= 1000 and _password_ok(pw, cfg["pass"]):
                self._clear_wrong()
                return self._go_home((self._open_session(),))
            self._count_wrong()
            time.sleep(1)
            return self._html(401, sign_in_page("That password is not right."))
        if route == "setup":
            is_open = bool((cfg.get("setup") or {}).get("hash")) and (cfg.get("setup") or {}).get("exp", 0) > time.time()
            if not is_open:
                if method == "POST":
                    self.close_connection = True
                return self._html(200, sign_in_page("That setup address has already been used." if method == "POST" else ""))
            if method != "POST":
                return self._html(200, setup_page())
            form = self._form()
            if not self._same_origin():
                return self._html(200, setup_page("That request did not come from this page."))
            locked = self._locked()
            if locked:
                return self._html(429, setup_page(f"Too many wrong tries. Try again in {-(-locked // 60)} minutes."))
            tok, pw = form.get("token") or "", form.get("password") or ""
            if not tok or not hmac.compare_digest(cfg["setup"]["hash"], hashlib.sha256(tok.encode()).hexdigest()):
                self._count_wrong()
                time.sleep(1)
                return self._html(200, setup_page("This is not the setup address you were given. Open the full address again."))
            if not MIN_PASSWORD <= len(pw) <= 1000:
                return self._html(200, setup_page(f"Use {MIN_PASSWORD} characters or more."))
            if pw != (form.get("again") or ""):
                return self._html(200, setup_page("The two passwords do not match."))
            with changed:
                cfg = _load("config")
                cfg["pass"] = _hash_password(pw)
                cfg["pass_set"] = dt.datetime.now().isoformat(timespec="seconds")
                cfg.pop("setup", None)                  # the setup address stops working here
                _save("config", cfg)
                _save("sessions", {})                   # any earlier sign-in ends
            return self._go_home((self._open_session(),))
        if route == "s/login.css":
            return self._static("login.css", "text/css")
        if route == "s/app.webmanifest":                 # the home-screen manifest and its icons: nothing personal, open before sign-in
            return self._static_bytes("app.webmanifest", "application/manifest+json")
        if route in ("s/icon-192.png", "s/icon-512.png"):
            return self._static_bytes(route[2:], "image/png")
        if route == "s/login.js":
            return self._static("login.js", "text/javascript")

        # everything below needs a signed-in session
        s = self._session()
        if s is None:
            if method == "POST":
                self.close_connection = True
            if route.startswith("api/"):
                return self._json(401, {"error": "sign in"})
            return self._go_home() if route else self._html(200, sign_in_page())
        if route == "s/app.css":
            return self._static("app.css", "text/css")
        if route == "s/app.js":
            return self._static("app.js", "text/javascript")
        if route.startswith("s/mod/") and route.count("/") == 3:       # a part of the page one of the owner's own mods brings
            _engine_path()
            import mods
            got = mods.page_file(route.split("/")[2], route.split("/")[3])
            if got:
                return self._send(200, got[0], got[1] + "; charset=utf-8", (("Cache-Control", "no-cache"),))
            return self._send(404, b"", "text/plain")
        if route in ("s/ec/event-calendar.min.js", "s/ec/event-calendar.min.css"):
            try:
                with open(os.path.join(EC, route[5:]), "rb") as f:
                    return self._send(200, f.read(), ("text/javascript" if route.endswith(".js") else "text/css") + "; charset=utf-8",
                                      (("Cache-Control", "public, max-age=86400"),))
            except OSError:
                return self._send(404, b"", "text/plain")
        if route == "manual" and method in ("GET", "HEAD"):        # "How your page works": behind the same sign-in as everything else
            try:
                with open(MANUAL, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8", csp=MANUAL_CSP)
            except OSError:
                return self._html(404, "<!doctype html><meta charset=utf-8><title>Not here yet</title><p style='font:16px system-ui;margin:2em'>The manual is not on this computer yet. It arrives with the next install or update.</p><p><a href=\"/\">Back to your page</a></p>")

        if route == "api/data" and method == "GET":
            have = self.headers.get("X-Brief-Have") or ""

            def etag():
                a, f = _answers(), _load("feed")
                return '"' + hashlib.sha1(f"{f.get('received')}|{a['v']}|{a['av']}|{files_mark()}|{s['csrf']}".encode()).hexdigest() + '"'
            with changed:
                end = time.time() + (HOLD_PAGE if self.headers.get("X-Brief-Wait") == "1" else 0)
                while have == etag() and time.time() < end:         # hold the page's line open until something changes
                    changed.wait(min(2.0, max(0.05, end - time.time())))
                tag = etag()
                if have == tag:
                    return self._send(304, b"", "application/json; charset=utf-8", (("ETag", tag),))
                docs = dict(_load("feed").get("docs") or {})
                if isinstance(docs.get("current"), dict):           # this computer serves its own page files: the mark is theirs
                    docs["current"] = dict(docs["current"], page_files=files_mark())
                out = {"csrf": s["csrf"], "etag": tag, "listening": True, "live": docs, "answers": dict(_answers()["items"])}
            return self._json(200, out, (("ETag", tag),))
        if route.startswith("api/mail"):
            return self._mail(route, method, s)
        if route.startswith("api/texts"):
            return self._texts(route, method, s)
        if route.startswith("api/mod/"):
            return self._mod(route, method, s)
        if route == "api/contacts" and method == "GET":               # Settings, Contacts: one page of people, read only
            _engine_path()
            import contacts_book
            q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            try:
                return self._json(200, contacts_book.page((q.get("q") or "")[:100], int(q.get("offset") or 0), int(q.get("limit") or 50)))
            except ValueError:
                return self._json(400, {"error": "bad page"})
            except Exception:  # noqa: BLE001  the database held by a pass: the page asks again
                return self._json(200, {"busy": True})
        if route == "api/calendar/events" and method == "GET":        # the Calendar part: the gathered events, read only
            live = os.path.join(os.path.dirname(HERE), "live")
            if live not in sys.path:
                sys.path.insert(0, live)
            import calendar_view
            return self._json(200, calendar_view.events())
        if route == "api/calendar/add" and method == "POST":           # his Save in the Calendar part's New event form
            body = self._body_json(PAGE_BODY)
            if body is None:
                return None
            if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                return self._json(403, {"error": "refused"})
            _engine_path()
            import calendar_view
            return self._json(200, calendar_view.add(body))
        if route in ("api/answer", "api/logout", "api/password", "api/signout_all") and method == "POST":
            body = self._body_json(PAGE_BODY)
            if body is None:
                return None
            if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                return self._json(403, {"error": "refused"})
            if route == "api/logout":
                with changed:
                    every = _load("sessions")
                    every.pop(s["id"], None)
                    _save("sessions", every)
                return self._json(200, {"ok": True}, (self._cookie("", 1),))
            if route == "api/signout_all":              # every sign-in on this page ends, this browser's too
                with changed:
                    _save("sessions", {})
                return self._json(200, {"ok": True}, (self._cookie("", 1),))
            if route == "api/password":                 # the present password, then the new one twice; never logged
                locked = self._locked()
                if locked:
                    return self._json(200, {"ok": False, "error": f"Too many wrong passwords. Try again in {-(-locked // 60)} minutes."})
                cur, new, again = (body.get(k) if isinstance(body.get(k), str) else "" for k in ("current", "new", "again"))
                cfg = _load("config")
                if not cfg.get("pass") or not cur or len(cur) > 1000 or not _password_ok(cur, cfg["pass"]):
                    self._count_wrong()
                    time.sleep(1)
                    return self._json(200, {"ok": False, "error": "The present password is not right."})
                if not MIN_PASSWORD <= len(new) <= 1000:
                    return self._json(200, {"ok": False, "error": f"Use {MIN_PASSWORD} characters or more for the new password."})
                if new != again:
                    return self._json(200, {"ok": False, "error": "The two new passwords do not match."})
                with changed:
                    cfg = _load("config")
                    cfg["pass"] = _hash_password(new)
                    cfg["pass_set"] = dt.datetime.now().isoformat(timespec="seconds")
                    _save("config", cfg)
                    every = _load("sessions")           # every other sign-in ends; this browser stays signed in
                    _save("sessions", {s["id"]: every[s["id"]]} if s["id"] in every else {})
                return self._json(200, {"ok": True})
            key = str(body.get("key") or "")
            if not re.fullmatch(r"[A-Za-z0-9_\-.~:@+]{1,180}", key):
                return self._json(400, {"error": "bad item"})
            rec, clean = body.get("record"), None
            if isinstance(rec, dict):
                if rec.get("action") not in ACTIONS:
                    return self._json(400, {"error": "bad action"})
                clean = {"sent": False}
                for f in ("id", "action", "label", "text", "until", "result", "at", "device", "item_title", "item_updated", "open_card",
                          "button", "meaning", "pick"):        # a choice button's id and meaning: the engine checks them (presses.chosen); pick: the card's pick was pressed
                    if isinstance(rec.get(f), str):
                        clean[f] = rec[f][:60000 if f == "text" else 4000]      # his words can be a whole email; the rest stay short
                if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", clean.get("at") or ""):
                    clean["at"] = dt.datetime.now().isoformat(timespec="seconds")
                clean.setdefault("id", key)
                q = rec.get("question")
                if isinstance(q, int) and not isinstance(q, bool) and 1 <= q <= 20:
                    clean["question"] = q                           # the numbered question on the card this answer is for
                r = rec.get("redo")
                if isinstance(r, int) and not isinstance(r, bool) and 1 <= r <= 20:
                    clean["redo"] = r                               # Change on one answered question: its place among them
                if isinstance(rec.get("calendar"), dict):           # the day and time he picked for a calendar item
                    c = {f: (rec["calendar"][f][:300] if isinstance(rec["calendar"].get(f), str) else None)
                         for f in ("title", "date", "start", "end", "location")}
                    if not re.fullmatch(r"\d{4}-\d\d-\d\d", c["date"] or ""):
                        return self._json(400, {"error": "bad day"})
                    if any(c[f] is not None and not re.fullmatch(r"\d\d:\d\d", c[f]) for f in ("start", "end")):
                        return self._json(400, {"error": "bad time"})
                    c["all_day"] = bool(rec["calendar"].get("all_day"))
                    c["accepted_as_shown"] = bool(rec["calendar"].get("accepted_as_shown"))
                    clean["calendar"] = c
                clean["status"] = "saved"                           # only the engine moves it on from here
            with changed:
                a, now = _answers(), time.time()
                # an Undo by the owner is remembered for 15 minutes so the listener can tell it from an answer the engine cleared
                a["undone"] = {k: u for k, u in a["undone"].items() if u.get("t", 0) > now - 900}
                if clean is None:
                    if key in a["items"]:
                        a["undone"][key] = {"at": str(a["items"][key].get("at") or ""), "t": now}
                    a["items"].pop(key, None)
                else:
                    a["items"][key] = clean
                    a["undone"].pop(key, None)
                a["v"] += 1
                a["av"] += 1
                _save("answers", a)
                changed.notify_all()
            return self._json(200, {"ok": True})
        if route:
            if method == "POST":
                self.close_connection = True
            return self._go_home()
        try:
            with open(os.path.join(APP, "shell.html"), encoding="utf-8") as f:
                shell = f.read()
        except OSError:
            shell = ""
        return self._html(200, page_head("Live Page", ["app.css"], ["app.js"]) + shell + "</body></html>")


    def _texts(self, route, method, s):
        """The Texts part's doors, for a signed-in browser. Reading is open to the session; every change (a send, a read mark, taking
        a queued text back, discarding a draft) needs the page's own address and its token, and a text is queued only by the owner's
        own Send press here: the Google Messages link (textlink.py) takes it from the queue, and nothing else queues one."""
        live = os.path.join(os.path.dirname(HERE), "live")
        if live not in sys.path:
            sys.path.insert(0, live)
        import texts
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try:
            if route == "api/texts" and method == "GET":
                return self._json(200, texts.conversations(q.get("q") or "", q.get("before") or "", q.get("limit") or 50))
            if route == "api/texts/status" and method == "GET":        # the Google Messages line for the Errors block, always as of now
                return self._json(200, {"ok": True, "problem": texts._problem()})
            if route == "api/texts/thread" and method == "GET":
                lim = q.get("limit") or ""
                return self._json(200, texts.thread(q.get("id") or "", min(max(int(lim), 20), 5000) if lim.isdigit() else 200,
                                                    q.get("before") or ""))       # a page of the newest, or the page before a given text
            if route == "api/texts/file" and method == "GET":        # a text's picture, shown in the conversation (or a file, to save)
                if not re.fullmatch(r"\d{1,12}", q.get("id") or ""):
                    return self._json(400, {"error": "bad file"})
                try:
                    name, saved, data = texts.picture(q["id"])
                except LookupError as e:
                    return self._json(404, {"ok": False, "error": str(e)})
                safe = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name)[:150] or "file"
                shown = VIEW_KINDS.get(os.path.splitext(saved.lower())[1])
                if shown and shown.startswith("image/"):
                    return self._send(200, data, shown, (("Content-Disposition", f"inline; filename=\"{safe}\""),), csp=VIEW_CSP, frame="SAMEORIGIN")
                return self._send(200, data, "application/octet-stream",
                                  (("Content-Disposition", f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(name)}"),))
            if route == "api/texts/outbox" and method == "GET":
                return self._json(200, {"ok": True, "sends": texts.outbox_for(q.get("id") or "")})
            if route.startswith("api/texts/link"):
                # signing in to Google Messages: the signed-in page at any of its own addresses (this computer, or its own private https
                # address), the same checks as Send: same origin and the page's check on every press; the cookies in the body only
                import textlink
                if route == "api/texts/link" and method == "GET":
                    return self._json(200, {"ok": True, "link": textlink.public(), "problem": texts._problem()})
                if method == "POST" and route in ("api/texts/link/signin", "api/texts/link/cancel", "api/texts/link/takeback"):
                    body = self._body_json(PAGE_BODY)
                    if body is None:
                        return None
                    if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                        return self._json(403, {"error": "refused"})
                    if route == "api/texts/link/signin":
                        return self._json(200, textlink.pair(body.get("cookies") or ""))
                    if route == "api/texts/link/takeback":          # his press of Take it back now: the pass's take-back, at once
                        return self._json(200, textlink.take_back())
                    return self._json(200, textlink.cancel_pair())
            if method == "POST" and route in ("api/texts/send", "api/texts/read", "api/texts/cancel", "api/texts/discard"):
                body = self._body_json(PAGE_BODY)
                if body is None:
                    return None
                if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                    return self._json(403, {"error": "refused"})
                if route == "api/texts/send":
                    return self._json(200, texts.queue_send(body.get("conv"), body.get("text"), body.get("to"), body.get("name")))
                if route == "api/texts/read":
                    return self._json(200, texts.mark_read(str(body.get("id") or "")))
                if route == "api/texts/cancel":
                    return self._json(200, texts.cancel(body.get("id")))
                return self._json(200, texts.discard_draft(body.get("id")))
        except texts.Busy:
            return self._json(200, {"ok": False, "busy": True})
        if method == "POST":
            self.close_connection = True
        return self._json(404, {"error": "no such door"})

    def _mail(self, route, method, s):
        """The Mail part's doors, for a signed-in browser: the list and search, one conversation, one file, and a file the
        owner adds from his computer. Reading only, except the upload (kept in the home, never sent by itself); every change
        to his mail is a press, through the answers like every other press."""
        mail = _engine_mail()
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try:
            if route == "api/mail" and method == "GET":
                return self._json(200, mail.rows(q.get("view") or "inbox", q.get("account") or "", (q.get("q") or "")[:300],
                                                 q.get("before") or "", q.get("limit") or 50, q.get("deep") == "1",
                                                 (q.get("folder") or "")[:300], q.get("fresh") == "1"))
            if route == "api/mail/folders" and method == "GET":
                return self._json(200, mail.folders((q.get("account") or "")[:200], q.get("fresh") == "1"))
            if route == "api/mail/rules" and method == "GET":
                import mail_rules
                return self._json(200, mail_rules.listing())
            if route == "api/mail/unsub" and method == "GET":       # does this email (or each of these) offer Unsubscribe? (mail_handle.py)
                import mail_handle
                if re.fullmatch(r"\d+(,\d+){0,24}", q.get("ids") or ""):
                    return self._json(200, mail_handle.lookups([int(x) for x in q["ids"].split(",")], q.get("fresh") == "1"))
                if not str(q.get("id") or "").isdigit():
                    return self._json(400, {"error": "bad email"})
                return self._json(200, mail_handle.lookup(int(q["id"]), q.get("fresh") == "1"))
            if route == "api/mail/pull_status" and method == "GET":
                return self._json(200, mail.pull_status())
            if route == "api/mail/thread" and method == "GET":
                if not re.fullmatch(r"\d{1,12}", q.get("id") or ""):
                    return self._json(400, {"error": "bad email"})
                return self._json(200, mail.thread(int(q["id"]), q.get("fresh") == "1"))
            if route == "api/mail/body" and method == "GET":         # the email as sent, shown in a frame that runs nothing
                if not re.fullmatch(r"\d{1,12}", q.get("id") or ""):
                    return self._json(400, {"error": "bad email"})
                pictures = q.get("pictures") == "1"
                got = mail.body_doc(int(q["id"]), pictures)
                if got is None:
                    return self._json(404, {"error": "no html"})
                return self._send(200, got[0], "text/html; charset=utf-8", csp=BODY_CSP_PICTURES if pictures else BODY_CSP,
                                  frame="SAMEORIGIN")
            if route == "api/mail/invite" and method == "GET":      # the meeting invite an email carries, if any (invites.py)
                if not (q.get("id") or "").isdigit():
                    return self._json(400, {"error": "bad email"})
                import invites
                return self._json(200, invites.show(int(q["id"])))
            if route == "api/mail/labels" and method == "GET":
                if not re.fullmatch(r"[^@\s<>,;\"']{1,200}@[^@\s<>,;\"']{1,200}", q.get("account") or ""):
                    return self._json(400, {"error": "bad mailbox"})
                return self._json(200, mail.labels(q["account"]))
            if route == "api/mail/sample" and method == "GET":
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", q.get("card") or "") or not re.fullmatch(r"\d{0,12}", q.get("id") or ""):
                    return self._json(400, {"error": "bad card"})
                return self._json(200, mail.sample(q["card"], int(q["id"]) if q.get("id") else None))
            if route == "api/mail/file" and method == "GET":
                ref = q.get("ref") or ""
                if not re.fullmatch(r"(att:\d{1,12}|msg:\d{1,12}:[^/\\]{1,200}|up:[0-9a-f]{24})", ref):
                    return self._json(400, {"error": "bad file"})
                try:
                    name, data = mail.file(ref)
                except LookupError as e:
                    return self._json(404, {"ok": False, "error": str(e)})
                safe = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name)[:150] or "file"
                shown = VIEW_KINDS.get(os.path.splitext(name.lower())[1]) if q.get("view") == "1" else None
                if shown:       # opened over the page as itself, inside the page's own frame only
                    return self._send(200, data, shown, (("Content-Disposition", f"inline; filename=\"{safe}\""),),
                                      csp=VIEW_CSP, frame="SAMEORIGIN")
                return self._send(200, data, "application/octet-stream",
                                  (("Content-Disposition", f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(name)}"),))
            if route == "api/mail/upload" and method == "POST":
                if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                    return self._json(403, {"error": "refused"})
                raw = self._body(UPLOAD_BODY)
                if raw is None:
                    return self._json(413, {"ok": False, "error": f"That file is larger than {mail.MOST_UPLOAD // 1_000_000} MB."})
                try:
                    return self._json(200, {"ok": True, "file": mail.upload(unquote(self.headers.get("X-File-Name") or "file"), raw)})
                except ValueError as e:
                    return self._json(200, {"ok": False, "error": str(e)})
            if route.startswith("api/mail/compose/") or route == "api/mail/suggest":
                return self._compose(route, method, q, s)
        except mail.Busy:
            return self._json(200, {"ok": False, "busy": True})
        if method == "POST":
            self.close_connection = True
        return self._json(404, {"error": "no such door"})


    def _compose(self, route, method, q, s):
        """Writing mail from the Mail part (mail_compose.py): the panel's starting point, address suggestions, signatures and
        kept drafts; and the owner's own Send press, which sends at once (so it must come from his signed-in page)."""
        _engine_mail()
        import mail_compose as mc
        if route == "api/mail/suggest" and method == "GET":
            return self._json(200, mc.suggest((q.get("q") or "")[:100]))
        if route == "api/mail/compose/config" and method == "GET":
            return self._json(200, mc.config())
        if route == "api/mail/compose/start" and method == "GET":
            if not re.fullmatch(r"\d{0,12}", q.get("id") or ""):
                return self._json(400, {"error": "bad email"})
            return self._json(200, mc.start(q.get("kind") or "new", q.get("id") or None))
        if route == "api/mail/compose/drafts" and method == "GET":
            return self._json(200, mc.drafts())
        if route == "api/mail/compose/draft" and method == "GET":
            return self._json(200, mc.draft(q.get("id") or ""))
        doors = {"api/mail/compose/send": mc.send, "api/mail/compose/save": mc.save_draft,
                 "api/mail/compose/drop": lambda b: mc.drop_draft(b.get("draft")),
                 "api/mail/compose/signature": lambda b: mc.set_signature(b.get("account"), b.get("html"))}
        if route in doors and method == "POST":
            body = self._body_json(PAGE_BODY)
            if body is None:
                return None
            if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                return self._json(403, {"error": "refused"})
            return self._json(200, doors[route](body if isinstance(body, dict) else {}))
        self.close_connection = True
        return self._json(404, {"error": "no such door"})


    def _mod(self, route, method, s):
        """A mod's own doors (mods.door), for its part of the page: reading for the signed-in browser; a POST only from this page's
        own address with its check, like every press."""
        _engine_path()
        import mods
        parts = route.split("/", 3)
        name, rest = parts[2], (parts[3] if len(parts) > 3 else "")
        if not mods.NAME_OK.match(name) or method not in ("GET", "POST"):
            return self._json(404, {"error": "no such door"})
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        body = None
        if method == "POST":
            body = self._body_json(PAGE_BODY)
            if body is None:
                return None
            if not self._same_origin() or not hmac.compare_digest(s["csrf"], self.headers.get("X-Brief-Csrf") or ""):
                return self._json(403, {"error": "refused"})
        got = mods.door(name, rest, method, q, body)
        if got is None:
            return self._json(404, {"error": "no such door"})
        return self._json(got[0], got[1])


def _engine_path():
    live = os.path.join(os.path.dirname(HERE), "live")
    if live not in sys.path:
        sys.path.insert(0, live)


def _engine_mail():
    """The engine's mail module, in this same program (the listener has the engine on its path)."""
    live = os.path.join(os.path.dirname(HERE), "live")
    if live not in sys.path:
        sys.path.insert(0, live)
    import mail
    import mail_cache
    mail_cache.enable()             # in the listener the Mail part reads its own small copy, never waiting on a pass (mail_cache.py)
    return mail


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 32
    _room = threading.BoundedSemaphore(MOST_AT_ONCE)

    def process_request(self, request, client_address):
        """Serve at most MOST_AT_ONCE requests at a time; one more than that is closed at once, unanswered."""
        if not self._room.acquire(blocking=False):
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._room.release()

    def handle_error(self, request, client_address):       # a broken connection is nobody's news: nothing is printed
        pass


def start():
    """Start serving on this computer's own address, in threads of the calling program. Returns the server."""
    os.makedirs(DATA, exist_ok=True)
    ensure_key()
    try:
        live = os.path.join(os.path.dirname(HERE), "live")
        if live not in sys.path:
            sys.path.insert(0, live)
        import texts_cache
        texts_cache.enable()            # the Texts part reads its own small copy of the texts here (quick search and list), never waiting on the database
    except Exception:  # noqa: BLE001  without it the texts are read from the database itself
        pass
    server = _Server(("127.0.0.1", publish.page_port()), Door)          # 127.0.0.1 only: no other device can connect
    threading.Thread(target=server.serve_forever, name="local-page", daemon=True).start()
    refresh_feed()
    return server


if __name__ == "__main__":
    if "--setup" in sys.argv:
        os.makedirs(DATA, exist_ok=True)
        where = make_setup(public="--public" in sys.argv)
        if "--open" in sys.argv:
            import webbrowser
            webbrowser.open(where)
            print("the one-time address was opened in the browser; it works once and for 7 days")
        else:
            print(f"one-time setup address, good for 7 days, for the owner only: {where}")
    else:
        print(__doc__)
