r"""Connections: the ways the assistant reaches an owner's accounts.

One file in this folder per KIND of connection (Microsoft work mail, Google
mail, Google calendar). The files ship
with the product and name nobody. WHICH accounts are connected, their addresses
and their sign-ins belong to the owner: the list is connections.json in their
personal folder, and every secret (a sign-in, a token, an app secret) is in the
locked key store beside it (keys.py), never in a file a person or a program
can read.

The shape of a connection type, and how to add one, is in CONNECTIONS.md here.
An add-on made for one owner goes in <home>\taught\connections\ instead and
is found the same way.

    types()                 {type name: module} for every connection type
    module(type)            one type's module
    listed(kind=None)       the owner's connections that are on
    save(conn) / remove(id) write the owner's list
    secret(conn, name)      read one of a connection's secrets from the locked store
    put_secret(conn, name, value)
    send(address, ...)      send one email from the owner's connection with that address
    send_mime(address, raw, thread)   send one complete email the engine built (a reply, a forward, a new email)
    mailbox(address)        (connection, its type module) for the owner's mail account with that address
    can(conn)               the mail actions a mail connection can do now: {"archive", "trash", "label", "read"}
    note_granted(conn, scope)   what the provider says this sign-in allows (not a secret), kept for can()
    people(kind)            the people a kind of connection knows by id (for names)
"""
import importlib.util
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.dirname(HERE)
if LIVE not in sys.path:
    sys.path.insert(0, LIVE)
import paths  # noqa: E402

_modules = {}
ID = re.compile(r"^c[0-9]{1,4}$")


def _folders():
    return [HERE, os.path.join(paths.TAUGHT, "connections")]


def types():
    """Every connection type there is: this folder's, then the owner's taught ones."""
    out = {}
    for folder in _folders():
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".py") or name.startswith("_") or name in ("run.py",):
                continue
            key = name[:-3]
            if key in out:
                continue
            try:
                out[key] = _load(key, os.path.join(folder, name))
            except Exception as e:  # noqa: BLE001  one broken add-on must not hide the rest
                print(f"connection type {key} could not be loaded: {type(e).__name__}: {e}", file=sys.stderr)
    return out


def _load(key, path):
    if path not in _modules:
        spec = importlib.util.spec_from_file_location(f"connection_{key}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for need in ("TYPE", "NAME", "KIND", "SETUP", "gather"):
            if not hasattr(mod, need):
                raise ValueError(f"{os.path.basename(path)} has no {need}")
        _modules[path] = mod
    return _modules[path]


def module(type_name):
    for folder in _folders():
        path = os.path.join(folder, f"{type_name}.py")
        if os.path.exists(path):
            return _load(type_name, path)
    raise KeyError(f"there is no connection type called {type_name}")


# --- the owner's list ---------------------------------------------------------------
def _file():
    try:
        with open(paths.CONNECTIONS_JSON, encoding="utf-8") as f:
            got = json.load(f)
    except (OSError, ValueError):
        got = {}
    got.setdefault("apps", {})
    got.setdefault("connections", [])
    return got


def _write(data):
    os.makedirs(paths.PERSONAL, exist_ok=True)
    tmp = paths.CONNECTIONS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, paths.CONNECTIONS_JSON)


def listed(kind=None, everything=False):
    """The owner's connections that are switched on (all of them with everything=True)."""
    gone = ("phone_texts",)         # a type that no longer exists (texts come only through the Google Messages link, never phone backups): a connection left in the list is ignored, not an error
    return [c for c in _file()["connections"]
            if c.get("type") not in gone and (everything or c.get("on", True)) and (kind is None or c.get("kind") == kind)]


def get(conn_id):
    for c in _file()["connections"]:
        if c.get("id") == conn_id:
            return c
    return None


def new_id():
    used = {c.get("id") for c in _file()["connections"]}
    n = 1
    while f"c{n}" in used:
        n += 1
    return f"c{n}"


def save(conn):
    """Add or replace one connection in the owner's list. Never holds a secret."""
    if not ID.match(str(conn.get("id") or "")):
        raise ValueError("a connection needs an id like c1")
    conn["kind"] = module(conn["type"]).KIND
    data = _file()
    data["connections"] = [c for c in data["connections"] if c.get("id") != conn["id"]] + [conn]
    data["connections"].sort(key=lambda c: int(c["id"][1:]))
    _write(data)
    return conn


def remove(conn_id):
    """Take a connection off the list and forget its secrets."""
    import keys
    data = _file()
    data["connections"] = [c for c in data["connections"] if c.get("id") != conn_id]
    _write(data)
    for name in keys.names():
        if name.startswith(conn_id + "_"):
            keys.forget(name)


def app(name):
    """The owner's own registration with a provider (its public id and the like); the secret half is in the store."""
    return dict(_file()["apps"].get(name) or {})


def app_asks(name):
    """What setup asks once for a provider registration: the APP_ASKS of whichever type declares them."""
    for mod in types().values():
        if getattr(mod, "APP", None) == name and getattr(mod, "APP_ASKS", None):
            return list(mod.APP_ASKS)
    return []


def app_ready(name):
    """True when every answer the registration needs is on file (plain ones in the list, secret ones locked)."""
    have = app(name)
    return all((secret("app_" + name, a["key"].replace("client_", "")) if a.get("secret") else have.get(a["key"]))
               for a in app_asks(name))


def save_app(name, values):
    data = _file()
    data["apps"][name] = dict(values)
    _write(data)


# --- secrets ------------------------------------------------------------------------
class _Lock:
    """One writer to the key store at a time, across processes."""

    def __enter__(self):
        self.path = paths.KEYS + ".lock"
        os.makedirs(paths.PERSONAL, exist_ok=True)
        end = time.time() + 20
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 60:      # left by a process that died
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() > end:
                    raise TimeoutError("the key store is busy")
                time.sleep(0.1)

    def __exit__(self, *_a):
        os.close(self.fd)
        try:
            os.remove(self.path)
        except OSError:
            pass


def secret(conn, name):
    """One secret of a connection (or of an app registration when conn is "app_<name>"), or None."""
    import keys
    return keys.get(f"{conn if isinstance(conn, str) else conn['id']}_{name}")


def put_secret(conn, name, value):
    import keys
    with _Lock():
        keys.set_(f"{conn if isinstance(conn, str) else conn['id']}_{name}", value)


# --- used by the rest of the engine ---------------------------------------------------
def send(address, to, cc, subject, body, files=()):
    """Send one email from the owner's connection with this address. Raises when it cannot."""
    import replay_guard
    replay_guard.refuse("sending an email")
    for c in listed("email"):
        if str(c.get("address") or "").lower() == str(address).lower() and c.get("send"):
            mod = module(c["type"])
            if not getattr(mod, "CAN_SEND", False):
                break
            return mod.send(c, list(to), list(cc), subject, body, list(files))
    raise RuntimeError(f"{address} is not a connected account that can send")


def send_mime(address, raw, thread_id=None):
    """Send one complete email (bytes, built by the engine's mail.py) from the owner's connection with this address.
    Raises when it cannot. The message carries its own To, Cc and Bcc; the provider delivers to all of them."""
    import replay_guard
    replay_guard.refuse("sending an email")
    conn, mod = mailbox(address)
    if conn is None or not conn.get("send") or not getattr(mod, "CAN_SEND", False):
        raise RuntimeError(f"{address} is not a connected account that can send")
    if not hasattr(mod, "send_mime"):
        raise NotImplementedError(f"the {mod.NAME} connection cannot send a built email")
    return mod.send_mime(conn, raw, thread_id)


def mailbox(address):
    """(connection, its type module) for the owner's mail connection with this address, or (None, None)."""
    for c in listed("email"):
        if str(c.get("address") or "").lower() == str(address or "").strip().lower():
            return c, module(c["type"])
    return None, None


MAIL_ACTS = ("archive", "trash", "label", "read")
_GRANTED = None


def _granted_file():
    return os.path.join(paths.STATE, "granted_scopes.json")


def note_granted(conn, scope):
    """Keep what the provider says a sign-in allows (a list of permission names, never a secret)."""
    global _GRANTED
    cid = conn if isinstance(conn, str) else conn.get("id")
    have = _granted()
    if have.get(cid) == scope:
        return
    have[cid] = scope
    _GRANTED = have
    try:
        os.makedirs(paths.STATE, exist_ok=True)
        with open(_granted_file() + ".tmp", "w", encoding="utf-8") as f:
            json.dump(have, f, indent=1)
        os.replace(_granted_file() + ".tmp", _granted_file())
    except OSError:
        pass


def _granted():
    global _GRANTED
    if _GRANTED is None:
        try:
            with open(_granted_file(), encoding="utf-8") as f:
                _GRANTED = json.load(f) or {}
        except (OSError, ValueError):
            _GRANTED = {}
    return dict(_GRANTED)


def can(conn):
    """{"archive", "trash", "label", "read": True or False} for one mail connection: what its type can do, and, when the
    type names the permission it needs (ACT_SCOPE), whether the sign-in on this computer allows it. Not known yet counts as yes;
    a refused action then says so plainly."""
    mod = module(conn["type"])
    acts = set(getattr(mod, "CAN_ACT", ()) or ())
    need = getattr(mod, "ACT_SCOPE", None)
    scope = _granted().get(conn.get("id"))
    allowed = True if not need or scope is None else any(n in str(scope).split() for n in ([need] if isinstance(need, str) else need))
    return {a: (a in acts and allowed) for a in MAIL_ACTS}


def people(kind):
    """{id: {"name", "email", "is_bot", "deleted"}} from every connection of a kind that can list people."""
    out = {}
    for c in listed(kind):
        fn = getattr(module(c["type"]), "people", None)
        if fn:
            try:
                out.update(fn(c))
            except Exception:  # noqa: BLE001  names are a nicety; never stop a pass for them
                pass
    return out
