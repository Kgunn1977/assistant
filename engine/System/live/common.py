r"""Shared setup for the live system. Import this before anything from the engine.

THREE PARTS, KEPT APART
  general   this folder and the page's folder beside it: the code that is the
            same for anyone. It names no person, no company and no trade.
  personal  <home>\personal: who the owner is, what matters to them, which
            sources are on, their page's address and key, their settings.
            General code reads it through personal(); a missing file means the
            empty starter set, and everything still runs.
  taught    <home>\taught\<name>: add-ons made for one owner (connection types; see connections).
The home itself (database, items, answers, logs) is the owner's data.

Importing this module points everything at the home (see paths.py). The
assistant reads the owner's accounts through their connections and writes only
inside the home. The one thing it can send is an email the owner writes and
sends themself (send.py).
"""
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# This folder first, so the assistant's own modules are the ones every import finds.
sys.path[:] = [HERE] + [p for p in sys.path if os.path.normcase(os.path.abspath(p or ".")) != os.path.normcase(HERE)]
import paths  # noqa: E402

SYSTEM = paths.SYSTEM
ROOT = paths.ROOT
HOME = paths.HOME           # a test home can stand in for the real one: set ASSISTANT_LIVE_HOME
os.environ["ASSISTANT_LIVE_HOME"] = HOME
if os.environ.get("ASSISTANT_REPLAY") == "1":     # a replay's own programs: their web opener refuses anything that sends
    import replay_guard  # noqa: E402
    replay_guard.install()
PERSONAL = paths.PERSONAL
TAUGHT = paths.TAUGHT
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

# The scheduled job runs without a window. Children must not open one either,
# and must run under the console Python so their output can be captured.
if os.path.basename(sys.executable).lower() == "pythonw.exe":
    sys.executable = os.path.join(os.path.dirname(sys.executable), "python.exe")
_popen_init = subprocess.Popen.__init__


def _no_window(self, *args, **kwargs):
    # no window, and normal priority said outright: the scheduled task starts
    # the pass below normal, and a child would otherwise be started the same way
    # The no-window flag is added to whatever flags the caller passed, never replaced by them
    # (Windows refuses it together with a new console or a detached process, so those are left alone).
    flags = kwargs.get("creationflags") or 0
    if not flags & (getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) | getattr(subprocess, "DETACHED_PROCESS", 0x8)):
        flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    kwargs["creationflags"] = flags | getattr(subprocess, "NORMAL_PRIORITY_CLASS", 0x20)
    _popen_init(self, *args, **kwargs)


subprocess.Popen.__init__ = _no_window

LOGS = os.path.join(HOME, "logs")
PASS_LOG = os.path.join(LOGS, "pass.log")
AI_LOG = os.path.join(LOGS, "ai.jsonl")
PROMPTS = os.path.join(HERE, "prompts")
THINK_STATE = os.path.join(HOME, "think_state.json")
ALERTS_SENT = os.path.join(HOME, "alerts_sent.json")
LOCK = os.path.join(HOME, "pass.lock")
ITEMS_JSON = os.path.join(HOME, "items.json")
HEALTH_JSON = os.path.join(HOME, "health.json")
ANSWERS = os.path.join(HOME, "answers")
ANSWERS_APPLIED = os.path.join(ANSWERS, "applied")
SETTINGS = os.path.join(PERSONAL, "settings.json")
PERSONAL_JSON = os.path.join(PERSONAL, "personal.json")
IMPORTANT = os.path.join(PERSONAL, "Important.md")
PAGE_KEY = os.path.join(PERSONAL, "local_settings.json")     # the page's address and its key; never printed
PUBLISH = os.path.join(SYSTEM, "live_page", "publish.py")

DEFAULT_SETTINGS = {
    "alerts": {"server": "https://ntfy.sh", "topic": ""},
}
# The empty starter set: what the general part runs on when nobody has made it theirs yet.
STARTER = {
    "owner": "the owner",            # the name prompts and cards use for the person served
    "about": "",                     # one or two sentences on who they are and what they do, for the thinking calls
    "page_title": "Your desk",       # the page's heading
    "page_subtitle": "",             # the line under it
    "full_name": "",                 # the owner's whole name, as their own contact entry
    "sources": [],                   # which kinds of connection are read: any of email, calendar, sms, or a taught connection type's kind
    "own_domains": [],               # mail domains that are the owner's own (their company's); never junk
    "today_calendars": [],           # calendars whose events show in the page's Today; empty shows none
    "private_words": [],             # words that must never be written into the general part (names, companies)
}


CHANNELS = {"email": {"word": "email", "title": "Mail"}, "sms": {"word": "text", "title": "Text messages"},
            "calendar": {"word": "calendar", "title": "Calendar"}}
_channels = {}


def channels():
    """{kind: {"word", "title", "seconds"}} for every kind of source: the core's (mail, texts, calendar), then each connection
    type's own, an owner's taught one too (its KIND, and WORD, TITLE and SECONDS when it says them). Asked once per program."""
    if not _channels:
        out = {k: dict(v) for k, v in CHANNELS.items()}
        try:
            import connections
            for t in connections.types().values():
                k = getattr(t, "KIND", "")
                if k and k not in out:
                    out[k] = {"word": getattr(t, "WORD", getattr(t, "NAME", k)), "title": getattr(t, "TITLE", getattr(t, "NAME", k))}
                if k and getattr(t, "SECONDS", None):
                    out[k]["seconds"] = int(t.SECONDS)
        except Exception:  # noqa: BLE001  the core's kinds still stand
            pass
        _channels.update(out)
    return _channels


def channel_word(kind):
    """How a message of this kind is named in a line ("text", a connection type's WORD); the kind itself when none is known."""
    return (channels().get(kind) or {}).get("word") or str(kind or "")


def sender_kinds():
    """The prefixes a sender is named with ("email: Pat", "sms: ...", a connection type's own kind)."""
    return set(channels()) | {"text"}


def personal():
    """The owner's personal settings over the starter set. A missing or
    unreadable file is the starter set, so the general part always runs."""
    got = read_json(PERSONAL_JSON, None)
    out = dict(STARTER)
    if isinstance(got, dict):
        out.update({k: v for k, v in got.items() if v is not None})
    return out


def owner():
    return str(personal().get("owner") or STARTER["owner"])


def settings():
    """The settings file, made with defaults the first time."""
    if not os.path.exists(SETTINGS):
        write_json(SETTINGS, DEFAULT_SETTINGS)
    with open(SETTINGS, encoding="utf-8") as f:
        return json.load(f)


def important_lines():
    """The owner's list of what deserves a notification, one line per kind of thing. Empty when they have none."""
    try:
        with open(IMPORTANT, encoding="utf-8") as f:
            return [ln[1:].strip() for ln in f.read().splitlines() if ln.startswith("-")]
    except OSError:
        return []


def now():
    return dt.datetime.now()


AI_NOW = "ASSISTANT_NOW"        # the replay's day end (local time, ISO): the moment the AI is told it is, and the last moment it may see


def until():
    """The replay's day end while one runs (replay.py sets ASSISTANT_NOW for its own programs), else None."""
    got = os.environ.get(AI_NOW)
    try:
        return dt.datetime.fromisoformat(got) if got else None
    except ValueError:
        return None


def ai_now():
    """The moment the AI is told it is: the replay's day end while one runs, else the computer's clock. Record stamps stay on
    now(): the engine compares stamps it wrote with the database's own now(), and one shifted clock beside it would set them
    out of order."""
    return until() or dt.datetime.now()


def ai_today():
    return ai_now().date()


def replay_stored_before():
    """The moment the rebuild's days end: texts before it were stored by the day-by-day replay, which skips describing their
    pictures (they stay stored and shown). None when no replay has finished a day here."""
    st = read_json(os.path.join(paths.STATE, "replay", "state.json"), {}) or {}
    try:
        return dt.datetime.combine(dt.date.fromisoformat(str(st["last_done"])[:10]) + dt.timedelta(days=1), dt.time())
    except (KeyError, ValueError):
        return None


def describe_sql(column="m.ts"):
    """(" AND <column> >= ?", [moment]) leaving out pictures the replay stored, else ("", [])."""
    cut = replay_stored_before()
    return (f" AND {column} >= ?", [cut]) if cut else ("", [])


def until_sql(column="m.ts"):
    """(" AND <column> < ?", [day end]) while a replay runs, else ("", []): a later message is never shown to the AI."""
    u = until()
    return (f" AND {column} < ?", [u]) if u else ("", [])


def write_json(path, obj):
    """Whole file to a temp name, then renamed, so a reader never sees half."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(obj, f, indent=1, default=_plain)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _plain(o):
    if isinstance(o, (dt.datetime, dt.date)):
        return o.isoformat(timespec="seconds") if isinstance(o, dt.datetime) else o.isoformat()
    return str(o)


def rulebook():
    """The guardrails' checks (rules
ulebook.py), loaded by its own path: the name "rules" is also an older module in core."""
    import importlib.util
    m = sys.modules.get("assistant_rulebook")
    if m is None:
        spec = importlib.util.spec_from_file_location("assistant_rulebook", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", "rulebook.py"))
        m = importlib.util.module_from_spec(spec)
        sys.modules["assistant_rulebook"] = m
        spec.loader.exec_module(m)
    return m


def log_line(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{now():%Y-%m-%d %H:%M:%S} {text}\n")

