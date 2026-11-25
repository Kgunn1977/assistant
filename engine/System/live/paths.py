r"""Where everything is. The one place paths are written; import from here.

The general part is this folder (and the page's folder beside it). Everything
about one owner lives in the home: their database, rules, state, and the
personal folder with who they are, which accounts are connected and the locked
store that holds their sign-ins. This file names no person and no account; the
account tables below are read from the owner's personal folder.

A test home can stand in for the real one: set ASSISTANT_LIVE_HOME.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))        # the general part: the engine
SYSTEM = os.path.dirname(HERE)                           # holds this folder and the page's folder
ROOT = os.path.dirname(SYSTEM)
HOME = os.environ.get("ASSISTANT_LIVE_HOME") or os.path.join(ROOT, "Live")

PERSONAL = os.path.join(HOME, "personal")
TAUGHT = os.path.join(HOME, "taught")
RESOURCES = os.path.join(HOME, "Resources")
BRIEFINGS = os.path.join(HOME, "Briefings")
STATE = os.path.join(HOME, "state")

DB = os.path.join(RESOURCES, "Database", "assistant.duckdb")
ATTACHMENTS = os.path.join(RESOURCES, "Attachments")
RULES = os.path.join(RESOURCES, "Rules")                 # the owner's own rules, one document per subject
RULES_DRAFT = os.path.join(RULES, "Draft")
DATA = os.path.join(RESOURCES, "Data")                   # instances, never rules
JUNK_SENDERS = os.path.join(DATA, "Junk senders.md")

CORE = os.path.join(HERE, "core")                        # reading, judging and rules code
CONNECTIONS = os.path.join(HERE, "connections")          # one file per kind of connection
STARTER = os.path.join(HERE, "starter")                  # the empty rules documents and data a new home starts with
CORE_RULES = os.path.join(HERE, "core_rules")            # core rules (how the system works): read here, never copied into a home
GOALS = os.path.join(CORE_RULES, "Goals.md")
PROMPTS = os.path.join(HERE, "prompts")
# Older names for the same folders, kept so every caller reads one place.
CONFIG = MODULE_A = CONTRACTS = CORE
SHADOW = OUTPUT_ROOT = HOME

PERSONAL_JSON = os.path.join(PERSONAL, "personal.json")
CONNECTIONS_JSON = os.path.join(PERSONAL, "connections.json")   # which accounts are connected; no secrets
KEYS = os.path.join(PERSONAL, "keys.dat")                       # the locked store: sign-ins and keys
CREDENTIALS = os.path.join(PERSONAL, "signins")                 # reserved; nothing readable is kept here

SOURCE_TYPES = ("email", "sms", "calendar")
# Mail services anyone can have an address at: never one of the owner's "own" domains.
PUBLIC_MAIL = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
               "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            got = json.load(f)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


JOBS_JSON = os.path.join(PERSONAL, "jobs.json")


def job_names():
    """(pass job, listener job): the names of THIS copy's two scheduled jobs on this computer.

    Every copy of the assistant has its own pair, so two copies on one computer never start, stop or
    stand in for each other's. The names are the ones written in the owner's personal folder when
    setup made the jobs; before that, names made from where the home is. Anything that starts, stops
    or looks for a job uses this, never a name written out."""
    got = _read(JOBS_JSON)
    if got.get("pass") and got.get("listener"):
        return str(got["pass"]), str(got["listener"])
    import hashlib
    tag = hashlib.sha1(os.path.normcase(os.path.abspath(HOME)).encode("utf-8")).hexdigest()[:6]
    return f"Assistant live pass {tag}", f"Assistant live listener {tag}"


def personal():
    return _read(PERSONAL_JSON)


def connections():
    """The owner's connections that are switched on, as written in their personal folder."""
    return [c for c in _read(CONNECTIONS_JSON).get("connections") or []
            if isinstance(c, dict) and c.get("type") and c.get("id") and c.get("on", True)]


def accounts():
    """The owner's mail addresses: {address: {"mechanism": connection type, "sends": bool, "id": ...}}."""
    out = {}
    for c in connections():
        if c.get("kind") == "email" and c.get("address"):
            out[str(c["address"]).lower()] = {"mechanism": c["type"], "sends": bool(c.get("send")), "id": c["id"]}
    return out


def own_domains():
    """Domains that are the owner's own: named in their settings, or the domain of a connected address
    that is not a public mail service. Mail from these is never junk."""
    named = [str(d).lower().lstrip("@") for d in personal().get("own_domains") or [] if d]
    found = [a.split("@")[-1] for a in accounts() if a.split("@")[-1] not in PUBLIC_MAIL]
    return tuple(dict.fromkeys(named + found))


def owner_name():
    me = personal()
    return str(me.get("full_name") or me.get("owner") or "the owner")


ACCOUNTS = accounts()
OWN_DOMAINS = own_domains()
TIMEZONE = str(personal().get("timezone") or "")
